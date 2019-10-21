import logging.config

# setup default null handler
logging.getLogger(__name__).addHandler(logging.NullHandler())

# disable paramiko logging
logging.getLogger("paramiko").setLevel(logging.WARNING)
