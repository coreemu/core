# Container Build

This provides a brief overview of using the containerfiles provided to help build CORE
and parts related to it. You should be able to use docker/podman interchangeably.

## Build CORE Packages

There is a Containerfile to help support building CORE packages, using
the latest from a given branch. The environment helps ensure we use an older
version of glibc to avoid incompatibilities.

```shell
<docker|podman> build -t core-build -f Containerfile.core-python .
```

## EMANE Python Bindings

There is a Containerfile to help build EMANE python bindings, which are needed to install
into the CORE virtual environment to support certain EMANE interactions.

```shell
<docker|podman> build -t emane-python -f Containerfile.emane-python .
```

## Rocky/Ubuntu Containers

There a Containerfile to help build and provide a full containerized environment that is inclusive
of CORE, EMANE, and OSPF MDR for both Ubuntu and Rocky Linux.

```shell
<docker|podman> build -t core-rocky -f Containerfile.rocky .
<docker|podman> build -t core-ubuntu -f Containerfile.ubuntu .
```

## Image Tagging for GitHub

Proper tags need to be applied to support pushing built images up to GitHub.

```shell
<docker|podman> tag core-rocky ghcr.io/coreemu/core-rocky:latest
<docker|podman> tag core-rocky ghcr.io/coreemu/core-rocky:<VERSION>
<docker|podman> tag core-ubuntu ghcr.io/coreemu/core-ubuntu:latest
<docker|podman> tag core-ubuntu ghcr.io/coreemu/core-ubuntu:<VERSION>
```
