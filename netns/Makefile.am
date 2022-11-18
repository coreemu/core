# CORE
#
# Makefile for building netns.
#

AM_CFLAGS = -Wall -fno-strict-aliasing -O3 -g @libev_CFLAGS@

SRC_COMMON = vnode_msg.c vnode_cmd.c vnode_chnl.c vnode_io.c \
	     vnode_msg.h vnode_cmd.h vnode_chnl.h vnode_io.h \
	     vnode_tlv.h myerr.h netns.h
SRC_VNODED = vnoded_main.c vnode_server.c netns.c \
	     vnode_server.h
SRC_VCMD = vcmd_main.c vnode_client.c \
	   vnode_client.h
SRC_NETNS = netns_main.c netns.c netns.h

bin_PROGRAMS	= vnoded vcmd netns
vnoded_LDADD = @libev_LIBS@
vnoded_SOURCES = $(SRC_COMMON) $(SRC_VNODED)
vcmd_LDADD = @libev_LIBS@
vcmd_SOURCES = $(SRC_COMMON) $(SRC_VCMD)
netns_SOURCES = $(SRC_NETNS)

# extra cruft to remove
DISTCLEANFILES = Makefile.in MANIFEST
