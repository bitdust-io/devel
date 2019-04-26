#!/usr/bin/python
# config_defaults.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (config_types.py) is part of BitDust Software.
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

module:: config_defaults
"""


TYPE_UNDEFINED = 0
TYPE_BOOLEAN = 1
TYPE_STRING = 2
TYPE_TEXT = 3
TYPE_INTEGER = 4
TYPE_POSITIVE_INTEGER = 5
TYPE_NON_ZERO_POSITIVE_INTEGER = 6
TYPE_FOLDER_PATH = 7
TYPE_FILE_PATH = 8
TYPE_COMBO_BOX = 9
TYPE_PASSWORD = 10
TYPE_DISK_SPACE = 11
TYPE_PORT_NUMBER = 12


def labels():
    return {
        TYPE_UNDEFINED: 'undefined',
        TYPE_BOOLEAN: 'boolean',
        TYPE_STRING: 'string',
        TYPE_TEXT: 'text',
        TYPE_INTEGER: 'integer',
        TYPE_POSITIVE_INTEGER: 'positive integer',
        TYPE_NON_ZERO_POSITIVE_INTEGER: 'non zero positive integer',
        TYPE_FOLDER_PATH: 'folder path',
        TYPE_FILE_PATH: 'file path',
        TYPE_COMBO_BOX: 'selection',
        TYPE_PASSWORD: 'password',
        TYPE_DISK_SPACE: 'disk space',
        TYPE_PORT_NUMBER: 'port number',
    }


def defaults():
    return {
        'interface/api/json-rpc-enabled': TYPE_BOOLEAN,
        'interface/api/json-rpc-port': TYPE_PORT_NUMBER,
        'interface/api/rest-http-enabled': TYPE_BOOLEAN,
        'interface/api/rest-http-port': TYPE_PORT_NUMBER,
        'interface/ftp/enabled': TYPE_BOOLEAN,
        'interface/ftp/port': TYPE_PORT_NUMBER,
        'logs/debug-level': TYPE_POSITIVE_INTEGER,
        'logs/memdebug-enabled': TYPE_BOOLEAN,
        'logs/memdebug-port': TYPE_PORT_NUMBER,
        'logs/memprofile-enabled': TYPE_BOOLEAN,
        'logs/stream-enabled': TYPE_BOOLEAN,
        'logs/stream-port': TYPE_PORT_NUMBER,
        'logs/traffic-enabled': TYPE_BOOLEAN,
        'logs/traffic-port': TYPE_PORT_NUMBER,
        'other/upnp-at-startup': TYPE_BOOLEAN,
        'paths/backups': TYPE_FOLDER_PATH,
        'paths/customers': TYPE_FOLDER_PATH,
        'paths/messages': TYPE_FOLDER_PATH,
        'paths/receipts': TYPE_FOLDER_PATH,
        'paths/restore': TYPE_FOLDER_PATH,
        'personal/betatester': TYPE_BOOLEAN,
        'personal/email': TYPE_STRING,
        'personal/name': TYPE_STRING,
        'personal/nickname': TYPE_STRING,
        'personal/private-key-size': TYPE_STRING,
        'personal/surname': TYPE_STRING,
        'services/accountant/enabled': TYPE_BOOLEAN,
        'services/backup-db/enabled': TYPE_BOOLEAN,
        'services/backups/block-size': TYPE_DISK_SPACE,
        'services/backups/enabled': TYPE_BOOLEAN,
        'services/backups/keep-local-copies-enabled': TYPE_BOOLEAN,
        'services/backups/max-block-size': TYPE_DISK_SPACE,
        'services/backups/max-copies': TYPE_POSITIVE_INTEGER,
        'services/backups/wait-suppliers-enabled': TYPE_BOOLEAN,
        'services/blockchain/enabled': TYPE_BOOLEAN,
        'services/blockchain/host': TYPE_STRING,
        'services/blockchain/port': TYPE_PORT_NUMBER,
        'services/blockchain/explorer/enabled': TYPE_BOOLEAN,
        'services/blockchain/explorer/port': TYPE_PORT_NUMBER,
        'services/blockchain/wallet/enabled': TYPE_BOOLEAN,
        'services/blockchain/wallet/port': TYPE_PORT_NUMBER,
        'services/blockchain/miner/enabled': TYPE_BOOLEAN,
        'services/broadcasting/enabled': TYPE_BOOLEAN,
        'services/broadcasting/routing-enabled': TYPE_BOOLEAN,
        'services/broadcasting/max-broadcast-connections': TYPE_NON_ZERO_POSITIVE_INTEGER,
        'services/contract-chain/enabled': TYPE_BOOLEAN,
        'services/customer/enabled': TYPE_BOOLEAN,
        'services/customer/needed-space': TYPE_DISK_SPACE,
        'services/customer/suppliers-number': TYPE_COMBO_BOX,
        'services/customer-contracts/enabled': TYPE_BOOLEAN,
        'services/customer-family/enabled': TYPE_BOOLEAN,
        'services/customer-patrol/enabled': TYPE_BOOLEAN,
        'services/customer-support/enabled': TYPE_BOOLEAN,
        'services/data-motion/enabled': TYPE_BOOLEAN,
        'services/entangled-dht/enabled': TYPE_BOOLEAN,
        'services/entangled-dht/udp-port': TYPE_PORT_NUMBER,
        'services/entangled-dht/known-nodes': TYPE_STRING,
        'services/employer/enabled': TYPE_BOOLEAN,
        'services/gateway/enabled': TYPE_BOOLEAN,
        'services/http-connections/enabled': TYPE_BOOLEAN,
        'services/http-connections/http-port': TYPE_PORT_NUMBER,
        'services/http-transport/enabled': TYPE_BOOLEAN,
        'services/http-transport/receiving-enabled': TYPE_BOOLEAN,
        'services/http-transport/sending-enabled': TYPE_BOOLEAN,
        'services/http-transport/priority': TYPE_POSITIVE_INTEGER,
        'services/identity-server/enabled': TYPE_BOOLEAN,
        'services/identity-server/host': TYPE_STRING,
        'services/identity-server/tcp-port': TYPE_PORT_NUMBER,
        'services/identity-server/web-port': TYPE_PORT_NUMBER,
        'services/identity-propagate/enabled': TYPE_BOOLEAN,
        'services/identity-propagate/known-servers': TYPE_STRING,
        'services/identity-propagate/preferred-servers': TYPE_STRING,
        'services/identity-propagate/min-servers': TYPE_NON_ZERO_POSITIVE_INTEGER,
        'services/identity-propagate/max-servers': TYPE_NON_ZERO_POSITIVE_INTEGER,
        'services/identity-server/enabled': TYPE_BOOLEAN,
        'services/ip-port-responder/enabled': TYPE_BOOLEAN,
        'services/keys-registry/enabled': TYPE_BOOLEAN,
        'services/keys-storage/enabled': TYPE_BOOLEAN,
        'services/list-files/enabled': TYPE_BOOLEAN,
        'services/miner/enabled': TYPE_BOOLEAN,
        'services/my-ip-port/enabled': TYPE_BOOLEAN,
        'services/network/enabled': TYPE_BOOLEAN,
        'services/network/proxy/enabled': TYPE_BOOLEAN,
        'services/network/proxy/host': TYPE_STRING,
        'services/network/proxy/password': TYPE_PASSWORD,
        'services/network/proxy/port': TYPE_PORT_NUMBER,
        'services/network/proxy/ssl': TYPE_BOOLEAN,
        'services/network/proxy/username': TYPE_STRING,
        'services/network/receive-limit': TYPE_POSITIVE_INTEGER,
        'services/network/send-limit': TYPE_POSITIVE_INTEGER,
        'services/nodes-lookup/enabled': TYPE_BOOLEAN,
        'services/p2p-hookups/enabled': TYPE_BOOLEAN,
        'services/p2p-notifications/enabled': TYPE_BOOLEAN,
        'services/private-messages/enabled': TYPE_BOOLEAN,
        'services/proxy-server/enabled': TYPE_BOOLEAN,
        'services/proxy-server/routes-limit': TYPE_POSITIVE_INTEGER,
        'services/proxy-server/current-routes': TYPE_TEXT,
        'services/proxy-transport/enabled': TYPE_BOOLEAN,
        'services/proxy-transport/sending-enabled': TYPE_BOOLEAN,
        'services/proxy-transport/receiving-enabled': TYPE_BOOLEAN,
        'services/proxy-transport/priority': TYPE_POSITIVE_INTEGER,
        'services/proxy-transport/my-original-identity': TYPE_TEXT,
        'services/proxy-transport/current-router': TYPE_STRING,
        'services/proxy-transport/preferred-routers': TYPE_TEXT,
        'services/proxy-transport/router-lifetime-seconds': TYPE_POSITIVE_INTEGER,
        'services/rebuilding/enabled': TYPE_BOOLEAN,
        'services/restores/enabled': TYPE_BOOLEAN,
        'services/shared-data/enabled': TYPE_BOOLEAN,
        'services/supplier/donated-space': TYPE_DISK_SPACE,
        'services/supplier/enabled': TYPE_BOOLEAN,
        'services/supplier-contracts/enabled': TYPE_BOOLEAN,
        'services/supplier-relations/enabled': TYPE_BOOLEAN,
        'services/tcp-connections/enabled': TYPE_BOOLEAN,
        'services/tcp-connections/tcp-port': TYPE_PORT_NUMBER,
        'services/tcp-connections/upnp-enabled': TYPE_BOOLEAN,
        'services/tcp-transport/enabled': TYPE_BOOLEAN,
        'services/tcp-transport/receiving-enabled': TYPE_BOOLEAN,
        'services/tcp-transport/sending-enabled': TYPE_BOOLEAN,
        'services/tcp-transport/priority': TYPE_POSITIVE_INTEGER,
        'services/udp-datagrams/enabled': TYPE_BOOLEAN,
        'services/udp-datagrams/udp-port': TYPE_PORT_NUMBER,
        'services/udp-transport/enabled': TYPE_BOOLEAN,
        'services/udp-transport/receiving-enabled': TYPE_BOOLEAN,
        'services/udp-transport/sending-enabled': TYPE_BOOLEAN,
        'services/udp-transport/priority': TYPE_POSITIVE_INTEGER,
    }
