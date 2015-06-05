# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.

import os, glob
from distutils.core import setup, Extension

netns = Extension("netns", sources = ["netnsmodule.c", "netns.c"])
vcmd = Extension("vcmd",
                 sources = ["vcmdmodule.c",
                            "vnode_client.c",
                            "vnode_chnl.c",
                            "vnode_io.c",
                            "vnode_msg.c",
                            "vnode_cmd.c",
                            ],
                 library_dirs = ["build/lib"],
                 libraries = ["ev"])

setup(name = "core-python-netns",
      version = "1.0",
      description = "Extension modules to support virtual nodes using " \
          "Linux network namespaces",
      ext_modules = [netns, vcmd],
      url = "http://www.nrl.navy.mil/itd/ncs/products/core",
      author = "Boeing Research & Technology",
      author_email = "core-dev@pf.itd.nrl.navy.mil",
      license = "BSD",
      long_description="Extension modules and utilities to support virtual " \
          "nodes using Linux network namespaces")
