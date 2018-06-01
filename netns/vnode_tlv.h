/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_tlv.h
 *
 */

#ifndef _VNODE_TLV_H_
#define _VNODE_TLV_H_

static inline int tlv_string(char **var, vnode_tlv_t *tlv)
{
  if (tlv->val[tlv->vallen - 1] != '\0')
  {
    WARNX("string not null-terminated");
    return -1;
  }

  *var = (char *)tlv->val;

  return 0;
}

static inline int tlv_int32(int32_t *var, vnode_tlv_t *tlv)
{
  if (tlv->vallen != sizeof(int32_t))
  {
    WARNX("invalid value length for int32: %u", tlv->vallen);
    return -1;
  }

  *var = *(int32_t *)tlv->val;

  return 0;
}

#endif	/* _VNODE_TLV_H_ */
