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

    <a href="http://bitdust.io/automats/p2p_connector/p2p_connector.png" target="_blank">
    <img src="http://bitdust.io/automats/p2p_connector/p2p_connector.png" style="max-width:100%;">
    </a>

The ``p2p_connector()`` state machine manages the user's connection with other remote users.

It calls other state machines and works with them in parallel.

Control passes to the ``network_connector()`` automat which prepares the Internet connection.

Next, there is a start of transport protocols.

User Identity file that contains a public user address get updated. 
The new version of the file is sent to the Identity server 
in order for that to all the other users can find out the contact with user.

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

import sys

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio

from main import settings

from lib import misc
from lib import net_misc

from automats import automat
from automats import global_state

from dht import dht_service

from transport import callback

from services import driver

from userid import my_id

import propagate
import ratings
import network_connector

#------------------------------------------------------------------------------ 

_P2PConnector = None
_ActiveProtocols = set()

#------------------------------------------------------------------------------

def active_protos():
    global _ActiveProtocols
    return _ActiveProtocols


def inbox(newpacket, info, status, message):
    # here need to mark this protocol as working
    if info.proto in ['tcp',]:
        if not net_misc.IpIsLocal(str(info.host).split(':')[0]):
            # but we want to check that this packet is come from the Internet, not our local network
            # because we do not want to use this proto as first method if it is not working for all
            if info.proto not in active_protos():
                lg.out(2, 'p2p_connector.Inbox [transport_%s] seems to work !!!!!!!!!!!!!!!!!!!!!' % info.proto)
                lg.out(2, '                    We got the first packet from %s://%s' % (info.proto, str(info.host)))
                active_protos().add(info.proto)
    elif info.proto in ['udp',]:
        if info.proto not in active_protos():
            lg.out(2, 'p2p_connector.Inbox [transport_%s] seems to work !!!!!!!!!!!!!!!!!!!!!' % info.proto)
            lg.out(2, '                    We got the first packet from %s://%s' % (info.proto, str(info.host)))
            active_protos().add(info.proto)
    A('inbox-packet', (newpacket, info, status, message))

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """    
    global _P2PConnector
    if _P2PConnector is None:
        _P2PConnector = P2PConnector('p2p_connector', 'AT_STARTUP', 6, True)
    if event is not None:
        _P2PConnector.automat(event, arg)
    return _P2PConnector


def Destroy():
    """
    Destroy p2p_connector() automat and remove its instance from memory.
    """
    global _P2PConnector
    if _P2PConnector is None:
        return
    _P2PConnector.destroy()
    del _P2PConnector
    _P2PConnector = None


class P2PConnector(automat.Automat):
    """
    """

    timers = {
        'timer-20sec': (20.0, ['INCOMMING?']),
        }
    
    def init(self):
        self.log_events = True
        self.identity_changed = False
        self.version_number = ''

    def state_changed(self, oldstate, newstate, event, arg):
        global_state.set_global_state('P2P ' + newstate)
        # tray_icon.state_changed(network_connector.A().state, self.state)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'NETWORK?'
                self.doInit(arg)
                network_connector.A('reconnect')
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
                self.doRestartFireHire(arg)
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
                self.doRestartBackupMonitor(arg)
                self.doRestartCustomersRejector(arg)
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
            if event == 'my-id-updated' and not self.isMyIdentityChanged(arg) :
                self.state = 'CONTACTS'
                self.doPropagateMyIdentity(arg)
            elif event == 'my-id-updated' and self.isMyIdentityChanged(arg) :
                self.state = 'NETWORK?'
                network_connector.A('reconnect')
        return None

    def isUsingBestProto(self, arg):
        """
        Condition method.
        """
        return self._check_to_use_best_proto()

    def isMyIdentityChanged(self, arg):
        """
        Condition method.
        """
        return self.identity_changed

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        propagate.single(arg, wide=True)

    def doInit(self, arg):
        self.version_number = bpio.ReadTextFile(settings.VersionNumberFile()).strip()
        lg.out(4, 'p2p_connector.doInit RevisionNumber=%s' % str(self.version_number))
        callback.add_inbox_callback(inbox)
        
    def doUpdateMyIdentity(self, arg):
        self.identity_changed = self._update_my_identity()
        self.automat('my-id-updated')
        
    def doPropagateMyIdentity(self, arg):
        #TODO need to run this actions one by one, not in parallel - use Defered chain
        propagate.update()
        propagate.write_to_dht()
        dht_service.set_node_data('idurl', my_id.getLocalID())
        d = propagate.start(wide=True)
        d.addCallback(lambda contacts_list: self.automat('my-id-propagated', contacts_list))

    def doPopBestProto(self, arg):
        self._pop_active_proto()

    def doInitRatings(self, arg):
        ratings.init()

    def doRestartBackupMonitor(self, arg):
        """
        Action method.
        """
        if driver.is_started('service_backup_monitor'):
            from storage import backup_monitor
            backup_monitor.A('restart')

    def doRestartCustomersRejector(self, arg):
        """
        Action method.
        """
        if driver.is_started('service_customer_patrol'):
            from supplier import customers_rejector
            customers_rejector.A('restart')

    def doRestartFireHire(self, arg):
        """
        Action method.
        """
        if driver.is_started('service_employer'):
            from customer import fire_hire
            fire_hire.A('restart')

    def _check_to_use_best_proto(self):
        #out(4, 'p2p_connector._check_to_use_best_proto active_protos()=%s' % str(active_protos()))
        #if no incomming traffic - do nothing
        if len(active_protos()) == 0:
            return True
        lid = my_id.getLocalIdentity()
        order = lid.getProtoOrder()
        #if no protocols in local identity - do nothing
        if len(order) == 0:
            return True
        first = order[0]
        #if first contact in local identity is not working yet
        #but there is another working methods - switch first method
        if first not in active_protos():
            lg.out(2, 'p2p_connector._check_to_use_best_proto first contact (%s) is not working!   active_protos()=%s' % (first, str(active_protos())))
            return False
        #if tcp contact is on first place and it is working - we are VERY HAPPY! - no need to change anything - return False
        if first == 'tcp' and 'tcp' in active_protos():
            return True
        #but if tcp method is not the first and it works - we want to TURN IT ON! - return True
        if first != 'tcp' and 'tcp' in active_protos():
            lg.out(2, 'p2p_connector._check_to_use_best_proto tcp is not first but it works active_protos()=%s' % str(active_protos()))
            return False
        #if we are using udp and it is working - this is fantastic!
        if first == 'udp' and 'udp' in active_protos():
            return True
        #udp seems to be working and first contact is not working - so switch to udp
        if first != 'udp' and 'udp' in active_protos():
            lg.out(2, 'p2p_connector._check_to_use_best_proto udp is not first but it works active_protos()=%s' % str(active_protos()))
            return False
        #in other cases - do nothing
        return True

    def _pop_active_proto(self):
        if len(active_protos()) == 0:
            return
        lid = my_id.getLocalIdentity()
        order = lid.getProtoOrder()
        first = order[0]
        wantedproto = ''
        #if first contact in local identity is not working yet
        #but there is another working methods - switch first method
        if first not in active_protos():
            #take (but not remove) any item from the set
            wantedproto = active_protos().pop()
            active_protos().add(wantedproto)
        #if udp method is not the first but it works - switch to udp
        if first != 'udp' and 'udp' in active_protos():
            wantedproto = 'udp'
        #if tcp method is not the first but it works - switch to tcp
        if first != 'tcp' and 'tcp' in active_protos():
            wantedproto = 'tcp'
        lg.out(4, 'p2p_connector.PopWorkingProto will pop %s contact order=%s active_protos()=%s' % (
            wantedproto, str(order), str(active_protos())))
        # now move best proto on the top
        # other users will use this method to send to us
        lid.popProtoContact(wantedproto)
        # save local id
        # also need to propagate our identity
        # other users must know our new contacts
        my_id.setLocalIdentity(lid)
        my_id.saveLocalIdentity() 
    
#    def _is_id_changed(self, changes):
#        s = set(changes)
#        if s.intersection([
#            'transport.transport-tcp.transport-tcp-enable',
#            'transport.transport-tcp.transport-tcp-receiving-enable',
#            'transport.transport-udp.transport-udp-enable',
#            'transport.transport-udp.transport-udp-receiving-enable',
#            ]):
#            return True
#        if 'transport.transport-tcp.transport-tcp-port' in s and settings.enableTCP():
#            return True
#        # if 'transport.transport-udp.transport-udp-port' in s and settings.enableUDP():
#        #     return True
#        return False
    
    def _update_my_identity(self):
        """
        If some transports was enabled or disabled we want to update identity contacts.
        Just empty all of the contacts and create it again in the same order.
        """
        #getting local identity
        lid = my_id.getLocalIdentity()
        oldcontats = lid.getContactsByProto()
        nowip = misc.readExternalIP()
        order = lid.getProtoOrder()
        lid.clearContacts()
        #prepare contacts data
        cdict = {}
        cdict['tcp'] = 'tcp://'+nowip+':'+str(settings.getTCPPort())
        cdict['udp'] = 'udp://%s@%s' % (lid.getIDName().lower(), lid.getIDHost())
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
                active_protos().discard(proto)
        del order
    #    #if IP is not external and upnp configuration was failed for some reasons
    #    #we may want to use another contact methods, NOT tcp
    #    if IPisLocal() and run_upnpc.last_result('tcp') != 'upnp-done':
    #        lg.out(4, 'p2p_connector.update_identity want to push tcp contact: local IP, no upnp ...')
    #        lid.pushProtoContact('tcp')
        #update software version number
        repo, location = misc.ReadRepoLocation()
        lid.version = (self.version_number.strip() + ' ' + repo.strip() + ' ' + bpio.osinfo().strip()).strip()
        #generate signature with changed content
        lid.sign()
        #remember the identity
        my_id.setLocalIdentity(lid)
        #finally saving local identity
        my_id.saveLocalIdentity()
        lg.out(4, 'p2p_connector.UpdateIdentity')
        lg.out(4, '    version: %s' % str(lid.version))
        lg.out(4, '    contacts: %s' % str(lid.contacts))
        #_UpnpResult.clear()
        changed = False
        for proto, contact in my_id.getLocalIdentity().getContactsByProto().items():
            if proto not in oldcontats.keys():
                changed = True
                break
            if contact != oldcontats.get(proto, ''):
                changed = True
                break
        return changed

