VERSION		:= $(shell dpkg -l linux-source 2> /dev/null | \
	awk '/^i/ {print gensub("([0-9]+[.][0-9]+[.][0-9]+)[.0-9]*", "\\1", "1", $$3)}')
TARBALL		:= /usr/src/linux-source-$(VERSION).tar.bz2

SUBVERSION	:= -core
REVISION	:= 1.0

PATCHDIR	:= patches
PATCHES		:= $(sort $(wildcard $(PATCHDIR)/*.patch))

CONFIG		:= config.core

DEPDEBS		:= linux-source kernel-package po-debconf gettext

CONCURRENCY_LEVEL	:= $(shell lscpu 2> /dev/null | \
	awk '/^CPU\(s\)/ {print $$2}')
ifeq ($(strip $(CONCURRENCY_LEVEL)),)
CONCURRENCY_LEVEL	:= 1
endif

MAINTAINER	?= $(shell id -nu)
EMAIL		?= $(MAINTAINER)@$(shell hostname -f)

MAKEKPKGFLAGS	:= --initrd --rootcmd fakeroot --us --uc	\
    --append-to-version $(SUBVERSION) --revision $(REVISION)

.PHONY: build
build: debcheck defaultconfig patch
	export CONCURRENCY_LEVEL="$(CONCURRENCY_LEVEL)"			\
	    KPKG_MAINTAINER="$(MAINTAINER)" KPKG_EMAIL="$(EMAIL)";	\
	cd linux-source-$(VERSION) &&					\
	    if [ -f ../$(CONFIG) ]; then				\
	        cat ../$(CONFIG) >> .config;				\
	    fi &&							\
	    fakeroot make-kpkg $(MAKEKPKGFLAGS) binary-arch

.PHONY: debcheck
debcheck:
	for d in $(DEPDEBS); do						\
	    if ! dpkg-query -s $$d > /dev/null 2>&1; then		\
		echo ERROR: build dependency not installed: $$d >&2;	\
		exit 1;							\
	    fi;								\
	done

.PHONY: defaultconfig
defaultconfig: linux-source-$(VERSION)
	export KPKG_MAINTAINER="$(MAINTAINER)" KPKG_EMAIL="$(EMAIL)";	   \
	cd linux-source-$(VERSION) && make-kpkg $(MAKEKPKGFLAGS) configure

.PHONY: patch
patch: linux-source-$(VERSION) patch-stamp
patch-stamp: $(PATCHES)
	for p in $^; do							\
	    if ! patch -d linux-source-$(VERSION) -p1 < $$p; then	\
		echo ERROR: applying patch failed: $$p >&2;		\
		exit 1;							\
	    fi;								\
	done
	touch patch-stamp

.PHONY: source
source: linux-source-$(VERSION)

linux-source-$(VERSION): $(TARBALL)
	tar -xjf $^

.PHONY: clean
clean:
	rm -rf linux-source-$(VERSION) patch-stamp
