"""
Defines how CORE netns will be build for installation.
"""

from setuptools import setup, Extension
from distutils.command.install import install


class CustomInstall(install):
    user_options = install.user_options + [
        ("service=", None, "determine which service file to include")
    ]

    def initialize_options(self):
        install.initialize_options(self)
        self.service = "sysv"

    def finalize_options(self):
        install.finalize_options(self)
        assert self.service in ("sysv", "systemd"), "must be sysv or systemd"

    def run(self):
        install.run(self)

netns = Extension(
    "netns",
    sources=[
        "netnsmodule.c",
        "netns.c"
    ]
)

vcmd = Extension(
    "vcmd",
    sources=[
        "vcmdmodule.c",
        "vnode_client.c",
        "vnode_chnl.c",
        "vnode_io.c",
        "vnode_msg.c",
        "vnode_cmd.c",
    ],
    library_dirs=["build/lib"],
    libraries=["ev"]
)

setup(
    name="core-netns",
    version="1.0",
    description="Extension modules to support virtual nodes using Linux network namespaces",
    scripts=["vcmd", "vnoded", "netns"],
    ext_modules=[
        netns,
        vcmd
    ],
    url="http://www.nrl.navy.mil/itd/ncs/products/core",
    author="Boeing Research & Technology",
    author_email="core-dev@nrl.navy.mil",
    license="BSD",
    long_description="Extension modules and utilities to support virtual nodes using Linux network namespaces",
    cmdclass={
        "install": CustomInstall
    }
)
