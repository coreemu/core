# CORE
# Copyright (c) 2014 The Boeing Company.
# See the LICENSE file included in this distribution.

from xml.dom.minidom import parse
from xmlutils import getoneelement
from xmlparser1 import CoreDocumentParser1

class CoreVersionParser(object):
    '''\
    Helper class to check the version of Network Plan document.  This
    simply looks for a "Scenario" element; when present, this
    indicates a 1.0 version document.  The dom member is set in order
    to prevent parsing a file twice (it can be passed to the
    appropriate CoreDocumentParser class.)
    '''
    def __init__(self, filename, options={}):
        if 'dom' in options:
            self.dom = options['dom']
        else:
            self.dom = parse(filename)
        self.scenario = getoneelement(self.dom, 'Scenario')
        if self.scenario is not None:
            self.version = 1.0
        else:
            self.version = 'unknown'

def core_document_parser(session, filename, options):
    vp = CoreVersionParser(filename, options)
    if 'dom' not in options:
        options['dom'] = vp.dom
    if vp.version == 1.0:
        doc = CoreDocumentParser1(session, filename, options)
    else:
        raise ValueError, 'unsupported document version: %s' % vp.version
    return doc
