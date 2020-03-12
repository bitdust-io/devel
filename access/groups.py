#!/usr/bin/python
# groups.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (groups.py) is part of BitDust Software.
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

"""
.. module:: groups


BitDust Groups are intended to organize isolated private data flows between multiple users.

Owner of the group (customer) first creates a new "group key" that will be used to
protect data flows between participants of the group.

To add a new member to the group he just need to share the private part of that key
with the trusted person - that is implemented in `group_access_donor()` state machine.
Remote user once received the key will recognize that the key is actually a "group key"
(alias of the key must begins with `group_`) and will start a new instance
of `group_access_coordinator()` state machine which suppose to connect him to
other participants of the group.

In order to run data flows between multiple users a new role was introduced which is
called `message_broker`. All group communications are done via message broker - he holds
the queue and participants are connected to the queue as "consumers" and "producers".

If owner / participant is not on-line at the moment the broker will keep the message for
some time. Basically broker removes a message from the queue only after all consumers
received it with acknowledgment. If single consumer not reading any messages from the queue
for a quite some time broker will release him automatically to prevent queue to be overloaded.

The owner of the group or one of the participants will have to first make sure that
at least one message broker "was hired" for the group. Basically first "consumer"
or "producer" who is interested in the particular queue will have to check and hire
a new message broker for given customer.

Customer can create multiple groups&queues but will have only one primary message broker
and possibly secondary and third brokers in stand by mode. This way there is no concurrency
exist in that flow and all group messages just passing by via single host from producers to
consumers: `producer -> message broker -> consumer`.

To hire a message broker owner, consumer or producer needs to find a new host in the network
via DHT and share public part of the group key with him. So message broker is not able to
read messages content but only validate the signatures and verify that participants are authorized.

Message broker publishes his info on DHT and so all of the group members
are able to find and connect to it. Secondary and third message broker also will be
hired but will be in "stand by" mode and not receive the messages from producers.

In case primary broker went offline but one of the producers wanted to publish a new message
to the queue - he will fail and switch to the secondary message broker quickly.
So producer will just re-try the message but to the secondary message broker.
Because other consumers are already connected to the secondary broker they will not recognize
any difference and will receive the message right away. This way mechanism of automatic failover
of message broker from primary to secondary suppose to prevent message lost.

In short group is:
    1. group key created by "group owner" and shared to participants
    2. message queue served by message broker
    3. DHT record holding ID of primary, secondary and third message brokers

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys
import base64

from twisted.internet.defer import Deferred, fail

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from lib import strng
from lib import serialization

from main import settings


from userid import my_id
from userid import global_id

from crypt import my_keys

#------------------------------------------------------------------------------

def init():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'groups.init')


def shutdown():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'groups.shutdown')

#------------------------------------------------------------------------------

def prepare_customer_group(group_alias, customer_id=None, label=None, queue_position=0, key_size=4096):
    if customer_id is None:
        customer_id = my_id.getGlobalID()
    group_key_id = global_id.MakeCustomerQueueID(queue_alias=group_alias, customer_id=customer_id, position=queue_position)
    if not my_keys.is_key_private(group_key_id):
        my_keys.generate_key(group_key_id, label=label or group_alias, key_size=key_size)
    return group_key_id

