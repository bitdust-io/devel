#!/usr/bin/env python
# message_peddler.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (message_peddler.py) is part of BitDust Software.
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
.. module:: message_peddler
.. role:: red

BitDust message_peddler() Automat

EVENTS:
    * :red:`message-pushed`
    * :red:`queue-connect`
    * :red:`queue-disconnect`
    * :red:`queue-read`
    * :red:`queues-loaded`
    * :red:`start`
    * :red:`stop`
"""


#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import sys

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in keys_synchronizer.py')

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from crypt import my_keys

from lib import jsn
from lib import strng
from lib import utime
from lib import packetid

from contacts import identitycache

from system import bpio
from system import local_fs

from main import settings
from main import events

from p2p import p2p_service

from stream import p2p_queue
from stream import queue_keeper
from stream import message

from userid import global_id
from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------ 

_MessagePeddler = None

_ActiveStreams = {}
_ActiveCustomers = {}

#------------------------------------------------------------------------------

def streams():
    global _ActiveStreams
    return _ActiveStreams


def customers():
    global _ActiveCustomers
    return _ActiveCustomers

#------------------------------------------------------------------------------

def register_stream(queue_id):
    if queue_id in streams():
        raise Exception('queue already exist')
    queue_info = global_id.ParseGlobalQueueID(queue_id)
    customer_idurl = global_id.glob2idurl(queue_info['owner_id'])
    if not customer_idurl:
        raise Exception('unknown customer')
    if not id_url.is_cached(customer_idurl):
        raise Exception('customer idurl is not cached yet')
    if customer_idurl not in customers():
        customers()[customer_idurl] = []
    else:
        if queue_id in customers()[customer_idurl]:
            raise Exception('queue is already registered for that customer')
    customers()[customer_idurl].append(queue_id)
    streams()[queue_id] = {
        'active': False,
        'consumers': {},
        'producers': {},
        'messages': [],
        'last_sequence_id': -1,
    }
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, customer_idurl=customer_idurl)
    return True


def unregister_stream(queue_id):
    if queue_id not in streams():
        raise Exception('queue is not exist')
    queue_info = global_id.ParseGlobalQueueID(queue_id)
    customer_idurl = global_id.glob2idurl(queue_info['owner_id'])
    if not customer_idurl:
        raise Exception('unknown customer')
    if not id_url.is_cached(customer_idurl):
        raise Exception('customer idurl is not cached yet')
    if customer_idurl not in customers():
        raise Exception('customer is not registered')
    if queue_id not in customers()[customer_idurl]:
        raise Exception('queue is not registered for that customer')
    customers()[customer_idurl].remove(queue_id)
    if not customers()[customer_idurl]:
        customers().pop(customer_idurl)
    streams().pop(queue_id)
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, customer_idurl=customer_idurl)
    return True

#------------------------------------------------------------------------------

def on_consume_queue_messages(json_messages):
    # if _Debug:
    #     lg.args(_DebugLevel, json_messages=json_messages)
    received = 0
    pushed = 0
    for json_message in json_messages:
        try:
            msg_type = json_message.get('type', '')
            msg_direction = json_message['dir']
            packet_id = json_message['packet_id']
            from_idurl = json_message['owner_idurl']
            to_user = json_message['to']
            msg_data = json_message['data']
        except:
            lg.exc()
            continue
        if msg_direction != 'incoming':
            continue
        if msg_type != 'queue_message':
            continue
        if to_user != my_id.getID():
            continue
        queue_id = msg_data.get('queue_id')
        if queue_id not in streams():
            lg.warn('skipped incoming message, queue %r is not registered' % queue_id)
            p2p_service.SendFailNoRequest(from_idurl, packet_id, 'queue ID not registered')
            continue
        if not streams()[queue_id]['active']:
            lg.warn('skipped incoming message, queue %r is not active' % queue_id)
            p2p_service.SendFailNoRequest(from_idurl, packet_id, 'queue is not active')
            continue
        try:
            payload = msg_data['payload']
        except:
            lg.exc()
            continue
        if not A():
            lg.warn('message_peddler() not started yet')
            continue
        if not A().state == 'READY':
            lg.warn('message_peddler() is not ready yet')
            continue
        if payload == 'queue-read':
            # request from queue_member() to catch up unread messages from the queue
            consumer_id = msg_data.get('consumer_id')
            if consumer_id not in streams()[queue_id]['consumers']:
                lg.warn('skipped incoming message, consumer %r is not registered for queue %r' % (consumer_id, queue_id, ))
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'consumer is not registered')
                continue
            if not streams()[queue_id]['consumers'][consumer_id]['active']:
                lg.warn('skipped incoming message, consumer %r is not active in queue %r' % (consumer_id, queue_id, ))
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'consumer is not active')
                continue
            consumer_last_sequence_id = msg_data.get('last_sequence_id')
            if _Debug:
                lg.args(_DebugLevel, event='queue-read', queue_id=queue_id, consumer_id=consumer_id, consumer_last_sequence_id=consumer_last_sequence_id)
            A('queue-read', queue_id=queue_id, consumer_id=consumer_id, consumer_last_sequence_id=consumer_last_sequence_id)
            p2p_service.SendAckNoRequest(from_idurl, packet_id)
            continue
        # incoming message from queue_member() to push new message to the queue and deliver to all other group members
        producer_id = msg_data.get('producer_id')
        if producer_id not in streams()[queue_id]['producers']:
            lg.warn('skipped incoming message, producer %r is not registered for queue %r' % (producer_id, queue_id, ))
            p2p_service.SendFailNoRequest(from_idurl, packet_id, 'producer is not registered')
            continue
        if not streams()[queue_id]['producers'][producer_id]['active']:
            lg.warn('skipped incoming message, producer %r is not active in queue %r' % (producer_id, queue_id, ))
            p2p_service.SendFailNoRequest(from_idurl, packet_id, 'producer is not active')
            continue
        try:
            payload = msg_data['payload']
            created = msg_data['created']
        except:
            lg.exc()
            continue
        new_sequence_id = increment_sequence_id(queue_id)
        streams()[queue_id]['messages'].append(new_sequence_id)
        queued_json_message = store_message(queue_id, new_sequence_id, producer_id, payload, created)
        received += 1
        if _Debug:
            lg.out(_DebugLevel, '<<< PUSH <<<    into %r by %r at sequence %d' % (
                queue_id, producer_id, new_sequence_id, ))
        try:
            new_message = p2p_queue.write_message(
                producer_id=producer_id,
                queue_id=queue_id,
                data=queued_json_message,
                creation_time=created,
            )
        except:
            lg.exc()
            continue
        register_delivery(queue_id, new_sequence_id, new_message.message_id)
        pushed += 1
        A('message-pushed', new_message)
        p2p_service.SendAckNoRequest(from_idurl, packet_id)
    if received > pushed:
        lg.warn('some of received messages was not pushed to the queue')
    return True


def on_message_processed(processed_message):
    sequence_id = processed_message.get_sequence_id()
    if _Debug:
        lg.args(_DebugLevel, queue_id=processed_message.queue_id, sequence_id=sequence_id,
                message_id=processed_message.message_id,
                success_notifications=processed_message.success_notifications,
                failed_notifications=processed_message.failed_notifications, )
    if sequence_id is None:
        return False
    if not unregister_delivery(
        queue_id=processed_message.queue_id,
        sequence_id=sequence_id,
        message_id=processed_message.message_id,
        failed_consumers=processed_message.failed_notifications,
    ):
        lg.err('failed to unregister message delivery attempt, message_id %r not found at position %d in queue %r' % (
            processed_message.message_id, sequence_id, processed_message.queue_id))
        return False
    if processed_message.failed_notifications:
        if _Debug:
            lg.out(_DebugLevel, '>>> FAILED >>>    from %r at sequence %d, failed_consumers=%d' % (
                processed_message.queue_id, sequence_id, len(processed_message.failed_notifications), ))
    else:
        erase_message(processed_message.queue_id, sequence_id)
        streams()[processed_message.queue_id]['messages'].remove(sequence_id)
        if _Debug:
            lg.out(_DebugLevel, '>>> PULL >>>    from %r at sequence %d with success count %d' % (
                processed_message.queue_id, sequence_id, len(processed_message.success_notifications), ))
    return True


def on_consumer_notify(message_info):
    payload = message_info['payload']
    consumer_id = message_info['consumer_id']
    queue_id = message_info['queue_id']
    packet_id = 'queue_%s_%s' % (queue_id, packetid.UniqueID(), )
    sequence_id = payload['sequence_id']
    last_sequence_id = get_latest_sequence_id(queue_id)
    producer_id = payload['producer_id']
    if _Debug:
        lg.args(_DebugLevel, producer_id=producer_id, consumer_id=consumer_id, queue_id=queue_id,
                sequence_id=sequence_id, last_sequence_id=last_sequence_id)
    ret = message.send_message(
        json_data={
            'items': [{
                'sequence_id': sequence_id,
                'created': payload['created'],
                'producer_id': producer_id,
                'payload': payload['payload'],
            }, ],
            'last_sequence_id': last_sequence_id,
        },
        recipient_global_id=consumer_id,
        packet_id=packet_id,
        skip_handshake=True,
        fire_callbacks=False,
    )
    if _Debug:
        lg.out(_DebugLevel, '>>> NOTIFY >>>    from %r by producer %r to consumer %r at sequence %d' % (
            queue_id, producer_id, consumer_id, sequence_id, ))
    return ret

#------------------------------------------------------------------------------

def get_latest_sequence_id(queue_id):
    if queue_id not in streams():
        return -1
    return streams()[queue_id].get('last_sequence_id', -1)


def increment_sequence_id(queue_id):
    last_sequence_id = streams()[queue_id]['last_sequence_id']
    new_sequence_id = last_sequence_id + 1
    streams()[queue_id]['last_sequence_id'] = new_sequence_id
    return new_sequence_id

#------------------------------------------------------------------------------

def store_message(queue_id, sequence_id, producer_id, payload, created):
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    message_path = os.path.join(messages_dir, strng.to_text(sequence_id))
    stored_json_message = {
        'sequence_id': sequence_id,
        'created': created,
        'producer_id': producer_id,
        'payload': payload,
        'attempts': [],
    }
    local_fs.WriteTextFile(message_path, jsn.dumps(stored_json_message))
    return stored_json_message


def register_delivery(queue_id, sequence_id, message_id):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, sequence_id=sequence_id, message_id=message_id)
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    message_path = os.path.join(messages_dir, strng.to_text(sequence_id))
    stored_json_message = jsn.loads_text(local_fs.ReadTextFile(message_path))
    stored_json_message['attempts'].append({
        'message_id': message_id,
        'started': utime.get_sec1970(),
        'finished': None,
        'failed_consumers': [],
    })
    if not local_fs.WriteTextFile(message_path, jsn.dumps(stored_json_message)):
        return False
    return True


def unregister_delivery(queue_id, sequence_id, message_id, failed_consumers):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, sequence_id=sequence_id, message_id=message_id, failed_consumers=failed_consumers)
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    message_path = os.path.join(messages_dir, strng.to_text(sequence_id))
    stored_json_message = jsn.loads_text(local_fs.ReadTextFile(message_path))
    found_attempt_number = None
    for attempt_number in range(len(stored_json_message['attempts'])-1, -1, -1):
        if stored_json_message['attempts'][attempt_number]['message_id'] == message_id:
            found_attempt_number = attempt_number
            break
    if found_attempt_number is None:
        return False
    stored_json_message['attempts'][found_attempt_number].update({
        'finished': utime.get_sec1970(),
        'failed_consumers': failed_consumers,
    })
    if not local_fs.WriteTextFile(message_path, jsn.dumps(stored_json_message)):
        return False
    return True


def erase_message(queue_id, sequence_id):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, sequence_id=sequence_id)
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    message_path = os.path.join(messages_dir, strng.to_text(sequence_id))
    os.remove(message_path)
    return True


def get_messages_for_consumer(queue_id, consumer_id, consumer_last_sequence_id, max_messages_count=100):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id, consumer_last_sequence_id=consumer_last_sequence_id)
    queue_current_sequence_id = streams()[queue_id]['last_sequence_id']
    if consumer_last_sequence_id > queue_current_sequence_id:
        lg.warn('consumer %r is ahead of queue %r position: %d > %d' % (
            consumer_id, queue_id, consumer_last_sequence_id, queue_current_sequence_id, ))
        return []
    if consumer_last_sequence_id == queue_current_sequence_id:
        return []
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    all_stored_queue_messages = os.listdir(messages_dir)
    all_stored_queue_messages.sort(key=lambda i: int(i))
    result = []
    for sequence_id in all_stored_queue_messages:
        if consumer_last_sequence_id >= int(sequence_id):
            continue
        message_path = os.path.join(messages_dir, strng.to_text(sequence_id))
        try:
            stored_json_message = jsn.loads_text(local_fs.ReadTextFile(message_path))
        except:
            lg.exc()
            continue
        stored_json_message.pop('attempts')
        result.append(stored_json_message)
        if len(result) >= max_messages_count:
            break
    return result

#------------------------------------------------------------------------------

def close_all_streams():
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    list_queues = os.listdir(queues_dir)
    for queue_id in list_queues:
        close_stream(queue_id)
    return True


def load_streams():
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    loaded_queues = 0
    loaded_consumers = 0
    loaded_producers = 0
    loaded_messages = 0
    if not os.path.isdir(queues_dir):
        bpio._dirs_make(queues_dir)
    for queue_id in os.listdir(queues_dir):
        queue_dir = os.path.join(queues_dir, queue_id)
        messages_dir = os.path.join(queue_dir, 'messages')
        consumers_dir = os.path.join(queue_dir, 'consumers')
        producers_dir = os.path.join(queue_dir, 'producers')
        if queue_id not in streams():
            try:
                register_stream(queue_id)
            except:
                lg.exc()
                continue
            loaded_queues += 1
        last_sequence_id = -1
        all_stored_queue_messages = os.listdir(messages_dir)
        all_stored_queue_messages.sort(key=lambda i: int(i))
        for sequence_id in all_stored_queue_messages:
            streams()[queue_id]['messages'].append(sequence_id)
            if int(sequence_id) >= last_sequence_id:
                last_sequence_id = sequence_id
            loaded_messages += 1
        streams()[queue_id]['last_sequence_id'] = last_sequence_id
        for consumer_id in os.listdir(consumers_dir):
            if consumer_id in streams()[queue_id]['consumers']:
                lg.warn('consumer %r already exist in stream %r' % (consumer_id, queue_id, ))
                continue
            consumer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(consumers_dir, consumer_id)))
            streams()[queue_id]['consumers'][consumer_id] = consumer_info
            streams()[queue_id]['consumers'][consumer_id]['active'] = False
            loaded_consumers += 1
        for producer_id in os.listdir(producers_dir):
            if producer_id in streams()[queue_id]['producers']:
                lg.warn('producer %r already exist in stream %r' % (producer_id, queue_id, ))
                continue
            producer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(producers_dir, producer_id)))
            streams()[queue_id]['producers'][producer_id] = producer_info
            streams()[queue_id]['producers'][producer_id]['active'] = False
            loaded_producers += 1
    ret = {
        'queues': loaded_queues,
        'consumers': loaded_consumers,
        'producers': loaded_producers,
        'messages': loaded_messages,
    }
    if _Debug:
        lg.args(_DebugLevel, **ret)
    return ret

#------------------------------------------------------------------------------

def open_stream(queue_id):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id)
    if queue_id in streams():
        lg.warn('stream already exist: %r' % queue_id)
        return False
    register_stream(queue_id)
    save_stream(queue_id)
    return True


def close_stream(queue_id):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id)
    if queue_id not in streams():
        lg.warn('stream not found: %r' % queue_id)
        return False
    if streams()[queue_id]['active']:
        stop_stream(queue_id)
    erase_stream(queue_id)
    unregister_stream(queue_id)
    return True


def save_stream(queue_id):
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    consumers_dir = os.path.join(queue_dir, 'consumers')
    producers_dir = os.path.join(queue_dir, 'producers')
    stream_info = streams()[queue_id]
    bpio._dirs_make(messages_dir)
    bpio._dirs_make(consumers_dir)
    bpio._dirs_make(producers_dir)
    for consumer_id, consumer_info in stream_info['consumers'].items():
        local_fs.WriteTextFile(os.path.join(consumers_dir, consumer_id), jsn.dumps(consumer_info))
    for producer_id, producer_info in stream_info['producers'].items():
        local_fs.WriteTextFile(os.path.join(producers_dir, producer_id), jsn.dumps(producer_info))
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, queue_dir=queue_dir)
    return True


def erase_stream(queue_id):
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    erased_files = 0
    if os.path.isdir(queue_dir):
        erased_files += bpio.rmdir_recursive(queue_dir, ignore_errors=True)
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, queue_dir=queue_dir, erased_files=erased_files)
    return True

#------------------------------------------------------------------------------

def add_consumer(queue_id, consumer_id, consumer_info=None):
    if queue_id not in streams():
        return False
    if consumer_id in streams()[queue_id]['consumers']:
        return False
    if not consumer_info:
        consumer_info = {
            'active': False,
            'last_sequence_id': -1,
        }
    streams()[queue_id]['consumers'][consumer_id] = consumer_info
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id)
    save_consumer(queue_id, consumer_id)
    return True


def remove_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        return False
    streams()[queue_id]['consumers'].pop(consumer_id)
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id)
    erase_consumer(queue_id, consumer_id)
    return True


def save_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        return False
    if consumer_id in streams()[queue_id]['consumers']:
        return False
    consumer_info = streams()[queue_id]['consumers'][consumer_id]
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    consumers_dir = os.path.join(queue_dir, 'consumers')
    if not os.path.isdir(consumers_dir):
        bpio._dirs_make(consumers_dir)
    consumer_path = os.path.join(consumers_dir, consumer_id)
    ret = local_fs.WriteTextFile(consumer_path, jsn.dumps(consumer_info))
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id, consumer_path=consumer_path, ret=ret)
    return ret


def erase_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        return False
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    consumers_dir = os.path.join(queue_dir, 'consumers')
    consumer_path = os.path.join(consumers_dir, consumer_id)
    if not os.path.isfile(consumer_path):
        return False
    os.remove(consumer_path)
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id, consumer_path=consumer_path)
    return True

#------------------------------------------------------------------------------

def add_producer(queue_id, producer_id, producer_info=None):
    if queue_id not in streams():
        return False
    if producer_id in streams()[queue_id]['producers']:
        return False
    if not producer_info:
        producer_info = {
            'active': False,
            'last_sequence_id': -1,
        }
    streams()[queue_id]['producers'][producer_id] = producer_info
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, producer_id=producer_id)
    save_producer(queue_id, producer_id)
    return True


def remove_producer(queue_id, producer_id):
    if queue_id not in streams():
        return False
    if producer_id not in streams()[queue_id]['producers']:
        return False
    streams()[queue_id]['producers'].pop(producer_id)
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, producer_id=producer_id)
    erase_producer(queue_id, producer_id)
    return True


def save_producer(queue_id, producer_id):
    if queue_id not in streams():
        return False
    if producer_id in streams()[queue_id]['producers']:
        return False
    producer_info = streams()[queue_id]['producers'][producer_id]
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    producers_dir = os.path.join(queue_dir, 'producers')
    if not os.path.isdir(producers_dir):
        bpio._dirs_make(producers_dir)
    producer_path = os.path.join(producers_dir, producer_id)
    ret = local_fs.WriteTextFile(producer_path, jsn.dumps(producer_info))
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, producer_id=producer_id, producer_path=producer_path, ret=ret)
    return ret


def erase_producer(queue_id, producer_id):
    if queue_id not in streams():
        return False
    if producer_id not in streams()[queue_id]['producers']:
        return False
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    producers_dir = os.path.join(queue_dir, 'producers')
    producer_path = os.path.join(producers_dir, producer_id)
    if not os.path.isfile(producer_path):
        return False
    os.remove(producer_path)
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, producer_id=producer_id, producer_path=producer_path)
    return True

#------------------------------------------------------------------------------

def is_consumer_active(queue_id, consumer_id):
    if queue_id not in streams():
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        return False
    return streams()[queue_id]['consumers'][consumer_id]['active']


def start_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        return False
    if not p2p_queue.is_consumer_exists(consumer_id):
        p2p_queue.add_consumer(consumer_id)
    if not p2p_queue.is_callback_method_registered(consumer_id, on_consumer_notify):
        p2p_queue.add_callback_method(consumer_id, on_consumer_notify)
    if not p2p_queue.is_consumer_subscribed(consumer_id, queue_id):
        p2p_queue.subscribe_consumer(consumer_id, queue_id)
    streams()[queue_id]['consumers'][consumer_id]['active'] = True
    return True


def stop_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        return False
    if p2p_queue.is_callback_method_registered(consumer_id, on_consumer_notify):
        p2p_queue.remove_callback_method(consumer_id, on_consumer_notify)
    if p2p_queue.is_consumer_subscribed(consumer_id, queue_id):
        p2p_queue.unsubscribe_consumer(consumer_id, queue_id, remove_empty=True)
    streams()[queue_id]['consumers'][consumer_id]['active'] = False
    return True

#------------------------------------------------------------------------------

def is_producer_active(queue_id, producer_id):
    if queue_id not in streams():
        return False
    if producer_id not in streams()[queue_id]['producers']:
        return False
    return streams()[queue_id]['producers'][producer_id]['active']


def start_producer(queue_id, producer_id):
    if queue_id not in streams():
        return False
    if producer_id not in streams()[queue_id]['producers']:
        return False
    if not p2p_queue.is_producer_exist(producer_id):
        p2p_queue.add_producer(producer_id)
    if not p2p_queue.is_producer_connected(producer_id, queue_id):
        p2p_queue.connect_producer(producer_id, queue_id)
    streams()[queue_id]['producers'][producer_id]['active'] = True
    return True


def stop_producer(queue_id, producer_id):
    if queue_id not in streams():
        return False
    if producer_id not in streams()[queue_id]['producers']:
        return False
    if p2p_queue.is_producer_connected(producer_id, queue_id):
        p2p_queue.disconnect_producer(producer_id, queue_id, remove_empty=True)
    streams()[queue_id]['producers'][producer_id]['active'] = False
    return True

#------------------------------------------------------------------------------

def is_stream_active(queue_id):
    if queue_id not in streams():
        return False
    return streams()[queue_id]['active']


def start_stream(queue_id):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id)
    if not p2p_queue.is_queue_exist(queue_id):
        p2p_queue.open_queue(queue_id)
    for consumer_id in list(streams()[queue_id]['consumers'].keys()):
        start_consumer(queue_id, consumer_id)
    for producer_id in list(streams()[queue_id]['producers'].keys()):
        start_producer(queue_id, producer_id)
    streams()[queue_id]['active'] = True
    p2p_queue.touch_queues()
    return True


def stop_stream(queue_id):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id)
    for producer_id in list(streams()[queue_id]['producers'].keys()):
        stop_producer(queue_id, producer_id)
    for consumer_id in list(streams()[queue_id]['consumers'].keys()):
        stop_consumer(queue_id, consumer_id)
    p2p_queue.close_queue(queue_id)
    streams()[queue_id]['active'] = False
    p2p_queue.touch_queues()
    return True


def start_all_streams():
    for queue_id, one_stream in streams().items():
        if not one_stream['active']:
            start_stream(queue_id)


def stop_all_streams():
    for queue_id, one_stream in streams().items():
        if one_stream['active']:
            stop_stream(queue_id)

#------------------------------------------------------------------------------

def A(event=None, *args, **kwargs):
    """
    Access method to interact with `message_peddler()` machine.
    """
    global _MessagePeddler
    if event is None:
        return _MessagePeddler
    if _MessagePeddler is None:
        _MessagePeddler = MessagePeddler(
            name='message_peddler',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _MessagePeddler.automat(event, *args, **kwargs)
    return _MessagePeddler

#------------------------------------------------------------------------------

class MessagePeddler(automat.Automat):
    """
    This class implements all the functionality of ``message_peddler()`` state machine.
    """

    def __init__(self, name, state, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `message_peddler()` state machine.
        """
        super(MessagePeddler, self).__init__(
            name=name,
            state=state,
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `message_peddler()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `message_peddler()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `message_peddler()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'LOAD'
                self.doInit(*args, **kwargs)
                self.doLoadKnownQueues(*args, **kwargs)
        #---LOAD---
        elif self.state == 'LOAD':
            if event == 'queues-loaded':
                self.state = 'READY'
                self.doRunQueues(*args, **kwargs)
        #---READY---
        elif self.state == 'READY':
            if event == 'stop':
                self.state = 'CLOSED'
                self.doStopQueues(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'queue-connect':
                self.doStartJoinQueue(*args, **kwargs)
            elif event == 'queue-disconnect':
                self.doLeaveStopQueue(*args, **kwargs)
            elif event == 'queue-read':
                self.doConsumeMessages(*args, **kwargs)
            elif event == 'message-pushed':
                self.doProcessMessage(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        message.consume_messages(
            consumer_id=self.name,
            callback=on_consume_queue_messages,
            direction='incoming',
            message_types=['queue_message', ],
        )

    def doLoadKnownQueues(self, *args, **kwargs):
        """
        Action method.
        """
        load_streams()
        reactor.callLater(0, self.automat, 'queues-loaded')  # @UndefinedVariable

    def doRunQueues(self, *args, **kwargs):
        """
        Action method.
        """
        p2p_queue.add_message_processed_callback(on_message_processed)
        start_all_streams()

    def doStopQueues(self, *args, **kwargs):
        """
        Action method.
        """
        stop_all_streams()
        p2p_queue.remove_message_processed_callback(on_message_processed)

    def doStartJoinQueue(self, *args, **kwargs):
        """
        Action method.
        """
        group_key_info = kwargs['group_key']
        result_defer = kwargs['result_defer']
        request_packet = kwargs['request_packet']
        if _Debug:
            lg.args(_DebugLevel, request_packet=request_packet)
        if not my_keys.verify_key_info_signature(group_key_info):
            p2p_service.SendFail(request_packet, 'group key verification failed')
            result_defer.callback(False)
            return
        try:
            group_key_id, key_object = my_keys.read_key_info(group_key_info)
        except Exception as exc:
            p2p_service.SendFail(request_packet, strng.to_text(exc))
            result_defer.callback(False)
            return
        group_key_alias, group_creator_idurl = my_keys.split_key_id(group_key_id)
        if not group_key_alias or not group_creator_idurl:
            lg.warn('wrong group_key_id')
            p2p_service.SendFail(request_packet, 'wrong group_key_id')
            result_defer.callback(False)
            return
        if my_keys.is_key_registered(group_key_id):
            if my_keys.is_key_private(group_key_id):
                p2p_service.SendFail(request_packet, 'private key already registered')
                result_defer.callback(False)
                return
            if my_keys.get_public_key_raw(group_key_id) != key_object.toPublicString():
                p2p_service.SendFail(request_packet, 'another public key already registered')
                result_defer.callback(False)
                return
        else:
            if not my_keys.register_key(group_key_id, key_object, group_key_info.get('label', '')):
                p2p_service.SendFail(request_packet, 'key register failed')
                result_defer.callback(False)
                return
        queue_id = kwargs['queue_id']
        consumer_id = kwargs['consumer_id']
        producer_id = kwargs['producer_id']
        position = kwargs.get('position', -1)
        if id_url.is_cached(group_creator_idurl):
            self._do_check_create_queue_keeper(group_creator_idurl, request_packet, queue_id, consumer_id, producer_id, position, result_defer)
            return
        caching_story = identitycache.immediatelyCaching(group_creator_idurl)
        caching_story.addCallback(lambda _: self._do_check_create_queue_keeper(
            group_creator_idurl, request_packet, queue_id, consumer_id, producer_id, position, result_defer))
        if _Debug:
            caching_story.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='message_peddler.doStartJoinQueue')
        caching_story.addErrback(self._on_group_creator_idurl_cache_failed, request_packet, result_defer)

    def doLeaveStopQueue(self, *args, **kwargs):
        """
        Action method.
        """
        group_key_info = kwargs['group_key']
        queue_id = kwargs['queue_id']
        consumer_id = kwargs['consumer_id']
        producer_id = kwargs['producer_id']
        request_packet = kwargs['request_packet']
        result_defer = kwargs['result_defer']
        if _Debug:
            lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id, producer_id=producer_id, request_packet=request_packet)
        if queue_id not in streams():
            p2p_service.SendFail(request_packet, 'queue %r not registered' % queue_id)
            result_defer.callback(True)
            return
        if not my_keys.verify_key_info_signature(group_key_info):
            p2p_service.SendFail(request_packet, 'group key verification failed')
            result_defer.callback(False)
            return
        try:
            group_key_id, _ = my_keys.read_key_info(group_key_info)
        except Exception as exc:
            p2p_service.SendFail(request_packet, strng.to_text(exc))
            result_defer.callback(False)
            return
        group_key_alias, group_creator_idurl = my_keys.split_key_id(group_key_id)
        if not group_key_alias or not group_creator_idurl:
            lg.warn('wrong group_key_id')
            p2p_service.SendFail(request_packet, 'wrong group_key_id')
            result_defer.callback(False)
            return
        if consumer_id:
            if not stop_consumer(queue_id, consumer_id):
                p2p_service.SendFail(request_packet, 'failed to stop consumer %r for queue %r' % (consumer_id, queue_id))
                result_defer.callback(False)
                return
            if not remove_consumer(queue_id, consumer_id):
                p2p_service.SendFail(request_packet, 'consumer %r is not registered for queue %r' % (consumer_id, queue_id))
                result_defer.callback(False)
                return
        if producer_id:
            if not stop_producer(queue_id, producer_id):
                p2p_service.SendFail(request_packet, 'failed to stop producer %r for queue %r' % (producer_id, queue_id))
                result_defer.callback(False)
                return
            if not remove_producer(queue_id, producer_id):
                p2p_service.SendFail(request_packet, 'producer %r is not registered for queue %r' % (producer_id, queue_id))
                result_defer.callback(False)
                return
        if not streams()[queue_id]['consumers'] and not streams()[queue_id]['producers']:
            lg.info('no consumers and no producers left, closing queue %r' % queue_id)
            stop_stream(queue_id)
            close_stream(queue_id)
        customer_idurl = global_id.GetGlobalQueueOwnerIDURL(queue_id)
        if customer_idurl in customers():
            if len(customers()[customer_idurl]) == 0:
                lg.info('no streams left for %r, clean up queue_keeper()' % customer_idurl)
                queue_keeper.close(customer_idurl)
                if my_keys.is_key_registered(group_key_id):
                    lg.info('clean up group key %r' % group_key_id)
                    my_keys.erase_key(group_key_id)
        p2p_service.SendAck(request_packet, 'accepted')
        result_defer.callback(True)

    def doConsumeMessages(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_send_past_messages(**kwargs)

    def doProcessMessage(self, *args, **kwargs):
        """
        Action method.
        """
        

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _MessagePeddler
        message.clear_consumer_callbacks(self.name)
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        self.destroy()
        _MessagePeddler = None

    def _do_send_past_messages(self, queue_id, consumer_id, consumer_last_sequence_id):
        list_messages = get_messages_for_consumer(queue_id, consumer_id, consumer_last_sequence_id)
        message.send_message(
            json_data={
                'items': list_messages,
                'last_sequence_id': get_latest_sequence_id(queue_id),
            },
            recipient_global_id=consumer_id,
            packet_id='queue_%s_%s' % (queue_id, packetid.UniqueID(), ),
            skip_handshake=True,
            fire_callbacks=False,
        )

    def _do_close_streams(self, queues_list):
        for queue_id in queues_list:
            if queue_id not in streams():
                continue
            if streams()[queue_id]['active']:
                for consumer_id in streams()[queue_id]['consumers']:
                    if consumer_id:
                        if not stop_consumer(queue_id, consumer_id):
                            lg.warn('failed to stop consumer %r in for queue %r' % (consumer_id, queue_id, ))
                        if not remove_consumer(queue_id, consumer_id):
                            lg.warn('consumer %r is not registered for queue %r' % (consumer_id, queue_id, ))
                for producer_id in streams()[queue_id]['producers']:
                    if producer_id:
                        if not stop_producer(queue_id, producer_id):
                            lg.warn('failed to stop producer %r in for queue %r' % (producer_id, queue_id, ))
                        if not remove_producer(queue_id, producer_id):
                            lg.warn('producer %r is not registered for queue %r' % (producer_id, queue_id, ))
            stop_stream(queue_id)
            close_stream(queue_id)
            customer_idurl = global_id.GetGlobalQueueOwnerIDURL(queue_id)
            if customer_idurl in customers():
                if len(customers()[customer_idurl]) == 0:
                    lg.info('no streams left for %r, clean up queue_keeper()' % customer_idurl)
                    queue_keeper.close(customer_idurl)
                    group_key_id = global_id.GetGlobalQueueKeyID(queue_id)
                    if my_keys.is_key_registered(group_key_id):
                        lg.info('clean up group key %r' % group_key_id)
                        my_keys.erase_key(group_key_id)


    def _do_check_create_queue_keeper(self, customer_idurl, request_packet, queue_id, consumer_id, producer_id, position, result_defer):
        if _Debug:
            lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id, producer_id=producer_id, position=position)
        queue_keeper_result = Deferred()
        queue_keeper_result.addCallback(
            self._on_queue_keeper_connect_result,
            queue_id=queue_id,
            consumer_id=consumer_id,
            producer_id=producer_id,
            request_packet=request_packet,
            result_defer=result_defer,
        )
        if _Debug:
            queue_keeper_result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='message_peddler.doStartJoinQueue')
        qk = queue_keeper.check_create(customer_idurl=customer_idurl)
        qk.automat(
            'connect',
            queue_id=queue_id,
            desired_position=position,
            result_callback=queue_keeper_result,
        )

    def _on_queue_keeper_connect_result(self, result, queue_id, consumer_id, producer_id, request_packet, result_defer):
        if _Debug:
            lg.args(_DebugLevel, result=result, queue_id=queue_id, consumer_id=consumer_id, producer_id=producer_id, request_packet=request_packet)
        if not result:
            lg.err('queue keeper failed to connect')
            return None
        if queue_id not in streams():
            open_stream(queue_id)
        if not is_stream_active(queue_id):
            start_stream(queue_id)
        if consumer_id:
            add_consumer(queue_id, consumer_id)
            start_consumer(queue_id, consumer_id)
        if producer_id:
            add_producer(queue_id, producer_id)
            start_producer(queue_id, producer_id)
        p2p_service.SendAck(request_packet, 'accepted')
        result_defer.callback(True)
        return None

    def _on_identity_url_changed(self, evt):
        if my_id.getIDURL().to_bin() in [evt.data['new_idurl'], evt.data['old_idurl']]:
            return
        old_idurl = evt.data['old_idurl']
        new_id = global_id.idurl2glob(evt.data['new_idurl'])
        queues_to_be_closed = []
        if old_idurl in customers().keys():
            for queue_id in customers()[old_idurl]:
                queues_to_be_closed.append(queue_id)
        self._do_close_streams(queues_to_be_closed)
        for queue_id in streams().keys():
            rotated_consumers = []
            rotated_producers = []
            for cur_consumer_id in streams()[queue_id]['consumers']:
                consumer_idurl = global_id.glob2idurl(cur_consumer_id)
                if consumer_idurl == old_idurl:
                    rotated_consumers.append((cur_consumer_id, new_id, ))
            for cur_producer_id in streams()[queue_id]['producers']:
                producer_idurl = global_id.glob2idurl(cur_producer_id)
                if producer_idurl == old_idurl:
                    rotated_producers.append((cur_producer_id, new_id, ))
            for old_consumer_id, new_consumer_id in rotated_consumers:
                old_consumer_info = streams()[queue_id]['consumers'][old_consumer_id]
                if old_consumer_info['active']:
                    stop_consumer(queue_id, old_consumer_id)
                remove_consumer(queue_id, old_consumer_id)
                add_consumer(queue_id, new_consumer_id, consumer_info=old_consumer_info)
                if old_consumer_info['active']:
                    start_consumer(queue_id, new_consumer_id)
            for old_producer_id, new_producer_id in rotated_producers:
                old_producer_info = streams()[queue_id]['producers'][old_producer_id]
                if old_producer_info['active']:
                    stop_producer(queue_id, old_producer_id)
                remove_producer(queue_id, old_producer_id)
                add_producer(queue_id, new_producer_id, producer_info=old_producer_info)
                if old_producer_info['active']:
                    start_producer(queue_id, new_producer_id)

    def _on_group_creator_idurl_cache_failed(self, err, request_packet, result_defer):
        p2p_service.SendFail(request_packet, 'group creator idurl cache failed')
        result_defer.callback(False)
        return None
