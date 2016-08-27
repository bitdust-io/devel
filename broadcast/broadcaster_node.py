

"""
.. module:: broadcaster_node
.. role:: red

BitDust broadcaster_node() Automat

EVENTS:
    * :red:`broadcast-message-received`
    * :red:`broadcaster-disconnected`
    * :red:`broadcasters-connected`
    * :red:`broadcasters-failed`
    * :red:`init`
    * :red:`new-broadcaster-connected`
    * :red:`new-outbound-message`
    * :red:`shutdown`
    * :red:`timer-1min`
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------ 

import time
import json

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat

from p2p import contact_status
from p2p import commands

from transport import callback

from broadcast import broadcasters_finder

from p2p import p2p_service

#------------------------------------------------------------------------------ 

_BroadcasterNode = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _BroadcasterNode
    if _BroadcasterNode is None:
        # set automat name and starting state here
        _BroadcasterNode = BroadcasterNode('broadcaster_node', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _BroadcasterNode.automat(event, arg)
    return _BroadcasterNode
    
#------------------------------------------------------------------------------ 

class BroadcasterNode(automat.Automat):
    """
    This class implements all the functionality of the ``broadcaster_node()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['BROADCASTING']),
        }
    
    def init(self):
        self.max_broadcasters = 4 # TODO - read from settings
        self.connected_broadcasters = []
        self.messages_sent = {}
        self.broadcasters_finder = None
        self.last_success_action_time = None

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when broadcaster_node() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the broadcaster_node()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'BROADCASTERS?'
                self.doInit(arg)
                self.doLookupBroadcasters(arg)
        elif self.state == 'BROADCASTERS?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doStopBroadcastersLookup(arg)
                self.doDisconnectBroadcasters(arg)
                self.doDestroyMe(arg)
            elif event == 'broadcasters-connected':
                self.state = 'BROADCASTING'
                self.doNotifyConnected(arg)
            elif event == 'broadcasters-failed':
                self.state = 'OFFLINE'
                self.doDisconnectBroadcasters(arg)
        elif self.state == 'OFFLINE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'new-broadcaster-connected':
                self.state = 'BROADCASTERS?'
                self.doConnectNewBroadcaster(arg)
                self.doLookupBroadcasters(arg)
        elif self.state == 'CLOSED':
            pass
        elif self.state == 'BROADCASTING':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDisconnectBroadcasters(arg)
                self.doDestroyMe(arg)
            elif event == 'new-broadcaster-connected':
                self.doConnectNewBroadcaster(arg)
            elif event == 'broadcast-message-received':
                self.doCheckAndSendForward(arg)
            elif event == 'broadcaster-disconnected':
                self.doDisconnectOneBroadcaster(arg)
            elif event == 'new-outbound-message':
                self.doBroadcastMessage(arg)
            elif event == 'timer-1min' and self.isLineActive(arg):
                self.doTestReconnectBroadcasters(arg)
            elif event == 'timer-1min' and not self.isLineActive(arg):
                self.state = 'OFFLINE'
                self.doDisconnectBroadcasters(arg)
        return None

    def isLineActive(self, arg):
        """
        Condition method.
        """
        for idurl in self.connected_broadcasters:
            if contact_status.isOnline(idurl):
                # if at least one broadcaster is connected
                # we assume the line is still active 
                return True
        if not self.last_success_action_time:
            return False
        return time.time() - self.last_success_action_time > 5*60

    def doInit(self, arg):
        """
        Action method.
        """
        callback.append_inbox_callback(self._on_inbox_packet)

    def doLookupBroadcasters(self, arg):
        """
        Action method.
        """
        result = Deferred()
        result.addCallback(self.automat)
        self.broadcasters_finder = broadcasters_finder.create()
        self.broadcasters_finder.automat('start', (self.max_broadcasters, result))

    def doStopBroadcastersLookup(self, arg):
        """
        Action method.
        """
        self.broadcasters_finder.automat('stop')
        del self.broadcasters_finder
        self.broadcasters_finder = None

    def doDisconnectBroadcasters(self, arg):
        """
        Action method.
        """
        self.connected_broadcasters = []

    def doConnectNewBroadcaster(self, arg):
        """
        Action method.
        """
        if arg.CreatorID in self.connected_broadcasters:
            lg.warn('%s already connected as broadcaster' % arg.CreatorID)
            return
        self.connected_broadcasters.append(arg.CreatorID)
        self.last_success_action_time = time.time()

    def doDisconnectOneBroadcaster(self, arg):
        """
        Action method.
        """
        if arg.CreatorID not in self.connected_broadcasters:
            lg.warn('%s is not connected' % arg.CreatorID)
            return
        self.connected_broadcasters.remove(arg.CreatorID)

    def doCheckAndSendForward(self, arg):
        """
        Action method.
        """
        try:
            msg = json.loads(arg.Payload)
        except:
            lg.exc()
            return False
        msgid = msg['id']
        if msgid in self.messages_sent:
            if _Debug:
                lg.out(_DebugLevel, 'broadcaster_node.doCheckAndSendForward resending skipped, %s was already sent to my broadcasters')
            return
        self._send_broadcast_message(arg)
        self.last_success_action_time = time.time()

    def doBroadcastMessage(self, arg):
        """
        Action method.
        """
        msg = self._new_message(arg.CreatorID, arg.Payload)
        msgid = msg['id']
        assert msgid in self.messages_sent
        self.messages_sent[msgid] = int(time.time())
        self._send_broadcast_message(msg)

    def doNotifyConnected(self, arg):
        """
        Action method.
        """
        self.last_success_action_time = time.time()

    def doTestReconnectBroadcasters(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        callback.remove_inbox_callback(self._on_inbox_packet)
        automat.objects().pop(self.index)
        global _Broadcaster
        del _Broadcaster
        _Broadcaster = None
    
    #------------------------------------------------------------------------------ 

    def _on_inbox_packet(self, newpacket, info, status, error_message):
        if status != 'finished':
            return False
        if newpacket.Command == commands.Broadcast():
            self.automat('broadcast-message-received', newpacket)
            return True
#         if newpacket.Command == commands.Ack():
#             if newpacket.PacketID not in self.acks_pending:
#                 return False
#             self.automat('ack-received', newpacket)
#             return True
        return False

    def _send_broadcast_message(self, json_data):
        for idurl in self.connected_broadcasters:
            p2p_service.SendBroadcastMessage(idurl, json_data)
            
#     def _send_ack(self, idurl, msgid, acks=0):
#         p2p_service.SendAckNoRequest(idurl, packetid,
#             response="%s %d" % (msgid, acks))
        
    def _new_message(self, creator, payload):
        tm = int(time.time())
        msgid = '%d:%s' % (tm, creator) 
        return {
            'creator': creator,
            'started': tm,
            'id': msgid,
            'payload': payload,
        }
        
