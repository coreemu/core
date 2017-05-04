"""
Convenience methods to setup logging.
"""

import logging

_LOG_LEVEL = logging.INFO
_LOG_FORMAT = "%(levelname)-7s %(asctime)s %(name)-15s %(funcName)-15s %(lineno)-4d: %(message)s"
_INITIAL = True


def setup(level=_LOG_LEVEL, log_format=_LOG_FORMAT):
    """
    Configure a logging with a basic configuration, output to console.

    :param logging.LEVEL level: level for logger, defaults to module defined format
    :param int log_format: format for logger, default to DEBUG
    :return: nothing
    """
    logging.basicConfig(level=level, format=log_format)


def get_logger(name):
    """
    Retrieve a logger for logging.

    :param str name: name for logger to retrieve
    :return: logging.logger
    """
    global _INITIAL
    if _INITIAL:
        setup()
        _INITIAL = False

    return logging.getLogger(name)
