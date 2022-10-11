#!/usr/bin/env python
# msgtypes.py
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
import six

import hashlib
import random

from . import encoding  # @UnresolvedImport


class Message(object):
    """ Base class for messages - all "unknown" messages use this class """
    def __init__(self, rpcID, nodeID):
        self.id = encoding.to_text(rpcID)
        self.nodeID = encoding.to_text(nodeID)

    def __repr__(self, *args, **kwargs):
        return str(self)


class RequestMessage(Message):
    """
    Message containing an RPC request.
    """
    def __init__(self, nodeID, method, methodArgs, rpcID=None, layerID=0):
        if rpcID is None:
            hsh = hashlib.sha1()
            hsh.update(str(random.getrandbits(255)).encode())
            rpcID = hsh.hexdigest()
        Message.__init__(self, rpcID, nodeID)
        self.request = method
        self.args = methodArgs
        self.layerID = layerID

    def __str__(self):
        return '<RequestMessage(%d) %s %s with %r>' % (self.layerID, self.id[:6], self.nodeID[:6], self.args)


class QuestionMessage(Message):
    """
    Message containing an RPC request from a node which do not want to be included in DHT layer.
    """
    def __init__(self, nodeID, method, methodArgs, rpcID=None, layerID=0):
        if rpcID is None:
            hsh = hashlib.sha1()
            hsh.update(str(random.getrandbits(255)).encode())
            rpcID = hsh.hexdigest()
        Message.__init__(self, rpcID, nodeID)
        self.request = method
        self.args = methodArgs
        self.layerID = layerID

    def __str__(self):
        return '<QuestionMessage(%d) %s %s with %r>' % (self.layerID, self.id[:6], self.nodeID[:6], self.args)


class ResponseMessage(Message):
    """
    Message containing the result from a successful RPC request.
    """
    def __init__(self, rpcID, nodeID, response, layerID=0):
        Message.__init__(self, rpcID, nodeID)
        self.response = response
        self.layerID = layerID

    def __str__(self):
        return '<ResponseMessage(%d) %s %s with %r>' % (self.layerID, self.id[:6], self.nodeID[:6], self.response)


class ErrorMessage(ResponseMessage):
    """
    Message containing the error from an unsuccessful RPC request.
    """
    def __init__(self, rpcID, nodeID, exceptionType, errorMessage, layerID=0):
        ResponseMessage.__init__(self, rpcID, nodeID, errorMessage, layerID=layerID)
        if isinstance(exceptionType, type):
            self.exceptionType = '%s.%s' % (exceptionType.__module__, exceptionType.__name__)
        else:
            self.exceptionType = exceptionType
            if isinstance(self.exceptionType, six.binary_type):
                self.exceptionType = self.exceptionType.decode()

    def __str__(self):
        return '<ErrorMessage(%d) %s %s with %r>' % (self.layerID, self.id[:6], self.nodeID[:6], self.exceptionType)
