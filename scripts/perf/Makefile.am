# CORE
# (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz  <jeffrey.m.ahrenholz@boeing.com>
#
# Makefile for installing performance monitoring scripts.
#

DISTCLEANFILES = Makefile.in


# Hook scripts installed to /usr[/local]/share/core/examples/hooks
hooksdir=$(pkgdatadir)/examples/hooks
dist_hooks_SCRIPTS = perflogstart.sh perflogstop.sh sessiondatacollect.sh \
		     timesyncstop.sh timesyncstart.sh perflogserver.py \
		     configuration_hook.sh datacollect_hook.sh

# Files installed to /etc/core/
perfconfdir=$(sysconfdir)/core
dist_perfconf_DATA = perflogserver.conf

