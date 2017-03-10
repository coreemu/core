# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.

"""
This is a convenience module that imports a set of platform-dependent
defaults.
"""

import os

from core.session import Session
from core.phys import pnodes

from core.misc.utils import ensurepath
ensurepath(["/sbin", "/bin", "/usr/sbin", "/usr/bin"])
del ensurepath

if os.uname()[0] == "Linux":
    from core.netns import nodes
    try:
        from core.xen import xen
    except ImportError:
        # print "Xen support disabled."
        pass
elif os.uname()[0] == "FreeBSD":
    from core.bsd import nodes

del os

__all__ = ['Session', 'pnodes', 'nodes', 'xen']
