#
# CORE
# Copyright (c)2011-2014 the Boeing Company.
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
from xmlparser import core_document_parser
from xmlwriter import core_document_writer

def opensessionxml(session, filename, start=False, nodecls=nodes.CoreNode):
    ''' Import a session from the EmulationScript XML format.
    '''
    options = {'start': start, 'nodecls': nodecls}
    doc = core_document_parser(session, filename, options)
    if start:
        session.name = os.path.basename(filename)
        session.filename = filename
        session.node_count = str(session.getnodecount())
        session.instantiate()

def savesessionxml(session, filename, version):
    ''' Export a session to the EmulationScript XML format.
    '''
    doc = core_document_writer(session, version)
    doc.writexml(filename)
