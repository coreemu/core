import atexit
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Dict, List, Type

from core import utils
from core.configservice.manager import ConfigServiceManager
from core.emane.modelmanager import EmaneModelManager
from core.emulator.session import Session
from core.executables import get_requirements
from core.services.coreservices import ServiceManager

logger = logging.getLogger(__name__)

DEFAULT_EMANE_PREFIX: str = "/usr"


def signal_handler(signal_number: int, _) -> None:
    """
    Handle signals and force an exit with cleanup.

    :param signal_number: signal number
    :param _: ignored
    :return: nothing
    """
    logger.info("caught signal: %s", signal_number)
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
        config = config if config else {}
        self.config: Dict[str, str] = config

        # session management
        self.sessions: Dict[int, Session] = {}

        # load services
        self.service_errors: List[str] = []
        self.service_manager: ConfigServiceManager = ConfigServiceManager()
        self._load_services()

        # check and load emane
        self.has_emane: bool = False
        self._load_emane()

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
        use_ovs = self.config.get("ovs") == "1"
        for requirement in get_requirements(use_ovs):
            utils.which(requirement, required=True)

    def _load_services(self) -> None:
        """
        Loads default and custom services for use within CORE.

        :return: nothing
        """
        # load default services
        self.service_errors = ServiceManager.load_locals()
        # load custom services
        service_paths = self.config.get("custom_services_dir")
        logger.debug("custom service paths: %s", service_paths)
        if service_paths is not None:
            for service_path in service_paths.split(","):
                service_path = Path(service_path.strip())
                custom_service_errors = ServiceManager.add_services(service_path)
                self.service_errors.extend(custom_service_errors)
        # load default config services
        self.service_manager.load_locals()
        # load custom config services
        custom_dir = self.config.get("custom_config_services_dir")
        if custom_dir is not None:
            custom_dir = Path(custom_dir)
            self.service_manager.load(custom_dir)

    def _load_emane(self) -> None:
        """
        Check if emane is installed and load models.

        :return: nothing
        """
        # check for emane
        path = utils.which("emane", required=False)
        self.has_emane = path is not None
        if not self.has_emane:
            logger.info("emane is not installed, emane functionality disabled")
            return
        # get version
        emane_version = utils.cmd("emane --version")
        logger.info("using emane: %s", emane_version)
        emane_prefix = self.config.get("emane_prefix", DEFAULT_EMANE_PREFIX)
        emane_prefix = Path(emane_prefix)
        EmaneModelManager.load_locals(emane_prefix)
        # load custom models
        custom_path = self.config.get("emane_models_dir")
        if custom_path is not None:
            logger.info("loading custom emane models: %s", custom_path)
            custom_path = Path(custom_path)
            EmaneModelManager.load(custom_path, emane_prefix)

    def shutdown(self) -> None:
        """
        Shutdown all CORE session.

        :return: nothing
        """
        logger.info("shutting down all sessions")
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
        logger.info("created session: %s", _id)
        self.sessions[_id] = session
        return session

    def delete_session(self, _id: int) -> bool:
        """
        Shutdown and delete a CORE session.

        :param _id: session id to delete
        :return: True if deleted, False otherwise
        """
        logger.info("deleting session: %s", _id)
        session = self.sessions.pop(_id, None)
        result = False
        if session:
            logger.info("shutting session down: %s", _id)
            session.data_collect()
            session.shutdown()
            result = True
        else:
            logger.error("session to delete did not exist: %s", _id)
        return result
