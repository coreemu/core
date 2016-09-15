RPMBUILD = .rpmbuild

CORE_VERSION = $(shell cat .version 2> /dev/null)

.PHONY: all
all: clean .version build

.PHONY: clean
clean:
	rm -rf $(RPMBUILD)

.PHONY: build
build: dist
	for d in SOURCES SPECS; do mkdir -p $(RPMBUILD)/$$d; done
	cp -afv core-$(CORE_VERSION).tar.gz $(RPMBUILD)/SOURCES
	cp -afv packaging/rpm/core.spec $(RPMBUILD)/SPECS
	rpmbuild -bb --clean $(RPMBUILD)/SPECS/core.spec \
	    --define "_topdir $$PWD/.rpmbuild"
	@printf "\nRPM packages saved in $(RPMBUILD)/RPMS\n\n"

.PHONY: dist
dist: Makefile
	$(MAKE) dist

Makefile: configure
	./configure --prefix=/usr --exec-prefix=/usr

configure: bootstrap.sh
	./bootstrap.sh

bootstrap.sh:
	@printf "\nERROR: make must be called from the top-level directory:\n"
	@printf "    make -f packaging/$(lastword $(MAKEFILE_LIST))\n\n"
	@false

.version: Makefile
	$(MAKE) $@

$(RPMBUILD):
	mkdir -p $@
