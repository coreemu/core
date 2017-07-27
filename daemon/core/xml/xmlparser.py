from xml.dom.minidom import parse

from core.xml.xmlparser0 import CoreDocumentParser0
from core.xml.xmlparser1 import CoreDocumentParser1
from core.xml.xmlutils import get_first_child_by_tag_name


class CoreVersionParser(object):
    """
    Helper class to check the version of Network Plan document.  This
    simply looks for a "Scenario" element; when present, this
    indicates a 0.0 version document.  The dom member is set in order
    to prevent parsing a file twice (it can be passed to the
    appropriate CoreDocumentParser class.)
    """

    DEFAULT_SCENARIO_VERSION = '1.0'

    def __init__(self, filename, options):
        if 'dom' in options:
            self.dom = options['dom']
        else:
            self.dom = parse(filename)
        scenario = get_first_child_by_tag_name(self.dom, 'scenario')
        if scenario:
            version = scenario.getAttribute('version')
            if not version:
                version = self.DEFAULT_SCENARIO_VERSION
            self.version = version
        elif get_first_child_by_tag_name(self.dom, 'Scenario'):
            self.version = '0.0'
        else:
            self.version = 'unknown'


def core_document_parser(session, filename, options):
    vp = CoreVersionParser(filename, options)
    if 'dom' not in options:
        options['dom'] = vp.dom
    if vp.version == '0.0':
        doc = CoreDocumentParser0(session, filename, options)
    elif vp.version == '1.0':
        doc = CoreDocumentParser1(session, filename, options)
    else:
        raise ValueError('unsupported document version: %s' % vp.version)
    return doc
