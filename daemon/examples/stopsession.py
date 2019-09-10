#!/usr/bin/env python
# (c)2010-2012 the Boeing Company
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
# List and stop CORE sessions from the command line.
#

import optparse
import socket

from core.api.tlv import coreapi
from core.emulator.enumerations import CORE_API_PORT, MessageFlags, SessionTlvs


def main():
    parser = optparse.OptionParser(usage="usage: %prog [-l] <sessionid>")
    parser.add_option("-l", "--list", dest="list", action="store_true",
                      help="list running sessions")
    (options, args) = parser.parse_args()

    if options.list is True:
        num = '0'
        flags = MessageFlags.STRING.value
    else:
        num = args[0]
        flags = MessageFlags.DELETE.value
    tlvdata = coreapi.CoreSessionTlv.pack(SessionTlvs.NUMBER.value, num)
    message = coreapi.CoreSessionMessage.pack(flags, tlvdata)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', CORE_API_PORT))
    sock.send(message)

    # receive and print a session list
    if options.list is True:
        hdr = sock.recv(coreapi.CoreMessage.header_len)
        msgtype, msgflags, msglen = coreapi.CoreMessage.unpack_header(hdr)
        data = ""
        if msglen:
            data = sock.recv(msglen)
        message = coreapi.CoreMessage(msgflags, hdr, data)
        sessions = message.get_tlv(coreapi.SessionTlvs.NUMBER.value)
        print("sessions: {}".format(sessions))

    sock.close()


if __name__ == "__main__":
    main()
