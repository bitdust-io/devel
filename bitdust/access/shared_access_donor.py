#!/usr/bin/env python
# shared_access_donor.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
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
    * :red:`audit-ok`
    * :red:`blockchain-ok`
    * :red:`fail`
    * :red:`init`
    * :red:`list-files-ok`
    * :red:`priv-key-ok`
    * :red:`timer-10sec`
    * :red:`timer-15sec`
    * :red:`timer-2sec`
    * :red:`timer-30sec`
    * :red:`user-identity-cached`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 6

#------------------------------------------------------------------------------

import time

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import packetid
from bitdust.lib import serialization
from bitdust.lib import strng

from bitdust.main import events

from bitdust.contacts import identitycache
from bitdust.contacts import contactsdb

from bitdust.p2p import p2p_service
from bitdust.p2p import online_status
from bitdust.p2p import commands

from bitdust.crypt import key
from bitdust.crypt import my_keys
from bitdust.crypt import encrypted

from bitdust.userid import my_id
from bitdust.userid import global_id
from bitdust.userid import id_url

from bitdust.access import key_ring

from bitdust.storage import backup_fs

#------------------------------------------------------------------------------


class SharedAccessDonor(automat.Automat):
    """
    This class implements all the functionality of the ``shared_access_donor()`` state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['CACHE']),
        'timer-15sec': (15.0, ['PUB_KEY', 'PING', 'AUDIT', 'LIST_FILES']),
        'timer-2sec': (2.0, ['PUB_KEY']),
        'timer-30sec': (30.0, ['PRIV_KEY']),
    }

    def __init__(self, debug_level=0, log_events=False, publish_events=False, **kwargs):
        """
        Create shared_access_donor() state machine.
        Use this method if you need to call Automat.__init__() in a special way.
        """
        super(SharedAccessDonor, self).__init__(name='shared_access_donor', state='AT_STARTUP', debug_level=debug_level or _DebugLevel, log_events=log_events or _Debug, publish_events=publish_events, **kwargs)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of shared_access_donor() machine.
        """
        self.log_transitions = _Debug
        self.caching_deferred = None
        self.remote_idurl = None
        self.remote_identity = None
        self.ping_response = None
        self.key_id = None
        self.result_defer = None
        self.suppliers_responses = {}
        self.suppliers_acks = 0

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'CACHE'
                self.doInit(*args, **kwargs)
                self.doInsertInboxCallback(*args, **kwargs)
                self.doCacheRemoteIdentity(*args, **kwargs)
        #---PING---
        elif self.state == 'PING':
            if event == 'ack':
                self.state = 'BLOCKCHAIN'
                self.doBlockchainLookupVerifyUserPubKey(*args, **kwargs)
            elif event == 'fail' or event == 'timer-15sec':
                self.state = 'CLOSED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---CACHE---
        elif self.state == 'CACHE':
            if event == 'user-identity-cached':
                self.state = 'PING'
                self.doSendMyIdentityToUser(*args, **kwargs)
            elif event == 'fail' or event == 'timer-10sec':
                self.state = 'CLOSED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---BLOCKCHAIN---
        elif self.state == 'BLOCKCHAIN':
            if event == 'fail':
                self.state = 'CLOSED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'blockchain-ok':
                self.state = 'AUDIT'
                self.doAuditUserMasterKey(*args, **kwargs)
        #---LIST_FILES---
        elif self.state == 'LIST_FILES':
            if event == 'list-files-ok':
                self.state = 'CLOSED'
                self.doReportDone(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'fail' or event == 'timer-15sec':
                self.state = 'CLOSED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---AUDIT---
        elif self.state == 'AUDIT':
            if event == 'audit-ok':
                self.state = 'PUB_KEY'
                self.doSendPubKeyToSuppliers(*args, **kwargs)
            elif event == 'fail' or event == 'timer-15sec':
                self.state = 'CLOSED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---PUB_KEY---
        elif self.state == 'PUB_KEY':
            if event == 'ack':
                self.doCheckAllAcked(*args, **kwargs)
            elif event == 'fail' or (event == 'timer-15sec' and not self.isSomeSuppliersAcked(*args, **kwargs)):
                self.state = 'CLOSED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'all-suppliers-acked' or (event == 'timer-2sec' and self.isSomeSuppliersAcked(*args, **kwargs)):
                self.state = 'PRIV_KEY'
                self.doSendPrivKeyToUser(*args, **kwargs)
        #---PRIV_KEY---
        elif self.state == 'PRIV_KEY':
            if event == 'priv-key-ok':
                self.state = 'LIST_FILES'
                self.doSendMyListFiles(*args, **kwargs)
            elif event == 'fail' or event == 'timer-30sec':
                self.state = 'CLOSED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isSomeSuppliersAcked(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.suppliers_acks > 0

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.remote_idurl = id_url.field(kwargs['trusted_idurl'])
        self.key_id = strng.to_text(kwargs['key_id'])
        self.result_defer = kwargs.get('result_defer', None)

    def doInsertInboxCallback(self, *args, **kwargs):
        """
        Action method.
        """

    def doCacheRemoteIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        self.caching_deferred = identitycache.immediatelyCaching(self.remote_idurl)
        self.caching_deferred.addCallback(self._on_remote_identity_cached)
        self.caching_deferred.addErrback(lambda err: self.automat('fail', err) and None)

    def doSendMyIdentityToUser(self, *args, **kwargs):
        """
        Action method.
        """
        def _on_ack(response):
            self.ping_response = time.time()
            self.automat('ack', response)
            return response

        def _on_fail(err):
            self.automat('fail', err)
            return None

        d = online_status.ping(
            idurl=self.remote_idurl,
            channel='shared_access_donor',
            ping_retries=1,
            keep_alive=True,
        )
        d.addCallback(_on_ack)
        d.addErrback(_on_fail)

    def doBlockchainLookupVerifyUserPubKey(self, *args, **kwargs):
        """
        Action method.
        """
        # TODO:
        self.automat('blockchain-ok')

    def doAuditUserMasterKey(self, *args, **kwargs):
        """
        Action method.
        """
        master_key_id = my_keys.make_key_id(alias='master', creator_idurl=self.remote_idurl)
        d = key_ring.audit_private_key(master_key_id, self.remote_idurl)
        d.addCallback(lambda audit_result: (self.automat('audit-ok') if audit_result else self.automat('fail', Exception('remote user master key audit process failed')), ))
        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='shared_access_donor.doAuditUserMasterKey')
        d.addErrback(lambda err: self.automat('fail', err))

    def doSendPubKeyToSuppliers(self, *args, **kwargs):
        """
        Action method.
        """
        if not my_keys.is_key_registered(self.key_id):
            self.automat('fail', Exception('key not found'))
            return
        self.suppliers_acks = 0
        for supplier_idurl in contactsdb.suppliers():
            if supplier_idurl:
                d = key_ring.share_key(self.key_id, supplier_idurl, include_private=False, include_signature=False)
                d.addCallback(self._on_supplier_pub_key_shared, supplier_idurl)
                d.addErrback(self._on_supplier_pub_key_failed, supplier_idurl)
                self.suppliers_responses[supplier_idurl] = d

    def doCheckAllAcked(self, *args, **kwargs):
        """
        Action method.
        """
        if len(self.suppliers_responses) == 0:
            self.automat('all-suppliers-acked')

    def doSendPrivKeyToUser(self, *args, **kwargs):
        """
        Action method.
        """
        d = key_ring.share_key(self.key_id, self.remote_idurl, include_private=True, include_signature=True)
        d.addCallback(self._on_user_priv_key_shared)
        d.addErrback(self._on_user_priv_key_failed)

    def doSendMyListFiles(self, *args, **kwargs):
        """
        Action method.
        """
        self.automat('list-files-ok')
        return
        # TODO: cleanup
        json_list_files = backup_fs.SerializeIndex(
            customer_idurl=global_id.glob2idurl(self.key_id),
            to_json=True,
            filter_cb=lambda path_id, path, info: True if strng.to_text(info.key_id) == strng.to_text(self.key_id) else False,
        )
        raw_list_files = serialization.DictToBytes(json_list_files, keys_to_text=True, values_to_text=True, encoding='utf-8')
        if _Debug:
            lg.out(_DebugLevel, 'shared_access_donor.doSendMyListFiles prepared list of files for %s :\n%s' % (self.remote_idurl, raw_list_files))
        block = encrypted.Block(
            CreatorID=my_id.getIDURL(),
            BackupID=self.key_id,
            Data=raw_list_files,
            SessionKey=key.NewSessionKey(session_key_type=key.SessionKeyType()),
            SessionKeyType=key.SessionKeyType(),
            EncryptKey=self.key_id,
        )
        encrypted_list_files = block.Serialize()
        packet_id = '%s:%s' % (
            self.key_id,
            packetid.UniqueID(),
        )
        p2p_service.SendFiles(
            idurl=self.remote_idurl,
            raw_list_files_info=encrypted_list_files,
            packet_id=packet_id,
            callbacks={
                commands.Ack(): lambda response, _: self.automat('list-files-ok', response),
                commands.Fail(): lambda response, _: self.automat('fail', Exception(str(response))),
                None: lambda pkt_out: self.automat('fail', Exception('timeout')),
            },
        )

    def doReportDone(self, *args, **kwargs):
        """
        Action method.
        """
        lg.info('share key [%s] with %r finished with success' % (self.key_id, self.remote_idurl))
        events.send('private-key-shared', data=dict(
            global_id=global_id.UrlToGlobalID(self.remote_idurl),
            remote_idurl=self.remote_idurl,
            key_id=self.key_id,
        ))
        if self.result_defer:
            self.result_defer.callback(True)

    def doReportFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        lg.warn('share key [%s] with %s failed: %s' % (self.key_id, self.remote_idurl, args))
        reason = 'key transfer failed with unknown reason'
        if args and args[0]:
            reason = args[0]
        else:
            if self.remote_identity is None:
                reason = 'remote identity caching failed',
            else:
                if self.ping_response is None:
                    reason = 'remote node not responding',
                else:
                    if self.suppliers_responses:
                        reason = 'connection timeout with my suppliers'
                    else:
                        if event.count('timer-'):
                            reason = 'key transfer failed because of network connection timeout'
        events.send('private-key-share-failed', data=dict(
            global_id=global_id.UrlToGlobalID(self.remote_idurl),
            remote_idurl=self.remote_idurl,
            key_id=self.key_id,
            reason=reason,
        ))
        if self.result_defer:
            self.result_defer.errback(Exception(reason))

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.remote_idurl = None
        self.remote_identity = None
        self.ping_response = None
        self.key_id = None
        self.result_defer = None
        self.suppliers_responses.clear()
        self.suppliers_acks = 0
        if self.caching_deferred:
            self.caching_deferred.cancel()
            self.caching_deferred = None
        self.destroy()

    def _on_remote_identity_cached(self, xmlsrc):
        self.caching_deferred = None
        self.remote_identity = contactsdb.get_contact_identity(self.remote_idurl)
        if self.remote_identity is None:
            self.automat('fail', Exception('remote id caching failed'))
        else:
            self.automat('user-identity-cached')

    def _on_supplier_pub_key_shared(self, response, supplier_idurl):
        self.suppliers_responses.pop(supplier_idurl, None)
        self.suppliers_acks += 1
        self.automat('ack', response)
        lg.warn('suppliers_acks=%d, suppliers_responses=%d' % (self.suppliers_acks, len(self.suppliers_responses)))
        return None

    def _on_supplier_pub_key_failed(self, err, supplier_idurl):
        lg.warn(err)
        self.suppliers_responses.pop(supplier_idurl, None)
        return None

    def _on_user_priv_key_shared(self, response):
        lg.info('your private key %s was sent to %s' % (self.key_id, self.remote_idurl))
        self.automat('priv-key-ok', response)
        return None

    def _on_user_priv_key_failed(self, err):
        lg.warn(err)
        self.automat('fail', Exception('private key delivery failed to remote node'))
        return None
