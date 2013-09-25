/*
 * Copyright (c) 2006-2011 the Boeing Company
 * ng_wlan is based on ng_hub, which is:
 * Copyright (c) 2004 Ruslan Ermilov
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 */

#ifndef _NETGRAPH_NG_WLAN_H_
#define	_NETGRAPH_NG_WLAN_H_

/* Node type name and magic cookie. */
#define	NG_WLAN_NODE_TYPE	"wlan"
#define	NGM_WLAN_COOKIE		1146673193

/* Control message parse info */
struct ng_wlan_config {
	u_int32_t	node1;
	u_int32_t	node2;
};
#define NG_WLAN_CONFIG_TYPE_INFO  { 		\
	{ "node1", &ng_parse_uint32_type },	\
	{ "node2", &ng_parse_uint32_type },	\
	{ NULL }				\
}

struct ng_wlan_set_data {
	u_int32_t	node1;
	u_int32_t	node2;
	u_int64_t	delay;	/* keep these aligned with struct ng_wlan_tag */
	u_int64_t	bandwidth;
	u_int16_t	per;
	u_int16_t	duplicate;
	u_int32_t	jitter;
	u_int16_t	burst;
};
#define NG_WLAN_SET_DATA_TYPE_INFO  { 		\
	{ "node1", &ng_parse_uint32_type },	\
	{ "node2", &ng_parse_uint32_type },	\
	{ "delay", &ng_parse_uint64_type },	\
	{ "bandwidth", &ng_parse_uint64_type },	\
	{ "per", &ng_parse_uint16_type },	\
	{ "duplicate", &ng_parse_uint16_type },	\
	{ "jitter", &ng_parse_uint32_type },	\
	{ "burst", &ng_parse_uint16_type },	\
	{ NULL }				\
}

struct ng_wlan_mer {
	uint16_t	mer;
	uint16_t	mburst;
};
#define NG_WLAN_MER_TYPE_INFO {			\
	{ "mer", &ng_parse_uint16_type }, 	\
	{ "mburst", &ng_parse_uint16_type }, 	\
	{ NULL } 				\
}

#ifdef MULTICAST_LOOKUPS
struct ng_wlan_multicast_set_data {
	u_int32_t	node1;
	u_int32_t	node2;
	u_int32_t	group;
	u_int32_t	source;
};
#define NG_WLAN_MULTICAST_SET_DATA_TYPE_INFO  { \
	{ "node1", &ng_parse_uint32_type },	\
	{ "node2", &ng_parse_uint32_type },	\
	{ "group", &ng_parse_uint32_type },	\
	{ "source", &ng_parse_uint32_type },	\
	{ NULL }				\
}
#endif /* MULTICAST_LOOKUPS */

/* List of supported Netgraph control messages */
enum {
	NGM_WLAN_LINK_NODES = 1,
	NGM_WLAN_UNLINK_NODES,
	NGM_WLAN_NODES_SET,
	NGM_WLAN_NODES_UNSET,
	NGM_WLAN_NODES_GET,
	NGM_WLAN_MER,		/* MULTICAST_ERR */
	NGM_WLAN_MULTICAST_SET, /* MULTICAST_LOOKUPS */
	NGM_WLAN_MULTICAST_UNSET, /* MULTICAST_LOOKUPS */
	NGM_WLAN_MULTICAST_GET, /* MULTICAST_LOOKUPS */
};

#endif /* _NETGRAPH_NG_WLAN_H_ */
