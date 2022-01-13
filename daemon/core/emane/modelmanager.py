import logging
import pkgutil
from pathlib import Path
from typing import Dict, List, Type

from core import utils
from core.emane import models as emane_models
from core.emane.emanemodel import EmaneModel
from core.errors import CoreError

logger = logging.getLogger(__name__)


class EmaneModelManager:
    models: Dict[str, Type[EmaneModel]] = {}

    @classmethod
    def load_locals(cls, emane_prefix: Path) -> List[str]:
        """
        Load local core emane models and make them available.

        :param emane_prefix: installed emane prefix
        :return: list of errors encountered loading emane models
        """
        errors = []
        for module_info in pkgutil.walk_packages(
            emane_models.__path__, f"{emane_models.__name__}."
        ):
            models = utils.load_module(module_info.name, EmaneModel)
            for model in models:
                logger.debug("loading emane model: %s", model.name)
                try:
                    model.load(emane_prefix)
                    cls.models[model.name] = model
                except CoreError as e:
                    errors.append(model.name)
                    logger.debug("not loading emane model(%s): %s", model.name, e)
        return errors

    @classmethod
    def load(cls, path: Path, emane_prefix: Path) -> List[str]:
        """
        Search and load custom emane models and make them available.

        :param path: path to search for custom emane models
        :param emane_prefix: installed emane prefix
        :return: list of errors encountered loading emane models
        """
        subdirs = [x for x in path.iterdir() if x.is_dir()]
        subdirs.append(path)
        errors = []
        for subdir in subdirs:
            logger.debug("loading emane models from: %s", subdir)
            models = utils.load_classes(subdir, EmaneModel)
            for model in models:
                logger.debug("loading emane model: %s", model.name)
                try:
                    model.load(emane_prefix)
                    cls.models[model.name] = model
                except CoreError as e:
                    errors.append(model.name)
                    logger.debug("not loading emane model(%s): %s", model.name, e)
        return errors

    @classmethod
    def get(cls, name: str) -> Type[EmaneModel]:
        model = cls.models.get(name)
        if model is None:
            raise CoreError(f"emame model does not exist {name}")
        return model
