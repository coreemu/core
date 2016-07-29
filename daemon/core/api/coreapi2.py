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
from core.api import coreapi, corewrapper

wrapper = corewrapper
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
            parser = wrapper.CoreMessageParser(msgstr)
            if parser.getType() == legacy.CORE_API_REG_MSG:
                regMsg = parser.createWrapper()
                print "RegisterMessage"
                print "\twireless=", regMsg.getWireless()
                print "\tmobility=", regMsg.getMobility()
                print "\tutility=", regMsg.getUtility()
                print "\texec=",  regMsg.getExecsrv()
                print "\tgui=", regMsg.getGui()
                print "\temul=", regMsg.getEmulsrv()
                print "\tsess=", regMsg.getSession()
            elif parser.getType() == legacy.CORE_API_SESS_MSG:
                sessMsg = parser.createWrapper()
                print "SessionMessage"
                print "\tnumber=",  sessMsg.getNumber()
                print "\tname=",  sessMsg.getName()
                print "\tfile=",  sessMsg.getFile()
                print "\tnodecount=",  sessMsg.getNodecount()
                print "\tdate=",  sessMsg.getDate()
                print "\tthumb=",  sessMsg.getThumb()
                print "\tuser=",  sessMsg.getUser()
                print "\topaque=",  sessMsg.getOpaque()
                sessions = sessMsg.getNumber().split("|")
                port_num = int(sessions[0])
                newMsg = core_pb2.CoreMessage()
                newMsg.session.SetInParent()
                newMsg.session.clientId = 'client' + sessions[0]
                newMsg.session.port_num = port_num
                api2msgs.append(CoreApiBridge.packApi2(newMsg))
            else:
                print "received message type", parser.getType()
        return api2msgs

    @staticmethod
    def packApi2(message):
        data = message.SerializeToString()
        return struct.pack(HDRFMT, len(data)) + data

    @staticmethod
    def translateApi2SessionMsg(message):
        print 'Received session request message'
        msgs = []
        msgs.append(wrapper.RegMsg.instantiate(0, gui='true'))
        return msgs



    @staticmethod
    def translateExperimentMsg(message):
        print 'Received experiment message'
        msgs = []
        # Flag need to be 0 otherwise CORE will not enter runtime state (per JavaAdaptor, need verification)
        msgs.append(wrapper.SessionMsg.instantiate(
            0, "0", 
            nodecount=str(len(message.nodes) + len(message.devices))))
        # Quickly transition through the definition and configuration states
        msgs.append(wrapper.EventMsg.instantiate(legacy.CORE_EVENT_DEFINITION_STATE))
        msgs.append(wrapper.EventMsg.instantiate(legacy.CORE_EVENT_CONFIGURATION_STATE))

        # Send location
        # TODO: Add this info to the Experiment
        msgs.append(wrapper.ConfMsg.instantiate(obj="location",
                                                dataTypes=(9,9,9,9,9,9),
                                                dataValues='0|0| 47.5766974863|-122.125920191|0.0|150.0'))

        # Send control net configuration
        # TODO

        # send node types
        # TODO

        # send services
        # TODO

        # send nodes
        devices = {}
        for node in message.nodes:
            if node.idx in devices:
                raise IOError, "received experiment with node/device duplicates"
            devices[node.idx] = node
            # TODO: Add other fields
            msgs.append(wrapper.NodeMsg.instantiate(
                legacy.CORE_API_ADD_FLAG|legacy.CORE_API_STR_FLAG,
                node.idx,
                str(node.name)))
            '''
            for iface in node.interfaces:
                msgs.append(wrapper.IfaceMsg.instantiate(legacy.CORE_API_ADD_FLAG,
                                                         node.idx,
                                                         iface.idx,
                                                         ip4=iface.ip4_addr))
            '''

        for device in message.devices:
            if device.idx in devices:
                raise IOError, "received experiment with node/device duplicates"
            devices[device.idx] = device
            # TODO: Add other fields
            msgs.append(wrapper.NodeMsg.instantiate(
                legacy.CORE_API_ADD_FLAG|legacy.CORE_API_STR_FLAG,
                device.idx,
                str(device.name),
                type = legacy.CORE_NODE_SWITCH)) # TODO: Update this later

        for network in message.networks:
            for channel in network.channels:
                if len(channel.endpoints) == 2:
                    ep0 = channel.endpoints[0]
                    ep1 = channel.endpoints[1]
                    if ep0.dev_idx not in devices or ep1.dev_idx not in devices:
                        raise IOError, "received channel message with invalid first endpoint device (%d)" % (ep0.dev_idx)
                    if ep1.dev_idx not in devices:
                        raise IOError, "received channel message with invalid second endpoint device (%d)" % (ep1.dev_idx)
                    if ep0.intf_idx in devices[ep0.dev_idx].interfaces:
                        raise IOError, "received channel message with invalid first endpoint interface (%d)" % (ep0.intf_idx)
                    if ep1.intf_idx in devices[ep1.dev_idx].interfaces:
                        raise IOError, "received channel message with invalid second endpoint interface (%d)" % (ep1.intf_idx)

                    if0 = devices[ep0.dev_idx].interfaces[ep0.intf_idx]
                    if1 = devices[ep1.dev_idx].interfaces[ep1.intf_idx]
                    
                    msgs.append(wrapper.LinkMsg.instantiate(legacy.CORE_API_ADD_FLAG,
                                                            ep0.dev_idx,ep0.intf_idx,
                                                            ep1.dev_idx,ep1.intf_idx,
                                                            if1ip4=if0.ip4_addr if if0.HasField("ip4_addr") else None, 
                                                            if2ip4=if1.ip4_addr if if1.HasField("ip4_addr") else None))
                                                       
        # send metadata
        # TODO


        # transition to instantiation state
        # TODO
        msgs.append(wrapper.EventMsg.instantiate(legacy.CORE_EVENT_INSTANTIATION_STATE))
        

        return msgs


    @staticmethod
    def translateEvent(event):
        print 'Received event'





