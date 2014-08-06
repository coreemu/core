# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.

import os, glob
from distutils.core import setup
from core.constants import COREDPY_VERSION

# optionally pass CORE_CONF_DIR using environment variable
confdir = os.environ.get('CORE_CONF_DIR')
if confdir is None:
    confdir="/etc/core"

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
      data_files = [("sbin", glob.glob("sbin/core*")),
                    (confdir, ["data/core.conf"]),
                    (confdir, ["data/xen.conf"]),
                    ("share/core/examples", ["examples/controlnet_updown"]),
                    ("share/core/examples",
                     glob.glob("examples/*.py")),
                    ("share/core/examples/netns",
                     glob.glob("examples/netns/*[py,sh]")),
                    ("share/core/examples/services",
                     glob.glob("examples/services/*")),
                    ("share/core/examples/myservices",
                     glob.glob("examples/myservices/*")),
                    ],
      description = "Python components of CORE",
      url = "http://www.nrl.navy.mil/itd/ncs/products/core",
      author = "Boeing Research & Technology",
      author_email = "core-dev@pf.itd.nrl.navy.mil",
      license = "BSD",
      long_description="Python scripts and modules for building virtual " \
          "emulated networks.")
