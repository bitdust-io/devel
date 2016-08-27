

"""
.. module:: broadcasters_finder
.. role:: red

BitDust broadcasters_finder() Automat

EVENTS:
    * :red:`broadcaster-connected`
    * :red:`dht-failed`
    * :red:`dht-reconnected`
    * :red:`found-one-user`
    * :red:`inbox-packet`
    * :red:`no-service`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-10sec`
    * :red:`users-not-found`
"""


#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------ 

import random

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat

from p2p import commands
from p2p import p2p_service

from contacts import identitycache
from userid import my_id

from transport import callback

from dht import dht_service

#------------------------------------------------------------------------------ 

def create():
    return BroadcastersFinder('broadcasters_finder', 'AT_STARTUP', _DebugLevel, _Debug)

#------------------------------------------------------------------------------ 

class BroadcastersFinder(automat.Automat):
    """
    This class implements all the functionality of the ``broadcasters_finder()`` state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['ACK?','SERVICE?']),
        }

    def init(self):
        self.connected_broadcasters = []

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when broadcasters_finder() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the broadcasters_finder()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'DHT_REFRESH'
                self.Attempts=0
                self.doInit(arg)
                self.doDHTReconnect(arg)
        elif self.state == 'ACK?':
            if event == 'inbox-packet' and self.isAckFromUser(arg):
                self.state = 'SERVICE?'
                self.doBroadcasterConnect(arg)
            elif event == 'timer-10sec' and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
            elif event == 'stop' or ( self.Attempts==5 and event == 'timer-10sec' ):
                self.state = 'FAILED'
                self.doNotifyFailed(arg)
                self.doDestroyMe(arg)
        elif self.state == 'RANDOM_USER':
            if event == 'found-one-user':
                self.state = 'ACK?'
                self.doRememberUser(arg)
                self.Attempts+=1
                self.doSendMyIdentity(arg)
            elif event == 'stop' or event == 'users-not-found':
                self.state = 'FAILED'
                self.doNotifyFailed(arg)
                self.doDestroyMe(arg)
        elif self.state == 'FAILED':
            pass
        elif self.state == 'SERVICE?':
            if event == 'broadcaster-connected' and self.isMoreNeeded(arg):
                self.state = 'RANDOM_USER'
                self.doSaveBroadcaster(arg)
                self.doDHTFindRandomUser(arg)
            elif event == 'broadcaster-connected' and not self.isMoreNeeded(arg):
                self.state = 'DONE'
                self.doSaveBroadcaster(arg)
                self.doNotifySuccess(arg)
                self.doDestroyMe(arg)
            elif ( event == 'timer-10sec' or event == 'no-service' ) and self.Attempts<5:
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
            elif event == 'stop' or ( self.Attempts==5 and ( event == 'timer-10sec' or event == 'no-service' ) ):
                self.state = 'FAILED'
                self.doNotifyFailed(arg)
                self.doDestroyMe(arg)
        elif self.state == 'DONE':
            pass
        elif self.state == 'DHT_REFRESH':
            if event == 'dht-reconnected':
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
            elif event == 'stop' or event == 'dht-failed':
                self.state = 'FAILED'
                self.doNotifyFailed(arg)
                self.doDestroyMe(arg)
        return None

    def isAckFromUser(self, arg):
        """
        Condition method.
        """
        newpacket, info, status, error_message = arg
        if newpacket.Command == commands.Ack():
            if newpacket.OwnerID == self.target_idurl:
                return True
        return False

    def isMoreNeeded(self, arg):
        """
        Condition method.
        """
        return len(self.connected_broadcasters) < self.max_broadcasters

    def doInit(self, arg):
        """
        Action method.
        """
        self.max_broadcasters, self.result_defer = arg
        callback.insert_inbox_callback(0, self._inbox_packet_received)

    def doDHTReconnect(self, arg):
        """
        Action method.
        """
        d = dht_service.reconnect()
        d.addCallback(lambda x: self.automat('dht-reconnected'))
        d.addErrback(lambda x: self.automat('dht-failed'))

    def doDHTFindRandomUser(self, arg):
        """
        Action method.
        """
        d = dht_service.find_node(dht_service.random_key())
        d.addCallback(self._found_nodes)
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

    def doBroadcasterConnect(self, arg):
        """
        Action method.
        """
        service_info = 'service_broadcasting route'
        p2p_service.SendRequestService(
            self.target_idurl, service_info, callbacks={
                commands.Ack():  self._node_acked,
                commands.Fail(): self._node_failed,
            }
        )

    def doSaveBroadcaster(self, arg):
        """
        Action method.
        """
        self.connected_broadcasters.append(arg)

    def doNotifySuccess(self, arg):
        """
        Action method.
        """
        self.result_defer.callback('broadcasters-connected', self.connected_broadcasters)

    def doNotifyFailed(self, arg):
        """
        Action method.
        """
        self.result_defer.callback('broadcasters-failed')

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        callback.remove_inbox_callback(self._inbox_packet_received)
        automat.objects().pop(self.index)

    #------------------------------------------------------------------------------ 
    
    def _inbox_packet_received(self, newpacket, info, status, error_message):
        self.automat('inbox-packet', (newpacket, info, status, error_message))
        return False
    
    def _found_nodes(self, nodes):
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._found_nodes %d nodes' % len(nodes))
        # DEBUG
#         if _Debug:
#             if _DebugLevel >= 8:
#                 if my_id.getLocalID().count('veselin_kpn'):
#                     self._got_target_idurl({'idurl':'http://veselin-p2p.ru/bitdust_j_vps1005.xml'})
#                     return
        if len(nodes) > 0:
            node = random.choice(nodes)
            d = node.request('idurl')
            d.addCallback(self._got_target_idurl)
            d.addErrback(lambda err:  self.automat('users-not-found'))
        else:
            self.automat('users-not-found')

    def _got_target_idurl(self, response):
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._got_target_idurl response=%s' % str(response) )
        try:
            idurl = response['idurl']
        except:
            idurl = None
        if not idurl or idurl == 'None':
            self.automat('users-not-found')
            return response
        if idurl in self.connected_broadcasters:
            if _Debug:
                lg.out(_DebugLevel, '    %s is already a connected broadcaster' % idurl)
            self.automat('users-not-found')
            return response
        d = identitycache.immediatelyCaching(idurl)
        d.addCallback(lambda src: self._got_target_identity(src, idurl))
        d.addErrback(lambda x: self.automat('users-not-found'))
        return response

    def _got_target_identity(self, src, idurl):
        """
        Need to check that remote user is supported at least one of our protocols.
        """
        ident = identitycache.FromCache(idurl)
        remoteprotos = set(ident.getProtoOrder())
        myprotos = set(my_id.getLocalIdentity().getProtoOrder())
        if len(myprotos.intersection(remoteprotos)) > 0:
            self.automat('found-one-user', idurl)
        else:
            self.automat('users-not-found')

    def _node_acked(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._supplier_acked %r %r' % (response, info))
        if not response.Payload.startswith('accepted'):
            if _Debug:
                lg.out(_DebugLevel, 'broadcasters_finder._node_failed %r %r' % (response, info))
            self.automat('no-service')
            return
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._node_acked !!!! broadcaster %s connected' % response.CreatorID)
        self.automat('broadcaster-connected', response.CreatorID)

    def _node_failed(self, response, info):
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._node_failed %r %r' % (response, info))
        self.automat('no-service')

