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

if __name__ == "__main__":
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from lib import utime
from lib import misc

from p2p import commands
from p2p import p2p_service


#------------------------------------------------------------------------------

MAX_QUEUE_LENGTH = 20

#------------------------------------------------------------------------------

_ActiveQueues = {}
_PendingNotifications = {}

_LastMessageID = None

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


def consumer(consumer_global_id=None):
    global _Consumers
    if consumer_global_id is None:
        return _Consumers
    if consumer_global_id not in _Consumers:
        _Consumers[consumer_global_id] = dict(
            commands=[],
            messages={},
            queues=[],
        )
    return _Consumers[consumer_global_id]


def producers():
    global _Producers
    return _Producers


#------------------------------------------------------------------------------

def valid_queue_id(queue_id):
    try:
        str(queue_id)
    except:
        return False
    if not misc.ValidUserName(queue_id):
        return False
#     qid = global_id.ParseGlobalID(queue_id)
#     if not qid['user']:
#         return False
#     if not qid['key_alias']:
#         return False
#     if not qid['path'] or not qid['path'].startswith('.queue'):
#         return False
    return True

#------------------------------------------------------------------------------

def add_consumer(consumer_global_id):
    if consumer_global_id in consumer():
        lg.warn('consumer already exist')
        return False
    new_consumer = consumer(consumer_global_id)
    lg.info('new consumer added: %s with %s' % (consumer_global_id, str(new_consumer), ))
    return True


def remove_consumer(consumer_global_id):
    if consumer_global_id not in consumer():
        lg.warn('consumer not exist')
        return False
    consumer().pop(consumer_global_id)
    lg.info('existing consumer removed: %s' % str(consumer_global_id))
    return True

#------------------------------------------------------------------------------

def add_callback_method(consumer_global_id, callback_method):
    if consumer_global_id not in consumer():
        lg.warn('consumer not found')
        return False
    if callback_method in consumer(consumer_global_id)['commands']:
        lg.warn('callback method already exist')
        return False
    consumer(consumer_global_id)['commands'].append(callback_method)
    lg.info('callback_method %s added for consumer %s' % (callback_method, consumer_global_id))
    return True


def remove_callback_method(consumer_global_id, callback_method):
    if consumer_global_id not in consumer():
        lg.warn('consumer not found')
        return False
    if callback_method not in consumer(consumer_global_id)['commands']:
        lg.warn('callback method not found')
        return False
    consumer(consumer_global_id)['commands'].remove(callback_method)
    lg.info('callback_method %s removed from consumer %s' % (callback_method, consumer_global_id))
    return True

#------------------------------------------------------------------------------

def open_queue(queue_id):
    if queue_id in queue():
        return False
    queue(queue_id)
    return True


def close_queue(queue_id):
    if queue_id not in queue():
        return False
    queue().pop(queue_id)
    for consumer_global_id in consumer().keys():
        unsubscribe_consumer(consumer_global_id, queue_id)
    close_queue_pending_messages(queue_id, 'queue closed')
    return True

#------------------------------------------------------------------------------

def subscribe_consumer(consumer_global_id, queue_id):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    if consumer_global_id not in consumer():
        lg.warn('consumer not found')
        return False
    if queue_id in consumer(consumer_global_id)['queues']:
        lg.warn('already subscribed')
        return False
    consumer(consumer_global_id)['queues'].append(queue_id)
    lg.info('conumer %s subscribed to read queue %s' % (consumer_global_id, queue_id, ))
    return True


def unsubscribe_consumer(consumer_global_id, queue_id=None):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    if consumer_global_id not in consumer():
        lg.warn('consumer not found')
        return False
    if queue_id is None:
        consumer(consumer_global_id)['queues'] = []
        lg.info('conumer %s unsubscribed from all queues' % (consumer_global_id, ))
        return True
    if queue_id not in consumer(consumer_global_id)['queues']:
        lg.warn('currently given consumer not subscribed for that queue')
        return False
    consumer(consumer_global_id)['queues'].remove(queue_id)
    lg.info('conumer %s unsubscribed from queue %s' % (consumer_global_id, queue_id, ))
    return True

#------------------------------------------------------------------------------

def push_message(queue_id, json_data):
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
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.push_message  %s added to queue %s' % (message_id, queue_id, ))
    reactor.callLater(0, do_consume)
    # reactor.callLater(0, notify_consumers, queue_id, message_id)
    return True


def pop_message(queue_id, message_id):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return None
    if queue_id not in queue().keys():
        lg.warn('queue id not found')
        return None
    if message_id not in queue(queue_id):
        lg.warn('message id not found in the queue')
        return None
    message_json = queue(queue_id).pop(message_id)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.pop_message  %s removed from queue %s and will be send to consumers' % (message_id, queue_id, ))
    return message_json

#------------------------------------------------------------------------------

def on_notification_succeed(result, consumer_global_id, queue_id, message_id):
    # lg.info(result)
    close_pending_message(consumer_global_id, queue_id, message_id, why='acked')
    return result


def on_notification_failed(err, consumer_global_id, queue_id, message_id):
    lg.err(err)
    close_pending_message(consumer_global_id, queue_id, message_id, why='failed')
    return err

#------------------------------------------------------------------------------

def close_pending_message(consumer_global_id, queue_id, message_id, why=None):
    if consumer_global_id not in consumer():
        lg.warn('consumer not found')
        return False
    if queue_id not in consumer(consumer_global_id)['queues']:
        lg.warn('consumer is not reading that queue anymore')
    if message_id not in consumer(consumer_global_id)['messages']:
        lg.warn('message id not found in consumer queue')
        return False
    consumer(consumer_global_id)['messages'].pop(message_id)
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.close_pending_message queue_id=%s, message_id=%s, consumer_id=%s, because "%s", more: %d items' % (
            queue_id, message_id, consumer_global_id, why, len(consumer(consumer_global_id)['messages'])))
    return True


def close_queue_pending_messages(queue_id, why=None):
    for consumer_global_id in consumer().keys():
        to_be_removed = []
        for message_info in consumer(consumer_global_id)['messages'].values():
            if message_info['queue_id'] == queue_id:
                to_be_removed.append(message_info['message_id'])
        for message_id in to_be_removed:
            close_pending_message(consumer_global_id, queue_id, message_id, why=why)
    return True


def close_all_pending_messages(consumer_global_id):
    if consumer_global_id not in consumer():
        lg.warn('consumer not found')
        return False
    consumer(consumer_global_id)['messages'].clear()
    return True

#------------------------------------------------------------------------------

def do_notify(callback_method, consumer_global_id, queue_id, message_id, message_json):
    ret = Deferred()
    ret.addCallback(on_notification_succeed, consumer_global_id, queue_id, message_id)
    ret.addErrback(on_notification_failed, consumer_global_id, queue_id, message_id)
    if isinstance(callback_method, str):
        p2p_service.SendEvent(callback_method, message_json, packet_id=message_id, callbacks={
            commands.Ack(): lambda response, info: ret.callback(True),
            commands.Fail(): lambda response, info: ret.callback(False),
        })
    else:
        try:
            result = callback_method(queue_id, message_id, message_json)
        except:
            lg.exc()
            result = False
        reactor.callLater(0, ret.callback, result)
        # ret.callback(result)
    return ret


def do_consume(interested_consumers=None):
    if not interested_consumers:
        interested_consumers = consumer().keys()
    to_be_consumed = []
    pending_messages = 0
    for consumer_global_id in interested_consumers:
        if len(consumer(consumer_global_id)['commands']) == 0:
            # skip, no avaliable notification methods found for given consumer
            continue
        if len(consumer(consumer_global_id)['messages']) > MAX_QUEUE_LENGTH:
            # skip, consumer is overloaded, too much was sent to him, but no response
            reactor.callLater(0, unsubscribe_consumer, consumer_global_id)
            reactor.callLater(0, close_all_pending_messages, consumer_global_id)
            continue
        if len(consumer(consumer_global_id)['messages']) > 3:
            # skip, consumer already notified and need to respond first
            pending_messages += 1
            continue
        interested_queues = set()
        for queue_id in consumer(consumer_global_id)['queues']:
            if queue_id not in queue():
                lg.warn('consumer queue not found')
                continue
            if len(queue(queue_id)) == 0:
                continue
            interested_queues.add(queue_id)
        if len(interested_queues) == 0:
            # skip, no new messages in the queues which consumer subscribed on
            continue
        for queue_id in interested_queues:
            oldest_message_id = queue(queue_id).keys()[0]
            to_be_consumed.append((consumer_global_id, queue_id, oldest_message_id, ))
    if pending_messages > 0:
        reactor.callLater(2, do_consume)
    if not to_be_consumed:
        # nothing to consume
        return False
    notifications_count = 0
    for _consumer_global_id, _queue_id, _message_id in to_be_consumed:
        _message_json = pop_message(_queue_id, _message_id)
        if _message_json is None:
            lg.warn('message %s not found in the queue %s' % (_message_id, _queue_id))
            return False
        for callback_method in consumer(_consumer_global_id)['commands']:
            ret = do_notify(
                callback_method,
                _consumer_global_id,
                _queue_id,
                _message_id,
                _message_json,
            )
            consumer(_consumer_global_id)['messages'][_message_id] = dict(
                queue_id=_queue_id,
                message_id=_message_id,
                callback_method=callback_method,
                time=utime.get_sec1970(),
                result=ret,
            )
            notifications_count += 1
            break
    if notifications_count == 0:
        return False
    return True


#------------------------------------------------------------------------------

def _test_callback(queue_id, message_id, message_json):
    print '_test_callback', queue_id, message_id, message_json
    return True


def test():
    lg.set_debug_level(24)
    add_consumer('alice@histone.com')
    add_callback_method('alice@histone.com', _test_callback)
    open_queue('test123')
    subscribe_consumer('alice@histone.com', 'test123')
    push_message('test123', json_data=dict(abc=123))
    push_message('test123', json_data=dict(abc=456))
    push_message('test123', json_data=dict(abc=789))
    push_message('test123', json_data=dict(abc='abc'))
    reactor.run()


if __name__ == '__main__':
    test()
