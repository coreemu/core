# Container Build

This provides a brief overview of using the containerfiles provided to help build CORE
and parts related to it. You should be able to use docker/podman interchangeably.

## Building Local

These Containerfiles are dependent on building against a local CORE python package
built against the currently checked out source code. You will need to build images
in proper order to ensure expected artifacts are available.

```shell
# build emane python package
<docker|podman> build -t emane-python -f Containerfile.emane-python .

# build core package from current source code
<docker|podman> build -t core-package -f local/Containerfile.core-package ..

# optionally you can build the core package against source, providing a branch if desired
<docker|podman> build -t core-package --build-arg BRANCH=develop -f github/Containerfile.core-package .

# build variation of a CORE image (rocky, ubuntu, or frr variations)
<docker|podman> build -t core -f local/Containerfile.<type> .
```

## Building from GitHub

These Containerfiles build against packages direct from GitHub.

```shell
# build emane python package
<docker|podman> build -t emane-python -f Containerfile.emane-python .

# build variation of a CORE image (rocky, ubuntu, or frr variations)
<docker|podman> build -t core -f github/Containerfile.<type> .
```

## Image Tagging for GitHub

Proper tags need to be applied to support pushing built images up to GitHub.

```shell
<docker|podman> tag core-rocky ghcr.io/coreemu/core-rocky:latest
<docker|podman> tag core-rocky ghcr.io/coreemu/core-rocky:<VERSION>
<docker|podman> tag core-ubuntu ghcr.io/coreemu/core-ubuntu:latest
<docker|podman> tag core-ubuntu ghcr.io/coreemu/core-ubuntu:<VERSION>
```
