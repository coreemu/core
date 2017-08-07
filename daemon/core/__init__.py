import logzero

# configure custom format with function name
_format_template = "%(color)s[%(levelname)1.1s %(asctime)s %(module)s:%(funcName)s:" \
                   "%(lineno)d]%(end_color)s %(message)s"
_formatter = logzero.LogFormatter(fmt=_format_template)
logzero.formatter(_formatter)

logger = logzero.logger
