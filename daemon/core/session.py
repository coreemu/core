"""
session.py: defines the Session class used by the core-daemon daemon program
that manages a CORE session.
"""

import logging
import os
import random
import shutil
import subprocess
import tempfile
import threading
import time
from multiprocessing.pool import ThreadPool

import pwd

from core import constants
from core.api import coreapi
from core.broker import CoreBroker
from core.conf import ConfigurableManager
from core.conf import ConfigurableOptions
from core.conf import Configuration
from core.data import EventData
from core.data import ExceptionData
from core.emane.emanemanager import EmaneManager
from core.enumerations import ConfigDataTypes
from core.enumerations import EventTypes
from core.enumerations import ExceptionLevels
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs
from core.location import CoreLocation
from core.misc import nodeutils
from core.misc import utils
from core.misc.event import EventLoop
from core.misc.ipaddress import MacAddress
from core.mobility import MobilityManager
from core.netns import nodes
from core.sdt import Sdt
from core.service import CoreServices
from core.xml import corexml, corexmldeployment


class Session(object):
    """
    CORE session manager.
    """

    def __init__(self, session_id, config=None, mkdir=True):
        """
        Create a Session instance.

        :param int session_id: session id
        :param dict config: session configuration
        :param bool mkdir: flag to determine if a directory should be made
        """
        self.session_id = session_id

        # define and create session directory when desired
        self.session_dir = os.path.join(tempfile.gettempdir(), "pycore.%s" % self.session_id)
        if mkdir:
            os.mkdir(self.session_dir)

        self.name = None
        self.file_name = None
        self.thumbnail = None
        self.user = None
        self.event_loop = EventLoop()

        # dict of objects: all nodes and nets
        self.objects = {}
        self._objects_lock = threading.Lock()

        # TODO: should the default state be definition?
        self.state = EventTypes.NONE.value
        self._state_time = time.time()
        self._state_file = os.path.join(self.session_dir, "state")

        self._hooks = {}
        self._state_hooks = {}

        self.add_state_hook(state=EventTypes.RUNTIME_STATE.value, hook=self.runtime_state_hook)

        self.master = False

        # handlers for broadcasting information
        self.event_handlers = []
        self.exception_handlers = []
        self.node_handlers = []
        self.link_handlers = []
        self.file_handlers = []
        self.config_handlers = []
        self.shutdown_handlers = []

        # session options/metadata
        self.options = SessionConfig()
        if not config:
            config = {}
        for key, value in config.iteritems():
            self.options.set_config(key, value)
        self.metadata = SessionMetaData()

        # initialize session feature helpers
        self.broker = CoreBroker(session=self)
        self.location = CoreLocation()
        self.mobility = MobilityManager(session=self)
        self.services = CoreServices(session=self)
        self.emane = EmaneManager(session=self)
        self.sdt = Sdt(session=self)

    def shutdown(self):
        """
        Shutdown all emulation objects and remove the session directory.
        """
        # shutdown/cleanup feature helpers
        self.emane.shutdown()
        self.broker.shutdown()
        self.sdt.shutdown()

        # delete all current objects
        self.delete_objects()

        # remove this sessions working directory
        preserve = self.options.get_config("preservedir") == "1"
        if not preserve:
            shutil.rmtree(self.session_dir, ignore_errors=True)

        # call session shutdown handlers
        for handler in self.shutdown_handlers:
            handler(self)

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

        :param core.enumerations.EventTypes state: state to set to
        :param send_event: if true, generate core API event messages
        :return: nothing
        """
        state_value = state.value
        state_name = state.name

        if self.state == state_value:
            logging.info("session(%s) is already in state: %s, skipping change", self.session_id, state_name)
            return

        self.state = state_value
        self._state_time = time.time()
        logging.info("changing session(%s) to state %s", self.session_id, state_name)

        self.write_state(state_value)
        self.run_hooks(state_value)
        self.run_state_hooks(state_value)

        if send_event:
            event_data = EventData(event_type=state_value, time="%s" % time.time())
            self.broadcast_event(event_data)

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
            logging.exception("error writing state file: %s", state)

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
        if hooks:
            for hook in hooks:
                self.run_hook(hook)
        else:
            logging.info("no state hooks for %s", state)

    def set_hook(self, hook_type, file_name, source_name, data):
        """
        Store a hook from a received file message.

        :param str hook_type: hook type
        :param str file_name: file name for hook
        :param str source_name: source name
        :param data: hook data
        :return: nothing
        """
        logging.info("setting state hook: %s - %s from %s", hook_type, file_name, source_name)

        _hook_id, state = hook_type.split(':')[:2]
        if not state.isdigit():
            logging.error("error setting hook having state '%s'", state)
            return

        state = int(state)
        hook = file_name, data

        # append hook to current state hooks
        state_hooks = self._hooks.setdefault(state, [])
        state_hooks.append(hook)

        # immediately run a hook if it is in the current state
        # (this allows hooks in the definition and configuration states)
        if self.state == state:
            logging.info("immediately running new state hook")
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
        logging.info("running hook %s", file_name)

        # write data to hook file
        try:
            hook_file = open(os.path.join(self.session_dir, file_name), "w")
            hook_file.write(data)
            hook_file.close()
        except IOError:
            logging.exception("error writing hook '%s'", file_name)

        # setup hook stdout and stderr
        try:
            stdout = open(os.path.join(self.session_dir, file_name + ".log"), "w")
            stderr = subprocess.STDOUT
        except IOError:
            logging.exception("error setting up hook stderr and stdout")
            stdout = None
            stderr = None

        # execute hook file
        try:
            args = ["/bin/sh", file_name]
            subprocess.check_call(args, stdout=stdout, stderr=stderr,
                                  close_fds=True, cwd=self.session_dir, env=self.get_environment())
        except (OSError, subprocess.CalledProcessError):
            logging.exception("error running hook: %s", file_name)

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
                logging.exception(message)
                self.exception(ExceptionLevels.ERROR, "Session.run_state_hooks", None, message)

    def add_state_hook(self, state, hook):
        """
        Add a state hook.

        :param int state: state to add hook for
        :param func hook: hook callback for the state
        :return: nothing
        """
        hooks = self._state_hooks.setdefault(state, [])
        if hook in hooks:
            raise ValueError("attempting to add duplicate state hook")
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
            xml_file_version = self.options.get_config("xmlfilever")
            if xml_file_version in ("1.0",):
                xml_file_name = os.path.join(self.session_dir, "session-deployed.xml")
                xml_writer = corexml.CoreXmlWriter(self)
                corexmldeployment.CoreXmlDeployment(self, xml_writer.scenario)
                xml_writer.write(xml_file_name)

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
                utils.load_config(environment_config_file, env)
        except IOError:
            logging.warn("environment configuration file does not exist: %s", environment_config_file)

        # attempt to read and add user environment file
        if self.user:
            environment_user_file = os.path.join("/home", self.user, ".core", "environment")
            try:
                utils.load_config(environment_user_file, env)
            except IOError:
                logging.debug("user core environment settings file not present: %s", environment_user_file)

        return env

    def set_thumbnail(self, thumb_file):
        """
        Set the thumbnail filename. Move files from /tmp to session dir.

        :param str thumb_file: tumbnail file to set for session
        :return: nothing
        """
        if not os.path.exists(thumb_file):
            logging.error("thumbnail file to set does not exist: %s", thumb_file)
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
                logging.exception("failed to set permission on %s", self.session_dir)

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
        :rtype: core.coreobj.PyCoreNode
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
                logging.error("failed to remove object, object with id was not found: %s", object_id)

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
            logging.exception("error writing nodes file")

    def dump_session(self):
        """
        Log information about the session in its current state.
        """
        logging.info("session id=%s name=%s state=%s", self.session_id, self.name, self.state)
        logging.info("file=%s thumbnail=%s node_count=%s/%s",
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

        # start feature helpers
        self.broker.startup()
        self.mobility.startup()

        # boot the services on each node
        self.boot_nodes()

        # set broker local instantiation to complete
        self.broker.local_instantiation_complete()

        # notify listeners that instantiation is complete
        event = EventData(event_type=EventTypes.INSTANTIATION_COMPLETE.value)
        self.broadcast_event(event)

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
            count = len([x for x in self.objects if not nodeutils.is_node(x, (NodeTypes.PEER_TO_PEER, NodeTypes.CONTROL_NET))])

            # on Linux, GreTapBridges are auto-created, not part of GUI's node count
            count -= len([x for x in self.objects if nodeutils.is_node(x, NodeTypes.TAP_BRIDGE) and not nodeutils.is_node(x, NodeTypes.TUNNEL)])

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
        logging.info("session(%s) checking if not in runtime state, current state: %s", self.session_id,
                    coreapi.state_name(self.state))
        if self.state == EventTypes.RUNTIME_STATE.value:
            logging.info("valid runtime state found, returning")
            return

        # check to verify that all nodes and networks are running
        if not self.broker.instantiation_complete():
            return

        # start event loop and set to runtime
        self.event_loop.run()
        self.set_state(EventTypes.RUNTIME_STATE, send_event=True)

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
                    self.services.stop_services(obj)

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
        logging.info("session(%s) checking shutdown: %s nodes remaining", self.session_id, node_count)

        shutdown = False
        if node_count == 0:
            shutdown = True
            self.set_state(EventTypes.SHUTDOWN_STATE)

        return shutdown

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
            pool = ThreadPool()
            results = []

            start = time.time()
            for obj in self.objects.itervalues():
                # TODO: PyCoreNode is not the type to check
                if isinstance(obj, nodes.PyCoreNode) and not nodeutils.is_node(obj, NodeTypes.RJ45):
                    # add a control interface if configured
                    logging.info("booting node: %s", obj.name)
                    self.add_remove_control_interface(node=obj, remove=False)
                    result = pool.apply_async(self.services.boot_services, (obj,))
                    results.append(result)

            pool.close()
            pool.join()
            for result in results:
                result.get()
            logging.debug("boot run time: %s", time.time() - start)

        self.update_control_interface_hosts()

    def get_control_net_prefixes(self):
        """
        Retrieve control net prefixes.

        :return: control net prefix list
        :rtype: list
        """
        p = self.options.get_config("controlnet")
        p0 = self.options.get_config("controlnet0")
        p1 = self.options.get_config("controlnet1")
        p2 = self.options.get_config("controlnet2")
        p3 = self.options.get_config("controlnet3")

        if not p0 and p:
            p0 = p

        return [p0, p1, p2, p3]

    def get_control_net_server_interfaces(self):
        """
        Retrieve control net server interfaces.

        :return: list of control net server interfaces
        :rtype: list
        """
        d0 = self.options.get_config("controlnetif0")
        if d0:
            logging.error("controlnet0 cannot be assigned with a host interface")
        d1 = self.options.get_config("controlnetif1")
        d2 = self.options.get_config("controlnetif2")
        d3 = self.options.get_config("controlnetif3")
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
            if index < 4 and self.get_control_net_prefixes()[index] is not None:
                return index
        return -1

    def get_control_net_object(self, net_index):
        # TODO: all nodes use an integer id and now this wants to use a string
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
        logging.debug("add/remove control net: index(%s) remove(%s) conf_required(%s)", net_index, remove, conf_required)
        prefix_spec_list = self.get_control_net_prefixes()
        prefix_spec = prefix_spec_list[net_index]
        if not prefix_spec:
            if conf_required:
                # no controlnet needed
                return None
            else:
                control_net_class = nodeutils.get_node_class(NodeTypes.CONTROL_NET)
                prefix_spec = control_net_class.DEFAULT_PREFIX_LIST[net_index]
        logging.debug("prefix spec: %s", prefix_spec)

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
            updown_script = self.options.get_config("controlnet_updown_script")
            if not updown_script:
                logging.warning("controlnet updown script not configured")

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
                    logging.error("Control network prefix not found for server '%s'" % servers[0])
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
        # TODO: potentially remove documentation saying object ids are ints
        # TODO: need to move broker code out of the session object
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
            logging.exception(msg)
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
        if not self.options.get_config_bool("update_etc_hosts", default=False):
            return

        try:
            control_net = self.get_control_net_object(net_index)
        except KeyError:
            logging.exception("error retrieving control net object")
            return

        header = "CORE session %s host entries" % self.session_id
        if remove:
            logging.info("Removing /etc/hosts file entries.")
            utils.file_demunge("/etc/hosts", header)
            return

        entries = []
        for interface in control_net.netifs():
            name = interface.node.name
            for address in interface.addrlist:
                entries.append("%s %s" % (address.split("/")[0], name))

        logging.info("Adding %d /etc/hosts file entries." % len(entries))

        utils.file_munge("/etc/hosts", header, "\n".join(entries) + "\n")

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
                logging.warn("could not schedule past event for time %s (run time is now %s)", time, current_time)
                return
            event_time = event_time - current_time

        self.event_loop.add_event(event_time, self.run_event, node=node, name=name, data=data)

        if not name:
            name = ""
        logging.info("scheduled event %s at time %s data=%s", name, event_time + current_time, data)

    # TODO: if data is None, this blows up, but this ties into how event functions are ran, need to clean that up
    def run_event(self, node_id=None, name=None, data=None):
        """
        Run a scheduled event, executing commands in the data string.

        :param int node_id: node id to run event
        :param str name: event name
        :param str data: event data
        :return: nothing
        """
        now = self.runtime()
        if not name:
            name = ""

        logging.info("running event %s at time %s cmd=%s" % (name, now, data))
        if not node_id:
            utils.mute_detach(data)
        else:
            node = self.get_object(node_id)
            node.cmd(data, wait=False)


class SessionConfig(ConfigurableManager, ConfigurableOptions):
    """
    Session configuration object.
    """
    name = "session"
    options = [
        Configuration(_id="controlnet", _type=ConfigDataTypes.STRING, label="Control Network"),
        Configuration(_id="controlnet0", _type=ConfigDataTypes.STRING, label="Control Network 0"),
        Configuration(_id="controlnet1", _type=ConfigDataTypes.STRING, label="Control Network 1"),
        Configuration(_id="controlnet2", _type=ConfigDataTypes.STRING, label="Control Network 2"),
        Configuration(_id="controlnet3", _type=ConfigDataTypes.STRING, label="Control Network 3"),
        Configuration(_id="controlnet_updown_script", _type=ConfigDataTypes.STRING, label="Control Network Script"),
        Configuration(_id="enablerj45", _type=ConfigDataTypes.BOOL, default="1", options=["On", "Off"],
                      label="Enable RJ45s"),
        Configuration(_id="preservedir", _type=ConfigDataTypes.BOOL, default="0", options=["On", "Off"],
                      label="Preserve session dir"),
        Configuration(_id="enablesdt", _type=ConfigDataTypes.BOOL, default="0", options=["On", "Off"],
                      label="Enable SDT3D output"),
        Configuration(_id="sdturl", _type=ConfigDataTypes.STRING, default=Sdt.DEFAULT_SDT_URL, label="SDT3D URL")
    ]
    config_type = RegisterTlvs.UTILITY.value

    def __init__(self):
        super(SessionConfig, self).__init__()
        self.set_configs(self.default_values())

    def get_config(self, _id, node_id=ConfigurableManager._default_node,
                   config_type=ConfigurableManager._default_type, default=None):
        value = super(SessionConfig, self).get_config(_id, node_id, config_type, default)
        if value == "":
            value = default
        return value

    def get_config_bool(self, name, default=None):
        value = self.get_config(name)
        if value is None:
            return default
        return value.lower() == "true"

    def get_config_int(self, name, default=None):
        value = self.get_config(name, default=default)
        if value is not None:
            value = int(value)
        return value


class SessionMetaData(ConfigurableManager):
    """
    Metadata is simply stored in a configs[] dict. Key=value pairs are
    passed in from configure messages destined to the "metadata" object.
    The data is not otherwise interpreted or processed.
    """
    name = "metadata"
    config_type = RegisterTlvs.UTILITY.value
