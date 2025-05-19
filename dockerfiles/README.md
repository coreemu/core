# Container Build

## Build CORE Packages

There is a Dockerfile to help support building CORE packages, using
the latest from a given branch. The environment helps ensure we use an older
version of glibc to avoid incompatibilities.

```shell
docker build -t core-build -f Dockerfile.build .
```

## EMANE Python Bindings

There is a Dockerfile to help build EMANE python bindings, which are needed to install
into the CORE virtual environment to support certain EMANE interactions.

```shell
docker build -t emane-python -f Dockerfile.emane-python .
```

## Rocky/Ubuntu Containers

There a Dockerfile to help build and provide a full containerized environment that is inclusive
of CORE, EMANE, and OSPF MDR for both Ubuntu and Rocky Linux.

```shell
docker build -t core-rocky -f Dockerfile.rocky .
docker build -t core-ubuntu -f Dockerfile.ubuntu .
```

## Image Tagging for GitHub

Proper tags need to be applied to support pushing built images up to GitHub.

```shell
docker tag core-rocky ghcr.io/coreemu/core-rocky:latest
docker tag core-rocky ghcr.io/coreemu/core-rocky:<VERSION>
docker tag core-ubuntu ghcr.io/coreemu/core-ubuntu:latest
docker tag core-ubuntu ghcr.io/coreemu/core-ubuntu:<VERSION>
```
