#!/usr/bin/env python
#p2p_connector.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: p2p_connector

.. raw:: html

    <a href="http://bitpie.net/automats/p2p_connector/p2p_connector.png" target="_blank">
    <img src="http://bitpie.net/automats/p2p_connector/p2p_connector.png" style="max-width:100%;">
    </a>

The ``p2p_connector()`` state machine manages the user's connection with other remote users.

It calls other state machines and works with them in parallel.

Control passes to the ``network_connector()`` automat which prepares the Internet connection.

Next, there is a start of transport protocols.

User Identity file that contains a public user address get updated. 
The new version of the file is sent to the Identity server 
in order for that to all the other users can find out the contact with user.

Next, control is passed to the state machine ``central_connector()``, 
which will make the connection to the Central server.

Then, as soon as user receive the first packet from any of the remote users, 
the ``p2p_connector()`` goes into state "CONNECTED".

If user changes his network settings all process should be restarted.

EVENTS:
    * :red:`inbox-packet`
    * :red:`init`
    * :red:`my-id-propagated`
    * :red:`my-id-updated`
    * :red:`network_connector.state`
    * :red:`ping-contact`
    * :red:`reconnect`
    * :red:`timer-20sec`
"""

import os
import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in p2p_connector.py')
from twisted.internet.defer import Deferred, DeferredList, maybeDeferred, succeed
from twisted.internet.task import LoopingCall

import lib.dhnio as dhnio
import lib.misc as misc
import lib.settings as settings
import lib.dhnnet as dhnnet
import lib.automat as automat
import lib.automats as automats

import dht.dht_service as dht_service

import transport.callback as callback

import raid.raid_worker as raid_worker

import initializer
import network_connector
import backup_monitor
import backup_db_keeper
import list_files_orator
import fire_hire
import data_sender
import contact_status
import identitypropagate
import ratings
import dhnicon


#------------------------------------------------------------------------------ 

_P2PConnector = None
_RevisionNumber = None
_WorkingProtocols = set()
_IdentityChangedFlag = False

#------------------------------------------------------------------------------

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """    
    global _P2PConnector
    if _P2PConnector is None:
        _P2PConnector = P2PConnector('p2p_connector', 'AT_STARTUP', 6)
    if event is not None:
        _P2PConnector.automat(event, arg)
    return _P2PConnector

class P2PConnector(automat.Automat):
    """
    """

    timers = {
        'timer-20sec': (20.0, ['INCOMMING?']),
        }
    
    def init(self):
        self.ackCounter = 0

    def state_changed(self, oldstate, newstate):
        automats.set_global_state('P2P ' + newstate)
        initializer.A('p2p_connector.state', newstate)
        # central_connector.A('p2p_connector.state', newstate)
        dhnicon.state_changed(network_connector.A().state, self.state)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'NETWORK?'
                self.doInit(arg)
                network_connector.A('init')
                backup_monitor.A('init')
                backup_db_keeper.A('init')
                list_files_orator.A('init')
                fire_hire.A('init')
                data_sender.A('init')
                raid_worker.A('init')
        #---NETWORK?---
        elif self.state == 'NETWORK?':
            if ( event == 'network_connector.state' and arg == 'DISCONNECTED' ) :
                self.state = 'DISCONNECTED'
            elif ( event == 'network_connector.state' and arg == 'CONNECTED' ) :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
        #---CONTACTS---
        elif self.state == 'CONTACTS':
            if event == 'my-id-propagated' :
                self.state = 'INCOMMING?'
                fire_hire.A('restart')
            elif ( ( event == 'network_connector.state' and arg == 'CONNECTED' ) ) or event == 'reconnect' :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
        #---INCOMMING?---
        elif self.state == 'INCOMMING?':
            if event == 'inbox-packet' and not self.isUsingBestProto(arg) :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
                self.doPopBestProto(arg)
            elif event == 'inbox-packet' and self.isUsingBestProto(arg) :
                self.state = 'CONNECTED'
                self.doInitRatings(arg)
                backup_monitor.A('restart')
            elif event == 'reconnect' or ( event == 'network_connector.state' and arg == 'CONNECTED' ) :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
            elif event == 'timer-20sec' or ( event == 'network_connector.state' and arg == 'DISCONNECTED' ) :
                self.state = 'DISCONNECTED'
                self.doInitRatings(arg)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'ping-contact' :
                self.doSendMyIdentity(arg)
            elif ( event == 'network_connector.state' and arg not in [ 'CONNECTED' , 'DISCONNECTED' ] ) :
                self.state = 'NETWORK?'
            elif ( event == 'network_connector.state' and arg == 'DISCONNECTED' ) :
                self.state = 'DISCONNECTED'
            elif event == 'reconnect' or ( event == 'network_connector.state' and arg == 'CONNECTED' ) :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'ping-contact' :
                self.doSendMyIdentity(arg)
            elif ( event == 'network_connector.state' and arg not in [ 'CONNECTED', 'DISCONNECTED', ] ) :
                self.state = 'NETWORK?'
            elif event == 'inbox-packet' or event == 'reconnect' or ( ( event == 'network_connector.state' and arg == 'CONNECTED' ) ) :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
        #---MY_IDENTITY---
        elif self.state == 'MY_IDENTITY':
            if event == 'my-id-updated' :
                self.state = 'CONTACTS'
                self.doPropagateMyIdentity(arg)

    def isUsingBestProto(self, arg):
        return DoWeUseTheBestProto()

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        identitypropagate.single(arg, wide=True)

    def doInit(self, arg):
        global _RevisionNumber
        _RevisionNumber = dhnio.ReadTextFile(settings.RevisionNumberFile()).strip()
        dhnio.Dprint(4, 'p2p_connector.doInit RevisionNumber=%s' % str(_RevisionNumber))
        callback.add_inbox_callback(Inbox)
        
    def doUpdateMyIdentity(self, arg):
        UpdateIdentity()
        
    def doPropagateMyIdentity(self, arg):
        identitypropagate.update()
        identitypropagate.write_to_dht()
        dht_service.set_node_data('idurl', misc.getLocalID())
        d = identitypropagate.start()
        d.addCallback(lambda contacts_list: self.automat('my-id-propagated', contacts_list))

    def doPopBestProto(self, arg):
        PopWorkingProto()

    def doInitRatings(self, arg):
        ratings.init()

#-------------------------------------------------------------------------------

def Inbox(newpacket, info, status, message):
    global _WorkingProtocols
    # here we mark this protocol as working
    if info.proto in ['tcp', 'udp',]:
        if not dhnnet.IpIsLocal(str(info.host).split(':')[0]):
            # but we want to check that this packet is come from the Internet, not our local network
            # because we do not want to use this proto as first method if it is not working for all
            if info.proto not in _WorkingProtocols:
                dhnio.Dprint(2, 'p2p_connector.Inbox [transport_%s] seems to work !!!!!!!!!!!!!!!!!!!!!' % info.proto)
                dhnio.Dprint(2, '                    We got the first packet from %s://%s' % (info.proto, str(info.host)))
                _WorkingProtocols.add(info.proto)
    elif info.proto in ['cspace', 'dhtudp',]:
        if info.proto not in _WorkingProtocols:
            dhnio.Dprint(2, 'p2p_connector.Inbox [transport_%s] seems to work !!!!!!!!!!!!!!!!!!!!!' % info.proto)
            dhnio.Dprint(2, '                    We got the first packet from %s://%s' % (info.proto, str(info.host)))
            _WorkingProtocols.add(info.proto)
    A('inbox-packet', (newpacket, info, status, message))


def TransportUDPSessionStateChanged(automatindex, oldstate, newstate):
    if newstate != 'CONNECTED':
        return
    sess = automat.objects().get(automatindex, None)
    if sess is None:
        return
    idurl = sess.remote_idurl
    if idurl is None:
        return
    if contact_status.isOffline(idurl):
        A('ping-contact', idurl)

#------------------------------------------------------------------------------ 

def IPisLocal():
    externalip = misc.readExternalIP()
    localip = misc.readLocalIP()
    return localip != externalip


def UpdateIdentity():
    """
    If some transports was enabled or disabled we want to update identity contacts.
    Just empty all of the contacts and create it again in the same order.
    """
    global _RevisionNumber
    global _WorkingProtocols

    #getting local identity
    lid = misc.getLocalIdentity()
    oldcontats = lid.getContactsByProto()
    nowip = misc.readExternalIP()
    order = lid.getProtoOrder()
    lid.clearContacts()

    #prepare contacts data
    cdict = {}
    cdict['tcp'] = 'tcp://'+nowip+':'+settings.getTCPPort()
#    if transport_control._TransportSSHEnable:
#        cdict['ssh'] = 'ssh://'+nowip+':'+settings.getSSHPort()
#    if transport_control._TransportHTTPEnable:
#        cdict['http'] = 'http://'+nowip+':'+settings.getHTTPPort()
#    if transport_control._TransportQ2QEnable:
#        cdict['q2q'] = 'q2q://'+settings.getQ2Quserathost()
#    if transport_control._TransportEmailEnable:
#        cdict['email'] = 'email://'+settings.getEmailAddress()
    # if transport_control._TransportCSpaceEnable:
    #     cdict['cspace'] = 'cspace://'+settings.getCSpaceKeyID()
    # if transport_control._TransportUDPEnable:
    #     if stun.getUDPClient() is None or stun.getUDPClient().externalAddress is None:
    #         cdict['udp'] = 'udp://'+nowip+':'+settings.getUDPPort()
    #     else:
    #         cdict['udp'] = 'udp://'+stun.getUDPClient().externalAddress[0]+':'+str(stun.getUDPClient().externalAddress[1])
    cdict['dhtudp'] = 'dhtudp://%s@%s' % (lid.getIDName().lower(), 
                                          lid.getIDHost())

    #making full order list
    for proto in cdict.keys():
        if proto not in order:
            order.append(proto)

    #add contacts data to the local identity
    #check if some transport is not installed
    for proto in order:
        if settings.transportIsEnabled(proto) and settings.transportReceivingIsEnabled(proto):
            contact = cdict.get(proto, None)
            if contact is not None:
                lid.setProtoContact(proto, contact)
        else:
            # if protocol is disabled - mark this
            # because we may want to turn it on in the future
            _WorkingProtocols.discard(proto)
            
    #misc.setLocalIdentity(lid)

    del order

#    #if IP is not external and upnp configuration was failed for some reasons
#    #we want to use another contact methods, NOT tcp or ssh
#    if IPisLocal() and run_upnpc.last_result('tcp') != 'upnp-done':
#        dhnio.Dprint(4, 'p2p_connector.update_identity want to push tcp contact: local IP, no upnp ...')
#        lid.pushProtoContact('tcp')
#        misc.setLocalIdentity(lid)

    #update software version number
    revnum = _RevisionNumber.strip()
    repo, location = misc.ReadRepoLocation()
    lid.version = (revnum.strip() + ' ' + repo.strip() + ' ' + dhnio.osinfo().strip()).strip()
    
    #generate signature with changed content
    lid.sign()
    
    #remember the identity
    misc.setLocalIdentity(lid)

    #finally saving local identity
    misc.saveLocalIdentity()
    dhnio.Dprint(4, 'p2p_connector.UpdateIdentity')
    dhnio.Dprint(4, '    version: %s' % str(lid.version))
    dhnio.Dprint(4, '    contacts: %s' % str(lid.contacts))
    #_UpnpResult.clear()
    
    changed = False
    for proto, contact in misc.getLocalIdentity().getContactsByProto().items():
        if proto not in oldcontats.keys():
            changed = True
            break
        if contact != oldcontats.get(proto, ''):
            changed = True
            break
    if changed:
        dhnio.Dprint(4, 'p2p_connector.UpdateIdentity want to RECONNECT because some contacts was changed')
        network_connector.A('reconnect')
        
    A('my-id-updated')

    
def UpdateTransports(arg):
    global _IdentityChangedFlag
    dhnio.Dprint(4, 'p2p_connector.UpdateTransports')
    # if _IdentityChangedFlag:
    #     _IdentityChangedFlag = False
    #     network_connector.A('reconnect')
    A('transports-updated')


def IDchanged(changes):
    s = set(changes)
    if s.intersection([
        'transport.transport-tcp.transport-tcp-enable',
        'transport.transport-tcp.transport-tcp-receiving-enable',
        # 'transport.transport-udp.transport-udp-enable',
        # 'transport.transport-udp.transport-udp-receiving-enable',
        # 'transport.transport-cspace.transport-cspace-enable',
        # 'transport.transport-cspace.transport-cspace-receiving-enable',
        'transport.transport-dhtudp.transport-dhtudp-enable',
        'transport.transport-dhtudp.transport-dhtudp-receiving-enable',
        # 'transport.transport-ssh.transport-ssh-enable',
        # 'transport.transport-http.transport-http-enable',
        # 'transport.transport-email.transport-email-enable',
        # 'transport.transport-q2q.transport-q2q-enable',
        # 'transport.transport-skype.transport-skype-enable',
        ]):
        return True
    if 'transport.transport-tcp.transport-tcp-port' in s and settings.enableTCP():
        return True
    # if 'transport.transport-udp.transport-udp-port' in s and settings.enableUDP():
    #     return True
#    if 'transport.transport-ssh.transport-ssh-port' in s and settings.enableSSH():
#        return True
#    if 'transport.transport-q2q.transport-q2q-username' in s and settings.enableQ2Q():
#        return True
#    if 'transport.transport-cspace.transport-cspace-key-id' in s and settings.enableCSpace():
#        return True
#    if 'transport.transport-http.transport-http-server-port' in s and settings.enableHTTP():
#        return True
    if 'transport.transport-dhtudp.transport-dhtudp-port' in s and settings.enableDHTUDP():
        return True
    if 'transport.transport-dhtudp.transport-dht-port' in s and settings.enableDHTUDP():
        return True
    return False

#    global _SettingsChanges
#    if _SettingsChanges.intersection([
#        'transport.transport-tcp.transport-tcp-enable',
#        'transport.transport-ssh.transport-ssh-enable',
#        'transport.transport-http.transport-http-enable',
#        'transport.transport-email.transport-email-enable',
#        'transport.transport-q2q.transport-q2q-enable',
#        'transport.transport-cspace.transport-cspace-enable',
#        'transport.transport-skype.transport-skype-enable',
#        ]):
#        return True
#    if 'transport.transport-tcp.transport-tcp-port' in _SettingsChanges and settings.enableTCP():
#        return True
#    if 'transport.transport-ssh.transport-ssh-port' in _SettingsChanges and settings.enableSSH():
#        return True
#    if 'transport.transport-q2q.transport-q2q-username' in _SettingsChanges and settings.enableQ2Q():
#        return True
#    if 'transport.transport-http.transport-http-server-port' in _SettingsChanges and settings.enableHTTP():
#        return True
#    if 'transport.transport-tcp.transport-tcp-port' in _SettingsChanges and settings.enableTCP():
#        return True
#    if 'transport.transport-cspace.transport-cspace-key-id' in _SettingsChanges and settings.enableCSpace():
#        return True
#    return False


def DoWeUseTheBestProto():
    global _WorkingProtocols
    #dhnio.Dprint(4, 'p2p_connector.DoWeUseTheBestProto _WorkingProtocols=%s' % str(_WorkingProtocols))
    #if no incomming traffic - do nothing
    if len(_WorkingProtocols) == 0:
        return True
    lid = misc.getLocalIdentity()
    order = lid.getProtoOrder()
    #if no protocols in local identity - do nothing
    if len(order) == 0:
        return True
    first = order[0]
    #if first contact in local identity is not working yet
    #but there is another working methods - switch first method
    if first not in _WorkingProtocols:
        dhnio.Dprint(2, 'p2p_connector.DoWeUseTheBestProto first contact (%s) is not working!   _WorkingProtocols=%s' % (first, str(_WorkingProtocols)))
        return False
    #if tcp contact is on first place and it is working - we are VERY HAPPY! - no need to change anything - return False
    if first == 'tcp' and 'tcp' in _WorkingProtocols:
        return True
    #but if tcp method is not the first and it works - we want to TURN IT ON! - return True
    if first != 'tcp' and 'tcp' in _WorkingProtocols:
        dhnio.Dprint(2, 'p2p_connector.DoWeUseTheBestProto tcp is not first but it works _WorkingProtocols=%s' % str(_WorkingProtocols))
        return False
    #if we are using dhtudp and it is working - this is fantastic!
    if first == 'dhtudp' and 'dhtudp' in _WorkingProtocols:
        return True
    #if we are using cspace and it is working - this is fantastic!
    # if transport_control._TransportCSpaceEnable:
    #     if first == 'cspace' and 'cspace' in _WorkingProtocols:
    #         return True
    #if we are using udp and it is working - not so bad
    # if transport_control._TransportUDPEnable:
    #     if first == 'udp' and 'udp' in _WorkingProtocols:
    #         return True
    #dhtudp seems to be working and first contact is not working - so switch to dhtudp
    if first != 'dhtudp' and 'dhtudp' in _WorkingProtocols:
        dhnio.Dprint(2, 'p2p_connector.DoWeUseTheBestProto dhtudp is not first but it works _WorkingProtocols=%s' % str(_WorkingProtocols))
        return False
    #cspace seems to be working and first contact is not working - so switch to cspace
    # if transport_control._TransportCSpaceEnable:
    #     if first != 'cspace' and 'cspace' in _WorkingProtocols:
    #         dhnio.Dprint(2, 'p2p_connector.DoWeUseTheBestProto cspace is not first but it works _WorkingProtocols=%s' % str(_WorkingProtocols))
    #         return False
    #udp is working - we ca use it if all others is failed
    # if transport_control._TransportUDPEnable:
    #     if first != 'udp' and 'udp' in _WorkingProtocols:
    #         dhnio.Dprint(2, 'p2p_connector.DoWeUseTheBestProto udp is not first but it works _WorkingProtocols=%s' % str(_WorkingProtocols))
    #         return False
    #in other cases - do nothing
    return True


def PopWorkingProto():
    global _WorkingProtocols
    if len(_WorkingProtocols) == 0:
        return
    lid = misc.getLocalIdentity()
    order = lid.getProtoOrder()
    first = order[0]
    wantedproto = ''
    #if first contact in local identity is not working yet
    #but there is another working methods - switch first method
    if first not in _WorkingProtocols:
        #take (but not remove) any item from the set
        wantedproto = _WorkingProtocols.pop()
        _WorkingProtocols.add(wantedproto)
    # if q2q method is not the first but it works - switch to q2q
    # disabled because we do not use q2q now
    # if first != 'q2q' and 'q2q' in _WorkingProtocols:
    #     wantedproto = 'q2q'
    #if udp method is not the first but it works - switch to udp
    # if transport_control._TransportUDPEnable:
    #     if first != 'udp' and 'udp' in _WorkingProtocols:
    #         wantedproto = 'udp'
    #if cspace method is not the first but it works - switch to cspace
    # if transport_control._TransportCSpaceEnable:
    #     if first != 'cspace' and 'cspace' in _WorkingProtocols:
    #         wantedproto = 'cspace'
    #if dhtudp method is not the first but it works - switch to dhtudp
    if first != 'dhtudp' and 'dhtudp' in _WorkingProtocols:
        wantedproto = 'dhtudp'
    #if tcp method is not the first but it works - switch to tcp
    if first != 'tcp' and 'tcp' in _WorkingProtocols:
        wantedproto = 'tcp'
    dhnio.Dprint(4, 'p2p_connector.PopWorkingProto will pop %s contact   order=%s _WorkingProtocols=%s' % (wantedproto, str(order), str(_WorkingProtocols)))
    # now move best proto on the top
    # other users will use this method to send to us
    lid.popProtoContact(wantedproto)
    # save local id
    # also need to propagate our identity
    # other users must know our new contacts
    misc.setLocalIdentity(lid)
    misc.saveLocalIdentity() 


def WorkingProtos():
    global _WorkingProtocols
    return _WorkingProtocols


