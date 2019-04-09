#!/usr/bin/python
# config_details.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
    return """
{logs} logs
    Program logs settings.
{logs/debug-level} debug level
    Higher values will produce more log messages.
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
{personal/betatester} betatester
    Are you agree to participate in the BitDust project testing?
    We are going to provide some bonuses to people who help us at this stage, to be decided later.
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
    Backups setting.
{services/backups/enabled} enable backups
    Enable service "Backups".
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
    You can ser one of the following values: 2, 4, 7, 13, 18, 26, 64.
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
