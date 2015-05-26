# Copyright (c)2012 the Boeing Company.
# See the LICENSE file included in this directory.

import os, glob
from distutils.core import setup
from corens3.constants import COREDPY_VERSION

setup(name = "corens3-python",
      version = COREDPY_VERSION,
      packages = [
        "corens3",
        ],
      description = "Python ns-3 components of CORE",
      url = "http://www.nrl.navy.mil/itd/ncs/products/core",
      author = "Boeing Research & Technology",
      author_email = "core-dev@pf.itd.nrl.navy.mil",
      license = "GPLv2",
      long_description="Python scripts and modules for building virtual " \
          "simulated networks.")
