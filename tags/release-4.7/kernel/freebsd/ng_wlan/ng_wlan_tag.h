/*
 * Copyright (c) 2006-2011 the Boeing Company
 * All rights reserved.
 *
 * author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
 */


#define NG_TAG_WLAN 0x01
#ifdef FREEBSD411
#define WLAN_META_SIZE (sizeof(struct ng_meta))+(sizeof(struct ng_wlan_tag))
#define WLAN_META_PRIORITY 0x01
#define TAGSIZE (sizeof(struct ng_wlan_tag) - sizeof(struct meta_field_header))
#else
#define TAGSIZE (sizeof(struct ng_wlan_tag) - sizeof(struct m_tag))
#endif

#define NG_WLAN_MAX_DELAY 2000000	/* 2,000,000us = 2s */
#define NG_WLAN_MAX_BW  1000000000 	/* 1,000,000,000bps = 1000M */
#define NG_WLAN_MAX_PER 100		/* 100% */
#define NG_WLAN_MAX_DUP 50		/* 50% */
#define NG_WLAN_MAX_JITTER NG_WLAN_MAX_DELAY
#define NG_WLAN_MAX_BURST NG_WLAN_MAX_PER

/* Tag data that is prepended to packets passing through the WLAN node.
 */
struct ng_wlan_tag {
#ifdef FREEBSD411
	struct meta_field_header meta_hdr;
#else
	struct m_tag	tag;
#endif
	u_int64_t	delay;
	u_int64_t	bandwidth;
	u_int16_t	per;
	u_int16_t	duplicate;
	u_int32_t	jitter;
	u_int16_t	burst;
};

#define TAG_HAS_DATA(t) (t->delay || t->bandwidth || t->per || t->duplicate \
			 || t->jitter || t->burst )

#define WLAN_TAG_ZERO(t) do {		\
	t->delay = 0;			\
	t->bandwidth = 0;		\
	t->per = 0;			\
	t->duplicate = 0;		\
	t->jitter = 0;			\
	t->burst = 0;			\
} while(0);

#define WLAN_TAG_COPY(a, b) do {				\
	a->delay = ((struct ng_wlan_tag*)b)->delay;		\
	a->bandwidth = ((struct ng_wlan_tag*)b)->bandwidth;	\
	a->per = ((struct ng_wlan_tag*)b)->per;			\
	a->duplicate = ((struct ng_wlan_tag*)b)->duplicate;	\
	a->jitter = ((struct ng_wlan_tag*)b)->jitter;		\
	a->burst = ((struct ng_wlan_tag*)b)->burst;		\
} while(0);
