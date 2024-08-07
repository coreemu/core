import logging
import os
from pathlib import Path

from core import utils
from core.emane.modelmanager import EmaneModelManager
from core.emulator.session import Session
from core.executables import get_requirements
from core.services.manager import ServiceManager

logger = logging.getLogger(__name__)

DEFAULT_EMANE_PREFIX: str = "/usr"


class CoreEmu:
    """
    Provides logic for creating and configuring CORE sessions and the nodes within them.
    """

    def __init__(self, config: dict[str, str] = None) -> None:
        """
        Create a CoreEmu object.

        :param config: configuration options
        """
        # set umask 0
        os.umask(0)

        # configuration
        config = config if config else {}
        self.config: dict[str, str] = config

        # session management
        self.sessions: dict[int, Session] = {}

        # load services
        self.service_errors: list[str] = []
        self.service_manager: ServiceManager = ServiceManager()
        self._load_services()

        # check and load emane
        self.has_emane: bool = False
        self._load_emane()

        # check executables exist on path
        self._validate_env()

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
        self.service_manager.load_locals()
        # load custom services
        custom_dir = self.config.get("custom_services_dir")
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
        while self.sessions:
            _, session = self.sessions.popitem()
            session.shutdown()

    def create_session(self, _id: int = None, _cls: type[Session] = Session) -> Session:
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
