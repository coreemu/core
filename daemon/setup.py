# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.

import os, glob
from distutils.core import setup
from core.constants import COREDPY_VERSION

setup(name = "core-python",
      version = COREDPY_VERSION,
      packages = [
        "core",
        "core.addons",
        "core.api",
        "core.emane",
        "core.misc",
        "core.bsd",
        "core.netns",
        "core.phys",
        "core.xen",
        "core.services",
        ],
      description = "Python components of CORE",
      url = "http://www.nrl.navy.mil/itd/ncs/products/core",
      author = "Boeing Research & Technology",
      author_email = "core-dev@pf.itd.nrl.navy.mil",
      license = "BSD",
      long_description="Python scripts and modules for building virtual " \
          "emulated networks.")
