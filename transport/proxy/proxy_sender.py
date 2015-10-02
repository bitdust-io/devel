

"""
.. module:: proxy_sender
.. role:: red

BitDust proxy_sender(at_startup) Automat

.. raw:: html

    <a href="proxy_sender.png" target="_blank">
    <img src="proxy_sender.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`init`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------ 

_Debug = True

#------------------------------------------------------------------------------ 

import time

from automats import automat

from logs import lg

from system import bpio

from crypt import encrypted
from crypt import key
from crypt import signed

from p2p import commands

from userid import my_id

from transport import gateway 
from transport import callback
from transport import packet_out

import proxy_interface
import proxy_receiver

#------------------------------------------------------------------------------ 

_ProxySender = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with proxy_sender machine.
    """
    global _ProxySender
    if _ProxySender is None:
        # set automat name and starting state here
        _ProxySender = ProxySender('proxy_sender', 'AT_STARTUP')
    if event is not None:
        _ProxySender.automat(event, arg)
    return _ProxySender

#------------------------------------------------------------------------------ 

class ProxySender(automat.Automat):
    """
    This class implements all the functionality of the ``proxy_sender()`` state machine.
    """

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of proxy_sender machine.
        """

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when proxy_sender state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the proxy_sender
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://code.google.com/p/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'STOPPED'
                self.doInit(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---REDIRECTING---
        elif self.state == 'REDIRECTING':
            if event == 'stop' :
                self.state = 'STOPPED'
                self.doStop(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doStop(arg)
                self.doDestroyMe(arg)
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'start' :
                self.state = 'REDIRECTING'
                self.doStart(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        return None

    def doInit(self, arg):
        """
        Action method.
        """

    def doStart(self, arg):
        """
        Action method.
        """
        callback.insert_outbox_filter_callback(-1, self._on_outbox_packet)

    def doStop(self, arg):
        """
        Action method.
        """
        callback.remove_finish_file_sending_callback(self._on_outbox_packet)

#    def doRegisterOutboxFile(self, arg):
#        """
#        Action method.
#        """
#        remote_idurl, filename, host, description, single = arg
#        if not single:
#            d = proxy_interface.interface_register_file_sending(
#                host, remote_idurl, filename, description)
#            d.addCallback(self._on_outbox_file_registered, remote_idurl, filename, host, description)
#            d.addErrback(self._on_outbox_file_register_failed, remote_idurl, filename, host, description)
        
#    def doEncryptAndSendOutboxPacket(self, arg):
#        """
#        Action method.
#        """
#        try:
#            remote_idurl, filename, host, description, single = arg
#            router_name, router_host = host.split('@')
#            router_idurl = 'http://%s/%s.xml' % (router_host, router_name)
#        except:
#            lg.exc()
#            return
#        src = my_id.getLocalID() + '\n' + remote_idurl + '\n' + bpio.ReadBinaryFile(filename)
#        block = encrypted.Block(
#            my_id.getLocalID(),
#            'routed data',
#            0,
#            key.NewSessionKey(),
#            key.SessionKeyType(),
#            True,
#            src,)
#        newpacket = signed.Packet(
#            commands.Data(), 
#            router_idurl, 
#            my_id.getLocalID(),
#            'routed_packet', 
#            block.Serialize(), 
#            router_idurl)
#        gateway.outbox(newpacket, callbacks={
#            commands.Ack(): self._on_outbox_packet_acked,
#            commands.Fail(): self._on_outbox_packet_failed}) 
#        del src
#        del block
#        del newpacket
#        lg.out(12, 'proxy_sender.doSendOutboxPacket for %s routed via %s' % (remote_idurl, router_idurl))

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        automat.objects().pop(self.index)
        global _ProxySender
        del _ProxySender
        _ProxySender = None
        
    def _on_outbox_packet(self, outpacket, wide, callbacks):
        """
        """
        router_idurl = proxy_receiver.GetRouterIDURL()
        if not router_idurl:
            return None
        if outpacket.RemoteID != router_idurl:
            return None
        if _Debug:
            lg.out(8, 'proxy_sender._on_outbox_packet %s were redirected to %s' % (outpacket, router_idurl))
        return packet_out.create(outpacket, wide, callbacks, target=router_idurl)

#    def _on_outbox_file_registered(self, remote_idurl, filename, host, description):
#        """
#        """
#        lg.out(12, 'proxy_sender._on_outbox_file_registered')
        
#    def _on_outbox_packet_acked(self, newpacket, info):
#        """
#        """
#        lg.out(12, 'proxy_sender._on_outbox_packet_acked')
        
#    def _on_outbox_packet_failed(self, remote_id, packet_id, why):
#        """
#        """
#        lg.out(12, 'proxy_sender._on_outbox_packet_failed')
    
#------------------------------------------------------------------------------ 

def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    main()

