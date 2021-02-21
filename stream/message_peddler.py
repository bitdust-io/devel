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

from twisted.internet.defer import Deferred, DeferredList

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from crypt import my_keys

from lib import jsn
from lib import strng
from lib import utime
from lib import packetid
from lib import serialization

from contacts import identitycache

from system import bpio
from system import local_fs
from system import tmpfile

from main import settings
from main import config
from main import events

from p2p import p2p_service

from access import groups

from storage import archive_writer

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
        raise Exception('customer idurl %r is not cached yet' % customer_idurl)
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
        'archive': [],
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
        raise Exception('customer idurl %r is not cached yet' % customer_idurl)
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
    if not A():
        lg.warn('message_peddler() not started yet')
        return False
    if not A().state == 'READY':
        lg.warn('message_peddler() is not ready yet')
        return False
    for json_message in json_messages:
        try:
            msg_type = json_message.get('type', '')
            msg_direction = json_message['dir']
            packet_id = json_message['packet_id']
            from_idurl = json_message['owner_idurl']
            to_user = json_message['to']
            msg_data = json_message['data']
            msg_action = msg_data.get('action', 'read')
        except:
            lg.exc()
            continue
        if msg_direction != 'incoming':
            continue
        if to_user != my_id.getID():
            continue
        if msg_type not in ['queue_message', 'queue_message_replica', ]:
            continue
        if msg_action not in ['produce', 'consume', ]:
            continue
        queue_id = msg_data.get('queue_id')
        if not queue_id:
            continue
        if msg_type == 'queue_message':
            if queue_id not in streams():
                lg.warn('skipped incoming queue_message, queue %r is not registered' % queue_id)
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'queue ID not registered')
                continue
            if not streams()[queue_id]['active']:
                lg.warn('skipped incoming queue_message, queue %r is not active' % queue_id)
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'queue is not active')
                continue
        my_queue_id = queue_id
        if msg_type == 'queue_message_replica':
            queue_alias, owner_id, _ = global_id.SplitGlobalQueueID(queue_id)
            my_queue_id = global_id.MakeGlobalQueueID(queue_alias, owner_id, my_id.getID())
            if my_queue_id not in streams():
                lg.warn('skipped incoming queue_message_replica, queue %r is not registered' % my_queue_id)
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'queue ID not registered')
                continue
            if not streams()[my_queue_id]['active']:
                lg.warn('skipped incoming queue_message_replica, queue %r is not active' % my_queue_id)
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'queue is not active')
                continue
        if msg_action == 'consume':
            # request from queue_member() to catch up unread messages from the queue
            consumer_id = msg_data.get('consumer_id')
            if consumer_id not in streams()[queue_id]['consumers']:
                lg.warn('skipped incoming "queue-read" request, consumer %r is not registered for queue %r' % (consumer_id, queue_id, ))
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'consumer is not registered')
                continue
            if not streams()[queue_id]['consumers'][consumer_id]['active']:
                lg.warn('skipped incoming "queue-read" request, consumer %r is not active in queue %r' % (consumer_id, queue_id, ))
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'consumer is not active')
                continue
            consumer_last_sequence_id = int(msg_data.get('last_sequence_id', -1))
            if _Debug:
                lg.args(_DebugLevel, event='queue-read', queue_id=queue_id, consumer_id=consumer_id, consumer_last_sequence_id=consumer_last_sequence_id)
            A('queue-read', queue_id=queue_id, consumer_id=consumer_id, consumer_last_sequence_id=consumer_last_sequence_id)
            p2p_service.SendAckNoRequest(from_idurl, packet_id)
            continue
        if msg_action == 'produce':
            try:
                payload = msg_data['payload']
                created = msg_data['created']
                producer_id = msg_data['producer_id']
            except:
                lg.exc()
                continue
            if msg_type == 'queue_message':
                if producer_id not in streams()[queue_id]['producers']:
                    lg.warn('skipped incoming queue_message, producer %r is not registered for queue %r' % (producer_id, queue_id, ))
                    p2p_service.SendFailNoRequest(from_idurl, packet_id, 'producer is not registered')
                    continue
                if not streams()[queue_id]['producers'][producer_id]['active']:
                    lg.warn('skipped incoming queue_message, producer %r is not active in queue %r' % (producer_id, queue_id, ))
                    p2p_service.SendFailNoRequest(from_idurl, packet_id, 'producer is not active')
                    continue
            if msg_type == 'queue_message_replica':
                if producer_id not in streams()[my_queue_id]['producers']:
                    lg.warn('skipped incoming queue_message_replica, producer %r is not registered for queue %r' % (producer_id, my_queue_id, ))
                    p2p_service.SendFailNoRequest(from_idurl, packet_id, 'producer is not registered')
                    continue
                if not streams()[my_queue_id]['producers'][producer_id]['active']:
                    lg.warn('skipped incoming queue_message_replica, producer %r is not active in queue %r' % (producer_id, my_queue_id, ))
                    p2p_service.SendFailNoRequest(from_idurl, packet_id, 'producer is not active')
                    continue
            if msg_type == 'queue_message_replica':
                # incoming message replica from another message_peddler() to store locally in case brokers needs to be rotated
                do_store_message_replica(from_idurl, packet_id, my_queue_id, producer_id, payload, created)
                continue
            try:
                known_brokers = {int(k): v for k, v in msg_data['brokers'].items()}
            except:
                lg.exc()
                continue
            # incoming message from queue_member() to push new message to the queue and deliver to all other group members
            received += 1
            if not do_push_message(from_idurl, packet_id, queue_id, producer_id, payload, created, known_brokers):
                continue
            pushed += 1
            continue
        raise Exception('unexpected message "action": %r' % msg_action)
    if received > pushed:
        lg.warn('some of the received messages was not pushed to the queue %r' % queue_id)
    return True


def do_push_message(from_idurl, packet_id, queue_id, producer_id, payload, created, known_brokers):
    new_sequence_id = increment_sequence_id(queue_id)
    streams()[queue_id]['messages'].append(new_sequence_id)
    queued_json_message = store_message(queue_id, new_sequence_id, producer_id, payload, created)
    if not queued_json_message:
        return False
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
        return False
    register_delivery(queue_id, new_sequence_id, new_message.message_id)
    A('message-pushed', new_message, known_brokers=known_brokers)
    p2p_service.SendAckNoRequest(from_idurl, packet_id)
    return True


def do_store_message_replica(from_idurl, packet_id, queue_id, producer_id, payload, created):
    try:
        new_sequence_id = payload['sequence_id']
    except:
        lg.exc()
        return False
    set_latest_sequence_id(queue_id, new_sequence_id)
    streams()[queue_id]['messages'].append(new_sequence_id)
    queued_json_message = store_message(queue_id, new_sequence_id, producer_id, payload, created)
    if not queued_json_message:
        lg.err('failed to store message replica %r in %r from %r via broker %r' % (packet_id, queue_id, producer_id, from_idurl, ))
        return False
    if _Debug:
        lg.out(_DebugLevel, '<<< REPLICA <<<    into %r by %r at sequence %d via %r' % (
            queue_id, producer_id, new_sequence_id, from_idurl, ))
    p2p_service.SendAckNoRequest(from_idurl, packet_id)
    return True

#------------------------------------------------------------------------------

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
        update_processed_message(processed_message.queue_id, sequence_id)
        streams()[processed_message.queue_id]['archive'].append(sequence_id)
        streams()[processed_message.queue_id]['messages'].remove(sequence_id)
        if _Debug:
            lg.out(_DebugLevel, '>>> PULL >>>    from %r at sequence %d with success count %d' % (
                processed_message.queue_id, sequence_id, len(processed_message.success_notifications), ))
    return True


def on_consumer_notify(message_info):
    payload = message_info['payload']
    consumer_id = message_info['consumer_id']
    queue_id = message_info['queue_id']
    packet_id = packetid.MakeQueueMessagePacketID(queue_id, packetid.UniqueID())
    sequence_id = payload['sequence_id']
    last_sequence_id = get_latest_sequence_id(queue_id)
    producer_id = payload['producer_id']
    if _Debug:
        lg.args(_DebugLevel, producer_id=producer_id, consumer_id=consumer_id, queue_id=queue_id,
                sequence_id=sequence_id, last_sequence_id=last_sequence_id)
    ret = message.send_message(
        json_data={
            'msg_type': 'queue_message',
            'action': 'read',
            'created': utime.get_sec1970(),
            'items': [{
                'sequence_id': sequence_id,
                'created': payload['created'],
                'producer_id': producer_id,
                'payload': payload['payload'],
            }, ],
            'last_sequence_id': last_sequence_id,
        },
        recipient_global_id=my_keys.make_key_id(alias='master', creator_glob_id=consumer_id),
        packet_id=packet_id,
        message_ack_timeout=25,
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


def set_latest_sequence_id(queue_id, new_sequence_id):
    new_sequence_id = int(new_sequence_id)
    current_sequence_id = int(streams()[queue_id]['last_sequence_id'])
    streams()[queue_id]['last_sequence_id'] = new_sequence_id
    if new_sequence_id == current_sequence_id + 1: 
        if _Debug:
            lg.args(_DebugLevel, queue_id=queue_id, current_sequence_id=current_sequence_id, new_sequence_id=new_sequence_id)
    else:
        lg.warn('message sequence_id update is not consistent in %r : %r -> %r' % (
            queue_id, current_sequence_id, new_sequence_id, ))
    return new_sequence_id


def increment_sequence_id(queue_id):
    last_sequence_id = int(streams()[queue_id]['last_sequence_id'])
    new_sequence_id = last_sequence_id + 1
    streams()[queue_id]['last_sequence_id'] = new_sequence_id
    return new_sequence_id

#------------------------------------------------------------------------------

def store_message(queue_id, sequence_id, producer_id, payload, created, processed=None):
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
        'processed': None,
    }
    if processed:
        stored_json_message['attempts'].append({
            'message_id': payload['message_id'],
            'started': None,
            'finished': utime.get_sec1970(),
            'failed_consumers': [],
        })
        stored_json_message['processed'] = processed
    if not local_fs.WriteTextFile(message_path, jsn.dumps(stored_json_message)):
        lg.err('failed to store message %d in %r from %r' % (sequence_id, queue_id, producer_id, ))
        return None
    if _Debug:
        lg.args(_DebugLevel, sequence_id=sequence_id, producer_id=producer_id, queue_id=queue_id)
    return stored_json_message


def update_processed_message(queue_id, sequence_id):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, sequence_id=sequence_id)
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    message_path = os.path.join(messages_dir, strng.to_text(sequence_id))
    stored_json_message = jsn.loads_text(local_fs.ReadTextFile(message_path))
    if not stored_json_message:
        lg.err('failed reading message %d from %r' % (sequence_id, queue_id, ))
        return False
    stored_json_message['processed'] = utime.get_sec1970()
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
    try:
        os.remove(message_path)
    except:
        lg.exc()
        return False
    return True


def read_messages(queue_id, sequence_id_list=[]):
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    if not sequence_id_list:
        sequence_id_list = sorted([int(sequence_id) for sequence_id in os.listdir(messages_dir)])
    result = []
    for sequence_id in sequence_id_list:
        message_path = os.path.join(messages_dir, strng.to_text(sequence_id))
        stored_json_message = jsn.loads_text(local_fs.ReadTextFile(message_path))
        if not stored_json_message:
            lg.err('failed reading message %d from %r' % (sequence_id, queue_id, ))
            continue
        stored_json_message.pop('attempts')
        result.append(stored_json_message)
    return result


def get_messages_for_consumer(queue_id, consumer_id, consumer_last_sequence_id, max_messages_count=100):
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
        if not stored_json_message:
            lg.err('failed reading message %d from %r' % (sequence_id, queue_id, ))
            continue
        stored_json_message.pop('attempts')
        result.append(stored_json_message)
        if len(result) >= max_messages_count:
            break
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id,
                consumer_last_sequence_id=consumer_last_sequence_id, result=len(result))
    return result

#------------------------------------------------------------------------------

def register_delivery(queue_id, sequence_id, message_id):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, sequence_id=sequence_id, message_id=message_id)
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    message_path = os.path.join(messages_dir, strng.to_text(sequence_id))
    stored_json_message = jsn.loads_text(local_fs.ReadTextFile(message_path))
    if not stored_json_message:
        lg.err('failed reading message %d from %r' % (sequence_id, queue_id, ))
        return False
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
    if not stored_json_message:
        lg.err('failed reading message %d from %r' % (sequence_id, queue_id, ))
        return False
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

#------------------------------------------------------------------------------

def close_all_streams():
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    list_queues = os.listdir(queues_dir)
    for queue_id in list_queues:
        close_stream(queue_id)
    return True

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
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, typ=type(queue_id))
    if not os.path.isdir(messages_dir):
        bpio._dirs_make(messages_dir)
    if not os.path.isdir(consumers_dir):
        bpio._dirs_make(consumers_dir)
    if not os.path.isdir(producers_dir):
        bpio._dirs_make(producers_dir)
    for consumer_id, consumer_info in stream_info['consumers'].items():
        local_fs.WriteTextFile(os.path.join(consumers_dir, consumer_id), jsn.dumps(consumer_info))
    for producer_id, producer_info in stream_info['producers'].items():
        local_fs.WriteTextFile(os.path.join(producers_dir, producer_id), jsn.dumps(producer_info))
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
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id, consumer_info=consumer_info)
    if not save_consumer(queue_id, consumer_id):
        raise Exception('failed to save consumer info')
    return True


def remove_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        return False
    streams()[queue_id]['consumers'].pop(consumer_id)
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id)
    if not erase_consumer(queue_id, consumer_id):
        raise Exception('failed to erase consumer info')
    return True


def save_consumer(queue_id, consumer_id):
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
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id, ret=ret)
    return ret


def erase_consumer(queue_id, consumer_id):
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    consumers_dir = os.path.join(queue_dir, 'consumers')
    consumer_path = os.path.join(consumers_dir, consumer_id)
    if not os.path.isfile(consumer_path):
        return False
    try:
        os.remove(consumer_path)
    except:
        lg.exc()
        return False
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
        lg.args(_DebugLevel, queue_id=queue_id, producer_id=producer_id, producer_info=producer_info)
    if not save_producer(queue_id, producer_id):
        raise Exception('failed to store producer info')
    return True


def remove_producer(queue_id, producer_id):
    if queue_id not in streams():
        return False
    if producer_id not in streams()[queue_id]['producers']:
        return False
    streams()[queue_id]['producers'].pop(producer_id)
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, producer_id=producer_id)
    if not erase_producer(queue_id, producer_id):
        raise Exception('failed to erase producer info')
    return True


def save_producer(queue_id, producer_id):
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
        lg.args(_DebugLevel, queue_id=queue_id, producer_id=producer_id, ret=ret)
    return ret


def erase_producer(queue_id, producer_id):
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    producers_dir = os.path.join(queue_dir, 'producers')
    producer_path = os.path.join(producers_dir, producer_id)
    if not os.path.isfile(producer_path):
        return False
    try:
        os.remove(producer_path)
    except:
        lg.exc()
        return False
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, producer_id=producer_id)
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
        lg.warn('queue % is not active, can not start consumer %r' % (queue_id, consumer_id, ))
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        lg.warn('not able to start consumer %r because it was not added to the queue %r' % (consumer_id, queue_id, ))
        return False
    if not p2p_queue.is_consumer_exists(consumer_id):
        p2p_queue.add_consumer(consumer_id)
    if not p2p_queue.is_callback_method_registered(consumer_id, on_consumer_notify):
        p2p_queue.add_callback_method(consumer_id, on_consumer_notify)
    if not p2p_queue.is_consumer_subscribed(consumer_id, queue_id):
        p2p_queue.subscribe_consumer(consumer_id, queue_id)
    streams()[queue_id]['consumers'][consumer_id]['active'] = True
    save_consumer(queue_id, consumer_id)
    lg.info('consumer %r started in the queue %r' % (consumer_id, queue_id, ))
    return True


def stop_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        lg.warn('queue % is not active, can not stop consumer %r' % (queue_id, consumer_id, ))
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        lg.warn('not able to stop consumer %r because it was not added to the queue %r' % (consumer_id, queue_id, ))
        return False
    if p2p_queue.is_callback_method_registered(consumer_id, on_consumer_notify):
        p2p_queue.remove_callback_method(consumer_id, on_consumer_notify)
    if p2p_queue.is_consumer_subscribed(consumer_id, queue_id):
        p2p_queue.unsubscribe_consumer(consumer_id, queue_id, remove_empty=True)
    streams()[queue_id]['consumers'][consumer_id]['active'] = False
    save_consumer(queue_id, consumer_id)
    lg.info('consumer %r stopped in the queue %r' % (consumer_id, queue_id, ))
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
        lg.warn('queue % is not active, can not start producer %r' % (queue_id, producer_id, ))
        return False
    if producer_id not in streams()[queue_id]['producers']:
        lg.warn('not able to start producer %r because it was not added to the queue %r' % (producer_id, queue_id, ))
        return False
    if not p2p_queue.is_producer_exist(producer_id):
        p2p_queue.add_producer(producer_id)
    if not p2p_queue.is_producer_connected(producer_id, queue_id):
        p2p_queue.connect_producer(producer_id, queue_id)
    streams()[queue_id]['producers'][producer_id]['active'] = True
    save_producer(queue_id, producer_id)
    lg.info('producer %r started in the queue %r' % (producer_id, queue_id, ))
    return True


def stop_producer(queue_id, producer_id):
    if queue_id not in streams():
        lg.warn('queue % is not active, can not stop producer %r' % (queue_id, producer_id, ))
        return False
    if producer_id not in streams()[queue_id]['producers']:
        lg.warn('not able to stop producer %r because it was not added to the queue %r' % (producer_id, queue_id, ))
        return False
    if p2p_queue.is_producer_connected(producer_id, queue_id):
        p2p_queue.disconnect_producer(producer_id, queue_id, remove_empty=True)
    streams()[queue_id]['producers'][producer_id]['active'] = False
    save_producer(queue_id, producer_id)
    lg.info('producer %r stopped in the queue %r' % (producer_id, queue_id, ))
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
        self.archive_chunk_size = config.conf().getInt('services/message-broker/archive-chunk-size')
        self.archive_in_progress = False
        events.add_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        message.consume_messages(
            consumer_callback_id=self.name,
            callback=on_consume_queue_messages,
            direction='incoming',
            message_types=['queue_message', 'queue_message_replica', ],
        )

    def doLoadKnownQueues(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_cache_known_customers()

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
        last_sequence_id = kwargs['last_sequence_id']
        archive_folder_path = kwargs['archive_folder_path']
        if _Debug:
            lg.args(_DebugLevel, request_packet=request_packet)
        if not my_keys.verify_key_info_signature(group_key_info):
            p2p_service.SendFail(request_packet, 'group key verification failed')
            result_defer.callback(False)
            return
        try:
            group_key_id, key_object = my_keys.read_key_info(group_key_info)
        except:
            lg.exc()
            p2p_service.SendFail(request_packet, 'failed reading key info')
            result_defer.callback(False)
            return
        group_key_alias, group_creator_idurl = my_keys.split_key_id(group_key_id)
        if not group_key_alias or not group_creator_idurl:
            lg.warn('wrong group_key_id: %r' % group_key_id)
            p2p_service.SendFail(request_packet, 'invalid group_key_id')
            result_defer.callback(False)
            return
        if my_keys.is_key_registered(group_key_id):
            if my_keys.is_key_private(group_key_id):
                p2p_service.SendFail(request_packet, 'private key already registered')
                result_defer.callback(False)
                return
            if my_keys.get_public_key_raw(group_key_id) != key_object.toPublicString():
                my_keys.erase_key(group_key_id)
                if not my_keys.register_key(group_key_id, key_object, group_key_info.get('label', '')):
                    p2p_service.SendFail(request_packet, 'key register failed')
                    result_defer.callback(False)
                    return
                # p2p_service.SendFail(request_packet, 'another public key already registered with same id')
                # result_defer.callback(False)
                # return
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
            self._do_check_create_queue_keeper(
                group_creator_idurl, request_packet, queue_id, consumer_id, producer_id,
                position, last_sequence_id, archive_folder_path, result_defer)
            return
        caching_story = identitycache.immediatelyCaching(group_creator_idurl)
        caching_story.addCallback(lambda _: self._do_check_create_queue_keeper(
            group_creator_idurl, request_packet, queue_id, consumer_id, producer_id,
            position, last_sequence_id, archive_folder_path, result_defer))
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
            p2p_service.SendFail(request_packet, 'group key verification failed while stopping consumer or producer')
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
            # TODO: need to find a better way to keep data for offline groups
            # currently it will lead to a resources leakage - need to clean up queues which are not in use for a long time
            if False:
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
        queue_id = kwargs['queue_id']
        consumer_id = kwargs['consumer_id']
        consumer_last_sequence_id = kwargs['consumer_last_sequence_id']
        queue_current_sequence_id = get_latest_sequence_id(queue_id)
        if consumer_last_sequence_id > queue_current_sequence_id:
            lg.warn('consumer %r is ahead of queue %r position: %d > %d' % (
                consumer_id, queue_id, consumer_last_sequence_id, queue_current_sequence_id, ))
        list_messages = []
        if consumer_last_sequence_id < queue_current_sequence_id:
            list_messages = get_messages_for_consumer(queue_id, consumer_id, consumer_last_sequence_id)
        self._do_send_past_messages(queue_id, consumer_id, list_messages)

    def doProcessMessage(self, *args, **kwargs):
        """
        Action method.
        """
        message_in = args[0]
        self._do_replicate_message(message_in, known_brokers=kwargs.get('known_brokers', {}))
        self._do_archive_other_messages(message_in.queue_id)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _MessagePeddler
        message.clear_consumer_callbacks(self.name)
        events.remove_subscriber(self._on_identity_url_changed, 'identity-url-changed')
        self.destroy()
        _MessagePeddler = None

    def _do_cache_known_customers(self):
        service_dir = settings.ServiceDir('service_message_broker')
        queues_dir = os.path.join(service_dir, 'queues')
        if not os.path.isdir(queues_dir):
            bpio._dirs_make(queues_dir)
        to_be_cached = []
        for queue_id in os.listdir(queues_dir):
            queue_info = global_id.ParseGlobalQueueID(queue_id)
            customer_idurl = global_id.glob2idurl(queue_info['owner_id'])
            if not customer_idurl:
                lg.err('unknown customer IDURL for queue: %r' % queue_id)
                continue
            if not id_url.is_cached(customer_idurl):
                to_be_cached.append(customer_idurl)
        if not to_be_cached:
            return self._do_load_streams()
        d = identitycache.start_multiple(to_be_cached)
        if _Debug:
            d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='message_peddler._do_cache_known_customers')
        d.addBoth(self._do_load_streams)
        return d

    def _do_load_streams(self, *args):
        service_dir = settings.ServiceDir('service_message_broker')
        queues_dir = os.path.join(service_dir, 'queues')
        loaded_queues = 0
        loaded_consumers = 0
        loaded_producers = 0
        loaded_messages = 0
        loaded_archive_messages = 0
        if not os.path.isdir(queues_dir):
            bpio._dirs_make(queues_dir)
        for queue_id in os.listdir(queues_dir):
            queue_dir = os.path.join(queues_dir, queue_id)
            messages_dir = os.path.join(queue_dir, 'messages')
            consumers_dir = os.path.join(queue_dir, 'consumers')
            producers_dir = os.path.join(queue_dir, 'producers')
            if queue_id not in streams():
                queue_info = global_id.ParseGlobalQueueID(queue_id)
                customer_idurl = global_id.glob2idurl(queue_info['owner_id'])
                if not id_url.is_cached(customer_idurl):
                    lg.err('customer %r IDURL still is not cached, not able to load stream %r' % (
                        customer_idurl, queue_id, ))
                    continue
                try:
                    register_stream(queue_id)
                except:
                    lg.exc()
                    continue
                loaded_queues += 1
            last_sequence_id = -1
            all_stored_queue_messages = os.listdir(messages_dir)
            all_stored_queue_messages.sort(key=lambda i: int(i))
            for _sequence_id in all_stored_queue_messages:
                sequence_id = int(_sequence_id)
                stored_json_message = jsn.loads_text(local_fs.ReadTextFile(os.path.join(messages_dir, strng.to_text(_sequence_id))))
                if stored_json_message:
                    if stored_json_message.get('processed'):
                        streams()[queue_id]['archive'].append(sequence_id)
                        loaded_archive_messages += 1
                    else:
                        streams()[queue_id]['messages'].append(sequence_id)
                    if sequence_id >= last_sequence_id:
                        last_sequence_id = sequence_id
                    loaded_messages += 1
                else:
                    lg.err('failed reading message %d from %r' % (sequence_id, queue_id, ))
            streams()[queue_id]['last_sequence_id'] = last_sequence_id
            for consumer_id in os.listdir(consumers_dir):
                if consumer_id in streams()[queue_id]['consumers']:
                    lg.warn('consumer %r already exist in stream %r' % (consumer_id, queue_id, ))
                    continue
                consumer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(consumers_dir, consumer_id)))
                if not consumer_info:
                    lg.err('failed reading consumer info %r from %r' % (consumer_id, queue_id, ))
                    continue
                streams()[queue_id]['consumers'][consumer_id] = consumer_info
                streams()[queue_id]['consumers'][consumer_id]['active'] = False
                loaded_consumers += 1
            for producer_id in os.listdir(producers_dir):
                if producer_id in streams()[queue_id]['producers']:
                    lg.warn('producer %r already exist in stream %r' % (producer_id, queue_id, ))
                    continue
                producer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(producers_dir, producer_id)))
                if not producer_info:
                    lg.err('failed reading producer info %r from %r' % (producer_id, queue_id, ))
                    continue
                streams()[queue_id]['producers'][producer_id] = producer_info
                streams()[queue_id]['producers'][producer_id]['active'] = False
                loaded_producers += 1
        ret = {
            'queues': loaded_queues,
            'consumers': loaded_consumers,
            'producers': loaded_producers,
            'messages': loaded_messages,
            'archive': loaded_archive_messages,
        }
        if _Debug:
            lg.args(_DebugLevel, **ret)
        reactor.callLater(0, self.automat, 'queues-loaded')  # @UndefinedVariable

    def _do_send_past_messages(self, queue_id, consumer_id, list_messages):
        latest_sequence_id = get_latest_sequence_id(queue_id)
        message.send_message(
            json_data={
                'msg_type': 'queue_message',
                'action': 'read',
                'created': utime.get_sec1970(),
                'items': list_messages,
                'last_sequence_id': latest_sequence_id,
            },
            recipient_global_id=my_keys.make_key_id(alias='master', creator_glob_id=consumer_id),
            packet_id=packetid.MakeQueueMessagePacketID(queue_id, packetid.UniqueID()),
            message_ack_timeout=25,
            skip_handshake=True,
            fire_callbacks=False,
        )
        if _Debug:
            lg.out(_DebugLevel, '>>> PAST MSG >>>    from %r to consumer %r with %d messages at sequence %d' % (
                queue_id, consumer_id, len(list_messages), latest_sequence_id, ))

    def _do_close_streams(self, queues_list):
        for queue_id in queues_list:
            if queue_id not in streams():
                continue
            if streams()[queue_id]['active']:
                for consumer_id in list(streams()[queue_id]['consumers']):
                    if consumer_id:
                        if not stop_consumer(queue_id, consumer_id):
                            lg.warn('failed to stop consumer %r in for queue %r' % (consumer_id, queue_id, ))
                        if not remove_consumer(queue_id, consumer_id):
                            lg.warn('consumer %r is not registered for queue %r' % (consumer_id, queue_id, ))
                for producer_id in list(streams()[queue_id]['producers']):
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


    def _do_check_create_queue_keeper(self, customer_idurl, request_packet, queue_id, consumer_id, producer_id,
                                      position, last_sequence_id, archive_folder_path, result_defer):
        if _Debug:
            lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id, producer_id=producer_id,
                    position=position, archive_folder_path=archive_folder_path)
        queue_keeper_result = Deferred()
        if _Debug:
            queue_keeper_result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='message_peddler._do_check_create_queue_keeper')

        qk = queue_keeper.existing(customer_idurl)
        if qk:
            if qk.state in ['DHT_WRITE', 'CONNECTED', ]:
                if qk.known_position == 0 and position > 0:
                    lg.warn('SKIP request, current known position is %d but requested position is %d' % (qk.known_position, position, ))
                    p2p_service.SendFail(request_packet, 'requested position %d is ahead of current position of the broker %d' % (
                        position, qk.known_position, ))
                    return

        qk = queue_keeper.check_create(customer_idurl=customer_idurl, auto_create=True)
        queue_keeper_result.addCallback(
            self._on_queue_keeper_connect_result,
            queue_id=queue_id,
            consumer_id=consumer_id,
            producer_id=producer_id,
            last_sequence_id=last_sequence_id,
            request_packet=request_packet,
            result_defer=result_defer,
        )
        qk.automat(
            'connect',
            queue_id=queue_id,
            desired_position=position,
            archive_folder_path=archive_folder_path,
            result_callback=queue_keeper_result,
            use_dht_cache=False,
        )

    def _do_replicate_message(self, message_in, known_brokers={}):
        if _Debug:
            lg.args(_DebugLevel, message_in=message_in, known_brokers=known_brokers)
        replicate_attempts = 0
        for other_broker_pos in range(groups.REQUIRED_BROKERS_COUNT):
            other_broker_idurl = known_brokers.get(other_broker_pos)
            if not other_broker_idurl:
                continue
            if id_url.to_bin(other_broker_idurl) == my_id.getIDURL().to_bin():
                continue
            d = message.send_message(
                json_data={
                    'msg_type': 'queue_message_replica',
                    'action': 'read',
                    'created': message_in.created,
                    'message_id': message_in.message_id,
                    'producer_id': message_in.producer_id,
                    'queue_id': message_in.queue_id,
                    'payload': message_in.payload,
                    'broker_position': other_broker_pos,
                },
                recipient_global_id=my_keys.make_key_id(alias='master', creator_idurl=other_broker_idurl),
                packet_id='qreplica_%s_%s' % (message_in.queue_id, packetid.UniqueID()),
                message_ack_timeout=25,
                skip_handshake=False,
                fire_callbacks=False,
            )
            d.addCallback(self._on_replicate_message_success, message_in, other_broker_pos)
            if _Debug:
                d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='message_peddler._do_replicate_message')
            d.addErrback(self._on_replicate_message_failed, message_in, other_broker_pos)
            replicate_attempts += 1
        if replicate_attempts == 0:
            lg.err('message was not replicated: %r' % message_in)

    def _do_build_archive_data(self, queue_id, archive_info):
        list_messages = read_messages(queue_id, sequence_id_list=archive_info['sequence_id_list'])
        raw_data = serialization.DictToBytes({'items': list_messages, })
        fileno, local_path = tmpfile.make('outbox', extension='.msg')
        os.write(fileno, raw_data)
        os.close(fileno)
        if _Debug:
            lg.args(_DebugLevel, archive_id=archive_info['archive_id'], messages_count=len(list_messages),
                    local_path=local_path, raw_data_bytes=len(raw_data))
        return archive_info['archive_id'], local_path

    def _do_archive_other_messages(self, queue_id):
        archive_snapshot_sequence_id_list = list(streams()[queue_id]['archive'])
        prepared_for_archive = len(archive_snapshot_sequence_id_list)
        if _Debug:
            lg.args(_DebugLevel, prepared_for_archive=prepared_for_archive, archive_chunk_size=self.archive_chunk_size,
                    archive_in_progress=self.archive_in_progress)
        if prepared_for_archive < self.archive_chunk_size:
            return
        if self.archive_in_progress:
            return
        customer_idurl = global_id.GetGlobalQueueOwnerIDURL(queue_id)
        qk = queue_keeper.queue_keepers().get(customer_idurl)
        if not qk:
            lg.err('queue_keeper() for %r was not found' % queue_id)
            return
        if qk.known_archive_folder_path is None:
            lg.err('archive folder path is unknown for %r' % queue_id)
            return
        self.archive_in_progress = True
        archive_snapshot_sequence_id_list.sort()
        archive_id = strng.to_text(archive_snapshot_sequence_id_list[-1])
        archive_result = Deferred()
        archive_result.addCallback(self._on_archive_backup_done, queue_id=queue_id)
        archive_result.addErrback(self._on_archive_backup_failed, queue_id=queue_id)
        aw = archive_writer.ArchiveWriter(local_data_callback=self._do_build_archive_data)
        aw.automat(
            'start',
            queue_id=queue_id,
            archive_info={
                'archive_id': archive_id,
                'sequence_id_list': archive_snapshot_sequence_id_list,
            },
            archive_folder_path=qk.known_archive_folder_path,
            result_defer=archive_result,
        )
        lg.info('started archive backup with %d messages, archive_id=%s' % (len(archive_snapshot_sequence_id_list), archive_id, ))

    def _on_archive_backup_done(self, archive_info, queue_id):
        if _Debug:
            lg.args(_DebugLevel, queue_id=queue_id, archive_info=archive_info)
        # TODO: notify other message brokers about that
        if queue_id in streams():
            for sequence_id in archive_info['sequence_id_list']:
                streams()[queue_id]['archive'].remove(sequence_id)
                erase_message(queue_id, sequence_id)
        else:
            lg.err('did not found stream %s' % queue_id)
        self.archive_in_progress = False
        self.automat('archive-backup-prepared')
        return None

    def _on_archive_backup_failed(self, err, queue_id):
        lg.err('archive in %r failed with : %r' % (queue_id, err, ))
        self.archive_in_progress = False
        self.automat('archive-backup-failed')
        return None

    def _on_queue_keeper_connect_result(self, result, queue_id, consumer_id, producer_id, last_sequence_id, request_packet, result_defer):
        if _Debug:
            lg.args(_DebugLevel, result=result, queue_id=queue_id, consumer_id=consumer_id, producer_id=producer_id,
                    last_sequence_id=last_sequence_id, request_packet=request_packet)
        if not result:
            lg.err('queue keeper failed to connect')
            p2p_service.SendFail(request_packet, 'failed to connect')
            result_defer.callback(False)
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
        cur_sequence_id = get_latest_sequence_id(queue_id)
        if last_sequence_id > cur_sequence_id:
            lg.warn('based on request from connected group member going to update last_sequence_id: %d -> %d' % (
                cur_sequence_id, last_sequence_id, ))
            set_latest_sequence_id(queue_id, last_sequence_id)
        p2p_service.SendAck(request_packet, 'accepted')
        result_defer.callback(True)
        return None

    def _on_identity_url_changed(self, evt):
        if my_id.getIDURL().to_bin() in [evt.data['new_idurl'], evt.data['old_idurl']]:
            return
        old_idurl = evt.data['old_idurl']
        new_id = global_id.idurl2glob(evt.data['new_idurl'])
        queues_to_be_closed = []
        if id_url.is_in(old_idurl, customers().keys(), as_field=False):
            for queue_id in customers()[id_url.field(old_idurl)]:
                queues_to_be_closed.append(queue_id)
        self._do_close_streams(queues_to_be_closed)
        for queue_id in streams().keys():
            rotated_consumers = []
            rotated_producers = []
            for cur_consumer_id in streams()[queue_id]['consumers']:
                consumer_idurl = global_id.glob2idurl(cur_consumer_id)
                if id_url.to_bin(consumer_idurl) == id_url.to_bin(old_idurl):
                    rotated_consumers.append((cur_consumer_id, new_id, ))
            for cur_producer_id in streams()[queue_id]['producers']:
                producer_idurl = global_id.glob2idurl(cur_producer_id)
                if id_url.to_bin(producer_idurl) == old_idurl:
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
        if _Debug:
            lg.args(_DebugLevel, err=err, request_packet=request_packet)
        p2p_service.SendFail(request_packet, 'group creator idurl cache failed')
        result_defer.callback(False)
        return None

    def _on_replicate_message_success(self, result, message_in, other_broker_pos):
        if _Debug:
            lg.args(_DebugLevel, result=result, message_in=message_in, other_broker_pos=other_broker_pos)

    def _on_replicate_message_failed(self, result, message_in, other_broker_pos):
        if _Debug:
            lg.args(_DebugLevel, result=result, message_in=message_in, other_broker_pos=other_broker_pos)
