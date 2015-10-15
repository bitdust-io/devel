

"""
.. module:: packet_out
.. role:: red

BitDust packet_out() Automat

.. raw:: html

    <a href="packet_out.png" target="_blank">
    <img src="packet_out.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`cancel`
    * :red:`failed`
    * :red:`inbox-packet`
    * :red:`item-cancelled`
    * :red:`items-sent`
    * :red:`nothing-to-send`
    * :red:`register-item`
    * :red:`remote-identity-on-hand`
    * :red:`run`
    * :red:`unregister-item`
    * :red:`write-error`
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 12

#------------------------------------------------------------------------------ 

import os
import time

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat

from p2p import commands

from lib import nameurl
from lib import misc

from system import tmpfile

from contacts import contactsdb
from contacts import identitycache
from userid import my_id

from main import settings

import callback
import gateway
import stats

#------------------------------------------------------------------------------ 

_OutboxQueue = []
_PacketsCounter = 0

#------------------------------------------------------------------------------ 

def get_packets_counter():
    global _PacketsCounter
    return _PacketsCounter

def increment_packets_counter():
    global _PacketsCounter
    _PacketsCounter += 1  

#------------------------------------------------------------------------------ 

def queue():
    """
    """
    global _OutboxQueue
    return _OutboxQueue


def create(outpacket, wide, callbacks, target=None, route=None):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'packet_out.create  %s' % str(outpacket))
    p = PacketOut(outpacket, wide, callbacks, target, route)
    queue().append(p)
    p.automat('run')
    return p
    
    
def search(proto, host, filename, remote_idurl=None):
    for p in queue():
        if p.filename != filename:
            continue
        for i in p.items:
            if i.proto == proto:
                if not remote_idurl:
                    return p, i
                if p.remote_idurl and remote_idurl != p.remote_idurl:
                    if _Debug:
                        lg.out(_DebugLevel, 'packet_out.search found a packet addressed for another idurl: %s' % p.remote_idurl)
                return p, i
    if _Debug:
        for p in queue():
            lg.out(_DebugLevel, '%s [%s]' % (os.path.basename(p.filename), 
                ('|'.join(map(lambda i: '%s:%s' % (i.proto, i.host), p.items)))))
    return None, None


def search_by_transfer_id(transfer_id):
    for p in queue():
        for i in p.items:
            if i.transfer_id and i.transfer_id == transfer_id:
                return p, i
    return None, None


def search_by_response_packet(newpacket, proto=None, host=None):
    if _Debug:
        lg.out(_DebugLevel, 'packet_out.search_by_response_packet [%s/%s/%s]:%s %s' % (
            nameurl.GetName(newpacket.OwnerID), nameurl.GetName(newpacket.CreatorID), 
            nameurl.GetName(newpacket.RemoteID), newpacket.PacketID, newpacket.Command))
    result = []
    target_idurl = newpacket.CreatorID
    if newpacket.OwnerID == my_id.getLocalID():
        target_idurl = newpacket.RemoteID
    for p in queue():
        if p.outpacket.PacketID != newpacket.PacketID:
            continue
        if p.outpacket.RemoteID != p.remote_idurl:
            if target_idurl != p.remote_idurl:
                # ????
                pass
        if target_idurl != p.outpacket.RemoteID:
            continue
        result.append(p)
        if _Debug:
            lg.out(_DebugLevel, 'packet_out.search_by_response_packet [%s/%s/%s]:%s cb:%s' % (
                nameurl.GetName(p.outpacket.OwnerID), nameurl.GetName(p.outpacket.CreatorID), 
                 nameurl.GetName(p.outpacket.RemoteID), p.outpacket.PacketID, 
                 p.callbacks.keys()))
    if len(result) == 0:
        if _Debug:
            lg.warn('- not found [%s/%s/%s]:%s %s' % (
                nameurl.GetName(newpacket.OwnerID), nameurl.GetName(newpacket.CreatorID), 
                nameurl.GetName(newpacket.RemoteID), newpacket.PacketID, newpacket.Command))
    return result

#------------------------------------------------------------------------------ 

class WorkItem:
    def __init__(self, proto, host):
        self.proto = proto
        self.host = host
        self.time = time.time()
        self.transfer_id = None
        self.status = None
        self.error_message = None
        self.bytes_sent = 0


class PacketOut(automat.Automat):
    """
    This class implements all the functionality of the ``packet_out()`` state machine.
    """

    timers = {
        'timer-20sec': (20.0, ['RESPONSE?']),
        }

    MESSAGES = {
        'MSG_1': 'file in queue was cancelled',
        'MSG_2': 'sending file was cancelled',
        'MSG_3': 'response waiting were cancelled',
        'MSG_4': 'outgoing packet was cancelled',
        'MSG_5': 'pushing outgoing packet was cancelled',
        }
    
    def __init__(self, outpacket, wide, callbacks={}, target=None, route=None):
        self.outpacket = outpacket
        self.wide = wide
        self.callbacks = callbacks
        self.remote_idurl = target
        self.caching_deferred = None
        self.description = self.outpacket.Command+'('+self.outpacket.PacketID+')'
        self.label = 'out_%d_%s (%d callbacks%s)' % (
            get_packets_counter(), self.description, len(self.callbacks),
            ' routed' if self.route else '')
        self.route = route
        if self.route:
            self.description = self.route['description']
            self.remote_idurl = self.route['remoteid']
        automat.Automat.__init__(self, self.label, 'AT_STARTUP', _DebugLevel, _Debug)
        increment_packets_counter()

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.log_events = True
        self.error_message = None 
        self.time = time.time()
        self.description = self.outpacket.Command+'('+self.outpacket.PacketID+')'
        self.payloadsize = len(self.outpacket.Payload)
        if not self.remote_idurl:
            if self.outpacket.CreatorID == my_id.getLocalID():
                # our data will go to
                self.remote_idurl = self.outpacket.RemoteID.strip()
            else:
                if self.outpacket.Command == commands.Data():      
                    self.remote_idurl = self.outpacket.CreatorID.strip()       
                else:
                    self.remote_idurl = self.outpacket.RemoteID.strip()
                    if _Debug:
                        lg.out(_DebugLevel, 'packet_out.init sending a packet we did not make, and that is not Data packet')
        self.remote_identity = contactsdb.get_contact_identity(self.remote_idurl)
        self.timeout = None
        self.packetdata = None
        self.filename = None
        self.filesize = None
        self.items = []
        self.results = []
        self.response_packet = None
        self.response_info = None

    def msg(self, msgid, arg=None):
        return self.MESSAGES.get(msgid, '')
            
    def is_timed_out(self):
        if self.time is None or self.timeout is None:
            return False
        return time.time() - self.time > self.timeout
        
    def set_callback(self, command, cb):
        self.callbacks[command] = cb
        
    def A(self, event, arg):
        #---SENDING---
        if self.state == 'SENDING':
            if event == 'register-item' :
                self.doSetTransferID(arg)
            elif ( event == 'unregister-item' or event == 'item-cancelled' ) and self.isMoreItems(arg) :
                self.doPopItem(arg)
                self.doReportItem(arg)
            elif event == 'inbox-packet' and self.isResponse(arg) :
                self.Acked=True
                self.doSaveResponse(arg)
                self.doReportResponse(arg)
            elif event == 'unregister-item' and not self.isMoreItems(arg) and self.isAckNeeded(arg) and not self.Acked :
                self.state = 'RESPONSE?'
                self.doPopItem(arg)
                self.doReportItem(arg)
            elif event == 'cancel' :
                self.state = 'CANCEL'
                self.doCancelItems(arg)
                self.doErrMsg(event,self.msg('MSG_2', arg))
                self.doPopItems(arg)
                self.doReportCancelItems(arg)
                self.doReportCancelled(arg)
                self.doDestroyMe(arg)
            elif ( event == 'unregister-item' or event == 'item-cancelled' ) and not self.isMoreItems(arg) and ( self.Acked or not self.isAckNeeded(arg) ) :
                self.state = 'SENT'
                self.doPopItem(arg)
                self.doReportItem(arg)
                self.doReportDoneNoAck(arg)
                self.doDestroyMe(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'run' and self.isRemoteIdentityKnown(arg) :
                self.state = 'ITEMS?'
                self.doInit(arg)
                self.Cancelled=False
                self.doReportStarted(arg)
                self.doSerializeAndWrite(arg)
                self.doPushItems(arg)
            elif event == 'run' and not self.isRemoteIdentityKnown(arg) :
                self.state = 'CACHING'
                self.doInit(arg)
                self.doCacheRemoteIdentity(arg)
        #---CACHING---
        elif self.state == 'CACHING':
            if event == 'remote-identity-on-hand' :
                self.state = 'ITEMS?'
                self.Cancelled=False
                self.doReportStarted(arg)
                self.doSerializeAndWrite(arg)
                self.doPushItems(arg)
            elif event == 'failed' :
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'cancel' :
                self.state = 'CANCEL'
                self.doErrMsg(event,self.msg('MSG_4', arg))
                self.doReportCancelled(arg)
                self.doDestroyMe(arg)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---ITEMS?---
        elif self.state == 'ITEMS?':
            if event == 'nothing-to-send' or event == 'write-error' :
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'items-sent' and not self.Cancelled :
                self.state = 'IN_QUEUE'
            elif event == 'cancel' :
                self.Cancelled=True
            elif event == 'items-sent' and self.Cancelled :
                self.state = 'CANCEL'
                self.doCancelItems(arg)
                self.doErrMsg(event,self.msg('MSG_5', arg))
                self.doPopItems(arg)
                self.doReportCancelItems(arg)
                self.doReportCancelled(arg)
                self.doDestroyMe(arg)
        #---IN_QUEUE---
        elif self.state == 'IN_QUEUE':
            if event == 'item-cancelled' and self.isMoreItems(arg) :
                self.doPopItem(arg)
                self.doReportItem(arg)
            elif event == 'register-item' :
                self.state = 'SENDING'
                self.Acked=False
                self.doSetTransferID(arg)
            elif event == 'cancel' :
                self.state = 'CANCEL'
                self.doCancelItems(arg)
                self.doErrMsg(event,self.msg('MSG_1', arg))
                self.doPopItems(arg)
                self.doReportCancelItems(arg)
                self.doReportCancelled(arg)
                self.doDestroyMe(arg)
            elif event == 'item-cancelled' and not self.isMoreItems(arg) :
                self.state = 'FAILED'
                self.doPopItem(arg)
                self.doReportItem(arg)
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---SENT---
        elif self.state == 'SENT':
            pass
        #---CANCEL---
        elif self.state == 'CANCEL':
            pass
        #---RESPONSE?---
        elif self.state == 'RESPONSE?':
            if event == 'cancel' :
                self.state = 'CANCEL'
                self.doErrMsg(event,self.msg('MSG_3', arg))
                self.doReportCancelItems(arg)
                self.doReportCancelled(arg)
                self.doDestroyMe(arg)
            elif event == 'inbox-packet' and self.isResponse(arg) :
                self.state = 'SENT'
                self.doSaveResponse(arg)
                self.doReportResponse(arg)
                self.doReportDoneWithAck(arg)
                self.doDestroyMe(arg)
        return None

    def isRemoteIdentityKnown(self, arg):
        """
        Condition method.
        """
        return self.remote_identity is not None

    def isAckNeeded(self, arg):
        """
        Condition method.
        """
        return len(self.callbacks) > 0

    def isMoreItems(self, arg):
        """
        Condition method.
        """
        return len(self.items) > 1

    def isResponse(self, arg):
        """
        Condition method.
        """
        newpacket, info = arg
        return newpacket.Command in self.callbacks.keys()

    def doInit(self, arg):
        """
        Action method.
        """

    def doCacheRemoteIdentity(self, arg):
        """
        Action method.
        """
        self.caching_deferred = identitycache.immediatelyCaching(self.remote_idurl)
        self.caching_deferred.addCallback(self._remote_identity_cached)
        self.caching_deferred.addErrback(lambda err: self.automat('failed'))

    def doSerializeAndWrite(self, arg):
        """
        Action method.
        """
        # serialize and write packet on disk
        a_packet = self.outpacket
        if self.route:
            a_packet = self.route['packet']
        try:
            fileno, self.filename = tmpfile.make('outbox')
            self.packetdata = a_packet.Serialize()
            os.write(fileno, self.packetdata)
            os.close(fileno)
            self.filesize = len(self.packetdata)
            self.timeout = max(int(self.filesize/(settings.SendingSpeedLimit()/len(queue()))), 
                               settings.SendTimeOut())
        except:
            lg.exc()
            self.packetdata = None
            self.automat('write-error')
            
    def doPushItems(self, arg):
        """
        Action method.
        """
        self._push()

    def doPopItem(self, arg):
        """
        Action method.
        """
        self._pop(arg)
            
    def doPopItems(self, arg):
        """
        Action method.
        """
        self.items = []

    def doSetTransferID(self, arg):
        """
        Action method.
        """
        ok = False
        proto, host, filename, transfer_id = arg
        for i in xrange(len(self.items)):
            if self.items[i].proto == proto: # and self.items[i].host == host:
                self.items[i].transfer_id = transfer_id
                if _Debug:
                    lg.out(_DebugLevel, 'packet_out.doSetTransferID  %r:%r = %r' % (proto, host, transfer_id))
                ok = True
        if not ok:
            lg.warn('not found item for %r:%r' % (proto, host))

    def doSaveResponse(self, arg):
        """
        Action method.
        """
        self.response_packet, self.response_info = arg

    def doCancelItems(self, arg):
        """
        Action method.
        """
        for i in self.items:
            t = gateway.transports().get(i.proto, None)
            if t:
                if i.transfer_id:
                    t.call('cancel_file_sending', i.transfer_id)
                t.call('cancel_outbox_file', i.host, self.filename)
                
    def doReportStarted(self, arg):
        """
        Action method.
        """
        callback.run_outbox_callbacks(self)

    def doReportItem(self, arg):
        """
        Action method.
        """
        assert self.popped_item
        stats.count_outbox(
            self.remote_idurl, self.popped_item.proto, 
            self.popped_item.status, self.popped_item.bytes_sent)
        callback.run_finish_file_sending_callbacks(
            self, self.popped_item, self.popped_item.status, 
            self.popped_item.bytes_sent, self.popped_item.error_message)
        self.popped_item = None

    def doReportCancelItems(self, arg):
        """
        Action method.
        """
        for item in self.results:
            stats.count_outbox(self.remote_idurl, item.proto, 'failed', 0)
            callback.run_finish_file_sending_callbacks(
                self, item, 'failed', 0, self.error_message)

    def doReportResponse(self, arg):
        """
        Action method.
        """
        if self.response_packet.Command in self.callbacks:
            self.callbacks[self.response_packet.Command](self.response_packet, self.response_info)

    def doReportDoneWithAck(self, arg):
        """
        Action method.
        """
        callback.run_queue_item_status_callbacks(self, 'finished', '')

    def doReportDoneNoAck(self, arg):
        """
        Action method.
        """
        callback.run_queue_item_status_callbacks(self, 'finished', '')

    def doReportFailed(self, arg):
        """
        Action method.
        """
        try:
            msg = str(arg[-1])
        except:
            msg = 'failed'
        callback.run_queue_item_status_callbacks(self, 'failed', msg)

    def doReportCancelled(self, arg):
        """
        Action method.
        """
        msg = arg
        if not isinstance(msg, str):
            msg = 'cancelled'
        callback.run_queue_item_status_callbacks(self, 'failed', msg)

    def doErrMsg(self, event, arg):
        """
        Action method.
        """
        if event.count('timer'):
            self.error_message = 'timeout responding from remote side'
        else:
            self.error_message = arg

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        if self.caching_deferred:
            self.caching_deferred.cancel()
            self.caching_deferred = None
        self.outpacket = None
        self.remote_identity = None
        self.callbacks.clear()
        queue().remove(self)
        self.destroy()

    def _remote_identity_cached(self, xmlsrc):
        self.caching_deferred = None
        self.remote_identity = contactsdb.get_contact_identity(self.remote_idurl)
        if self.remote_identity is None:
            self.automat('failed')
        else:
            self.automat('remote-identity-on-hand')

    def _push(self):
        if self.route:
            # if this packet is routed - send directly to route host
            d = gateway.send_file(
                self.route['remoteid'], 
                self.route['proto'], 
                self.route['host'], 
                self.filename, 
                self.description)
            self.items.append(WorkItem(self.route['proto'], self.route['host']))
            self.automat('items-sent')
            return
        # get info about his local IP
        localIP = identitycache.GetLocalIP(self.remote_idurl)
        workitem_sent = False
        if self.wide: 
            # send to all his contacts
            for contactmethod in self.remote_identity.getContacts():
                proto, host = nameurl.IdContactSplit(contactmethod)
                if  host.strip() and \
                    settings.transportIsEnabled(proto) and \
                    settings.transportSendingIsEnabled(proto) and \
                    gateway.can_send(proto) and \
                    gateway.is_installed(proto):
                        if proto == 'tcp' and localIP:
                            host = localIP
                        d = gateway.send_file(self.remote_idurl, proto, host, self.filename, self.description)
                        self.items.append(WorkItem(proto, host))
                        workitem_sent = True
            if not workitem_sent:
                self.automat('nothing-to-send')
                lg.warn('(wide) no supported protocols with %s' % self.remote_idurl)
            else:
                self.automat('items-sent')
            return
        # send to one of his contacts,
        # now need to decide which transport to use
        # let's prepare his contacts first
        byproto = self.remote_identity.getContactsByProto()
        tcp_contact = None
        if settings.enableTCP() and settings.enableTCPsending():
            tcp_contact = byproto.get('tcp', None)
        udp_contact = None
        if settings.enableUDP() and settings.enableUDPsending():
            udp_contact = byproto.get('udp', None)
        proxy_contact = None
        if settings.enablePROXY() and settings.enablePROXYsending():
            proxy_contact = byproto.get('proxy', None)
        working_protos = stats.peers_protos().get(self.remote_idurl, set())
        # tcp seems to be the most stable proto
        # now let's check if we know his local IP and 
        # he enabled tcp in his settings to be able to receive packets from others 
        # try to send to his local IP first, not external
        if tcp_contact and localIP:
            if gateway.is_installed('tcp') and gateway.can_send(proto):
                proto, host, port, fn = nameurl.UrlParse(tcp_contact)
                if port:
                    host = localIP+':'+str(port)
                gateway.send_file(self.remote_idurl, proto, host, self.filename, self.description)
                self.items.append(WorkItem(proto, host))
                self.automat('items-sent')
                return
        # tcp is the best proto - if it is working - this is the best case!!!
        if tcp_contact and 'tcp' in working_protos:
            proto, host, port, fn = nameurl.UrlParse(tcp_contact)
            if host.strip() and gateway.is_installed(proto) and gateway.can_send(proto):  
                if port:
                    host = host+':'+str(port)
                gateway.send_file(self.remote_idurl, proto, host, self.filename, self.description)
                self.items.append(WorkItem(proto, host))
                self.automat('items-sent')
                return
        # udp contact
        if udp_contact and 'udp' in working_protos:
            proto, host = nameurl.IdContactSplit(udp_contact)
            if host.strip() and gateway.is_installed('udp') and gateway.can_send(proto):
                gateway.send_file(self.remote_idurl, proto, host, self.filename, self.description)
                self.items.append(WorkItem(proto, host))
                self.automat('items-sent')
                return
        # proxy contact - he may use other node to receive and send packets
        if proxy_contact and 'proxy' in working_protos:
            proto, host = nameurl.IdContactSplit(proxy_contact)
            if host.strip() and gateway.is_installed('proxy') and gateway.can_send(proto):
                gateway.send_file(self.remote_idurl, proto, host, self.filename, self.description)
                self.items.append(WorkItem(proto, host))
                self.automat('items-sent')
                return
        # finally use the first proto we supported if we can not find the best preferable method
        for contactmethod in self.remote_identity.getContacts():
            proto, host, port, fn = nameurl.UrlParse(contactmethod)
            if port:
                host = host+':'+str(port)
            # if method exist but empty - don't use it
            if host.strip():
                # try sending with tcp even if it is switched off in the settings
                if gateway.is_installed(proto) and gateway.can_send(proto):
                    if settings.enableTransport(proto) and settings.transportSendingIsEnabled(proto):
                        gateway.send_file(self.remote_idurl, proto, host, self.filename, self.description)
                        self.items.append(WorkItem(proto, host))
                        self.automat('items-sent')
                        return
        self.automat('nothing-to-send')
        lg.warn('no supported protocols with %s : %s %s %s, byproto:%s' % (
            self.remote_idurl, tcp_contact, udp_contact, working_protos, str(byproto)))
        

    def _pop(self, packet_args):
        self.popped_item = None
        if len(packet_args) == 4:
            transfer_id, status, size, error_message = packet_args
            for i in self.items:
                if i.transfer_id and i.transfer_id == transfer_id:
                    self.items.remove(i)
                    i.status = status
                    i.error_message = error_message
                    i.bytes_sent = size
                    self.results.append(i)
                    self.popped_item = i
                    break
        elif len(packet_args) == 6:
            proto, host, filename, size, descr, err_msg = packet_args
            for i in self.items:
                if i.proto == proto and i.host == host:
                    self.items.remove(i)
                    i.status = 'failed'
                    i.error_message = err_msg
                    i.bytes_sent = size
                    self.results.append(i)
                    self.popped_item = i
                    break
        else:
            raise Exception('Wrong argument!')        
