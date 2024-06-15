#!/usr/bin/env python
# contact.py
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

import six

_Debug = False


class Contact(object):
    """
    Encapsulation for remote contact.

    This class contains information on a single remote contact, and also
    provides a direct RPC API to the remote node which it represents
    """
    def __init__(self, id, ipAddress, udpPort, networkProtocol, firstComm=0):
        self.id = id
        self.address = ipAddress
        self.port = udpPort
        self._networkProtocol = networkProtocol
        self.commTime = firstComm

    def __eq__(self, other):
        if isinstance(other, Contact):
            return self.id == other.id
        elif isinstance(other, six.string_types):
            return self.id == other
        else:
            return False

    def __ne__(self, other):
        if isinstance(other, Contact):
            return self.id != other.id
        elif isinstance(other, six.string_types):
            return self.id != other
        else:
            return True

    def __repr__(self, *args, **kwargs):
        return str(self)

    def __str__(self):
        return '<%s at %r:%d>' % (self.id[:6], self.address, self.port)

    def __getattr__(self, name):
        """
        This override allows the host node to call a method of the remote node
        (i.e. this contact) as if it was a local function.

        For instance, if C{remoteNode} is a instance of C{Contact}, the
        following will result in C{remoteNode}'s C{test()} method to be
        called with argument C{123}::
         remoteNode.test(123)

        Such a RPC method call will return a Deferred, which will callback
        when the contact responds with the result (or an error occurs).
        This happens via this contact's C{_networkProtocol} object (i.e. the
        host Node's C{_protocol} object).
        """
        def _sendRPC(*args, **kwargs):
            return self._networkProtocol.sendRPC(self, name, args, **kwargs)

        return _sendRPC


class LayeredContact(Contact):
    def __init__(self, id, ipAddress, udpPort, networkProtocol, firstComm=0, layerID=0):
        self.layerID = layerID
        super(LayeredContact, self).__init__(id, ipAddress, udpPort, networkProtocol, firstComm)

    def __str__(self):
        return '<Contact(%d) %s at %r:%d>' % (self.layerID, self.id[:6], self.address, self.port)

    def __getattr__(self, name):
        def _sendRPC(*args, **kwargs):
            kwargs['layerID'] = self.layerID
            if _Debug:
                print('[DHT CONTACT]: %r sending RPC %r args=%r kwargs=%r' % (self, name, args, kwargs))
            ret = self._networkProtocol.sendRPC(self, name, args, **kwargs)
            if _Debug:
                print('[DHT CONTACT]: %r RPC result is %r' % (self, ret))
            return ret

        return _sendRPC
