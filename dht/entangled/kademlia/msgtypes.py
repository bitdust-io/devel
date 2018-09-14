#!/usr/bin/env python
# msgtypes.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (msgtypes.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

from __future__ import absolute_import
import hashlib
import random


class Message(object):
    """ Base class for messages - all "unknown" messages use this class """

    def __init__(self, rpcID, nodeID):
        self.id = rpcID
        self.nodeID = nodeID


class RequestMessage(Message):
    """
    Message containing an RPC request.
    """

    def __init__(self, nodeID, method, methodArgs, rpcID=None):
        if rpcID is None:
            hash = hashlib.sha1()
            hash.update(str(random.getrandbits(255)))
            rpcID = hash.digest()
        Message.__init__(self, rpcID, nodeID)
        self.request = method
        self.args = methodArgs


class ResponseMessage(Message):
    """
    Message containing the result from a successful RPC request.
    """

    def __init__(self, rpcID, nodeID, response):
        Message.__init__(self, rpcID, nodeID)
        self.response = response


class ErrorMessage(ResponseMessage):
    """
    Message containing the error from an unsuccessful RPC request.
    """

    def __init__(self, rpcID, nodeID, exceptionType, errorMessage):
        ResponseMessage.__init__(self, rpcID, nodeID, errorMessage)
        if isinstance(exceptionType, type):
            self.exceptionType = '%s.%s' % (exceptionType.__module__, exceptionType.__name__)
        else:
            self.exceptionType = exceptionType
