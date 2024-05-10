#!/usr/bin/python
# p2p_queue.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
    + Consumers will listen to the queue and read the messages coming in
    + Producer only start sending if he have a Public Key
    + Consumer can only listen if he possess the correct Private Key
    + Queue is only stored on given node: both producer and consumer must be connected to that machine
    + Global queue ID is unique : queue_alias&alice@somehost.net&bob@anotherhost.com
    + Queue size is limited by a parameter, you can not publish when queue is overloaded

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys
import time

from collections import OrderedDict

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in p2p_queue.py')

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import utime
from bitdust.lib import misc
from bitdust.lib import packetid
from bitdust.lib import strng
from bitdust.lib import jsn
from bitdust.lib import serialization

from bitdust.main import events

from bitdust.crypt import my_keys
from bitdust.crypt import signed

from bitdust.p2p import commands
from bitdust.p2p import p2p_service

from bitdust.userid import global_id
from bitdust.userid import my_id
from bitdust.userid import id_url

#------------------------------------------------------------------------------

MAX_QUEUE_LENGTH = 100
MAX_CONSUMER_PENDING_MESSAGES = int(MAX_QUEUE_LENGTH/2)

MIN_PROCESS_QUEUES_DELAY = 0.1
MAX_PROCESS_QUEUES_DELAY = 2.0

#------------------------------------------------------------------------------

_ProcessQueuesDelay = 0.1
_ProcessQueuesTask = None
_ProcessQueuesLastTime = 0

_ActiveQueues = {}

_LastMessageID = None

_Producers = {}
_Consumers = {}

_EventPacketReceivedCallbacks = []
_MessageProcessedCallbacks = []

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.init')
    add_event_handler(do_handle_event_packet)
    start()


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.shutdown')
    remove_event_handler(do_handle_event_packet)
    stop()


#------------------------------------------------------------------------------


def make_message_id():
    """
    Generate a unique message ID to be stored in the queue.
    """
    global _LastMessageID
    if _LastMessageID is None:
        _LastMessageID = int(str(int(time.time()*100.0))[4:])
    _LastMessageID += 1
    return _LastMessageID


#------------------------------------------------------------------------------


def queue(queue_id=None):
    global _ActiveQueues
    if queue_id is None:
        return _ActiveQueues
    if queue_id not in _ActiveQueues:
        raise Exception('queue not found')
    return _ActiveQueues[queue_id]


def consumer(consumer_id=None):
    global _Consumers
    if consumer_id is None:
        return _Consumers
    if consumer_id not in _Consumers:
        raise Exception('consumer not found')
    return _Consumers[consumer_id]


def producer(producer_id=None):
    global _Producers
    if producer_id is None:
        return _Producers
    if producer_id not in _Producers:
        raise Exception('producer not found')
    return _Producers[producer_id]


#------------------------------------------------------------------------------


def start():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.start')
    reactor.callLater(0, process_queues)  # @UndefinedVariable
    return True


def stop():
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.stop')
    global _ProcessQueuesTask
    if _ProcessQueuesTask:
        if _ProcessQueuesTask.active():
            _ProcessQueuesTask.cancel()
        _ProcessQueuesTask = None
        return True
    return False


def process_queues(interested_consumers=None):
    global _ProcessQueuesDelay
    global _ProcessQueuesTask
    global _ProcessQueuesLastTime
    has_activity = do_consume(interested_consumers=interested_consumers)
    _ProcessQueuesLastTime = time.time()
    if _ProcessQueuesTask is None or _ProcessQueuesTask.called:
        _ProcessQueuesDelay = misc.LoopAttenuation(
            _ProcessQueuesDelay,
            has_activity,
            MIN_PROCESS_QUEUES_DELAY,
            MAX_PROCESS_QUEUES_DELAY,
        )
        # attenuation
        _ProcessQueuesTask = reactor.callLater(_ProcessQueuesDelay, process_queues)  # @UndefinedVariable


def touch_queues(interested_consumers=None):
    global _ProcessQueuesDelay
    global _ProcessQueuesTask
    global _ProcessQueuesLastTime
    if time.time() - _ProcessQueuesLastTime < MIN_PROCESS_QUEUES_DELAY:
        return False
    reactor.callLater(0, process_queues, interested_consumers=interested_consumers)  # @UndefinedVariable
    return True


#------------------------------------------------------------------------------


def valid_queue_id(queue_id):
    if not queue_id:
        return False
    try:
        str(queue_id)
    except:
        return False
    queue_info = global_id.ParseGlobalQueueID(queue_id)
    if not misc.ValidName(queue_info['queue_alias']):
        return False
    owner_id = global_id.ParseGlobalID(queue_info['owner_id'])
    if not owner_id['idurl']:
        return False
    supplier_id = global_id.ParseGlobalID(queue_info['supplier_id'])
    if not supplier_id['idurl']:
        return False
    return True


def is_queue_exist(queue_id):
    return queue_id in queue()


def open_queue(queue_id):
    global _ActiveQueues
    if not valid_queue_id(queue_id):
        raise Exception('invalid queue id')
    if queue_id in queue():
        raise Exception('queue already exist')
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id)
    _ActiveQueues[queue_id] = OrderedDict()
    lg.info('new queue opened: %s' % queue_id)
    return True


def close_queue(queue_id, remove_empty_consumers=False, remove_empty_producers=False):
    global _ActiveQueues
    if not valid_queue_id(queue_id):
        raise Exception('invalid queue id')
    if queue_id not in queue():
        raise Exception('queue not exist')
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id)
    for producer_id in list(producer().keys()):
        if is_producer_connected(producer_id, queue_id):
            disconnect_producer(producer_id, queue_id, remove_empty=remove_empty_producers)
    for message_id in list(queue(queue_id).keys()):
        if message_id not in queue(queue_id):
            continue
        for consumer_id in list(queue(queue_id)[message_id].notifications.keys()):
            msg_obj = queue(queue_id).get(message_id)
            if msg_obj:
                callback_object = queue(queue_id)[message_id].notifications.get(consumer_id)
                if callback_object and not callback_object.called:
                    lg.info('canceling non-finished notification in the queue %s' % queue_id)
                    callback_object.cancel()
    for consumer_id in list(consumer().keys()):
        if is_consumer_subscribed(consumer_id, queue_id):
            unsubscribe_consumer(consumer_id, queue_id, remove_empty=remove_empty_consumers)
    _ActiveQueues.pop(queue_id)
    lg.info('existing queue closed: %s' % queue_id)
    return True


def rename_queue(old_queue_id, new_queue_id):
    if old_queue_id == new_queue_id:
        return False
    if not valid_queue_id(old_queue_id):
        raise Exception('invalid queue id')
    if not valid_queue_id(new_queue_id):
        raise Exception('invalid queue id')
    if old_queue_id not in queue():
        raise Exception('queue not exist')
    if _Debug:
        lg.args(_DebugLevel, old=old_queue_id, new=new_queue_id)
    stored_messages = queue().pop(old_queue_id)
    for message_id, msg_obj in stored_messages.items():
        for consumer_id, callback_object in list(msg_obj.notifications.items()):
            if not callback_object.called:
                callback_object.addCallback(on_notification_succeed, consumer_id, new_queue_id, message_id)
                callback_object.addErrback(on_notification_failed, consumer_id, new_queue_id, message_id)
    subscribed_consumers = list_subscribed_consumers(old_queue_id)
    connected_producers = list_connected_producers(old_queue_id)
    queue()[new_queue_id] = stored_messages
    for consumer_id in subscribed_consumers:
        consumer(consumer_id).queues.remove(old_queue_id)
        consumer(consumer_id).queues.append(new_queue_id)
    for producer_id in connected_producers:
        producer(producer_id).queues.remove(old_queue_id)
        producer(producer_id).queues.append(new_queue_id)
    lg.info('existing queue renamed: %s -> %s' % (old_queue_id, new_queue_id))
    return True


#------------------------------------------------------------------------------


def is_consumer_exists(consumer_id):
    return consumer_id in consumer()


def add_consumer(consumer_id):
    global _Consumers
    if consumer_id in consumer():
        raise Exception('consumer already exist')
    _Consumers[consumer_id] = ConsumerInfo(consumer_id)
    lg.info('new consumer added: %s' % consumer_id)
    return True


def remove_consumer(consumer_id):
    global _Consumers
    if consumer_id not in consumer():
        raise Exception('consumer not exist')
    old_consumer = _Consumers.pop(consumer_id)
    old_consumer.commands = {}
    old_consumer.queues = []
    lg.info('existing consumer removed: %s' % str(consumer_id))
    return True


#------------------------------------------------------------------------------


def is_callback_method_registered(consumer_id, callback_method):
    if consumer_id not in consumer():
        return False
    if callback_method not in consumer(consumer_id).commands:
        return False
    return True


def add_callback_method(consumer_id, callback_method, interested_queues_list=None):
    if consumer_id not in consumer():
        raise Exception('consumer not found')
    if callback_method in consumer(consumer_id).commands:
        raise Exception('callback method already exist')
    consumer(consumer_id).commands[callback_method] = interested_queues_list
    if _Debug:
        lg.args(_DebugLevel, c=consumer_id, cb=callback_method)
    return True


def remove_callback_method(consumer_id, callback_method):
    if consumer_id not in consumer():
        raise Exception('consumer not found')
    if callback_method not in consumer(consumer_id).commands:
        raise Exception('callback method not found')
    consumer(consumer_id).commands.pop(callback_method)
    if _Debug:
        lg.args(_DebugLevel, c=consumer_id, cb=callback_method)
    return True


#------------------------------------------------------------------------------


def is_consumer_subscribed(consumer_id, queue_id=None):
    if queue_id and not valid_queue_id(queue_id):
        return False
    if consumer_id not in consumer():
        return False
    if not queue_id:
        return len(consumer(consumer_id).queues) > 0
    if queue_id not in consumer(consumer_id).queues:
        return False
    return True


def list_subscribed_consumers(queue_id):
    if not valid_queue_id(queue_id):
        return []
    return [c_id for c_id in consumer().keys() if queue_id in consumer(c_id).queues]


def subscribe_consumer(consumer_id, queue_id):
    if not valid_queue_id(queue_id):
        raise Exception('invalid queue id')
    if consumer_id not in consumer():
        raise Exception('consumer not found')
    if queue_id in consumer(consumer_id).queues:
        raise Exception('consumer is already subscribed')
    consumer(consumer_id).queues.append(queue_id)
    lg.info('consumer %s subscribed to read queue %s' % (consumer_id, queue_id))
    return True


def unsubscribe_consumer(consumer_id, queue_id=None, remove_empty=False):
    if not valid_queue_id(queue_id):
        raise Exception('invalid queue id')
    if consumer_id not in consumer():
        raise Exception('consumer not found')
    if queue_id is None:
        consumer(consumer_id).queues = []
        lg.info('consumer %s unsubscribed from all queues' % (consumer_id, ))
        if remove_empty:
            remove_consumer(consumer_id)
        return True
    if queue_id not in consumer(consumer_id).queues:
        raise Exception('consumer is not subscribed')
    consumer(consumer_id).queues.remove(queue_id)
    lg.info('consumer %s unsubscribed from queue %s' % (consumer_id, queue_id))
    if remove_empty:
        if len(consumer(consumer_id).queues) == 0:
            remove_consumer(consumer_id)
    return True


#------------------------------------------------------------------------------


def is_producer_exist(producer_id):
    return producer_id in producer()


def add_producer(producer_id):
    global _Producers
    if is_producer_exist(producer_id):
        raise Exception('producer already exist')
    _Producers[producer_id] = ProducerInfo(producer_id)
    lg.info('new producer added: %s' % producer_id)
    return True


def remove_producer(producer_id):
    global _Producers
    if not is_producer_exist(producer_id):
        raise Exception('producer not exist')
    old_producer = _Producers.pop(producer_id)
    old_producer.queues = []
    for event_id in list(old_producer.publishers.keys()):
        old_producer.stop_publisher(event_id)
    lg.info('existing producer removed: %s' % str(producer_id))
    return True


#------------------------------------------------------------------------------


def is_producer_connected(producer_id, queue_id=None):
    if queue_id and not valid_queue_id(queue_id):
        return False
    if not is_producer_exist(producer_id):
        return False
    if not queue_id:
        return len(producer(producer_id).queues) > 0
    return queue_id in producer(producer_id).queues


def list_connected_producers(queue_id):
    if not valid_queue_id(queue_id):
        return []
    return [p_id for p_id in producer().keys() if queue_id in producer(p_id).queues]


def connect_producer(producer_id, queue_id):
    if not is_producer_exist(producer_id):
        raise Exception('producer not exist')
    if not is_queue_exist(queue_id):
        raise Exception('queue not exist')
    if queue_id not in producer(producer_id).queues:
        producer(producer_id).queues.append(queue_id)
        lg.info('producer %s connected to queue %s' % (producer_id, queue_id))
    else:
        lg.warn('producer %s already connected to queue %s' % (producer_id, queue_id))
    return True


def disconnect_producer(producer_id, queue_id=None, remove_empty=False):
    if not is_producer_exist(producer_id):
        raise Exception('producer not exist')
    if not is_queue_exist(queue_id):
        raise Exception('queue not exist')
    if queue_id is None:
        producer(producer_id).queues = []
        lg.info('producer %s disconnected from all queues' % (producer_id, ))
        if remove_empty:
            remove_producer(producer_id)
        return True
    if queue_id not in producer(producer_id).queues:
        raise Exception('producer is not connected to that queue')
    producer(producer_id).queues.remove(queue_id)
    lg.info('producer %s disconnected from queue %s' % (producer_id, queue_id))
    if remove_empty:
        if len(producer(producer_id).queues) == 0:
            remove_producer(producer_id)
    return True


#------------------------------------------------------------------------------


def is_event_publishing(producer_id, event_id):
    if not is_producer_exist(producer_id):
        return False
    return producer(producer_id).is_event_publishing(event_id)


def start_event_publisher(producer_id, event_id):
    if not is_producer_exist(producer_id):
        raise Exception('producer not exist')
    return producer(producer_id).start_publisher(event_id)


def stop_event_publisher(producer_id, event_id):
    if not is_producer_exist(producer_id):
        raise Exception('producer not exist')
    return producer(producer_id).stop_publisher(event_id)


#------------------------------------------------------------------------------


def start_notification(consumer_id, queue_id, message_id):
    if not valid_queue_id(queue_id):
        raise Exception('invalid queue id')
    if consumer_id not in consumer():
        raise Exception('consumer not found')
    if queue_id not in queue():
        raise Exception('queue not exist')
    if message_id not in queue(queue_id):
        raise Exception('message not exist')
    if consumer_id in queue(queue_id)[message_id].notifications:
        raise Exception('notification already sent to given consumer')
    callback_object = Deferred()
    queue(queue_id)[message_id].notifications[consumer_id] = callback_object
    consumer(consumer_id).consumed_messages += 1
    callback_object.addCallback(on_notification_succeed, consumer_id, queue_id, message_id)
    callback_object.addErrback(on_notification_failed, consumer_id, queue_id, message_id)
    queue(queue_id)[message_id].state = 'SENT'
    if _Debug:
        lg.args(_DebugLevel, consumer_id=consumer_id, queue_id=queue_id, message_id=message_id, notifications=len(queue(queue_id)[message_id].notifications))
    return callback_object


def finish_notification(consumer_id, queue_id, message_id, success):
    if not valid_queue_id(queue_id):
        raise Exception('invalid queue id')
    if queue_id not in queue():
        raise Exception('queue not exist')
    if message_id not in queue(queue_id):
        raise Exception('message not exist')
    if consumer_id not in queue(queue_id)[message_id].notifications:
        raise Exception('not found pending notification for given consumer')
    defer_result = queue(queue_id)[message_id].notifications[consumer_id]
    if defer_result is None:
        raise Exception('notification already finished')
    if not isinstance(defer_result, Deferred):
        raise Exception('invalid notification type')
    queue(queue_id)[message_id].notifications[consumer_id] = None
    # queue(queue_id)[message_id].notifications.pop(consumer_id)
    if success:
        queue(queue_id)[message_id].success_notifications.append(consumer_id)
        consumer(consumer_id).success_notifications += 1
    else:
        queue(queue_id)[message_id].failed_notifications.append(consumer_id)
        consumer(consumer_id).failed_notifications += 1
    if not defer_result.called:
        lg.info('canceling non-finished notification in the queue %s' % queue_id)
        defer_result.cancel()
    del defer_result
    if _Debug:
        lg.args(_DebugLevel, consumer_id=consumer_id, queue_id=queue_id, message_id=message_id, success=success, notifications=len(queue(queue_id)[message_id].notifications))
    return True


#------------------------------------------------------------------------------


def on_notification_succeed(result, consumer_id, queue_id, message_id):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.on_notification_succeed : message %r delivered to consumer %r in %r' % (message_id, consumer_id, queue_id))
    if is_queue_exist(queue_id) and is_consumer_exists(consumer_id):
        try:
            # reactor.callLater(0, finish_notification, consumer_id, queue_id, message_id, success=True)  # @UndefinedVariable
            finish_notification(consumer_id, queue_id, message_id, success=True)
        except:
            lg.exc()
    else:
        lg.warn('notification %r was not finished for consumer %r in %r' % (message_id, consumer_id, queue_id))
    # TODO: add a counter and execute cleanup less frequently
    do_cleanup(target_queues=[queue_id])
    # reactor.callLater(0, do_cleanup, target_queues=[queue_id, ])  # @UndefinedVariable
    return result


def on_notification_failed(err, consumer_id, queue_id, message_id):
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.on_notification_failed FAILED message %r for consumer %r in %r : %r' % (message_id, consumer_id, queue_id, err.getErrorMessage()))
    if is_queue_exist(queue_id) and is_consumer_exists(consumer_id):
        try:
            # reactor.callLater(0, finish_notification, consumer_id, queue_id, message_id, success=False)  # @UndefinedVariable
            finish_notification(consumer_id, queue_id, message_id, success=False)
        except:
            lg.exc()
    else:
        lg.warn('failed notification %r was not finished for consumer %r in %r' % (message_id, consumer_id, queue_id))
    # TODO: add a counter and execute cleanup less frequently
    do_cleanup(target_queues=[queue_id])
    return None


#------------------------------------------------------------------------------


def write_message(producer_id, queue_id, data, creation_time=None):
    if not valid_queue_id(queue_id):
        raise Exception('invalid queue id')
    if not is_producer_exist(producer_id):
        raise Exception('unknown producer')
    if not is_producer_connected(producer_id, queue_id):
        raise Exception('producer was not connected to the queue')
    if len(queue(queue_id)) >= MAX_QUEUE_LENGTH:
        raise P2PQueueIsOverloaded('queue is overloaded')
    producer(producer_id).produced_messages += 1
    new_message = QueueMessage(producer_id, queue_id, data, created=creation_time)
    queue(queue_id)[new_message.message_id] = new_message
    queue(queue_id)[new_message.message_id].state = 'PUSHED'
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.write_message  %r added to queue %s with %r' % (new_message.message_id, queue_id, data))
    touch_queues()
    return new_message


def pull_message(queue_id, message_id=None):
    if not valid_queue_id(queue_id):
        raise Exception('invalid queue id')
    if queue_id not in list(queue().keys()):
        raise Exception('queue id not found')
    if message_id is None:
        if len(list(queue(queue_id).keys())) == 0:
            lg.info('there is no messages in the queue %s' % queue_id)
            return None
        message_id = list(queue(queue_id).keys())[0]
    if message_id not in queue(queue_id):
        lg.info('given message was not found in the queue %s' % queue_id)
        return None
    existing_message = queue(queue_id).pop(message_id)
    existing_message.state = 'PULLED'
    if _Debug:
        lg.out(_DebugLevel, 'p2p_queue.pull_message  %r removed from queue %s' % (message_id, queue_id))
    return existing_message


def lookup_pending_message(consumer_id, queue_id):
    if not valid_queue_id(queue_id):
        raise Exception('invalid queue id')
    if queue_id not in queue():
        raise Exception('queue not exist')
    if consumer_id not in consumer():
        raise Exception('consumer not found')
    pending_message_id = None
    # here we assume that OrderedDict is really ordered
    for message_id, message_obj in queue(queue_id).items():
        # loop all messages from the beginning
        if consumer_id not in message_obj.consumers:
            # only interested consumers needs to be selected
            continue
        if consumer_id in message_obj.success_notifications or consumer_id in message_obj.failed_notifications:
            # only select consumer which was not notified yet
            continue
        if consumer_id in message_obj.notifications:
            # notification already started to given consumer
            continue
        pending_message_id = message_id
        break
    return pending_message_id


#------------------------------------------------------------------------------


def push_signed_message(producer_id, queue_id, data, creation_time=None):
    # TODO: to be continue
    try:
        signed_data = signed.Packet(
            Command=commands.Event(),
            OwnerID=producer_id,
            CreatorID=my_id.getIDURL(),
            PacketID=packetid.UniqueID(),
            Payload=serialization.DictToBytes(data, keys_to_text=True),
            RemoteID=queue_id,
            KeyID=producer_id,
        )
    except:
        lg.exc()
        raise Exception('sign message failed')
    return write_message(producer_id, queue_id, data=signed_data.Serialize(), creation_time=creation_time)


def pop_signed_message(queue_id, message_id):
    # TODO: to be continue
    existing_message = pull_message(queue_id, message_id)
    if not existing_message:
        return existing_message
    try:
        signed_data = signed.Unserialize(existing_message.payload)
    except:
        raise Exception('unserialize message fails')
    if not signed_data:
        raise Exception('unserialized message is empty')
    if not signed_data.Valid():
        raise Exception('unserialized message is not valid')
    try:
        existing_message.payload = serialization.BytesToDict(signed_data.Payload, keys_to_text=True)
    except:
        raise Exception('failed reading message json data')
    return existing_message


#------------------------------------------------------------------------------


def add_event_handler(cb):
    global _EventPacketReceivedCallbacks
    _EventPacketReceivedCallbacks.append(cb)


def insert_event_handler(cb):
    global _EventPacketReceivedCallbacks
    _EventPacketReceivedCallbacks.insert(0, cb)


def remove_event_handler(cb):
    global _EventPacketReceivedCallbacks
    _EventPacketReceivedCallbacks.remove(cb)


#------------------------------------------------------------------------------


def add_message_processed_callback(cb):
    global _MessageProcessedCallbacks
    _MessageProcessedCallbacks.append(cb)


def remove_message_processed_callback(cb):
    global _MessageProcessedCallbacks
    _MessageProcessedCallbacks.remove(cb)


#------------------------------------------------------------------------------


def on_event_packet_received(newpacket, info, status, error_message):
    global _EventPacketReceivedCallbacks
    try:
        e_json = serialization.BytesToDict(newpacket.Payload, keys_to_text=True, values_to_text=True)
        strng.to_text(e_json['event_id'])
    except:
        lg.warn('invalid json payload')
        return False
    handled = False
    for cb in _EventPacketReceivedCallbacks:
        handled = cb(newpacket, e_json)
        if handled:
            break
    return handled


def do_handle_event_packet(newpacket, e_json):
    event_id = strng.to_text(e_json['event_id'])
    payload = e_json['payload']
    queue_id = strng.to_text(e_json.get('queue_id'))
    producer_id = e_json.get('producer_id')
    message_id = strng.to_text(e_json.get('message_id'))
    created = strng.to_text(e_json.get('created'))
    if _Debug:
        lg.args(_DebugLevel, event_id=event_id, queue_id=queue_id, producer_id=producer_id, message_id=message_id)
    if queue_id and producer_id and message_id:
        # this message have an ID and producer so it came from a queue and needs to be consumed
        # also, more info coming from the queue needs to be attached to the event body
        # TODO: need more verifications to be implemented here
        # SECURITY
        if _Debug:
            lg.info('received new event %s from the queue at %s' % (event_id, queue_id))
        payload.update(dict(
            queue_id=queue_id,
            producer_id=producer_id,
            message_id=message_id,
            created=created,
        ))
        events.send(event_id, data=payload)
        p2p_service.SendAck(newpacket)
        return True
    if producer_id == my_id.getID() and not queue_id:
        # this message addressed directly to me, not to any specific queue
        return True
    # this message does not have nor ID nor producer so it came from another user directly
    # lets' try to find a queue for that event and see if we need to publish it or not
    queue_id = global_id.MakeGlobalQueueID(
        queue_alias=event_id,
        owner_id=global_id.MakeGlobalID(idurl=newpacket.OwnerID),
        supplier_id=global_id.MakeGlobalID(idurl=my_id.getGlobalID()),
    )
    if queue_id not in queue():
        # such queue is not found locally, that means message is
        # probably addressed to that node and needs to be consumed directly
        # TODO: check if we actually should consume the event locally and populate the event
        # need more verifications to be implemented here
        # SECURITY
        if _Debug:
            lg.warn('received event %s was not delivered to any queue, consume now and send an Ack' % event_id)
        # also add more info coming from the queue
        payload.update(dict(
            queue_id=queue_id,
            producer_id=producer_id,
            message_id=message_id,
            created=created,
        ))
        events.send(event_id, data=payload)
        p2p_service.SendAck(newpacket)
        return True
    # found a queue for that message, pushing there
    # TODO: add verification of producer's identity and signature
    # SECURITY
    if _Debug:
        lg.info('pushing event %s to the queue %s on behalf of producer %s' % (event_id, queue_id, producer_id))
    try:
        write_message(
            producer_id=producer_id,
            queue_id=queue_id,
            data=payload,
            creation_time=created,
        )
    except Exception as exc:
        lg.exc()
        p2p_service.SendFail(newpacket, str(exc))
        return True
    p2p_service.SendAck(newpacket)
    return True


#------------------------------------------------------------------------------


def do_notify(callback_method, consumer_id, queue_id, message_id):
    existing_message = queue(queue_id)[message_id]
    event_id = global_id.ParseGlobalQueueID(queue_id)['queue_alias']
    if consumer_id in existing_message.notifications:
        if _Debug:
            lg.dbg(_DebugLevel, 'notification %r already started for consumer %r' % (message_id, consumer_id))
        # notification already sent to given consumer
        return False
    if _Debug:
        lg.args(_DebugLevel, cb=callback_method, c=consumer_id, q=queue_id, m=message_id)
    ret = start_notification(consumer_id, queue_id, message_id)
    if id_url.is_idurl(callback_method):
        p2p_service.SendEvent(
            remote_idurl=id_url.field(callback_method),
            event_id=event_id,
            payload=existing_message.payload,
            producer_id=existing_message.producer_id,
            consumer_id=consumer_id,
            queue_id=queue_id,
            message_id=existing_message.message_id,
            created=existing_message.created,
            callbacks={
                commands.Ack(): lambda response, info: ret.callback(True),
                commands.Fail(): lambda response, info: ret.callback(False),
                None: lambda pkt_out: ret.callback(False),
            },
        )
    else:
        try:
            result = callback_method(
                dict(
                    event_id=event_id,
                    payload=existing_message.payload,
                    producer_id=existing_message.producer_id,
                    consumer_id=consumer_id,
                    queue_id=queue_id,
                    message_id=existing_message.message_id,
                    created=existing_message.created,
                )
            )
        except:
            lg.exc('%r %r %r %r' % (callback_method, consumer_id, queue_id, message_id))
            result = False
        if isinstance(result, Deferred):
            result.addCallback(lambda ok: ret.callback(True) if ok else ret.callback(False))
            result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='p2p_queue.do_notify')
            result.addErrback(lambda err: ret.callback(False))
        else:
            reactor.callLater(0, ret.callback, result)  # @UndefinedVariable
    return ret


def do_consume(interested_consumers=None):
    if not interested_consumers:
        interested_consumers = list(consumer().keys())
    disconnected_consumers = []
    to_be_consumed = []
    for consumer_id in interested_consumers:
        if len(consumer(consumer_id).queues) == 0:
            # skip, consumer is not subscribed to any queues
            continue
        if len(consumer(consumer_id).commands) == 0:
            # skip, no available notification methods found for given consumer
            disconnected_consumers.append(consumer_id)
            continue
        interested_queues = set()
        for queue_id in consumer(consumer_id).queues:
            if queue_id not in queue():
                continue
            if len(queue(queue_id)) == 0:
                # no messages in the queue
                continue
            interested_queues.add(queue_id)
        if len(interested_queues) == 0:
            # skip, no new messages in the queues which consumer subscribed on
            continue
        for queue_id in interested_queues:
            to_be_consumed.append((
                consumer_id,
                queue_id,
            ))
    if not to_be_consumed:
        # nothing to consume
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
        for callback_method, interested_queues_list in consumer(_consumer_id).commands.items():
            if interested_queues_list:
                matching = False
                for interested_queue in interested_queues_list:
                    if _queue_id.startswith(interested_queue):
                        matching = True
                        break
                if not matching:
                    continue
            do_notify(callback_method, _consumer_id, _queue_id, _message_id)
            notifications_count += 1
            consumers_affected.append(_consumer_id)
            break
    if _Debug:
        lg.args(_DebugLevel, notifications_count=notifications_count, consumers_affected=consumers_affected)
    del to_be_consumed
    del consumers_affected
    if notifications_count == 0:
        # nothing was sent
        return False
    return True


def do_cleanup(target_queues=None):
    global _MessageProcessedCallbacks
    to_be_removed = set()
    if not target_queues:
        target_queues = list(queue().keys())
    for queue_id in target_queues:
        if not is_queue_exist(queue_id):
            continue
        for _message in queue(queue_id).values():
            if _message.state == 'SENT':
                found_pending_notifications = False
                for defer_result in _message.notifications.values():
                    if defer_result and not defer_result.called:
                        found_pending_notifications = True
                if not found_pending_notifications:
                    # no pending notifications found, but state is SENT : all is done
                    to_be_removed.add((queue_id, _message.message_id))
                    continue
                if len(_message.failed_notifications) + len(_message.success_notifications) >= len(_message.consumers):
                    # all notifications are sent and results are received (or timeouts) - remove message from the queue
                    to_be_removed.add((queue_id, _message.message_id))
                    continue
            if len(_message.consumers) == 0:
                # there is no consumers for that message - remove it
                to_be_removed.add((queue_id, _message.message_id))
                continue
    for queue_id, message_id in to_be_removed:
        processed_message = pull_message(queue_id, message_id)
        if processed_message:
            for cb in _MessageProcessedCallbacks:
                if not cb(processed_message):
                    lg.warn('message %r was not correctly processed' % message_id)
    to_be_removed.clear()
    del to_be_removed
    return True


#------------------------------------------------------------------------------


class QueueMessage(object):

    def __init__(self, producer_id, queue_id, json_data, created=None):
        self.message_id = make_message_id()
        self.producer_id = producer_id
        self.queue_id = queue_id
        self.created = created or utime.utcnow_to_sec1970()
        self.payload = jsn.dict_items_to_text(json_data)
        self.state = 'CREATED'
        self.notifications = {}
        self.success_notifications = []
        self.failed_notifications = []
        self.consumers = []
        for consumer_id in consumer():
            if queue_id in consumer(consumer_id).queues:
                self.consumers.append(consumer_id)
        if len(self.consumers) == 0:
            if _Debug:
                lg.warn('message %r from %r in queue %r will have no consumers' % (self.message_id, self.producer_id, self.queue_id))

    def __repr__(self):
        return 'QueueMessage[%s](%s by %s in %s)' % (
            self.state,
            self.message_id,
            self.producer_id,
            self.queue_id,
        )

    def get_sequence_id(self):
        return self.payload.get('sequence_id', None)


#------------------------------------------------------------------------------


class ConsumerInfo(object):

    def __init__(self, consumer_id):
        self.state = 'READY'
        self.consumer_id = consumer_id
        self.commands = {}
        self.queues = []
        self.consumed_messages = 0
        self.success_notifications = 0
        self.failed_notifications = 0


#------------------------------------------------------------------------------


class ProducerInfo(object):

    def __init__(self, producer_id):
        self.state = 'READY'
        self.producer_id = producer_id
        self.produced_messages = 0
        self.queues = []
        self.publishers = {}

    def is_event_publishing(self, event_id):
        return event_id in self.publishers

    def do_push_message(self, evt):
        if not self.queues:
            if _Debug:
                lg.warn('producer is not connected to any queue')
            return False
        for queue_id in self.queues:
            try:
                write_message(producer_id=self.producer_id, queue_id=queue_id, data=evt.data, creation_time=evt.created)
            except P2PQueueIsOverloaded as exc:
                lg.warn('queue_id=%s producer_id=%s: %s' % (queue_id, self.producer_id, exc))
        return True

    def start_publisher(self, event_id):
        if event_id in self.publishers:
            raise Exception('event publisher already exist')
        self.publishers[event_id] = lambda evt: self.do_push_message(evt)
        return events.add_subscriber(self.publishers[event_id], event_id)

    def stop_publisher(self, event_id):
        if event_id not in self.publishers:
            raise Exception('event publisher not found')
        result = events.remove_subscriber(self.publishers[event_id], event_id)
        if not self.publishers.pop(event_id, None):
            lg.warn('publisher event %s for producer %s was not cleaned correctly' % (event_id, self.producer_id))
        if not result:
            lg.warn('event subscriber for %s was not removed' % event_id)
        return result


#------------------------------------------------------------------------------


class P2PQueueIsOverloaded(Exception):
    pass


#------------------------------------------------------------------------------


def _test_callback_bob(message_json):
    # time.sleep(1)
    print('               !!!!!!!!!!!!! _test_callback_bob:', message_json)
    return True


def _test_callback_dave(message_json):
    # time.sleep(1)
    print('               !!!!!!!!!!!!! _test_callback_dave:', message_json)
    return True


def test():
    lg.set_debug_level(24)
    init()
    my_keys.generate_key('customer$bob@server-second.com')
    open_queue('event-test123&bob@server-second.com&carl@thirdnode.net')
    add_producer('alice@host-one.com')
    connect_producer('alice@host-one.com', 'event-test123&bob@server-second.com&carl@thirdnode.net')
    start_event_publisher('alice@host-one.com', 'test123')
    add_consumer('bob@server-second.com')
    add_callback_method('bob@server-second.com', _test_callback_bob)
    subscribe_consumer('bob@server-second.com', 'event-test123&bob@server-second.com&carl@thirdnode.net')
    add_consumer('dave@server-4.com')
    add_callback_method('dave@server-4.com', _test_callback_dave)
    subscribe_consumer('dave@server-4.com', 'event-test123&bob@server-second.com&carl@thirdnode.net')
    events.send('test123', data=dict(abc='abc', counter=0))
    events.send('test123', data=dict(abc='abc', counter=2))
    events.send('test123', data=dict(abc='abc', counter=4))
    events.send('test123', data=dict(abc='abc', counter=1))
    events.send('test123', data=dict(abc='abc', counter=6))
    events.send('test123', data=dict(abc='abc', counter=23))
    events.send('test123', data=dict(abc='abc', counter=620))
    events.send('test123', data=dict(abc='abc', counter=20))
    events.send('test123', data=dict(abc='abc', counter=30))
    events.send('test123', data=dict(abc='abc', counter=40))
    reactor.run()  # @UndefinedVariable


if __name__ == '__main__':
    test()
