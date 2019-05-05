#!/usr/bin/python
# network_transport.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (network_transport.py) is part of BitDust Software.
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
#
#
#

"""
.. module:: network_transport.

.. role:: red
BitDust network_transport() Automat


EVENTS:
    * :red:`failed`
    * :red:`init`
    * :red:`receiving-started`
    * :red:`restart`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`stopped`
    * :red:`transport-initialized`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import platform

from twisted.internet.defer import fail

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import misc
from lib import nameurl
from lib import strng

from userid import my_id

from main import settings

from transport import gateway

#------------------------------------------------------------------------------


class NetworkTransport(automat.Automat):
    """
    This class implements all the functionality of the ``network_transport()``
    state machine.
    """

    fast = True

    def __init__(self, proto, interface, state_changed_callback=None):
        self.proto = strng.to_text(proto)
        self.host = None
        self.interface = interface
        self.state_changed_callback = None
        self.options = {}
        automat.Automat.__init__(
            self,
            name='%s_transport' % proto,
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )

    def call(self, method_name, *args):
        method = getattr(self.interface, method_name, None)
        if method is None:
            lg.err('method %s not found in %r transport' % (method_name, self.proto))
            return fail(Exception('Method %s not found in the transport %s interface' % (method_name, self.proto)))
        return method(*args)

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when automat's state were
        changed.
        """
        if self.state_changed_callback:
            self.state_changed_callback(self, oldstate, newstate)
        gateway.on_transport_state_changed(self, oldstate, newstate)

    def state_not_changed(self, curstate, event_string, *args, **kwargs):
        """
        A small hack to catch all events after "verify" processing.
        """
        if self.state_changed_callback:
            self.state_changed_callback(self, curstate, curstate)
        gateway.on_transport_state_changed(self, curstate, curstate)

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'INIT'
                self.StartNow = False
                self.StopNow = False
                self.doInit(*args, **kwargs)
        #---STARTING---
        elif self.state == 'STARTING':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'failed':
                self.state = 'OFFLINE'
            elif event == 'receiving-started' and not self.StopNow:
                self.state = 'LISTENING'
                self.doSaveOptions(*args, **kwargs)
            elif event == 'stop':
                self.StopNow = True
            elif event == 'receiving-started' and self.StopNow:
                self.state = 'STOPPING'
                self.StopNow = False
                self.doStop(*args, **kwargs)
            elif event == 'restart':
                self.StopNow = True
                self.StartNow = True
        #---LISTENING---
        elif self.state == 'LISTENING':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStop(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stop':
                self.state = 'STOPPING'
                self.StopNow = False
                self.doStop(*args, **kwargs)
            elif event == 'restart':
                self.state = 'STOPPING'
                self.StopNow = False
                self.StartNow = True
                self.doStop(*args, **kwargs)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'start' or event == 'restart':
                self.state = 'STARTING'
                self.StopNow = False
                self.StartNow = False
                self.doStart(*args, **kwargs)
        #---STOPPING---
        elif self.state == 'STOPPING':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'stopped' and not self.StartNow:
                self.state = 'OFFLINE'
            elif event == 'stopped' and self.StartNow:
                self.state = 'STARTING'
                self.StartNow = False
                self.doStart(*args, **kwargs)
            elif event == 'start' or event == 'restart':
                self.StartNow = True
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---INIT---
        elif self.state == 'INIT':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'transport-initialized' and self.StartNow:
                self.state = 'STARTING'
                self.doCreateProxy(*args, **kwargs)
                self.StartNow = False
                self.doStart(*args, **kwargs)
            elif event == 'transport-initialized' and not self.StartNow:
                self.state = 'OFFLINE'
                self.doCreateProxy(*args, **kwargs)
            elif event == 'start' or event == 'restart':
                self.StartNow = True
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(8, 'network_transport.doInit : %s' % str(*args, **kwargs))
        gateway.attach(self)
        try:
            listener, state_changed_callback = args[0]
        except:
            listener, state_changed_callback = args[0], None
        self.state_changed_callback = state_changed_callback
        self.interface.init(listener)

    def doStart(self, *args, **kwargs):
        """
        Action method.
        """
        options = {'idurl': my_id.getLocalID(), }
        id_contact = ''
        default_host = ''
#         ident = my_id.getLocalIdentity()
#         if ident:
#             id_contact = ident.getContactsByProto().get(self.proto, '')
#         if id_contact:
#             assert id_contact.startswith(self.proto + '://')
#             id_contact = id_contact.lstrip(self.proto + '://')
        if self.proto == 'tcp':
            if not id_contact:
                default_host = strng.to_bin(misc.readExternalIP()) + b':' + strng.to_bin(str(settings.getTCPPort()))
            options['host'] = id_contact or default_host
            options['tcp_port'] = settings.getTCPPort()
        elif self.proto == 'udp':
            if not id_contact:
                default_host = strng.to_bin(nameurl.GetName(my_id.getLocalID())) + b'@' + strng.to_bin(platform.node())
            options['host'] = id_contact or default_host
            options['dht_port'] = settings.getDHTPort()
            options['udp_port'] = settings.getUDPPort()
        elif self.proto == 'proxy':
            pass
        elif self.proto == 'http':
            if not id_contact:
                default_host = strng.to_bin(misc.readExternalIP()) + b':' + strng.to_bin(str(settings.getHTTPPort()))
            options['host'] = id_contact or default_host
            options['http_port'] = settings.getHTTPPort()
        if _Debug:
            lg.out(8, 'network_transport.doStart connecting %s transport : %s' % (self.proto.upper(), options))
        self.interface.connect(options)

    def doStop(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(8, 'network_transport.doStop disconnecting %s transport' % (self.proto.upper()))
        self.interface.disconnect()

    def doCreateProxy(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0]:
            self.interface.create_proxy(args[0])

    def doSaveOptions(self, *args, **kwargs):
        """
        Action method.
        """
        proto, self.host, self.options = args[0]
        proto = strng.to_text(proto)
        if proto != self.proto:
            lg.warn('wrong protocol: %r' % proto)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        # gateway.transports().pop(self.proto)
        self.interface.shutdown()
        self.destroy()
        self.interface = None
        gateway.detach(self)
