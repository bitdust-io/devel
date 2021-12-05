#!/usr/bin/python
# service_shared_data.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_shared_data.py) is part of BitDust Software.
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
#
#
#
#

"""
..

module:: service_shared_data
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return SharedDataService()


class SharedDataService(LocalService):

    service_name = 'service_shared_data'
    config_path = 'services/shared-data/enabled'

    def dependent_on(self):
        return [
            'service_my_data',
        ]

    def start(self):
        from main import events
        from transport import callback
        callback.append_inbox_callback(self._on_inbox_packet_received)
        events.add_subscriber(self._on_supplier_modified, 'supplier-modified')
        events.add_subscriber(self._on_my_list_files_refreshed, 'my-list-files-refreshed')
        events.add_subscriber(self._on_key_erased, 'key-erased')
        self._do_open_known_shares()
        return True

    def stop(self):
        from main import events
        from transport import callback
        events.remove_subscriber(self._on_key_erased, 'key-erased')
        events.remove_subscriber(self._on_my_list_files_refreshed, 'my-list-files-refreshed')
        events.remove_subscriber(self._on_supplier_modified, 'supplier-modified')
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        return True

    def _on_key_erased(self, evt):
        from access import shared_access_coordinator
        active_share = shared_access_coordinator.get_active_share(evt.data['key_id'])
        if active_share:
            active_share.automat('shutdown')

    def _on_supplier_modified(self, evt):
        from access import key_ring
        from crypt import my_keys
        from userid import global_id
        from userid import my_id
        from logs import lg
        if evt.data['new_idurl']:
            my_keys_to_be_republished = []
            for key_id in my_keys.known_keys():
                if not key_id.startswith('share_'):
                    continue
                _glob_id = global_id.ParseGlobalID(key_id)
                if _glob_id['idurl'].to_bin() == my_id.getIDURL().to_bin():
                    # only send public keys of my own shares
                    my_keys_to_be_republished.append(key_id)
            for key_id in my_keys_to_be_republished:
                d = key_ring.transfer_key(key_id, trusted_idurl=evt.data['new_idurl'], include_private=False, include_signature=False)
                d.addErrback(lambda *a: lg.err('transfer key failed: %s' % str(*a)))

    def _on_my_list_files_refreshed(self, evt):
        from access import shared_access_coordinator
        from customer import supplier_connector
        from p2p import p2p_service
        from p2p import commands
        for key_id in shared_access_coordinator.list_active_shares():
            cur_share = shared_access_coordinator.get_active_share(key_id)
            if not cur_share:
                continue
            if cur_share.state != 'CONNECTED':
                continue
            for supplier_idurl in cur_share.known_suppliers_list:
                sc = supplier_connector.by_idurl(
                    supplier_idurl,
                    customer_idurl=cur_share.customer_idurl,
                )
                if sc is not None and sc.state == 'CONNECTED':
                    p2p_service.SendListFiles(
                        target_supplier=supplier_idurl,
                        customer_idurl=cur_share.customer_idurl,
                        key_id=cur_share.key_id,
                        timeout=30,
                        callbacks={
                            commands.Files(): lambda r, i: self._on_list_files_response(r, i, cur_share.customer_idurl, supplier_idurl, cur_share.key_id),
                            commands.Fail(): lambda r, i: self._on_list_files_failed(r, i, cur_share.customer_idurl, supplier_idurl, cur_share.key_id),
                        }
                    )

    def _on_list_files_response(self, response, info, customer_idurl, supplier_idurl, key_id):
        from logs import lg
        # TODO: remember the response and prevent sending ListFiles() too often

    def _on_list_files_failed(self, response, info, customer_idurl, supplier_idurl, key_id):
        from logs import lg
        from lib import strng
        from access import key_ring
        if strng.to_text(response.Payload) == 'key not registered' or strng.to_text(response.Payload) == '':
            lg.warn('supplier %r of customer %r do not possess public key %r yet, sending it now' % (
                supplier_idurl, customer_idurl, key_id, ))
            result = key_ring.transfer_key(key_id, supplier_idurl, include_private=False, include_signature=False)
            result.addCallback(lambda r: self._on_key_transfer_success(customer_idurl, supplier_idurl, key_id))
            result.addErrback(lambda err: lg.err('failed sending key %r to %r : %r' % (key_id, supplier_idurl, err, )))
        else:
            lg.err('failed requesting ListFiles() with %r for customer %r from supplier %r' % (
                key_id, customer_idurl, supplier_idurl, ))
        return None

    def _on_key_transfer_success(self, customer_idurl, supplier_idurl, key_id):
        from logs import lg
        from p2p import p2p_service
        lg.info('public key %r shared to supplier %r of customer %r, now will send ListFiles()' % (key_id, supplier_idurl, customer_idurl))
        p2p_service.SendListFiles(
            target_supplier=supplier_idurl,
            customer_idurl=customer_idurl,
            key_id=key_id,
            timeout=30,
        )

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from p2p import commands
        from access import key_ring
        if newpacket.Command == commands.Files():
            return key_ring.on_files_received(newpacket, info)
        return False

    def _do_open_known_shares(self):
        from crypt import my_keys
        from access import shared_access_coordinator
        from storage import backup_fs
        known_offline_shares = []
        for key_id in my_keys.known_keys():
            if not key_id.startswith('share_'):
                continue
            active_share = shared_access_coordinator.get_active_share(key_id)
            if active_share:
                continue
            known_offline_shares.append(key_id)
        to_be_opened = []
        for pathID, localPath, itemInfo in backup_fs.IterateIDs():
            if not itemInfo.key_id:
                continue
            if itemInfo.key_id in to_be_opened:
                continue
            if itemInfo.key_id not in known_offline_shares:
                continue
            to_be_opened.append(itemInfo.key_id)
        for key_id in to_be_opened:
            active_share = shared_access_coordinator.SharedAccessCoordinator(key_id, log_events=True, publish_events=False, )
            active_share.automat('restart')
