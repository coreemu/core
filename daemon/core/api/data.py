#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Tom Goff <thomas.goff@boeing.com>
#
'''
data.py: constant definitions for the CORE API, enumerating the
different message and TLV types (these constants are also found in coreapi.h)
'''

def enumdict(d):
    for k, v in d.iteritems():
        exec "%s = %s" % (v, k) in globals()

# Constants

CORE_API_VER		=	"1.23"
CORE_API_PORT		=	4038

# Message types

message_types = {
    0x01: "CORE_API_NODE_MSG",
    0x02: "CORE_API_LINK_MSG",
    0x03: "CORE_API_EXEC_MSG",
    0x04: "CORE_API_REG_MSG",
    0x05: "CORE_API_CONF_MSG",
    0x06: "CORE_API_FILE_MSG",
    0x07: "CORE_API_IFACE_MSG",
    0x08: "CORE_API_EVENT_MSG",
    0x09: "CORE_API_SESS_MSG",
    0x0A: "CORE_API_EXCP_MSG",
    0x0B: "CORE_API_MSG_MAX",
}

enumdict(message_types)

# Generic Message Flags

message_flags = {
    0x01: "CORE_API_ADD_FLAG",
    0x02: "CORE_API_DEL_FLAG",
    0x04: "CORE_API_CRI_FLAG",
    0x08: "CORE_API_LOC_FLAG",
    0x10: "CORE_API_STR_FLAG",
    0x20: "CORE_API_TXT_FLAG",
    0x40: "CORE_API_TTY_FLAG",
}

enumdict(message_flags)

# Node Message TLV Types

node_tlvs = {
    0x01: "CORE_TLV_NODE_NUMBER",
    0x02: "CORE_TLV_NODE_TYPE",
    0x03: "CORE_TLV_NODE_NAME",
    0x04: "CORE_TLV_NODE_IPADDR",
    0x05: "CORE_TLV_NODE_MACADDR",
    0x06: "CORE_TLV_NODE_IP6ADDR",
    0x07: "CORE_TLV_NODE_MODEL",
    0x08: "CORE_TLV_NODE_EMUSRV",
    0x0A: "CORE_TLV_NODE_SESSION",
    0x20: "CORE_TLV_NODE_XPOS",
    0x21: "CORE_TLV_NODE_YPOS",
    0x22: "CORE_TLV_NODE_CANVAS",
    0x23: "CORE_TLV_NODE_EMUID",
    0x24: "CORE_TLV_NODE_NETID",
    0x25: "CORE_TLV_NODE_SERVICES",
    0x30: "CORE_TLV_NODE_LAT",
    0x31: "CORE_TLV_NODE_LONG",
    0x32: "CORE_TLV_NODE_ALT",
    0x42: "CORE_TLV_NODE_ICON",
    0x50: "CORE_TLV_NODE_OPAQUE",
}

enumdict(node_tlvs)

node_types = dict(enumerate([
    "CORE_NODE_DEF",
    "CORE_NODE_PHYS",
    "CORE_NODE_XEN",
    "CORE_NODE_TBD",
    "CORE_NODE_SWITCH",
    "CORE_NODE_HUB",
    "CORE_NODE_WLAN",
    "CORE_NODE_RJ45",
    "CORE_NODE_TUNNEL",
    "CORE_NODE_KTUNNEL",
    "CORE_NODE_EMANE",
]))

enumdict(node_types)

rj45_models = dict(enumerate([
    "RJ45_MODEL_LINKED",
    "RJ45_MODEL_WIRELESS",
    "RJ45_MODEL_INSTALLED",
]))

enumdict(rj45_models)

# Link Message TLV Types

link_tlvs = {
    0x01: "CORE_TLV_LINK_N1NUMBER",
    0x02: "CORE_TLV_LINK_N2NUMBER",
    0x03: "CORE_TLV_LINK_DELAY",
    0x04: "CORE_TLV_LINK_BW",
    0x05: "CORE_TLV_LINK_PER",
    0x06: "CORE_TLV_LINK_DUP",
    0x07: "CORE_TLV_LINK_JITTER",
    0x08: "CORE_TLV_LINK_MER",
    0x09: "CORE_TLV_LINK_BURST",
    CORE_TLV_NODE_SESSION: "CORE_TLV_LINK_SESSION",
    0x10: "CORE_TLV_LINK_MBURST",
    0x20: "CORE_TLV_LINK_TYPE",
    0x21: "CORE_TLV_LINK_GUIATTR",
    0x22: "CORE_TLV_LINK_UNI",
    0x23: "CORE_TLV_LINK_EMUID",
    0x24: "CORE_TLV_LINK_NETID",
    0x25: "CORE_TLV_LINK_KEY",
    0x30: "CORE_TLV_LINK_IF1NUM",
    0x31: "CORE_TLV_LINK_IF1IP4",
    0x32: "CORE_TLV_LINK_IF1IP4MASK",
    0x33: "CORE_TLV_LINK_IF1MAC",
    0x34: "CORE_TLV_LINK_IF1IP6",
    0x35: "CORE_TLV_LINK_IF1IP6MASK",
    0x36: "CORE_TLV_LINK_IF2NUM",
    0x37: "CORE_TLV_LINK_IF2IP4",
    0x38: "CORE_TLV_LINK_IF2IP4MASK",
    0x39: "CORE_TLV_LINK_IF2MAC",
    0x40: "CORE_TLV_LINK_IF2IP6",
    0x41: "CORE_TLV_LINK_IF2IP6MASK",
    0x42: "CORE_TLV_LINK_IF1NAME",
    0x43: "CORE_TLV_LINK_IF2NAME",
    0x50: "CORE_TLV_LINK_OPAQUE",
}

enumdict(link_tlvs)

link_types = dict(enumerate([
    "CORE_LINK_WIRELESS",
    "CORE_LINK_WIRED",
]))

enumdict(link_types)

# Execute Message TLV Types

exec_tlvs = {
    0x01: "CORE_TLV_EXEC_NODE",
    0x02: "CORE_TLV_EXEC_NUM",
    0x03: "CORE_TLV_EXEC_TIME",
    0x04: "CORE_TLV_EXEC_CMD",
    0x05: "CORE_TLV_EXEC_RESULT",
    0x06: "CORE_TLV_EXEC_STATUS",
    CORE_TLV_NODE_SESSION: "CORE_TLV_EXEC_SESSION",
}

enumdict(exec_tlvs)

# Register Message TLV Types

reg_tlvs = {
    0x01: "CORE_TLV_REG_WIRELESS",
    0x02: "CORE_TLV_REG_MOBILITY",
    0x03: "CORE_TLV_REG_UTILITY",
    0x04: "CORE_TLV_REG_EXECSRV",
    0x05: "CORE_TLV_REG_GUI",
    0x06: "CORE_TLV_REG_EMULSRV",
    CORE_TLV_NODE_SESSION: "CORE_TLV_REG_SESSION",
}

enumdict(reg_tlvs)

# Configuration Message TLV Types

conf_tlvs = {
    0x01: "CORE_TLV_CONF_NODE",
    0x02: "CORE_TLV_CONF_OBJ",
    0x03: "CORE_TLV_CONF_TYPE",
    0x04: "CORE_TLV_CONF_DATA_TYPES",
    0x05: "CORE_TLV_CONF_VALUES",
    0x06: "CORE_TLV_CONF_CAPTIONS",
    0x07: "CORE_TLV_CONF_BITMAP",
    0x08: "CORE_TLV_CONF_POSSIBLE_VALUES",
    0x09: "CORE_TLV_CONF_GROUPS",
    CORE_TLV_NODE_SESSION: "CORE_TLV_CONF_SESSION",
    0x0B: "CORE_TLV_CONF_IFNUM",
    CORE_TLV_NODE_NETID: "CORE_TLV_CONF_NETID",
    0x50: "CORE_TLV_CONF_OPAQUE",
}

enumdict(conf_tlvs)

conf_flags = {
    0x00: "CONF_TYPE_FLAGS_NONE",
    0x01: "CONF_TYPE_FLAGS_REQUEST",
    0x02: "CONF_TYPE_FLAGS_UPDATE",
    0x03: "CONF_TYPE_FLAGS_RESET",
}

enumdict(conf_flags)

conf_data_types = {
    0x01: "CONF_DATA_TYPE_UINT8",
    0x02: "CONF_DATA_TYPE_UINT16",
    0x03: "CONF_DATA_TYPE_UINT32",
    0x04: "CONF_DATA_TYPE_UINT64",
    0x05: "CONF_DATA_TYPE_INT8",
    0x06: "CONF_DATA_TYPE_INT16",
    0x07: "CONF_DATA_TYPE_INT32",
    0x08: "CONF_DATA_TYPE_INT64",
    0x09: "CONF_DATA_TYPE_FLOAT",
    0x0A: "CONF_DATA_TYPE_STRING",
    0x0B: "CONF_DATA_TYPE_BOOL",
}

enumdict(conf_data_types)

# File Message TLV Types

file_tlvs = {
    0x01: "CORE_TLV_FILE_NODE",
    0x02: "CORE_TLV_FILE_NAME",
    0x03: "CORE_TLV_FILE_MODE",
    0x04: "CORE_TLV_FILE_NUM",
    0x05: "CORE_TLV_FILE_TYPE",
    0x06: "CORE_TLV_FILE_SRCNAME",
    CORE_TLV_NODE_SESSION: "CORE_TLV_FILE_SESSION",
    0x10: "CORE_TLV_FILE_DATA",
    0x11: "CORE_TLV_FILE_CMPDATA",
}

enumdict(file_tlvs)

# Interface Message TLV Types

iface_tlvs = {
    0x01: "CORE_TLV_IFACE_NODE",
    0x02: "CORE_TLV_IFACE_NUM",
    0x03: "CORE_TLV_IFACE_NAME",
    0x04: "CORE_TLV_IFACE_IPADDR",
    0x05: "CORE_TLV_IFACE_MASK",
    0x06: "CORE_TLV_IFACE_MACADDR",
    0x07: "CORE_TLV_IFACE_IP6ADDR",
    0x08: "CORE_TLV_IFACE_IP6MASK",
    0x09: "CORE_TLV_IFACE_TYPE",
    CORE_TLV_NODE_SESSION: "CORE_TLV_IFACE_SESSION",
    0x0B: "CORE_TLV_IFACE_STATE",
    CORE_TLV_NODE_EMUID: "CORE_TLV_IFACE_EMUID",
    CORE_TLV_NODE_NETID: "CORE_TLV_IFACE_NETID",
}

enumdict(iface_tlvs)

# Event Message TLV Types

event_tlvs = {
    0x01: "CORE_TLV_EVENT_NODE",
    0x02: "CORE_TLV_EVENT_TYPE",
    0x03: "CORE_TLV_EVENT_NAME",
    0x04: "CORE_TLV_EVENT_DATA",
    0x05: "CORE_TLV_EVENT_TIME",
    CORE_TLV_NODE_SESSION: "CORE_TLV_EVENT_SESSION",
}

enumdict(event_tlvs)

event_types = dict(enumerate([
    "CORE_EVENT_NONE",
    "CORE_EVENT_DEFINITION_STATE",
    "CORE_EVENT_CONFIGURATION_STATE",
    "CORE_EVENT_INSTANTIATION_STATE",
    "CORE_EVENT_RUNTIME_STATE",
    "CORE_EVENT_DATACOLLECT_STATE",
    "CORE_EVENT_SHUTDOWN_STATE",
    "CORE_EVENT_START",
    "CORE_EVENT_STOP",
    "CORE_EVENT_PAUSE",
    "CORE_EVENT_RESTART",
    "CORE_EVENT_FILE_OPEN",
    "CORE_EVENT_FILE_SAVE",
    "CORE_EVENT_SCHEDULED",
    "CORE_EVENT_RECONFIGURE",
]))

enumdict(event_types)

# Session Message TLV Types

session_tlvs = {
    0x01: "CORE_TLV_SESS_NUMBER",
    0x02: "CORE_TLV_SESS_NAME",
    0x03: "CORE_TLV_SESS_FILE",
    0x04: "CORE_TLV_SESS_NODECOUNT",
    0x05: "CORE_TLV_SESS_DATE",
    0x06: "CORE_TLV_SESS_THUMB",
    0x07: "CORE_TLV_SESS_USER",
    0x0A: "CORE_TLV_SESS_OPAQUE",
}

enumdict(session_tlvs)

# Exception Message TLV Types

exception_tlvs = {
    0x01: "CORE_TLV_EXCP_NODE",
    0x02: "CORE_TLV_EXCP_SESSION",
    0x03: "CORE_TLV_EXCP_LEVEL",
    0x04: "CORE_TLV_EXCP_SOURCE",
    0x05: "CORE_TLV_EXCP_DATE",
    0x06: "CORE_TLV_EXCP_TEXT",
    0x0A: "CORE_TLV_EXCP_OPAQUE",
}

enumdict(exception_tlvs)

exception_levels = dict(enumerate([
    "CORE_EXCP_LEVEL_NONE",
    "CORE_EXCP_LEVEL_FATAL",
    "CORE_EXCP_LEVEL_ERROR",
    "CORE_EXCP_LEVEL_WARNING",
    "CORE_EXCP_LEVEL_NOTICE",
]))

enumdict(exception_levels)

del enumdict
