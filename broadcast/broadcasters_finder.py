

"""
.. module:: broadcasters_finder
.. role:: red

BitDust broadcasters_finder() Automat

EVENTS:
    * :red:`ack-received`
    * :red:`found-one-user`
    * :red:`init`
    * :red:`service-accepted`
    * :red:`service-denied`
    * :red:`shutdown`
    * :red:`start`
    * :red:`timer-3sec`
    * :red:`timer-5sec`
    * :red:`users-not-found`
"""


#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat

from p2p import commands
from p2p import p2p_service
from p2p import lookup

from contacts import identitycache
from userid import my_id

from transport import callback

#------------------------------------------------------------------------------ 

_BroadcastersFinder = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _BroadcastersFinder
    if event is None and arg is None:
        return _BroadcastersFinder 
    if _BroadcastersFinder is None:
        # set automat name and starting state here
        _BroadcastersFinder = BroadcastersFinder('broadcasters_finder', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _BroadcastersFinder.automat(event, arg)
    return _BroadcastersFinder
    
#------------------------------------------------------------------------------ 

class BroadcastersFinder(automat.Automat):
    """
    This class implements all the functionality of the ``broadcasters_finder()`` state machine.
    """

    timers = {
        'timer-3sec': (3.0, ['SERVICE?']),
        'timer-5sec': (5.0, ['ACK?']),
        }

    def init(self):
        self.target_idurl = None
        self.requested_packet_id = None
        self.request_service_params = None
        self.current_broadcasters = []

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'READY'
                self.doInit(arg)
        elif self.state == 'ACK?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'ack-received':
                self.state = 'SERVICE?'
                self.doSendRequestService(arg)
            elif event == 'timer-5sec' and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
        elif self.state == 'RANDOM_USER':
            if event == 'found-one-user':
                self.state = 'ACK?'
                self.doRememberUser(arg)
                self.Attempts+=1
                self.doSendMyIdentity(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'users-not-found':
                self.state = 'READY'
                self.doNotifyLookupFailed(arg)
        elif self.state == 'SERVICE?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif self.Attempts==5 and ( event == 'timer-3sec' or event == 'service-denied' ):
                self.state = 'READY'
                self.doNotifyLookupFailed(arg)
            elif event == 'service-accepted':
                self.state = 'READY'
                self.doNotifyLookupSuccess(arg)
            elif ( event == 'timer-3sec' or event == 'service-denied' ) and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
        elif self.state == 'READY':
            if event == 'start':
                self.state = 'RANDOM_USER'
                self.doSetNotifyCallback(arg)
                self.Attempts=0
                self.doDHTFindRandomUser(arg)
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, arg):
        """
        Action method.
        """
        callback.insert_inbox_callback(0, self._inbox_packet_received)

    def doSetNotifyCallback(self, arg):
        """
        Action method.
        """
        self.result_callback, self.request_service_params, self.current_broadcasters = arg

    def doDHTFindRandomUser(self, arg):
        """
        Action method.
        """
        d = lookup.start()
        d.addCallback(self._nodes_lookup_finished)
        d.addErrback(lambda err: self.automat('users-not-found'))

    def doRememberUser(self, arg):
        """
        Action method.
        """
        self.target_idurl = arg

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        p2p_service.SendIdentity(self.target_idurl, wide=True)

    def doSendRequestService(self, arg):
        """
        Action method.
        """
        service_info = 'service_broadcasting ' + self.request_service_params
        out_packet = p2p_service.SendRequestService(
            self.target_idurl, service_info, callbacks={
                commands.Ack():  self._node_acked,
                commands.Fail(): self._node_failed,
            }
        )
        self.requested_packet_id = out_packet.PacketID

    def doNotifyLookupSuccess(self, arg):
        """
        Action method.
        """
        if self.result_callback:
            self.result_callback('broadcaster-connected', arg)
        self.result_callback = None
        self.request_service_params = None
        self.current_broadcasters = []

    def doNotifyLookupFailed(self, arg):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder.doNotifyLookupFailed, Attempts=%d' % self.Attempts)
        if self.result_callback:
            self.result_callback('lookup-failed', arg)
        self.result_callback = None
        self.request_service_params = None
        self.current_broadcasters = []
        
    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        callback.remove_inbox_callback(self._inbox_packet_received)
        automat.objects().pop(self.index)
        global _BroadcastersFinder
        del _BroadcastersFinder
        _BroadcastersFinder = None

    #------------------------------------------------------------------------------ 

    def _inbox_packet_received(self, newpacket, info, status, error_message):
        if  newpacket.Command == commands.Ack() and \
            newpacket.OwnerID == self.target_idurl and \
            newpacket.PacketID == 'identity' and \
            self.state == 'ACK?':
            self.automat('ack-received', self.target_idurl)
            return True
        return False

    def _node_acked(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._supplier_acked %r %r' % (response, info))
        if not response.Payload.startswith('accepted'):
            if _Debug:
                lg.out(_DebugLevel, 'broadcasters_finder._node_failed %r %r' % (response, info))
            self.automat('service-denied')
            return
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._node_acked !!!! broadcaster %s connected' % response.CreatorID)
        self.automat('service-accepted', response.CreatorID)

    def _node_failed(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._node_failed %r %r' % (response, info))
        self.automat('service-denied')

    def _nodes_lookup_finished(self, idurls):
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._nodes_lookup_finished : %r' % idurls)
        for idurl in idurls:
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if len(myprotos.intersection(remoteprotos)) > 0:
                self.automat('found-one-user', idurl)
                return
        self.automat('users-not-found')
