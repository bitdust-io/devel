

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
    * :red:`outbox-packet`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 18

#------------------------------------------------------------------------------ 

import os


from automats import automat

from logs import lg

from system import tmpfile

from lib import packetid
from lib import nameurl

from crypt import encrypted
from crypt import key
from crypt import signed

from p2p import commands

from userid import my_id

from transport import gateway 
from transport import callback

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
        _ProxySender = ProxySender('proxy_sender', 'AT_STARTUP', _DebugLevel, _Debug)
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
            if event == 'outbox-packet' :
                self.doEncryptAndSendToProxyRouter(arg)
            elif event == 'stop' :
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

    def doEncryptAndSendToProxyRouter(self, arg):
        """
        Action method.
        """
        import proxy_receiver
        router_idurl = proxy_receiver.GetRouterIDURL()
        router_identity_obj = proxy_receiver.GetRouterIdentity()
        router_proto_host = proxy_receiver.GetRouterProtoHost()
        if not router_idurl or not router_proto_host or not router_identity_obj:
            if _Debug:
                lg.warn('proxy router is not configured yet')
            return
        outpacket, wide, callbacks = arg
        router_proto, router_host = router_proto_host
        publickey = router_identity_obj.publickey
        src = ''
        src += my_id.getLocalID() + '\n'
        src += outpacket.RemoteID + '\n'
        src += 'wide\n' if wide else '\n' 
        src += outpacket.Serialize()
        block = encrypted.Block(
            my_id.getLocalID(),
            'routed outgoing data',
            0,
            key.NewSessionKey(),
            key.SessionKeyType(),
            True,
            src,
            EncryptFunc=lambda inp: key.EncryptStringPK(publickey, inp))
        newpacket = signed.Packet(
            commands.Data(), 
            outpacket.OwnerID,
            my_id.getLocalID(), 
            'routed_out_'+outpacket.PacketID, 
            block.Serialize(), 
            router_idurl)
        fileno, filename = tmpfile.make('proxy-out')
        packetdata = newpacket.Serialize()
        os.write(fileno, packetdata)
        os.close(fileno)
        result = gateway.send_file(router_idurl, 
                          router_proto, 
                          router_host, 
                          filename, 
                          'Routed packet for %s' % outpacket.RemoteID)
        if _Debug:
            lg.out(_DebugLevel-8, '<<< ROUTED-OUT <<< %s' % str(outpacket))
            lg.out(_DebugLevel-8, '                   sent on %s://%s with %d bytes' % (
                router_proto, router_host, len(packetdata)))
        del src
        del block
        del newpacket
        del outpacket
        del router_identity_obj
        del router_idurl
        del router_proto_host

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
        # if _Debug:
            # lg.out(8, 'proxy_sender._on_outbox_packet filtering %s' % (outpacket))
        import proxy_receiver
        router_idurl = proxy_receiver.GetRouterIDURL()
        if not router_idurl:
            # if _Debug:
                # lg.out(8, '        proxy_receiver() is not yet found a router')
            return None
        if outpacket.RemoteID == router_idurl:
            # if _Debug:
                # lg.out(8, '        outpacket is addressed for router and must be sent in a usual way')
            return None
        if _Debug:
            lg.out(_DebugLevel, 'proxy_sender._on_outbox_packet   %s were redirected for %s' % (outpacket, router_idurl))
        self.automat('outbox-packet', (outpacket, wide, callbacks))
        return True
        # return packet_out.create(outpacket, wide, callbacks, target=router_idurl)



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
        

    
#------------------------------------------------------------------------------ 


def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    main()

