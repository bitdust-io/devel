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

MAX_QUEUE_LENGTH = 100
MAX_CONSUMER_PENDING_MESSAGES = int( MAX_QUEUE_LENGTH / 2 )

#------------------------------------------------------------------------------

_ActiveQueues = {}

_LastMessageID = None

_Producers = {}
_Consumers = {}

#------------------------------------------------------------------------------

def init():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.init')
    start()


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.shutdown')
    stop()

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


def consumer(consumer_id=None):
    global _Consumers
    if consumer_id is None:
        return _Consumers
    if consumer_id not in _Consumers:
        _Consumers[consumer_id] = dict(
            commands=[],
            queues=[],
            messages=0,
        )
    return _Consumers[consumer_id]


def producer(producer_id=None):
    global _Producers
    if producer_id is None:
        return _Producers
    if producer_id not in _Producers:
        _Producers[producer_id] = dict(
            queues=[],
        )
    return _Producers


#------------------------------------------------------------------------------

MIN_PROCESS_QUEUES_DELAY = 0.1
MAX_PROCESS_QUEUES_DELAY = 1

_ProcessQueuesDelay = 0.01
_ProcessQueuesTask = None


def start():
    reactor.callLater(0, process_queues)
    return True


def stop():
    global _ProcessQueuesTask
    if _ProcessQueuesTask:
        if _ProcessQueuesTask.active():
            _ProcessQueuesTask.cancel()
        _ProcessQueuesTask = None
        return True
    return False


def process_queues():
    global _ProcessQueuesDelay
    global _ProcessQueuesTask
    has_activity = do_consume()
    _ProcessQueuesDelay = misc.LoopAttenuation(
        _ProcessQueuesDelay, has_activity,
        MIN_PROCESS_QUEUES_DELAY,
        MAX_PROCESS_QUEUES_DELAY,
    )
    # attenuation
    _ProcessQueuesTask = reactor.callLater(_ProcessQueuesDelay, process_queues)

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

def add_consumer(consumer_id):
    if consumer_id in consumer():
        lg.warn('consumer already exist')
        return False
    new_consumer = consumer(consumer_id)
    lg.info('new consumer added: %s with %s' % (consumer_id, str(new_consumer), ))
    return True


def remove_consumer(consumer_id):
    if consumer_id not in consumer():
        lg.warn('consumer not exist')
        return False
    consumer().pop(consumer_id)
    lg.info('existing consumer removed: %s' % str(consumer_id))
    return True

#------------------------------------------------------------------------------

def add_producer(producer_id):
    if producer_id in producer():
        lg.warn('producer already exist')
        return False
    new_producer = producer(producer_id)
    lg.info('new producer added: %s with %s' % (producer_id, str(new_producer), ))
    return True


def remove_producer(producer_id):
    if producer_id not in producer():
        lg.warn('producer not exist')
        return False
    producer().pop(producer_id)
    lg.info('existing producer removed: %s' % str(producer_id))
    return True

#------------------------------------------------------------------------------

def add_callback_method(consumer_id, callback_method):
    if consumer_id not in consumer():
        lg.warn('consumer not found')
        return False
    if callback_method in consumer(consumer_id)['commands']:
        lg.warn('callback method already exist')
        return False
    consumer(consumer_id)['commands'].append(callback_method)
    lg.info('callback_method %s added for consumer %s' % (callback_method, consumer_id))
    return True


def remove_callback_method(consumer_id, callback_method):
    if consumer_id not in consumer():
        lg.warn('consumer not found')
        return False
    if callback_method not in consumer(consumer_id)['commands']:
        lg.warn('callback method not found')
        return False
    consumer(consumer_id)['commands'].remove(callback_method)
    lg.info('callback_method %s removed from consumer %s' % (callback_method, consumer_id))
    return True

#------------------------------------------------------------------------------

def open_queue(queue_id):
    if queue_id in queue():
        lg.warn('queue already exist')
        return False
    queue(queue_id)
    return True


def close_queue(queue_id):
    if queue_id not in queue():
        lg.warn('queue not exist')
        return False
    queue().pop(queue_id)
    for consumer_id in consumer().keys():
        unsubscribe_consumer(consumer_id, queue_id)
    # delete_queue_messages(queue_id, 'queue closed')
    return True

#------------------------------------------------------------------------------

def subscribe_consumer(consumer_id, queue_id):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    if consumer_id not in consumer():
        lg.warn('consumer not found')
        return False
    if queue_id in consumer(consumer_id)['queues']:
        lg.warn('already subscribed')
        return False
    consumer(consumer_id)['queues'].append(queue_id)
    lg.info('conumer %s subscribed to read queue %s' % (consumer_id, queue_id, ))
    return True


def unsubscribe_consumer(consumer_id, queue_id=None):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    if consumer_id not in consumer():
        lg.warn('consumer not found')
        return False
    if queue_id is None:
        consumer(consumer_id)['queues'] = []
        lg.info('conumer %s unsubscribed from all queues' % (consumer_id, ))
        return True
    if queue_id not in consumer(consumer_id)['queues']:
        lg.warn('currently given consumer not subscribed for that queue')
        return False
    consumer(consumer_id)['queues'].remove(queue_id)
    lg.info('conumer %s unsubscribed from queue %s' % (consumer_id, queue_id, ))
    return True

#------------------------------------------------------------------------------

def start_notification(consumer_id, queue_id, message_id, defer_result):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    if consumer_id not in consumer():
        lg.warn('consumer not found')
        return False
    if queue_id not in queue():
        lg.warn('queue not exist')
        return False
    if message_id not in queue(queue_id):
        lg.warn('message not exist')
        return False
    if consumer_id in queue(queue_id)[message_id].notifications:
        lg.warn('notification already sent to given consumer')
        return False
    defer_result.addCallback(on_notification_succeed, consumer_id, queue_id, message_id)
    defer_result.addErrback(on_notification_failed, consumer_id, queue_id, message_id)
    queue(queue_id)[message_id].state = 'SENT'
    queue(queue_id)[message_id].notifications[consumer_id] = defer_result
    return True


def finish_notification(consumer_id, queue_id, message_id, success):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    if queue_id not in queue():
        lg.warn('queue not exist')
        return False
    if message_id not in queue(queue_id):
        lg.warn('message not exist')
        return False
    if consumer_id not in queue(queue_id)[message_id].notifications:
        lg.warn('not found pending notification for given consumer')
        return False
    defer_result = queue(queue_id)[message_id].notifications.pop(consumer_id)
    if success:
        queue(queue_id)[message_id].success_notifications += 1
    else:
        queue(queue_id)[message_id].failed_notifications += 1
    if not isinstance(defer_result, Deferred):
        lg.warn('invalid notification type')
        return False
    if not defer_result.called:
        lg.warn('cancelling not-finished notification')
        defer_result.cancel()
    del defer_result
    return True

#------------------------------------------------------------------------------

def push_message(producer_id, queue_id, json_data):
    if producer_id not in producer():
        lg.warn('unknown producer')
        return False
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return False
    if len(queue(queue_id)) >= MAX_QUEUE_LENGTH:
        lg.warn('queue is overloaded')
        return False
    new_message = QueueMessage(producer_id, queue_id, json_data)
    queue(queue_id)[new_message.message_id] = new_message
    queue(queue_id)[new_message.message_id].state = 'PUSHED'
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.push_message  %s added to queue %s' % (new_message.message_id, queue_id, ))
    # reactor.callLater(0, do_consume)
    return True


def lookup_pending_message(consumer_id, queue_id):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return None
    if queue_id not in queue():
        lg.warn('queue not exist')
        return False
    if consumer_id not in consumer():
        lg.warn('consumer not found')
        return None
    queue_pos = 0
    while queue_pos < len(queue(queue_id)):
        # loop all messages from the begining
        if consumer_id not in queue(queue_id).values()[queue_pos].consumers:
            # only interested consumers needs to be selected
            queue_pos += 1
            continue
        if consumer_id in queue(queue_id).values()[queue_pos].notifications:
            # only select consumer which was not notified yet
            queue_pos += 1
            continue
        break
    if queue_pos >= len(queue(queue_id)):
        return None
    return queue(queue_id).values()[queue_pos].message_id


def pop_message(queue_id, message_id=None):
    if not valid_queue_id(queue_id):
        lg.warn('invalid queue id')
        return None
    if queue_id not in queue().keys():
        lg.warn('queue id not found')
        return None
    if message_id is None:
        if len(queue(queue_id).keys()) == 0:
            lg.warn('there is no messages in the queue')
            return None
        message_id = queue(queue_id).keys()[0]
    if message_id not in queue(queue_id):
        lg.warn('given message was not found in the queue')
        return None
    existing_message = queue(queue_id).pop(message_id)
    existing_message.state = 'PULLED'
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.pop_message  %s removed from queue %s' % (message_id, queue_id, ))
    return existing_message

#------------------------------------------------------------------------------

def on_notification_succeed(result, consumer_id, queue_id, message_id):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.on_notification_succeed : message %s delivered to consumer %s from queue %s' % (
            message_id, consumer_id, queue_id))
    finish_notification(consumer_id, queue_id, message_id, success=True)
    reactor.callLater(0, do_cleanup)
    # reactor.callLater(0, do_consume)
    return result


def on_notification_failed(err, consumer_id, queue_id, message_id):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.on_notification_failed : message %s delivery FAILED to consumer %s from queue %s : %s' % (
            message_id, consumer_id, queue_id, err))
    finish_notification(consumer_id, queue_id, message_id, success=False)
    reactor.callLater(0, do_cleanup)
    # reactor.callLater(0, do_consume)
    return err

#------------------------------------------------------------------------------

def do_notify(callback_method, consumer_id, queue_id, message_id):
    existing_message = queue(queue_id)[message_id]

    if consumer_id in existing_message.notifications:
        # notification already sent to given consumer
        return False

    message_json = dict(
        payload=existing_message.payload,
        message_id=existing_message.message_id,
        queue_id=existing_message.queue_id,
        created=existing_message.created,
        producer_id=existing_message.producer_id,
        consumer_id=consumer_id,
    )

    ret = Deferred()

    if isinstance(callback_method, str):
        p2p_service.SendEvent(callback_method, message_json, packet_id=message_id, callbacks={
            commands.Ack(): lambda response, info: ret.callback(True),
            commands.Fail(): lambda response, info: ret.callback(False),
        })
    else:
        try:
            result = callback_method(message_json)
        except:
            lg.exc()
            result = False
        reactor.callLater(0, ret.callback, result)

    return start_notification(consumer_id, queue_id, message_id, ret)


def do_consume(interested_consumers=None):
    if not interested_consumers:
        interested_consumers = consumer().keys()
    to_be_consumed = []
    for consumer_id in interested_consumers:
        if len(consumer(consumer_id)['commands']) == 0:
            # skip, no avaliable notification methods found for given consumer
            continue
        if consumer(consumer_id)['messages'] > MAX_CONSUMER_PENDING_MESSAGES:
            # skip, consumer is overloaded, too much was sent to him, but no response
            reactor.callLater(0, unsubscribe_consumer, consumer_id)
            continue
        interested_queues = set()
        for queue_id in consumer(consumer_id)['queues']:
            if queue_id not in queue():
                lg.warn('consumer queue not found')
                continue
            if len(queue(queue_id)) == 0:
                # no messages in the queue
                continue
            interested_queues.add(queue_id)
        if len(interested_queues) == 0:
            # skip, no new messages in the queues which consumer subscribed on
            continue
        for queue_id in interested_queues:
            to_be_consumed.append((consumer_id, queue_id, ))
    if not to_be_consumed:
        # nothing to consume
        # reactor.callLater(5, do_consume)
        return False
    notifications_count = 0
    consumers_affected = []
    for _consumer_id, _queue_id in to_be_consumed:
        if _consumer_id in consumers_affected:
            # only one message per consumer at a time
            continue
        _message_id = lookup_pending_message(_consumer_id, _queue_id)
        if _message_id is None:
            # no new messages found for that consumer
            continue
        for callback_method in consumer(_consumer_id)['commands']:
            if not do_notify(callback_method, _consumer_id, _queue_id, _message_id, ):
                break
            notifications_count += 1
            consumers_affected.append(_consumer_id)
            break
    del to_be_consumed
    del consumers_affected
    if notifications_count == 0:
        # nothing was sent
        # reactor.callLater(5, do_consume)
        return False
    # reactor.callLater(0.01, do_consume)
    return True


def do_cleanup():
    to_be_removed = []
    for queue_id in queue().keys():
        for _message in queue(queue_id).values():
            if len(_message.consumers) == 0:
                # there is not consumers for that message - remove it
                to_be_removed.append((queue_id, _message.message_id, ))
                continue
            if _message.failed_notifications + _message.success_notifications >= len(_message.consumers):
                # all notifications was sent and results were receved (or timeouts) - remote it
                to_be_removed.append((queue_id, _message.message_id, ))
                continue
    for queue_id, message_id in to_be_removed:
        pop_message(queue_id, message_id)
    del to_be_removed
    return True


#------------------------------------------------------------------------------

class QueueMessage(object):

    def __init__(self, producer_id, queue_id, json_data):
        self.message_id = make_message_id()
        self.producer_id = producer_id
        self.queue_id = queue_id
        self.created = utime.get_sec1970()
        self.payload = json_data
        self.state = 'CREATED'
        self.notifications = {}
        self.success_notifications = 0
        self.failed_notifications = 0
        self.consumers = []
        for consumer_id in consumer():
            if queue_id in consumer(consumer_id)['queues']:
                self.consumers.append(consumer_id)
        if len(self.consumers) == 0:
            lg.warn('message will have no consumers')

#------------------------------------------------------------------------------

def _test_callback(message_json):
    time.sleep(1)
    print '_test_callback:', message_json
    return True


def test():
    lg.set_debug_level(24)
    init()
    add_producer('alice@host-one.com')
    add_consumer('bob@server-second.com')
    add_callback_method('bob@server-second.com', _test_callback)
    open_queue('test123')
    subscribe_consumer('bob@server-second.com', 'test123')
    push_message('alice@host-one.com', 'test123', json_data=dict(abc=123))
    push_message('alice@host-one.com', 'test123', json_data=dict(abc=456))
    push_message('alice@host-one.com', 'test123', json_data=dict(abc=789))
    push_message('alice@host-one.com', 'test123', json_data=dict(abc='abc'))
    push_message('alice@host-one.com', 'test123', json_data=dict(abc='def'))
    push_message('alice@host-one.com', 'test123', json_data=dict(abc='ghi'))
    push_message('alice@host-one.com', 'test123', json_data=dict(abc='jkl'))
    push_message('alice@host-one.com', 'test123', json_data=dict(abc='nop'))
    reactor.run()


if __name__ == '__main__':
    test()
