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
_PendingNotifications = {}

_LastMessageID = 0

_Producers = {}
_Consumers = {}

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


def notifications(queue_id=None):
    global _PendingNotifications
    if queue_id is None:
        return _PendingNotifications
    if queue_id not in _PendingNotifications:
        _PendingNotifications[queue_id] = OrderedDict()
    return _PendingNotifications[queue_id]


def consumers():
    global _Consumers
    return _Consumers


def producers():
    global _Producers
    return _Producers


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
    if len(queue(queue_id)) >= MAX_QUEUE_LENGTH:
        lg.warn('queue is overloaded')
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

def do_send_remote_notification(remote_idurl, consumer_global_id, queue_id, message_id, message_json):
    from p2p import commands
    from p2p import p2p_service
#     remote_idurl = global_id.GlobalUserToIDURL(consumer_global_id)
#     if not remote_idurl:
#         lg.warn('invalid consumer global id')
#         return False
    result = Deferred()
    p2p_service.SendEvent(remote_idurl, message_json, packet_id=message_id, callbacks={
        commands.Ack(): lambda response, info: result.callback(response),
        commands.Fail(): lambda response, info: result.errback(response),
    })
    return result


def do_run_callback_method(callback_method, consumer_global_id, queue_id, message_id, message_json):
    try:
        result = callback_method(queue_id, message_id, message_json)
    except:
        lg.exc()
        result = False
    return result

#------------------------------------------------------------------------------

def notify_consumers(queue_id, message_id, message_json):
    message_json = queue(queue_id).get(message_id, None)
    if message_json is None:
        lg.warn('message %s was not found in the queue %s' % (message_id, queue_id))
        return False
    _interested_consumers = {}
    for consumer_global_id, consumer_queues in consumers().items():
        if queue_id not in consumer_queues:
            # skip other queues for that consumer
            continue
        if message_id in notifications(queue_id):
            lg.warn('message %s notification in queue %s already executed' % (message_id, queue_id, ))
            continue
        for callback_method in consumer_queues[queue_id]:
            if isinstance(callback_method, str):
                result = do_send_remote_notification(
                    callback_method, consumer_global_id, queue_id, message_id, message_json)
            else:
                result = do_run_callback_method(
                    callback_method, consumer_global_id, queue_id, message_id, message_json)
            if consumer_global_id in _interested_consumers:
                lg.warn('that consumer already marked to be notified')
            _interested_consumers[consumer_global_id] = (callback_method, result, )
    if len(_interested_consumers):
        notifications(queue_id)[message_id] = dict(
            queue_id=queue_id,
            message_id=message_id,
            message_json=message_json,
            consumers=_interested_consumers,
        )
        reactor.callLater(0, check_pending_notifications)
    else:
        lg.warn('no new interested consumers found')

#------------------------------------------------------------------------------

def close_notification_consumer(notification_info, consumer_global_id, why=None):
    try:
        queue_id = notification_info['queue_id']
        message_id = notification_info['message_id']
    except:
        lg.exc()
        return False
    if queue_id not in notifications():
        lg.warn('queue id not found in pending notifications')
        return False
    if message_id not in notifications(queue_id):
        lg.warn('message id not found in pending notifications for that queue')
        return False
    if consumer_global_id not in notifications(queue_id)[message_id]['consumers']:
        lg.warn('consumer id not found in pending notifications for given queue and message')
        return False
    notifications(queue_id)[message_id]['consumers'].pop(consumer_global_id)
    if len(notifications(queue_id)[message_id]['consumers']) == 0:
        close_notification(queue_id, message_id)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.close_notification_consumer queue_id=%s, message_id=%s, consumer_id=%s' % (
            queue_id, message_id, consumer_global_id, ))
    return True


def close_notification(queue_id, message_id):
    if queue_id not in notifications():
        lg.warn('queue id not found in pending notifications')
        return False
    if message_id not in notifications(queue_id):
        lg.warn('message id not found in pending notifications for that queue')
        return False
    notifications(queue_id).pop(message_id)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.close_notification queue_id=%s, message_id=%s' % (
            queue_id, message_id, ))
    return True


def check_pending_notifications():
    has_changed = False
    for notification_info in notifications().values():
        for interested_consumer_id, notification_result in notification_info['consumers'].items():
            callback_method, result = notification_result
            if result is True or result is False:
                close_notification_consumer(
                    notification_info, interested_consumer_id)
                has_changed = True
            elif isinstance(result, Deferred):
                result.addCallback(lambda ok: close_notification_consumer(
                    notification_info, interested_consumer_id))
                result.addErrback(lambda err: close_notification_consumer(
                    notification_info, interested_consumer_id))
                has_changed = True
            else:
                lg.err('wrong notification result type')
