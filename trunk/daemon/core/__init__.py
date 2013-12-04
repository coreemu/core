# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.

"""core

Top-level Python package containing CORE components.

See http://www.nrl.navy.mil/itd/ncs/products/core and
http://code.google.com/p/coreemu/ for more information on CORE.

Pieces can be imported individually, for example

    import core.netns.vnode

or everything listed in __all__ can be imported using

    from core import *
"""

__all__ = []

# Automatically import all add-ons listed in addons.__all__
from addons import *
