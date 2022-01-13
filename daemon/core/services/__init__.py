"""
Services

Services available to nodes can be put in this directory.  Everything listed in
__all__ is automatically loaded by the main core module.
"""
from pathlib import Path

from core.services.coreservices import ServiceManager

_PATH: Path = Path(__file__).resolve().parent


def load():
    """
    Loads all services from the modules that reside under core.services.

    :return: list of services that failed to load
    """
    return ServiceManager.add_services(_PATH)
