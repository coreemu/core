import atexit
import logging
import os
import signal
import sys
from typing import Dict, List, Type

import core.services
from core import configservices, utils
from core.configservice.manager import ConfigServiceManager
from core.emulator.session import Session
from core.executables import COMMON_REQUIREMENTS, OVS_REQUIREMENTS, VCMD_REQUIREMENTS
from core.services.coreservices import ServiceManager


def signal_handler(signal_number: int, _) -> None:
    """
    Handle signals and force an exit with cleanup.

    :param signal_number: signal number
    :param _: ignored
    :return: nothing
    """
    logging.info("caught signal: %s", signal_number)
    sys.exit(signal_number)


signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGUSR1, signal_handler)
signal.signal(signal.SIGUSR2, signal_handler)


class CoreEmu:
    """
    Provides logic for creating and configuring CORE sessions and the nodes within them.
    """

    def __init__(self, config: Dict[str, str] = None) -> None:
        """
        Create a CoreEmu object.

        :param config: configuration options
        """
        # set umask 0
        os.umask(0)

        # configuration
        if config is None:
            config = {}
        self.config: Dict[str, str] = config

        # session management
        self.sessions: Dict[int, Session] = {}

        # load services
        self.service_errors: List[str] = []
        self.load_services()

        # config services
        self.service_manager: ConfigServiceManager = ConfigServiceManager()
        config_services_path = os.path.abspath(os.path.dirname(configservices.__file__))
        self.service_manager.load(config_services_path)
        custom_dir = self.config.get("custom_config_services_dir")
        if custom_dir:
            self.service_manager.load(custom_dir)

        # check executables exist on path
        self._validate_env()

        # catch exit event
        atexit.register(self.shutdown)

    def _validate_env(self) -> None:
        """
        Validates executables CORE depends on exist on path.

        :return: nothing
        :raises core.errors.CoreError: when an executable does not exist on path
        """
        requirements = COMMON_REQUIREMENTS
        use_ovs = self.config.get("ovs") == "True"
        if use_ovs:
            requirements += OVS_REQUIREMENTS
        else:
            requirements += VCMD_REQUIREMENTS
        for requirement in requirements:
            utils.which(requirement, required=True)

    def load_services(self) -> None:
        """
        Loads default and custom services for use within CORE.

        :return: nothing
        """
        # load default services
        self.service_errors = core.services.load()

        # load custom services
        service_paths = self.config.get("custom_services_dir")
        logging.debug("custom service paths: %s", service_paths)
        if service_paths:
            for service_path in service_paths.split(","):
                service_path = service_path.strip()
                custom_service_errors = ServiceManager.add_services(service_path)
                self.service_errors.extend(custom_service_errors)

    def shutdown(self) -> None:
        """
        Shutdown all CORE session.

        :return: nothing
        """
        logging.info("shutting down all sessions")
        sessions = self.sessions.copy()
        self.sessions.clear()
        for _id in sessions:
            session = sessions[_id]
            session.shutdown()

    def create_session(self, _id: int = None, _cls: Type[Session] = Session) -> Session:
        """
        Create a new CORE session.

        :param _id: session id for new session
        :param _cls: Session class to use
        :return: created session
        """
        if not _id:
            _id = 1
            while _id in self.sessions:
                _id += 1
        session = _cls(_id, config=self.config)
        session.service_manager = self.service_manager
        logging.info("created session: %s", _id)
        self.sessions[_id] = session
        return session

    def delete_session(self, _id: int) -> bool:
        """
        Shutdown and delete a CORE session.

        :param _id: session id to delete
        :return: True if deleted, False otherwise
        """
        logging.info("deleting session: %s", _id)
        session = self.sessions.pop(_id, None)
        result = False
        if session:
            logging.info("shutting session down: %s", _id)
            session.shutdown()
            result = True
        else:
            logging.error("session to delete did not exist: %s", _id)
        return result
