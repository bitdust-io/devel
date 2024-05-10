#!/usr/bin/python
# service_private_groups.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_private_groups.py) is part of BitDust Software.
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

module:: service_private_groups
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return PrivateGroupsService()


class PrivateGroupsService(LocalService):

    service_name = 'service_private_groups'
    config_path = 'services/private-groups/enabled'

    def dependent_on(self):
        return [
            'service_my_data',
            'service_private_messages',
        ]

    def start(self):
        from bitdust.main import events
        from bitdust.access import groups
        # from bitdust.access import group_member
        from bitdust.access import group_participant
        groups.init()
        events.add_subscriber(self._on_supplier_modified, 'supplier-modified')
        # events.add_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        # if driver.is_on('service_entangled_dht'):
        #     self._do_join_message_brokers_dht_layer()
        # group_member.start_group_members()
        group_participant.start_group_participants()
        events.add_subscriber(groups.on_identity_url_changed, 'identity-url-changed')
        return True

    def stop(self):
        from bitdust.main import events
        from bitdust.access import groups
        # from bitdust.access import group_member
        from bitdust.access import group_participant
        events.remove_subscriber(groups.on_identity_url_changed, 'identity-url-changed')
        # group_member.shutdown_group_members()
        group_participant.shutdown_group_participants()
        # events.remove_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        events.remove_subscriber(self._on_supplier_modified, 'supplier-modified')
        groups.shutdown()
        return True

    def health_check(self):
        # TODO: probably at least one queue must be connected if service is enabled
        return True

    # def _do_join_message_brokers_dht_layer(self):
    #     from bitdust.logs import lg
    #     from bitdust.dht import dht_service
    #     from bitdust.dht import dht_records
    #     from bitdust.dht import known_nodes
    #     lg.info('going to join message brokers DHT layer: %d' % dht_records.LAYER_MESSAGE_BROKERS)
    #     known_seeds = known_nodes.nodes()
    #     dht_service.open_layer(
    #         seed_nodes=known_seeds,
    #         layer_id=dht_records.LAYER_MESSAGE_BROKERS,
    #         connect_now=True,
    #         attach=False,
    #     )

    # def _on_dht_layer_connected(self, evt):
    #     if evt.data['layer_id'] == 0:
    #         self._do_join_message_brokers_dht_layer()

    def _on_supplier_modified(self, evt):
        from bitdust.logs import lg
        from bitdust.access import key_ring
        from bitdust.crypt import my_keys
        from bitdust.userid import global_id
        from bitdust.userid import my_id
        if evt.data['new_idurl']:
            my_keys_to_be_republished = []
            for key_id in my_keys.known_keys():
                if not key_id.startswith('group_'):
                    continue
                _glob_id = global_id.NormalizeGlobalID(key_id)
                if _glob_id['idurl'] == my_id.getIDURL():
                    # only send public keys of my own groups
                    my_keys_to_be_republished.append(key_id)
            for group_key_id in my_keys_to_be_republished:
                d = key_ring.transfer_key(group_key_id, trusted_idurl=evt.data['new_idurl'], include_private=False, include_signature=False)
                d.addErrback(lambda *a: lg.err('transfer key failed: %s' % str(*a)))
