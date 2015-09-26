#!/usr/bin/python
#network_transport.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: network_transport
.. role:: red
BitDust network_transport() Automat


EVENTS:
    * :red:`failed`
    * :red:`init`
    * :red:`receiving-started`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`stopped`
    * :red:`transport-initialized`
"""

import platform

from twisted.internet.defer import fail

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat

from system import bpio

from lib import misc
from lib import nameurl

from userid import my_id

from main import settings

import gateway 

#------------------------------------------------------------------------------ 

class NetworkTransport(automat.Automat):
    """
    This class implements all the functionality of the ``network_transport()`` state machine.
    """
    
    fast = True

    def __init__(self, proto, interface, state_changed_callback=None):
        self.proto = proto
        self.interface = interface
        self.state_changed_callback = None
        automat.Automat.__init__(self, '%s_transport' % proto, 'AT_STARTUP', 8, True)
        
    def call(self, method_name, *args):
        method = getattr(self.interface, method_name, None)
        if method is None:
            lg.out(2, 'network_transport.call ERROR method %s not found in protos' % (method_name, self.proto))
            return fail(Exception('Method %s not found in the transport %s interface' % (method_name, self.proto)))
        return method(*args)

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """

    def state_changed(self, oldstate, newstate, event, arg):
        """
        This method intended to catch the moment when automat's state were changed.
        """
        if self.state_changed_callback:
            self.state_changed_callback(self, oldstate, newstate)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'INIT'
                self.StartNow=False
                self.StopNow=False
                self.doInit(arg)
        #---STARTING---
        elif self.state == 'STARTING':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'failed' :
                self.state = 'OFFLINE'
            elif event == 'receiving-started' and not self.StopNow :
                self.state = 'LISTENING'
            elif event == 'stop' :
                self.StopNow=True
            elif event == 'receiving-started' and self.StopNow :
                self.state = 'STOPPING'
                self.StopNow=False
                self.doStop(arg)
        #---LISTENING---
        elif self.state == 'LISTENING':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doStop(arg)
                self.doDestroyMe(arg)
            elif event == 'stop' :
                self.state = 'STOPPING'
                self.StopNow=False
                self.doStop(arg)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start' :
                self.state = 'STARTING'
                self.StartNow=False
                self.doStart(arg)
        #---STOPPING---
        elif self.state == 'STOPPING':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stopped' and not self.StartNow :
                self.state = 'OFFLINE'
            elif event == 'start' :
                self.StartNow=True
            elif event == 'stopped' and self.StartNow :
                self.state = 'STARTING'
                self.StartNow=False
                self.doStart(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---INIT---
        elif self.state == 'INIT':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start' :
                self.StartNow=True
            elif event == 'transport-initialized' and self.StartNow :
                self.state = 'STARTING'
                self.doCreateProxy(arg)
                self.StartNow=False
                self.doStart(arg)
            elif event == 'transport-initialized' and not self.StartNow :
                self.state = 'OFFLINE'
                self.doCreateProxy(arg)
        return None

    def doInit(self, arg):
        """
        Action method.
        """
        gateway.attach(self)
        try:
            listener, state_changed_callback = arg
        except:
            listener, state_changed_callback = arg, None
        self.state_changed_callback = state_changed_callback
        self.interface.init(listener)

    def doStart(self, arg):
        """
        Action method.
        """
        options = { 'idurl': my_id.getLocalID(),}
        id_contact = ''
        default_host = ''
        ident = my_id.getLocalIdentity()
        if ident:
            id_contact = ident.getContactsByProto().get(self.proto, '')
        if id_contact:
            assert id_contact.startswith(self.proto+'://')
            id_contact = id_contact.strip(self.proto+'://')
        if self.proto == 'tcp':
            if not id_contact:
                default_host = bpio.ReadTextFile(settings.ExternalIPFilename())+':'+str(settings.getTCPPort())
            options['host'] = id_contact or default_host
            options['tcp_port'] = settings.getTCPPort()
        elif self.proto == 'udp':
            if not id_contact:
                default_host = nameurl.GetName(my_id.getLocalID())+'@'+platform.node()
            options['host'] = id_contact or default_host
            options['dht_port'] = settings.getDHTPort()
            options['udp_port'] = settings.getUDPPort()
        elif self.proto == 'proxy':
            if not id_contact:
                default_host = nameurl.GetName(my_id.getLocalID())+'@'+platform.node()
            options['host'] = id_contact or default_host
        self.interface.connect(options) 

    def doStop(self, arg):
        """
        Action method.
        """
        lg.out(12, 'network_transport.doStop disconnecting %r' % self.interface)
        self.interface.disconnect()

    def doCreateProxy(self, arg):
        """
        Action method.
        """
        if arg:
            self.interface.create_proxy(arg)

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        # gateway.transports().pop(self.proto)
        self.interface.shutdown()
        self.destroy()
        self.interface = None
        gateway.detach(self)


