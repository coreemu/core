#
# CORE
# Copyright (c)2016 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Rod Santiago
#          John Kharouta
#

"""
This is a convenience module that imports the python module generated 
from the core.proto IDL
"""

from core_pb2 import *
import struct


API2HDRFMT = "H"
API2HDRSIZ = struct.calcsize(API2HDRFMT)
   
def pack(message):
    ''' Pack an API2 message for transmission
    '''
    data = message.SerializeToString()
    return struct.pack(API2HDRFMT, len(data)) + data


def recvAndUnpack(recv):
    ''' Receive and unpack from coreapi2
    '''

    try:
        hdr = recv(API2HDRSIZ)
    except Exception, e:
        raise IOError, "error receiving API 2 header (%s)" % e

    if len(hdr) != API2HDRSIZ:
        if len(hdr) == 0:
            raise EOFError, "client disconnected"
        else:            
            raise IOError, "invalid message header size"
                
    dataToRead = struct.unpack(API2HDRFMT, hdr)[0]
    data = ""
    while len(data) < dataToRead:
        data += recv(dataToRead - len(data))
    return data


def findNodeByIdx(exp, idx):
    ''' Find a node with the given index in the given Experiment
    '''
    for a_node in exp.nodes:
        if a_node.idx == idx:
            return a_node
    return None

def findDeviceByIdx(exp, idx):
    ''' Find a device with the given index in the given Experiment
    '''
    for a_dev in exp.devices:
        if a_dev.idx == idx:
            return a_dev
    return None

def getNodeByIdx(exp, idx):
    node = findNodeByIdx(exp, idx)
    if not node:
        node = exp.nodes.add()
    return node

def getDeviceByIdx(exp, idx):
    device = findDeviceByIdx(exp, idx)
    if not device:
        device = exp.devices.add()
    return device



