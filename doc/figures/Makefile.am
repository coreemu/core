# CORE
# (c)2009-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
#

# define new file extensions for handling figures and html
SUFFIXES 	= .jpg .gif
GIFTOJPG	= convert -background white -flatten

# dia figures can be manually converted to jpg
# On Ubuntu 11.10, this is failing for some reason.
DIATOJPG	= dia -t jpg -e


# these are file extension handlers for automatically converting between image
# file types; the .jpg files are built from .gif files from the GUI

# file extension handler to convert .gif to .jpg
%.jpg:  %.gif
	$(GIFTOJPG) $(top_srcdir)/gui/icons/tiny/$< $@

# file extension handler so we can list .gif as dependency for .gif.jpg
%.gif: 
	@echo "Using GUI file $(top_srcdir)/gui/icons/tiny/$@"


# list of base names for figures
figures		= core-architecture core-workflow
# list of figures + dia suffix
figures_dia	= $(figures:%=%.dia)
# list of figure + jpg suffix
figures_jpg	= $(figures:%=%.jpg)

# icons from the GUI source
icons		= select start router host pc mdr router_green \
		  lanswitch hub wlan \
		  link rj45 tunnel marker oval rectangle text \
		  stop observe plot twonode run document-properties
# list of icons + .gif.jpg suffix
icons_jpg	= $(icons:%=%.jpg)

BUILT_SOURCES =	$(figures_dia) $(figures_jpg) $(icons_jpg)

clean-local:
	rm -f $(icons_jpg)

EXTRA_DIST = $(figures_dia) $(figures_jpg)

# extra cruft to remove
DISTCLEANFILES	= Makefile.in $(icons_jpg)

