"""
Utilities for working with python struct data.
"""

from core.misc import log

logger = log.get_logger(__name__)


def pack_values(clazz, packers):
    """
    Pack values for a given legacy class.

    :param class clazz: class that will provide a pack method
    :param list packers: a list of tuples that are used to pack values and transform them
    :return: packed data string of all values
    """

    # iterate through tuples of values to pack
    data = ""
    for packer in packers:
        # check if a transformer was provided for valid values
        transformer = None
        if len(packer) == 2:
            tlv_type, value = packer
        elif len(packer) == 3:
            tlv_type, value, transformer = packer
        else:
            raise RuntimeError("packer had more than 3 arguments")

        # convert unicode to normal str for packing
        if isinstance(value, unicode):
            value = str(value)

        # only pack actual values and avoid packing empty strings
        # protobuf defaults to empty strings and does no imply a value to set
        if value is None or (isinstance(value, str) and not value):
            continue

        # transform values as needed
        if transformer:
            value = transformer(value)

        # pack and add to existing data
        logger.info("packing: %s - %s", tlv_type, value)
        data += clazz.pack(tlv_type.value, value)

    return data
