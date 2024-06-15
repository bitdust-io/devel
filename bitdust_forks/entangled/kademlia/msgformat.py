#!/usr/bin/env python
# msgformat.py
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
from six.moves import range

from . import msgtypes  # @UnresolvedImport


class MessageTranslator(object):
    """
    Interface for RPC message translators/formatters.

    Classes inheriting from this should provide a translation services
    between the classes used internally by this Kademlia implementation
    and the actual data that is transmitted between nodes.
    """
    def fromPrimitive(self, msgPrimitive):
        """
        Create an RPC Message from a message's string representation.

        @param msgPrimitive: The unencoded primitive representation of a message
        @type msgPrimitive: str, int, list or dict

        @return: The translated message object
        @rtype: entangled.kademlia.msgtypes.Message
        """

    def toPrimitive(self, message):
        """
        Create a string representation of a message.

        @param message: The message object
        @type message: msgtypes.Message

        @return: The message's primitive representation in a particular
                 messaging format
        @rtype: str, int, list or dict
        """


class DefaultFormat(MessageTranslator):
    """
    The default on-the-wire message format for this library.
    """
    typeRequest, typeResponse, typeError = list(range(3))
    headerType, headerMsgID, headerNodeID, headerPayload, headerArgs = list(range(5))

    def fromPrimitive(self, msgPrimitive):
        msgType = msgPrimitive[self.headerType]
        if msgType == self.typeRequest:
            msg = msgtypes.RequestMessage(msgPrimitive[self.headerNodeID], msgPrimitive[self.headerPayload], msgPrimitive[self.headerArgs], msgPrimitive[self.headerMsgID])
        elif msgType == self.typeResponse:
            msg = msgtypes.ResponseMessage(msgPrimitive[self.headerMsgID], msgPrimitive[self.headerNodeID], msgPrimitive[self.headerPayload])
        elif msgType == self.typeError:
            msg = msgtypes.ErrorMessage(msgPrimitive[self.headerMsgID], msgPrimitive[self.headerNodeID], msgPrimitive[self.headerPayload], msgPrimitive[self.headerArgs])
        else:
            # Unknown message, no payload
            msg = msgtypes.Message(msgPrimitive[self.headerMsgID], msgPrimitive[self.headerNodeID])
        return msg

    def toPrimitive(self, message):
        msg = {self.headerMsgID: message.id, self.headerNodeID: message.nodeID}
        if isinstance(message, msgtypes.RequestMessage):
            msg[self.headerType] = self.typeRequest
            msg[self.headerPayload] = message.request
            msg[self.headerArgs] = message.args
        elif isinstance(message, msgtypes.ErrorMessage):
            msg[self.headerType] = self.typeError
            msg[self.headerPayload] = message.exceptionType
            msg[self.headerArgs] = message.response
        elif isinstance(message, msgtypes.ResponseMessage):
            msg[self.headerType] = self.typeResponse
            msg[self.headerPayload] = message.response
        return msg


class MultiLayerFormat(MessageTranslator):
    typeRequest, typeResponse, typeError, typeQuestion = list(range(4))
    headerType, headerMsgID, headerNodeID, headerPayload, headerArgs, headerLayer = list(range(6))

    def fromPrimitive(self, msgPrimitive):
        msgType = msgPrimitive[self.headerType]
        if msgType == self.typeRequest:
            layerID = msgPrimitive[self.headerLayer] if self.headerLayer in msgPrimitive else 0
            msg = msgtypes.RequestMessage(msgPrimitive[self.headerNodeID], msgPrimitive[self.headerPayload], msgPrimitive[self.headerArgs], msgPrimitive[self.headerMsgID], layerID=layerID)
        elif msgType == self.typeResponse:
            layerID = msgPrimitive[self.headerLayer] if self.headerLayer in msgPrimitive else 0
            msg = msgtypes.ResponseMessage(msgPrimitive[self.headerMsgID], msgPrimitive[self.headerNodeID], msgPrimitive[self.headerPayload], layerID=layerID)
        elif msgType == self.typeError:
            layerID = msgPrimitive[self.headerLayer] if self.headerLayer in msgPrimitive else 0
            msg = msgtypes.ErrorMessage(msgPrimitive[self.headerMsgID], msgPrimitive[self.headerNodeID], msgPrimitive[self.headerPayload], msgPrimitive[self.headerArgs], layerID=layerID)
        elif msgType == self.typeQuestion:
            layerID = msgPrimitive[self.headerLayer] if self.headerLayer in msgPrimitive else 0
            msg = msgtypes.QuestionMessage(msgPrimitive[self.headerNodeID], msgPrimitive[self.headerPayload], msgPrimitive[self.headerArgs], msgPrimitive[self.headerMsgID], layerID=layerID)
        else:
            # Unknown message, no payload
            msg = msgtypes.Message(msgPrimitive[self.headerMsgID], msgPrimitive[self.headerNodeID])
        return msg

    def toPrimitive(self, message):
        msg = {self.headerMsgID: message.id, self.headerNodeID: message.nodeID}
        if isinstance(message, msgtypes.RequestMessage):
            msg[self.headerType] = self.typeRequest
            msg[self.headerPayload] = message.request
            msg[self.headerArgs] = message.args
            msg[self.headerLayer] = message.layerID
        elif isinstance(message, msgtypes.ErrorMessage):
            msg[self.headerType] = self.typeError
            msg[self.headerPayload] = message.exceptionType
            msg[self.headerArgs] = message.response
            msg[self.headerLayer] = message.layerID
        elif isinstance(message, msgtypes.ResponseMessage):
            msg[self.headerType] = self.typeResponse
            msg[self.headerPayload] = message.response
            msg[self.headerLayer] = message.layerID
        elif isinstance(message, msgtypes.QuestionMessage):
            msg[self.headerType] = self.typeQuestion
            msg[self.headerPayload] = message.request
            msg[self.headerArgs] = message.args
            msg[self.headerLayer] = message.layerID
        return msg
