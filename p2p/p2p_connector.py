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
    * :red:`check-synchronize`
    * :red:`inbox-packet`
    * :red:`init`
    * :red:`my-id-propagated`
    * :red:`my-id-updated`
    * :red:`network_connector.state`
    * :red:`ping-contact`
    * :red:`timer-20sec`
"""

#------------------------------------------------------------------------------ 

_Debug = True

#------------------------------------------------------------------------------ 

import sys

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio

from main import settings

from lib import net_misc

from automats import automat
from automats import global_state

from dht import dht_service

from contacts import identitycache

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
                if _Debug:
                    lg.out(2, 'p2p_connector.Inbox [transport_%s] seems to work !!!!!!!!!!!!!!!!!!!!!' % info.proto)
                    lg.out(2, '                    We got packet from %s://%s' % (info.proto, str(info.host)))
                active_protos().add(info.proto)
    elif info.proto in ['udp',]:
        if info.proto not in active_protos():
            if _Debug:
                lg.out(2, 'p2p_connector.Inbox [transport_%s] seems to work !!!!!!!!!!!!!!!!!!!!!' % info.proto)
                lg.out(2, '                    We got packet from %s://%s' % (info.proto, str(info.host)))
            active_protos().add(info.proto)
    elif info.proto in ['proxy',]:
        if info.proto not in active_protos():
            if _Debug:
                lg.out(2, 'p2p_connector.Inbox [transport_%s] seems to work !!!!!!!!!!!!!!!!!!!!!' % info.proto)
                lg.out(2, '                    We got packet from %s://%s' % (info.proto, str(info.host)))
            active_protos().add(info.proto)
    A('inbox-packet', (newpacket, info, status, message))
    return False

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """    
    global _P2PConnector
    if _P2PConnector is None:
        _P2PConnector = P2PConnector(
            'p2p_connector', 'AT_STARTUP', 6, _Debug)
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
    
    def state_changed(self, oldstate, newstate, event, arg):
        global_state.set_global_state('P2P ' + newstate)
        # tray_icon.state_changed(network_connector.A().state, self.state)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'NETWORK?'
                self.NeedPropagate=True
                self.doInit(arg)
                network_connector.A('reconnect')
        #---NETWORK?---
        elif self.state == 'NETWORK?':
            if ( event == 'network_connector.state' and arg == 'DISCONNECTED' ) :
                self.state = 'DISCONNECTED'
            elif ( event == 'network_connector.state' and arg == 'CONNECTED' ) :
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
            elif event == 'timer-20sec' or ( event == 'network_connector.state' and arg == 'DISCONNECTED' ) :
                self.state = 'DISCONNECTED'
                self.doInitRatings(arg)
            elif event == 'check-synchronize' or ( event == 'network_connector.state' and arg == 'CONNECTED' ) :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'ping-contact' :
                self.doSendMyIdentity(arg)
            elif ( event == 'network_connector.state' and arg not in [ 'CONNECTED' , 'DISCONNECTED' ] ) :
                self.state = 'NETWORK?'
            elif ( event == 'network_connector.state' and arg == 'DISCONNECTED' ) :
                self.state = 'DISCONNECTED'
            elif event == 'check-synchronize' or ( event == 'network_connector.state' and arg == 'CONNECTED' ) :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'ping-contact' :
                self.doSendMyIdentity(arg)
            elif ( event == 'network_connector.state' and arg not in [ 'CONNECTED', 'DISCONNECTED', ] ) :
                self.state = 'NETWORK?'
            elif event == 'inbox-packet' or event == 'check-synchronize' or ( ( event == 'network_connector.state' and arg == 'CONNECTED' ) ) :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
        #---MY_IDENTITY---
        elif self.state == 'MY_IDENTITY':
            if event == 'my-id-updated' and self.isMyContactsChanged(arg) :
                self.state = 'NETWORK?'
                self.NeedPropagate=True
                network_connector.A('check-reconnect')
            elif event == 'my-id-updated' and not self.isMyContactsChanged(arg) and ( self.NeedPropagate or self.isMyIdentityChanged(arg) ) :
                self.state = 'PROPAGATE'
                self.doPropagateMyIdentity(arg)
            elif event == 'my-id-updated' and not ( self.NeedPropagate or self.isMyIdentityChanged(arg) ) and ( network_connector.A().state is not 'CONNECTED' ) :
                self.state = 'DISCONNECTED'
            elif event == 'my-id-updated' and not ( self.NeedPropagate or self.isMyIdentityChanged(arg) ) and ( network_connector.A().state is 'CONNECTED' ) :
                self.state = 'CONNECTED'
        #---PROPAGATE---
        elif self.state == 'PROPAGATE':
            if ( ( event == 'network_connector.state' and arg == 'CONNECTED' ) ) or event == 'check-synchronize' :
                self.state = 'MY_IDENTITY'
                self.doUpdateMyIdentity(arg)
            elif event == 'my-id-propagated' :
                self.state = 'INCOMMING?'
                self.NeedPropagate=False
                self.doRestartFireHire(arg)
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
        return arg[1]

    def isMyContactsChanged(self, arg):
        """
        Condition method.
        """
        return arg[0]

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        propagate.single(arg, wide=True)

    def doInit(self, arg):
        version_number = bpio.ReadTextFile(settings.VersionNumberFile()).strip()
        if _Debug:
            lg.out(4, 'p2p_connector.doInit RevisionNumber=%s' % str(version_number))
        callback.insert_inbox_callback(-1, inbox)
        
    def doUpdateMyIdentity(self, arg):
        if _Debug:
            lg.out(4, 'p2p_connector.doUpdateMyIdentity')
        contacts_changed = False
        old_contacts = list(my_id.getLocalIdentity().getContacts())
        identity_changed = my_id.rebuildLocalIdentity()
        if not identity_changed and len(active_protos()) > 0:
            self.automat('my-id-updated', (False, False))
            return
        new_contacts = my_id.getLocalIdentity().getContacts()
        if len(old_contacts) != len(new_contacts):
            contacts_changed = True
        if not contacts_changed:
            for pos in range(len(old_contacts)):
                if old_contacts[pos] != new_contacts[pos]:
                    contacts_changed = True
                    break
        if contacts_changed:
            # erase all stats about received packets
            # if some contacts in my identity has been changed
            if _Debug:
                lg.out(4, '    my contacts were changed, erase active_protos() flags')
            active_protos().clear()
        if _Debug:
            lg.out(4, '    identity has %sbeen changed' % ('' if identity_changed else 'not '))
        self.automat('my-id-updated', (contacts_changed, identity_changed))
        
    def doPropagateMyIdentity(self, arg):
        #TODO: need to run this actions one by one, not in parallel - use Defered chain
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
        # when transport proxy is working we do not need to check our contacts at all
        if settings.transportIsEnabled('proxy'):
            if driver.is_started('service_proxy_transport'):
                if settings.transportReceivingIsEnabled('proxy'):
                    try:
                        router_idurl = driver.services()['service_proxy_transport'].transport.options['router_idurl']
                    except:
                        router_idurl = None
                    if router_idurl:
                        router_identity = identitycache.FromCache(router_idurl)
                        contacts_is_ok = True
                        router_protos = router_identity.getContactsByProto()
                        if lid.getContactsNumber() != len(router_protos):
                            contacts_is_ok = False
                        if contacts_is_ok:
                            for proto, contact in router_protos.items():
                                if lid.getProtoContact(proto) != contact:
                                    contacts_is_ok = False
                        if contacts_is_ok:
                            if _Debug:
                                lg.out(6, 'p2p_connector._check_to_use_best_proto returning True : proxy_transport is fine :-)')
                            return True    
        first = order[0]
        #if first contact in local identity is not working yet
        #but there is another working methods - switch first method
        if first not in active_protos():
            if _Debug:
                lg.out(2, 'p2p_connector._check_to_use_best_proto first contact (%s) is not working!   active_protos()=%s' % (first, str(active_protos())))
            return False
        # #small hack to make udp as first method if all is fine
        # if first != 'udp' and ('udp' in active_protos() and 'tcp' in active_protos()):
        #     lg.out(2, 'p2p_connector._check_to_use_best_proto first contact (%s) but UDP also works!  active_protos()=%s' % (first, str(active_protos())))
        #     return False
        #if tcp contact is on first place and it is working - we are VERY HAPPY! - no need to change anything - return False
        if first == 'tcp' and 'tcp' in active_protos():
            return True
        #but if tcp method is not the first and it works - we want to TURN IT ON! - return True
        if first != 'tcp' and 'tcp' in active_protos():
            if _Debug:
                lg.out(2, 'p2p_connector._check_to_use_best_proto tcp is not first but it works active_protos()=%s' % str(active_protos()))
            return False
        #if we are using udp and it is working - this is fantastic!
        if first == 'udp' and 'udp' in active_protos():
            return True
        #udp seems to be working and first contact is not working - so switch to udp
        if first != 'udp' and 'udp' in active_protos():
            if _Debug:
                lg.out(2, 'p2p_connector._check_to_use_best_proto udp is not first but it works active_protos()=%s' % str(active_protos()))
            return False
        #if we are using proxy and it is working - that is fine - it must work always!
        if first == 'proxy' and 'proxy' in active_protos():
            return True
        #proxy seems to be working and first contact is not working - so switch to proxy
        if first != 'proxy' and 'proxy' in active_protos():
            if _Debug:
                lg.out(2, 'p2p_connector._check_to_use_best_proto proxy is not first but it works active_protos()=%s' % str(active_protos()))
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
        #if proxy method is not the first but it works - switch to proxy
        if first != 'proxy' and 'proxy' in active_protos():
            wantedproto = 'proxy'
        #if udp method is not the first but it works - switch to udp
        if first != 'udp' and 'udp' in active_protos():
            wantedproto = 'udp'
        #if tcp method is not the first but it works - switch to tcp
        if first != 'tcp' and 'tcp' in active_protos():
            wantedproto = 'tcp'
        if _Debug:
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

