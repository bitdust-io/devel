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
    # in case option does not have any description it will be marked as "internal"
    # "internal" options should not be displayed in the UI and so must not be available to the user
    return """
{interface/api/json-rpc-enabled}

{interface/api/json-rpc-port}

{interface/api/rest-http-enabled}

{interface/api/rest-http-port}

{interface/api/web-socket-enabled}

{interface/api/web-socket-port}

{interface/ftp/enabled}

{interface/ftp/port}

{logs/api-enabled}
Enable logging of all API calls that reach the main process to the `~/.bitdust/logs/api.log` file.

{logs/automat-events-enabled}
This option enables logging of all events that are submitted to state machines, see `~/.bitdust/logs/automats.log` file.

{logs/automat-transitions-enabled}
By enabling this option, you can also monitor the life cycle of each state machine running in the main process, see `~/.bitdust/logs/automats.log` file.

{logs/debug-level}
Higher values of `debug-level` option will produce more log messages in the console output, see `~/.bitdust/logs/main.log` file.

{logs/packet-enabled}
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
This service is under development.

{services/backup-db/enabled} enable backup-db service
The `backup_db()` service is responsible for storing service information about your files stored on the network, such as: name, version, size.

{services/backups/enabled} enable data uploading
This service enables uploading of personal data to the BitDust network.

{services/backups/block-size} preferred block size
Large files are also divided by chunks during uploading, that parameter defines preferred block size in bytes
which is used to split the raw data during uploading.

{services/backups/max-block-size} maximum block size
Maximum block size in bytes which used to split the raw data during uploading process.
The actual block size is calculated depending on size of the particular backup to optimize performance and data storage.
If you plan to do a large file uploads - set higher values to increase the performance.

{services/backups/keep-local-copies-enabled}
Enable this to keep a copy of every new backup on your local HDD as well as on remote machines of your suppliers.
This increases data reliability, rebuilding performance and decrease network load,
but consumes space on your HDD.
Every one Mb of source data uploaded will consume two Mb on your local HDD.


{services/backups/max-copies}

{services/backups/wait-suppliers-enabled}

{services/blockchain/enabled} enable  service

{services/blockchain/host}

{services/blockchain/port}

{services/blockchain/explorer/enabled}

{services/blockchain/explorer/port}

{services/blockchain/wallet/enabled}

{services/blockchain/wallet/port}

{services/blockchain/miner/enabled}

{services/broadcasting/enabled} enable  service

{services/broadcasting/routing-enabled}

{services/broadcasting/max-broadcast-connections}

{services/contract-chain/enabled}

{services/customer/enabled} store encrypted data on other nodes

{services/customer/needed-space}

{services/customer/suppliers-number}

{services/customer-contracts/enabled} enable  service

{services/customer-family/enabled} enable  service

{services/customer-patrol/enabled} enable  service

{services/customer-support/enabled} enable  service

{services/data-disintegration/enabled} enable  service

{services/data-motion/enabled} enable  service

{services/data-motion/supplier-request-queue-size}

{services/data-motion/supplier-sending-queue-size}

{services/entangled-dht/enabled} enable  service

{services/entangled-dht/udp-port}

{services/entangled-dht/known-nodes}

{services/entangled-dht/attached-layers}

{services/employer/enabled} enable  service

{services/employer/replace-critically-offline-enabled}

{services/employer/candidates}

{services/gateway/enabled} enable  service

{services/http-connections/enabled} enable  service

{services/http-connections/http-port}

{services/http-transport/enabled} enable  service

{services/http-transport/receiving-enabled}

{services/http-transport/sending-enabled}

{services/http-transport/priority}

{services/identity-server/enabled} start Identity server
You can start own Identity server and store identity files of other users on your machine.
This will help others to join and operate in the BitDust network.

{services/identity-server/host} your server host name
Each ID server must have a unique address within the network, set your external IP address or domain name here.

{services/identity-server/tcp-port}

{services/identity-server/web-port}

{services/identity-propagate/enabled} enable  service

{services/identity-propagate/known-servers}

{services/identity-propagate/preferred-servers}

{services/identity-propagate/min-servers}

{services/identity-propagate/max-servers}

{services/identity-propagate/automatic-rotate-enabled}

{services/identity-propagate/health-check-interval-seconds}

{services/identity-server/enabled} enable  service

{services/ip-port-responder/enabled} enable  service

{services/keys-registry/enabled} enable  service

{services/keys-storage/enabled} keys synchronization with my suppliers

{services/list-files/enabled} exchange service data with suppliers

{services/message-broker/enabled} help others to stream encrypted messages

{services/message-broker/archive-chunk-size}

{services/message-history/enabled} maintain message history

{services/miner/enabled} enable blockchain mining

{services/my-data/enabled} enable files index synchronization

{services/my-ip-port/enabled} detect my external IP via other nodes

{services/network/enabled} network services are enabled

{services/network/proxy/enabled}

{services/network/proxy/host}

{services/network/proxy/password}

{services/network/proxy/port}

{services/network/proxy/ssl}

{services/network/proxy/username}

{services/network/receive-limit}

{services/network/send-limit}

{services/nodes-lookup/enabled} enable network lookup service

{services/p2p-hookups/enabled} enable peer-to-peer communications

{services/p2p-notifications/enabled} enable peer-to-peer events delivery

{services/personal-messages/enabled} streamed personal notifications

{services/private-groups/enabled} encrypted group messaging

{services/private-groups/message-ack-timeout}

{services/private-groups/preferred-brokers}

{services/private-messages/enabled} encrypted peer-to-peer messaging

{services/private-messages/acknowledge-unread-messages-enabled}

{services/proxy-server/enabled} help others transmit encrypted traffic

{services/proxy-server/routes-limit}

{services/proxy-server/current-routes}

{services/proxy-transport/enabled} route my in/out traffic via extra node

{services/proxy-transport/sending-enabled}

{services/proxy-transport/receiving-enabled}

{services/proxy-transport/priority}

{services/proxy-transport/my-original-identity}

{services/proxy-transport/current-router}

{services/proxy-transport/preferred-routers}

{services/proxy-transport/router-lifetime-seconds}

{services/rebuilding/enabled} automatic data rebuilding

{services/rebuilding/child-processes-enabled}

{services/restores/enabled} enable data downloading

{services/shared-data/enabled} enable data sharing

{services/supplier/donated-space}

{services/supplier/enabled} donate own disk space to people

{services/supplier-contracts/enabled}

{services/tcp-connections/enabled}

{services/tcp-connections/tcp-port}

{services/tcp-connections/upnp-enabled}

{services/tcp-transport/enabled} use TCP as a transport protocol
Your BitDust node must have at least one active and reliable transport protocol to be able
to connect to other nodes via Internet.

{services/tcp-transport/receiving-enabled}

{services/tcp-transport/sending-enabled}

{services/tcp-transport/priority}

{services/udp-datagrams/enabled} enable UDP

{services/udp-datagrams/udp-port}

{services/udp-transport/enabled} use UDP as a transport protocol
Your BitDust node must have at least one active and reliable transport protocol to be able
to connect to other nodes via Internet.

{services/udp-transport/receiving-enabled}

{services/udp-transport/sending-enabled}

{services/udp-transport/priority}

"""


def raw2():
    return """
{logs} logs
{logs/debug-level} debug level
{logs/memdebug-enabled} enable memory debugger
    Enabled this and go to http://127.0.0.1:[memdebug port number] to watch memory usage.
    Requires "cherrypy" and "dowser" python packages to be installed inside ~/.bitdust/venv/.

{logs/memprofile-enabled} enable memory profiler
    Use "guppy" package to profile memory usage.

{logs/stream-enabled} enable web logs
    Enabled this and go to http://127.0.0.1:[logs port number] to browse the program log.
    Need to restart the program.

{personal} personal information
    Your personal information.

{personal/name} name
    Set your name if you wish.

{personal/surname} surname
    Set your family name if you wish.

{personal/nickname} nickname
    Set your nickname to private messaging.
    If you leave this blank your identity address will be used to form a nickname.

{paths/backups} local backups location
    Place for your local backups files.

{paths/customers} donated space location
    Place for your donated space.
    All encrypted files, uploaded by other users, will kept here.

{paths/messages} messages location
    Folder to store your private messages.

{paths/receipts} receipts location
    Folder to store financial receipts.

{paths/restore} restored files location
    Location where your restored files should be placed by default.

{services} network services
    Network services settings.

{services/backup-db} backup database
    Backup database settings.

{services/backup-db/enabled} enable backups
    Enable service "backup-db".

{services/backups} backups settings

{services/backups/enabled} enable backups

{services/backups/block-size} preferred block size
    Preferred block size in bytes which used to split the raw data during backup.

{services/backups/max-block-size} maximum block size
    Maximum block size in bytes which used to split the raw data during backup.
    The actual block size is calculated depending on size of the particular backup to optimize performance and data storage.
    If you plan to do a huge backups - set higher values to increase the speed.
{services/backups/max-copies} number of copies
    This value indicates how many copies of each file or directory need to keep on remote machines.
    Once a fresh backup of given file or directory were finished - the oldest copy will be removed automatically.
    A "0" value means unlimited number of copies, be sure you have enough amount of donated space on remote machines.
{services/backups/keep-local-copies-enabled} keep local copies
    Enable this to keep a copy of every new backup on your local HDD as well as on remote machines of your suppliers.
    This increases data reliability, rebuilding performance and decrease network load,
    but consumes space on your HDD.
    Every one Mb of source data uploaded will consume two Mb on your local HDD.
{services/backups/wait-suppliers-enabled} wait suppliers 24 hours
    If you disabled storing of local data of your backups but one day a critical amount of your suppliers become unreliable - your data may be lost completely.
    Enable this option to wait for 24 hours after finishing any backup and perform a check all of your suppliers before removing the locally backed up data for this copy.

{services/supplier} supplier service
    "Supplier" service settings.
{services/supplier/donated} donated space
    How many megabytes you ready to donate to other users?

{services/identity-server} own identity server
    You can start own Identity server and store identity files of other users on your machine to support the BitDustwork.
{services/identity-server/enabled} enable identity server
    Enable this to start "identity-server" service.
{services/identity-server/host} identity server hostname
    Set a domain name of your machine if you have it.
    Otherwise your external IP will be used as a host name.
    The host name is used to form a unique IDURL of any hosted identity.
    User ID looking more pretty and safe without IP address.
{services/identity-server/tcp-port} TCP port number
    A TCP port number to receive user's identity files.
{services/identity-server/web-port} WEB port number
    If port 80 is already taken you can start identity server on a different port.

{services/customer} customer service
    "Customer" service settings.
{services/customer/needed-space} needed space
    How many megabytes you need to store your files?
{services/customer/suppliers-number} number of suppliers
    Number of remote suppliers which keeps your backups.
    You can select one of the following values: 2, 4, 7, 13, 18, 26, 64.
    Right now we have only few testing nodes in the network, so high values is not working yet.
    WARNING! You will lost all your existing backups after changing suppliers number.

{services/network} network service
    "Network" service settings.
{services/network/receive-limit} incoming bandwidth limit
    Limit incoming traffic with a value in bytes per second.
    A value of "0" means no incoming limit.
{services/network/send-limit} outgoing bandwidth limit
    The value in bytes per second to decrease network load.
    A value of "0" means no outgoing limit.

{services/entangled-dht} entangled-dht service
    "Entangled-DHT" service settings.
{services/entangled-dht/udp-port} udp port number for distributed hash table
    This is a UDP port number for Distributed Hash Table communications.
    BitDust uses <a href="http://entangled.sourceforge.net/">Entangled Project</a> to implement DHT functionality.

{services/tcp-connections/tcp-port} tcp port number
    Enter the TCP port number, it will be used to connect with your machine by other users.
{services/tcp-connections/upnp-enabled} UPnP enable
    Enable this if you want to perform checking of UPnP devices to configure port forwarding automatically.

{services/tcp-transport} tcp-transport service
    You can use different protocols to transfer packets across the network, they are called "transports".
    Here you can customize your "TCP-transport" service, it is based on standard TCP protocol.
{services/tcp-transport/enabled} enable tcp-transport service
    Enable "TCP-transport" service.
{services/tcp-transport/receiving-enabled} enable tcp receiving
    Disable this if you do not want to use TCP-transport for receiving packets from other users.
{services/tcp-transport/sending-enabled} enable tcp sending
    Disable this if you do not want to use TCP-transport for sending packets to other users.

{services/udp-datagrams/udp-port} udp port number
    Set a UDP port for sending and receiving UDP datagrams.

{services/udp-transport} udp-transport service
    You can use different protocols to transfer packets across the network, they are called "transports".
    Here you can customize your "UDP-transport" service.
    It sends and receives UDP datagrams to transfer data from one peer to another in the network.
    UDP-transport performs own bandwidth management and load balancing.
{services/udp-transport/enabled} enable udp-transport service
    Enable "UDP-transport" service.
{services/udp-transport/receiving-enabled} enable udp receiving
    Disable this if you do not want to use UDP-transport for receiving packets from other users.
{services/udp-transport/sending-enabled} enable udp sending
    Disable this if you do not want to use UDP-transport for sending packets to other users.
"""
