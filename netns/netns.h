/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * netns.h
 *
 */

#ifndef _FORKNS_H_
#define _FORKNS_H_

#include <linux/sched.h>

pid_t nsfork(int flags);
pid_t nsexecvp(char *argv[]);

#endif	/* _FORKNS_H_ */
