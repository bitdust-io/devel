#!/usr/bin/python
# config_defaults.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (config_defaults.py) is part of BitDust Software.
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


def reset(conf_obj):
    """
    Configure default values for all BitDust local settings inside ~/.bitdust/[network name]/config/ folder.

    Every option must have a default value, however there are exceptions possible.

    Here all items suppose to have some widget in UI to interact with human.
    Keep it simple and understandable.
    """
    from bitdust.lib import diskspace
    from bitdust.main import settings

    conf_obj.setDefaultValue('interface/api/auth-secret-enabled', 'true')

    conf_obj.setDefaultValue('interface/api/rest-http-enabled', 'true')
    conf_obj.setDefaultValue('interface/api/rest-http-port', settings.DefaultRESTHTTPPort())

    conf_obj.setDefaultValue('interface/api/web-socket-enabled', 'true')
    conf_obj.setDefaultValue('interface/api/web-socket-port', settings.DefaultWebSocketPort())

    conf_obj.setDefaultValue('interface/ftp/enabled', 'true')
    conf_obj.setDefaultValue('interface/ftp/port', settings.DefaultFTPPort())

    conf_obj.setDefaultValue('logs/api-enabled', 'false')
    conf_obj.setDefaultValue('logs/automat-transitions-enabled', 'false')
    conf_obj.setDefaultValue('logs/automat-events-enabled', 'false')
    conf_obj.setDefaultValue('logs/debug-level', settings.defaultDebugLevel())
    conf_obj.setDefaultValue('logs/memdebug-enabled', 'false')
    conf_obj.setDefaultValue('logs/memdebug-port', '9996')
    conf_obj.setDefaultValue('logs/memprofile-enabled', 'false')
    conf_obj.setDefaultValue('logs/packet-enabled', 'false')
    conf_obj.setDefaultValue('logs/stream-enabled', 'false')
    conf_obj.setDefaultValue('logs/stream-port', settings.DefaultWebLogPort())
    conf_obj.setDefaultValue('logs/traffic-enabled', 'false')
    conf_obj.setDefaultValue('logs/traffic-port', settings.DefaultWebTrafficPort())

    conf_obj.setDefaultValue('paths/backups', '')
    conf_obj.setDefaultValue('paths/customers', '')
    conf_obj.setDefaultValue('paths/messages', '')
    conf_obj.setDefaultValue('paths/receipts', '')
    conf_obj.setDefaultValue('paths/restore', '')

    conf_obj.setDefaultValue('personal/private-key-size', settings.DefaultPrivateKeySize())

    conf_obj.setDefaultValue('services/accountant/enabled', 'false')

    conf_obj.setDefaultValue('services/api-router/enabled', 'false')
    conf_obj.setDefaultValue('services/api-router/host', '127.0.0.1')
    conf_obj.setDefaultValue('services/api-router/port', settings.DefaultWebSocketRouterPort())

    conf_obj.setDefaultValue('services/backup-db/enabled', 'true')

    conf_obj.setDefaultValue('services/backups/enabled', 'true')
    conf_obj.setDefaultValue('services/backups/block-size', diskspace.MakeStringFromBytes(settings.DefaultBackupBlockSize()))
    conf_obj.setDefaultValue('services/backups/max-block-size', diskspace.MakeStringFromBytes(settings.DefaultBackupMaxBlockSize()))
    conf_obj.setDefaultValue('services/backups/max-copies', '2')
    conf_obj.setDefaultValue('services/backups/keep-local-copies-enabled', 'true')
    conf_obj.setDefaultValue('services/backups/wait-suppliers-enabled', 'true')

    conf_obj.setDefaultValue('services/blockchain-id/enabled', 'true')

    conf_obj.setDefaultValue('services/blockchain-authority/enabled', 'false')
    conf_obj.setDefaultValue('services/blockchain-authority/registration-bonus-coins', 100)
    conf_obj.setDefaultValue('services/blockchain-authority/requests-reading-offset', 0)
    conf_obj.setDefaultValue('services/blockchain-authority/requests-reading-limit', 50)

    conf_obj.setDefaultValue('services/blockchain-explorer/enabled', 'false')
    conf_obj.setDefaultValue('services/blockchain-explorer/host', '127.0.0.1')
    conf_obj.setDefaultValue('services/blockchain-explorer/web-port', 19080)

    conf_obj.setDefaultValue('services/bismuth-blockchain/enabled', 'true')

    conf_obj.setDefaultValue('services/bismuth-node/enabled', 'false')
    conf_obj.setDefaultValue('services/bismuth-node/host', '127.0.0.1')
    conf_obj.setDefaultValue('services/bismuth-node/tcp-port', 15658)

    conf_obj.setDefaultValue('services/bismuth-wallet/enabled', 'true')

    conf_obj.setDefaultValue('services/bismuth-pool/enabled', 'false')
    conf_obj.setDefaultValue('services/bismuth-pool/host', '127.0.0.1')
    conf_obj.setDefaultValue('services/bismuth-pool/tcp-port', 18525)

    conf_obj.setDefaultValue('services/bismuth-miner/enabled', 'false')

    conf_obj.setDefaultValue('services/bismuth-identity/enabled', 'true')

    conf_obj.setDefaultValue('services/broadcasting/enabled', 'false')
    conf_obj.setDefaultValue('services/broadcasting/routing-enabled', 'false')
    conf_obj.setDefaultValue('services/broadcasting/max-broadcast-connections', '3')

    conf_obj.setDefaultValue('services/contract-chain/enabled', 'false')

    conf_obj.setDefaultValue('services/customer/enabled', 'true')
    conf_obj.setDefaultValue('services/customer/needed-space', diskspace.MakeStringFromBytes(settings.DefaultNeededBytes()))
    conf_obj.setDefaultValue('services/customer/suppliers-number', settings.DefaultDesiredSuppliers())

    conf_obj.setDefaultValue('services/customer-contracts/enabled', 'true')

    conf_obj.setDefaultValue('services/customer-family/enabled', 'true')

    conf_obj.setDefaultValue('services/customer-patrol/enabled', 'true')
    conf_obj.setDefaultValue('services/customer-patrol/customer-idle-days', 14)

    conf_obj.setDefaultValue('services/customer-support/enabled', 'true')

    conf_obj.setDefaultValue('services/data-disintegration/enabled', 'true')

    conf_obj.setDefaultValue('services/data-motion/enabled', 'true')
    conf_obj.setDefaultValue('services/data-motion/supplier-request-queue-size', 4)
    conf_obj.setDefaultValue('services/data-motion/supplier-sending-queue-size', 4)

    conf_obj.setDefaultValue('services/entangled-dht/enabled', 'true')
    conf_obj.setDefaultValue('services/entangled-dht/udp-port', settings.DefaultDHTPort())
    conf_obj.setDefaultValue('services/entangled-dht/known-nodes', '')
    conf_obj.setDefaultValue('services/entangled-dht/attached-layers', '')

    conf_obj.setDefaultValue('services/employer/enabled', 'true')
    conf_obj.setDefaultValue('services/employer/replace-critically-offline-enabled', 'true')
    conf_obj.setDefaultValue('services/employer/candidates', '')

    conf_obj.setDefaultValue('services/gateway/enabled', 'true')
    conf_obj.setDefaultValue('services/gateway/p2p-timeout', 15)

    conf_obj.setDefaultValue('services/http-connections/enabled', 'false')
    conf_obj.setDefaultValue('services/http-connections/http-port', settings.DefaultHTTPPort())

    conf_obj.setDefaultValue('services/http-transport/enabled', 'false')  # not done yet
    conf_obj.setDefaultValue('services/http-transport/receiving-enabled', 'true')
    conf_obj.setDefaultValue('services/http-transport/sending-enabled', 'true')
    conf_obj.setDefaultValue('services/http-transport/priority', 50)

    conf_obj.setDefaultValue('services/identity-server/enabled', 'false')
    conf_obj.setDefaultValue('services/identity-server/host', '')
    conf_obj.setDefaultValue('services/identity-server/tcp-port', settings.IdentityServerPort())
    conf_obj.setDefaultValue('services/identity-server/web-port', settings.IdentityWebPort())

    conf_obj.setDefaultValue('services/identity-propagate/enabled', 'true')
    conf_obj.setDefaultValue('services/identity-propagate/known-servers', '')
    conf_obj.setDefaultValue('services/identity-propagate/preferred-servers', '')
    conf_obj.setDefaultValue('services/identity-propagate/min-servers', 2)
    conf_obj.setDefaultValue('services/identity-propagate/max-servers', 5)
    conf_obj.setDefaultValue('services/identity-propagate/automatic-rotate-enabled', 'true')
    conf_obj.setDefaultValue('services/identity-propagate/health-check-interval-seconds', 60*5)

    conf_obj.setDefaultValue('services/joint-postman/enabled', 'true')

    conf_obj.setDefaultValue('services/ip-port-responder/enabled', 'true')

    conf_obj.setDefaultValue('services/keys-registry/enabled', 'true')

    conf_obj.setDefaultValue('services/keys-storage/enabled', 'true')
    conf_obj.setDefaultValue('services/keys-storage/reset-unreliable-backup-copies', 'true')

    conf_obj.setDefaultValue('services/list-files/enabled', 'true')

    conf_obj.setDefaultValue('services/message-history/enabled', 'true')

    conf_obj.setDefaultValue('services/miner/enabled', 'false')

    conf_obj.setDefaultValue('services/my-data/enabled', 'true')

    conf_obj.setDefaultValue('services/my-ip-port/enabled', 'true')

    conf_obj.setDefaultValue('services/network/enabled', 'true')
    conf_obj.setDefaultValue('services/network/proxy/enabled', 'false')
    conf_obj.setDefaultValue('services/network/proxy/host', '')
    conf_obj.setDefaultValue('services/network/proxy/password', '')
    conf_obj.setDefaultValue('services/network/proxy/port', '')
    conf_obj.setDefaultValue('services/network/proxy/ssl', 'false')
    conf_obj.setDefaultValue('services/network/proxy/username', '')
    conf_obj.setDefaultValue('services/network/receive-limit', settings.DefaultBandwidthInLimit())
    conf_obj.setDefaultValue('services/network/send-limit', settings.DefaultBandwidthOutLimit())

    conf_obj.setDefaultValue('services/nodes-lookup/enabled', 'true')

    conf_obj.setDefaultValue('services/p2p-hookups/enabled', 'true')

    conf_obj.setDefaultValue('services/p2p-notifications/enabled', 'true')

    conf_obj.setDefaultValue('services/personal-messages/enabled', 'true')

    conf_obj.setDefaultValue('services/private-groups/enabled', 'true')
    conf_obj.setDefaultValue('services/private-groups/message-ack-timeout', 30)
    conf_obj.setDefaultValue('services/private-groups/broker-connect-timeout', 120)
    conf_obj.setDefaultValue('services/private-groups/preferred-brokers', '')

    conf_obj.setDefaultValue('services/private-messages/enabled', 'true')
    conf_obj.setDefaultValue('services/private-messages/acknowledge-unread-messages-enabled', 'true')

    conf_obj.setDefaultValue('services/proxy-server/enabled', 'false')
    conf_obj.setDefaultValue('services/proxy-server/routes-limit', 20)
    conf_obj.setDefaultValue('services/proxy-server/current-routes', '{}')

    conf_obj.setDefaultValue('services/proxy-transport/enabled', 'true')
    conf_obj.setDefaultValue('services/proxy-transport/sending-enabled', 'true')
    conf_obj.setDefaultValue('services/proxy-transport/receiving-enabled', 'true')
    conf_obj.setDefaultValue('services/proxy-transport/priority', 100)
    conf_obj.setDefaultValue('services/proxy-transport/preferred-routers', '')
    # conf_obj.setDefaultValue('services/proxy-transport/router-lifetime-seconds', 600)
    # TODO: those two settings needs to be removed.
    # if service require storing locally a value which user should not modify we better move it to another place
    # in the future we can split those local data files in more structural way and move into
    # ~/.bitdust/[network name]/services/*/ sub folders
    conf_obj.setDefaultValue('services/proxy-transport/my-original-identity', '')
    conf_obj.setDefaultValue('services/proxy-transport/current-router', '')

    conf_obj.setDefaultValue('services/rebuilding/enabled', 'true')

    conf_obj.setDefaultValue('services/restores/enabled', 'true')

    conf_obj.setDefaultValue('services/shared-data/enabled', 'true')

    conf_obj.setDefaultValue('services/supplier/enabled', 'true')
    conf_obj.setDefaultValue('services/supplier/donated-space', diskspace.MakeStringFromBytes(settings.DefaultDonatedBytes()))

    conf_obj.setDefaultValue('services/supplier-contracts/enabled', 'true')
    conf_obj.setDefaultValue('services/supplier-contracts/initial-duration-hours', 6)
    conf_obj.setDefaultValue('services/supplier-contracts/duration-raise-factor', 2.0)

    conf_obj.setDefaultValue('services/tcp-connections/enabled', 'true')
    conf_obj.setDefaultValue('services/tcp-connections/tcp-port', settings.DefaultTCPPort())
    conf_obj.setDefaultValue('services/tcp-connections/upnp-enabled', 'true')

    conf_obj.setDefaultValue('services/tcp-transport/enabled', 'true')
    conf_obj.setDefaultValue('services/tcp-transport/receiving-enabled', 'true')
    conf_obj.setDefaultValue('services/tcp-transport/sending-enabled', 'true')
    conf_obj.setDefaultValue('services/tcp-transport/priority', 10)

    conf_obj.setDefaultValue('services/udp-datagrams/enabled', 'true')
    conf_obj.setDefaultValue('services/udp-datagrams/udp-port', settings.DefaultUDPPort())

    # TODO: UDP transport was temporary switched off
    conf_obj.setDefaultValue('services/udp-transport/enabled', 'false')
    conf_obj.setDefaultValue('services/udp-transport/receiving-enabled', 'true')
    conf_obj.setDefaultValue('services/udp-transport/sending-enabled', 'true')
    conf_obj.setDefaultValue('services/udp-transport/priority', 20)
