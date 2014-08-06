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

#include <sys/param.h>
#include <sys/systm.h>
#include <sys/kernel.h>
#include <sys/mbuf.h>
#include <sys/malloc.h>
#include <sys/errno.h>
#ifdef MULTICAST_LOOKUPS
#include <netinet/in_systm.h>	/* in.h */
#include <netinet/in.h>		/* IN_MULTICAST(), etc */
#include <netinet/ip.h>		/* struct ip */
#include <net/ethernet.h>	/* struct ether_header */
#endif /* MULTICAST_LOOKUPS */

#include <netgraph/ng_message.h>
#include <netgraph/ng_parse.h>
#include <netgraph/netgraph.h>
/* #include <netgraph/ng_wlan.h> */
#include "ng_wlan.h"
#include "ng_wlan_tag.h"

#ifdef NG_SEPARATE_MALLOC
MALLOC_DEFINE(M_NETGRAPH_WLAN, "netgraph_wlan", "netgraph WLAN node ");
#else
#define M_NETGRAPH_WLAN M_NETGRAPH
#endif

#ifdef WLAN_GIANT_LOCK
struct mtx ng_wlan_giant;
#endif

#ifdef MULTICAST_LOOKUPS
#define mtod_off(m,off,t)       ((t)(mtod((m),caddr_t)+(off)))
#define IP_MCAST_HDR_OFFSET	ETHER_HDR_LEN
#define IP_MCAST_MIN_LEN	(IP_MCAST_HDR_OFFSET + sizeof(struct ip))
#endif /* MULTICAST_LOOKUPS */

/*
 * WLAN node data types
 */
/* Hash table entry for wlan connectivity */
struct ng_wlan_hent {
	ng_ID_t 	l_id;
	ng_ID_t 	g_id;
	int		linked;
	u_int64_t	delay;
	u_int64_t	bandwidth;
	u_int16_t	per;
	u_int16_t	duplicate;
	u_int32_t	jitter;
	u_int16_t	burst;
	SLIST_ENTRY(ng_wlan_hent)	next;
};

/* Hash table bucket declaration */
/* struct ng_wlan_bucket {
 	struct ng_wlan_hent *slh_first;
};*/
SLIST_HEAD(ng_wlan_bucket, ng_wlan_hent);

#define MIN_BUCKETS 256
#define HASH(a, b)   ( ((a << 16) + b) % MIN_BUCKETS )

#define IS_PEER_KSOCKET(h) \
	(NG_PEER_NODE(h) != NULL && \
	 NG_PEER_NODE(h)->nd_type->name[0] == 'k' && \
	 NG_PEER_NODE(h)->nd_type->name[1] == 's')

/* WLAN node private data */
struct ng_wlan_private {
	struct ng_wlan_bucket *tab;
#ifndef FREEBSD411
	struct mtx ng_wlan_tab_lock;
#ifdef MULTICAST_LOOKUPS
	struct ng_wlan_mcast_bucket *mcast_tab;
	struct mtx ng_wlan_mcast_tab_lock;
	int multicast_enabled;
#endif
#endif /* !FREEBSD411 */
	int persistent;
	u_int16_t mer; /* multicast error rate */
	u_int16_t mburst; /* multicast burst rate */
};
typedef struct ng_wlan_private *priv_p;

/*
 * Local function declarations
 */
static int ng_wlan_lookup(node_p node, hook_p hook1, hook_p hook2,
	struct ng_wlan_tag *tag);
static int ng_wlan_unlink(node_p node, ng_ID_t node1, ng_ID_t node2);
static int ng_wlan_link(node_p node, ng_ID_t node1, ng_ID_t node2, 
	struct ng_wlan_set_data *data);

#ifdef MULTICAST_LOOKUPS
static int ng_wlan_mcast_lookup(node_p node, hook_p hook1, hook_p hook2, 
	u_int32_t group, u_int32_t source);
static int ng_wlan_mcast_link(node_p node, ng_ID_t node1, ng_ID_t node2,
	u_int32_t group, u_int32_t source, int unlink);

/* Hash table entry for multicast connectivity */
struct ng_wlan_mcast_hent {
	ng_ID_t 	l_id;
	ng_ID_t 	g_id;
	u_int32_t	group;
	u_int32_t	source;
	int		linked;
	SLIST_ENTRY(ng_wlan_mcast_hent)	next;
};

SLIST_HEAD(ng_wlan_mcast_bucket, ng_wlan_mcast_hent);
#define MCAST_HASH(a, b, g)   ( (((a << 16) + b) & g) % MIN_BUCKETS )
#endif /* MULTICAST_LOOKUPS */

/*
 * Netgraph node methods
 */
#ifndef FREEBSD411
static int ng_wlan_modevent(module_t mod, int type, void *unused);
#endif
static ng_constructor_t	ng_wlan_constructor;
static ng_rcvmsg_t	ng_wlan_rcvmsg;
static ng_shutdown_t	ng_wlan_rmnode;
static ng_newhook_t	ng_wlan_newhook;
static ng_rcvdata_t	ng_wlan_rcvdata;
#ifndef FREEBSD411
static ng_rcvdata_t	ng_wlan_rcvdata_ks;
#endif
static ng_disconnect_t	ng_wlan_disconnect;

/* Parse types */
static const struct ng_parse_struct_field ng_wlan_link_type_fields[]
	= NG_WLAN_CONFIG_TYPE_INFO;
static const struct ng_parse_type ng_wlan_link_type = {
	&ng_parse_struct_type,
	&ng_wlan_link_type_fields
};
static const struct ng_parse_struct_field ng_wlan_set_type_fields[]
	= NG_WLAN_SET_DATA_TYPE_INFO;
static const struct ng_parse_type ng_wlan_set_type = {
	&ng_parse_struct_type,
	&ng_wlan_set_type_fields
};
static const struct ng_parse_struct_field ng_wlan_mer_type_fields[]
	= NG_WLAN_MER_TYPE_INFO;
static const struct ng_parse_type ng_wlan_mer_type = {
	&ng_parse_struct_type,
	&ng_wlan_mer_type_fields
};
#ifdef MULTICAST_LOOKUPS
static const struct ng_parse_struct_field ng_wlan_multicast_set_type_fields[]
	= NG_WLAN_MULTICAST_SET_DATA_TYPE_INFO;
static const struct ng_parse_type ng_wlan_multicast_set_type = {
	&ng_parse_struct_type,
	&ng_wlan_multicast_set_type_fields
};
#endif /* MULTICAST_LOOKUPS */

/* List of commands and how to convert arguments to/from ASCII */
static const struct ng_cmdlist ng_wlan_cmdlist[] = {
	{
	  NGM_WLAN_COOKIE,
	  NGM_WLAN_LINK_NODES,
	  "link",
	  &ng_wlan_link_type,
	  NULL
	},
	{
	  NGM_WLAN_COOKIE,
	  NGM_WLAN_UNLINK_NODES,
	  "unlink",
	  &ng_wlan_link_type,
	  NULL
	},
	{
	  NGM_WLAN_COOKIE,
	  NGM_WLAN_NODES_SET,
	  "set",
	  &ng_wlan_set_type,
	  NULL
	},
	{
	  NGM_WLAN_COOKIE,
	  NGM_WLAN_NODES_UNSET,
	  "unset",
	  &ng_wlan_link_type,
	  NULL
	},
	{
	  NGM_WLAN_COOKIE,
	  NGM_WLAN_NODES_GET,
	  "get",
	  &ng_wlan_link_type,
	  &ng_wlan_set_type
	},
	{
	  NGM_WLAN_COOKIE,
	  NGM_WLAN_MER,
	  "mer",
	  &ng_wlan_mer_type,
	  NULL
	},
#ifdef MULTICAST_LOOKUPS
	{
	  NGM_WLAN_COOKIE,
	  NGM_WLAN_MULTICAST_SET,
	  "mcastset",
	  &ng_wlan_multicast_set_type,
	  NULL
	},
	{
	  NGM_WLAN_COOKIE,
	  NGM_WLAN_MULTICAST_UNSET,
	  "mcastunset",
	  &ng_wlan_multicast_set_type,
	  NULL
	},
	{
	  NGM_WLAN_COOKIE,
	  NGM_WLAN_MULTICAST_GET,
	  "mcastget",
	  &ng_wlan_multicast_set_type,
	  &ng_wlan_multicast_set_type
	},
#endif /* MULTICAST_LOOKUPS */
	{ 0 }
};

/*
 * Netgraph node type descriptor
 */
static struct ng_type ng_wlan_typestruct = {
	.version =	NG_ABI_VERSION,
	.name =		NG_WLAN_NODE_TYPE,
#ifndef FREEBSD411
	.mod_event =	ng_wlan_modevent,
#endif
	.constructor =	ng_wlan_constructor,
	.rcvmsg =	ng_wlan_rcvmsg,
	.shutdown =	ng_wlan_rmnode,
	.newhook =	ng_wlan_newhook,
	.rcvdata =	ng_wlan_rcvdata,
	.disconnect =	ng_wlan_disconnect,
	.cmdlist =	ng_wlan_cmdlist,
};
NETGRAPH_INIT(wlan, &ng_wlan_typestruct);

#ifndef FREEBSD411
/*
 * Function implementations
 */
static int
ng_wlan_modevent(module_t mod, int type, void *unused)
{
	int error = 0;

	switch (type) {
	case MOD_LOAD:
#ifdef WLAN_GIANT_LOCK
		mtx_init(&ng_wlan_giant, "ng_wlan_giant", NULL, MTX_DEF);
#endif
		break;
	case MOD_UNLOAD:
#ifdef WLAN_GIANT_LOCK
		mtx_destroy(&ng_wlan_giant);
#endif
		break;
	default:
		error = EOPNOTSUPP;
		break;
	}

	return (error);
}
#endif /* !FREEBSD411 */

#ifdef FREEBSD411
static int
ng_wlan_constructor(node_p *nodep)
#else
static int
ng_wlan_constructor(node_p node)
#endif
{
	priv_p priv;
#ifdef FREEBSD411
	int error=0;
#endif
	
	/* initialize the hash table */
	MALLOC( priv, priv_p, 
		sizeof(struct ng_wlan_private),
		M_NETGRAPH_WLAN, M_NOWAIT | M_ZERO);
	if (priv == NULL)
		return (ENOMEM);

	MALLOC(	priv->tab, struct ng_wlan_bucket *, 
		MIN_BUCKETS * sizeof(struct ng_wlan_bucket),
		M_NETGRAPH_WLAN, M_NOWAIT | M_ZERO);
	if (priv->tab == NULL) {
		FREE(priv, M_NETGRAPH_WLAN);
		return (ENOMEM);
	}
#ifdef FREEBSD411
	/* Call the generic node constructor. */
	if ((error=ng_make_node_common(&ng_wlan_typestruct, nodep))) {
		FREE(priv->tab, M_NETGRAPH_WLAN);
		FREE(priv, M_NETGRAPH_WLAN);
		return(error);
	}
	NG_NODE_SET_PRIVATE(*nodep, priv);
#else /* FREEBSD411 */
#ifdef MULTICAST_LOOKUPS
	priv->multicast_enabled = 0; /* turned off, until ng_wlan_mcast_link()*/
	/* initialize multicast hash table */
	MALLOC(	priv->mcast_tab, struct ng_wlan_mcast_bucket *, 
		MIN_BUCKETS * sizeof(struct ng_wlan_mcast_bucket),
		M_NETGRAPH_WLAN, M_NOWAIT | M_ZERO);
	if (priv->mcast_tab == NULL) {
		FREE(priv->tab, M_NETGRAPH_WLAN);
		FREE(priv, M_NETGRAPH_WLAN);
		return (ENOMEM);
	}
	mtx_init(&priv->ng_wlan_mcast_tab_lock, "ng_wlan_mcast_tab_lock", NULL,
		MTX_DEF);
#endif /* MULTICAST_LOOKUPS */
	mtx_init(&priv->ng_wlan_tab_lock, "ng_wlan_tab_lock", NULL, MTX_DEF);
	NG_NODE_SET_PRIVATE(node, priv);
#endif /* FREEBSD411 */

	return (0);
}

static  int
ng_wlan_newhook(node_p node, hook_p hook, const char *name)
{
	const priv_p priv = NG_NODE_PRIVATE(node);

	/* ksocket hooks "ks0", "ks1", etc. get special receive function */
	if (name[0] == 'k' && name[1] == 's') {
#ifndef FREEBSD411
		NG_HOOK_SET_RCVDATA(hook, ng_wlan_rcvdata_ks);
#endif
		return 0;
	}

	if (strcmp(name, "anchor") == 0) {
		if (priv->persistent)
			return(EISCONN);
                priv->persistent = 1;
	}
	return 0;
}

/*
 * Receive a control message.
 */
#ifdef FREEBSD411
static int
ng_wlan_rcvmsg(node_p node, struct ng_mesg *msg,
	const char *retaddr, struct ng_mesg **rptr)
#else
static int
ng_wlan_rcvmsg(node_p node, item_p item, hook_p lasthook)
#endif
{
	const priv_p priv = NG_NODE_PRIVATE(node);
	struct ng_mesg *resp = NULL;
	int error = 0;
	struct ng_wlan_config *nodes;
	struct ng_wlan_set_data *set_data;
	struct ng_wlan_tag tag;
	u_int32_t node1, node2;
	struct ng_hook h1, h2;
	struct ng_node n1, n2;
#ifndef FREEBSD411
	struct ng_mesg *msg;
#ifdef MULTICAST_LOOKUPS
	struct ng_wlan_multicast_set_data *mcsd;
	u_int32_t group, src;
	int unlink;
#endif /* MULTICAST_LOOKUPS */
#endif

#ifndef FREEBSD411
#ifdef WLAN_GIANT_LOCK
	mtx_lock(&ng_wlan_giant);
#else
	mtx_lock(&priv->ng_wlan_tab_lock);
#ifdef MULTICAST_LOOKUPS
	mtx_lock(&priv->ng_wlan_mcast_tab_lock);
#endif /* MULTICAST_LOOKUPS */
#endif
	NGI_GET_MSG(item, msg);
#endif /* !FREEBSD411 */

	switch (msg->header.typecookie) {
	case NGM_WLAN_COOKIE:
		switch (msg->header.cmd) {
			/* all of these messages take (node1=a,node2=b) param */
		case NGM_WLAN_LINK_NODES:
		case NGM_WLAN_UNLINK_NODES:
		case NGM_WLAN_NODES_UNSET:
		case NGM_WLAN_NODES_GET:
			if (msg->header.arglen
			    != sizeof(struct ng_wlan_config)) {
				error = EINVAL;
				break;
			}
			nodes = (struct ng_wlan_config *)msg->data;
			node1 = nodes->node1;
			node2 = nodes->node2;
			if (msg->header.cmd == NGM_WLAN_NODES_GET) {
				NG_MKRESPONSE(resp, msg, sizeof(*set_data), 
						M_NOWAIT);
				if (resp == NULL) {
					error = ENOMEM;
					break;
				}
				set_data = (struct ng_wlan_set_data*)resp->data;
				bzero(set_data, sizeof(*set_data));
				/* make fake peer/node structures for lookup */
#ifdef FREEBSD411
				h1.peer = &h2; h2.peer = &h1;
				h1.node = &n1; h2.node = &n2;
				n1.ID = node1; n2.ID = node2;
#else
				h1.hk_peer = &h2; h2.hk_peer = &h1;
				h1.hk_node = &n1; h2.hk_node = &n2;
				n1.nd_ID = node1; n2.nd_ID = node2;
#endif
				if (ng_wlan_lookup(node, &h1, &h2, &tag)) {
					set_data->node1 = node1;
					set_data->node2 = node2;
					WLAN_TAG_COPY(set_data, (&tag));
				} /* if not found, node1/node2 will be zero */
				break;
			}
			if (msg->header.cmd == NGM_WLAN_LINK_NODES)
				error = ng_wlan_link(node, node1, node2, NULL);
			else
				error = ng_wlan_unlink(node, node1, node2);
			break;
		case NGM_WLAN_NODES_SET:
			if (msg->header.arglen
			    != sizeof(struct ng_wlan_set_data)) {
				error = EINVAL;
				break;
			}
			set_data = (struct ng_wlan_set_data *)msg->data;
			node1 = set_data->node1;
			node2 = set_data->node2;
			if (set_data->delay > NG_WLAN_MAX_DELAY ||
			    set_data->bandwidth > NG_WLAN_MAX_BW ||
			    set_data->per > NG_WLAN_MAX_PER ||
			    set_data->duplicate > NG_WLAN_MAX_DUP ||
			    set_data->jitter > NG_WLAN_MAX_JITTER ||
			    set_data->burst > NG_WLAN_MAX_BURST) {
			    error = EINVAL;
			    break;
			}
			error = ng_wlan_link(node, node1, node2, set_data);
			break;
		case NGM_WLAN_MER:
			if (msg->header.arglen != sizeof(struct ng_wlan_mer)) {
				error = EINVAL;
				break;
			}
			priv->mer = *((u_int16_t *)msg->data);
			priv->mburst = *((u_int16_t *)&msg->data[2]);
			break;
		case NGM_WLAN_MULTICAST_SET:
		case NGM_WLAN_MULTICAST_UNSET:
		case NGM_WLAN_MULTICAST_GET:
#ifndef MULTICAST_LOOKUPS
			error = ENOTSUP;
			break;
#else
			if (msg->header.arglen
			    != sizeof(struct ng_wlan_multicast_set_data)) {
				error = EINVAL;
				break;
			}
			unlink = (msg->header.cmd == NGM_WLAN_MULTICAST_UNSET);
			mcsd = (struct ng_wlan_multicast_set_data *)msg->data;
			node1 = mcsd->node1;
			node2 = mcsd->node2;
			group = mcsd->group;
			src   = mcsd->source;
			if (msg->header.cmd == NGM_WLAN_MULTICAST_GET) {
				NG_MKRESPONSE(resp, msg, sizeof(*mcsd), 
						M_NOWAIT);
				if (resp == NULL) {
					error = ENOMEM;
					break;
				}
				mcsd = (struct ng_wlan_multicast_set_data*)
					resp->data;
				bzero(mcsd, sizeof(*mcsd));
				/* make fake peer/node structures for lookup */
#ifdef FREEBSD411
				h1.peer = &h2; h2.peer = &h1;
				h1.node = &n1; h2.node = &n2;
				n1.ID = node1; n2.ID = node2;
#else
				h1.hk_peer = &h2; h2.hk_peer = &h1;
				h1.hk_node = &n1; h2.hk_node = &n2;
				n1.nd_ID = node1; n2.nd_ID = node2;
#endif
				if (ng_wlan_mcast_lookup(node, &h1, &h2, group,
							src)){
					mcsd->node1 = node1;
					mcsd->node2 = node2;
					mcsd->group = group;
				} /* if not found, node1/node2 will be zero */
				break;
			}
			error = ng_wlan_mcast_link(node, node1,	node2, group,
					src, unlink);
			break;
#endif /* MULTICAST_LOOKUPS */
		default:
			error = EINVAL;
			break;
		}
		break;
	default:
		error = EINVAL;
		break;
	}

#ifndef FREEBSD411
	NG_RESPOND_MSG(error, node, item, resp);
#endif
	NG_FREE_MSG(msg);

#ifndef FREEBSD411
#ifdef WLAN_GIANT_LOCK
	mtx_unlock(&ng_wlan_giant);
#else
	mtx_unlock(&priv->ng_wlan_tab_lock);
#ifdef MULTICAST_LOOKUPS
	mtx_unlock(&priv->ng_wlan_mcast_tab_lock);
#endif /* MULTICAST_LOOKUPS */
#endif
#endif
	return(error);
}


#ifdef FREEBSD411
/*
 * Handle incoming data from connected netgraph hooks.
 * FreeBSD 4.11 version uses netgraph metadata.
 * Does not support ksocket backchannel, multicast lookups.
 */
static int
ng_wlan_rcvdata(hook_p hook, struct mbuf *m, meta_p meta)
{
	const node_p node = NG_HOOK_NODE(hook);
	const priv_p priv = NG_NODE_PRIVATE(node);
	int error = 0;
	hook_p hook2;
	struct mbuf *m2;
	int nhooks;
	struct ng_wlan_tag *tag = NULL;

	/* Checking for NG_INVALID flag fixes race upon shutdown */
	if ((NG_NODE_NOT_VALID(node)) ||
	    ((nhooks = NG_NODE_NUMHOOKS(node)) == 1)) {
		NG_FREE_DATA(m, meta);
		return (0);
	}

	/* Meta information is not preserved by this node but replaced with
	 * its own data. This sets meta = NULL */
	NG_FREE_META(meta);

	/* Count number of linked nodes, not just number of hooks */
	nhooks = 0;
	LIST_FOREACH(hook2, &node->hooks, hooks)
	{
		/* TODO: maintain a count of the number of linked nodes */
		if (hook2 == hook)
			continue;
		if (!ng_wlan_lookup(node, hook, hook2, NULL))
			continue;
		nhooks++;
	}
	if (nhooks==0) /* Nobody to receive the data */
		goto rcvdata_free_item_error;
	LIST_FOREACH(hook2, &node->hooks, hooks) 
	{
		if (hook2 == hook)
			continue;
		/* Allocate a meta+tag for sending with the data, which may or 
		   may not be used. If used, the ptr is set to NULL for the
		   next loop iteration; unused (non-NULL ptr) will be freed
		   after loop.
		 */
		if (!meta) {
			MALLOC(meta, meta_p, WLAN_META_SIZE,
				M_NETGRAPH, M_NOWAIT | M_ZERO);
			if (!meta) goto rcvdata_free_item_error_nobufs;
			meta->used_len = (u_short) WLAN_META_SIZE;
			meta->allocated_len = (u_short) WLAN_META_SIZE;
			meta->flags = 0;
			meta->priority = WLAN_META_PRIORITY;
			meta->discardability = -1;
			tag = (struct ng_wlan_tag*)meta->options;
			tag->meta_hdr.cookie = NGM_WLAN_COOKIE;
			tag->meta_hdr.type = NG_TAG_WLAN;
			tag->meta_hdr.len = sizeof(struct ng_wlan_tag);
		}
		WLAN_TAG_ZERO(tag);

		if ( !ng_wlan_lookup(node, hook, hook2, tag)) {
			/* determine if peers are connected, fill in tag data */
			continue;
		}
		if ((m->m_flags & M_MCAST) && (priv->mer > 0) && tag) {
			tag->per = priv->mer; /* use configured mcast error */
			tag->burst = priv->mburst; /* use conf mcast burst */
		}

		if (--nhooks == 0) { /* nhooks is really number of links */
			if (tag && TAG_HAS_DATA(tag)) {
				/* send metadata and set meta = NULL */
				NG_SEND_DATA(error, hook2, m, meta);
				tag = NULL;	/* tag used */
			} else {
				/* Don't send any metadata */
				NG_SEND_DATA_ONLY(error, hook2, m);
			}
			break; /* no need to loop and malloc */
		} else {
			if ((m2 = m_dup(m, M_DONTWAIT)) == NULL)
				goto rcvdata_free_item_error_nobufs;
			if (tag && TAG_HAS_DATA(tag)) {
				/* send metadata and set meta = NULL */
				NG_SEND_DATA(error, hook2, m2, meta);
				tag = NULL;	/* tag used */
			} else {
				/* Don't send any metadata */
				NG_SEND_DATA_ONLY(error, hook2, m2);
				if (error) /* XXX free mbuf? */
					continue;	/* don't give up */
			}
		} /* end if nhooks==0 */
	} /* end FOREACH hook */

	if (meta) /* cleanup unused meta+tag */
		NG_FREE_META(meta);

	goto rcvdata_out;

rcvdata_free_item_error_nobufs:
	error = ENOBUFS;
rcvdata_free_item_error:
	NG_FREE_DATA(m, meta);

rcvdata_out:
	return (error);
}

#else /* FREEBSD411 */
/*
 * Handle incoming data from connected netgraph hooks.
 * FreeBSD 7.0 version uses mbuf tags; has additional features:
 *  - ksocket backchannel for connecting two ng_wlans together
 *  - multicast lookups for different forwarding behavior for multicast packets
 */
static int
ng_wlan_rcvdata(hook_p hook, item_p item)
{
	const node_p node = NG_HOOK_NODE(hook);
	int error = 0;
	hook_p hook2;
	struct mbuf *m2;
	int nhooks;
	struct ng_wlan_tag *tag = NULL;
	struct mbuf *m;
	const priv_p priv = NG_NODE_PRIVATE(node);
	ng_ID_t srcid;
	node_p peer;
#ifdef MULTICAST_LOOKUPS
	u_int32_t group, src;
	struct ip *ip;
	struct ether_header *eh;
#endif /* MULTICAST_LOOKUPS */

	/* Checking for NG_INVALID flag fixes race upon shutdown */
	if ((NG_NODE_NOT_VALID(node)) ||
	    ((nhooks = NG_NODE_NUMHOOKS(node)) == 1)) {
		NG_FREE_ITEM(item);
		return (0);
	}

#ifdef WLAN_GIANT_LOCK
	mtx_lock(&ng_wlan_giant);
#else
	mtx_lock(&priv->ng_wlan_tab_lock);
#endif
	m = NGI_M(item); /* 'item' still owns it... we are peeking */

#ifdef MULTICAST_LOOKUPS
	mtx_lock(&priv->ng_wlan_mcast_tab_lock);
	src = group = 0;
	if (priv->multicast_enabled &&
	    (m->m_flags & M_MCAST) && (m->m_flags & M_PKTHDR)) {
		/* disassociate mbuf from item (now we must free it) */
		NGI_GET_M(item, m);
		/* Get group of packets sent to non-local multicast addresses */
		if ((m->m_pkthdr.len >= IP_MCAST_MIN_LEN) && 
		    (m = m_pullup(m, IP_MCAST_MIN_LEN)) != NULL) {
			eh = mtod_off(m, 0, struct ether_header *);
			if (ETHER_IS_MULTICAST(eh->ether_dhost) &&
			    ntohs(eh->ether_type) == ETHERTYPE_IP) {
				ip = mtod_off(m, IP_MCAST_HDR_OFFSET,
					      struct ip *);
				if ((ip->ip_v == IPVERSION) &&
				    IN_MULTICAST(ntohl(ip->ip_dst.s_addr)) &&
				    !(IN_LOCAL_GROUP(ntohl(ip->ip_dst.s_addr)))) {
					group = ntohl(ip->ip_dst.s_addr);
					src = NG_NODE_ID(NG_PEER_NODE(hook));
				}
			}
		} else if (!m) { /* m_pullup failed, free item and leave */
			error = EINVAL;
			goto rcvdata_free_item_error;
		}
		NGI_M(item) = m; /* give mbuf back to item */
	}
#endif /* MULTICAST_LOOKUPS */

	/* Count number of linked nodes, not just number of hooks */
	nhooks = 0;
	LIST_FOREACH(hook2, &node->nd_hooks, hk_hooks)
	{
		/* TODO: maintain a count of the number of linked nodes */
		if (hook2 == hook)
			continue;
		if (IS_PEER_KSOCKET(hook2)) { /* count all ksockets */
			nhooks++;
			continue;
		}
#ifdef MULTICAST_LOOKUPS
		/* count hook using multicast lookup if packet is multicast */
		if ( group > 0 ) {
		    if (!ng_wlan_mcast_lookup(node, hook, hook2, group, src) ||
		    	!ng_wlan_lookup(node, hook, hook2, NULL))
			continue;
		/* use normal unicast lookup */
		} else
#endif /* MULTICAST_LOOKUPS */
		if (!ng_wlan_lookup(node, hook, hook2, NULL))
			continue;
		nhooks++;
	}
	if (nhooks==0) /* Nobody to receive the data */
		goto rcvdata_free_item_error;

	LIST_FOREACH(hook2, &node->nd_hooks, hk_hooks) 
	{
		if (hook2 == hook)
			continue;
		/* Allocate a tag for prepending to the mbuf, which may or 
		   may not be used. If used, the ptr is set to NULL for the
		   next loop iteration; unused (non-NULL ptr) will be freed
		   after loop.
		 */
		if (!tag)
			tag = (struct ng_wlan_tag *)m_tag_alloc(NGM_WLAN_COOKIE,
				NG_TAG_WLAN, TAGSIZE, M_NOWAIT | M_ZERO);
		if (!tag) goto rcvdata_free_item_error_nobufs;
		WLAN_TAG_ZERO(tag);

		/* check for ksocket backchannel to another ng_wlan */
		srcid = 0;
		if (IS_PEER_KSOCKET(hook2)) {
			/* this hook is connected to a ksocket
			 * set srcid for prepending the mbuf */
			peer = NG_PEER_NODE(hook2);
			srcid = (NG_NODE_ID(peer) << 8) + 
				 NG_NODE_ID(NG_PEER_NODE(hook));
		} else
#ifdef MULTICAST_LOOKUPS
		if ( group > 0 ) {
		    if (!ng_wlan_mcast_lookup(node, hook, hook2, group, src) ||
			!ng_wlan_lookup(node, hook, hook2, tag))
			continue; /* multicast lookup failed */
		    /* multicast lookup success - tag data filled in */
		} else
#endif /* MULTICAST_LOOKUPS */
		if ( !ng_wlan_lookup(node, hook, hook2, tag)) {
			/* determine if peers are connected, fill in tag data */
			continue;
		}
		if ((m->m_flags & M_MCAST) && (priv->mer > 0) && tag) {
			tag->per = priv->mer; /* use configured mcast error */
			tag->burst = priv->mburst; /* use conf mcast burst */
		}

		if (--nhooks == 0) { /* nhooks is really number of links */
			if (srcid > 0) { /* add srcid for ksockets */
				NGI_GET_M(item, m);
				M_PREPEND(m, sizeof(ng_ID_t), M_DONTWAIT);
				if (!m) goto rcvdata_free_item_error_nobufs;
				mtod(m, ng_ID_t*)[0] = htonl(srcid);
				NGI_M(item) = m;
			} else 	if (tag && TAG_HAS_DATA(tag)) {
				m_tag_prepend(m, &tag->tag);
				tag = NULL;	/* tag used */
			}
			NG_FWD_ITEM_HOOK(error, item, hook2);
			break; /* no need to loop and malloc */
		} else {
			if ((m2 = m_dup(m, M_DONTWAIT)) == NULL)
				goto rcvdata_free_item_error_nobufs;
			if (srcid > 0) { /* add srcid for ksockets */
				M_PREPEND(m2, sizeof(ng_ID_t), M_DONTWAIT);
				if (!m2) goto rcvdata_free_item_error_nobufs;
				mtod(m2, ng_ID_t*)[0] = htonl(srcid);
			} else if (tag && TAG_HAS_DATA(tag)) {
				m_tag_prepend(m2, &tag->tag);
				tag = NULL;	/* tag used */
			}
			NG_SEND_DATA_ONLY(error, hook2, m2);
			if (error) /* XXX free mbuf? */
				continue;	/* don't give up */
		} /* end if nhooks==0 */
	} /* end FOREACH hook */

	if (tag) /* cleanup unused tag */
		m_tag_free(&tag->tag);

	/* assume item has been freed by fwd above (nhooks==0) */
	goto rcvdata_out;

rcvdata_free_item_error_nobufs:
	error = ENOBUFS;
rcvdata_free_item_error:
	NG_FREE_ITEM(item);

rcvdata_out:
#ifdef WLAN_GIANT_LOCK
	mtx_unlock(&ng_wlan_giant);
#else
	mtx_unlock(&priv->ng_wlan_tab_lock);
#ifdef MULTICAST_LOOKUPS
	mtx_unlock(&priv->ng_wlan_mcast_tab_lock);
#endif /* MULTICAST_LOOKUPS */
#endif
	return (error);
}
#endif /* FREEBSD411 */

#ifndef FREEBSD411
/*
 * Handle incoming data from hooks connected to kernel sockets
 */
static int
ng_wlan_rcvdata_ks(hook_p hook, item_p item)
{
	const node_p node = NG_HOOK_NODE(hook);
	const priv_p priv = NG_NODE_PRIVATE(node);
	int error = 0;
	hook_p hook2;
	struct mbuf *m, *m2;
	int nhooks;
	struct ng_wlan_tag *tag = NULL;
	ng_ID_t srcid;
	struct ng_hook hooklookup, hooklookup2;
	struct ng_node nodelookup;

	/* Checking for NG_INVALID flag fixes race upon shutdown */
	if ((NG_NODE_NOT_VALID(node)) ||
	    ((nhooks = NG_NODE_NUMHOOKS(node)) == 1)) {
		NG_FREE_ITEM(item);
		return (0);
	}

#ifndef FREEBSD411
#ifdef WLAN_GIANT_LOCK
	mtx_lock(&ng_wlan_giant);
#else
	mtx_lock(&priv->ng_wlan_tab_lock);
#endif
#endif
	/* this packet came from another system, so we read the
	 * netgraph ID from the mbuf for use in lookups */
	NGI_GET_M(item, m);
	if (m->m_pkthdr.len < sizeof(ng_ID_t)) { /* too short */
		error = EINVAL;
		goto rcvdata_ks_free_item_error;
	}
	if (m->m_len < sizeof(ng_ID_t) && 
	    (m = m_pullup(m, sizeof(ng_ID_t))) == NULL) {
	    	goto rcvdata_ks_free_item_error_nobufs;
	}
	srcid = ntohl(*mtod(m, ng_ID_t*));
	m_adj(m, sizeof(ng_ID_t));
	NGI_M(item) = (m);
	/* build fake hooks/node for performing lookup */
	hooklookup2.hk_node = &nodelookup;
	hooklookup.hk_peer = &hooklookup2;
	nodelookup.nd_ID = srcid;

	/* Count number of linked nodes, not just number of hooks */
	nhooks = 0;
	LIST_FOREACH(hook2, &node->nd_hooks, hk_hooks) {
		/* TODO: maintain a count of the number of linked nodes */
		if (hook2 == hook)
			continue;
		/* ksockets not counted here -- they'll be skipped */
		if (!ng_wlan_lookup(node, &hooklookup, hook2, NULL))
			continue;
		nhooks++;	
	}
	if (nhooks==0) /* Nobody to receive the data */
		goto rcvdata_ks_free_item_error;


	LIST_FOREACH(hook2, &node->nd_hooks, hk_hooks) {
		if (hook2 == hook)
			continue;
		/* Allocate a tag for prepending to the mbuf, which may or 
		   may not be used. If used, the ptr is set to NULL for the
		   next loop iteration; unused (non-NULL ptr) will be freed
		   after loop.
		 */
		if (!tag)
			tag = (struct ng_wlan_tag *)m_tag_alloc(NGM_WLAN_COOKIE,
				NG_TAG_WLAN, TAGSIZE, M_NOWAIT | M_ZERO);
		if (!tag) goto rcvdata_ks_free_item_error_nobufs;
		WLAN_TAG_ZERO(tag);

		/* don't send data to other ksockets */
		if (IS_PEER_KSOCKET(hook2)) {
			continue;
		/* determine if peers are connected */
		} else if ( !ng_wlan_lookup(node, &hooklookup, hook2, tag)) {
			continue;
		}

		if (--nhooks == 0) { /* nhooks is really number of links */
			if (tag && TAG_HAS_DATA(tag)) {
				m_tag_prepend(m, &tag->tag);
				tag = NULL;	/* tag used */
			}
			NG_FWD_ITEM_HOOK(error, item, hook2);
		} else {
			if ((m2 = m_dup(m, M_DONTWAIT)) == NULL)
				goto rcvdata_ks_free_item_error_nobufs;
			if (tag && TAG_HAS_DATA(tag)) {
				m_tag_prepend(m2, &tag->tag);
				tag = NULL;	/* tag used */
			}
			NG_SEND_DATA_ONLY(error, hook2, m2);
			if (error) /* XXX free mbuf? */
				continue;	/* don't give up */
		}
	}
	if (tag) /* cleanup unused tag */
		m_tag_free(&tag->tag);

	goto rcvdata_ks_out;

rcvdata_ks_free_item_error_nobufs:
	error = ENOBUFS;
rcvdata_ks_free_item_error:
	NG_FREE_ITEM(item);

rcvdata_ks_out:
#ifndef FREEBSD411
#ifdef WLAN_GIANT_LOCK
	mtx_unlock(&ng_wlan_giant);
#else
	mtx_unlock(&priv->ng_wlan_tab_lock);
#endif
#endif
	return (error);
}
#endif /* !FREEBSD411 */


static int
ng_wlan_disconnect(hook_p hook)
{
#ifdef FREEBSD411
	const priv_p priv = hook->node->private;
#else
	const priv_p priv = hook->hk_node->nd_private;
#endif
	
	if (NG_NODE_NUMHOOKS(NG_HOOK_NODE(hook)) == 0 &&
	    NG_NODE_IS_VALID(NG_HOOK_NODE(hook)) && !priv->persistent)
#ifdef FREEBSD411
		ng_rmnode(NG_HOOK_NODE(hook));
#else
		ng_rmnode_self(NG_HOOK_NODE(hook));
#endif
	return (0);
}

static int
ng_wlan_rmnode(node_p node)
{
	const priv_p priv = NG_NODE_PRIVATE(node);
	int b, s;
	struct ng_wlan_hent *tmp;
#ifdef MULTICAST_LOOKUPS
	struct ng_wlan_mcast_hent *mtmp;
#endif /* MULTICAST_LOOKUPS */
	s=splimp();

#ifdef FREEBSD411
	node->flags |= NG_INVALID;
	ng_cutlinks(node);
	ng_unname(node);
#else
	node->nd_flags |= NGF_INVALID;
#endif
	NG_NODE_SET_PRIVATE(node, NULL);
	NG_NODE_UNREF(node);
	/* empty any link lists */
	for (b = 0; b < MIN_BUCKETS; b++) {
		tmp = SLIST_FIRST(&priv->tab[b]);
		while (tmp) {
			SLIST_REMOVE_HEAD(&priv->tab[b], next);
			FREE(tmp, M_NETGRAPH_WLAN);
			tmp = SLIST_FIRST(&priv->tab[b]);
		}	
	}
	FREE(priv->tab, M_NETGRAPH_WLAN);
#ifndef FREEBSD411
	mtx_destroy(&priv->ng_wlan_tab_lock);
#endif
	priv->tab = NULL;
#ifdef MULTICAST_LOOKUPS
	/* empty any multicast entry link lists */
	for (b = 0; b < MIN_BUCKETS; b++) {
		mtmp = SLIST_FIRST(&priv->mcast_tab[b]);
		while (mtmp) {
			SLIST_REMOVE_HEAD(&priv->mcast_tab[b], next);
			FREE(mtmp, M_NETGRAPH_WLAN);
			mtmp = SLIST_FIRST(&priv->mcast_tab[b]);
		}	
	}
	FREE(priv->mcast_tab, M_NETGRAPH_WLAN);
	mtx_destroy(&priv->ng_wlan_mcast_tab_lock);
#endif /* MULTICAST_LOOKUPS */
	FREE(priv, M_NETGRAPH_WLAN);

	splx(s);
	return 0;
}

/*********************************************************************
*                           WLAN FUNCTIONS                           *
**********************************************************************/
	
#define NODE_SORT(a, b, l, g) do {	\
	if (a > b) {			\
		g = a;			\
		l = b;			\
	} else {			\
		g = b;			\
		l = a;			\
	}				\
} while (0);

/* 
 * Returns 1 if peers are linked, 0 if unlinked (default).
 */
static int
ng_wlan_lookup(node_p node, hook_p hook1, hook_p hook2, 
	struct ng_wlan_tag *tag)
{
	const priv_p priv = NG_NODE_PRIVATE(node);
	struct ng_wlan_hent *hent;
	node_p node1, node2;
	ng_ID_t l_id, g_id;
	int bucket;

	if (!hook1 || !hook2)
		return 0;
	node1 = NG_PEER_NODE(hook1);
	node2 = NG_PEER_NODE(hook2);
	if (!node1 || !node2)
		return 0;
	
	NODE_SORT(NG_NODE_ID(node1), NG_NODE_ID(node2), l_id, g_id);	
	bucket = HASH(l_id, g_id);

/*	mtx_lock(&priv->ng_wlan_tab_lock); */
	SLIST_FOREACH(hent, &priv->tab[bucket], next) {
		if ((hent->l_id == l_id) && (hent->g_id == g_id)) {
			/* optionally fill in tag with link data*/
			if (tag && hent->linked) {
				tag->delay 	= hent->delay;
				tag->bandwidth	= hent->bandwidth;
				tag->per 	= hent->per;
				tag->duplicate	= hent->duplicate;
				tag->jitter	= hent->jitter;
				tag->burst	= hent->burst;
			}
/*			mtx_unlock(&priv->ng_wlan_tab_lock); */
			return (hent->linked); /* linked or not linked flag */
		}
	}
/*	mtx_unlock(&priv->ng_wlan_tab_lock); */
	return 0; /* not linked (not found) */
}

#ifdef MULTICAST_LOOKUPS
/* 
 * Returns 1 if peers are linked for this multicast group,
 * 0 if unlinked (default).
 */
static int
ng_wlan_mcast_lookup(node_p node, hook_p hook1, hook_p hook2,
		u_int32_t group, u_int32_t source) 
{
	const priv_p priv = NG_NODE_PRIVATE(node);
	struct ng_wlan_mcast_hent *hent;
	node_p node1, node2;
	ng_ID_t l_id, g_id;
	int bucket;

	if (!hook1 || !hook2)
		return 0;

	node1 = NG_PEER_NODE(hook1);
	node2 = NG_PEER_NODE(hook2);
	if (!node1 || !node2)
		return 0;
	
	NODE_SORT(NG_NODE_ID(node1), NG_NODE_ID(node2), l_id, g_id);	
	bucket = MCAST_HASH(l_id, g_id, group);

	SLIST_FOREACH(hent, &priv->mcast_tab[bucket], next) {
		if ((hent->l_id == l_id) && (hent->g_id == g_id) &&
		    (hent->group == group) && (hent->source == source)) {
			return (hent->linked);
		}
	}
	return 0; /* not linked (not found) */
}

/*
 * Link/unlink to peers for a given multicast group.
 */
static int
ng_wlan_mcast_link(node_p node, ng_ID_t node1, ng_ID_t node2,
	u_int32_t group, u_int32_t source, int unlink)
{
	const priv_p priv = NG_NODE_PRIVATE(node);
	ng_ID_t l_id, g_id;
	int bucket;
	struct ng_wlan_mcast_hent *hent;

	NODE_SORT(node1, node2, l_id, g_id);	
	bucket = MCAST_HASH(l_id, g_id, group);
	priv->multicast_enabled = 1; /* turn on multicast lookups, 
					this is never turned off */

	/* Look for existing entry */
	SLIST_FOREACH(hent, &priv->mcast_tab[bucket], next) {
		if ((hent->l_id == l_id) && (hent->g_id == g_id) &&
		    (hent->group == group) && (hent->source == source))
			break;
	}

	/* Unlink called but no entry exists */
	if (!hent && unlink) {
		return 0;
	}

	/* Allocate and initialize a new hash table entry */
	if (!hent) {
		MALLOC(	hent, struct ng_wlan_mcast_hent *, 
			sizeof(*hent), M_NETGRAPH_WLAN, M_NOWAIT);
		if (hent == NULL) {
			return(ENOBUFS);
		}
		hent->l_id = l_id;
		hent->g_id = g_id;
		hent->group = group;
		hent->source = source;
		/* Add the new element to the hash bucket */
		SLIST_INSERT_HEAD(&priv->mcast_tab[bucket], hent, next);
	}

	if (unlink)
		hent->linked = 0;
	else
		hent->linked = 1;
	return 0;
}
#endif /* MULTICAST_LOOKUPS */

/* 
 * Link two peers together.
 * Once two peers have been linked together, the link can be flagged as
 * linked/unlinked in their hash table entry. Set link data if supplied.
 */
static int
ng_wlan_link(node_p node, ng_ID_t node1, ng_ID_t node2, 
	struct ng_wlan_set_data *data)
{
	const priv_p priv = NG_NODE_PRIVATE(node);
	ng_ID_t l_id, g_id;
	int bucket;
	struct ng_wlan_hent *hent;

	NODE_SORT(node1, node2, l_id, g_id);	
	bucket = HASH(l_id, g_id);
/*	mtx_lock(&priv->ng_wlan_tab_lock); */

	/* Look for existing entry */
	SLIST_FOREACH(hent, &priv->tab[bucket], next) {
		if ((hent->l_id == l_id) && (hent->g_id == g_id))
			break;
	}
	/* Allocate and initialize a new hash table entry */
	if (!hent) {
		MALLOC(	hent, struct ng_wlan_hent *, 
			sizeof(*hent), M_NETGRAPH_WLAN, M_NOWAIT | M_ZERO);
		if (hent == NULL) {
/*			mtx_unlock(&priv->ng_wlan_tab_lock); */
			return(ENOBUFS);
		}
		hent->l_id = l_id;
		hent->g_id = g_id;
		/* Add the new element to the hash bucket */
		SLIST_INSERT_HEAD(&priv->tab[bucket], hent, next);
	}

	hent->linked = 1;
	if (data) {
		hent->delay = data->delay;
		hent->bandwidth = data->bandwidth;
		hent->per = data->per;
		hent->duplicate = data->duplicate;
		hent->jitter = data->jitter;
		hent->burst = data->burst;
	} else {
		WLAN_TAG_ZERO(hent);
	}
/*	mtx_unlock(&priv->ng_wlan_tab_lock); */
	return 0;
}


/* 
 * Unlink two previously-linked peers.
 * because singly-linked list is not optimized for removals, we just
 * unset the "linked" flag. Link data is zeroed.
 */
static int
ng_wlan_unlink(node_p node, ng_ID_t node1, ng_ID_t node2)
{
	const priv_p priv = NG_NODE_PRIVATE(node);
	ng_ID_t l_id, g_id;
	int bucket;
	struct ng_wlan_hent *hent;

	NODE_SORT(node1, node2, l_id, g_id);	
	bucket = HASH(l_id, g_id);

	/* Look for existing entry */
/*	mtx_lock(&priv->ng_wlan_tab_lock); */
	SLIST_FOREACH(hent, &priv->tab[bucket], next) {
		/* entry exists in hash table, unset linked flag */
		if ((hent->l_id == l_id) && (hent->g_id == g_id)) {
			hent->linked = 0;
			WLAN_TAG_ZERO(hent);
/*			mtx_unlock(&priv->ng_wlan_tab_lock); */
			return(0);
		}
	}
	/* Entry does not exist in the hash table, do nothing. */
/*	mtx_unlock(&priv->ng_wlan_tab_lock); */
	return 0;
}

