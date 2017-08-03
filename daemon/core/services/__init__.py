"""
Services

Services available to nodes can be put in this directory.  Everything listed in
__all__ is automatically loaded by the main core module.
"""
import os

from core.misc import log
from core.service import ServiceManager

logger = log.get_logger(__name__)

_PATH = os.path.abspath(os.path.dirname(__file__))


def load():
    """
    Loads all services from the modules that reside under core.services.

    :return: nothing
    """
    ServiceManager.add_services(_PATH)
