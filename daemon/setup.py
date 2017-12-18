"""
Defines how CORE will be built for installation.
"""

from setuptools import setup

setup(name="core-python",
      version="5.0",
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
          "enum34",
          "logzero"
      ],
      tests_require=[
          "pytest",
          "pytest-runner"
          "pytest-cov",
          "mock"
      ],
      description="Python components of CORE",
      url="http://www.nrl.navy.mil/itd/ncs/products/core",
      author="Boeing Research & Technology",
      author_email="core-dev@nrl.navy.mil",
      license="BSD",
      long_description="Python scripts and modules for building virtual emulated networks.")
