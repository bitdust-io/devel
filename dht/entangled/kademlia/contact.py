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
import base64


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
        return '%s [%s] at <%s:%d>' % (
            self.__class__.__name__, base64.b64encode(self.id), self.address, self.port)

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
#        import sys, os
#        cod = sys._getframe().f_back.f_code
#        modul = os.path.basename(cod.co_filename).replace('.py', '')
#        caller = cod.co_name
#        print 'contact.__getattr__ from %s.%s' % (modul, caller)
        def _sendRPC(*args, **kwargs):
            #            print 'sendRPC', name, self.address, self.port, self.commTime
            return self._networkProtocol.sendRPC(self, name, args, **kwargs)
        return _sendRPC
