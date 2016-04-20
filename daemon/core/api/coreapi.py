#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
coreapi.py: uses coreapi_data for Message and TLV types, and defines TLV data
types and objects used for parsing and building CORE API messages.
'''

import struct

from core.api.data import *
from core.misc.ipaddr import *


class CoreTlvData(object):
    datafmt = None
    datatype = None
    padlen = None

    @classmethod
    def pack(cls, value):
        "return: (tlvlen, tlvdata)"
        tmp = struct.pack(cls.datafmt, value)
        return len(tmp) - cls.padlen, tmp

    @classmethod
    def unpack(cls, data):
        return struct.unpack(cls.datafmt, data)[0]
    
    @classmethod
    def packstring(cls, strvalue):
        return cls.pack(cls.fromstring(strvalue))
        
    @classmethod
    def fromstring(cls, s):
        return cls.datatype(s)

class CoreTlvDataObj(CoreTlvData):
    @classmethod
    def pack(cls, obj):
        "return: (tlvlen, tlvdata)"
        tmp = struct.pack(cls.datafmt, cls.getvalue(obj))
        return len(tmp) - cls.padlen, tmp

    @classmethod
    def unpack(cls, data):
        return cls.newobj(struct.unpack(cls.datafmt, data)[0])

    @staticmethod
    def getvalue(obj):
        raise NotImplementedError

    @staticmethod
    def newobj(obj):
        raise NotImplementedError

class CoreTlvDataUint16(CoreTlvData):
    datafmt = "!H"
    datatype = int
    padlen = 0

class CoreTlvDataUint32(CoreTlvData):
    datafmt = "!2xI"
    datatype = int
    padlen = 2

class CoreTlvDataUint64(CoreTlvData):
    datafmt = "!2xQ"
    datatype = long
    padlen = 2

class CoreTlvDataString(CoreTlvData):
    datatype = str

    @staticmethod
    def pack(value):
        if not isinstance(value, str):
            raise ValueError, "value not a string: %s" % value
        if len(value) < 256:
            hdrsiz = CoreTlv.hdrsiz
        else:
            hdrsiz = CoreTlv.longhdrsiz
        padlen = -(hdrsiz + len(value)) % 4
        return len(value), value + '\0' * padlen

    @staticmethod
    def unpack(data):
        return data.rstrip('\0')

class CoreTlvDataUint16List(CoreTlvData):
    ''' List of unsigned 16-bit values.
    '''
    datatype = tuple

    @staticmethod
    def pack(values):
        if not isinstance(values, tuple):
            raise ValueError, "value not a tuple: %s" % values
        data = ""
        for v in values:
            data += struct.pack("!H", v)
        padlen = -(CoreTlv.hdrsiz + len(data)) % 4
        return len(data), data + '\0' * padlen

    @staticmethod
    def unpack(data):
        datafmt = "!%dH" % (len(data)/2)
        return struct.unpack(datafmt, data)
        
    @classmethod
    def fromstring(cls, s):
        return tuple(map(lambda(x): int(x), s.split()))

class CoreTlvDataIPv4Addr(CoreTlvDataObj):
    datafmt = "!2x4s"
    datatype = IPAddr.fromstring
    padlen = 2

    @staticmethod
    def getvalue(obj):
        return obj.addr

    @staticmethod
    def newobj(value):
        return IPAddr(af = AF_INET, addr = value)

class CoreTlvDataIPv6Addr(CoreTlvDataObj):
    datafmt = "!16s2x"
    datatype = IPAddr.fromstring
    padlen = 2

    @staticmethod
    def getvalue(obj):
        return obj.addr

    @staticmethod
    def newobj(value):
        return IPAddr(af = AF_INET6, addr = value)

class CoreTlvDataMacAddr(CoreTlvDataObj):
    datafmt = "!2x8s"
    datatype = MacAddr.fromstring
    padlen = 2

    @staticmethod
    def getvalue(obj):
        return '\0\0' + obj.addr # extend to 64 bits

    @staticmethod
    def newobj(value):
        return MacAddr(addr = value[2:]) # only use 48 bits

class CoreTlv(object):
    hdrfmt = "!BB"
    hdrsiz = struct.calcsize(hdrfmt)

    longhdrfmt = "!BBH"
    longhdrsiz = struct.calcsize(longhdrfmt)

    tlvtypemap = {}
    tlvdataclsmap = {}

    def __init__(self, tlvtype, tlvdata):
        self.tlvtype = tlvtype
        if tlvdata:
            try:
                self.value = self.tlvdataclsmap[self.tlvtype].unpack(tlvdata)
            except KeyError:
                self.value = tlvdata
        else:
            self.value = None

    @classmethod
    def unpack(cls, data):
        "parse data and return (tlv, remainingdata)"
        tlvtype, tlvlen = struct.unpack(cls.hdrfmt, data[:cls.hdrsiz])
        hdrsiz = cls.hdrsiz
        if tlvlen == 0:
            tlvtype, zero, tlvlen = struct.unpack(cls.longhdrfmt,
                                                  data[:cls.longhdrsiz])
            hdrsiz = cls.longhdrsiz
        tlvsiz = hdrsiz + tlvlen
        tlvsiz += -tlvsiz % 4           # for 32-bit alignment
        return cls(tlvtype, data[hdrsiz:tlvsiz]), data[tlvsiz:]

    @classmethod
    def pack(cls, tlvtype, value):
        try:
            tlvlen, tlvdata = cls.tlvdataclsmap[tlvtype].pack(value)
        except Exception, e:
            raise ValueError, "TLV packing error type=%s: %s" % (tlvtype, e)
        if tlvlen < 256:
            hdr = struct.pack(cls.hdrfmt, tlvtype, tlvlen)
        else:
            hdr = struct.pack(cls.longhdrfmt, tlvtype, 0, tlvlen)
        return hdr + tlvdata
        
    @classmethod
    def packstring(cls, tlvtype, value):
        return cls.pack(tlvtype, cls.tlvdataclsmap[tlvtype].fromstring(value))

    def typestr(self):
        try:
            return self.tlvtypemap[self.tlvtype]
        except KeyError:
            return "unknown tlv type: %s" % str(self.tlvtype)

    def __str__(self):
        return "%s <tlvtype = %s, value = %s>" % \
               (self.__class__.__name__, self.typestr(), self.value)

class CoreNodeTlv(CoreTlv):
    tlvtypemap = node_tlvs
    tlvdataclsmap = {
        CORE_TLV_NODE_NUMBER: CoreTlvDataUint32,
        CORE_TLV_NODE_TYPE: CoreTlvDataUint32,
        CORE_TLV_NODE_NAME: CoreTlvDataString,
        CORE_TLV_NODE_IPADDR: CoreTlvDataIPv4Addr,
        CORE_TLV_NODE_MACADDR: CoreTlvDataMacAddr,
        CORE_TLV_NODE_IP6ADDR: CoreTlvDataIPv6Addr,
        CORE_TLV_NODE_MODEL: CoreTlvDataString,
        CORE_TLV_NODE_EMUSRV: CoreTlvDataString,
        CORE_TLV_NODE_SESSION: CoreTlvDataString,
        CORE_TLV_NODE_XPOS: CoreTlvDataUint16,
        CORE_TLV_NODE_YPOS: CoreTlvDataUint16,
        CORE_TLV_NODE_CANVAS: CoreTlvDataUint16,
        CORE_TLV_NODE_EMUID: CoreTlvDataUint32,
        CORE_TLV_NODE_NETID: CoreTlvDataUint32,
        CORE_TLV_NODE_SERVICES: CoreTlvDataString,
        CORE_TLV_NODE_LAT: CoreTlvDataString,
        CORE_TLV_NODE_LONG: CoreTlvDataString,
        CORE_TLV_NODE_ALT: CoreTlvDataString,
        CORE_TLV_NODE_ICON: CoreTlvDataString,
        CORE_TLV_NODE_OPAQUE: CoreTlvDataString,
    }

class CoreLinkTlv(CoreTlv):
    tlvtypemap = link_tlvs
    tlvdataclsmap = {
        CORE_TLV_LINK_N1NUMBER: CoreTlvDataUint32,
        CORE_TLV_LINK_N2NUMBER: CoreTlvDataUint32,
        CORE_TLV_LINK_DELAY: CoreTlvDataUint64,
        CORE_TLV_LINK_BW: CoreTlvDataUint64,
        CORE_TLV_LINK_PER: CoreTlvDataString,
        CORE_TLV_LINK_DUP: CoreTlvDataString,
        CORE_TLV_LINK_JITTER: CoreTlvDataUint64,
        CORE_TLV_LINK_MER: CoreTlvDataUint16,
        CORE_TLV_LINK_BURST: CoreTlvDataUint16,
        CORE_TLV_LINK_SESSION: CoreTlvDataString,
        CORE_TLV_LINK_MBURST: CoreTlvDataUint16,
        CORE_TLV_LINK_TYPE: CoreTlvDataUint32,
        CORE_TLV_LINK_GUIATTR: CoreTlvDataString,
        CORE_TLV_LINK_UNI: CoreTlvDataUint16,
        CORE_TLV_LINK_EMUID: CoreTlvDataUint32,
        CORE_TLV_LINK_NETID: CoreTlvDataUint32,
        CORE_TLV_LINK_KEY: CoreTlvDataUint32,
        CORE_TLV_LINK_IF1NUM: CoreTlvDataUint16,
        CORE_TLV_LINK_IF1IP4: CoreTlvDataIPv4Addr,
        CORE_TLV_LINK_IF1IP4MASK: CoreTlvDataUint16,
        CORE_TLV_LINK_IF1MAC: CoreTlvDataMacAddr,
        CORE_TLV_LINK_IF1IP6: CoreTlvDataIPv6Addr,
        CORE_TLV_LINK_IF1IP6MASK: CoreTlvDataUint16,
        CORE_TLV_LINK_IF2NUM: CoreTlvDataUint16,
        CORE_TLV_LINK_IF2IP4: CoreTlvDataIPv4Addr,
        CORE_TLV_LINK_IF2IP4MASK: CoreTlvDataUint16,
        CORE_TLV_LINK_IF2MAC: CoreTlvDataMacAddr,
        CORE_TLV_LINK_IF2IP6: CoreTlvDataIPv6Addr,
        CORE_TLV_LINK_IF2IP6MASK: CoreTlvDataUint16,
        CORE_TLV_LINK_IF1NAME: CoreTlvDataString,
        CORE_TLV_LINK_IF2NAME: CoreTlvDataString,
        CORE_TLV_LINK_OPAQUE: CoreTlvDataString,
    }

class CoreExecTlv(CoreTlv):
    tlvtypemap = exec_tlvs
    tlvdataclsmap = {
        CORE_TLV_EXEC_NODE: CoreTlvDataUint32,
        CORE_TLV_EXEC_NUM: CoreTlvDataUint32,
        CORE_TLV_EXEC_TIME: CoreTlvDataUint32,
        CORE_TLV_EXEC_CMD: CoreTlvDataString,
        CORE_TLV_EXEC_RESULT: CoreTlvDataString,
        CORE_TLV_EXEC_STATUS: CoreTlvDataUint32,
        CORE_TLV_EXEC_SESSION: CoreTlvDataString,
    }

class CoreRegTlv(CoreTlv):
    tlvtypemap = reg_tlvs
    tlvdataclsmap = {
        CORE_TLV_REG_WIRELESS: CoreTlvDataString,
        CORE_TLV_REG_MOBILITY: CoreTlvDataString,
        CORE_TLV_REG_UTILITY: CoreTlvDataString,
        CORE_TLV_REG_EXECSRV: CoreTlvDataString,
        CORE_TLV_REG_GUI: CoreTlvDataString,
        CORE_TLV_REG_EMULSRV: CoreTlvDataString,
        CORE_TLV_REG_SESSION: CoreTlvDataString,
    }

class CoreConfTlv(CoreTlv):
    tlvtypemap = conf_tlvs
    tlvdataclsmap = {
        CORE_TLV_CONF_NODE: CoreTlvDataUint32,
        CORE_TLV_CONF_OBJ: CoreTlvDataString,
        CORE_TLV_CONF_TYPE: CoreTlvDataUint16,
        CORE_TLV_CONF_DATA_TYPES: CoreTlvDataUint16List,
        CORE_TLV_CONF_VALUES: CoreTlvDataString,
        CORE_TLV_CONF_CAPTIONS: CoreTlvDataString,
        CORE_TLV_CONF_BITMAP: CoreTlvDataString,
        CORE_TLV_CONF_POSSIBLE_VALUES: CoreTlvDataString,
        CORE_TLV_CONF_GROUPS: CoreTlvDataString,
        CORE_TLV_CONF_SESSION: CoreTlvDataString,
        CORE_TLV_CONF_IFNUM: CoreTlvDataUint16,
        CORE_TLV_CONF_NETID: CoreTlvDataUint32,
        CORE_TLV_CONF_OPAQUE: CoreTlvDataString, 
    }

class CoreFileTlv(CoreTlv):
    tlvtypemap = file_tlvs
    tlvdataclsmap = {
        CORE_TLV_FILE_NODE: CoreTlvDataUint32,
        CORE_TLV_FILE_NAME: CoreTlvDataString,
        CORE_TLV_FILE_MODE: CoreTlvDataString,
        CORE_TLV_FILE_NUM: CoreTlvDataUint16,
        CORE_TLV_FILE_TYPE: CoreTlvDataString,
        CORE_TLV_FILE_SRCNAME: CoreTlvDataString,
        CORE_TLV_FILE_SESSION: CoreTlvDataString,
        CORE_TLV_FILE_DATA: CoreTlvDataString,
        CORE_TLV_FILE_CMPDATA: CoreTlvDataString,
    }

class CoreIfaceTlv(CoreTlv):
    tlvtypemap = iface_tlvs
    tlvdataclsmap = {
        CORE_TLV_IFACE_NODE: CoreTlvDataUint32,
        CORE_TLV_IFACE_NUM: CoreTlvDataUint16,
        CORE_TLV_IFACE_NAME: CoreTlvDataString,
        CORE_TLV_IFACE_IPADDR: CoreTlvDataIPv4Addr,
        CORE_TLV_IFACE_MASK: CoreTlvDataUint16,
        CORE_TLV_IFACE_MACADDR: CoreTlvDataMacAddr,
        CORE_TLV_IFACE_IP6ADDR: CoreTlvDataIPv6Addr,
        CORE_TLV_IFACE_IP6MASK: CoreTlvDataUint16,
        CORE_TLV_IFACE_TYPE: CoreTlvDataUint16,
        CORE_TLV_IFACE_SESSION: CoreTlvDataString,
        CORE_TLV_IFACE_STATE: CoreTlvDataUint16,
        CORE_TLV_IFACE_EMUID: CoreTlvDataUint32,
        CORE_TLV_IFACE_NETID: CoreTlvDataUint32,
    }

class CoreEventTlv(CoreTlv):
    tlvtypemap = event_tlvs
    tlvdataclsmap = {
        CORE_TLV_EVENT_NODE: CoreTlvDataUint32,
        CORE_TLV_EVENT_TYPE: CoreTlvDataUint32,
        CORE_TLV_EVENT_NAME: CoreTlvDataString,
        CORE_TLV_EVENT_DATA: CoreTlvDataString,
        CORE_TLV_EVENT_TIME: CoreTlvDataString,
        CORE_TLV_EVENT_SESSION: CoreTlvDataString,
    }

class CoreSessionTlv(CoreTlv):
    tlvtypemap = session_tlvs
    tlvdataclsmap = {
        CORE_TLV_SESS_NUMBER: CoreTlvDataString,
        CORE_TLV_SESS_NAME: CoreTlvDataString,
        CORE_TLV_SESS_FILE: CoreTlvDataString,
        CORE_TLV_SESS_NODECOUNT: CoreTlvDataString,
        CORE_TLV_SESS_DATE: CoreTlvDataString,
        CORE_TLV_SESS_THUMB: CoreTlvDataString,
        CORE_TLV_SESS_USER: CoreTlvDataString,
        CORE_TLV_SESS_OPAQUE: CoreTlvDataString,
    }

class CoreExceptionTlv(CoreTlv):
    tlvtypemap = exception_tlvs
    tlvdataclsmap = {
        CORE_TLV_EXCP_NODE: CoreTlvDataUint32,
        CORE_TLV_EXCP_SESSION: CoreTlvDataString,
        CORE_TLV_EXCP_LEVEL: CoreTlvDataUint16,
        CORE_TLV_EXCP_SOURCE: CoreTlvDataString,
        CORE_TLV_EXCP_DATE: CoreTlvDataString,
        CORE_TLV_EXCP_TEXT: CoreTlvDataString,
        CORE_TLV_EXCP_OPAQUE: CoreTlvDataString,
    }


class CoreMessage(object):
    hdrfmt = "!BBH"
    hdrsiz = struct.calcsize(hdrfmt)

    msgtype = None

    flagmap = {}

    tlvcls = CoreTlv

    def __init__(self, flags, hdr, data):
        self.rawmsg = hdr + data
        self.flags = flags
        self.tlvdata = {}
        self.parsedata(data)

    @classmethod
    def unpackhdr(cls, data):
        "parse data and return (msgtype, msgflags, msglen)"
        msgtype, msgflags, msglen = struct.unpack(cls.hdrfmt, data[:cls.hdrsiz])
        return msgtype, msgflags, msglen

    @classmethod
    def pack(cls, msgflags, tlvdata):
        hdr = struct.pack(cls.hdrfmt, cls.msgtype, msgflags, len(tlvdata))
        return hdr + tlvdata

    def addtlvdata(self, k, v):
        if k in self.tlvdata:
            raise KeyError, "key already exists: %s (val=%s)" % (k, v)
        self.tlvdata[k] = v

    def gettlv(self, tlvtype):
        if tlvtype in self.tlvdata:
            return self.tlvdata[tlvtype]
        else:
            return None

    def parsedata(self, data):
        while data:
            tlv, data = self.tlvcls.unpack(data)
            self.addtlvdata(tlv.tlvtype, tlv.value)
            
    def packtlvdata(self):
        ''' Opposite of parsedata(). Return packed TLV data using
        self.tlvdata dict. Used by repack().
        '''
        tlvdata = ""
        keys = sorted(self.tlvdata.keys())
        for k in keys:
            v = self.tlvdata[k]
            tlvdata += self.tlvcls.pack(k, v)
        return tlvdata
    
    def repack(self):
        ''' Invoke after updating self.tlvdata[] to rebuild self.rawmsg.
        Useful for modifying a message that has been parsed, before
        sending the raw data again.
        '''
        tlvdata = self.packtlvdata()
        self.rawmsg = self.pack(self.flags, tlvdata)

    def typestr(self):
        try:
            return message_types[self.msgtype]
        except KeyError:
            return "unknown message type: %s" % str(self.msgtype)

    def flagstr(self):
        msgflags = []
        flag = 1L
        while True:
            if (self.flags & flag):
                try:
                    msgflags.append(self.flagmap[flag])
                except KeyError:
                    msgflags.append("0x%x" % flag)
            flag <<= 1
            if not (self.flags & ~(flag - 1)):
                break
        return "0x%x <%s>" % (self.flags, " | ".join(msgflags))

    def __str__(self):
        tmp = "%s <msgtype = %s, flags = %s>" % \
              (self.__class__.__name__, self.typestr(), self.flagstr())
        for k, v in self.tlvdata.iteritems():
            if k in self.tlvcls.tlvtypemap:
                tlvtype = self.tlvcls.tlvtypemap[k]
            else:
                tlvtype = "tlv type %s" % k
            tmp += "\n  %s: %s" % (tlvtype, v)
        return tmp

    def nodenumbers(self):
        ''' Return a list of node numbers included in this message.
        '''
        n = None
        n2 = None
        # not all messages have node numbers
        if self.msgtype == CORE_API_NODE_MSG:
            n = self.gettlv(CORE_TLV_NODE_NUMBER)
        elif self.msgtype == CORE_API_LINK_MSG:
            n = self.gettlv(CORE_TLV_LINK_N1NUMBER)
            n2 = self.gettlv(CORE_TLV_LINK_N2NUMBER)
        elif self.msgtype == CORE_API_EXEC_MSG:
            n = self.gettlv(CORE_TLV_EXEC_NODE)
        elif self.msgtype == CORE_API_CONF_MSG:
            n = self.gettlv(CORE_TLV_CONF_NODE)
        elif self.msgtype == CORE_API_FILE_MSG:
            n = self.gettlv(CORE_TLV_FILE_NODE)
        elif self.msgtype == CORE_API_IFACE_MSG:
            n = self.gettlv(CORE_TLV_IFACE_NODE)
        elif self.msgtype == CORE_API_EVENT_MSG:
            n = self.gettlv(CORE_TLV_EVENT_NODE)
        r = []
        if n is not None:
            r.append(n)
        if n2 is not None:
            r.append(n2)
        return r
        
    def sessionnumbers(self):
        ''' Return a list of session numbers included in this message.
        '''
        r = []
        if self.msgtype == CORE_API_SESS_MSG:
            s = self.gettlv(CORE_TLV_SESS_NUMBER)
        elif self.msgtype == CORE_API_EXCP_MSG:
            s = self.gettlv(CORE_TLV_EXCP_SESSION)
        else:
            # All other messages share TLV number 0xA for the session number(s).
            s = self.gettlv(CORE_TLV_NODE_SESSION)
        if s is not None:
            for sid in s.split('|'):
                r.append(int(sid))
        return r


class CoreNodeMessage(CoreMessage):
    msgtype = CORE_API_NODE_MSG
    flagmap = message_flags
    tlvcls = CoreNodeTlv

class CoreLinkMessage(CoreMessage):
    msgtype = CORE_API_LINK_MSG
    flagmap = message_flags
    tlvcls = CoreLinkTlv

class CoreExecMessage(CoreMessage):
    msgtype = CORE_API_EXEC_MSG
    flagmap = message_flags
    tlvcls = CoreExecTlv

class CoreRegMessage(CoreMessage):
    msgtype = CORE_API_REG_MSG
    flagmap = message_flags
    tlvcls = CoreRegTlv

class CoreConfMessage(CoreMessage):
    msgtype = CORE_API_CONF_MSG
    flagmap = message_flags
    tlvcls = CoreConfTlv

class CoreFileMessage(CoreMessage):
    msgtype = CORE_API_FILE_MSG
    flagmap = message_flags
    tlvcls = CoreFileTlv

class CoreIfaceMessage(CoreMessage):
    msgtype = CORE_API_IFACE_MSG
    flagmap = message_flags
    tlvcls = CoreIfaceTlv

class CoreEventMessage(CoreMessage):
    msgtype = CORE_API_EVENT_MSG
    flagmap = message_flags
    tlvcls = CoreEventTlv

class CoreSessionMessage(CoreMessage):
    msgtype = CORE_API_SESS_MSG
    flagmap = message_flags
    tlvcls = CoreSessionTlv

class CoreExceptionMessage(CoreMessage):
    msgtype = CORE_API_EXCP_MSG
    flagmap = message_flags
    tlvcls = CoreExceptionTlv

msgclsmap = {
    CORE_API_NODE_MSG: CoreNodeMessage,
    CORE_API_LINK_MSG: CoreLinkMessage,
    CORE_API_EXEC_MSG: CoreExecMessage,
    CORE_API_REG_MSG: CoreRegMessage,
    CORE_API_CONF_MSG: CoreConfMessage,
    CORE_API_FILE_MSG: CoreFileMessage,
    CORE_API_IFACE_MSG: CoreIfaceMessage,
    CORE_API_EVENT_MSG: CoreEventMessage,
    CORE_API_SESS_MSG: CoreSessionMessage,
    CORE_API_EXCP_MSG: CoreExceptionMessage,
}

def msg_class(msgtypeid):
    global msgclsmap
    return msgclsmap[msgtypeid]

nodeclsmap = {}

def add_node_class(name, nodetypeid, nodecls, change = False):
    global nodeclsmap
    if nodetypeid in nodeclsmap:
        if not change:
            raise ValueError, \
                "node class already exists for nodetypeid %s" % nodetypeid
    nodeclsmap[nodetypeid] = nodecls
    if nodetypeid not in node_types:
        node_types[nodetypeid] = name
        exec "%s = %s" % (name, nodetypeid) in globals()
    elif name != node_types[nodetypeid]:
        raise ValueError, "node type already exists for '%s'" % name
    else:
        pass

def change_node_class(name, nodetypeid, nodecls):
    return add_node_class(name, nodetypeid, nodecls, change = True)

def node_class(nodetypeid):
    global nodeclsmap
    return nodeclsmap[nodetypeid]

def str_to_list(s):
    ''' Helper to convert pipe-delimited string ("a|b|c") into a list (a, b, c)
    '''
    if s is None:
        return None
    return s.split("|")

def state_name(n):
    ''' Helper to convert state number into state name using event types.
    '''
    if n in event_types:
        eventname = event_types[n]
        name = eventname.split('_')[2]
    else:
        name = "unknown"
    return name
