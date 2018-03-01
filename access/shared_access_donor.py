#!/usr/bin/env python
# shared_access_donor.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (shared_access_donor.py) is part of BitDust Software.
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
.. module:: shared_access_donor
.. role:: red

BitDust shared_access_donor() Automat

EVENTS:
    * :red:`ack`
    * :red:`all-suppliers-acked`
    * :red:`blockchain-ok`
    * :red:`fail`
    * :red:`init`
    * :red:`timer-5sec`
    * :red:`user-identity-cached`
"""

#------------------------------------------------------------------------------

from automats import automat

from transport import callback

from contacts import identitycache
from contacts import contactsdb

from p2p import p2p_service
from p2p import commands

#------------------------------------------------------------------------------

class SharedAccessDonor(automat.Automat):
    """
    This class implements all the functionality of the ``shared_access_donor()`` state machine.
    """

    timers = {
        'timer-5sec': (5.0, ['PUB_KEY','PING','PRIV_KEY','VERIFY','CACHE','LIST_FILES']),
    }

    def __init__(self, state):
        """
        Create shared_access_donor() state machine.
        Use this method if you need to call Automat.__init__() in a special way.
        """
        super(SharedAccessDonor, self).__init__("shared_access_donor", state)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of shared_access_donor() machine.
        """
        self.caching_deferred = None

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when shared_access_donor() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the shared_access_donor()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'CACHE'
                self.doInsertInboxCallback(arg)
                self.doCacheRemoteIdentity(arg)
        #---PRIV_KEY---
        elif self.state == 'PRIV_KEY':
            if event == 'fail' or event == 'timer-5sec':
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'ack':
                self.state = 'LIST_FILES'
                self.doSendMyListFiles(arg)
        #---PUB_KEY---
        elif self.state == 'PUB_KEY':
            if event == 'ack':
                self.doCheckAllAcked(arg)
            elif event == 'timer-5sec' and not self.isSomeSuppliersAcked(arg):
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'all-suppliers-acked' or ( event == 'timer-5sec' and self.isSomeSuppliersAcked(arg) ):
                self.state = 'PRIV_KEY'
                self.doSendPrivKeyToUser(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---PING---
        elif self.state == 'PING':
            if event == 'ack':
                self.state = 'BLOCKCHAIN'
                self.doBlockchainLookupVerifyUserPubKey(arg)
            elif event == 'fail' or event == 'timer-5sec':
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---VERIFY---
        elif self.state == 'VERIFY':
            if ( event == 'ack' and not self.isResponseValid(arg) ) or event == 'fail' or event == 'timer-5sec':
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'ack' and self.isResponseValid(arg):
                self.state = 'PUB_KEY'
                self.doSendPubKeyToSuppliers(arg)
        #---CACHE---
        elif self.state == 'CACHE':
            if event == 'user-identity-cached':
                self.state = 'PING'
                self.doSendMyIdentityToUser(arg)
            elif event == 'fail' or event == 'timer-5sec':
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---BLOCKCHAIN---
        elif self.state == 'BLOCKCHAIN':
            if event == 'blockchain-ok':
                self.state = 'VERIFY'
                self.doSendEncryptedSample(arg)
            elif event == 'fail':
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---LIST_FILES---
        elif self.state == 'LIST_FILES':
            if event == 'fail' or event == 'timer-5sec':
                self.state = 'CLOSED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'ack':
                self.state = 'CLOSED'
                self.doReportDone(arg)
                self.doDestroyMe(arg)
        return None

    def isResponseValid(self, arg):
        """
        Condition method.
        """

    def doInsertInboxCallback(self, arg):
        """
        Action method.
        """
        callback.insert_inbox_callback(0, self._on_inbox_packet_received)

    def doCacheRemoteIdentity(self, arg):
        """
        Action method.
        """
        self.remote_idurl = arg
        self.caching_deferred = identitycache.immediatelyCaching(self.remote_idurl)
        self.caching_deferred.addCallback(self._on_remote_identity_cached)
        self.caching_deferred.addErrback(lambda err: self.automat('fail'))

    def doSendMyIdentityToUser(self, arg):
        """
        Action method.
        """
        p2p_service.SendIdentity(self.target_idurl, wide=True)

    def doBlockchainLookupVerifyUserPubKey(self, arg):
        """
        Action method.
        """
        # TODO:
        self.automat('blockchain-ok')

    def doSendEncryptedSample(self, arg):
        """
        Action method.
        """
        from crypt import encrypted
        from userid import my_id
        from crypt import key
        sample_key = ''
        encrypted.Block(
            CreatorID=my_id.getLocalID(),
            BackupID='encrypted_sample',
            BlockNumber=0,
            SessionKey=key.NewSessionKey(),
            Data=sample_key,
            EncryptKey=lambda inp: self.remote_identity.encrypt(inp),
        )

    def doSendPrivKeyToUser(self, arg):
        """
        Action method.
        """

    def doSendPubKeyToSuppliers(self, arg):
        """
        Action method.
        """

    def doReportDone(self, arg):
        """
        Action method.
        """

    def doReportFailed(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        if self.caching_deferred:
            self.caching_deferred.cancel()
            self.caching_deferred = None
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        self.unregister()

    def isSomeSuppliersAcked(self, arg):
        """
        Condition method.
        """

    def doSendMyListFiles(self, arg):
        """
        Action method.
        """

    def doCheckAllAcked(self, arg):
        """
        Action method.
        """

    def _on_remote_identity_cached(self, xmlsrc):
        self.caching_deferred = None
        self.remote_identity = contactsdb.get_contact_identity(self.remote_idurl)
        if self.remote_identity is None:
            self.automat('fail')
        else:
            self.automat('user-identity-cached')

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        if newpacket.Command == commands.Ack() and \
                newpacket.OwnerID == self.target_idurl and \
                newpacket.PacketID == 'identity' and \
                self.state == 'ACK?':
            self.automat('ack', self.target_idurl)
            return True
        return False
