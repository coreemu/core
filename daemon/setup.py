"""
Defines how CORE will be built for installation.
"""

import glob
import os

from setuptools import find_packages
from distutils.core import setup

_CORE_DIR = "/etc/core"
_MAN_DIR = "share/man/man1"
_EXAMPLES_DIR = "share/core"


def recursive_files(data_path, files_path):
    data_files = []
    for path, directories, filenames in os.walk(files_path):
        directory = os.path.join(data_path, path)
        files = []
        for filename in filenames:
            files.append(os.path.join(path, filename))
        data_files.append((directory, files))
    return data_files


def glob_files(glob_path):
    return glob.glob(glob_path)


data_files = [
    (_CORE_DIR, [
        "data/core.conf",
        "data/logging.conf",
    ]),
    (_MAN_DIR, glob_files("../doc/man/**.1")),
]
data_files.extend(recursive_files(_EXAMPLES_DIR, "examples"))

setup(
    name="core",
    version="5.1",
    packages=find_packages(),
    install_requires=[
        "enum34",
        "lxml"
    ],
    tests_require=[
        "pytest",
        "pytest-runner",
        "pytest-cov",
        "mock",
    ],
    data_files=data_files,
    scripts=glob.glob("scripts/*"),
    description="Python components of CORE",
    url="http://www.nrl.navy.mil/itd/ncs/products/core",
    author="Boeing Research & Technology",
    author_email="core-dev@nrl.navy.mil",
    license="BSD",
    long_description="Python scripts and modules for building virtual emulated networks.",
)
