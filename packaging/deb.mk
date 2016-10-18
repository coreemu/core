DEBBUILD = .debbuild

CORE_VERSION = $(shell cat .version 2> /dev/null)

COREBUILD = $(DEBBUILD)/core-$(CORE_VERSION)

.PHONY: all
all: clean .version build

.PHONY: clean
clean:
	rm -rf $(DEBBUILD)

.PHONY: build
build: changelog
	cd $(COREBUILD) && dpkg-buildpackage -b -us -uc
	@printf "\ndebian packages built in $(DEBBUILD)\n\n"

.PHONY: changelog
changelog: debian
	echo "core ($(CORE_VERSION)-1) unstable; urgency=low" > $(COREBUILD)/debian/changelog.generated
	echo "  * interim package generated from source" >> $(COREBUILD)/debian/changelog.generated
	echo " -- CORE Developers <core-dev@pf.itd.nrl.navy.mil>  $$(date -R)" >> $(COREBUILD)/debian/changelog.generated
	cd $(COREBUILD)/debian && \
	    { test ! -L changelog && mv -f changelog changelog.save; } && \
	    { test "$$(readlink changelog)" = "changelog.generated" || \
	       ln -sf changelog.generated changelog; }

.PHONY: debian
debian: corebuild
	cd $(COREBUILD) && ln -s packaging/deb debian

.PHONY: corebuild
corebuild: $(DEBBUILD) dist
	tar -C $(DEBBUILD) -xzf core-$(CORE_VERSION).tar.gz

.PHONY: dist
dist: Makefile
	$(MAKE) dist

Makefile: configure
	./configure

configure: bootstrap.sh
	./bootstrap.sh

bootstrap.sh:
	@printf "\nERROR: make must be called from the top-level directory:\n"
	@printf "    make -f packaging/$(lastword $(MAKEFILE_LIST))\n\n"
	@false

.version: Makefile
	$(MAKE) $@

$(DEBBUILD):
	mkdir -p $@
