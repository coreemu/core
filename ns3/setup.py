import glob

from setuptools import setup

_EXAMPLES_DIR = "share/corens3/examples"

setup(
    name="core-ns3",
    version="5.1",
    packages=[
        "corens3",
    ],
    data_files=[(_EXAMPLES_DIR, glob.glob("examples/*"))],
    description="Python ns-3 components of CORE",
    url="http://www.nrl.navy.mil/itd/ncs/products/core",
    author="Boeing Research & Technology",
    author_email="core-dev@nrl.navy.mil",
    license="GPLv2",
    long_description="Python scripts and modules for building virtual simulated networks."
)
