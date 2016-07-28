#
# CORE
# Copyright (c)2016 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Rod Santiago
#          John Kharouta
#



import core_pb2
import struct
from core.api import *

legacy = coreapi

HDRFMT = "H"
HDRSIZ = struct.calcsize(HDRFMT)
   



class CoreApiBridge(object):

    @staticmethod
    def Api2toLegacy(data):
        message = core_pb2.CoreMessage()
        message.ParseFromString(data)
        if message.HasField('session'):
            return CoreApiBridge.translateApi2SessionMsg(message.session)
        if message.HasField('experiment'):
            return CoreApiBridge.translateExperimentMsg(message.experiment)
        if message.HasField('event'):
            return CoreApiBridge.translateEvent(message.event)
            
    @staticmethod
    def LegacytoApi2(messages):
        api2msgs = []
        for msgstr in messages:
            # Unpack the message
            msgtype, msgflags, msglen = legacy.CoreMessage.unpackhdr(msgstr)
            hdr = msgstr[0:legacy.CoreMessage.hdrsiz]
            data = msgstr[legacy.CoreMessage.hdrsiz:]
            msgcls = legacy.msg_class(msgtype)
            if msgtype == legacy.CORE_API_REG_MSG:
                oldMsg = RegisterMsgWrapper(msgflags, hdr, data)
                print "RegisterMessage"
                print "\twireless=", oldMsg.getWireless()
                print "\tmobility=", oldMsg.getMobility()
                print "\tutility=", oldMsg.getUtility()
                print "\texec=",  oldMsg.getExecsrv()
                print "\tgui=", oldMsg.getGui()
                print "\temul=", oldMsg.getEmulsrv()
                print "\tsess=", oldMsg.getSession()
            elif msgtype == legacy.CORE_API_SESS_MSG:
                oldMsg = SessionMsgWrapper(msgflags, hdr, data)
                print "SessionMessage"
                print "\tnumber=",  oldMsg.getNumber()
                print "\tname=",  oldMsg.getName()
                print "\tfile=",  oldMsg.getFile()
                print "\tnodecount=",  oldMsg.getNodecount()
                print "\tdate=",  oldMsg.getDate()
                print "\tthumb=",  oldMsg.getThumb()
                print "\tuser=",  oldMsg.getUser()
                print "\topaque=",  oldMsg.getOpaque()
                sessions = oldMsg.getNumber().split("|")
                port_num = int(sessions[0])
                newMsg = core_pb2.CoreMessage()
                newMsg.session.SetInParent()
                newMsg.session.clientId = 'client' + sessions[0]
                newMsg.session.port_num = port_num
                api2msgs.append(CoreApiBridge.packApi2(newMsg))
            else:
                print "received message type", msgtype
        return api2msgs

    @staticmethod
    def packApi2(message):
        data = message.SerializeToString()
        return struct.pack(HDRFMT, len(data)) + data

    @staticmethod
    def translateApi2SessionMsg(message):
        print 'Received session request message'
        msgs = []
        msgs.append(RegisterMsgWrapper.createLegacyMessage(0, gui='true'))
        return msgs



    @staticmethod
    def translateExperimentMsg(message):
        print 'Received experiment message'
        msgs = []
        # Flag need to be 0 otherwise CORE will not enter runtime state (per JavaAdaptor, need verification)
        msgs.append(SessionMsgWrapper.createLegacyMessage(
            0, "0", 
            nodecount=str(len(message.nodes) + len(message.devices))))
        # Quickly transition through the definition and configuration states
        msgs.append(EventMsgWrapper.createLegacyMessage(legacy.CORE_EVENT_DEFINITION_STATE))
        msgs.append(EventMsgWrapper.createLegacyMessage(legacy.CORE_EVENT_CONFIGURATION_STATE))

        # Send location
        # TODO: Add this info to the Experiment
        msgs.append(ConfigMsgWrapper.createLegacyMessage(obj="location",
                                                         dataTypes=(9,9,9,9,9,9),
                                                         dataValues='0|0| 47.5766974863|-122.125920191|0.0|150.0'))

        # Send control net configuration
        # TODO

        # send node types
        # TODO

        # send services
        # TODO

        # send nodes
        for node in message.nodes:
            # TODO: Add other fields
            msgs.append(NodeMsgWrapper.createLegacyMessage(
                legacy.CORE_API_ADD_FLAG|legacy.CORE_API_STR_FLAG,
                node.idx,
                str(node.name)))

        for device in message.devices:
            # TODO: Add other fields
            msgs.append(NodeMsgWrapper.createLegacyMessage(
                legacy.CORE_API_ADD_FLAG|legacy.CORE_API_STR_FLAG,
                device.idx,
                str(device.name),
                type = legacy.CORE_NODE_SWITCH)) # TODO: Update this later

        for network in message.networks:
            for channel in network.channels:
                if len(channel.endpoints) == 2:
                    ep0 = channel.endpoints[0]
                    ep1 = channel.endpoints[1]
                    msgs.append(LinkMsgWrapper.createLegacyMessage(legacy.CORE_API_ADD_FLAG,
                                                                   ep0.dev_idx,ep0.intf_idx,
                                                                   ep1.dev_idx,ep1.intf_idx))
                                                       
        # send metadata
        # TODO


        # transition to instantiation state
        # TODO
        msgs.append(EventMsgWrapper.createLegacyMessage(legacy.CORE_EVENT_INSTANTIATION_STATE))
        

        return msgs


    @staticmethod
    def translateEvent(event):
        print 'Received event'






''' 
Legacy API wrapper classes for decoding messages generated by the CORE daemon
'''


class NodeMsgWrapper(legacy.CoreNodeMessage):
                    
    @staticmethod
    def createLegacyMessage(flags, number, name=None, type=legacy.CORE_NODE_DEF, model=None, \
                            emusrv=None, session=None, emuid=-1, netid=-1, services=None, \
                            ipaddr=None, macaddr=None, ip6addr=None, \
                            xpos=-1, ypos=-1, canvas=-1, \
                            lat=None, long=None, alt=None, icon=None, opaque=None):
        tlvdata = legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_NUMBER,number)
        tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_TYPE,type)
        if name is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_NAME,name)
        if ipaddr is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_IPADDR,IPAddr(AF_INET, socket.inet_aton(ipaddr)))
        if macaddr is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_MACADDR,MacAddr.fromstring(macaddr))
        if ip6addr is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_IP6ADDR,IPAddr(AF_INET6, ip6addr))
        if model is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_MODEL,model)
        if emusrv is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_EMUSRV,emusrv)
        if session is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_SESSION,session)
        if xpos >= 0:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_XPOS,xpos)
        if ypos >= 0:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_YPOS,ypos)
        if canvas >= 0:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_CANVAS,canvas)
       # if emuid >= 0:
        tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_EMUID,number)
        if netid >= 0:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_NETID,netid)
        if services is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_SERVICES,services)
        if lat is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_LAT,lat)
        if long is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_LONG,long)
        if alt is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_ALT,alt)
        if icon is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_ICON,icon)
        if opaque is not None:
            tlvdata = tlvdata + legacy.CoreNodeTlv.pack(legacy.CORE_TLV_NODE_OPAQUE,opaque)
        hdr = struct.pack(legacy.CoreMessage.hdrfmt, legacy.CoreNodeMessage.msgtype, flags, len(tlvdata))
        return legacy.CoreNodeMessage(flags, hdr, tlvdata)


    def getNumber(self):
        return self.gettlv(legacy.CORE_TLV_NODE_NUMBER)
    def getType(self):
        return self.gettlv(legacy.CORE_TLV_NODE_TYPE)
    def getName(self):
        return self.gettlv(legacy.CORE_TLV_NODE_NAME)
    def getIpaddr(self):
        return self.gettlv(legacy.CORE_TLV_NODE_IPADDR)
    def getMacaddr(self):
        return self.gettlv(legacy.CORE_TLV_NODE_MACADDR)
    def getIp6addr(self):
        return self.gettlv(legacy.CORE_TLV_NODE_IP6ADDR)
    def getModel(self):
        return self.gettlv(legacy.CORE_TLV_NODE_MODEL)
    def getEmusrv(self):
        return self.gettlv(legacy.CORE_TLV_NODE_EMUSRV)
    def getSession(self):
        return self.gettlv(legacy.CORE_TLV_NODE_SESSION)
    def getXpos(self):
        return self.gettlv(legacy.CORE_TLV_NODE_XPOS)
    def getYpos(self):
        return self.gettlv(legacy.CORE_TLV_NODE_YPOS)
    def getCanvas(self):
        return self.gettlv(legacy.CORE_TLV_NODE_CANVAS)
    def getEmuid(self):
        return self.gettlv(legacy.CORE_TLV_NODE_EMUID)
    def getNetid(self):
        return self.gettlv(legacy.CORE_TLV_NODE_NETID)
    def getServices(self):
        return self.gettlv(legacy.CORE_TLV_NODE_SERVICES)
    def getLat(self):
        return self.gettlv(legacy.CORE_TLV_NODE_LAT)
    def getLong(self):
        return self.gettlv(legacy.CORE_TLV_NODE_LONG)
    def getAlt(self):
        return self.gettlv(legacy.CORE_TLV_NODE_ALT)
    def getIcon(self):
        return self.gettlv(legacy.CORE_TLV_NODE_ICON)
    def getOpaque(self):
        return self.gettlv(legacy.CORE_TLV_NODE_OPAQUE)

class LinkMsgWrapper(legacy.CoreLinkMessage):

    @staticmethod
    def createLegacyMessage(flags, n1number, if1num, n2number, if2num, 
                            delay=0, bw=0, per=None, dup=None, jitter=0, mer=0, burst=0, mburst=0, 
                            session=None, type=legacy.CORE_LINK_WIRED, guiattr=None, 
                            emuid=-1, netid=-1, key=-1, 
                            if1ip4=None, if1ip4mask=24, if1mac=None, if1ip6=None, if1ip6mask=64, 
                            if2ip4=None, if2ip4mask=24, if2mac=None, if2ip6=None, if2ip6mask=64, 
                            opaque=None):
        tlvdata = legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_N1NUMBER,n1number)
        tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_N2NUMBER,n2number)
        # TODO: do we need to set delay, bw, per, dup for default values (as in api.tcl)?
        tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_DELAY,delay)
        tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_BW,bw)
        if per is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_PER,per)
        if dup is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_DUP,dup)
        if jitter > 0:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_JITTER,jitter)
        if mer > 0:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_MER,mer)
        if burst > 0:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_BURST,burst)
        if mburst > 0:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_MBURST,mburst)
        if session is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_SESSION,session)
        tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_TYPE,type)
        if guiattr is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_GUIATTR,guiattr)
        if emuid >= 0:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_EMUID,emuid)
        if netid >= 0:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_NETID,netid)
        if key >= 0:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_KEY,key)
        if if1num > -2:
        	tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF1NUM,if1num)
        if if1ip4 is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF1IP4,IPAddr(AF_INET, socket.inet_aton(if1ip4)))
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF1IP4MASK,if1ip4mask)
        if if1mac is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF1MAC,MacAddr.fromstring(if1mac))
        if if1ip6 is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF1IP6,IPAddr(AF_INET6, socket.inet_pton(AF_INET6,if1ip6)))
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF1IP6MASK,if1ip6mask)
        if if2num > -2:
        	tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF2NUM,if2num)
        if if2ip4 is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF2IP4,IPAddr(AF_INET, socket.inet_aton(if2ip4)))
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF2IP4MASK,if2ip4mask)
        if if2mac is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF2MAC,MacAddr.fromstring(if2mac))
        if if2ip6 is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF2IP6,IPAddr(AF_INET6, socket.inet_pton(AF_INET6,if2ip6)))
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_IF2IP6MASK,if2ip6mask)
        if opaque is not None:
            tlvdata = tlvdata + legacy.CoreLinkTlv.pack(legacy.CORE_TLV_LINK_OPAQUE,opaque)

        hdr = struct.pack(legacy.CoreMessage.hdrfmt, legacy.CoreLinkMessage.msgtype, flags, len(tlvdata))
        return legacy.CoreLinkMessage(flags, hdr, tlvdata)



    def getN1number(self):
        return self.gettlv(legacy.CORE_TLV_LINK_N1NUMBER)
    def getN2number(self):
        return self.gettlv(legacy.CORE_TLV_LINK_N2NUMBER)
    def getDelay(self):
        return self.gettlv(legacy.CORE_TLV_LINK_DELAY)
    def getBw(self):
        return self.gettlv(legacy.CORE_TLV_LINK_BW)
    def getPer(self):
        return self.gettlv(legacy.CORE_TLV_LINK_PER)
    def getDup(self):
        return self.gettlv(legacy.CORE_TLV_LINK_DUP)
    def getJitter(self):
        return self.gettlv(legacy.CORE_TLV_LINK_JITTER)
    def getMer(self):
        return self.gettlv(legacy.CORE_TLV_LINK_MER)
    def getBurst(self):
        return self.gettlv(legacy.CORE_TLV_LINK_BURST)
    def getSession(self):
        return self.gettlv(legacy.CORE_TLV_LINK_SESSION)
    def getMburst(self):
        return self.gettlv(legacy.CORE_TLV_LINK_MBURST)
    def getType(self):
        return self.gettlv(legacy.CORE_TLV_LINK_TYPE)
    def getGuiattr(self):
        return self.gettlv(legacy.CORE_TLV_LINK_GUIATTR)
    def getEmuid(self):
        return self.gettlv(legacy.CORE_TLV_LINK_EMUID)
    def getNetid(self):
        return self.gettlv(legacy.CORE_TLV_LINK_NETID)
    def getKey(self):
        return self.gettlv(legacy.CORE_TLV_LINK_KEY)
    def getIf1num(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF1NUM)
    def getIf1ip4(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF1IP4)
    def getIf1ip4mask(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF1IP4MASK)
    def getIf1mac(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF1MAC)
    def getIf1ip6(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF1IP6)
    def getIf1ip6mask(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF1IP6MASK)
    def getIf2num(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF2NUM)
    def getIf2ip4(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF2IP4)
    def getIf2ip4mask(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF2IP4MASK)
    def getIf2mac(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF2MAC)
    def getIf2ip6(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF2IP6)
    def getIf2ip6mask(self):
        return self.gettlv(legacy.CORE_TLV_LINK_IF2IP6MASK)
    def getOpaque(self):
        return self.gettlv(legacy.CORE_TLV_LINK_OPAQUE)
        
class ExecMsgWrapper(legacy.CoreExecMessage):
    def getNode(self):
        return self.gettlv(legacy.CORE_TLV_EXEC_NODE)
    def getNum(self):
        return self.gettlv(legacy.CORE_TLV_EXEC_NUM)
    def getTime(self):
        return self.gettlv(legacy.CORE_TLV_EXEC_TIME)
    def getCmd(self):
        return self.gettlv(legacy.CORE_TLV_EXEC_CMD)
    def getResult(self):
        return self.gettlv(legacy.CORE_TLV_EXEC_RESULT)
    def getStatus(self):
        return self.gettlv(legacy.CORE_TLV_EXEC_STATUS)
    def getSession(self):
        return self.gettlv(legacy.CORE_TLV_EXEC_SESSION)

class RegisterMsgWrapper(legacy.CoreRegMessage):
    #
    # Overrides of CoreMessage methods to account for multiple values per key in 
    # RegisterMessages. 
    #

    def addtlvdata(self, k, v):
        ''' Append the value 'v' to list of values corresponding to key 'k'
        '''
        if k in self.tlvdata:
            self.tlvdata[k].append(v)
        else:
            self.tlvdata[k] = [v]

    def gettlv(self, tlvtype, idx=0):
        if tlvtype in self.tlvdata:
            return self.tlvdata[tlvtype][idx]
        else:
            return None

    def packtlvdata(self):
        ''' Return packed TLV data as in CoreMessage. Account for multiple values per key.
        '''
        tlvdata = ""
        keys = sorted(self.tlvdata.keys())
        for k in keys:
            for v in self.tlvdata[k]:
                tlvdata += self.tlvcls.pack(k, v)
        return tlvdata

    def __str__(self):
        tmp = "%s <msgtype = %s, flags = %s>" % \
              (self.__class__.__name__, self.typestr(), self.flagstr())
        for k, m in self.tlvdata.iteritems():
            if k in self.tlvcls.tlvtypemap:
                tlvtype = self.tlvcls.tlvtypemap[k]
            else:
                tlvtype = "tlv type %s" % k
            tmp += "\n  %s: " % tlvtype
            for v in m:
                tmp += "%s " % v
        return tmp

    @staticmethod
    def createLegacyMessage(flags, wireless=None, mobility=None, utility=None, execsrv=None, 
                           gui=None, emulsrv=None, session=None):
        tlvdata = ""
        if wireless is not None:
            tlvdata = tlvdata + legacy.CoreRegTlv.pack(legacy.CORE_TLV_REG_WIRELESS,wireless)
        if mobility is not None:
            tlvdata = tlvdata + legacy.CoreRegTlv.pack(legacy.CORE_TLV_REG_MOBILITY,mobility)
        if utility is not None:
            tlvdata = tlvdata + legacy.CoreRegTlv.pack(legacy.CORE_TLV_REG_UTILITY,utility)
        if execsrv is not None:
            tlvdata = tlvdata + legacy.CoreRegTlv.pack(legacy.CORE_TLV_REG_EXECSRV,execsrv)
        if gui is not None:
            tlvdata = tlvdata + legacy.CoreRegTlv.pack(legacy.CORE_TLV_REG_GUI,gui)
        if emulsrv is not None:
            tlvdata = tlvdata + legacy.CoreRegTlv.pack(legacy.CORE_TLV_REG_EMULSRV,emulsrv)
        if session is not None:
            tlvdata = tlvdata + legacy.CoreRegTlv.pack(legacy.CORE_TLV_REG_SESSION,session)
        hdr = struct.pack(legacy.CoreMessage.hdrfmt, legacy.CoreRegMessage.msgtype, flags, len(tlvdata))
        return legacy.CoreRegMessage(flags, hdr, tlvdata)


    def getWireless(self):
        return self.gettlv(legacy.CORE_TLV_REG_WIRELESS)
    def getMobility(self):
        return self.gettlv(legacy.CORE_TLV_REG_MOBILITY)
    def getUtility(self):
        return self.gettlv(legacy.CORE_TLV_REG_UTILITY)
    def getExecsrv(self):
        return self.gettlv(legacy.CORE_TLV_REG_EXECSRV)
    def getGui(self):
        return self.gettlv(legacy.CORE_TLV_REG_GUI)
    def getEmulsrv(self):
        return self.gettlv(legacy.CORE_TLV_REG_EMULSRV)
    def getSession(self):
        return self.gettlv(legacy.CORE_TLV_REG_SESSION)

class ConfigMsgWrapper(legacy.CoreConfMessage):

    @staticmethod
    def createLegacyMessage(obj, type=legacy.CONF_TYPE_FLAGS_NONE, node=-1, netid=-1, session=None, \
                          dataTypes=None, dataValues=None, possibleValues=None, valueGroups=None, \
                          captions=None, bitmap=None, opaque=None):
        tlvdata = legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_OBJ,obj)
        if type != legacy.CONF_TYPE_FLAGS_NONE:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_TYPE,type)
        if node >= 0:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_NODE,node)
        if dataTypes is not None:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_DATA_TYPES,dataTypes)
        if dataValues is not None:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_VALUES,dataValues)
        if captions is not None:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_CAPTIONS,captions)
        if bitmap is not None:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_BITMAP,bitmap)
        if possibleValues is not None:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_POSSIBLE_VALUES,possibleValues)
        if valueGroups is not None:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_GROUPS,valueGroups)
        if session is not None:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_SESSION,session)
        if netid >= 0:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_NETID,netid)
        if opaque is not None:
            tlvdata = tlvdata + legacy.CoreConfTlv.pack(legacy.CORE_TLV_CONF_OPAQUE,opaque)
        hdr = struct.pack(legacy.CoreMessage.hdrfmt, legacy.CoreConfMessage.msgtype, 0, len(tlvdata))
        return legacy.CoreConfMessage(0, hdr, tlvdata)



    def getNode(self):
        return self.gettlv(legacy.CORE_TLV_CONF_NODE)
    def getObj(self):
        return self.gettlv(legacy.CORE_TLV_CONF_OBJ)
    def getType(self):
        return self.gettlv(legacy.CORE_TLV_CONF_TYPE)
    def getData(self):
        return self.gettlv(legacy.CORE_TLV_CONF_DATA_TYPES)
    def getValues(self):
        return self.gettlv(legacy.CORE_TLV_CONF_VALUES)
    def getCaptions(self):
        return self.gettlv(legacy.CORE_TLV_CONF_CAPTIONS)
    def getBitmap(self):
        return self.gettlv(legacy.CORE_TLV_CONF_BITMAP)
    def getPossible(self):
        return self.gettlv(legacy.CORE_TLV_CONF_POSSIBLE_VALUES)
    def getGroups(self):
        return self.gettlv(legacy.CORE_TLV_CONF_GROUPS)
    def getSession(self):
        return self.gettlv(legacy.CORE_TLV_CONF_SESSION)
    def getNetid(self):
        return self.gettlv(legacy.CORE_TLV_CONF_NETID)
    def getOpaque(self):
        return self.gettlv(legacy.CORE_TLV_CONF_OPAQUE)

class FileMsgWrapper(legacy.CoreFileMessage):
    def getNode(self):
        return self.gettlv(legacy.CORE_TLV_FILE_NODE)
    def getName(self):
        return self.gettlv(legacy.CORE_TLV_FILE_NAME)
    def getMode(self):
        return self.gettlv(legacy.CORE_TLV_FILE_MODE)
    def getNum(self):
        return self.gettlv(legacy.CORE_TLV_FILE_NUM)
    def getType(self):
        return self.gettlv(legacy.CORE_TLV_FILE_TYPE)
    def getSrcname(self):
        return self.gettlv(legacy.CORE_TLV_FILE_SRCNAME)
    def getSession(self):
        return self.gettlv(legacy.CORE_TLV_FILE_SESSION)
    def getData(self):
        return self.gettlv(legacy.CORE_TLV_FILE_DATA)
    def getCmpdata(self):
        return self.gettlv(legacy.CORE_TLV_FILE_CMPDATA)

class InterfaceMsgWrapper(legacy.CoreIfaceMessage):
    def getNode(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_NODE)
    def getNum(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_NUM)
    def getName(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_NAME)
    def getIpaddr(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_IPADDR)
    def getMask(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_MASK)
    def getMacaddr(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_MACADDR)
    def getIp6addr(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_IP6ADDR)
    def getIp6mask(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_IP6MASK)
    def getType(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_TYPE)
    def getSession(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_SESSION)
    def getState(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_STATE)
    def getEmuid(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_EMUID)
    def getNetid(self):
        return self.gettlv(legacy.CORE_TLV_IFACE_NETID)

class EventMsgWrapper(legacy.CoreEventMessage):

    @staticmethod
    def createLegacyMessage(type, flags=0, nodenum=-1, name=None, data=None, session=None):
        tlvdata = legacy.CoreEventTlv.pack(legacy.CORE_TLV_EVENT_TYPE, type)
        if nodenum >= 0:
            tlvdata = tlvdata + legacy.CoreEventTlv.pack(legacy.CORE_TLV_EVENT_NODE, nodenum)
        if name is not None:
            tlvdata = tlvdata + legacy.CoreEventTlv.pack(legacy.CORE_TLV_EVENT_NAME, name)
        if data is not None:
            tlvdata = tlvdata + legacy.CoreEventTlv.pack(legacy.CORE_TLV_EVENT_DATA, data)
        if session is not None:
            tlvdata = tlvdata + legacy.CoreEventTlv.pack(legacy.CORE_TLV_EVENT_SESSION, session)
        hdr = struct.pack(legacy.CoreMessage.hdrfmt, legacy.CoreEventMessage.msgtype, flags, len(tlvdata))
        return legacy.CoreEventMessage(flags, hdr, tlvdata)

    def getNode(self):
        return self.gettlv(legacy.CORE_TLV_EVENT_NODE)
    def getType(self):
        return self.gettlv(legacy.CORE_TLV_EVENT_TYPE)
    def getName(self):
        return self.gettlv(legacy.CORE_TLV_EVENT_NAME)
    def getData(self):
        return self.gettlv(legacy.CORE_TLV_EVENT_DATA)
    def getTime(self):
        return self.gettlv(legacy.CORE_TLV_EVENT_TIME)
    def getSession(self):
        return self.gettlv(legacy.CORE_TLV_EVENT_SESSION)

class SessionMsgWrapper(legacy.CoreSessionMessage):

    @staticmethod
    def createLegacyMessage(flags, number, name=None, file=None, nodecount=None, thumb=None, user=None, opaque=None):
        tlvdata = legacy.CoreSessionTlv.pack(legacy.CORE_TLV_SESS_NUMBER,number)
        if name is not None:
            tlvdata = tlvdata + legacy.CoreSessionTlv.pack(legacy.CORE_TLV_SESS_NAME,name)
        if file is not None:
            tlvdata = tlvdata + legacy.CoreSessionTlv.pack(legacy.CORE_TLV_SESS_FILE,file)
        if nodecount is not None: # CORE API expects a string, which can be a list of node numbers
            tlvdata = tlvdata + legacy.CoreSessionTlv.pack(legacy.CORE_TLV_SESS_NODECOUNT,nodecount)
        if thumb is not None:
            tlvdata = tlvdata + legacy.CoreSessionTlv.pack(legacy.CORE_TLV_SESS_THUMB,thumb)
        if user is not None:
            tlvdata = tlvdata + legacy.CoreSessionTlv.pack(legacy.CORE_TLV_SESS_USER,user)
        if opaque is not None:
            tlvdata = tlvdata + legacy.CoreSessionTlv.pack(legacy.CORE_TLV_SESS_OPAQUE,opaque)
        hdr = struct.pack(legacy.CoreMessage.hdrfmt, legacy.CoreSessionMessage.msgtype, flags, len(tlvdata))
        return legacy.CoreSessionMessage(flags, hdr, tlvdata)


    def getNumber(self):
        return self.gettlv(legacy.CORE_TLV_SESS_NUMBER)
    def getName(self):
        return self.gettlv(legacy.CORE_TLV_SESS_NAME)
    def getFile(self):
        return self.gettlv(legacy.CORE_TLV_SESS_FILE)
    def getNodecount(self):
        return self.gettlv(legacy.CORE_TLV_SESS_NODECOUNT)
    def getDate(self):
        return self.gettlv(legacy.CORE_TLV_SESS_DATE)
    def getThumb(self):
        return self.gettlv(legacy.CORE_TLV_SESS_THUMB)
    def getUser(self):
        return self.gettlv(legacy.CORE_TLV_SESS_USER)
    def getOpaque(self):
        return self.gettlv(legacy.CORE_TLV_SESS_OPAQUE)

class ExceptionMsgWrapper(legacy.CoreExceptionMessage):
    def getNode(self):
        return self.gettlv(legacy.CORE_TLV_EXCP_NODE)
    def getSession(self):
        return self.gettlv(legacy.CORE_TLV_EXCP_SESSION)
    def getLevel(self):
        return self.gettlv(legacy.CORE_TLV_EXCP_LEVEL)
    def getSource(self):
        return self.gettlv(legacy.CORE_TLV_EXCP_SOURCE)
    def getDate(self):
        return self.gettlv(legacy.CORE_TLV_EXCP_DATE)
    def getText(self):
        return self.gettlv(legacy.CORE_TLV_EXCP_TEXT)
    def getOpaque(self):
        return self.gettlv(legacy.CORE_TLV_EXCP_OPAQUE)

class UnknownMsgWrapper(legacy.CoreMessage):
    "No method"
    pass
