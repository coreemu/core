# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.

"""
Defines how CORE will be built for installation.
"""

from setuptools import setup

from core.constants import COREDPY_VERSION

setup(name="core-python",
      version=COREDPY_VERSION,
      packages=[
          "core",
          "core.addons",
          "core.api",
          "core.bsd",
          "core.emane",
          "core.misc",
          "core.netns",
          "core.phys",
          "core.services",
          "core.xen",
          "core.xml",
      ],
      install_requires=[
        "enum34"
      ],
      setup_requires=[
          "pytest-runner"
      ],
      tests_require=[
          "pytest",
          "pytest-cov",
          "mock"
      ],
      description="Python components of CORE",
      url="http://www.nrl.navy.mil/itd/ncs/products/core",
      author="Boeing Research & Technology",
      author_email="core-dev@pf.itd.nrl.navy.mil",
      license="BSD",
      long_description="Python scripts and modules for building virtual emulated networks.")
