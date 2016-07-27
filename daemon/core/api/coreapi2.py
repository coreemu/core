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
from core.api.coreapi import *

class CoreMessage(object):
    hdrfmt = "H"
    hdrsiz = struct.calcsize(hdrfmt)


    @staticmethod
    def toLegacyApi(data):
        message = core_pb2.CoreMessage()
        message.ParseFromString(data)
        if message.HasField('session'):
            return CoreMessage.translateSessionMsg(message.session)
        if message.HasField('experiment'):
            return CoreMessage.translateExperimentMsg(message.experiment)
        if message.HasField('event'):
            return CoreMessage.translateEvent(message.event)
            
    @staticmethod
    def toApi2(messages):
        for msg in messages:
            msgtype, msgflags, msglen = coreapi.CoreMessage.unpackhdr(msg)
            data = msg[coreapi.CoreMessage.hdrsiz:]
            if msgtype == coreapi.CORE_API_REG_MSG:
                pass
            elif msgtype == coreapi.CORE_API_SESS_MSG:
                
            

    @staticmethod
    def translateSessionMsg(message):
        print 'Received session request message'
        msgs = []
        msgs.append(CoreMessage.createRegisterMessage(0, gui='true'))
        return msgs



    @staticmethod
    def translateExperimentMsg(message):
        print 'Received experiment message'


    @staticmethod
    def translateEvent(event):
        print 'Received event'



    @staticmethod
    def createRegisterMessage(flags, wireless=None, mobility=None, utility=None, execsrv=None, 
                            gui=None, emulsrv=None, session=None):
        tlvdata = ""
        if wireless is not None:
            tlvdata = tlvdata + CoreRegTlv.pack(CORE_TLV_REG_WIRELESS,wireless)
        if mobility is not None:
            tlvdata = tlvdata + CoreRegTlv.pack(CORE_TLV_REG_MOBILITY,mobility)
        if utility is not None:
            tlvdata = tlvdata + CoreRegTlv.pack(CORE_TLV_REG_UTILITY,utility)
        if execsrv is not None:
            tlvdata = tlvdata + CoreRegTlv.pack(CORE_TLV_REG_EXECSRV,execsrv)
        if gui is not None:
            tlvdata = tlvdata + CoreRegTlv.pack(CORE_TLV_REG_GUI,gui)
        if emulsrv is not None:
            tlvdata = tlvdata + CoreRegTlv.pack(CORE_TLV_REG_EMULSRV,emulsrv)
        if session is not None:
            tlvdata = tlvdata + CoreRegTlv.pack(CORE_TLV_REG_SESSION,session)
        hdr = struct.pack(CoreRegMessage.hdrfmt, CoreRegMessage.msgtype, flags, len(tlvdata))
        return CoreRegMessage(flags, hdr, tlvdata)
