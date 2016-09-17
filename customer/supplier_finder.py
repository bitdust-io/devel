#!/usr/bin/env python
#supplier_finder.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (supplier_finder.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com


"""
.. module:: supplier_finder
.. role:: red
BitDust supplier_finder() Automat


EVENTS:
    * :red:`found-one-user`
    * :red:`inbox-packet`
    * :red:`start`
    * :red:`supplier-connected`
    * :red:`supplier-not-connected`
    * :red:`timer-10sec`
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

import fire_hire
import supplier_connector 

#------------------------------------------------------------------------------ 

_SupplierFinder = None
_SuppliersToHire = []

#------------------------------------------------------------------------------ 

def AddSupplierToHire(idurl):
    """
    """
    global _SuppliersToHire
    _SuppliersToHire.append(idurl)

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _SupplierFinder
    if _SupplierFinder is None:
        # set automat name and starting state here
        _SupplierFinder = SupplierFinder('supplier_finder', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _SupplierFinder.automat(event, arg)
    return _SupplierFinder


class SupplierFinder(automat.Automat):
    """
    This class implements all the functionality of the ``supplier_finder()`` state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['ACK?','SERVICE?']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.target_idurl = None

    def state_changed(self, oldstate, newstate, event, arg):
        """
        This method intended to catch the moment when automat's state were changed.
        """

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start' and not self.isSomeCandidatesListed(arg) :
                self.state = 'RANDOM_USER'
                self.Attempts=0
                self.doInit(arg)
                self.doDHTFindRandomUser(arg)
            elif event == 'start' and self.isSomeCandidatesListed(arg) :
                self.state = 'ACK?'
                self.doInit(arg)
                self.doPopCandidate(arg)
                self.Attempts=1
                self.doSendMyIdentity(arg)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'inbox-packet' and self.isAckFromUser(arg) :
                self.state = 'SERVICE?'
                self.doSupplierConnect(arg)
            elif event == 'timer-10sec' and self.Attempts<5 :
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
            elif self.Attempts==5 and event == 'timer-10sec' :
                self.state = 'FAILED'
                self.doDestroyMe(arg)
                fire_hire.A('search-failed')
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---RANDOM_USER---
        elif self.state == 'RANDOM_USER':
            if event == 'users-not-found' :
                self.state = 'FAILED'
                self.doDestroyMe(arg)
                fire_hire.A('search-failed')
            elif event == 'found-one-user' :
                self.state = 'ACK?'
                self.doCleanPrevUser(arg)
                self.doRememberUser(arg)
                self.Attempts+=1
                self.doSendMyIdentity(arg)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'supplier-connected' :
                self.state = 'DONE'
                fire_hire.A('supplier-connected', self.target_idurl)
                self.doDestroyMe(arg)
            elif event == 'timer-10sec' and self.Attempts<5 :
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
            elif self.Attempts==5 and ( event == 'timer-10sec' or event == 'supplier-not-connected' ) :
                self.state = 'FAILED'
                self.doDestroyMe(arg)
                fire_hire.A('search-failed')
            elif self.Attempts<5 and event == 'supplier-not-connected' :
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
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


    def isSomeCandidatesListed(self, arg):
        """
        Condition method.
        """
        global _SuppliersToHire
        return len(_SuppliersToHire) > 0
        
#    def isServiceAccepted(self, arg):
#        """
#        Condition method.
#        """
#        newpacket, info, status, error_message = arg
#        if newpacket.Command == commands.Ack():
#            if newpacket.Payload.startswith('accepted'):
#                return True
#        return False

    def doInit(self, arg):
        """
        Action method.
        """
        callback.insert_inbox_callback(0, self._inbox_packet_received)

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        p2p_service.SendIdentity(self.target_idurl, wide=True)

    def doSupplierConnect(self, arg):
        """
        Action method.
        """
        sc = supplier_connector.by_idurl(self.target_idurl)
        if not sc:
            sc = supplier_connector.create(self.target_idurl)
        sc.automat('connect')
        sc.set_callback('supplier_finder', self._supplier_connector_state)
            
    def doDHTFindRandomUser(self, arg):
        """
        Action method.
        """
        d = lookup.start()
        d.addCallback(self._nodes_lookup_finished)
        d.addErrback(lambda err: self.automat('users-not-found'))

    def doCleanPrevUser(self, arg):
        """
        Action method.
        """
        sc = supplier_connector.by_idurl(self.target_idurl)
        if sc:
            sc.remove_callback('supplier_finder')
        self.target_idurl = None

    def doRememberUser(self, arg):
        """
        Action method.
        """
        self.target_idurl = arg
        
    def doPopCandidate(self, arg):
        """
        Action method.
        """
        global _SuppliersToHire
        self.target_idurl = _SuppliersToHire.pop() 

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _SupplierFinder
        del _SupplierFinder
        _SupplierFinder = None
        callback.remove_inbox_callback(self._inbox_packet_received)
        if self.target_idurl:
            sc = supplier_connector.by_idurl(self.target_idurl)
            if sc:
                sc.remove_callback('supplier_finder')
            self.target_idurl = None
        self.destroy()
        lg.out(14, 'supplier_finder.doDestroyMy index=%s' % self.index)

    #------------------------------------------------------------------------------ 

    def _inbox_packet_received(self, newpacket, info, status, error_message):
        self.automat('inbox-packet', (newpacket, info, status, error_message))
        return False
        
    def _nodes_lookup_finished(self, idurls):
        if _Debug:
            lg.out(_DebugLevel, 'broadcasters_finder._nodes_lookup_finished : %r' % idurls)
        if not idurls:
            self.automat('users-not-found')
            return
        for idurl in idurls:
            ident = identitycache.FromCache(idurl)
            remoteprotos = set(ident.getProtoOrder())
            myprotos = set(my_id.getLocalIdentity().getProtoOrder())
            if len(myprotos.intersection(remoteprotos)) > 0:
                self.automat('found-one-user', idurl)
                return
        self.automat('users-not-found')
        
#     def _found_nodes(self, nodes):
#         lg.out(14, 'supplier_finder._found_nodes %d nodes' % len(nodes))
#         # DEBUG
#         # self._got_target_idurl({'idurl':'http://p2p-machines.net/bitdust_j_vps1011.xml'})
#         # return
#         if len(nodes) > 0:
#             node = random.choice(nodes)
#             d = node.request('idurl')
#             d.addCallback(self._got_target_idurl)
#             d.addErrback(self._request_error)
#         else:
#             self.automat('users-not-found')
    
#     def _search_nodes_failed(self, err):
#         self.automat('users-not-found')
    
#     def _got_target_idurl(self, response):
#         lg.out(14, 'supplier_finder._got_target_idurl response=%s' % str(response) )
#         try:
#             idurl = response['idurl']
#         except:
#             idurl = None
#         if not idurl or idurl == 'None':
#             self.automat('users-not-found')
#             return response
#         if contactsdb.is_supplier(idurl):
#             lg.out(14, '    %s is supplier already' % idurl)
#             self.automat('users-not-found')
#             return response
#         d = identitycache.immediatelyCaching(idurl)
#         d.addCallback(lambda src: self._got_target_identity(src, idurl))
#         d.addErrback(lambda x: self.automat('users-not-found'))
#         return response
    
#     def _request_error(self, err):
#         lg.out(2, '_request_error' + str(err))
#         self.automat('users-not-found')
            
#     def _got_target_identity(self, src, idurl):
#         """
#         Need to check that remote user is supported at least one of our protocols.
#         """
#         ident = identitycache.FromCache(idurl)
#         remoteprotos = set(ident.getProtoOrder())
#         myprotos = set(my_id.getLocalIdentity().getProtoOrder())
#         if len(myprotos.intersection(remoteprotos)) > 0:
#             self.automat('found-one-user', idurl)
#         else:
#             self.automat('users-not-found')
            
    def _supplier_connector_state(self, supplier_idurl, newstate):
        if supplier_idurl != self.target_idurl:
            return
        if newstate is 'CONNECTED':
            self.automat('supplier-connected', self.target_idurl)
        elif newstate in ['DISCONNECTED', 'NO_SERVICE', ]:
            self.automat('supplier-not-connected')

