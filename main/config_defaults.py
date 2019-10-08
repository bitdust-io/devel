

def reset(conf_obj):
    """
    Configure default values for all BitDust local settings inside ~/.bitdust/config/ folder.

    Every option must have a default value, however there are exceptions possible.
    
    Here all items suppose to have some widget in UI to interact with human.
    Keep it simple and understandable.
    """
    from lib import diskspace
    from main import settings
    
    conf_obj.setDefaultValue('interface/api/json-rpc-enabled', 'true')
    conf_obj.setDefaultValue('interface/api/json-rpc-port', settings.DefaultJsonRPCPort())

    conf_obj.setDefaultValue('interface/api/rest-http-enabled', 'true')
    conf_obj.setDefaultValue('interface/api/rest-http-port', settings.DefaultRESTHTTPPort())

    conf_obj.setDefaultValue('interface/ftp/enabled', 'true')
    conf_obj.setDefaultValue('interface/ftp/port', settings.DefaultFTPPort())

    conf_obj.setDefaultValue('logs/debug-level', settings.defaultDebugLevel())
    conf_obj.setDefaultValue('logs/memdebug-enabled', 'false')
    conf_obj.setDefaultValue('logs/memdebug-port', '9996')
    conf_obj.setDefaultValue('logs/memprofile-enabled', 'false')
    conf_obj.setDefaultValue('logs/stream-enabled', 'false')
    conf_obj.setDefaultValue('logs/stream-port', settings.DefaultWebLogPort())
    conf_obj.setDefaultValue('logs/traffic-enabled', 'false')
    conf_obj.setDefaultValue('logs/traffic-port', settings.DefaultWebTrafficPort())
    conf_obj.setDefaultValue('logs/packet-enabled', 'false')

    conf_obj.setDefaultValue('paths/backups', '')
    conf_obj.setDefaultValue('paths/customers', '')
    conf_obj.setDefaultValue('paths/messages', '')
    conf_obj.setDefaultValue('paths/receipts', '')
    conf_obj.setDefaultValue('paths/restore', '')

    conf_obj.setDefaultValue('personal/private-key-size', settings.DefaultPrivateKeySize())
    conf_obj.setDefaultValue('personal/betatester', 'false')
    conf_obj.setDefaultValue('personal/email', '')
    conf_obj.setDefaultValue('personal/name', '')
    conf_obj.setDefaultValue('personal/nickname', '')
    conf_obj.setDefaultValue('personal/surname', '')

    conf_obj.setDefaultValue('services/accountant/enabled', 'false')

    conf_obj.setDefaultValue('services/backup-db/enabled', 'true')

    conf_obj.setDefaultValue('services/backups/enabled', 'true')
    conf_obj.setDefaultValue('services/backups/block-size', diskspace.MakeStringFromBytes(settings.DefaultBackupBlockSize()))
    conf_obj.setDefaultValue('services/backups/max-block-size', diskspace.MakeStringFromBytes(settings.DefaultBackupMaxBlockSize()))
    conf_obj.setDefaultValue('services/backups/max-copies', '2')
    conf_obj.setDefaultValue('services/backups/keep-local-copies-enabled', 'true')
    conf_obj.setDefaultValue('services/backups/wait-suppliers-enabled', 'true')

    conf_obj.setDefaultValue('services/blockchain/enabled', 'false')
    conf_obj.setDefaultValue('services/blockchain/host', '127.0.0.1')
    conf_obj.setDefaultValue('services/blockchain/port', 9100)
    conf_obj.setDefaultValue('services/blockchain/seeds', '')
    conf_obj.setDefaultValue('services/blockchain/explorer/enabled', 'true')
    conf_obj.setDefaultValue('services/blockchain/explorer/port', 9180)
    conf_obj.setDefaultValue('services/blockchain/wallet/enabled', 'true')
    conf_obj.setDefaultValue('services/blockchain/wallet/port', 9280)
    conf_obj.setDefaultValue('services/blockchain/miner/enabled', 'false')

    conf_obj.setDefaultValue('services/broadcasting/enabled', 'false')
    conf_obj.setDefaultValue('services/broadcasting/routing-enabled', 'false')
    conf_obj.setDefaultValue('services/broadcasting/max-broadcast-connections', '3')

    conf_obj.setDefaultValue('services/contract-chain/enabled', 'false')

    conf_obj.setDefaultValue('services/customer/enabled', 'true')
    conf_obj.setDefaultValue('services/customer/needed-space', diskspace.MakeStringFromBytes(settings.DefaultNeededBytes()))
    conf_obj.setDefaultValue('services/customer/suppliers-number', settings.DefaultDesiredSuppliers())

    conf_obj.setDefaultValue('services/customer-contracts/enabled', 'false')

    conf_obj.setDefaultValue('services/customer-family/enabled', 'true')

    conf_obj.setDefaultValue('services/customer-patrol/enabled', 'true')

    conf_obj.setDefaultValue('services/customer-support/enabled', 'true')

    conf_obj.setDefaultValue('services/data-motion/enabled', 'true')
    conf_obj.setDefaultValue('services/data-motion/supplier-request-queue-size', 4)            
    conf_obj.setDefaultValue('services/data-motion/supplier-sending-queue-size', 4)            

    conf_obj.setDefaultValue('services/entangled-dht/enabled', 'true')
    conf_obj.setDefaultValue('services/entangled-dht/udp-port', settings.DefaultDHTPort())
    conf_obj.setDefaultValue('services/entangled-dht/known-nodes', '')
    conf_obj.setDefaultValue('services/entangled-dht/node-id', '')

    conf_obj.setDefaultValue('services/employer/enabled', 'true')
    conf_obj.setDefaultValue('services/employer/candidates', '')

    conf_obj.setDefaultValue('services/gateway/enabled', 'true')

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
    conf_obj.setDefaultValue('services/identity-propagate/min-servers', settings.MinimumIdentitySources() + 1)
    conf_obj.setDefaultValue('services/identity-propagate/max-servers', int(settings.MaximumIdentitySources() / 2))
    conf_obj.setDefaultValue('services/identity-propagate/automatic-rotate-enabled', 'false')
    conf_obj.setDefaultValue('services/identity-propagate/health-check-interval-seconds', 60*5)

    conf_obj.setDefaultValue('services/ip-port-responder/enabled', 'true')

    conf_obj.setDefaultValue('services/keys-registry/enabled', 'true')

    conf_obj.setDefaultValue('services/keys-storage/enabled', 'true')

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

    conf_obj.setDefaultValue('services/private-messages/enabled', 'true')

    conf_obj.setDefaultValue('services/proxy-server/enabled', 'true')
    conf_obj.setDefaultValue('services/proxy-server/routes-limit', 10)
    conf_obj.setDefaultValue('services/proxy-server/current-routes', '{}')

    conf_obj.setDefaultValue('services/proxy-transport/enabled', 'true')
    conf_obj.setDefaultValue('services/proxy-transport/sending-enabled', 'true')
    conf_obj.setDefaultValue('services/proxy-transport/receiving-enabled', 'true')
    conf_obj.setDefaultValue('services/proxy-transport/priority', 100)
    conf_obj.setDefaultValue('services/proxy-transport/preferred-routers', '')
    conf_obj.setDefaultValue('services/proxy-transport/router-lifetime-seconds', 600)
    # TODO: those two settings needs to be removed.
    # if service require storing locally value which user should not modify be implemented
    # inside service (for example read/write to local file inside ~/.bitdust/*/ folder)
    # in the future we can split all files more structural way into ~/.bitdust/services/*/ sub folders
    conf_obj.setDefaultValue('services/proxy-transport/my-original-identity', '')
    conf_obj.setDefaultValue('services/proxy-transport/current-router', '')

    conf_obj.setDefaultValue('services/rebuilding/enabled', 'true')

    conf_obj.setDefaultValue('services/restores/enabled', 'true')

    conf_obj.setDefaultValue('services/shared-data/enabled', 'true')

    conf_obj.setDefaultValue('services/supplier/enabled', 'true')
    conf_obj.setDefaultValue('services/supplier/donated-space', diskspace.MakeStringFromBytes(settings.DefaultDonatedBytes()))

    conf_obj.setDefaultValue('services/supplier-contracts/enabled', 'false')

    conf_obj.setDefaultValue('services/supplier-relations/enabled', 'false')

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

