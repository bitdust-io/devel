

"""
.. module:: proxy_router
.. role:: red

BitDust proxy_router() Automat

.. raw:: html

    <a href="proxy_router.png" target="_blank">
    <img src="proxy_router.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`all-transports-ready`
    * :red:`cancel-route`
    * :red:`init`
    * :red:`request-route`
    * :red:`routed-connection-lost`
    * :red:`routed-inbox-packet-received`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
    * :red:`timeout`
"""



import os
import sys
import time
import cStringIO

from twisted.internet import reactor

try:
    from logs import lg
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))

from automats import automat

from crypt import encrypted
from crypt import key
from crypt import signed

from transport import gateway

from system import tmpfile

#------------------------------------------------------------------------------ 

_ProxyRouter = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with proxy_router() machine.
    """
    global _ProxyRouter
    if _ProxyRouter is None:
        # set automat name and starting state here
        _ProxyRouter = ProxyRouter('proxy_router', 'AT_STARTUP', 2, True)
    if event is not None:
        _ProxyRouter.automat(event, arg)
    return _ProxyRouter

#------------------------------------------------------------------------------ 

class ProxyRouter(automat.Automat):
    """
    This class implements all the functionality of the ``proxy_router()`` state machine.
    """

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of proxy_router() machine.
        """
        self.routes = {}

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when proxy_router() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the proxy_router()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://code.google.com/p/visio2python/>`_ tool.
        """
        #---LISTEN---
        if self.state == 'LISTEN':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop' :
                self.state = 'STOPPED'
                self.doUnregisterAllRouts(arg)
            elif event == 'request-route' or event == 'cancel-route' :
                self.doProcessRequest(arg)
            elif event == 'routed-inbox-packet-received' :
                self.doForwardRoutedPacket(arg)
            elif event == 'routed-connection-lost' :
                self.doUnRegisterRoute(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'STOPPED'
                self.doInit(arg)
        #---TRANSPORTS?---
        elif self.state == 'TRANSPORTS?':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'stop' or event == 'timeout' :
                self.state = 'STOPPED'
            elif event == 'all-transports-ready' :
                self.state = 'LISTEN'
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'start' :
                self.state = 'TRANSPORTS?'
                self.doWaitOtherTransports(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass


    def doInit(self, arg):
        """
        Action method.
        """
        from transport import gateway
        from transport import callback
        self.starting_transports = []
        # callback.add_inbox_callback(self._on_inbox_packet_received)
        gateway.add_transport_state_changed_callback(self._on_transport_state_changed)

    def doWaitOtherTransports(self, arg):
        """
        Action method.
        """
        from transport import gateway
        self.starting_transports = []
        for t in gateway.transports().values():
            if t.proto == 'proxy':
                continue
            if t.state == 'STARTING':
                self.starting_transports.append(t.proto)
        lg.out(12, 'proxy_router.doWaitOtherTransports : %s' % str(self.starting_transports))

    def doProcessRequest(self, arg):
        """
        Action method.
        """
        from p2p import commands
        request, info = arg
        target = request.CreatorID
        if request.Command == commands.RequestService():
            if not self.routes.has_key(target):
                self.routes[target] = (info.proto, info.host, time.time())
        elif request.Command == commands.CancelService():
            if self.routes.has_key(target):
                self.routes.pop(target)

    def doUnregisterAllRouts(self, arg):
        """
        Action method.
        """

    def doUnRegisterRoute(self, arg):
        """
        Action method.
        """

    def doForwardRoutedPacket(self, arg):
        """
        Action method.
        """
        self._forward_routed_packet(arg)
        
    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        from transport import gateway
        from transport import callback
        gateway.remove_transport_state_changed_callback(self._on_transport_state_changed)
        # callback.remove_inbox_callback(self._on_inbox_packet_received)
        automat.objects().pop(self.index)
        global _ProxyRouter
        del _ProxyRouter
        _ProxyRouter = None

    # def _on_inbox_packet_received(self, newpacket, info, status, error_message):
    #     target = newpacket.CreatorID
    #     if target in self.routes.keys():
    #         self.automat('routed-inbox-packet-received', newpacket)

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        lg.out(12, 'proxy_router._on_transport_state_changed %s : %s, starting transports: %s' % (
            transport.proto, newstate, self.starting_transports))
        if transport.proto in self.starting_transports:
            if newstate in ['LISTENING', 'OFFLINE',]:
                self.starting_transports.remove(transport.proto)
        if len(self.starting_transports) == 0:
            self.automat('all-transports-ready')

    def _forward_routed_packet(self, newpacket):
        block = encrypted.Unserialize(newpacket.Payload)
        if block is None:
            lg.out(2, 'proxy_router._forward_routed_packet ERROR reading data from %s' % newpacket.RemoteID)
            return
        try:
            session_key = key.DecryptLocalPK(block.EncryptedSessionKey)
            padded_data = key.DecryptWithSessionKey(session_key, block.EncryptedData)
            inpt = cStringIO.StringIO(padded_data[:int(block.Length)])
            sender_idurl = inpt.readline().rstrip('\n')
            receiver_idurl = inpt.readline().rstrip('\n')
        except:
            lg.out(2, 'proxy_router._forward_routed_packet ERROR reading data from %s' % newpacket.RemoteID)
            lg.out(2, '\n' + padded_data)
            lg.exc()
            try:
                inpt.close()
            except:
                pass
            return
        data = inpt.read()
        inpt.close()
        route = self.routes.get(receiver_idurl, None)
        if not route:
            lg.warn('route to %s not found, sender: %s' % (receiver_idurl, sender_idurl))
            return 
        # input_packet = signed.Unserialize(data)
        fileno, filename = tmpfile.make('outbox')
        os.write(fileno, data)
        os.close(fileno)
        filesize = len(data)
        proto, host, tm = route
        gateway.send_file(receiver_idurl, proto, host, filename, 'routed packet')
        lg.out(12, 'proxy_router._forward_routed_packet route %d bytes from %s to %s on %s://%s' % (
            filesize, sender_idurl, receiver_idurl, proto, host))

#------------------------------------------------------------------------------ 

def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

if __name__ == "__main__":
    main()

