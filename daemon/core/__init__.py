# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.

"""
core

Top-level Python package containing CORE components.

See http://www.nrl.navy.mil/itd/ncs/products/core for more information on CORE.

Pieces can be imported individually, for example

    from core.netns import vnode
"""

# Automatically import all add-ons listed in addons.__all__
from addons import *
