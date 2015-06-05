# CORE
# Copyright (c) 2015 The Boeing Company.
# See the LICENSE file included in this distribution.

from xmlwriter0 import CoreDocumentWriter0
from xmlwriter1 import CoreDocumentWriter1

def core_document_writer(session, version):
    if version == '0.0':
        doc = CoreDocumentWriter0(session)
    elif version == '1.0':
        doc = CoreDocumentWriter1(session)
    else:
        raise ValueError, 'unsupported document version: %s' % version
    return doc
