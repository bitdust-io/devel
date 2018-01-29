#!/usr/bin/python
# p2p_queue.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (p2p_queue.py) is part of BitDust Software.
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
.. module:: p2p_queue.


Methods to establish a messages queue between two or more nodes.:

    + Producers will send a messages to the queue
    + Consumers will listen to the queue and read the messages comming
    + Producer only start sending if he have a Public Key
    + Consumer can only listen if he posses the correct Private Key
    + Queue is only stored on given node: both producer and conumer must be connected to that machine
    + Global queue ID is unique : mykey$alice@somehost.net:.queue/xyz
    + Queue size is limited by a parameter, you can not publish when queue is overloaded

"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys
import json
import time

from collections import OrderedDict

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in p2p_queue.py')

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from lib import packetid
from lib import utime

from userid import my_id
from userid import identity
from userid import global_id

#------------------------------------------------------------------------------

MAX_QUEUE_LENGTH = 100

#------------------------------------------------------------------------------

_ActiveQueues = {}
_LastMessageID = 0
_Producers = {}
_Consumers = {}
_PendingNotifications = []

#------------------------------------------------------------------------------

def init():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.init')


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.shutdown')

#------------------------------------------------------------------------------


def make_message_id():
    """
    Generate a unique message ID to be stored in the queue.
    """
    global _LastMessageID
    if _LastMessageID is None:
        _LastMessageID = int(str(int(time.time() * 100.0))[4:])
    _LastMessageID += 1
    return _LastMessageID

#------------------------------------------------------------------------------

def queue(queue_id=None):
    global _ActiveQueues
    if queue_id is None:
        return _ActiveQueues
    if queue_id not in _ActiveQueues:
        _ActiveQueues[queue_id] = OrderedDict()
    return _ActiveQueues[queue_id]


def consumers():
    global _Consumers
    return _Consumers


def producers():
    global _Producers
    return _Producers


def notifications():
    global _PendingNotifications
    return _PendingNotifications

#------------------------------------------------------------------------------

def valid_queue_id(queue_id):
    qid = global_id.ParseGlobalID(queue_id)
    if not qid['user']:
        return False
    if not qid['key_alias']:
        return False
    if not qid['path'] or not qid['path'].startswith('.queue'):
        return False
    return True

#------------------------------------------------------------------------------

def add_consumer(consumer_global_id, queue_id, callback_method):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    if consumer_global_id not in consumers():
        lg.info('new consumer added: %s' % consumer_global_id)
        consumers()[consumer_global_id] = {}
    if queue_id not in consumers()[consumer_global_id]:
        lg.info('added new queue %s for consumer %s' % (queue_id, consumer_global_id, ))
        consumers()[consumer_global_id][queue_id] = []
    if callback_method in consumers()[consumer_global_id][queue_id]:
        lg.warn('callback method already in the queue')
        return False
    consumers()[consumer_global_id][queue_id].append(callback_method)
    lg.info('callback method %s added for %s on %s' % (callback_method, consumer_global_id, queue_id, ))
    return True


def remove_consumer(consumer_global_id, queue_id, callback_method):
    if consumer_global_id not in consumers():
        lg.warn('consumer not found')
        return False
    if queue_id not in consumers()[consumer_global_id]:
        lg.info('queue not found for consumer')
        return False
    if callback_method not in consumers()[consumer_global_id][queue_id]:
        lg.warn('callback method not found for given queue')
        return False
    consumers()[consumer_global_id][queue_id].remove(callback_method)
    lg.info('callback method %s removed for %s on %s' % (callback_method, consumer_global_id, queue_id, ))
    return True

#------------------------------------------------------------------------------

def push_to_queue(queue_id, json_data):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    message_id = make_message_id()
    message_json = dict(
        message_id=message_id,
        time=utime.get_sec1970(),
        payload=json_data,
    )
    queue(queue_id)[message_id] = message_json
    lg.info('message %s added to queue %s' % (message_id, queue_id, ))
    reactor.callLater(0, notify_consumers, queue_id, message_id, message_json)
    return True


def pop_from_queue(queue_id, message_id):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    if queue_id not in queue().keys():
        lg.warn('queue id not found')
        return False
    if message_id not in queue(queue_id):
        lg.warn('message id not found in the queue')
        return False
    queue(queue_id).pop(message_id)
    lg.info('message %s removed from queue %s' % (message_id, queue_id, ))
    return True

#------------------------------------------------------------------------------

def notify_consumers(queue_id, message_id, message_json):
    message_json = queue(queue_id).get(message_id, None)
    if message_json is None:
        lg.warn('message %s was not found in the queue %s' % (message_id, queue_id))
        return False
    for consumer_global_id, consumer_queues in consumers().items():
        if queue_id not in consumer_queues:
            # skip other queues for that consumer
            continue
        notifications = []
        for callback_method in consumer_queues[queue_id]:
            if isinstance(callback_method, str):
                result = do_send_remote_notification(consumer_global_id, queue_id, message_id, message_json)
            else:
                result = do_run_callback_method(callback_method, consumer_global_id, queue_id, message_id, message_json)
            notifications.append(result)
        notifications().append(dict(
            consumer_global_id=consumer_global_id,
            queue_id=queue_id,
            message_id=message_id,
            result=result,
        ))

def do_send_remote_notification():
    pass

def do_run_callback_method():
    from p2p import p2p_service
    p2p_service.SendEvent(remote_idurl, message_json, packet_id, wide, callbacks)

