import logging
from pathlib import Path
from typing import Dict, List, Type

from core import utils
from core.emane.emanemodel import EmaneModel
from core.errors import CoreError

logger = logging.getLogger(__name__)


class EmaneModelManager:
    models: Dict[str, Type[EmaneModel]] = {}

    @classmethod
    def load(cls, path: Path, prefix: Path) -> List[str]:
        """
        Load EMANE models and make them available.
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
                    model.load(prefix)
                    cls.models[model.name] = model
                except CoreError as e:
                    errors.append(model.name)
                    logger.debug("not loading service(%s): %s", model.name, e)
        return errors

    @classmethod
    def get(cls, name: str) -> Type[EmaneModel]:
        model = cls.models.get(name)
        if model is None:
            raise CoreError(f"emame model does not exist {name}")
        return model
