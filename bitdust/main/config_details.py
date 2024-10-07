#!/usr/bin/python
# config_details.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (config_details.py) is part of BitDust Software.
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

module:: config_details
"""


def raw():
    """
    In case option does not have any description here it will be marked as "internal".
    The "internal" options are not displayed in the UI, but still can be manipulated via API or command line.
    """
    return """
{interface/api/auth-secret-enabled}

{interface/api/rest-http-enabled}

{interface/api/rest-http-port}

{interface/api/web-socket-enabled}

{interface/api/web-socket-port}

{interface/ftp/enabled}

{interface/ftp/port}

{logs/api-enabled} log API calls
Enable logging of all API calls that reach the main process to the `~/.bitdust/logs/api.log` file.

{logs/automat-events-enabled} log state machines events
This option enables logging of all events that are submitted to state machines, see `~/.bitdust/logs/automats.log` file.

{logs/automat-transitions-enabled} log state machines transitions
By enabling this option, you can also monitor the life cycle of each state machine running in the main process, see `~/.bitdust/logs/automats.log` file.

{logs/debug-level} debug level
Higher values of `debug-level` option will produce more log messages in the console output, see `~/.bitdust/logs/stdout.log` file.

{logs/packet-enabled} log network packets
This option enables logging of all incoming & outgoing peer-to-peer packets - very helpful when analyzing/debugging network communications, see `~/.bitdust/logs/packet.log` file.

{logs/stream-enabled}

{logs/stream-port}

{logs/traffic-enabled}

{logs/traffic-port}


{paths/backups}

{paths/customers}

{paths/messages}

{paths/receipts}

{paths/restore}


[personal/private-key-size] RSA private key size
This value you specified when created your identity file for the first time.

{services/accountant/enabled} enable accountant service
The service is under development.

{services/backup-db/enabled} enable backup-db service
The `backup-db` service is responsible for storing service information about your files uploaded to the network, such as: file name, version, size.

{services/backups/enabled} enable data uploading
This service enables uploading of encrypted personal data to the BitDust network.

{services/backups/block-size} preferred block size
Large files are also divided by chunks during uploading, that parameter defines preferred block size in bytes
which is used to split the raw data during uploading.

{services/backups/max-block-size} maximum block size
Maximum block size in bytes which used to split the raw data during uploading process.
The actual block size is calculated depending on size of the particular backup to optimize performance and data storage.
If you plan to do a large file uploads - set higher values to increase the performance.

{services/backups/keep-local-copies-enabled} keep locally copies of uploaded files
Enable this to keep a copy of every uploaded file on your local disk as well as on remote machines of your suppliers.
This increases data reliability, rebuilding performance and decrease network load, but consumes much storage space of your own device.

{services/backups/max-copies} number of copies
When you upload same file multiple times data is not overwritten - another version is created instead.
This value indicates how many versions of same uploaded file must be stored on remote suppliers.
The oldest copies are removed automatically. A value of `0` indicates unlimited number of versions.

{services/backups/wait-suppliers-enabled} extra check after 24 hours
When critical amount of your suppliers become unreliable - your uploaded data is lost completely.
Enable this option to wait for 24 hours after any file upload and perform an extra check of all suppliers before cleaning up the local copy.
This is a compromise solution that does not sacrifice reliability but also decrease local storage consumption.

{services/broadcasting/enabled} send & receive encrypted broadcast messages
The service is under development.

{services/broadcasting/routing-enabled}

{services/broadcasting/max-broadcast-connections}

{services/contract-chain/enabled} accounting of spent & donated resources
The service is under development.

{services/customer/enabled} store encrypted data on other nodes
To be able to upload files to the BitDust network other nodes, called suppliers, must be already connected and allocate storage space for you.
The `customer` service is responsible for maintaining real-time connections with all of your suppliers and requesting storage space automatically.

{services/customer/needed-space} needed space
How much storage space do you require to store your uploaded files?
**WARNING!** When your uploaded files exceed the quota size you set here the older versions will be automatically erased by suppliers.

{services/customer/suppliers-number} number of suppliers
Number of suppliers who stores your encrypted files. You may select one of the following values: 2, 4, 7, 13, 18, 26, 64.
**WARNING!** You will lose all of your uploaded files when changing preferred number of suppliers.

{services/customer-contracts/enabled} digitally signed customer contracts
The service is under development.

{services/customer-family/enabled} maintain service info for my customers
When `supplier` service is enabled and started your device will also write additional service information to distributed hash table.
This way people are able to access encrypted shared files of each other on different suppliers across the network.

{services/customer-patrol/enabled} reject customers who are out of quota
When you are running `supplier` service other users are able to store files on your device.
The `customer-patrol` service makes sure that your customers do not exceed requested and agreed storage quotas.

{services/customer-patrol/customer-idle-days} customer idle limit
This option enables few periodic checks and will auto-reject customers who are no longer using your device to store any data.
Specify number of days of customer inactivity before user will be rejected and data erased automatically.
A value of `0` disables the feature.

{services/customer-support/enabled} assist my customers
This service performs periodic synchronization for your customers when you also enabled the `supplier` service and thus agreed to store encrypted data for them.
Your device will try to reconnect with all known customers and keep them up to date with the full list of files they own.

{services/data-disintegration/enabled} enable RAID & ECC data processing
Before the encrypted data is sent to the target storage nodes, it will be chunked and processed.
Each fragment corresponds to a supplier position in accordance with the number of suppliers you have selected.
Data processing includes error correction codes and redundancy to enable restoration of missing fragments in the future.

{services/data-motion/enabled} streaming of encrypted data
The service creates a queue of incoming and outgoing encrypted fragments of your data when uploading and downloading from the nodes of remote providers.

{services/data-motion/supplier-request-queue-size} concurrent outgoing packets
Determines the maximum number of encrypted data packets sent at the same time.
Affects the speed of data uploading to the suppliers' machines.

{services/data-motion/supplier-sending-queue-size} concurrent incoming packets
Determines the maximum number of simultaneously received encrypted data packets.
Affects the speed of data downloading from the suppliers' machines.

{services/entangled-dht/enabled} distributed hash-table node
Your device becomes one of the peers in the DHT network.
Provides the ability to read and write to a distributed hash table and access networking service layers.

{services/entangled-dht/udp-port} UDP port number
Set a UDP port number to be used for distributed hash-table communications.

{services/entangled-dht/known-nodes} override seed-nodes list
For the initial entrance to the DHT network, a list of so-called seed-nodes is required.
In the future, your device will work autonomously - thanks to the local routing table.
This value allows you to override the initial set of hard-coded seed-nodes and is intended for advanced software use.

{services/entangled-dht/attached-layers} override attached DHT layers
The software supports several local routing tables for the ability to store service data on the DHT at different parallel "layers".
This allows the network services to be separated from each other and also makes possible to run lookups in the DHT more faster.
On startup, your device will be automatically connected to some of the layers.
This value overrides this list and is intended for advanced software use.

{services/employer/enabled} search & connect with available suppliers
In order to store data on the network, you must already have your suppliers ready and accepting your uploads.
The `employer` network service automatically searches for new suppliers through the DHT network and monitors their reliability.

{services/employer/replace-critically-offline-enabled} automatically replace unreliable suppliers
The moment a critical number of your suppliers become unreliable, your uploaded data is no longer available for downloading.
When this option is enabled, your software will automatically replace the unreliable supplier when needed and reconstruct missing fragments.

{services/employer/candidates} candidates list
Place here a comma-separated list of nodes identifiers, in IDURL format, to be used first when the service tries to find a new supplier for you.
This way you can control who will be your supplier and where your data is stored.
Option is intended for advanced software use.

{services/gateway/enabled} enable encrypted peer-to-peer traffic
You can use `TCP`, `UDP`, and other network protocols to communicate with people on the network.
The `gateway` service controls application transport protocols and all encrypted packets passing through and reaching application engine.
Every incoming packet is digitally verified here, processed and sent to the underlying services.

{services/gateway/p2p-timeout} peer-to-peer reply timeout
Due to network failures or slowness, signed peer-to-peer packets are considered as "undelivered" without receiving a confirmation of delivery within the specified number of seconds.

{services/http-connections/enabled} HTTP enabled
This will allow BitDust to use the HTTP protocol for service data and encrypted traffic

{services/http-connections/http-port} HTTP port number
That option defines a port number to be used to listen for incoming HTTP connections.

{services/http-transport/enabled} use HTTP as a transport protocol
Your BitDust node must have at least one active and reliable transport protocol to be able
to connect to other nodes via Internet.
The service is under development.

{services/http-transport/receiving-enabled} receiving via HTTP
Disable this option if you do not want other nodes to send you encrypted data over HTTP and use transport protocol in unidirectional mode.

{services/http-transport/sending-enabled} sending via HTTP
Disable this option if you do not want to send encrypted data over HTTP and use transport protocol in unidirectional mode.

{services/http-transport/priority} priority
You can change this setting if you want BitDust to use the `http-transport` more often than other transport protocols.
Lower values have higher priority.

{services/identity-propagate/enabled} signed identity files exchange
Your identity file stores service information that is used by other nodes when they connect to your device to transfer data.
This service manages the synchronization and propagating of your identity file, and also remembers the identity files of other users.

{services/identity-propagate/known-servers}

{services/identity-propagate/preferred-servers}

{services/identity-propagate/min-servers}

{services/identity-propagate/max-servers}

{services/identity-propagate/automatic-rotate-enabled} automatic identity rotation
Automatically replaces untrusted ID servers - nodes that store a copy of your identity file.
This way, your device will remain identifiable on the network even when it is offline.

{services/identity-propagate/health-check-interval-seconds} health check interval
The period in seconds between checks that could potentially cause an automatic identity rotation when your primary ID server is down.

{services/identity-server/enabled} start Identity server
You can start own Identity server and store identity files of other users on your machine.
This will help others to join and operate in the BitDust network.

{services/identity-server/host} your server host name
Each ID server must have a unique address within the network, set your external IP address or domain name here.

{services/identity-server/tcp-port} TCP port number
TCP transport protocol is used for receiving digitally-signed identity files from other nodes.
That option defines TCP port number to be used to listen for incoming connections.

{services/identity-server/web-port} HTTP port number
Port number for Identity server HTTP interface.
This is used when other nodes are "reading" identity files from your Identity server.

{services/ip-port-responder/enabled} reply STUN requests
Helps other hosts connect to the network.
When the device is behind a NAT router, additional steps are required to determine the real external IP address.

{services/keys-registry/enabled} enables keys management
Keeps track of all your RSA keys that are used to encrypt files and messages.

{services/keys-storage/enabled} enable keys synchronization
The service maintains an encrypted backup of every RSA key you possess on your suppliers so that you can recover the keys and encrypted data in case of loss.

{services/keys-storage/reset-unreliable-backup-copies} reset unreliable backup copies
In worst scenario, when your suppliers are not reliable anymore and uploaded data got lost, software will be blocked trying to synchronize your keys.
This setting helps to overcome this situation by using locally stored copies of the keys.

{services/list-files/enabled} exchange service data with suppliers
The supplier does not know the real name of the file you uploaded to the network, but stores indexed fragments of your encrypted data.
The `list-files` service synchronizes index data and file lists with your suppliers.

{services/message-history/enabled} store messaging history
All your conversations are stored in a local SQLite3 database and are quickly searchable.

{services/miner/enabled} enable blockchain mining
The service is under development.

{services/my-data/enabled} remote files indexing
The service synchronizes with my suppliers in real time and prepares the encrypted storage environment for other dependent network services.

{services/my-ip-port/enabled} detect my external IP via other nodes
The service relies on other nodes and uses the STUN protocol to recognize your public IP address when connecting to the network.

{services/network/enabled} network is enabled
Basic network service of the application. If you disable it, all other network services will be turned off as well and your device will go offline.

{services/network/proxy/enabled}

{services/network/proxy/host}

{services/network/proxy/password}

{services/network/proxy/port}

{services/network/proxy/ssl}

{services/network/proxy/username}

{services/network/receive-limit} limit incoming traffic
The value in bytes per second to limit incoming network traffic.
Set value to `0` if you do not want to limit your incoming traffic.

{services/network/send-limit} limit outgoing traffic
The value in bytes per second to limit outgoing network traffic.
Set value to `0` if you do not want to limit your outgoing traffic.

{services/nodes-lookup/enabled} lookup nodes via DHT
The `network-lookup` service allows nodes to find each other in distributed hash table and initiate direct peer-to-peer connection when resources need to be allocated.

{services/p2p-hookups/enabled} peer-to-peer connections
The service is responsible for starting and maintaining direct network connections with other nodes in order to be able to transfer personal data instantly.

{services/p2p-notifications/enabled} events & notifications delivery
Supports other network services while sending and receiving service events.

{services/personal-messages/enabled} personal messages
Allows you to read incoming encrypted messages even when your device is disconnected.
Other nodes, called "message brokers", will maintain a stream of messages that you can subscribe to and receive at any time.

{services/private-groups/enabled} group communications
Allows the exchange of encrypted messages with multiple users using the same secret key through message brokers.

{services/private-groups/message-ack-timeout} acknowledgment timeout
Defines a timeout in seconds for an acknowledgment after sending encrypted message to message broker.

{services/private-groups/broker-connect-timeout} connect timeout
Defines a timeout in seconds for an acknowledgment from message broker while connecting to the group.

{services/private-groups/preferred-brokers}

{services/private-messages/enabled} encrypted peer-to-peer messaging
Enables peer-to-peer sending & receiving of encrypted JSON messages and also supports underlying services.

{services/private-messages/acknowledge-unread-messages-enabled}

{services/proxy-server/enabled} help others transmit encrypted traffic
Your device will act as an intermediate node and help other users stay connected to the network and exchange encrypted packets with each other.
This will consume your Internet traffic.

{services/proxy-server/routes-limit} maximum simultaneous connections
This option sets a limit on the number of connections your device will support at any given time.

{services/proxy-server/current-routes}

{services/proxy-transport/enabled} use intermediate nodes
The `proxy-transport` network protocol allows you to use another user's device as an intermediate node for encrypted data exchange.
This solves certain problems when connecting to the network and also makes your network connection more anonymous.

{services/proxy-transport/receiving-enabled} receiving enabled
Disable this option if you do not want other nodes to send you encrypted data via intermediate node and use that transport protocol in unidirectional mode.

{services/proxy-transport/sending-enabled} sending enabled
Disable this option if you do not want to send encrypted data via intermediate node and use that transport protocol in unidirectional mode.

{services/proxy-transport/priority} priority
You can change this setting if you want BitDust to use the `proxy-transport` more often than other transport protocols.
Lower values have higher priority.

{services/proxy-transport/my-original-identity}

{services/proxy-transport/current-router}

{services/proxy-transport/preferred-routers}

{services/proxy-transport/router-lifetime-seconds}

{services/rebuilding/enabled} automatic data rebuilding
When one of your suppliers is not available for some reason, all encrypted fragments that he stored for you are lost.
The `rebuilding` service will automatically download the available fragments from those suppliers that are still online, and "rebuild" the lost fragments that the new supplier receives.
**WARNING!** At the moment when a critical number of fragments are lost, downloading data is no longer possible.

{services/restores/enabled} enable data downloading
Controls network connections and incoming data streams when downloading encrypted fragments from suppliers nodes.

{services/shared-data/enabled} enable data sharing
Makes possible decentralized sharing of encrypted files with other users.

{services/supplier/enabled} donate own disk space to other users
To make it possible to store any files on the network, some other nodes must already be connected and provide storage space.
The `supplier` service allocates a part of your disk and serves encrypted files uploaded to your device from remote nodes.

{services/supplier/donated-space} donated space
The amount of storage space you want to donate to other users.

{services/supplier-contracts/enabled} digitally signed supplier contracts
The service is under development.

{services/tcp-connections/enabled} TCP enabled
This will allow BitDust to use the TCP protocol for service data and encrypted traffic

{services/tcp-connections/tcp-port}
Port number to listen for incoming TCP connections.

[services/tcp-connections/upnp-enabled]
The feature is under development and temporarily disabled.

{services/tcp-transport/enabled} use TCP as a transport protocol
BitDust can use different protocols to transfer packets across the network.
Your node must have at least one active and reliable transport protocol to be able
to connect to other nodes via Internet.

{services/tcp-transport/receiving-enabled} receiving via TCP
Disable this option if you do not want other nodes to send you encrypted data over TCP and use `tcp-transport` in unidirectional mode.

{services/tcp-transport/sending-enabled} sending via TCP
Disable this option if you do not want to send encrypted data over TCP and use `tcp-transport` in unidirectional mode.

{services/tcp-transport/priority} priority
You can change this setting if you want BitDust to use the `tcp-transport` more often than other transport protocols.
Lower values have higher priority.

{services/udp-datagrams/enabled} UDP enabled
This will allow BitDust to use the UDP protocol for service data and encrypted traffic.

{services/udp-datagrams/udp-port}
Port number to listen for incoming UDP datagrams.

[services/udp-transport/enabled] use UDP as a transport protocol
BitDust can use different protocols to transfer packets across the network.
Your node must have at least one active and reliable transport protocol to be able
to connect to other nodes via Internet.
The service is under development.

[services/udp-transport/receiving-enabled]
Disable this option if you do not want other nodes to send you encrypted data over UDP and use `udp-transport` in unidirectional mode.

[services/udp-transport/sending-enabled]
Disable this option if you do not want to send encrypted data over UDP and use `udp-transport` in unidirectional mode.

[services/udp-transport/priority]
You can change this setting if you want BitDust to use the `udp-transport` more often than other transport protocols.
Lower values have higher priority.
"""
