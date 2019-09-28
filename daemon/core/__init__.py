import logging.config

# setup default null handler
logging.getLogger(__name__).addHandler(logging.NullHandler())
