#
# CORE
# Copyright (c)2011-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#

'''
Helpers for loading and saving XML files. savesessionxml(session, filename) is
the main public interface here.
'''

import os.path
from core.netns import nodes
from xmlparser import CoreDocumentParser
from xmlwriter import CoreDocumentWriter

def opensessionxml(session, filename, start=False, nodecls=nodes.CoreNode):
    ''' Import a session from the EmulationScript XML format.
    '''
    doc = CoreDocumentParser(session, filename, start, nodecls)
    if start:
        session.name = os.path.basename(filename)
        session.filename = filename
        session.node_count = str(session.getnodecount())
        session.instantiate()

def savesessionxml(session, filename):
    ''' Export a session to the EmulationScript XML format.
    '''
    doc = CoreDocumentWriter(session)
    doc.writexml(filename)
