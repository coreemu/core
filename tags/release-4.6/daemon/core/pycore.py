# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.

"""
This is a convenience module that imports a set of platform-dependent
defaults.
"""

from misc.utils import ensurepath
ensurepath(["/sbin", "/bin", "/usr/sbin", "/usr/bin"])
del ensurepath

from session import Session

import os

if os.uname()[0] == "Linux":
    from netns import nodes
    try:
        from xen import xen
    except ImportError:
        #print "Xen support disabled."
        pass
elif os.uname()[0] == "FreeBSD":
    from bsd import nodes
from phys import pnodes
del os
