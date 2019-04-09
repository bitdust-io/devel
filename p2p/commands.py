#!/usr/bin/python
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (commands.py) is part of BitDust Software.
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
.. module:: commands.

This module describes all commands in the BitDust p2p communication protocol.
The command is stored as a string in the packet.Command field.
If all commands are repeatable, then sequence numbers are not so critical,
though we would want date so time for replay trouble was limited.
If backups are write, read, delete (and never write again), then replay
is not an issue here and we use PacketID that identifies data.
So we want things like "replace supplier Vincecate"  not "replace supplier 5"
where seeing command an extra time would not hurt.

These are the valid values for the command field of a packet:
    - Data/Ack/                 (if customer sends you data you store it) (could be parity packet too)
    - Retrieve/Data|Fail        (data packets returned exactly as is with our signature)
    - ListFiles/Files           (ask supplier to list backup IDs he knows about for us)
    - Identity/Ack              (ping/pong packets)
    - Message/Ack               (chat)
    - Coin/Ack                  (for contracts publishing/management)
"""

#------------------------------------------------------------------------------

P2PCommandAcks = {}

#------------------------------------------------------------------------------


def init():
    """
    Initialize a list of valid p2p commands.
    """
    global P2PCommandAcks
    # No Ack for Ack
    P2PCommandAcks[Ack()] = []
    # No Ack for Fail
    P2PCommandAcks[Fail()] = []
    # Ack Data with Ack or Fail unless it is our data coming back (would be only after Retrieve)
    P2PCommandAcks[Data()] = [Ack(), Fail(), ]
    # Ack Retrieve with Data or Fail
    P2PCommandAcks[Retrieve()] = [Data(), Fail(), ]
    # Ack ListFiles with Files
    P2PCommandAcks[ListFiles()] = [Files(), Fail(), ]
    # Ack Files with Ack or Fail
    P2PCommandAcks[Files()] = [Ack(), Fail(), ]
    # If identity comes in and no interested party then transport sends an Ack
    P2PCommandAcks[Identity()] = [Ack(), ]
    # Ack with Ack (maybe should be Files)
    P2PCommandAcks[DeleteFile()] = [Ack(), Fail(), ]
    # Ack with Ack (maybe should be Files)
    P2PCommandAcks[DeleteBackup()] = [Ack(), Fail(), ]
    # Ack with Ack or Fail
    P2PCommandAcks[Message()] = [Ack(), Fail(), ]
    # Ack with Ack or Fail
    P2PCommandAcks[Receipt()] = [Ack(), Fail(), ]
    P2PCommandAcks[Correspondent()] = [Correspondent(), Fail(), ]
    # RequestService must receive back Ack or Fail
    P2PCommandAcks[RequestService()] = [Ack(), Fail(), ]
    # CancelService must receive back Ack or Fail
    P2PCommandAcks[CancelService()] = [Ack(), Fail(), ]
    P2PCommandAcks[Broadcast()] = []
    P2PCommandAcks[Relay()] = []
    P2PCommandAcks[Coin()] = []
    P2PCommandAcks[RetrieveCoin()] = [Coin(), Fail(), ]
    P2PCommandAcks[Key()] = [Ack(), Fail(), ]
    P2PCommandAcks[AuditKey()] = [Ack(), Fail(), ]
    P2PCommandAcks[Event()] = [Ack(), Fail(), ]
    P2PCommandAcks[Contacts()] = [Contacts(), Ack(), Fail(), ]


def IsCommand(com):
    """
    Check to see if ``com`` is a valid command.
    """
    global P2PCommandAcks
    if len(P2PCommandAcks) == 0:
        init()
    return com in P2PCommandAcks


def IsCommandAck(com, ack):
    """
    """
    global P2PCommandAcks
    if len(P2PCommandAcks) == 0:
        init()
    return ack in P2PCommandAcks.get(com, [])


def IsAckExpected(com):
    """
    """
    expected = P2PCommandAcks.get(com, [])
    return Ack() in expected

#------------------------------------------------------------------------------


def Data():
    """
    Data packet, may be Data, Parity, Backup database, may be more.
    """
    return "Data"


def Ack():
    """
    Response packet for some request.
    """
    return "Ack"


def RequestService():
    """
    """
    return "RequestService"


def CancelService():
    """
    """
    return "CancelService"


def Retrieve():
    """
    Used to request some data from supplier for example.
    """
    # TODO: rename to RetrieveData
    return "Retrieve"


def Fail():
    """
    Used to report an error in response, for example when requested file is not
    found on remote machine.
    """
    return "Fail"


def Relay():
    """
    Used by proxy transport to route packets in/out via third node.
    """
    return "Relay"


def ListFiles():
    """
    Response from remote peer with a list of my files stored on his machine.
    """
    return "ListFiles"


def Files():
    """
    Request a list of my files from remote peer.
    """
    return "Files"


def Contacts():
    """
    Packet with a list of my contacts, may be suppliers, customers or
    correspondents or list of suppliers of another customer.
    Can also be an empty packet with a request to provide some other contacts
    from remote peer.
    """
    return "Contacts"


def Identity():
    """
    Packet containing peer identity file.
    """
    return "Identity"


def DeleteFile():
    """
    Request to delete a single file or list of my files from remote machine.
    """
    return "DeleteFile"


def DeleteBackup():
    """
    Request to delete whole backup or list of backups from remote machine.
    """
    return "DeleteBackup"


def Transfer():
    """
    Transfer funds to remote peer.
    """
    return "Transfer"


def Receipt():
    """
    Some billing report.
    """
    return "Receipt"


def Message():
    """
    A message from one peer to another.
    """
    return "Message"


def Correspondent():
    """
    Remote user should send you this to be included in your correspondents
    (friends) list.
    """
    return "Correspondent"


def Broadcast():
    """
    This message type is for delivering some piece of data to all peers in th network.
    It is used to broadcast "crypto-coins" between peers.
    """
    return "Broadcast"


def Coin():
    """
    """
    return "Coin"


def RetrieveCoin():
    """
    """
    return "RetrieveCoin"


def Key():
    """
    """
    return "Key"


def AuditKey():
    """
    """
    return "AuditKey"


def Event():
    """
    """
    return "Event"
