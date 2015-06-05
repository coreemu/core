/*
 * ng_pipe.c
 *
 * Copyright (c) 2004 University of Zagreb, Croatia
 * Copyright (c) 1996-1999 Whistle Communications, Inc.
 * All rights reserved.
 * 
 * Subject to the following obligations and disclaimer of warranty, use and
 * redistribution of this software, in source or object code forms, with or
 * without modifications are expressly permitted by Whistle Communications
 * and author; provided, however, that:
 * 1. Any and all reproductions of the source or object code must include the
 *    copyright notice above and the following disclaimer of warranties; and
 * 2. No rights are granted, in any manner or form, to use Whistle
 *    Communications, Inc. trademarks, including the mark "WHISTLE
 *    COMMUNICATIONS" on advertising, endorsements, or otherwise except as
 *    such appears in the above copyright notice or in the software.
 * 
 * THIS SOFTWARE IS BEING PROVIDED BY BOTH AUTHOR AND WHISTLE COMMUNICATIONS
 * "AS IS", AND TO THE MAXIMUM EXTENT PERMITTED BY LAW, THEY MAKE NO
 * REPRESENTATIONS OR WARRANTIES, EXPRESS OR IMPLIED, REGARDING THIS SOFTWARE,
 * INCLUDING WITHOUT LIMITATION, ANY AND ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT.
 * AUTHOR AND WHISTLE COMMUNICATIONS DO NOT WARRANT, GUARANTEE, OR MAKE
 * ANY REPRESENTATIONS REGARDING THE USE OF, OR THE RESULTS OF THE USE OF THIS
 * SOFTWARE IN TERMS OF ITS CORRECTNESS, ACCURACY, RELIABILITY OR OTHERWISE.
 * IN NO EVENT WILL AUTHOR OR WHISTLE COMMUNICATIONS BE LIABLE FOR ANY DAMAGES
 * RESULTING FROM OR ARISING OUT OF ANY USE OF THIS SOFTWARE, INCLUDING
 * WITHOUT LIMITATION, ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
 * PUNITIVE, OR CONSEQUENTIAL DAMAGES, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES, LOSS OF USE, DATA OR PROFITS, HOWEVER CAUSED AND UNDER ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
 * THIS SOFTWARE, EVEN IF AUTHOR OR WHISTLE COMMUNICATIONS IS ADVISED OF
 * THE POSSIBILITY OF SUCH DAMAGE.
 */

/* v 1.15 2004/10/25 */

/*
 * This node permits simple traffic shaping by emulating bandwidth
 * and delay, as well as random packet losses.
 * The node has two hooks, upper and lower. Traffic flowing from upper to
 * lower hook is referenced as downstream, and vice versa. Parameters for 
 * both directions can be set separately, except for delay.
 */

/*
 * TODO:
 *
 * - some splimp()s and extra checks are possibly pure paranoia,
 *   if they prove to be redundant they should be removed.
 *
 * - update the manpage.
 */


#include <sys/param.h>
#include <sys/errno.h>
#include <sys/systm.h>
#include <sys/kernel.h>
#include <sys/malloc.h>
#include <sys/mbuf.h>
#include <sys/time.h>

#include <vm/vm_zone.h>

#include <netinet/in.h>
#include <netinet/in_systm.h>
#include <netinet/ip.h>
#include <netinet/udp.h>

#include <netgraph/ng_message.h>
#include <netgraph/netgraph.h>
#include <netgraph/ng_parse.h>

#include "ng_pipe.h"

#ifdef XCP
#include "xcp_var.h"
#endif

#ifdef BOEING_WLAN
#include "../ng_wlan/ng_wlan.h"
#include "../ng_wlan/ng_wlan_tag.h"
#endif /* BOEING_WLAN */ 

typedef void idle_polling_t (void);
extern idle_polling_t *idle_polling_h;
extern int cpu_idle_hlt;

/* Packet header struct */
struct ngp_hdr {
	TAILQ_ENTRY(ngp_hdr) ngp_link;	/* next pkt in queue */
	struct	timeval when;		/* when to dequeue this packet? */
	struct	mbuf *m;		/* ptr to the actual packet data */
#ifdef BOEING_WLAN
	meta_p meta; /* optional metadata containing link effects from ng_wlan*/
#endif
};

TAILQ_HEAD(p_head ,ngp_hdr);

/* FIFO queue struct */
struct ngp_fifo {
	TAILQ_ENTRY(ngp_fifo) fifo_le;	/* list of active queues only */
	struct	p_head packet_head;	/* FIFO queue head */
	u_int32_t hash;			/* flow signature */
	struct	timeval vtime;		/* virtual time, for WFQ */
	u_int32_t rr_deficit;		/* for DRR */
	u_int32_t packets;		/* # of packets in this queue */
};

/* Per hook info */
struct hookinfo {
	hook_p	hook;
	LIST_ENTRY(hookinfo) hook_le;	/* all active ng_pipe instances */
	TAILQ_HEAD(, ngp_fifo) fifo_head; /* this hooks's FIFO queues */
	TAILQ_HEAD(, ngp_hdr) qout_head; /* delay queue head */
	struct	timeval	qin_utime;
	struct	ng_pipe_hookcfg cfg;
	struct	ng_pipe_hookrun run;
	struct	ng_pipe_hookstat stats;
#ifdef XCP
	struct	xcp_router_state xcps;
#endif
	uint64_t *ber_p;
};

/* Per node info */
struct privdata {
	node_p	node;
	LIST_ENTRY(privdata) node_le;
	u_int64_t delay;
	u_int32_t overhead;
	u_int32_t header_offset;
	struct	hookinfo lower;
	struct	hookinfo upper;
};
typedef struct privdata *sc_p;

/* Macro for calculating the virtual time for packet dequeueing in WFQ */
#define FIFO_VTIME_SORT(plen)						\
	if (hinfo->cfg.wfq && hinfo->cfg.bandwidth) {			\
		ngp_f->vtime.tv_usec = now->tv_usec + ((uint64_t) (plen) \
			+ sc->overhead ) * hinfo->run.fifo_queues *	\
			8000000 / hinfo->cfg.bandwidth;			\
		ngp_f->vtime.tv_sec = now->tv_sec +			\
			ngp_f->vtime.tv_usec / 1000000;			\
		ngp_f->vtime.tv_usec = ngp_f->vtime.tv_usec % 1000000;	\
		TAILQ_FOREACH(ngp_f1, &hinfo->fifo_head, fifo_le)	\
			if (ngp_f1->vtime.tv_sec > ngp_f->vtime.tv_sec || \
			    (ngp_f1->vtime.tv_sec == ngp_f->vtime.tv_sec && \
			    ngp_f1->vtime.tv_usec > ngp_f->vtime.tv_usec)) \
				break;					\
		if (ngp_f1 == NULL)					\
			TAILQ_INSERT_TAIL(&hinfo->fifo_head, ngp_f, fifo_le); \
		else							\
			TAILQ_INSERT_BEFORE(ngp_f1, ngp_f, fifo_le);	\
	} else								\
		TAILQ_INSERT_TAIL(&hinfo->fifo_head, ngp_f, fifo_le);	\


static void parse_cfg(struct ng_pipe_hookcfg *, struct ng_pipe_hookcfg *,
	struct hookinfo *);
static void pipe_dequeue(struct hookinfo *, struct timeval *);
static void pipe_scheduler(void);
static void pipe_poll(void);
static int ngp_modevent(module_t, int, void *);

/* linked list of all "pipe" nodes */
LIST_HEAD(pipe_node_head, privdata) node_head;

/* linked list of active "pipe" hooks */
LIST_HEAD(pipe_hook_head, hookinfo) hook_head;

/* timeout handle for pipe_scheduler */
struct callout_handle	ds_handle = { 0 };

/* saved value of cpu_idle_hlt */
static int old_cpu_idle_hlt = 0;

/* VM zone for storing ngp_hdr-s */
struct vm_zone *ngp_zone;

/* Netgraph methods */
static ng_constructor_t	ngp_constructor;
static ng_rcvmsg_t	ngp_rcvmsg;
static ng_shutdown_t	ngp_rmnode;
static ng_newhook_t	ngp_newhook;
static ng_rcvdata_t	ngp_rcvdata;
static ng_disconnect_t	ngp_disconnect;

/* Parse type for struct ng_pipe_hookstat */
static const struct ng_parse_struct_field
	ng_pipe_hookstat_type_fields[] = NG_PIPE_HOOKSTAT_INFO;
static const struct ng_parse_type ng_pipe_hookstat_type = {
	&ng_parse_struct_type,
	&ng_pipe_hookstat_type_fields
};

/* Parse type for struct ng_pipe_stats */
static const struct ng_parse_struct_field ng_pipe_stats_type_fields[] =
	NG_PIPE_STATS_INFO(&ng_pipe_hookstat_type);
static const struct ng_parse_type ng_pipe_stats_type = {
	&ng_parse_struct_type,
	&ng_pipe_stats_type_fields
};

/* Parse type for struct ng_pipe_hookrun */
static const struct ng_parse_struct_field
	ng_pipe_hookrun_type_fields[] = NG_PIPE_HOOKRUN_INFO;
static const struct ng_parse_type ng_pipe_hookrun_type = {
	&ng_parse_struct_type,
	&ng_pipe_hookrun_type_fields
};

/* Parse type for struct ng_pipe_run */
static const struct ng_parse_struct_field
	ng_pipe_run_type_fields[] = NG_PIPE_RUN_INFO(&ng_pipe_hookrun_type);
static const struct ng_parse_type ng_pipe_run_type = {
	&ng_parse_struct_type,
	&ng_pipe_run_type_fields
};

/* Parse type for struct ng_pipe_hookcfg */
static const struct ng_parse_struct_field
	ng_pipe_hookcfg_type_fields[] = NG_PIPE_HOOKCFG_INFO;
static const struct ng_parse_type ng_pipe_hookcfg_type = {
	&ng_parse_struct_type,
	&ng_pipe_hookcfg_type_fields
};

/* Parse type for struct ng_pipe_cfg */
static const struct ng_parse_struct_field
	ng_pipe_cfg_type_fields[] = NG_PIPE_CFG_INFO(&ng_pipe_hookcfg_type);
static const struct ng_parse_type ng_pipe_cfg_type = {
	&ng_parse_struct_type,
	&ng_pipe_cfg_type_fields
};

/* List of commands and how to convert arguments to/from ASCII */
static const struct ng_cmdlist ng_pipe_cmds[] = {
	{
	  NGM_PIPE_COOKIE,
	  NGM_PIPE_GET_STATS,
	  "getstats",
	  NULL,
	  &ng_pipe_stats_type
	},
	{
	  NGM_PIPE_COOKIE,
	  NGM_PIPE_CLR_STATS,
	  "clrstats",
	  NULL,
	  NULL
	},
	{
	  NGM_PIPE_COOKIE,
	  NGM_PIPE_GETCLR_STATS,
	  "getclrstats",
	  NULL,
	  &ng_pipe_stats_type
	},
	{
	  NGM_PIPE_COOKIE,
	  NGM_PIPE_GET_RUN,
	  "getrun",
	  NULL,
	  &ng_pipe_run_type
	},
	{
	  NGM_PIPE_COOKIE,
	  NGM_PIPE_GET_CFG,
	  "getcfg",
	  NULL,
	  &ng_pipe_cfg_type
	},
	{
	  NGM_PIPE_COOKIE,
	  NGM_PIPE_SET_CFG,
	  "setcfg",
	  &ng_pipe_cfg_type,
	  NULL
	},
	{ 0 }
};

/* Netgraph type descriptor */
static struct ng_type ng_pipe_typestruct = {
	NG_VERSION,
	NG_PIPE_NODE_TYPE,
	ngp_modevent,
	ngp_constructor,
	ngp_rcvmsg,
	ngp_rmnode,
	ngp_newhook,
	NULL,
	NULL,
	ngp_rcvdata,
	ngp_rcvdata,
	ngp_disconnect,
	ng_pipe_cmds
};
NETGRAPH_INIT(pipe, &ng_pipe_typestruct);

#ifdef BOEING_WLAN
/* generate a random integer between 1 and max */
#define pipe_good_random(max) (1 + (random() % max))
#endif

/*
 * Node constructor
 */
static int
ngp_constructor(node_p *nodep)
{
	sc_p privdata;
	node_p node;
	int error = 0;
	int s;

	MALLOC(privdata, sc_p, sizeof(*privdata), M_NETGRAPH, M_NOWAIT);
	if (privdata == NULL)
		return (ENOMEM);
	bzero(privdata, sizeof(*privdata));

	if ((error = ng_make_node_common(&ng_pipe_typestruct, nodep))) {
		FREE(privdata, M_NETGRAPH);
		return (error);
	}

	node=*nodep;
	node->private = privdata;
	privdata->node = node;

	/* Add new node to the "all nodes" list */
	s=splimp();
	LIST_INSERT_HEAD(&node_head, privdata, node_le);
	splx(s);

	return (0);
}


/*
 * Add a hook
 */
static int
ngp_newhook(node_p node, hook_p hook, const char *name)
{
	const sc_p sc = node->private;
	struct hookinfo *hinfo;

	if (strcmp(name, NG_PIPE_HOOK_UPPER) == 0) {
		bzero(&sc->upper, sizeof(sc->upper));
		sc->upper.hook = hook;
		hook->private = &sc->upper;
	} else if (strcmp(name, NG_PIPE_HOOK_LOWER) == 0) {
		bzero(&sc->lower, sizeof(sc->lower));
		sc->lower.hook = hook;
		hook->private = &sc->lower;
	} else
		return (EINVAL);

	/* Load non-zero initial cfg values */
	hinfo = (struct hookinfo *) hook->private;
	hinfo->cfg.qin_size_limit = 50;
	hinfo->cfg.fifo = 1;
	hinfo->cfg.droptail = 1;
	TAILQ_INIT(&hinfo->fifo_head);
	TAILQ_INIT(&hinfo->qout_head);
	return (0);
}


/*
 * Receive a control message
 */
static int
ngp_rcvmsg(node_p node, struct ng_mesg *msg, const char *retaddr,
	   struct ng_mesg **rptr)
{
	const sc_p sc = node->private;
	struct ng_mesg *resp = NULL;
	int error = 0;

	switch (msg->header.typecookie) {
	case NGM_PIPE_COOKIE:
		switch (msg->header.cmd) {
		case NGM_PIPE_GET_STATS:
		case NGM_PIPE_CLR_STATS:
		case NGM_PIPE_GETCLR_STATS:
                    {
			struct ng_pipe_stats *stats;

                        if (msg->header.cmd != NGM_PIPE_CLR_STATS) {
                                NG_MKRESPONSE(resp, msg,
                                    sizeof(*stats), M_NOWAIT);
				if (resp == NULL) {
					error = ENOMEM;
					goto done;
				}
				stats=(struct ng_pipe_stats *)resp->data;
				bcopy(&sc->upper.stats, &stats->downstream,
				    sizeof(stats->downstream));
				bcopy(&sc->lower.stats, &stats->upstream,
				    sizeof(stats->upstream));
                        }
                        if (msg->header.cmd != NGM_PIPE_GET_STATS) {
				bzero(&sc->upper.stats,
				    sizeof(sc->upper.stats));
				bzero(&sc->lower.stats,
				    sizeof(sc->lower.stats));
			}
                        break;
		    }
		case NGM_PIPE_GET_RUN:
                    {
			struct ng_pipe_run *run;

			NG_MKRESPONSE(resp, msg, sizeof(*run), M_NOWAIT);
			if (resp == NULL) {
				error = ENOMEM;
				goto done;
			}
			run = (struct ng_pipe_run *)resp->data;
			bcopy(&sc->upper.run, &run->downstream,
				sizeof(run->downstream));
			bcopy(&sc->lower.run, &run->upstream,
				sizeof(run->upstream));
                        break;
		    }
		case NGM_PIPE_GET_CFG:
                    {
			struct ng_pipe_cfg *cfg;

			NG_MKRESPONSE(resp, msg, sizeof(*cfg), M_NOWAIT);
			if (resp == NULL) {
				error = ENOMEM;
				goto done;
			}
			cfg = (struct ng_pipe_cfg *)resp->data;
			bcopy(&sc->upper.cfg, &cfg->downstream,
				sizeof(cfg->downstream));
			bcopy(&sc->lower.cfg, &cfg->upstream,
				sizeof(cfg->upstream));
			cfg->delay = sc->delay;
			cfg->overhead = sc->overhead;
			cfg->header_offset = sc->header_offset;
			if (cfg->upstream.bandwidth ==
			    cfg->downstream.bandwidth) {
				cfg->bandwidth = cfg->upstream.bandwidth;
				cfg->upstream.bandwidth = 0;
				cfg->downstream.bandwidth = 0;
			} else
				cfg->bandwidth = 0;
                        break;
		    }
		case NGM_PIPE_SET_CFG:
                    {
			struct ng_pipe_cfg *cfg;

			cfg = (struct ng_pipe_cfg *)msg->data;
			if (msg->header.arglen != sizeof(*cfg)) {
				error = EINVAL;
				break;
			}

			if (cfg->delay == -1)
				sc->delay = 0;
			else if (cfg->delay > 0 && cfg->delay < 10000000)
				sc->delay = cfg->delay;

			if (cfg->bandwidth == -1) {
				sc->upper.cfg.bandwidth = 0;
				sc->lower.cfg.bandwidth = 0;
				sc->overhead = 0;
			} else if (cfg->bandwidth >= 100 &&
			    cfg->bandwidth <= 1000000000) {
				sc->upper.cfg.bandwidth = cfg->bandwidth;
				sc->lower.cfg.bandwidth = cfg->bandwidth;
				if (cfg->bandwidth >= 10000000)
					sc->overhead = 8+4+12; /* Ethernet */
				else
					sc->overhead = 10; /* HDLC */
			}

			if (cfg->overhead == -1)
				sc->overhead = 0;
			else if (cfg->overhead > 0 && cfg->overhead < 256)
				sc->overhead = cfg->overhead;

			if (cfg->header_offset == -1)
				sc->header_offset = 0;
			else if (cfg->header_offset > 0 &&
			    cfg->header_offset < 64)
				sc->header_offset = cfg->header_offset;

			parse_cfg(&sc->upper.cfg, &cfg->downstream, &sc->upper);
			parse_cfg(&sc->lower.cfg, &cfg->upstream, &sc->lower);
                        break;
		    }

		default:
			error = EINVAL;
			break;
		}
		break;
	default:
		error = EINVAL;
		break;
	}
	if (rptr)
		*rptr = resp;
	else if (resp)
		FREE(resp, M_NETGRAPH);

done:
	FREE(msg, M_NETGRAPH);
	return (error);
}


static void
parse_cfg(struct ng_pipe_hookcfg *current, struct ng_pipe_hookcfg *new,
	struct hookinfo *hinfo)
{

	if (new->ber == -1) {
		current->ber = 0;
		if (hinfo->ber_p) {
			FREE(hinfo->ber_p, M_NETGRAPH);
			hinfo->ber_p = NULL;
		}
	}
	else if (new->ber >= 1 && new->ber <= 1000000000000) {
		static const uint64_t one = 0x1000000000000; /* = 2^48 */
		uint64_t p0, p;
		uint32_t fsize, i;

		if (hinfo->ber_p == NULL)
			MALLOC(hinfo->ber_p, uint64_t *, \
				(MAX_FSIZE + MAX_OHSIZE)*sizeof(uint64_t), \
				M_NETGRAPH, M_NOWAIT);
		current->ber = new->ber;

		/*
		 * For given BER and each frame size N (in bytes) calculate
		 * the probability P_OK that the frame is clean:
		 *
		 * P_OK(BER,N) = (1 - 1/BER)^(N*8)
		 *
		 * We use a 64-bit fixed-point format with decimal point
		 * positioned between bits 47 and 48.
		 */
		p0 = one - one / new->ber;
		p = one;
		for (fsize = 0; fsize < MAX_FSIZE + MAX_OHSIZE; fsize++) {
			hinfo->ber_p[fsize] = p;
			for (i=0; i<8; i++)
				p = (p*(p0&0xffff)>>48) + \
				    (p*((p0>>16)&0xffff)>>32) + \
				    (p*(p0>>32)>>16);
        	}
	}

	if (new->qin_size_limit == 0xffff)
		current->qin_size_limit = 0;
	else if (new->qin_size_limit >= 5)
		current->qin_size_limit = new->qin_size_limit;

	if (new->qout_size_limit == 0xffff)
		current->qout_size_limit = 0;
	else if (new->qout_size_limit >= 5)
		current->qout_size_limit = new->qout_size_limit;

	if (new->duplicate == -1)
		current->duplicate = 0;
	else if (new->duplicate > 0 && new->duplicate <= 50)
		current->duplicate = new->duplicate;

	if (new->fifo) {
		current->fifo = 1;
		current->wfq = 0;
		current->drr = 0;
	}

	if (new->wfq) {
		current->fifo = 0;
		current->wfq = 1;
		current->drr = 0;
	}

	if (new->drr) {
		current->fifo = 0;
		current->wfq = 0;
		/* DRR quantum */
		if (new->drr >= 32)
			current->drr = new->drr;
		else
			current->drr = 2048;		/* default quantum */
	}

	if (new->droptail) {
		current->droptail = 1;
		current->drophead = 0;
	}

	if (new->drophead) {
		current->droptail = 0;
		current->drophead = 1;
	}

	if (new->bandwidth == -1) {
		current->bandwidth = 0;
		current->fifo = 1;
		current->wfq = 0;
		current->drr = 0;
	} else if (new->bandwidth >= 100 && new->bandwidth <= 1000000000)
		current->bandwidth = new->bandwidth;

#ifdef XCP
	init_xcp_state(&hinfo->xcps, 0, current->bandwidth / 1024);
#endif
}


/*
 * Compute a hash signature for a packet. This function suffers from the
 * NIH sindrome, so probably it would be wise to look around what other
 * folks have found out to be a good and efficient IP hash function...
 */
__inline static int ip_hash(struct mbuf *m, int offset)
{
	u_int64_t i;
	struct ip *ip = (struct ip *)(mtod(m, u_char *) + offset);
	struct udphdr *udp = 0;

	if (m->m_len < sizeof(struct ip) + offset ||
	    ip->ip_v != 4 || ip->ip_hl << 2 != sizeof(struct ip))
		return 0;

	if ((m->m_len >= sizeof(struct ip) + sizeof(struct udphdr) + offset) &&
	    (ip->ip_p == IPPROTO_TCP || ip->ip_p == IPPROTO_UDP) &&
	    !(ntohs(ip->ip_off) & IP_OFFMASK))
		udp = (struct udphdr *)((u_char *) ip + sizeof(struct ip));

#if 0 /* an overkill IP hash, but could be too slow */
	i = 0;
	for ( j = (ip->ip_p & 0x1f) + 1; j ; j = j >> 2) {
		i ^= ((u_int64_t) ip->ip_src.s_addr
		    + ((u_int64_t) ip->ip_dst.s_addr << 7)
		    - ((u_int64_t) ip->ip_src.s_addr << 13)
		    - ((u_int64_t) ip->ip_dst.s_addr << 19)
		    + ((u_int64_t) ip->ip_p << 9)) << j;
		if (udp)
			i ^= (((u_int64_t) udp->uh_sport << (ip->ip_p + 5))
			    - ((u_int64_t) udp->uh_dport << ip->ip_p)) << j;
	}
#else /* a slightly faster yet less reliable version */
	i = ((u_int64_t) ip->ip_src.s_addr
	    ^ ((u_int64_t) ip->ip_dst.s_addr << 7)
	    ^ ((u_int64_t) ip->ip_src.s_addr << 13)
	    ^ ((u_int64_t) ip->ip_dst.s_addr << 19)
	    ^ ((u_int64_t) ip->ip_p << 9));
	if (udp)
		i ^= (((u_int64_t) udp->uh_sport << (ip->ip_p + 5))
		    ^ ((u_int64_t) udp->uh_dport << ip->ip_p));
#endif
	return (i ^ (i >> 32));
}


/*
 * Receive data on a hook - both in upstream and downstream direction.
 * We put the frame on the inbound queue, and try to initiate dequeuing
 * sequence immediately. If inbound queue is full, discard one frame
 * depending on dropping policy (from the head or from the tail of the
 * queue).
 */
static int
ngp_rcvdata(hook_p hook, struct mbuf *m, meta_p meta)
{
	struct hookinfo *const hinfo = (struct hookinfo *) hook->private;
	const sc_p sc = hook->node->private;
	struct timeval uuptime;
	struct timeval *now = &uuptime;
	struct ngp_fifo *ngp_f = NULL, *ngp_f1;
	struct ngp_hdr *ngp_h = NULL;
	int hash;
	int s;

	microuptime(now);
	s = splimp();

#ifdef BOEING_WLAN
	if (meta != NULL) {
		if ((meta->used_len != WLAN_META_SIZE) ||
		    (meta->options[0].cookie != NGM_WLAN_COOKIE)) {
			/* metadata from elsewhere, not queued */
			NG_FREE_META(meta); /* sets meta = NULL */
		}/* else metadata from ng_wlan, contains tag */
	}
#else
	NG_FREE_META(meta);
#endif

	/*
	 * Attach us to the list of active ng_pipes if this one was an empty
	 * one before, and also update the queue service deadline time.
	 */
	if (hinfo->run.qin_frames == 0) {
		struct timeval *when = &hinfo->qin_utime;
		if (when->tv_sec < now->tv_sec || (when->tv_sec == now->tv_sec
		    && when->tv_usec < now->tv_usec)) {
			when->tv_sec = now->tv_sec;
			when->tv_usec = now->tv_usec;
		}
		if (hinfo->run.qout_frames == 0) {
			LIST_INSERT_HEAD(&hook_head, hinfo, hook_le);
			if (cpu_idle_hlt) {
				old_cpu_idle_hlt = cpu_idle_hlt;
				cpu_idle_hlt = 0;
			}
		}
	}

	/* Populate the packet header */
	ngp_h = zalloc(ngp_zone);
	ngp_h->m = m;
#ifdef BOEING_WLAN
	ngp_h->meta = meta;
	meta = NULL; /* don't free elsewhere */
#endif

	if (hinfo->cfg.fifo)
		hash = 0;	/* all packets go into a single FIFO queue */
	else
		hash = ip_hash(m, sc->header_offset);

#ifdef XCP
	if (do_xcp)
		xcp_forward(m, sc->header_offset, &hinfo->xcps);
#endif

	/* Find the appropriate FIFO queue for the packet and enqueue it*/
	TAILQ_FOREACH(ngp_f, &hinfo->fifo_head, fifo_le)
		if (hash == ngp_f->hash)
			break;
	if (ngp_f == NULL) {
		ngp_f = zalloc(ngp_zone);
		TAILQ_INIT(&ngp_f->packet_head);
		ngp_f->hash = hash;
		ngp_f->packets = 1;
		ngp_f->rr_deficit = hinfo->cfg.drr;	/* DRR quantum */
		hinfo->run.fifo_queues++;
		TAILQ_INSERT_TAIL(&ngp_f->packet_head, ngp_h, ngp_link);
		FIFO_VTIME_SORT(m->m_pkthdr.len);
	} else {
		TAILQ_INSERT_TAIL(&ngp_f->packet_head, ngp_h, ngp_link);
		ngp_f->packets++;
	}
	hinfo->run.qin_frames++;
	hinfo->run.qin_octets += m->m_pkthdr.len;

	/* Discard a frame if inbound queue limit has been reached */
	if (hinfo->run.qin_frames > hinfo->cfg.qin_size_limit) {
		struct mbuf *m1;
		int longest = 0;

		/* Find the longest queue */
		TAILQ_FOREACH(ngp_f1, &hinfo->fifo_head, fifo_le)
			if (ngp_f1->packets > longest) {
				longest = ngp_f1->packets;
				ngp_f = ngp_f1;
			}

		/* Drop a frame from the queue head/tail, depending on cfg */
		if (hinfo->cfg.drophead) 
			ngp_h = TAILQ_FIRST(&ngp_f->packet_head);
		else 
			ngp_h = TAILQ_LAST(&ngp_f->packet_head, p_head);
		TAILQ_REMOVE(&ngp_f->packet_head, ngp_h, ngp_link);
		m1 = ngp_h->m;
#ifdef BOEING_WLAN
		NG_FREE_META(ngp_h->meta);
#endif /* BOEING_WLAN */
		zfree(ngp_zone, ngp_h);
		hinfo->run.qin_octets -= m1->m_pkthdr.len;
		hinfo->stats.in_disc_octets += m1->m_pkthdr.len;
		m_freem(m1);
		if (--(ngp_f->packets) == 0) {
			TAILQ_REMOVE(&hinfo->fifo_head, ngp_f, fifo_le);
			zfree(ngp_zone, ngp_f);
			hinfo->run.fifo_queues--;
		}
		hinfo->run.qin_frames--;
		hinfo->stats.in_disc_frames++;
	}

	/* Try to start the dequeuing process immediately */
	pipe_dequeue(hinfo, now);

	splx(s);
	return (0);
}


/*
 * Dequeueing sequence - we basically do the following:
 *  1) Try to extract the frame from the inbound (bandwidth) queue;
 *  2) In accordance to BER specified, discard the frame randomly;
 *  3) If the frame survives BER, prepend it with delay info and move it
 *     to outbound (delay) queue, or send directly to the outbound hook;
 *  4) Loop to 2) until bandwidth limit is reached, or inbound queue is
 *     flushed completely;
 *  5) Extract the first frame from the outbound queue, if it's time has come.
 *     Send this frame to the outbound hook;
 *  6) Loop to 6) until outbound queue is flushed completely, or the next
 *     frame in the queue is not scheduled to be dequeued yet
 *  
 * This routine must be called at splimp()!
 */
static void
pipe_dequeue(struct hookinfo *hinfo, struct timeval *now) {
	static uint64_t rand, oldrand;
	const sc_p sc = hinfo->hook->node->private;
	struct hookinfo *dest;
	struct ngp_fifo *ngp_f, *ngp_f1;
	struct ngp_hdr *ngp_h;
	struct timeval *when;
	meta_p meta = NULL;
	int error = 0;
	struct mbuf *m;
#ifdef BOEING_WLAN
	struct ngp_hdr *ngp_h1 = NULL;
	struct ng_wlan_tag *tag, wtag;
	int need_free_meta;
#endif /* BOEING_WLAN */

	/* Which one is the destination hook? */
	if (hinfo == &sc->lower)
		dest = &sc->upper;
	else
		dest = &sc->lower;

	/* Bandwidth queue processing */
	while ((ngp_f = TAILQ_FIRST(&hinfo->fifo_head))) {
		when = &hinfo->qin_utime;
		if (when->tv_sec > now->tv_sec || (when->tv_sec == now->tv_sec
		    && when->tv_usec > now->tv_usec))
			break;

		ngp_h = TAILQ_FIRST(&ngp_f->packet_head);
		m = ngp_h->m;
#ifdef BOEING_WLAN
		meta = ngp_h->meta;
		ngp_h->meta = NULL; /* keep ptr in meta*/
		need_free_meta = 0;
		if (meta != NULL) {
			need_free_meta = 1;
			tag = (struct ng_wlan_tag*)meta->options;
			WLAN_TAG_COPY( (&wtag), tag)
			/* enforce maximum parameters */
			if (wtag.delay > NG_WLAN_MAX_DELAY)
				wtag.delay = NG_WLAN_MAX_DELAY;
			if (wtag.duplicate > NG_WLAN_MAX_DUP)
				wtag.duplicate = NG_WLAN_MAX_DUP;
			if (wtag.jitter > NG_WLAN_MAX_JITTER)
				wtag.jitter = NG_WLAN_MAX_JITTER;
		} else {
			WLAN_TAG_ZERO( (&wtag) );
		}
#endif /* BOEING_WLAN */

		/* Deficit Round Robin (DRR) processing */
		if (hinfo->cfg.drr) {
			if (ngp_f->rr_deficit >= m->m_pkthdr.len) {
				ngp_f->rr_deficit -= m->m_pkthdr.len;
			} else {
				ngp_f->rr_deficit += hinfo->cfg.drr;
				TAILQ_REMOVE(&hinfo->fifo_head, ngp_f, fifo_le);
				TAILQ_INSERT_TAIL(&hinfo->fifo_head, \
							ngp_f, fifo_le);
				/* BOEING_WLAN: need to free meta here? */
				continue;
			}
		}

		/*
		 * Either create a duplicate and pass it on, or dequeue
		 * the original packet...
		 */
#ifdef BOEING_WLAN
		if (wtag.duplicate &&
		    pipe_good_random(100) <= wtag.duplicate) {
			ngp_h = zalloc(ngp_zone);
			KASSERT(ngp_h != NULL, ("ngp_h zalloc failed (3)"));
			ngp_h->m = m_dup(m, M_NOWAIT);
			ngp_h->meta = meta; /* reuse the old metadata instead of
					     * allocating another */
			need_free_meta = 0;
			meta = NULL;
			KASSERT(ngp_h->m != NULL, ("m_dup failed"));
			m = ngp_h->m; /* Boeing: we are now working with copied
					 mbuf, leaving original in the queue */
		} else
#endif /* BOEING_WLAN */
		if (hinfo->cfg.duplicate &&
		    random() % 100 <= hinfo->cfg.duplicate) {
			if ((m = m_dup(m, M_NOWAIT)))
				if ((ngp_h = zalloc(ngp_zone)))
					ngp_h->m = m;
			if ( m == NULL || ngp_h == NULL )
				panic("ng_pipe: m_dup or zalloc failed!");
		} else {
			TAILQ_REMOVE(&ngp_f->packet_head, ngp_h, ngp_link);
			hinfo->run.qin_frames--;
			hinfo->run.qin_octets -= m->m_pkthdr.len;
			ngp_f->packets--;
		}
#ifdef BOEING_WLAN
		/* free the metadata if it was not re-used for the duplicate */
		if (need_free_meta)
			NG_FREE_META(meta);
#endif /* BOEING_WLAN */

		/* Calculate the serialization delay */
#ifdef BOEING_WLAN
		if (wtag.bandwidth) {
			hinfo->qin_utime.tv_usec += ((uint64_t) m->m_pkthdr.len
				+ sc->overhead ) *
				8000000 / wtag.bandwidth;
			hinfo->qin_utime.tv_sec +=
				hinfo->qin_utime.tv_usec / 1000000;
			hinfo->qin_utime.tv_usec =
				hinfo->qin_utime.tv_usec % 1000000;
		} else
#endif /* BOEING_WLAN */
		if (hinfo->cfg.bandwidth) {
			hinfo->qin_utime.tv_usec += ((uint64_t) m->m_pkthdr.len
				+ sc->overhead ) *
				8000000 / hinfo->cfg.bandwidth;
			hinfo->qin_utime.tv_sec +=
				hinfo->qin_utime.tv_usec / 1000000;
			hinfo->qin_utime.tv_usec =
				hinfo->qin_utime.tv_usec % 1000000;
		}
		when = &ngp_h->when;
		when->tv_sec = hinfo->qin_utime.tv_sec;
		when->tv_usec = hinfo->qin_utime.tv_usec;

		/* Sort / rearrange inbound queues */
		if (ngp_f->packets) {
			if (hinfo->cfg.wfq) {
				TAILQ_REMOVE(&hinfo->fifo_head, ngp_f, fifo_le);
				FIFO_VTIME_SORT(TAILQ_FIRST(&ngp_f->packet_head)->m->m_pkthdr.len)
			}
		} else {
			TAILQ_REMOVE(&hinfo->fifo_head, ngp_f, fifo_le);
			zfree(ngp_zone, ngp_f);
			hinfo->run.fifo_queues--;
		}

		/* Randomly discard the frame, according to BER setting */
#ifdef BOEING_WLAN
		/* use specified Packet Error Rate setting for random discard */
		if (wtag.per &&
		    pipe_good_random(100) <= wtag.per) {
			hinfo->stats.out_disc_frames++;
			hinfo->stats.out_disc_octets += m->m_pkthdr.len;
			zfree(ngp_zone, ngp_h);
			m_freem(m);
			continue;
		} else
#endif /* BOEING_WLAN */
		if (hinfo->cfg.ber && 
		    ( (oldrand = rand) ^ (rand = random())<<17) >=
		    hinfo->ber_p[sc->overhead + m->m_pkthdr.len] ) {
			hinfo->stats.out_disc_frames++;
			hinfo->stats.out_disc_octets += m->m_pkthdr.len;
			zfree(ngp_zone, ngp_h);
			m_freem(m);
			continue;
		}

		/* Discard frame if outbound queue size limit exceeded */
		if (hinfo->cfg.qout_size_limit &&
		    hinfo->run.qout_frames>=hinfo->cfg.qout_size_limit) {
			hinfo->stats.out_disc_frames++;
			hinfo->stats.out_disc_octets += m->m_pkthdr.len;
			zfree(ngp_zone, ngp_h);
			m_freem(m);
			continue;
		}

#ifdef BOEING_WLAN
		/* Calculate the propagation delay including jitter */
		if (wtag.jitter) {
			when->tv_usec += pipe_good_random(wtag.jitter);
			/* overflow handled below... */
		}
		when->tv_usec += wtag.delay ? wtag.delay : sc->delay;
#else
		/* Calculate the propagation delay */
		when->tv_usec += sc->delay;
#endif /* BOEING_WLAN */
		when->tv_sec += when->tv_usec / 1000000;
		when->tv_usec = when->tv_usec % 1000000;

		/* Put the frame into the delay queue */
#ifdef BOEING_WLAN
	/* Because WLAN packets may have varying dequeue times, we need to
	 * perform sorted queueing; the dequeuing process expects packets in
	 * the queue that are sorted by time.
	 */
		TAILQ_FOREACH(ngp_h1, &hinfo->qout_head, ngp_link) {
			if (ngp_h1->when.tv_sec > ngp_h->when.tv_sec ||
			    (ngp_h1->when.tv_sec == ngp_h->when.tv_sec &&
			    ngp_h1->when.tv_usec > ngp_h->when.tv_usec))
				break;
		}
		if (ngp_h1 == NULL)
			TAILQ_INSERT_TAIL(&hinfo->qout_head, ngp_h, ngp_link);
		else
			TAILQ_INSERT_BEFORE(ngp_h1, ngp_h, ngp_link);
	/* The original code below just inserts the packet at the 
	 * tail of the queue because the delay time is constant. */
#else /* BOEING_WLAN */
		TAILQ_INSERT_TAIL(&hinfo->qout_head, ngp_h, ngp_link);
#endif /* BOEING_WLAN */
		hinfo->run.qout_frames++;
		hinfo->run.qout_octets += m->m_pkthdr.len;
	}

	/* Delay queue processing */
	while ((ngp_h = TAILQ_FIRST(&hinfo->qout_head))) {
		struct mbuf *m = ngp_h->m;

/* BOEING_WLAN: this is why we have sorted the queue input */
		when = &ngp_h->when;
		if (when->tv_sec > now->tv_sec ||
		    (when->tv_sec == now->tv_sec &&
		    when->tv_usec > now->tv_usec))
			break;

		/* Update outbound queue stats */
		hinfo->stats.fwd_frames++;
		hinfo->stats.fwd_octets += m->m_pkthdr.len;
		hinfo->run.qout_frames--;
		hinfo->run.qout_octets -= m->m_pkthdr.len;

		/* Dequeue/send the packet */
		TAILQ_REMOVE(&hinfo->qout_head, ngp_h, ngp_link);
		zfree(ngp_zone, ngp_h);
#ifdef BOEING_WLAN
		NG_SEND_DATA_ONLY(error, dest->hook, m);
#else
		NG_SEND_DATA(error, dest->hook, m, meta);
#endif /* BOEING_WLAN */
	}

	/* If both queues are empty detach us from the list of active queues */
	if (hinfo->run.qin_frames + hinfo->run.qout_frames == 0)
		LIST_REMOVE(hinfo, hook_le);
}


/*
 * This routine is called on every clock tick. We poll all nodes/hooks
 * for queued frames by calling pipe_dequeue().
 */
static void
pipe_scheduler(void)
{
	static struct timeval old;
	struct timeval new;

	microuptime(&new);
	if (old.tv_sec > new.tv_sec)
		printf ("ng_pipe: dsec=%ld\n", old.tv_sec - new.tv_sec);
	else if (old.tv_sec == new.tv_sec && old.tv_usec > new.tv_usec)
		printf ("ng_pipe: dusec=%ld\n", old.tv_usec - new.tv_usec);
	old.tv_sec = new.tv_sec;
	old.tv_usec = new.tv_usec;

	pipe_poll();

#ifdef XCP
	if ( do_xcp ) {
		sc_p priv;

        	/* Set off any XCP timers hooked to ng_pipe queues */

		LIST_FOREACH(priv, &node_head, node_le) {
			if ( --priv->upper.xcps.ticks_until_Te == 0 )
				xcp_Te_timeout(&priv->upper.xcps);
			if ( --priv->upper.xcps.ticks_until_Tq == 0 )
				xcp_Tq_timeout(&priv->upper.xcps);
			if ( --priv->lower.xcps.ticks_until_Te == 0 )
				xcp_Te_timeout(&priv->lower.xcps);
			if ( --priv->lower.xcps.ticks_until_Tq == 0 )
				xcp_Tq_timeout(&priv->lower.xcps);
		}
	}
#endif

	/* Reschedule  */
	ds_handle = timeout((timeout_t *) &pipe_scheduler, NULL, 1);
}


static void
pipe_poll(void)
{
	struct hookinfo *hinfo;
	int s;
	struct timeval now;
	
	s=splimp();

	microuptime(&now);
	LIST_FOREACH(hinfo, &hook_head, hook_le)
		pipe_dequeue(hinfo, &now);
	if (LIST_EMPTY(&hook_head) && cpu_idle_hlt == 0)
		cpu_idle_hlt = old_cpu_idle_hlt;

	splx(s);
}


/*
 * Shutdown processing
 *
 * This is tricky. If we have both a lower and upper hook, then we
 * probably want to extricate ourselves and leave the two peers
 * still linked to each other. Otherwise we should just shut down as
 * a normal node would. We run at splimp() in order to avoid race
 * condition with pipe_scheduler().
 */
static int
ngp_rmnode(node_p node)
{
	const sc_p privdata = node->private;
	int s;

	s=splimp();

	node->flags |= NG_INVALID;
	if (privdata->lower.hook && privdata->upper.hook)
		ng_bypass(privdata->lower.hook, privdata->upper.hook);
	ng_cutlinks(node);
	ng_unname(node);

	/* unlink the node from the list */
	LIST_REMOVE(privdata, node_le);

	node->private = NULL;
	ng_unref(privdata->node);
	FREE(privdata, M_NETGRAPH);

	splx(s);
	return (0);
}


/*
 * Hook disconnection
 */
static int
ngp_disconnect(hook_p hook)
{
	struct hookinfo *const hinfo = (struct hookinfo *) hook->private;
	struct ngp_fifo *ngp_f;
	struct ngp_hdr *ngp_h;
	int s, removed = 0;

	s=splimp();

	KASSERT(hinfo != NULL, ("%s: null info", __FUNCTION__));
	hinfo->hook = NULL;

	/* Flush all fifo queues associated with the hook */
	while ((ngp_f = TAILQ_FIRST(&hinfo->fifo_head))) {
		while ((ngp_h = TAILQ_FIRST(&ngp_f->packet_head))) {
			TAILQ_REMOVE(&ngp_f->packet_head, ngp_h, ngp_link);
			m_freem(ngp_h->m);
#ifdef BOEING_WLAN
			NG_FREE_META(ngp_h->meta);
#endif /* BOEING_WLAN */
			zfree(ngp_zone, ngp_h);
			removed++;
		}
		TAILQ_REMOVE(&hinfo->fifo_head, ngp_f, fifo_le);
		zfree(ngp_zone, ngp_f);
	}

	/* Flush the delay queue */
	while ((ngp_h = TAILQ_FIRST(&hinfo->qout_head))) {
		TAILQ_REMOVE(&hinfo->qout_head, ngp_h, ngp_link);
		m_freem(ngp_h->m);
#ifdef BOEING_WLAN
		NG_FREE_META(ngp_h->meta);
#endif /* BOEING_WLAN */
		zfree(ngp_zone, ngp_h);
		removed++;
	}

	/*
	 * Both queues should be empty by now, so detach us from
	 * the list of active queues
	 */
	if (removed)
		LIST_REMOVE(hinfo, hook_le);
	if (hinfo->run.qin_frames + hinfo->run.qout_frames != removed)
		printf("Mismatch: queued=%d but removed=%d !?!",
			hinfo->run.qin_frames + hinfo->run.qout_frames,
			removed);

	/* Release the packet loss probability table (BER) */
	if (hinfo->ber_p)
		FREE(hinfo->ber_p, M_NETGRAPH);

	if (hook->node->numhooks == 0)
		ng_rmnode(hook->node);

	splx(s);
	return (0);
}

static int
ngp_modevent(module_t mod, int type, void *unused)
{
	sc_p priv;
	int error = 0;
	int s;

	switch (type) {
	case MOD_LOAD:
		if (ngp_zone)
			error = EEXIST; 
		else {
			ngp_zone = zinit("ng_pipe",
			  max(sizeof(struct ngp_hdr), sizeof (struct ngp_fifo)),
			  nmbufs, ZONE_INTERRUPT, 0);
			if (ngp_zone == NULL) {
				error = ENOMEM;
				break;
			}
			LIST_INIT(&node_head);
			LIST_INIT(&hook_head);
			ds_handle = timeout((timeout_t *) &pipe_scheduler,
						NULL, 1);
			idle_polling_h = pipe_poll;
		}
		break;
	case MOD_UNLOAD:
		LIST_FOREACH(priv, &node_head, node_le)
			error = EBUSY;
			
		if (error == 0) {
			s = splimp();
			idle_polling_h = NULL;
			untimeout((timeout_t *) &pipe_scheduler, NULL,
					ds_handle);
			ds_handle.callout = NULL;
			zdestroy(ngp_zone);
			splx (s);
		}
		break;
	default:
		break;
	}

	return (error);
}
