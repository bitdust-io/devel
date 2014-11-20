#!/usr/bin/python
#gateway.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#


"""
.. module:: gateway

This is a replacement for `lib.transport_control` stuff.
Here is place to put `outgoing` files to send to other users in the network.
Also this code receives a `incoming` files from other nodes.

Keeps a list of available `transports` - we use a plug-in system so you can
use external p2p, mech, or centralized networks to transfer files in different ways.

To identify user need to place his ID inside given external network to his public identity file.
So BitPie.NET users can use different ways to communicate and transfer data.
BitPie.NET code will use that module to talk with nodes in the network.

Seems like we faced with such situation - 
BitPie.NET software need to work together with other networks software on same machine.
This means we need to communicate between system processes - this is work for plug-ins.
So the idea is to make plug-ins code working inside the main process thread - 
they just need to send/receive a short commands to another process in the OS.
So it must be atomic operations (or deferred) and do not use any resources.

And it seems like some plug-ins must have 2 parts:

    * BitPie.NET python module with interface to do peers communications
    * external code to run the given network 
    
Communication between both parts can be done in a different ways, I think XMLRPC can work for most cases.
We need to run XML-RPC on both sides because transport plug-in 
must be able to respond to the main process too. 

External network can be written in C++ or Java and the second part of the transport plig-in need to 
deal with that and be portable.   

Different networks provides various functions, something more than just transfer files.
Some of them uses DHT to store data on nodes - we can use that stuff also. 
"""

import os
import sys
import time
import optparse

from twisted.web import xmlrpc
from twisted.web import server
from twisted.internet import reactor
from twisted.internet import task
from twisted.internet.defer import Deferred 
from twisted.internet.defer import maybeDeferred 
from twisted.internet.defer import fail
from twisted.python import failure

from logs import lg

from lib import bpio
from lib import misc
from lib import settings
from lib import commands
from lib import nameurl
from lib import tmpfile

from services import driver

from crypt import signed

from userid import identitycache

import callback
import network_transport
import packet_in
import packet_out

#------------------------------------------------------------------------------ 

_AvailableTransports = {}
_TransportsDict = {}
_DoingShutdown = False
_LocalListener = None
_XMLRPCListener = None
_XMLRPCPort = None
_XMLRPCURL = ''
_LastTransferID = None
_LastInboxPacketTime = 0
_PacketsTimeOutTask = None
                
#------------------------------------------------------------------------------ 

def transport(proto):
    global _TransportsDict
    return _TransportsDict[proto]


def transports():
    global _TransportsDict
    return _TransportsDict


def listener():
    global _LocalListener
    return _LocalListener


def is_installed(proto):
    """
    Return True if given transport is installed.
    """
    return proto in transports()


def can_send(proto):
    """
    """
    return transport(proto).state == 'LISTENING'


def last_inbox_time():
    global _LastInboxPacketTime
    return _LastInboxPacketTime
    
#------------------------------------------------------------------------------ 

def init():
    """
    """
    global _LocalListener
    global _DoingShutdown
    lg.out(4, 'gateway.init')
    if _DoingShutdown:
        return
    _LocalListener = TransportGateLocalProxy()


#def init1(transportslist=[]):
#    """
#    Initialize the transports gateway - this will start all installed transports.
#    Return a list if started transports.
#    """
#    global _LocalListener
#    global _XMLRPCListener
#    global _XMLRPCPort
#    global _XMLRPCURL
#    global _DoingShutdown
#    global _TransportsDict
#    global _AvailableTransports
#    lg.out(4, 'gateway.init')
#    if _DoingShutdown:
#        return []
#    result = []
#    _LocalListener = TransportGateLocalProxy()
#    lg.out(6, 'gateway.init transports: %s' % str(transportslist))
#    for proto in transportslist:
#        iface = None
#        if proto == 'tcp':
#            try:
#                from tcp import tcp_interface
#                _AvailableTransports['tcp'] = True
#            except:
#                lg.exc()
#                continue
#            iface = tcp_interface.GateInterface()
#        elif proto == 'udp':
#            try:
#                from udp import udp_interface
#                _AvailableTransports['udp'] = True
#            except:
#                lg.exc()
#                continue
#            iface = udp_interface.GateInterface()
#        if iface is None:
#            raise Exception('transport not supported: %s'  % proto)
#        _TransportsDict[proto] = network_transport.NetworkTransport(proto, iface, on_transport_state_changed)
#        transport(proto).automat('init', _LocalListener)
#        result.append(proto)
#        lg.out(6, 'gateway.init initialized transport [%s]' % proto)
##    _XMLRPCListener = reactor.listenTCP(0, server.Site(TransportGateXMLRPCServer()))
##    _XMLRPCPort = _XMLRPCListener.getHost().port
##    _XMLRPCURL = "http://localhost:%d" % int(_XMLRPCPort)
##    if not transportslist:
##        transportslist = _AvailableTransports.keys()
##    lg.out(6, 'gateway.init  XML-RPC: %s, transports: %s' % (_XMLRPCURL, transportslist))
##    for proto in transportslist:
##        iface = None
##        if proto == 'tcp':
##            iface = tcp_interface.GateInterface()
##        elif proto == 'udp':
##            iface = udp_interface.GateInterface()
##        if iface is None:
##            raise Exception('transport not supported: %s'  % proto)
##        _TransportsDict[proto] = network_transport.NetworkTransport(proto, iface)
##        transport(proto).automat('init', _XMLRPCURL)
##        result.append(proto)
##        lg.out(6, 'gateway.init want to start transport [%s]' % proto)
#    return result


def shutdown():
    """
    Shut down the gateway, need to stop all transports.
    """
    global _LocalListener
    global _XMLRPCListener
    global _XMLRPCPort
    global _XMLRPCURL
    global _DoingShutdown
    lg.out(4, 'gateway.shutdown')
    if _DoingShutdown:
        return
    _DoingShutdown = True
    # for transp in transports().values():
    #     transp.automat('shutdown')
#    if _XMLRPCListener:
#        del _XMLRPCListener
#        _XMLRPCListener = None
#        _XMLRPCPort = None
#        _XMLRPCURL = None
    if _LocalListener:
        _LocalListener = None


def start():
    """
    """
    lg.out(4, 'gateway.start')
    result = []
    for proto, transp in transports().items():
        if settings.transportIsEnabled(proto): 
            if transp.state != 'LISTENING':
                lg.out(4, '    sending "start" to %s' % transp)
                transp.automat('start')
                result.append(proto)
            else:
                lg.out(4, '    %r is ready' % transp)
    reactor.callLater(5, packets_timeout_loop)
    return result

        
def stop():
    """
    """
    lg.out(4, 'gateway.stop')
    stop_packets_timeout_loop()
    shutdown_all_inbox_packets()
    shutdown_all_outbox_packets()
    result = []
    for proto, transp in transports().items():
        if settings.transportIsEnabled(proto): 
            if transp.state != 'OFFLINE':
                lg.out(4, '    send "stop" to %s' % transp)
                transp.automat('stop')
                result.append(proto)
            else:
                lg.out(4, '    %s already stopped' % proto)
    return result

#------------------------------------------------------------------------------ 

def attach(transport_instance):
    """
    """
    global _TransportsDict
    global _AvailableTransports
    _AvailableTransports[transport_instance.proto] = True
    # transport_instance.transport.state_changed_callback = on_transport_state_changed
    _TransportsDict[transport_instance.proto] = transport_instance
    lg.out(6, 'gateway.attach : %r' % transport_instance)


def detach(transport_instance):
    """
    """
    global _TransportsDict
    global _AvailableTransports
    if transport_instance.proto not in _AvailableTransports.keys():
        lg.warn('transport [%s] not available' % transport_instance.proto)
        return
    if transport_instance.proto not in _TransportsDict.keys():
        lg.warn('transport [%s] not attached' % transport_instance.proto)
        return
    _AvailableTransports.pop(transport_instance.proto)
    # transport_instance.transport.state_changed_callback = None
    _TransportsDict.pop(transport_instance.proto)
    lg.out(6, 'gateway.detach : %r' % transport_instance)

#------------------------------------------------------------------------------ 

def inbox(info):
    """
    1) The protocol modules write to temporary files and gives us that filename
    2) We unserialize
    3) We check that it is for us
    4) We check that it is from one of our contacts.
    5) We use signed.validate() to check signature and that number fields are numbers
    6) Any other sanity checks we can do and if anything funny we toss out the packet .
    7) Then change the filename to the PackedID that it should be.
       and call the right function(s) for this new packet
       (encryptedblock, scrubber, remotetester, customerservice, ...)
       to dispatch it to right place(s).
    8) We have to keep track of bandwidth to/from everyone, and make a report every 24 hours
       which we send to BitPie.NET sometime in the 24 hours after that.
    """
    global _DoingShutdown
    global _LastInboxPacketTime
    if _DoingShutdown:
        lg.out(6, "gateway.inbox ignoring input since _DoingShutdown ")
        return None
    if info.filename == "" or not os.path.exists(info.filename):
        lg.out(1, "gateway.inbox  ERROR bad filename=" + info.filename)
        return None
    try:
        data = bpio.ReadBinaryFile(info.filename)
    except:
        lg.out(1, "gateway.inbox ERROR reading file " + info.filename)
        return None
    if len(data) == 0:
        lg.out(1, "gateway.inbox ERROR zero byte file from %s://%s" % (info.proto, info.host))
        return None
    try:
        newpacket = signed.Unserialize(data)
    except:
        lg.out(1, "gateway.inbox ERROR during Unserialize data from %s://%s" % (info.proto, info.host))
        lg.exc()
        return None
    if newpacket is None:
        lg.warn("newpacket from %s://%s is None" % (info.proto, info.host))
        return None
    try:
        Command = newpacket.Command
        OwnerID = newpacket.OwnerID
        CreatorID = newpacket.CreatorID
        PacketID = newpacket.PacketID
        Date = newpacket.Date
        Payload = newpacket.Payload
        RemoteID = newpacket.RemoteID
        Signature = newpacket.Signature
        packet_sz = len(data)
    except:
        lg.out(1, "gateway.inbox ERROR during Unserialize data from %s://%s" % (info.proto, info.host))
        lg.out(1, "data length=" + str(len(data)))
        lg.exc()
        fd, filename = tmpfile.make('other', '.bad')
        os.write(fd, data)
        os.close(fd)
        return None
    _LastInboxPacketTime = time.time()
    lg.out(16, "gateway.inbox [%s] signed by %s|%s from %s://%s" % (
        newpacket.Command, nameurl.GetName(newpacket.CreatorID), 
        nameurl.GetName(newpacket.OwnerID), info.proto, info.host))
    return newpacket

#------------------------------------------------------------------------------ 

def outbox(outpacket, wide=False, callbacks={}): 
    """
    Sends `packet` to the network.
    
        :param outpacket: an instance of ``signed.Packet``
        :param wide:  set to True if you need to send the packet 
                      to all contacts of Remote Identity
        :param callbacks: provide a callback methods to get response
    """
    lg.out(16, "gateway.outbox [%s] signed by %s|%s to %s" % (
        outpacket.Command, 
        nameurl.GetName(outpacket.OwnerID),
        nameurl.GetName(outpacket.CreatorID),
        nameurl.GetName(outpacket.RemoteID),))
    return packet_out.create(outpacket, wide, callbacks)

#------------------------------------------------------------------------------ 

def send_work_item(proto, host, filename, description):
    """
    Send a file to remote peer by given transport.
    
    Args:
        workitem (object): object to keep info about the file
        proto (str): identifier of the transport 
        host (str): remote peer's host comes from identity contact
        port (int or str): remote peer's port number if present in the contact method
        dest_filename (str): a last part of the contact method, mostly not used  
    """
    send_file(proto, host, filename, description)

#------------------------------------------------------------------------------ 

def connect_to(proto, host):
    return transport(proto).call('connect_to', host)
    
    
def disconnect_from(proto, host):
    return transport(proto).call('disconnect_from', host)

    
def send_file(proto, host, filename, description=''):
    # print 'send_file', proto, host, filename, description
    return transport(proto).call('send_file', filename, host, description)


def send_file_single(proto, host, filename, description=''):
    return transport(proto).call('send_file_single', filename, host, description)

  
def make_transfer_ID():
    """
    Generate a unique transfer ID.
    """
    global _LastTransferID
    if _LastTransferID is None:
        _LastTransferID = int(str(int(time.time() * 100.0))[4:])
    _LastTransferID += 1
    return _LastTransferID
    
#------------------------------------------------------------------------------ 

def cancel_output_file(transferID, why=None):
    pkt_out, work_item = packet_out.search_by_transfer_id(transferID)
    if pkt_out is None:
        lg.warn('%s is not found' % str(transferID))
        return False
    pkt_out.automat('cancel', why)
    lg.out(14, 'gateway.cancel_output_file    %s' % transferID)
    return True

        
def cancel_input_file(transferID, why=None):
    pkt_in = packet_in.get(transferID)
    assert pkt_in != None
    pkt_in.automat('cancel', why)
    return True


def cancel_outbox_file(proto, host, filename, why=None):
    pkt_out, work_item = packet_out.search(proto, host, filename)
    if pkt_out is None:
        lg.out(2, 'gateway.cancel_outbox_file ERROR packet_out not found: %r' % ((proto, host, filename),))
        return None
    pkt_out.automat('cancel', why)

#------------------------------------------------------------------------------ 

def current_bytes_sent():
    res = {}
    # for transfer_id, info in transfers_out().items():
    #     res[transfer_id] = info.size
    for pkt_out in packet_out.queue():
        for item in pkt_out.items:
            if item.transfer_id:
                res[item.transfer_id] = pkt_out.payloadsize
    return res

def current_bytes_received():
    res = {}
    # for transfer_id, info in transfers_in().items():
    #     res[transfer_id] = info.size
    for pkt_in in packet_in.items().values():
        res[pkt_in.transfer_id] = pkt_in.size 
    return res

#------------------------------------------------------------------------------ 

def shutdown_all_outbox_packets():
    """
    """
    lg.out(12, 'gateway.shutdown_all_outbox_packets, %d live objects at the moment' % len(packet_out.queue()))
    for pkt_out in list(packet_out.queue()):
        pkt_out.event('cancel', 'shutdown')

def shutdown_all_inbox_packets():
    """
    """
    lg.out(12, 'gateway.shutdown_all_inbox_packets, %d live objects at the moment' % len(packet_in.items().values()))
    for pkt_in in list(packet_in.items().values()):
        pkt_in.event('cancel', 'shutdown')

def packets_timeout_loop():
    global _PacketsTimeOutTask
    # lg.out(18, 'gateway.packets_timeout_loop')
#    _PacketsTimeOutTask = reactor.callLater(5, packets_timeout_loop)
#    for pkt_in in packet_in.items().values():
#        if pkt_in.is_timed_out():
#            lg.out(18, 'gateway.packets_timeout_loop %r is timed out' % pkt_in)
#            pkt_in.automat('cancel', 'timeout')
#    for pkt_out in packet_out.queue():
#        if pkt_out.is_timed_out():
#            lg.out(18, 'gateway.packets_timeout_loop %r is timed out' % pkt_out)
#            pkt_out.automat('cancel', 'timeout')

def stop_packets_timeout_loop():
    global _PacketsTimeOutTask
    if _PacketsTimeOutTask:
        if _PacketsTimeOutTask.active():
            _PacketsTimeOutTask.cancel()
        _PacketsTimeOutTask = None

#------------------------------------------------------------------------------ 

def on_transport_state_changed(transport, oldstate, newstate):
    global _TransportsInitialization
    global _TransportsStarting
    global _TransportsStopping
    lg.out(6, 'gateway.on_transport_state_changed in %r : %s->%s' % (
        transport, oldstate, newstate))
    # print _TransportsInitialization, _TransportsStarting, _TransportsStopping
#        if A().state == 'GATE_INIT':
#            if newstate in ['STARTING', 'OFFLINE',]:
#                _TransportsInitialization.remove(proto)
#                if len(_TransportsInitialization) == 0:
#                    A('all-transports-ready')                
#    if A().state == 'UP':
#        if newstate in ['LISTENING', 'OFFLINE',]:
#            _TransportsStarting.remove(proto)
#            if len(_TransportsStarting) == 0:
#                A('network-up')
#    elif A().state == 'DOWN':
#        if newstate == 'OFFLINE':
#            _TransportsStopping.remove(proto)
#            if len(_TransportsStopping) == 0:
#                A('network-down')
    # print _TransportsInitialization, _TransportsStarting, _TransportsStopping
    
def on_transport_initialized(proto, xmlrpcurl=None):
    """
    """
    transport(proto).automat('transport-initialized', xmlrpcurl)
    return True

def on_receiving_started(proto, host, options_modified=None):
    """
    """
    lg.out(6, 'gateway.on_receiving_started %s host=%s' % (proto.upper(), host))
    transport(proto).automat('receiving-started')
    return True

def on_receiving_failed(proto, error_code=None):
    """
    """
    lg.out(6, 'gateway.on_receiving_failed %s    error=[%s]' % (proto.upper(), str(error_code)))
    transport(proto).automat('failed')
    return True

def on_disconnected(proto, result=None):
    """
    """
    lg.out(6, 'gateway.on_disconnected %s    result=%s' % (proto.upper(), str(result)))
    if transports().has_key(proto):
        transport(proto).automat('stopped')
    return True

def on_start_connecting(host):
    """
    """
    return True

def on_session_opened(host, remote_user_id):
    """
    """
    
def on_connection_failed(host, error_message=None):
    """
    """
    
def on_session_closed(host, remote_user_id, reason=None):
    """
    """
    
def on_message_received(host, remote_user_id, data):
    """
    """

def on_register_file_sending(proto, host, receiver_idurl, filename, size=0, description=''):
    """
    Called from transport plug-in when sending a single file were started to some remote peer.
    Must return a unique transfer ID so plug-in will know that ID.
    After finishing that given transfer - that ID is passed to `unregister_file_sending()`.
    """
    lg.out(18, 'gateway.on_register_file_sending %s %s' % (filename, description))
    pkt_out, work_item = packet_out.search(proto, host, filename)
    if pkt_out is None:
        lg.out(2, 'gateway.on_register_file_sending ERROR packet_out not found: %r %r %r' % (
            proto, host, os.path.basename(filename)))
        return None
    transfer_id = make_transfer_ID()
    lg.out(14, '>>> OUT >>> %s (%d) send {%s} via [%s] to %s at %s' % (
        pkt_out.description, transfer_id, os.path.basename(filename), proto, 
        nameurl.GetName(receiver_idurl), host))
    if pkt_out.remote_idurl != receiver_idurl and receiver_idurl:
        lg.out(2, 'gateway.on_register_file_sending ERROR  [%s] [%s]' % (pkt_out.remote_idurl, receiver_idurl))
    pkt_out.automat('register-item', (proto, host, filename, transfer_id))
    return transfer_id

def on_unregister_file_sending(transfer_id, status, bytes_sent, error_message=None):
    """
    Called from transport plug-in after finish sending a single file.
    """
    lg.out(18, 'on_unregister_file_sending %s %s' % (transfer_id, status))
    pkt_out, work_item = packet_out.search_by_transfer_id(transfer_id)
    if pkt_out is None:
        lg.warn('%s is not found' % str(transfer_id))
        return False
    pkt_out.automat('unregister-item', (transfer_id, status, bytes_sent, error_message))
    if status == 'finished':
        lg.out(14, '<<< OUT <<< %s (%d) [%s] %s with %d bytes' % (
            pkt_out.description, transfer_id, work_item.proto, status.upper(), bytes_sent))
    else:
        lg.out(14, '<<< OUT <<< %s (%d) [%s] %s : %s' % (
            pkt_out.description, transfer_id, work_item.proto, str(status).upper(), error_message))
    return True

def on_register_file_receiving(proto, host, sender_idurl, filename, size=0):
    """
    Called from transport plug-in when receiving a single file were started from some peer.
    Must return a unique transfer ID, create a `FileTransferInfo` object and put it into "transfers" list.
    Plug-in's code must create a temporary file and write incoming data into that file.
    """
    transfer_id = make_transfer_ID()
    lg.out(14, '>>> IN >>> %d receive {%s} via [%s] from %s at %s' % (
        transfer_id, os.path.basename(filename), proto, 
        nameurl.GetName(sender_idurl), host))
    packet_in.create(transfer_id).automat('register-item', (proto, host, sender_idurl, filename, size))
    return transfer_id

def on_unregister_file_receiving(transfer_id, status, bytes_received, error_message=''):
    """
    Called from transport plug-in after finish receiving a single file.
    """
    pkt_in = packet_in.get(transfer_id)
    assert pkt_in != None
    if status == 'finished':
        lg.out(14, '<<< IN <<< (%d) [%s] %s with %d bytes' % (
            transfer_id, pkt_in.proto, status.upper(), bytes_received))
    else:
        lg.out(14, '<<< IN <<< (%d) [%s] %s : %s' % (
            transfer_id, pkt_in.proto, status.upper(), error_message))
    pkt_in.automat('unregister-item', (status, bytes_received, error_message))
    return True

def on_cancelled_file_sending(proto, host, filename, size, description='', error_message=None):
    """
    """
    pkt_out, work_item = packet_out.search(proto, host, filename)
    if pkt_out is None:
        lg.out(2, 'gateway.on_cancelled_file_sending packet_out %s %s %s not found - IT IS OK' % (
            proto, host, os.path.basename(filename)))
        return True
    pkt_out.automat('item-cancelled', (proto, host, filename, size, description, error_message))
    lg.out(14, '>>> OUT >>>  {%s} CANCELLED via [%s] to %s : %s' % (
        os.path.basename(filename), proto, host, error_message))
    return True

#------------------------------------------------------------------------------ 

#class InputFile():
#    """
#    Keeps info about single incoming file transfer running at the moment.
#    """
#    def __init__(self, filename, transfer_id, proto, host, idurl, size=0):
#        self.filename = filename
#        self.transfer_id = transfer_id
#        self.proto = proto
#        self.host = host
#        self.remote_idurl = idurl
#        self.size = size
#        self.started = time.time()
        
#------------------------------------------------------------------------------ 

#class OutputFile():
#    def __init__(self, filename, transfer_id, proto, host, remote_idurl, size=0, description=''):
#        self.filename = filename
#        self.transfer_id = transfer_id
#        self.proto = proto
#        self.host = host
#        self.remote_idurl = remote_idurl
#        self.size = size
#        self.description = description
#        self.started = time.time()
        
#------------------------------------------------------------------------------ 

class TransportGateLocalProxy():
    """
    A class to handle calls from transport plug-ins in the main thread.
    """
    def __init__(self):
        self.methods = {
            'transport_initialized': on_transport_initialized,
            'receiving_started': on_receiving_started,
            'receiving_failed': on_receiving_failed,
            'disconnected': on_disconnected,
            'start_connecting': on_start_connecting,
            'session_opened': on_session_opened,
            'message_received': on_message_received,
            'connection_failed': on_connection_failed,
            'register_file_sending': on_register_file_sending,
            'unregister_file_sending': on_unregister_file_sending,
            'register_file_receiving': on_register_file_receiving,
            'unregister_file_receiving': on_unregister_file_receiving,
            'cancelled_file_sending': on_cancelled_file_sending,
        }
        
    def callRemote(self, method, *args):
        m = self.methods.get(method)
        if not m:
            lg.warn('unsupported method: %s' % method)
            return fail('unsupported method: %s' % method) 
        _d = Deferred()
        def _call():
            r = maybeDeferred(m, *args)
            r.addCallback(_d.callback)
            r.addErrback(_d.errback)
        reactor.callLater(0, _call)
        return _d 

#------------------------------------------------------------------------------ 

class TransportGateXMLRPCServer(xmlrpc.XMLRPC):
    """
    XML-RPC server to receive calls from transport plug-ins.
    """

    def __init__(self):
        xmlrpc.XMLRPC.__init__(self, allowNone=True)
        self.methods = {
            'transport_initialized': on_transport_initialized,
            'receiving_started': on_receiving_started,
            'receiving_failed': on_receiving_failed,
            'disconnected': on_disconnected,
            'start_connecting': on_start_connecting,
            'session_opened': on_session_opened,
            'message_received': on_message_received,
            'connection_failed': on_connection_failed,
            'register_file_sending': on_register_file_sending,
            'unregister_file_sending': on_unregister_file_sending,
            'register_file_receiving': on_register_file_receiving,
            'unregister_file_receiving': on_unregister_file_receiving,
            'cancelled_file_sending': on_cancelled_file_sending,
        }

    def lookupProcedure(self, procedurePath):
        try:
            return self.methods[procedurePath]
        except KeyError, e:
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                        "procedure %s not found" % procedurePath)

    def listProcedures(self):
        return self.methods.keys()

#------------------------------------------------------------------------------ 

def parseCommandLine():
    oparser = optparse.OptionParser()
    oparser.add_option("-d", "--debug", dest="debug", type="int", help="set debug level")
    oparser.set_default('debug', 10)
    oparser.add_option("-t", "--tcpport", dest="tcpport", type="int", help="specify port for TCP transport")
    oparser.set_default('tcpport', settings.getTCPPort())
    oparser.add_option("-u", "--udpport", dest="udpport", type="int", help="specify port for UDP transport")
    oparser.set_default('udpport', settings.getUDPPort())
    oparser.add_option("-p", "--dhtport", dest="dhtport", type="int", help="specify UDP port for DHT network")
    oparser.set_default('dhtport', settings.getDHTPort())
    oparser.add_option("-s", "--packetsize", dest="packetsize", type="int", help="set size of UDP datagrams")
    oparser.set_default('packetsize', 480)
    (options, args) = oparser.parse_args()
    return options, args

def main():
    lg.life_begins()
    bpio.init()
    settings.init()
    misc.init()
    identitycache.init()
    from crypt import key
    key.InitMyKey()
    (options, args) = parseCommandLine()
    settings.override('transport.transport-tcp.transport-tcp-port', options.tcpport)
    settings.override('transport.transport-udp.transport-udp-port', options.udpport)
    settings.override('network.network-dht-port', options.dhtport)
    lg.set_debug_level(options.debug)
    tmpfile.init()
    if True:
        import lib.udp
        lib.udp.listen(options.udpport)
        import dht.dht_service
        dht.dht_service.init(options.dhtport)
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)
    init(['tcp', 'udp'])
    start()
    globals()['num_in'] = 0
    def _in(a,b,c,d):
        lg.out(2, 'INBOX %d : %r' % (globals()['num_in'], a))
        globals()['num_in'] += 1
        return True
    callback.add_inbox_callback(_in)
    if len(args) > 0:
        globals()['num_out'] = 0
        def _s():
            p = signed.Packet(commands.Data(), misc.getLocalID(), 
                              misc.getLocalID(), misc.getLocalID(), 
                              bpio.ReadBinaryFile(args[1]), args[0])
            outbox(p, wide=True)
            lg.out(2, 'OUTBOX %d : %r' % (globals()['num_out'], p))
            globals()['num_out'] += 1
        old_state_changed = transport('udp').state_changed 
        def new_state_changed(oldstate, newstate, event, arg):
            old_state_changed(oldstate, newstate, event, arg)
            if newstate == 'LISTENING':
                reactor.callLater(1, _s)
        transport('udp').state_changed = new_state_changed 
        # t = task.LoopingCall(_s)
        # reactor.callLater(5, t.start, 60, True)
        # reactor.callLater(2, t.stop)
        
    reactor.run()
    
if __name__ == "__main__":
    main()
      




