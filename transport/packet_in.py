

"""
.. module:: packet_in
.. role:: red

BitDust packet_in() Automat

.. raw:: html

    <a href="packet_in.png" target="_blank">
    <img src="packet_in.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`cancel`
    * :red:`failed`
    * :red:`register-item`
    * :red:`remote-id-cached`
    * :red:`unregister-item`
    * :red:`unserialize-failed`
    * :red:`valid-inbox-packet`
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------ 

import os
import time

from twisted.internet import reactor

from logs import lg

from automats import automat

from system import bpio
from system import tmpfile

from main import settings

from userid import my_id

from contacts import contactsdb 
from contacts import identitycache

from services import driver

import gateway
import stats
import callback
import packet_out

#------------------------------------------------------------------------------ 

_InboxItems = {}
_PacketsCounter = 0

#------------------------------------------------------------------------------ 

def get_packets_counter():
    global _PacketsCounter
    return _PacketsCounter

def increment_packets_counter():
    global _PacketsCounter
    _PacketsCounter += 1  
    
#------------------------------------------------------------------------------ 

def items():
    """
    """
    global _InboxItems
    return _InboxItems


def create(transfer_id):
    p = PacketIn(transfer_id)
    items()[transfer_id] = p
    # lg.out(10, 'packet_in.create  %s,  %d working items now' % (
    #     transfer_id, len(items())))
    return p


def get(transfer_id):
    return items().get(transfer_id, None)

#------------------------------------------------------------------------------ 

def process(newpacket, info):
    if not driver.is_started('service_p2p_hookups'):
        if _Debug:
            lg.out(_DebugLevel, 'packet_in.process SKIP incoming packet, service_p2p_hookups is not started')
        return
    handled = False
    if _Debug:
        lg.out(_DebugLevel, 'packet_in.process %s from %s://%s : %s' % (
            str(newpacket), info.proto, info.host, info.status))
    from p2p import commands
    from p2p import p2p_service
    if newpacket.Command == commands.Identity() and newpacket.RemoteID == my_id.getLocalID():
        # contact sending us current identity we might not have
        # so we handle it before check that packet is valid
        # because we might not have his identity on hands and so can not verify the packet  
        # so we check that his Identity is valid and save it into cache
        # than we check the packet to be valid too.
        handled = handled or p2p_service.Identity(newpacket)            
        # return
    # check that signed by a contact of ours
    if not newpacket.Valid():              
        lg.warn('new packet from %s://%s is NOT VALID: %r' % (
            info.proto, info.host, newpacket))
        return
    for p in packet_out.search_by_response_packet(newpacket, info.proto, info.host):
        p.automat('inbox-packet', (newpacket, info))
        handled = True
    handled = handled or callback.run_inbox_callbacks(newpacket, info, info.status, info.error_message)
    if not handled and newpacket.Command not in [ commands.Ack(), commands.Fail() ]:
        if _Debug:
            lg.out(_DebugLevel-8, '    incoming %s from [%s://%s]' % (
                newpacket, info.proto, info.host))
            lg.out(_DebugLevel-8, '        NOT HANDLED !!!')

#------------------------------------------------------------------------------ 

class PacketIn(automat.Automat):
    """
    This class implements all the functionality of the ``packet_in()`` state machine.
    """

    def __init__(self, transfer_id):
        self.transfer_id = transfer_id
        self.time = None
        self.timeout = None
        self.proto = None
        self.host = None 
        self.sender_idurl = None
        self.filename = None
        self.size = None
        self.bytes_received = None
        self.status = None
        self.error_message = None
        self.label = 'in_%d_%s' % (get_packets_counter(), self.transfer_id)
        automat.Automat.__init__(self, self.label, 'AT_STARTUP', _DebugLevel, _Debug)
        increment_packets_counter()
        
    def is_timed_out(self):
        if self.time is None or self.timeout is None:
            return False
        return time.time() - self.time > self.timeout

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.log_events = False

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'register-item' :
                self.state = 'RECEIVING'
                self.doInit(arg)
        #---RECEIVING---
        elif self.state == 'RECEIVING':
            if event == 'cancel' :
                self.doCancelItem(arg)
            elif event == 'unregister-item' and not self.isTransferFinished(arg) :
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doEraseInputFile(arg)
                self.doDestroyMe(arg)
            elif event == 'unregister-item' and self.isTransferFinished(arg) and not self.isRemoteIdentityCached(arg) :
                self.state = 'CACHING'
                self.doCacheRemoteIdentity(arg)
            elif event == 'unregister-item' and self.isTransferFinished(arg) and self.isRemoteIdentityCached(arg) :
                self.state = 'INBOX?'
                self.doReadAndUnserialize(arg)
        #---INBOX?---
        elif self.state == 'INBOX?':
            if event == 'valid-inbox-packet' :
                self.state = 'DONE'
                self.doReportReceived(arg)
                self.doEraseInputFile(arg)
                self.doDestroyMe(arg)
            elif event == 'unserialize-failed' :
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doEraseInputFile(arg)
                self.doDestroyMe(arg)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---CACHING---
        elif self.state == 'CACHING':
            if event == 'failed' :
                self.state = 'FAILED'
                self.doReportCacheFailed(arg)
                self.doEraseInputFile(arg)
                self.doDestroyMe(arg)
            elif event == 'remote-id-cached' :
                self.state = 'INBOX?'
                self.doReadAndUnserialize(arg)
        return None

    def isTransferFinished(self, arg):
        """
        Condition method.
        """
        status, bytes_received, error_message = arg
        if status != 'finished':
            return False
        if self.size and self.size > 0 and self.size != bytes_received:
            return False
        return True

    def isRemoteIdentityCached(self, arg):
        """
        Condition method.
        """
        if not self.sender_idurl:
            return True
        return self.sender_idurl and identitycache.HasKey(self.sender_idurl)

    def doInit(self, arg):
        """
        Action method.
        """
        self.proto, self.host, self.sender_idurl, self.filename, self.size = arg
        self.time = time.time()
        self.timeout = max(int(self.size/settings.SendingSpeedLimit()), 10)
        if not self.sender_idurl:
            lg.warn('sender_idurl is None: %s' % str(arg))

    def doEraseInputFile(self, arg):
        """
        Action method.
        """
        reactor.callLater(1, tmpfile.throw_out, self.filename, 'received')

    def doCancelItem(self, arg):
        """
        Action method.
        """
        t = gateway.transports().get(self.proto, None)
        if t: 
            t.call('cancel_file_receiving', self.transfer_id)

    def doCacheRemoteIdentity(self, arg):
        """
        Action method.
        """
        d = identitycache.immediatelyCaching(self.sender_idurl)
        d.addCallback(self._remote_identity_cached, arg)
        d.addErrback(lambda err: self.automat('failed', arg))

    def doReadAndUnserialize(self, arg):
        """
        Action method.
        """
        self.status, self.bytes_received, self.error_message = arg
        # DO UNSERIALIZE HERE , no exceptions
        newpacket = gateway.inbox(self)
        if newpacket is None:
            lg.out(14, '<<< IN <<< !!!NONE!!! [%s] %s from %s %s' % (
                         self.proto.upper().ljust(5), self.status.ljust(8), 
                         self.host, os.path.basename(self.filename),))
            # net_misc.ConnectionFailed(None, proto, 'receiveStatusReport %s' % host)
            try:
                fd, fn = tmpfile.make('other', '.inbox.error')
                data = bpio.ReadBinaryFile(self.filename)
                os.write(fd, 'from %s:%s %s\n' % (self.proto, self.host, self.status))
                os.write(fd, str(data))
                os.close(fd)
                os.remove(self.filename)
            except:
                lg.exc()
            self.automat('unserialize-failed', None)
            return
        self.automat('valid-inbox-packet', newpacket)

    def doReportReceived(self, arg):
        """
        Action method.
        """
        newpacket = arg
        stats.count_inbox(self.sender_idurl, self.proto, self.status, self.bytes_received)
        process(newpacket, self)

    def doReportFailed(self, arg):
        """
        Action method.
        """
        status, bytes_received, error_message = arg
        stats.count_inbox(self.sender_idurl, self.proto, status, bytes_received)

    def doReportCacheFailed(self, arg):
        """
        Action method.
        """
        status, bytes_received, error_message = arg
        stats.count_inbox(self.sender_idurl, self.proto, status, bytes_received)
        lg.out(18, 'packet_in.doReportCacheFailed WARNING : %s' % self.sender_idurl)

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        items().pop(self.transfer_id)
        self.destroy()

    def _remote_identity_cached(self, xmlsrc, arg):
        sender_identity = contactsdb.get_contact_identity(self.sender_idurl)
        if sender_identity is None:
            self.automat('failed')
        else:
            self.automat('remote-id-cached', arg)
