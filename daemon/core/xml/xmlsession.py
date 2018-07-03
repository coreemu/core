"""
Helpers for loading and saving XML files. savesessionxml(session, filename) is
the main public interface here.
"""

import os.path

from core.enumerations import NodeTypes
from core.misc import nodeutils
from core.xml import corexml
from core.xml.xmlparser import core_document_parser
from core.xml.xmlwriter import core_document_writer


def open_session_xml(session, filename, start=False, nodecls=None):
    """
    Import a session from the EmulationScript XML format.
    """

    # set default node class when one is not provided
    if not nodecls:
        nodecls = nodeutils.get_node_class(NodeTypes.DEFAULT)

    options = {'start': start, 'nodecls': nodecls}
    doc = core_document_parser(session, filename, options)
    if start:
        session.name = os.path.basename(filename)
        session.filename = filename
        session.instantiate()


def save_session_xml(session, filename, version):
    """
    Export a session to the EmulationScript XML format.
    """
    corexml.CoreXmlWriter(session).write(filename)
