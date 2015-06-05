/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_chnl.h
 *
 */

#ifndef _VNODE_CHNL_H_
#define _VNODE_CHNL_H_

int vnode_connect(const char *name);
int vnode_listen(const char *name);

#endif	/* _VNODE_CHNL_H_ */
