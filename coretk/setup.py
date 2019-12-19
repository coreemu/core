from setuptools import find_packages, setup

setup(
    name="coretk",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["netaddr", "pillow"],
    description="CORE GUI",
    url="https://github.com/coreemu/core",
    author="Boeing Research & Technology",
    license="BSD",
)
