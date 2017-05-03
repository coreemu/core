"""
session.py: defines the Session class used by the core-daemon daemon program
that manages a CORE session.
"""

import atexit
import os
import random
import shlex
import shutil
import subprocess
import tempfile
import threading
import time

import pwd

from core import constants
from core.api import coreapi
from core.broker import CoreBroker
from core.conf import Configurable
from core.conf import ConfigurableManager
from core.data import ConfigData
from core.data import EventData
from core.data import ExceptionData
from core.data import FileData
from core.emane.emanemanager import EmaneManager
from core.enumerations import ConfigDataTypes
from core.enumerations import ConfigFlags
from core.enumerations import ConfigTlvs
from core.enumerations import EventTypes
from core.enumerations import ExceptionLevels
from core.enumerations import MessageFlags
from core.enumerations import MessageTypes
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs
from core.location import CoreLocation
from core.misc import log
from core.misc import nodeutils
from core.misc import utils
from core.misc.event import EventLoop
from core.misc.ipaddress import MacAddress
from core.mobility import BasicRangeModel
from core.mobility import MobilityManager
from core.mobility import Ns2ScriptedMobility
from core.netns import nodes
from core.sdt import Sdt
from core.service import CoreServices
from core.xen.xenconfig import XenConfigManager
from core.xml.xmlsession import save_session_xml

logger = log.get_logger(__name__)


class HookManager(object):
    """
    Manages hooks that can be ran as part of state changes.
    """

    def __init__(self, hook_dir):
        """
        Creates a HookManager instance.

        :param str hook_dir: the hook directory
        """
        self.hook_dir = hook_dir
        self.hooks = {}

    def add(self, hook_type, file_name, source_name, data):
        """
        Adds a hook to the manager.

        :param str hook_type: hook type
        :param str file_name: file name for hook
        :param str source_name: source name for hook
        :param data: data for hook
        :return: nothing
        """
        logger.info("setting state hook: %s - %s from %s", hook_type, file_name, source_name)

        hook_id, state = hook_type.split(":")[:2]
        if not state.isdigit():
            logger.error("error setting hook having state: %s", state)
            return

        state = int(state)
        hook = file_name, data

        # append hook to current state hooks
        state_hooks = self.hooks.setdefault(state, [])
        state_hooks.append(hook)

    def clear(self):
        """
        Clear all known hooks.

        :return: nothing
        """
        self.hooks.clear()

    def state_change(self, state, environment):
        """
        Mark a state change to notify related hooks to run with the provided environment.

        :param int state: the new state after a change
        :param dict environment: environment to run hook in
        :return: nothing
        """
        # retrieve all state hooks
        hooks = self.hooks.get(state, [])

        if not hooks:
            logger.info("no state hooks for state: %s", state)

        # execute all state hooks
        for hook in hooks:
            self.run(hook, environment)

    def run(self, hook, environment):
        """
        Run a hook, with a provided environment.

        :param tuple hook: hook to run
        :param dict environment: environment to run hook with
        :return:
        """
        file_name, data = hook
        logger.info("running hook: %s", file_name)
        hook_file_name = os.path.join(self.hook_dir, file_name)

        # write data to hook file
        try:
            hook_file = open(hook_file_name, "w")
            hook_file.write(data)
            hook_file.close()
        except IOError:
            logger.exception("error writing hook: %s", file_name)

        # setup hook stdout and stderr
        try:
            stdout = open(hook_file_name + ".log", "w")
            stderr = subprocess.STDOUT
        except IOError:
            logger.exception("error setting up hook stderr and stdout: %s", hook_file_name)
            stdout = None
            stderr = None

        # execute hook file
        try:
            stdin = open(os.devnull, "r")
            command = ["/bin/sh", file_name]
            subprocess.check_call(command, stdin=stdin, stdout=stdout, stderr=stderr,
                                  close_fds=True, cwd=self.hook_dir, env=environment)
        except subprocess.CalledProcessError:
            logger.exception("error running hook '%s'", file_name)


class SessionManager(object):
    """
    Manages currently known sessions.
    """
    sessions = set()
    session_lock = threading.Lock()

    @classmethod
    def add(cls, session):
        """
        Add a session to the manager.

        :param Session session: session to add
        :return: nothing
        """
        with cls.session_lock:
            logger.info("adding session to manager: %s", session.session_id)
            cls.sessions.add(session)

    @classmethod
    def remove(cls, session):
        """
        Remove session from the manager.

        :param Session session: session to remove
        :return: nothing
        """
        with cls.session_lock:
            logger.info("removing session from manager: %s", session.session_id)
            if session in cls.sessions:
                cls.sessions.remove(session)
            else:
                logger.info("session was already removed: %s", session.session_id)

    @classmethod
    def on_exit(cls):
        """
        Method used to shutdown all currently known sessions, in case of unexpected exit.

        :return: nothing
        """
        logger.info("caught program exit, shutting down all known sessions")
        while cls.sessions:
            with cls.session_lock:
                session = cls.sessions.pop()
            logger.error("WARNING: automatically shutting down non-persistent session %s - %s",
                         session.session_id, session.name)
            session.shutdown()


class Session(object):
    """
    CORE session manager.
    """

    def __init__(self, session_id, config=None, server=None, persistent=False, mkdir=True):
        """
        Create a Session instance.

        :param int session_id: session id
        :param dict config: session configuration
        :param core.coreserver.CoreServer server: core server object
        :param bool persistent: flag is session is considered persistent
        :param bool mkdir: flag to determine if a directory should be made
        """
        self.session_id = session_id

        # dict of configuration items from /etc/core/core.conf config file
        if not config:
            config = {}
        self.config = config

        # define and create session directory when desired
        self.session_dir = os.path.join(tempfile.gettempdir(), "pycore.%s" % self.session_id)
        if mkdir:
            os.mkdir(self.session_dir)

        self.name = None
        self.file_name = None
        self.thumbnail = None
        self.user = None
        self._state_time = time.time()
        self.event_loop = EventLoop()

        # dict of objects: all nodes and nets
        self.objects = {}
        self._objects_lock = threading.Lock()

        # dict of configurable objects
        self.config_objects = {}
        self._config_objects_lock = threading.Lock()

        # TODO: should the default state be definition?
        self.state = EventTypes.NONE.value
        self._state_file = os.path.join(self.session_dir, "state")

        self._hooks = {}
        self._state_hooks = {}

        self.add_state_hook(state=EventTypes.RUNTIME_STATE.value, hook=self.runtime_state_hook)

        # TODO: remove this server reference
        self.server = server

        if not persistent:
            SessionManager.add(self)

        self.master = False

        # setup broker
        self.broker = CoreBroker(session=self)
        self.add_config_object(CoreBroker.name, CoreBroker.config_type, self.broker.configure)

        # setup location
        self.location = CoreLocation()
        self.add_config_object(CoreLocation.name, CoreLocation.config_type, self.location.configure)

        # setup mobiliy
        self.mobility = MobilityManager(session=self)
        self.add_config_object(MobilityManager.name, MobilityManager.config_type, self.mobility.configure)
        self.add_config_object(BasicRangeModel.name, BasicRangeModel.config_type, BasicRangeModel.configure_mob)
        self.add_config_object(Ns2ScriptedMobility.name, Ns2ScriptedMobility.config_type,
                               Ns2ScriptedMobility.configure_mob)

        # setup services
        self.services = CoreServices(session=self)
        self.add_config_object(CoreServices.name, CoreServices.config_type, self.services.configure)

        # setup emane
        self.emane = EmaneManager(session=self)
        self.add_config_object(EmaneManager.name, EmaneManager.config_type, self.emane.configure)

        # setup xen
        self.xen = XenConfigManager(session=self)
        self.add_config_object(XenConfigManager.name, XenConfigManager.config_type, self.xen.configure)

        # setup sdt
        self.sdt = Sdt(session=self)

        # future parameters set by the GUI may go here
        self.options = SessionConfig(session=self)
        self.add_config_object(SessionConfig.name, SessionConfig.config_type, self.options.configure)
        self.metadata = SessionMetaData()
        self.add_config_object(SessionMetaData.name, SessionMetaData.config_type, self.metadata.configure)

        # handlers for broadcasting information
        self.event_handlers = []
        self.exception_handlers = []
        self.node_handlers = []
        self.link_handlers = []
        self.file_handlers = []
        self.config_handlers = []

    def shutdown(self):
        """
        Shutdown all emulation objects and remove the session directory.
        """

        # shutdown emane
        self.emane.shutdown()

        # shutdown broker
        self.broker.shutdown()

        # shutdown NRL's SDT3D
        self.sdt.shutdown()

        # delete all current objects
        self.delete_objects()

        preserve = False
        if hasattr(self.options, "preservedir") and self.options.preservedir == "1":
            preserve = True

        # remove this sessions working directory
        if not preserve:
            shutil.rmtree(self.session_dir, ignore_errors=True)

        # remove session from server if one was provided
        if self.server:
            self.server.remove_session(self)

        # remove this session from the manager
        SessionManager.remove(self)

    def broadcast_event(self, event_data):
        """
        Handle event data that should be provided to event handler.

        :param core.data.EventData event_data: event data to send out
        :return: nothing
        """

        for handler in self.event_handlers:
            handler(event_data)

    def broadcast_exception(self, exception_data):
        """
        Handle exception data that should be provided to exception handlers.

        :param core.data.ExceptionData exception_data: exception data to send out
        :return: nothing
        """

        for handler in self.exception_handlers:
            handler(exception_data)

    def broadcast_node(self, node_data):
        """
        Handle node data that should be provided to node handlers.

        :param core.data.ExceptionData node_data: node data to send out
        :return: nothing
        """

        for handler in self.node_handlers:
            handler(node_data)

    def broadcast_file(self, file_data):
        """
        Handle file data that should be provided to file handlers.

        :param core.data.FileData file_data: file data to send out
        :return: nothing
        """

        for handler in self.file_handlers:
            handler(file_data)

    def broadcast_config(self, config_data):
        """
        Handle config data that should be provided to config handlers.

        :param core.data.ConfigData config_data: config data to send out
        :return: nothing
        """

        for handler in self.config_handlers:
            handler(config_data)

    def broadcast_link(self, link_data):
        """
        Handle link data that should be provided to link handlers.

        :param core.data.ExceptionData link_data: link data to send out
        :return: nothing
        """

        for handler in self.link_handlers:
            handler(link_data)

    def set_state(self, state, send_event=False):
        """
        Set the session's current state.

        :param EventTypes state: state to set to
        :param send_event: if true, generate core API event messages
        :return: nothing
        """
        state_name = coreapi.state_name(state)

        if self.state == state:
            logger.info("session is already in state: %s, skipping change", state_name)
            return []

        self.state = state
        self._state_time = time.time()
        logger.info("changing session %s to state %s(%s) at %s",
                    self.session_id, state, state_name, self._state_time)

        self.write_state(state)
        self.run_hooks(state)
        self.run_state_hooks(state)

        if send_event:
            event_data = EventData(
                event_type=state,
                time="%s" % time.time()
            )
            self.broadcast_event(event_data)
            # TODO: append data to replies? convert replies to data?
            # replies.append(event_data)

            # send event message to connected handlers (e.g. GUI)
            # if self.is_connected():
            # try:
            #     if return_event:
            #         replies.append(message)
            #     else:
            #         self.broadcast_raw(None, message)
            # except IOError:
            #     logger.exception("error broadcasting event message: %s", message)

            # also inform slave servers
            # TODO: deal with broker, potentially broker should really live within the core server/handlers
            # self.broker.handlerawmsg(message)

    def write_state(self, state):
        """
        Write the current state to a state file in the session dir.

        :param int state: state to write to file
        :return: nothing
        """
        try:
            state_file = open(self._state_file, "w")
            state_file.write("%d %s\n" % (state, coreapi.state_name(state)))
            state_file.close()
        except IOError:
            logger.exception("error writing state file: %s", state)

    def run_hooks(self, state):
        """
        Run hook scripts upon changing states. If hooks is not specified, run all hooks in the given state.

        :param int state: state to run hooks for
        :return: nothing
        """

        # check that state change hooks exist
        if state not in self._hooks:
            return

        # retrieve all state hooks
        hooks = self._hooks.get(state, [])

        # execute all state hooks
        for hook in hooks:
            self.run_hook(hook)
        else:
            logger.info("no state hooks for %s", state)

    def set_hook(self, hook_type, file_name, source_name, data):
        """
        Store a hook from a received file message.

        :param str hook_type: hook type
        :param str file_name: file name for hook
        :param str source_name: source name
        :param data: hook data
        :return: nothing
        """
        logger.info("setting state hook: %s - %s from %s", hook_type, file_name, source_name)

        hook_id, state = hook_type.split(':')[:2]
        if not state.isdigit():
            logger.error("error setting hook having state '%s'", state)
            return

        state = int(state)
        hook = file_name, data

        # append hook to current state hooks
        state_hooks = self._hooks.setdefault(state, [])
        state_hooks.append(hook)

        # immediately run a hook if it is in the current state
        # (this allows hooks in the definition and configuration states)
        if self.state == state:
            logger.info("immediately running new state hook")
            self.run_hook(hook)

    def del_hooks(self):
        """
        Clear the hook scripts dict.
        """
        self._hooks.clear()

    def run_hook(self, hook):
        """
        Run a hook.

        :param tuple hook: hook to run
        :return: nothing
        """
        file_name, data = hook
        logger.info("running hook %s", file_name)

        # write data to hook file
        try:
            hook_file = open(os.path.join(self.session_dir, file_name), "w")
            hook_file.write(data)
            hook_file.close()
        except IOError:
            logger.exception("error writing hook '%s'", file_name)

        # setup hook stdout and stderr
        try:
            stdout = open(os.path.join(self.session_dir, file_name + ".log"), "w")
            stderr = subprocess.STDOUT
        except IOError:
            logger.exception("error setting up hook stderr and stdout")
            stdout = None
            stderr = None

        # execute hook file
        try:
            subprocess.check_call(["/bin/sh", file_name], stdin=open(os.devnull, 'r'),
                                  stdout=stdout, stderr=stderr, close_fds=True,
                                  cwd=self.session_dir, env=self.get_environment())
        except subprocess.CalledProcessError:
            logger.exception("error running hook '%s'", file_name)

    def run_state_hooks(self, state):
        """
        Run state hooks.

        :param int state: state to run hooks for
        :return: nothing
        """
        for hook in self._state_hooks.get(state, []):
            try:
                hook(state)
            except:
                message = "exception occured when running %s state hook: %s" % (coreapi.state_name(state), hook)
                logger.exception(message)
                self.exception(
                    ExceptionLevels.ERROR,
                    "Session.run_state_hooks",
                    None,
                    message
                )

    def add_state_hook(self, state, hook):
        """
        Add a state hook.

        :param int state: state to add hook for
        :param func hook: hook callback for the state
        :return: nothing
        """
        hooks = self._state_hooks.setdefault(state, [])
        assert hook not in hooks
        hooks.append(hook)

        if self.state == state:
            hook(state)

    def del_state_hook(self, state, hook):
        """
        Delete a state hook.

        :param int state: state to delete hook for
        :param func hook: hook to delete
        :return:
        """
        hooks = self._state_hooks.setdefault(state, [])
        hooks.remove(hook)

    def runtime_state_hook(self, state):
        """
        Runtime state hook check.

        :param int state: state to check
        :return: nothing
        """
        if state == EventTypes.RUNTIME_STATE.value:
            self.emane.poststartup()
            xml_file_version = self.get_config_item("xmlfilever")
            if xml_file_version in ('1.0',):
                xml_file_name = os.path.join(self.session_dir, "session-deployed.xml")
                save_session_xml(self, xml_file_name, xml_file_version)

    def get_environment(self, state=True):
        """
        Get an environment suitable for a subprocess.Popen call.
        This is the current process environment with some session-specific
        variables.

        :param bool state: flag to determine if session state should be included
        :return:
        """
        env = os.environ.copy()
        env["SESSION"] = "%s" % self.session_id
        env["SESSION_SHORT"] = "%s" % self.short_session_id()
        env["SESSION_DIR"] = "%s" % self.session_dir
        env["SESSION_NAME"] = "%s" % self.name
        env["SESSION_FILENAME"] = "%s" % self.file_name
        env["SESSION_USER"] = "%s" % self.user
        env["SESSION_NODE_COUNT"] = "%s" % self.get_node_count()

        if state:
            env["SESSION_STATE"] = "%s" % self.state

        # attempt to read and add environment config file
        environment_config_file = os.path.join(constants.CORE_CONF_DIR, "environment")
        try:
            if os.path.isfile(environment_config_file):
                utils.readfileintodict(environment_config_file, env)
        except IOError:
            logger.exception("error reading environment configuration file: %s", environment_config_file)

        # attempt to read and add user environment file
        if self.user:
            environment_user_file = os.path.join("/home", self.user, ".core", "environment")
            try:
                utils.readfileintodict(environment_user_file, env)
            except IOError:
                logger.exception("error reading user core environment settings file: %s", environment_user_file)

        return env

    def set_thumbnail(self, thumb_file):
        """
        Set the thumbnail filename. Move files from /tmp to session dir.

        :param str thumb_file: tumbnail file to set for session
        :return: nothing
        """
        if not os.path.exists(thumb_file):
            logger.error("thumbnail file to set does not exist: %s", thumb_file)
            self.thumbnail = None
            return

        destination_file = os.path.join(self.session_dir, os.path.basename(thumb_file))
        shutil.copy(thumb_file, destination_file)
        self.thumbnail = destination_file

    def set_user(self, user):
        """
        Set the username for this session. Update the permissions of the
        session dir to allow the user write access.

        :param str user: user to give write permissions to for the session directory
        :return: nothing
        """
        if user:
            try:
                uid = pwd.getpwnam(user).pw_uid
                gid = os.stat(self.session_dir).st_gid
                os.chown(self.session_dir, uid, gid)
            except IOError:
                logger.exception("failed to set permission on %s", self.session_dir)

        self.user = user

    def get_object_id(self):
        """
        Return a unique, new random object id.
        """
        object_id = None

        with self._objects_lock:
            while True:
                object_id = random.randint(1, 0xFFFF)
                if object_id not in self.objects:
                    break

        return object_id

    def add_object(self, cls, *clsargs, **clskwds):
        """
        Add an emulation object.

        :param class cls: object class to add
        :param list clsargs: list of arguments for the class to create
        :param dict clskwds: dictionary of arguments for the class to create
        :return: the created class instance
        """
        obj = cls(self, *clsargs, **clskwds)

        self._objects_lock.acquire()
        if obj.objid in self.objects:
            self._objects_lock.release()
            obj.shutdown()
            raise KeyError("duplicate object id %s for %s" % (obj.objid, obj))
        self.objects[obj.objid] = obj
        self._objects_lock.release()

        return obj

    def get_object(self, object_id):
        """
        Get an emulation object.

        :param int object_id: object id to retrieve
        :return: object for the given id
        """
        if object_id not in self.objects:
            raise KeyError("unknown object id %s" % object_id)
        return self.objects[object_id]

    def get_object_by_name(self, name):
        """
        Get an emulation object using its name attribute.

        :param str name: name of object to retrieve
        :return: object for the name given
        """
        with self._objects_lock:
            for obj in self.objects.itervalues():
                if hasattr(obj, "name") and obj.name == name:
                    return obj
        raise KeyError("unknown object with name %s" % name)

    def delete_object(self, object_id):
        """
        Remove an emulation object.

        :param int object_id: object id to remove
        :return: nothing
        """
        with self._objects_lock:
            try:
                obj = self.objects.pop(object_id)
                obj.shutdown()
            except KeyError:
                logger.error("failed to remove object, object with id was not found: %s", object_id)

    def delete_objects(self):
        """
        Clear the objects dictionary, and call shutdown for each object.
        """
        with self._objects_lock:
            while self.objects:
                _, obj = self.objects.popitem()
                obj.shutdown()

    def write_objects(self):
        """
        Write objects to a 'nodes' file in the session dir.
        The 'nodes' file lists: number, name, api-type, class-type
        """
        try:
            nodes_file = open(os.path.join(self.session_dir, "nodes"), "w")
            with self._objects_lock:
                for object_id in sorted(self.objects.keys()):
                    obj = self.objects[object_id]
                    nodes_file.write("%s %s %s %s\n" % (object_id, obj.name, obj.apitype, type(obj)))
            nodes_file.close()
        except IOError:
            logger.exception("error writing nodes file")

    def add_config_object(self, name, object_type, callback):
        """
        Objects can register configuration objects that are included in
        the Register Message and may be configured via the Configure
        Message. The callback is invoked when receiving a Configure Message.

        :param str name: name of configuration object to add
        :param int object_type: register tlv type
        :param func callback: callback function for object
        :return: nothing
        """
        register_tlv = RegisterTlvs(object_type)
        logger.info("adding config object callback: %s - %s", name, register_tlv)
        with self._config_objects_lock:
            self.config_objects[name] = (object_type, callback)

    def config_object(self, config_data):
        """
        Invoke the callback for an object upon receipt of configuration data for that object.
        A no-op if the object doesn't exist.

        :param core.data.ConfigData config_data: configuration data to execute against
        :return: responses to the configuration data
        :rtype: list
        """
        name = config_data.object
        logger.info("session(%s): handling config message(%s): \n%s",
                    self.session_id, name, config_data)

        replies = []

        if name == "all":
            with self._config_objects_lock:
                for name in self.config_objects:
                    config_type, callback = self.config_objects[name]
                    reply = callback(self, config_data)

                    if reply:
                        replies.append(reply)

                return replies

        if name in self.config_objects:
            with self._config_objects_lock:
                config_type, callback = self.config_objects[name]

            reply = callback(self, config_data)

            if reply:
                replies.append(reply)

            return replies
        else:
            logger.info("session object doesn't own model '%s', ignoring", name)

        return replies

    def dump_session(self):
        """
        Log information about the session in its current state.
        """
        logger.info("session id=%s name=%s state=%s", self.session_id, self.name, self.state)
        logger.info("file=%s thumbnail=%s node_count=%s/%s",
                    self.file_name, self.thumbnail, self.get_node_count(), len(self.objects))

    def exception(self, level, source, object_id, text):
        """
        Generate and broadcast an exception event.

        :param str level: exception level
        :param str source: source name
        :param int object_id: object id
        :param str text: exception message
        :return: nothing
        """

        exception_data = ExceptionData(
            node=object_id,
            session=str(self.session_id),
            level=level,
            source=source,
            date=time.ctime(),
            text=text
        )

        self.broadcast_exception(exception_data)

    def get_config_item(self, name):
        """
        Return an entry from the configuration dictionary that comes from
        command-line arguments and/or the core.conf config file.

        :param str name: name of configuration to retrieve
        :return: config value
        """
        return self.config.get(name)

    def get_config_item_bool(self, name, default=None):
        """
        Return a boolean entry from the configuration dictionary, may
        return None if undefined.

        :param str name: configuration item name
        :param default: default value to return if not found
        :return: boolean value of the configuration item
        :rtype: bool
        """
        item = self.get_config_item(name)
        if item is None:
            return default
        return bool(item.lower() == "true")

    def get_config_item_int(self, name, default=None):
        """
        Return an integer entry from the configuration dictionary, may
        return None if undefined.

        :param str name: configuration item name
        :param default: default value to return if not found
        :return: integer value of the configuration item
        :rtype: int
        """
        item = self.get_config_item(name)
        if item is None:
            return default
        return int(item)

    def instantiate(self):
        """
        We have entered the instantiation state, invoke startup methods
        of various managers and boot the nodes. Validate nodes and check
        for transition to the runtime state.
        """

        # write current objects out to session directory file
        self.write_objects()

        # controlnet may be needed by some EMANE models
        self.add_remove_control_interface(node=None, remove=False)

        # instantiate will be invoked again upon Emane configure
        if self.emane.startup() == self.emane.NOT_READY:
            return

        # startup broker
        self.broker.startup()

        # startup mobility
        self.mobility.startup()

        # boot the services on each node
        self.boot_nodes()

        # allow time for processes to start
        time.sleep(0.125)

        # validate nodes
        self.validate_nodes()

        # set broker local instantiation to complete
        self.broker.local_instantiation_complete()

        # assume either all nodes have booted already, or there are some
        # nodes on slave servers that will be booted and those servers will
        # send a node status response message
        self.check_runtime()

    def get_node_count(self):
        """
        Returns the number of CoreNodes and CoreNets, except for those
        that are not considered in the GUI's node count.
        """

        with self._objects_lock:
            count = len(filter(lambda x: not nodeutils.is_node(x, (NodeTypes.PEER_TO_PEER, NodeTypes.CONTROL_NET)),
                               self.objects))

            # on Linux, GreTapBridges are auto-created, not part of GUI's node count
            count -= len(filter(
                lambda (x): nodeutils.is_node(x, NodeTypes.TAP_BRIDGE) and not nodeutils.is_node(x, NodeTypes.TUNNEL),
                self.objects))

        return count

    def check_runtime(self):
        """
        Check if we have entered the runtime state, that all nodes have been
        started and the emulation is running. Start the event loop once we
        have entered runtime (time=0).
        """
        # this is called from instantiate() after receiving an event message
        # for the instantiation state, and from the broker when distributed
        # nodes have been started
        if self.state == EventTypes.RUNTIME_STATE.value:
            logger.info("valid runtime state found, returning")
            return

        # check to verify that all nodes and networks are running
        if not self.broker.instantiation_complete():
            return

        # start event loop and set to runtime
        self.event_loop.run()
        self.set_state(EventTypes.RUNTIME_STATE.value, send_event=True)

    def data_collect(self):
        """
        Tear down a running session. Stop the event loop and any running
        nodes, and perform clean-up.
        """
        # stop event loop
        self.event_loop.stop()

        # stop node services
        with self._objects_lock:
            for obj in self.objects.itervalues():
                # TODO: determine if checking for CoreNode alone is ok
                if isinstance(obj, nodes.PyCoreNode):
                    self.services.stopnodeservices(obj)

        # shutdown emane
        self.emane.shutdown()

        # update control interface hosts
        self.update_control_interface_hosts(remove=True)

        # remove all four possible control networks. Does nothing if ctrlnet is not installed.
        self.add_remove_control_interface(node=None, net_index=0, remove=True)
        self.add_remove_control_interface(node=None, net_index=1, remove=True)
        self.add_remove_control_interface(node=None, net_index=2, remove=True)
        self.add_remove_control_interface(node=None, net_index=3, remove=True)

    def check_shutdown(self):
        """
        Check if we have entered the shutdown state, when no running nodes
        and links remain.
        """
        node_count = self.get_node_count()

        logger.info("checking shutdown for session %d: %d nodes remaining", self.session_id, node_count)

        # TODO: do we really want a check that finds 0 nodes to initiate a shutdown state?
        if node_count == 0:
            self.set_state(state=EventTypes.SHUTDOWN_STATE.value, send_event=True)
            self.sdt.shutdown()

    def short_session_id(self):
        """
        Return a shorter version of the session ID, appropriate for
        interface names, where length may be limited.
        """
        ssid = (self.session_id >> 8) ^ (self.session_id & ((1 << 8) - 1))
        return "%x" % ssid

    def boot_nodes(self):
        """
        Invoke the boot() procedure for all nodes and send back node
        messages to the GUI for node messages that had the status
        request flag.
        """
        with self._objects_lock:
            for obj in self.objects.itervalues():
                # TODO: determine instance type we need to check, due to method issue below
                if isinstance(obj, nodes.PyCoreNode) and not nodeutils.is_node(obj, NodeTypes.RJ45):
                    # add a control interface if configured
                    self.add_remove_control_interface(node=obj, remove=False)
                    obj.boot()

        self.update_control_interface_hosts()

    def validate_nodes(self):
        """
        Validate all nodes that are known by the session.

        :return: nothing
        """
        with self._objects_lock:
            for obj in self.objects.itervalues():
                # TODO: this can be extended to validate everything, bad node check here as well
                # such as vnoded process, bridges, etc.
                if not isinstance(obj, nodes.PyCoreNode):
                    continue

                if nodeutils.is_node(obj, NodeTypes.RJ45):
                    continue

                obj.validate()

    def get_control_lnet_prefixes(self):
        """
        Retrieve control net prefixes.

        :return: control net prefix list
        :rtype: list
        """
        p = getattr(self.options, "controlnet", self.config.get("controlnet"))
        p0 = getattr(self.options, "controlnet0", self.config.get("controlnet0"))
        p1 = getattr(self.options, "controlnet1", self.config.get("controlnet1"))
        p2 = getattr(self.options, "controlnet2", self.config.get("controlnet2"))
        p3 = getattr(self.options, "controlnet3", self.config.get("controlnet3"))

        if not p0 and p:
            p0 = p

        return [p0, p1, p2, p3]

    def get_control_net_server_interfaces(self):
        """
        Retrieve control net server interfaces.

        :return: list of control net server interfaces
        :rtype: list
        """
        d0 = self.config.get("controlnetif0")
        if d0:
            logger.error("controlnet0 cannot be assigned with a host interface")
        d1 = self.config.get("controlnetif1")
        d2 = self.config.get("controlnetif2")
        d3 = self.config.get("controlnetif3")
        return [None, d1, d2, d3]

    def get_control_net_index(self, dev):
        """
        Retrieve control net index.

        :param str dev: device to get control net index for
        :return: control net index, -1 otherwise
        :rtype: int
        """
        if dev[0:4] == "ctrl" and int(dev[4]) in [0, 1, 2, 3]:
            index = int(dev[4])
            if index == 0:
                return index
            if index < 4 and self.get_control_lnet_prefixes()[index] is not None:
                return index
        return -1

    def get_control_net_object(self, net_index):
        # TODO: all nodes use an integer id and now this wants to use a string =(
        object_id = "ctrl%dnet" % net_index
        return self.get_object(object_id)

    def add_remove_control_net(self, net_index, remove=False, conf_required=True):
        """
        Create a control network bridge as necessary.
        When the remove flag is True, remove the bridge that connects control
        interfaces. The conf_reqd flag, when False, causes a control network
        bridge to be added even if one has not been configured.

        :param int net_index: network index
        :param bool remove: flag to check if it should be removed
        :param bool conf_required: flag to check if conf is required
        :return: control net object
        :rtype: core.netns.nodes.CtrlNet
        """
        prefix_spec_list = self.get_control_lnet_prefixes()
        prefix_spec = prefix_spec_list[net_index]
        if not prefix_spec:
            if conf_required:
                # no controlnet needed
                return None
            else:
                control_net_class = nodeutils.get_node_class(NodeTypes.CONTROL_NET)
                prefix_spec = control_net_class.DEFAULT_PREFIX_LIST[net_index]

        server_interface = self.get_control_net_server_interfaces()[net_index]

        # return any existing controlnet bridge
        try:
            control_net = self.get_control_net_object(net_index)

            if remove:
                self.delete_object(control_net.objid)
                return None

            return control_net
        except KeyError:
            if remove:
                return None

        # build a new controlnet bridge
        object_id = "ctrl%dnet" % net_index

        # use the updown script for control net 0 only.
        updown_script = None

        if net_index == 0:
            try:
                if self.config["controlnet_updown_script"]:
                    updown_script = self.config["controlnet_updown_script"]
            except KeyError:
                logger.exception("error retreiving controlnet updown script")

            # Check if session option set, overwrite if so
            new_updown_script = getattr(self.options, "controlnet_updown_script", default=None)
            if new_updown_script:
                updown_script = new_updown_script

        prefixes = prefix_spec.split()
        if len(prefixes) > 1:
            # a list of per-host prefixes is provided
            assign_address = True
            if self.master:
                try:
                    # split first (master) entry into server and prefix
                    prefix = prefixes[0].split(":", 1)[1]
                except IndexError:
                    # no server name. possibly only one server
                    prefix = prefixes[0]
            else:
                # slave servers have their name and localhost in the serverlist
                servers = self.broker.getservernames()
                servers.remove("localhost")
                prefix = None

                for server_prefix in prefixes:
                    try:
                        # split each entry into server and prefix
                        server, p = server_prefix.split(":")
                    except ValueError:
                        server = ""
                        p = None

                    if server == servers[0]:
                        # the server name in the list matches this server
                        prefix = p
                        break

                if not prefix:
                    logger.error("Control network prefix not found for server '%s'" % servers[0])
                    assign_address = False
                    try:
                        prefix = prefixes[0].split(':', 1)[1]
                    except IndexError:
                        prefix = prefixes[0]
        # len(prefixes) == 1
        else:
            # TODO: can we get the server name from the servers.conf or from the node assignments?
            # with one prefix, only master gets a ctrlnet address
            assign_address = self.master
            prefix = prefixes[0]

        control_net_class = nodeutils.get_node_class(NodeTypes.CONTROL_NET)
        control_net = self.add_object(cls=control_net_class, objid=object_id, prefix=prefix,
                                      assign_address=assign_address,
                                      updown_script=updown_script, serverintf=server_interface)

        # tunnels between controlnets will be built with Broker.addnettunnels()
        # TODO: potentialy remove documentation saying object ids are ints
        self.broker.addnet(object_id)
        for server in self.broker.getservers():
            self.broker.addnodemap(server, object_id)

        return control_net

    def add_remove_control_interface(self, node, net_index=0, remove=False, conf_required=True):
        """
        Add a control interface to a node when a 'controlnet' prefix is
        listed in the config file or session options. Uses
        addremovectrlnet() to build or remove the control bridge.
        If conf_reqd is False, the control network may be built even
        when the user has not configured one (e.g. for EMANE.)

        :param core.netns.nodes.CoreNode node: node to add or remove control interface
        :param int net_index: network index
        :param bool remove: flag to check if it should be removed
        :param bool conf_required: flag to check if conf is required
        :return: nothing
        """
        control_net = self.add_remove_control_net(net_index, remove, conf_required)
        if not control_net:
            return

        if not node:
            return

        # ctrl# already exists
        if node.netif(control_net.CTRLIF_IDX_BASE + net_index):
            return

        control_ip = node.objid

        try:
            addrlist = ["%s/%s" % (control_net.prefix.addr(control_ip), control_net.prefix.prefixlen)]
        except ValueError:
            msg = "Control interface not added to node %s. " % node.objid
            msg += "Invalid control network prefix (%s). " % control_net.prefix
            msg += "A longer prefix length may be required for this many nodes."
            logger.exception(msg)
            return

        interface1 = node.newnetif(net=control_net,
                                   ifindex=control_net.CTRLIF_IDX_BASE + net_index,
                                   ifname="ctrl%d" % net_index, hwaddr=MacAddress.random(),
                                   addrlist=addrlist)
        node.netif(interface1).control = True

    def update_control_interface_hosts(self, net_index=0, remove=False):
        """
        Add the IP addresses of control interfaces to the /etc/hosts file.

        :param int net_index: network index to update
        :param bool remove: flag to check if it should be removed
        :return: nothing
        """
        if not self.get_config_item_bool("update_etc_hosts", False):
            return

        try:
            control_net = self.get_control_net_object(net_index)
        except KeyError:
            logger.exception("error retrieving control net object")
            return

        header = "CORE session %s host entries" % self.session_id
        if remove:
            logger.info("Removing /etc/hosts file entries.")
            utils.filedemunge("/etc/hosts", header)
            return

        entries = []
        for interface in control_net.netifs():
            name = interface.node.name
            for address in interface.addrlist:
                entries.append("%s %s" % (address.split("/")[0], name))

        logger.info("Adding %d /etc/hosts file entries." % len(entries))

        utils.filemunge("/etc/hosts", header, "\n".join(entries) + "\n")

    def runtime(self):
        """
        Return the current time we have been in the runtime state, or zero
        if not in runtime.
        """
        if self.state == EventTypes.RUNTIME_STATE.value:
            return time.time() - self._state_time
        else:
            return 0.0

    def add_event(self, event_time, node=None, name=None, data=None):
        """
        Add an event to the event queue, with a start time relative to the
        start of the runtime state.

        :param event_time: event time
        :param core.netns.nodes.CoreNode node: node to add event for
        :param str name: name of event
        :param data: data for event
        :return: nothing
        """
        event_time = float(event_time)
        current_time = self.runtime()

        if current_time > 0.0:
            if time <= current_time:
                logger.warn("could not schedule past event for time %s (run time is now %s)", time, current_time)
                return
            event_time = event_time - current_time

        self.event_loop.add_event(event_time, self.run_event, node=node, name=name, data=data)

        if not name:
            name = ""
        logger.info("scheduled event %s at time %s data=%s", name, event_time + current_time, data)

    def run_event(self, node_id=None, name=None, data=None):
        """
        Run a scheduled event, executing commands in the data string.

        :param int node_id: node id to run event
        :param str name: event name
        :param data: event data
        :return: nothing
        """
        now = self.runtime()
        if not name:
            name = ""

        logger.info("running event %s at time %s cmd=%s" % (name, now, data))
        commands = shlex.split(data)
        if not node_id:
            utils.mutedetach(commands)
        else:
            node = self.get_object(node_id)
            node.cmd(commands, wait=False)

    def send_objects(self):
        """
        Return API messages that describe the current session.
        """

        # send node messages for node and network objects
        # send link messages from net objects
        number_nodes = 0
        number_links = 0
        with self._objects_lock:
            for obj in self.objects.itervalues():
                node_data = obj.data(message_type=MessageFlags.ADD.value)
                if node_data:
                    self.broadcast_node(node_data)
                    # replies.append(message)
                    number_nodes += 1

                links_data = obj.all_link_data(flags=MessageFlags.ADD.value)
                for link_data in links_data:
                    self.broadcast_link(link_data)
                    # replies.append(link_data)
                    number_links += 1

        # send model info
        configs = self.mobility.getallconfigs()
        configs += self.emane.getallconfigs()
        for node_number, cls, values in configs:
            config_data = cls.config_data(
                flags=0,
                node_id=node_number,
                type_flags=ConfigFlags.UPDATE.value,
                values=values
            )
            self.broadcast_config(config_data)

        # service customizations
        service_configs = self.services.getallconfigs()
        for node_number, service in service_configs:
            opaque = "service:%s" % service._name
            config_data = ConfigData(
                node=node_number,
                opaque=opaque
            )
            # replies.append(self.services.configure_request(config_data))
            config_response = self.services.configure_request(config_data)
            self.broadcast_config(config_response)

            for file_name, config_data in self.services.getallfiles(service):
                # flags = MessageFlags.ADD.value
                # tlv_data = coreapi.CoreFileTlv.pack(FileTlvs.NODE.value, node_number)
                # tlv_data += coreapi.CoreFileTlv.pack(FileTlvs.NAME.value, str(file_name))
                # tlv_data += coreapi.CoreFileTlv.pack(FileTlvs.TYPE.value, opaque)
                # tlv_data += coreapi.CoreFileTlv.pack(FileTlvs.DATA.value, str(config_data))
                # replies.append(coreapi.CoreFileMessage.pack(flags, tlv_data))

                file_data = FileData(
                    message_type=MessageFlags.ADD.value,
                    node=node_number,
                    name=str(file_name),
                    type=opaque,
                    data=str(config_data)
                )
                self.broadcast_file(file_data)

        # TODO: send location info

        # send hook scripts
        for state in sorted(self._hooks.keys()):
            for file_name, config_data in self._hooks[state]:
                # flags = MessageFlags.ADD.value
                # tlv_data = coreapi.CoreFileTlv.pack(FileTlvs.NAME.value, str(file_name))
                # tlv_data += coreapi.CoreFileTlv.pack(FileTlvs.TYPE.value, "hook:%s" % state)
                # tlv_data += coreapi.CoreFileTlv.pack(FileTlvs.DATA.value, str(config_data))
                # replies.append(coreapi.CoreFileMessage.pack(flags, tlv_data))

                file_data = FileData(
                    message_type=MessageFlags.ADD.value,
                    name=str(file_name),
                    type="hook:%s" % state,
                    data=str(config_data)
                )
                self.broadcast_file(file_data)

        config_data = ConfigData()

        # retrieve session configuration data
        options_config = self.options.configure_request(config_data, type_flags=ConfigFlags.UPDATE.value)
        self.broadcast_config(options_config)

        # retrieve session metadata
        metadata_config = self.metadata.configure_request(config_data, type_flags=ConfigFlags.UPDATE.value)
        self.broadcast_config(metadata_config)

        logger.info("informing GUI about %d nodes and %d links", number_nodes, number_links)


class SessionConfig(ConfigurableManager, Configurable):
    """
    Session configuration object.
    """
    name = "session"
    config_type = RegisterTlvs.UTILITY.value
    config_matrix = [
        ("controlnet", ConfigDataTypes.STRING.value, "", "", "Control network"),
        ("controlnet_updown_script", ConfigDataTypes.STRING.value, "", "", "Control network script"),
        ("enablerj45", ConfigDataTypes.BOOL.value, "1", "On,Off", "Enable RJ45s"),
        ("preservedir", ConfigDataTypes.BOOL.value, "0", "On,Off", "Preserve session dir"),
        ("enablesdt", ConfigDataTypes.BOOL.value, "0", "On,Off", "Enable SDT3D output"),
        ("sdturl", ConfigDataTypes.STRING.value, Sdt.DEFAULT_SDT_URL, "", "SDT3D URL"),
    ]
    config_groups = "Options:1-%d" % len(config_matrix)

    def __init__(self, session):
        """
        Creates a SessionConfig instance.

        :param core.session.Session session: session this manager is tied to
        :return: nothing
        """
        ConfigurableManager.__init__(self)
        self.session = session
        self.session.broker.handlers.add(self.handle_distributed)
        self.reset()

    def reset(self):
        """
        Reset the session configuration.

        :return: nothing
        """
        defaults = self.getdefaultvalues()
        for key in self.getnames():
            # value may come from config file
            value = self.session.get_config_item(key)
            if value is None:
                value = self.valueof(key, defaults)
                value = self.offontobool(value)
            setattr(self, key, value)

    def configure_values(self, config_data):
        """
        Handle configuration values.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        :return: None
        """
        return self.configure_values_keyvalues(config_data, self, self.getnames())

    def configure_request(self, config_data, type_flags=ConfigFlags.NONE.value):
        """
        Handle a configuration request.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        :param type_flags:
        :return:
        """
        node_id = config_data.node
        values = []

        for key in self.getnames():
            value = getattr(self, key)
            if value is None:
                value = ""
            values.append("%s" % value)

        return self.config_data(0, node_id, type_flags, values)

    # TODO: update logic to not be tied to old style messages
    def handle_distributed(self, message):
        """
        Handle the session options config message as it has reached the
        broker. Options requiring modification for distributed operation should
        be handled here.

        :param message: message to handle
        :return: nothing
        """
        if not self.session.master:
            return

        if message.message_type != MessageTypes.CONFIG.value or message.get_tlv(ConfigTlvs.OBJECT.value) != "session":
            return

        values_str = message.get_tlv(ConfigTlvs.VALUES.value)
        if values_str is None:
            return

        value_strings = values_str.split('|')
        if not self.haskeyvalues(value_strings):
            return

        for value_string in value_strings:
            key, value = value_string.split('=', 1)
            if key == "controlnet":
                self.handle_distributed_control_net(message, value_strings, value_strings.index(value_string))

    # TODO: update logic to not be tied to old style messages
    def handle_distributed_control_net(self, message, values, index):
        """
        Modify Config Message if multiple control network prefixes are
        defined. Map server names to prefixes and repack the message before
        it is forwarded to slave servers.

        :param message: message to handle
        :param list values: values to handle
        :param int index: index ti get key value from
        :return: nothing
        """
        key_value = values[index]
        key, value = key_value.split('=', 1)
        control_nets = value.split()

        if len(control_nets) < 2:
            logger.warn("multiple controlnet prefixes do not exist")
            return

        servers = self.session.broker.getservernames()
        if len(servers) < 2:
            logger.warn("not distributed")
            return

        servers.remove("localhost")
        # master always gets first prefix
        servers.insert(0, "localhost")
        # create list of "server1:ctrlnet1 server2:ctrlnet2 ..."
        control_nets = map(lambda x: "%s:%s" % (x[0], x[1]), zip(servers, control_nets))
        values[index] = "controlnet=%s" % (" ".join(control_nets))
        values_str = "|".join(values)
        message.tlvdata[ConfigTlvs.VALUES.value] = values_str
        message.repack()


class SessionMetaData(ConfigurableManager):
    """
    Metadata is simply stored in a configs[] dict. Key=value pairs are
    passed in from configure messages destined to the "metadata" object.
    The data is not otherwise interpreted or processed.
    """
    name = "metadata"
    config_type = RegisterTlvs.UTILITY.value

    def configure_values(self, config_data):
        """
        Handle configuration values.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        :return: None
        """
        values = config_data.data_values
        if values is None:
            return None

        key_values = values.split('|')
        for key_value in key_values:
            try:
                key, value = key_value.split('=', 1)
            except ValueError:
                raise ValueError("invalid key in metdata: %s", key_value)

            self.add_item(key, value)

        return None

    def configure_request(self, config_data, type_flags=ConfigFlags.NONE.value):
        """
        Handle a configuration request.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        :param int type_flags: configuration request flag value
        :return: configuration data
        :rtype: ConfigData
        """
        node_number = config_data.node
        values_str = "|".join(map(lambda item: "%s=%s" % item, self.items()))
        return self.config_data(0, node_number, type_flags, values_str)

    def config_data(self, flags, node_id, type_flags, values_str):
        """
        Retrieve configuration data object, leveraging provided data.

        :param flags: configuration data flags
        :param int node_id: node id
        :param type_flags: type flags
        :param values_str: values string
        :return: configuration data
        :rtype: ConfigData
        """
        data_types = tuple(map(lambda (k, v): ConfigDataTypes.STRING.value, self.items()))

        return ConfigData(
            message_type=flags,
            node=node_id,
            object=self.name,
            type=type_flags,
            data_types=data_types,
            data_values=values_str
        )

    def add_item(self, key, value):
        """
        Add configuration key/value pair.

        :param key: configuration key
        :param value: configuration value
        :return: nothing
        """
        self.configs[key] = value

    def get_item(self, key):
        """
        Retrieve configuration value.

        :param key: key for configuration value to retrieve
        :return: configuration value
        """
        try:
            return self.configs[key]
        except KeyError:
            logger.exception("error retrieving item from configs: %s", key)

        return None

    def items(self):
        """
        Retrieve configuration items.

        :return: configuration items iterator
        """
        return self.configs.iteritems()


# configure the program exit function to run
atexit.register(SessionManager.on_exit)
