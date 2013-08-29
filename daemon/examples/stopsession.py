#!/usr/bin/env python
# (c)2010-2012 the Boeing Company
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
# List and stop CORE sessions from the command line.
#

import socket, optparse
from core.constants import *
from core.api import coreapi

def main():
    parser = optparse.OptionParser(usage = "usage: %prog [-l] <sessionid>")
    parser.add_option("-l", "--list", dest = "list", action = "store_true",
                      help = "list running sessions")
    (options, args) = parser.parse_args()

    if options.list is True:
        num = '0'
        flags = coreapi.CORE_API_STR_FLAG
    else:
        num = args[0]
        flags = coreapi.CORE_API_DEL_FLAG
    tlvdata = coreapi.CoreSessionTlv.pack(coreapi.CORE_TLV_SESS_NUMBER, num)
    msg = coreapi.CoreSessionMessage.pack(flags, tlvdata)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', coreapi.CORE_API_PORT))
    sock.send(msg)

    # receive and print a session list
    if options.list is True:
        hdr = sock.recv(coreapi.CoreMessage.hdrsiz)
        msgtype, msgflags, msglen = coreapi.CoreMessage.unpackhdr(hdr)
        data = ""
        if msglen:
            data = sock.recv(msglen)
        msg = coreapi.CoreMessage(msgflags, hdr, data)
        sessions = msg.gettlv(coreapi.CORE_TLV_SESS_NUMBER)
        print "sessions:",  sessions

    sock.close()

if __name__ == "__main__":
    main()
