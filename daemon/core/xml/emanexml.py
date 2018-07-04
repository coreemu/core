from lxml import etree

from core import logger
from core.misc import utils
from core.xml import corexml


def _value_to_params(value):
    """
    Helper to convert a parameter to a parameter tuple.

    :param str value: value string to convert to tuple
    :return: parameter tuple, None otherwise
    """
    try:
        values = utils.make_tuple_fromstr(value, str)

        if not hasattr(values, "__iter__"):
            return None

        if len(values) < 2:
            return None

        return values

    except SyntaxError:
        logger.exception("error in value string to param list")
    return None


def create_file(xml_element, doc_name, file_path):
    doctype = '<!DOCTYPE %(doc_name)s SYSTEM "file:///usr/share/emane/dtd/%(doc_name)s.dtd">' % {"doc_name": doc_name}
    corexml.write_xml_file(xml_element, file_path, doctype=doctype)


def add_param(xml_element, name, value):
    etree.SubElement(xml_element, "param", name=name, value=value)


def add_configurations(xml_element, configurations, config, config_ignore):
    """
    Add emane model configurations to xml element.

    :param lxml.etree.Element xml_element: xml element to add emane configurations to
    :param list[core.config.Configuration] configurations: configurations to add to xml
    :param dict config: configuration values
    :param set config_ignore: configuration options to ignore
    :return:
    """
    for configuration in configurations:
        # ignore custom configurations
        name = configuration.id
        if name in config_ignore:
            continue

        # check if value is a multi param
        value = str(config[name])
        params = _value_to_params(value)
        if params:
            params_element = etree.SubElement(xml_element, "paramlist", name=name)
            for param in params:
                etree.SubElement(params_element, "item", value=param)
        else:
            add_param(xml_element, name, value)
