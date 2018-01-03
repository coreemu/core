"""
Defines how CORE will be built for installation.
"""

from setuptools import setup, find_packages

setup(
    name="core",
    version="5.0",
    packages=find_packages(),
    install_requires=[
        "enum34",
    ],
    tests_require=[
        "pytest",
        "pytest-runner",
        "pytest-cov",
        "mock",
    ],
    data_files=[
        ("/etc/core", [
            "data/core.conf", 
            "data/xen.conf",
            "data/logging.conf",
        ]),
        ("/etc/init.d", [
            "../scripts/core-daemon",
        ]),
    ],
    scripts=[
        "sbin/core-cleanup",
        "sbin/core-daemon",
        "sbin/core-manage",
        "sbin/coresendmsg",
        "sbin/core-xen-cleanup",
    ],
    description="Python components of CORE",
    url="http://www.nrl.navy.mil/itd/ncs/products/core",
    author="Boeing Research & Technology",
    author_email="core-dev@nrl.navy.mil",
    license="BSD",
    long_description="Python scripts and modules for building virtual emulated networks."
)
