#!/usr/bin/env python
# protocol.py
#
# Copyright (C) 2007-2008 Francois Aucamp, Meraka Institute, CSIR
# See AUTHORS for all authors and contact information. 
# 
# License: GNU Lesser General Public License, version 3 or later; see COPYING
#          included in this archive for details.
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

from __future__ import absolute_import
from __future__ import print_function
import six
import time
import traceback

from twisted.internet import protocol, defer
from twisted.python import failure

import twisted.internet.reactor
reactor = twisted.internet.reactor

from . import constants  # @UnresolvedImport
from . import encoding  # @UnresolvedImport
from . import msgtypes  # @UnresolvedImport
from . import msgformat  # @UnresolvedImport
from .contact import Contact  # @UnresolvedImport

#------------------------------------------------------------------------------

_Debug = False

#------------------------------------------------------------------------------


class TimeoutError(Exception):
    """
    Raised when a RPC times out.
    """


class KademliaProtocol(protocol.DatagramProtocol):
    """
    Implements all low-level network-related functions of a Kademlia node.
    """
    msgSizeLimit = constants.udpDatagramMaxSize - 26
    maxToSendDelay = 10**-3
    minToSendDelay = 10**-5

    def __init__(self, node, msgEncoder=encoding.Bencode(), msgTranslator=msgformat.DefaultFormat()):
        self._node = node
        self._encoder = msgEncoder
        self._translator = msgTranslator
        self._counter = None
        self._sentMessages = {}
        self._partialMessages = {}
        self._partialMessagesProgress = {}

    def sendRPC(self, contact, method, args, rawResponse=False, **kwargs):
        """
        Sends an RPC to the specified contact.

        @param contact: The contact (remote node) to send the RPC to
        @type contact: kademlia.contacts.Contact
        @param method: The name of remote method to invoke
        @type method: str
        @param args: A list of (non-keyword) arguments to pass to the remote
                    method, in the correct order
        @type args: tuple
        @param rawResponse: If this is set to C{True}, the caller of this RPC
                            will receive a tuple containing the actual response
                            message object and the originating address tuple as
                            a result; in other words, it will not be
                            interpreted by this class. Unless something special
                            needs to be done with the metadata associated with
                            the message, this should remain C{False}.
        @type rawResponse: bool

        @return: This immediately returns a deferred object, which will return
                 the result of the RPC call, or raise the relevant exception
                 if the remote node raised one. If C{rawResponse} is set to
                 C{True}, however, it will always return the actual response
                 message (which may be a C{ResponseMessage} or an
                 C{ErrorMessage}).
        @rtype: twisted.internet.defer.Deferred
        """
        msg = msgtypes.RequestMessage(self._node.id, method, args)
        msgPrimitive = self._translator.toPrimitive(msg)
        encodedMsg = self._encoder.encode(msgPrimitive, encoding='utf-8')

        df = defer.Deferred()
        if rawResponse:
            df._rpcRawResponse = True

        # Transmit the data
        if _Debug:
            print('        <<< [%s] sendRPC' % time.time(), (method, msg.id, contact.address, contact.port))
        if self._counter:
            self._counter('sendRPC')
        # Set the RPC timeout timer
        timeoutCall = reactor.callLater(constants.rpcTimeout * 3, self._msgTimeout, msg.id)  # IGNORE:E1101
        self._sentMessages[msg.id] = (contact.id, df, timeoutCall)
        self._send(encodedMsg, msg.id, (contact.address, contact.port))
        return df

    def dispatch(self, datagram, address):
        if _Debug:
            print('                    datagram of %d bytes to dispatch from %r' % (len(datagram), address))
        msgPrimitive = self._encoder.decode(datagram, encoding='utf-8')
        if _Debug:
            print('                        msgPrimitive: %r' % msgPrimitive)
        message = self._translator.fromPrimitive(msgPrimitive)

        remoteContact = Contact(encoding.to_text(message.nodeID), address[0], address[1], self)
        # Refresh the remote node's details in the local node's k-buckets
        self._node.addContact(remoteContact)

        if _Debug:                                                                                                                                                                                                                                
            print('        >>> [%s] dht.dispatch %r from %r' % (
                time.time(), message.id, address, ))

        if isinstance(message, msgtypes.RequestMessage):
            # This is an RPC method request
            message_request = message.request
            if isinstance(message_request, six.binary_type):
                message_request = message_request.decode()
            self._handleRPC(remoteContact, message.id, message_request, message.args)
            if message.id in self._sentMessages:
                if _Debug:
                    print('                    RPC Request message received [%s]' % message_request)
                # Cancel timeout timer for this RPC
                df, timeoutCall = self._sentMessages[message.id][1:3]
                timeoutCall.cancel()
                del self._sentMessages[message.id]
            else:
                if _Debug:
                    print('                     RPC Request message %r was not identified, currently sent: %r' % (
                        message.id, [k for k in self._sentMessages.keys()], ))

        elif isinstance(message, msgtypes.ResponseMessage):
            message_response = message.response
            if isinstance(message_response, six.binary_type):
                message_response = message_response.decode()
            # Find the message that triggered this response
            if message.id in self._sentMessages:
                # Cancel timeout timer for this RPC
                df, timeoutCall = self._sentMessages[message.id][1:3]
                timeoutCall.cancel()
                del self._sentMessages[message.id]

                if hasattr(df, '_rpcRawResponse'):
                    if _Debug:
                        print('                        respond with tuple (%r, %r)' % (message, address))
                    # The RPC requested that the raw response message and originating address be returned; do not interpret it
                    df.callback((message, address))
                elif isinstance(message, msgtypes.ErrorMessage):
                    # The RPC request raised a remote exception; raise it locally
                    remoteException = None
                    exc_msg = message_response
                    remoteException = Exception(exc_msg)
                    if _Debug:
                        print('                    respond with error "%s"' % exc_msg)
                    df.errback(remoteException)
                else:
                    # We got a result from the RPC
                    if _Debug:
                        print('                    respond with message_response: %r' % message_response)
                    df.callback(message_response)
            else:
                # If the original message isn't found, it must have timed out
                # TODO: we should probably do something with this...
                if _Debug:
                    print('                    message %r was not identified, currently sent: %r' % (
                        message.id, [k for k in self._sentMessages.keys()], ))
        return True

    def datagramReceived(self, datagram, address):
        """
        Handles and parses incoming RPC messages (and responses)

        @note: This is automatically called by Twisted when the protocol
               receives a UDP datagram
        """
        try:
            if _Debug:
                _t = time.time()
            # we must consistently rely on "pagination" logic actually ( or not rely at all )
            # we can't just check those two bytes in the header and say that packet is "paginated"! 
            # what if a small data packet accidentally have those bytes set to \x00 just randomly?
            # so I change the protocol so it will always include such header.
            # if those two bytes are not set - it is a data coming from "late and not updated" node and we must reject it
            header_ok = False
            if datagram[0:1] == b'\x00' and datagram[45:46] == b'\x00':
                header_ok = True
            if not header_ok:
                if _Debug:
                    print('WARNING, dispatching old-style datagram, remote use is running old version')
                self.dispatch(datagram, address)
                return
   
            header = datagram[0:46]
            totalPackets = (ord(encoding.to_text(header[1:2])) << 8) | ord(encoding.to_text(header[2:3]))
            seqNumber = (ord(encoding.to_text(header[3:4])) << 8) | ord(encoding.to_text(header[4:5]))
            msgID = encoding.to_text(header[5:45], encoding='utf-8')
    
            if _Debug:
                print('                        datagramReceived with %d bytes   totalPackets=%d seqNumber=%d msgID=%r from %r' % (
                    len(datagram), totalPackets, seqNumber, msgID, address))
    
            if seqNumber < 0 or seqNumber >= totalPackets:
                if _Debug:
                    print('                            skip, seqNumber with totalPackets')
                return
    
            if msgID not in self._partialMessages:
                self._partialMessages[msgID] = {}
            self._partialMessages[msgID][seqNumber] = datagram[46:]
    
            if len(self._partialMessages[msgID]) < totalPackets:
                if _Debug:
                    print('                            skip, _partialMessages=%r' % self._partialMessages)
                return
    
            keys = sorted(self._partialMessages[msgID].keys())
            data = b''
            for key in keys:
                data += self._partialMessages[msgID][key]
            datagram = data
            if _Debug:
                print('                                finished message of %d pieces: %r' % (totalPackets, keys))
            del self._partialMessages[msgID]
    
            self.dispatch(datagram, address)
        except Exception as exc:
            print(exc)


    def _send(self, data, rpcID, address):
        """
        Transmit the specified data over UDP, breaking it up into several
        packets if necessary.

        If the data is spread over multiple UDP datagrams, the packets have the
        following structure::
            |           |     |      |      |        ||||||||||||   0x00   |
            |Transmision|Total number|Sequence number| RPC ID   |Header end|
            | type ID   | of packets |of this packet |          | indicator|
            | (1 byte)  | (2 bytes)  |  (2 bytes)    |(40 bytes)| (1 byte) |
            |           |     |      |      |        ||||||||||||          |

        @note: The header used for breaking up large data segments will
               possibly be moved out of the KademliaProtocol class in the
               future, into something similar to a message translator/encoder
               class (see C{kademlia.msgformat} and C{kademlia.encoding}).
        """
        if len(data) > self.msgSizeLimit:
            # We have to spread the data over multiple UDP datagrams, and provide sequencing information
            # 1st byte is transmission type id, bytes 2 & 3 are the total number of packets in this transmission,
            # bytes 4 & 5 are the sequence number for this specific packet
            totalPackets = int(len(data) / self.msgSizeLimit)
            if len(data) % self.msgSizeLimit > 0:
                totalPackets += 1
            encTotalPackets = chr(totalPackets >> 8) + chr(totalPackets & 0xff)
            seqNumber = 0
            startPos = 0
            while seqNumber < totalPackets:
                # reactor.iterate() #IGNORE:E1101
                packetData = data[startPos:startPos + self.msgSizeLimit]
                encSeqNumber = chr(seqNumber >> 8) + chr(seqNumber & 0xff)
                # actually we must always pass a header!
                txHeader = encoding.to_bin(encTotalPackets) + encoding.to_bin(encSeqNumber) + encoding.to_bin(rpcID)
                txData = b'\x00' + txHeader + b'\x00' + packetData 
                reactor.callLater(self.maxToSendDelay * seqNumber + self.minToSendDelay, self._write, txData, address)  # IGNORE:E1101
                startPos += self.msgSizeLimit
                seqNumber += 1
        else:
            totalPackets = 1
            encTotalPackets = chr(totalPackets >> 8) + chr(totalPackets & 0xff)
            seqNumber = 0
            encSeqNumber = chr(seqNumber >> 8) + chr(seqNumber & 0xff)
            txHeader = encoding.to_bin(encTotalPackets) + encoding.to_bin(encSeqNumber) + encoding.to_bin(rpcID)
            txData = b'\x00' + txHeader + b'\x00' + data 
            self._write(txData, address)

    def _write(self, data, address):
        if self._counter:
            self._counter('_write')
        try:
            self.transport.write(data, address)
        except Exception as exc:
            if _Debug:
                print('ERROR sending UDP datagram: %r' % exc)
            return False
        if _Debug:
            print('                            dht._write %d bytes to %s' % (len(data), str(address)))
        return True

    def _sendResponse(self, contact, rpcID, response):
        """
        Send a RPC response to the specified contact.
        """
        msg = msgtypes.ResponseMessage(rpcID, self._node.id, response)
        msgPrimitive = self._translator.toPrimitive(msg)
        encodedMsg = self._encoder.encode(msgPrimitive, encoding='utf-8')
        if _Debug:
            print('                    _sendResponse', (contact.address, contact.port), rpcID, response)
        if self._counter:
            self._counter('_sendResponse')
        self._send(encodedMsg, rpcID, (contact.address, contact.port))

    def _sendError(self, contact, rpcID, exceptionType, exceptionMessage):
        """
        Send an RPC error message to the specified contact.
        """
        msg = msgtypes.ErrorMessage(rpcID, self._node.id, exceptionType, exceptionMessage)
        msgPrimitive = self._translator.toPrimitive(msg)
        encodedMsg = self._encoder.encode(msgPrimitive, encoding='utf-8')
        if _Debug:
            print('                    _sendError', (contact.address, contact.port), rpcID, exceptionType, exceptionMessage)
        if self._counter:
            self._counter('_sendError')
        self._send(encodedMsg, rpcID, (contact.address, contact.port))

    def _handleRPC(self, senderContact, rpcID, method, args):
        """
        Executes a local function in response to an RPC request.
        """
        # Set up the deferred callchain
        def handleError(f):
            self._sendError(senderContact, rpcID, f.type, f.getErrorMessage())

        def handleResult(result):
            self._sendResponse(senderContact, rpcID, result)

        df = defer.Deferred()
        df.addCallback(handleResult)
        df.addErrback(handleError)

        if _Debug:
            print('            _handleRPC', rpcID, method, args)

        if self._counter:
            self._counter('_handleRPC')

        # Execute the RPC
        func = getattr(self._node, method, None)

        if callable(func) and hasattr(func, 'rpcmethod'):
            # Call the exposed Node method and return the result to the deferred callback chain
            try:
                try:
                    # Try to pass the sender's node id to the function...
                    result = func(*args, **{'_rpcNodeID': senderContact.id})
                except TypeError:
                    # ...or simply call it if that fails
                    result = func(*args)
            except Exception as e:
                traceback.print_exc()
                df.errback(failure.Failure(e))
            else:
                if _Debug:
                    print('                            result is OK')
                df.callback(result)
        else:
            if _Debug:
                print('                                no such exposed method')
            # No such exposed method
            df.errback(failure.Failure(AttributeError('Invalid method: %s' % method)))

    def _msgTimeout(self, messageID):
        """
        Called when an RPC request message times out.
        """
        if self._counter:
            self._counter('_msgTimeout')
        if _Debug:
            print('               !!! [%s] _msgTimeout' % time.time(), messageID, [k for k in self._sentMessages.keys()], )
        # Find the message that timed out
        if messageID in self._sentMessages:
            remoteContactID, df = self._sentMessages[messageID][0:2]
            if messageID in self._partialMessages:
                # We are still receiving this message
                # See if any progress has been made; if not, kill the message
                if messageID in self._partialMessagesProgress:
                    if len(self._partialMessagesProgress[messageID]) == len(self._partialMessages[messageID]):
                        # No progress has been made
                        del self._partialMessagesProgress[messageID]
                        del self._partialMessages[messageID]
                        df.errback(failure.Failure(TimeoutError(remoteContactID)))
                        return
                # Reset the RPC timeout timer
                timeoutCall = reactor.callLater(constants.rpcTimeout * 3, self._msgTimeout, messageID)  # IGNORE:E1101
                self._sentMessages[messageID] = (remoteContactID, df, timeoutCall)
                if _Debug:
                    print('                    reset timeout for', messageID)
                return
            del self._sentMessages[messageID]
            # The message's destination node is now considered to be dead;
            # raise an (asynchronous) TimeoutError exception and update the host node
            self._node.removeContact(remoteContactID)
            df.errback(failure.Failure(TimeoutError(remoteContactID)))
        else:
            # This should never be reached
            print("ERROR: deferred timed out, but is not present in sent messages list!")
