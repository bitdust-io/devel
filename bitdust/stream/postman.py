#!/usr/bin/env python
# postman.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (postman.py) is part of BitDust Software.
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
    pass
except:
    sys.exit('Error initializing twisted.internet.reactor in keys_synchronizer.py')

#------------------------------------------------------------------------------

from twisted.internet.defer import DeferredList

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.crypt import my_keys

from bitdust.lib import jsn
from bitdust.lib import utime
from bitdust.lib import packetid

from bitdust.contacts import identitycache

from bitdust.system import bpio
from bitdust.system import local_fs

from bitdust.main import settings
from bitdust.main import events

from bitdust.p2p import p2p_service
from bitdust.p2p import propagate

from bitdust.stream import p2p_queue
from bitdust.stream import message

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

#------------------------------------------------------------------------------

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


def init():
    if _Debug:
        lg.out(_DebugLevel, 'postman.init')
    events.add_subscriber(on_identity_url_changed, 'identity-url-changed')
    message.consume_messages(
        consumer_callback_id='postman',
        callback=on_consume_queue_messages,
        direction='incoming',
        message_types=[
            'queue_message',
        ],
    )
    p2p_queue.add_message_processed_callback(on_message_processed)
    start_all_streams()
    do_cache_known_customers()


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'postman.shutdown')
    stop_all_streams()
    p2p_queue.remove_message_processed_callback(on_message_processed)
    message.clear_consumer_callbacks('postman')
    events.remove_subscriber(on_identity_url_changed, 'identity-url-changed')


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
        'last_sequence_id': -1,
    }
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, customer=customer_idurl, customer_streams=len(customers().get(customer_idurl, [])))
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
        lg.args(_DebugLevel, queue_id=queue_id, customer=customer_idurl, customer_streams=len(customers().get(customer_idurl, [])))
    return True


#------------------------------------------------------------------------------


def on_consume_queue_messages(json_messages):
    received = 0
    pushed = 0
    handled = False
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
        if global_id.latest_glob_id(to_user) != my_id.getID():
            continue
        if msg_type != 'queue_message':
            continue
        if msg_action not in ['produce', 'consume']:
            continue
        queue_id = msg_data.get('queue_id')
        if not queue_id:
            continue
        if msg_type == 'queue_message':
            if queue_id not in streams():
                group_creator_idurl = global_id.GetGlobalQueueOwnerIDURL(queue_id)
                if not group_creator_idurl.is_latest():
                    lg.warn('group creator idurl was rotated, consumer must refresh own identity cache: %r ~ %r' % (group_creator_idurl.to_original(), group_creator_idurl.to_bin()))
                    known_ident = identitycache.get_one(group_creator_idurl.to_bin())
                    if not known_ident:
                        lg.err('unknown group creator identity: %r' % group_creator_idurl.to_bin())
                        p2p_service.SendFailNoRequest(from_idurl, packet_id, 'unknown group creator identity')
                        continue
                    p2p_service.SendFailNoRequest(from_idurl, packet_id, 'identity:%s' % known_ident.serialize(as_text=True))
                    continue
                lg.warn('skipped incoming queue_message, queue %r is not registered' % queue_id)
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'queue ID not registered')
                continue
            if not streams()[queue_id]['active']:
                lg.warn('skipped incoming queue_message, queue %r is not active' % queue_id)
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'queue is not active')
                continue
        if msg_action == 'consume':
            # request from group_participant() to catch up unread messages from the queue
            # TODO: decide about a solution to read past messages and potentially cleanup that block
            consumer_id = msg_data.get('consumer_id')
            if consumer_id not in streams()[queue_id]['consumers']:
                lg.warn('skipped incoming "queue-read" request, consumer %r is not registered for queue %r' % (consumer_id, queue_id))
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'consumer is not registered')
                continue
            if not streams()[queue_id]['consumers'][consumer_id]['active']:
                lg.warn('skipped incoming "queue-read" request, consumer %r is not active in queue %r' % (consumer_id, queue_id))
                p2p_service.SendFailNoRequest(from_idurl, packet_id, 'consumer is not active')
                continue
            p2p_service.SendAckNoRequest(from_idurl, packet_id)
            handled = True
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
                    lg.warn('skipped incoming queue_message, producer %r is not registered for queue %r' % (producer_id, queue_id))
                    p2p_service.SendFailNoRequest(from_idurl, packet_id, 'producer is not registered')
                    continue
                if not streams()[queue_id]['producers'][producer_id]['active']:
                    lg.warn('skipped incoming queue_message, producer %r is not active in queue %r' % (producer_id, queue_id))
                    p2p_service.SendFailNoRequest(from_idurl, packet_id, 'producer is not active')
                    continue
            # incoming message from group_participant() to push new message to the queue and deliver to all other group members
            received += 1
            if not do_push_message(from_idurl, packet_id, queue_id, producer_id, payload, created):
                continue
            pushed += 1
            handled = True
            continue
        raise Exception('unexpected message "action": %r' % msg_action)
    if received > pushed:
        lg.warn('some of the received messages was not pushed to the queue %r' % queue_id)
    if not handled:
        if _Debug:
            lg.dbg(_DebugLevel, 'queue messages was not handled: %r' % json_messages)
    return handled


def do_push_message(from_idurl, packet_id, queue_id, producer_id, payload, created):
    new_sequence_id = increment_sequence_id(queue_id)
    json_message = make_message(new_sequence_id, producer_id, payload, created)
    if _Debug:
        lg.out(_DebugLevel, '<<< PUSH <<<    into %r by %r at sequence %d' % (queue_id, producer_id, new_sequence_id))
    try:
        p2p_queue.write_message(
            producer_id=producer_id,
            queue_id=queue_id,
            data=json_message,
            creation_time=created,
        )
    except:
        lg.exc()
        return False
    p2p_service.SendAckNoRequest(from_idurl, packet_id)
    return True


#------------------------------------------------------------------------------


def on_message_processed(processed_message):
    sequence_id = processed_message.get_sequence_id()
    if _Debug:
        lg.args(
            _DebugLevel, queue_id=processed_message.queue_id, sequence_id=sequence_id, message_id=processed_message.message_id, success_notifications=processed_message.success_notifications,
            failed_notifications=processed_message.failed_notifications
        )
    if sequence_id is None:
        return False
    if processed_message.failed_notifications:
        if _Debug:
            lg.out(_DebugLevel, '>>> FAILED >>>    from %r at sequence %d, failed_consumers=%d' % (processed_message.queue_id, sequence_id, len(processed_message.failed_notifications)))
    else:
        if _Debug:
            lg.out(_DebugLevel, '>>> PULL >>>    from %r at sequence %d with success count %d' % (processed_message.queue_id, sequence_id, len(processed_message.success_notifications)))
    return True


def on_consumer_notify(message_info):
    try:
        queue_id = message_info['queue_id']
    except:
        lg.exc('invalid incoming message: %r' % message_info)
        return False
    if not queue_id.startswith('group_'):
        # ignore the message, it seems it is not a queue message but it is addressed to the same consumer
        return False
    try:
        payload = message_info['payload']
    except:
        lg.exc('invalid incoming message: %r' % message_info)
        return False
    if 'sequence_id' not in payload:
        # ignore the message, it seems it is not a queue message but it is addressed to the same consumer
        return False
    try:
        consumer_id = message_info['consumer_id']
        packet_id = packetid.MakeQueueMessagePacketID(queue_id, packetid.UniqueID())
        sequence_id = payload['sequence_id']
        last_sequence_id = get_latest_sequence_id(queue_id)
        producer_id = payload['producer_id']
    except:
        lg.exc('invalid incoming message: %r' % message_info)
        return False
    if _Debug:
        lg.args(_DebugLevel, p=producer_id, c=consumer_id, q=queue_id, s=sequence_id, l=last_sequence_id)
    ret = message.send_message(
        json_data={
            'msg_type': 'queue_message',
            'action': 'read',
            'created': utime.utcnow_to_sec1970(),
            'items': [
                {
                    'sequence_id': sequence_id,
                    'created': payload['created'],
                    'producer_id': producer_id,
                    'payload': payload['payload'],
                },
            ],
            'last_sequence_id': last_sequence_id,
        },
        recipient_global_id=my_keys.make_key_id(alias='master', creator_glob_id=consumer_id),
        packet_id=packet_id,
        # message_ack_timeout=config.conf().getInt('services/message-broker/message-ack-timeout'),
        skip_handshake=True,
        fire_callbacks=False,
    )
    ret.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, ignore=True, method='postman.on_consumer_notify')
    if _Debug:
        lg.out(_DebugLevel, '>>> NOTIFY >>>    from %r by producer %r to consumer %r at sequence %d' % (queue_id, producer_id, consumer_id, sequence_id))
    return ret


#------------------------------------------------------------------------------


def get_latest_sequence_id(queue_id):
    if queue_id not in streams():
        return -1
    return streams()[queue_id].get('last_sequence_id', -1)


def increment_sequence_id(queue_id):
    last_sequence_id = int(streams()[queue_id]['last_sequence_id'])
    if last_sequence_id <= 0:
        last_sequence_id = utime.get_milliseconds1970()
    new_last_sequence_id = utime.get_milliseconds1970()
    if last_sequence_id >= new_last_sequence_id:
        new_last_sequence_id = last_sequence_id + 1
    streams()[queue_id]['last_sequence_id'] = new_last_sequence_id
    return new_last_sequence_id


def make_message(sequence_id, producer_id, payload, created):
    return {
        'sequence_id': sequence_id,
        'created': created,
        'producer_id': producer_id,
        'payload': payload,
        'attempts': [],
        'processed': None,
    }


#------------------------------------------------------------------------------


def close_all_streams():
    service_dir = settings.ServiceDir('service_joint_postman')
    queues_dir = os.path.join(service_dir, 'queues')
    list_queues = os.listdir(queues_dir)
    for queue_id in list_queues:
        close_stream(queue_id, erase_data=False)
    return True


def check_rotate_queues():
    service_dir = settings.ServiceDir('service_joint_postman')
    queues_dir = os.path.join(service_dir, 'queues')
    if not os.path.isdir(queues_dir):
        bpio._dirs_make(queues_dir)
    rotated = 0
    known_queueus = os.listdir(queues_dir)
    for queue_id in known_queueus:
        queue_info = global_id.ParseGlobalQueueID(queue_id)
        this_broker_idurl = global_id.glob2idurl(queue_info['supplier_id'])
        if id_url.is_cached(this_broker_idurl) and not this_broker_idurl.is_latest():
            latest_queue_id = global_id.MakeGlobalQueueID(queue_info['queue_alias'], queue_info['owner_id'], this_broker_idurl.to_id())
            if latest_queue_id != queue_id:
                latest_queue_path = os.path.join(queues_dir, latest_queue_id)
                old_queue_path = os.path.join(queues_dir, queue_id)
                if not os.path.isfile(latest_queue_path):
                    bpio.move_dir_recursive(old_queue_path, latest_queue_path)
                    try:
                        bpio._dir_remove(old_queue_path)
                    except:
                        pass
                    rotated += 1
                    lg.info('detected and processed queue rotate : %r -> %r' % (queue_id, latest_queue_id))
                else:
                    bpio._dir_remove(old_queue_path)
                    lg.warn('found an old queue %r and deleted' % old_queue_path)
    if _Debug:
        lg.args(_DebugLevel, rotated=rotated)


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


def close_stream(queue_id, erase_data=True):
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id)
    if queue_id not in streams():
        lg.warn('stream not found: %r' % queue_id)
        return False
    if streams()[queue_id]['active']:
        stop_stream(queue_id)
    if erase_data:
        erase_stream(queue_id)
    unregister_stream(queue_id)
    return True


def save_stream(queue_id):
    service_dir = settings.ServiceDir('service_joint_postman')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    consumers_dir = os.path.join(queue_dir, 'consumers')
    producers_dir = os.path.join(queue_dir, 'producers')
    stream_info = streams()[queue_id]
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, typ=type(queue_id))
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
    service_dir = settings.ServiceDir('service_joint_postman')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    erased_files = 0
    if os.path.isdir(queue_dir):
        erased_files += bpio.rmdir_recursive(queue_dir, ignore_errors=True)
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, queue_dir=queue_dir, erased_files=erased_files)
    return True


def rename_stream(old_queue_id, new_queue_id):
    service_dir = settings.ServiceDir('service_joint_postman')
    queues_dir = os.path.join(service_dir, 'queues')
    old_queue_dir = os.path.join(queues_dir, old_queue_id)
    new_queue_dir = os.path.join(queues_dir, new_queue_id)
    old_customer_idurl = global_id.GetGlobalQueueOwnerIDURL(old_queue_id)
    new_customer_idurl = global_id.GetGlobalQueueOwnerIDURL(new_queue_id)
    if old_customer_idurl not in customers().keys():
        return False
    if old_queue_id not in customers()[old_customer_idurl]:
        return False
    customers()[old_customer_idurl].remove(old_queue_id)
    if not customers()[old_customer_idurl]:
        customers().pop(old_customer_idurl)
    streams()[new_queue_id] = streams().pop(old_queue_id)
    if new_customer_idurl not in customers():
        customers()[new_customer_idurl] = []
    if new_queue_id not in customers()[new_customer_idurl]:
        customers()[new_customer_idurl].append(new_queue_id)
    if os.path.isdir(new_queue_dir):
        bpio.rmdir_recursive(new_queue_dir, ignore_errors=True)
    if os.path.isdir(old_queue_dir):
        bpio.move_dir_recursive(old_queue_dir, new_queue_dir)
    if _Debug:
        lg.args(_DebugLevel, old=old_queue_id, new=new_queue_id)
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
    service_dir = settings.ServiceDir('service_joint_postman')
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
    service_dir = settings.ServiceDir('service_joint_postman')
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
    service_dir = settings.ServiceDir('service_joint_postman')
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
    service_dir = settings.ServiceDir('service_joint_postman')
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
        lg.warn('queue % is not active, can not start consumer %r' % (queue_id, consumer_id))
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        lg.warn('not able to start consumer %r because it was not added to the queue %r' % (consumer_id, queue_id))
        return False
    if not p2p_queue.is_consumer_exists(consumer_id):
        p2p_queue.add_consumer(consumer_id)
    if not p2p_queue.is_callback_method_registered(consumer_id, on_consumer_notify):
        p2p_queue.add_callback_method(consumer_id, on_consumer_notify, interested_queues_list=['group_'])
    if not p2p_queue.is_consumer_subscribed(consumer_id, queue_id):
        p2p_queue.subscribe_consumer(consumer_id, queue_id)
    streams()[queue_id]['consumers'][consumer_id]['active'] = True
    save_consumer(queue_id, consumer_id)
    lg.info('consumer %s started in the queue %s' % (consumer_id, queue_id))
    return True


def stop_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        lg.warn('queue % is not active, can not stop consumer %r' % (queue_id, consumer_id))
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        lg.warn('not able to stop consumer %r because it was not added to the queue %r' % (consumer_id, queue_id))
        return False
    if p2p_queue.is_callback_method_registered(consumer_id, on_consumer_notify):
        p2p_queue.remove_callback_method(consumer_id, on_consumer_notify)
    if p2p_queue.is_consumer_subscribed(consumer_id, queue_id):
        p2p_queue.unsubscribe_consumer(consumer_id, queue_id, remove_empty=True)
    streams()[queue_id]['consumers'][consumer_id]['active'] = False
    save_consumer(queue_id, consumer_id)
    lg.info('consumer %s stopped in the queue %s' % (consumer_id, queue_id))
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
        lg.warn('queue % is not active, can not start producer %r' % (queue_id, producer_id))
        return False
    if producer_id not in streams()[queue_id]['producers']:
        lg.warn('not able to start producer %r because it was not added to the queue %r' % (producer_id, queue_id))
        return False
    if not p2p_queue.is_producer_exist(producer_id):
        p2p_queue.add_producer(producer_id)
    if not p2p_queue.is_producer_connected(producer_id, queue_id):
        p2p_queue.connect_producer(producer_id, queue_id)
    streams()[queue_id]['producers'][producer_id]['active'] = True
    save_producer(queue_id, producer_id)
    lg.info('producer %s started in the queue %s' % (producer_id, queue_id))
    return True


def stop_producer(queue_id, producer_id):
    if queue_id not in streams():
        lg.warn('queue % is not active, can not stop producer %r' % (queue_id, producer_id))
        return False
    if producer_id not in streams()[queue_id]['producers']:
        lg.warn('not able to stop producer %r because it was not added to the queue %r' % (producer_id, queue_id))
        return False
    if p2p_queue.is_producer_connected(producer_id, queue_id):
        p2p_queue.disconnect_producer(producer_id, queue_id, remove_empty=True)
    streams()[queue_id]['producers'][producer_id]['active'] = False
    save_producer(queue_id, producer_id)
    lg.info('producer %s stopped in the queue %s' % (producer_id, queue_id))
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
    if p2p_queue.is_queue_exist(queue_id):
        p2p_queue.close_queue(queue_id, remove_empty_consumers=True, remove_empty_producers=True)
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


def ping_all_streams():
    target_nodes = list(set(list_customers() + list_consumers_producers()))
    if _Debug:
        lg.args(_DebugLevel, target_nodes=target_nodes)
    propagate.propagate(selected_contacts=target_nodes, wide=True, refresh_cache=True)


#------------------------------------------------------------------------------


def list_customers():
    ret = list(customers().keys())
    if _Debug:
        lg.args(_DebugLevel, r=ret)
    return ret


def list_consumers_producers(include_consumers=True, include_producers=True):
    result = set()
    for queue_id in streams().keys():
        if include_consumers:
            for consumer_id in streams()[queue_id]['consumers']:
                consumer_idurl = global_id.glob2idurl(consumer_id)
                if consumer_idurl not in result:
                    result.add(consumer_idurl)
        if include_producers:
            for producer_id in streams()[queue_id]['producers']:
                producer_idurl = global_id.glob2idurl(producer_id)
                if producer_idurl not in result:
                    result.add(producer_idurl)
    ret = list(result)
    if _Debug:
        lg.args(_DebugLevel, r=ret)
    return ret


#------------------------------------------------------------------------------


def on_queue_connect_request(request_packet, result_defer, consumer_id, producer_id, group_key_info):
    if _Debug:
        lg.args(_DebugLevel, consumer_id=consumer_id, producer_id=producer_id)
    if not my_keys.verify_key_info_signature(group_key_info):
        if _Debug:
            lg.exc('group key verification failed', exc_value=Exception(group_key_info))
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
    group_key_id = my_keys.latest_key_id(group_key_id)
    group_key_alias, group_creator_idurl = my_keys.split_key_id(group_key_id)
    if not group_key_alias or not group_creator_idurl:
        lg.warn('wrong group_key_id: %r' % group_key_id)
        p2p_service.SendFail(request_packet, 'invalid group_key_id')
        result_defer.callback(False)
        return
    if not group_creator_idurl.is_latest():
        lg.warn('group creator idurl was rotated, consumer must refresh own identity cache: %r ~ %r' % (group_creator_idurl.to_original(), group_creator_idurl.to_bin()))
        known_ident = identitycache.get_one(group_creator_idurl.to_bin())
        if not known_ident:
            lg.err('unknown group creator identity: %r' % group_creator_idurl)
            p2p_service.SendFail(request_packet, 'unknown group creator identity')
            result_defer.callback(False)
            return
        p2p_service.SendFail(request_packet, 'identity:%s' % known_ident.serialize(as_text=True))
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
    else:
        if not my_keys.register_key(group_key_id, key_object, group_key_info.get('label', '')):
            p2p_service.SendFail(request_packet, 'key register failed')
            result_defer.callback(False)
            return
    consumer_idurl = global_id.glob2idurl(consumer_id)
    producer_idurl = global_id.glob2idurl(producer_id)
    caching_list = []
    if not id_url.is_cached(group_creator_idurl):
        caching_list.append(identitycache.immediatelyCaching(group_creator_idurl))
    if not id_url.is_cached(consumer_idurl):
        caching_list.append(identitycache.immediatelyCaching(consumer_idurl))
    if not id_url.is_cached(producer_idurl):
        caching_list.append(identitycache.immediatelyCaching(producer_idurl))
    dl = DeferredList(caching_list, consumeErrors=True)
    dl.addCallback(lambda _: do_connect_queue(
        request_packet,
        result_defer,
        consumer_id,
        producer_id,
        group_key_info,
        group_creator_idurl,
    ))
    # TODO: need to cleanup registered key in case request was rejected or ID cache failed
    dl.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='postman.on_queue_connect_request')
    dl.addErrback(on_group_creator_idurl_cache_failed, request_packet, result_defer)


def on_queue_disconnect_request(request_packet, result_defer, consumer_id, producer_id, group_key_info, queue_id):
    if not my_keys.verify_key_info_signature(group_key_info):
        if _Debug:
            lg.exc('group key verification failed while stopping consumer or producer', exc_value=Exception(group_key_info))
        p2p_service.SendFail(request_packet, 'group key verification failed while stopping consumer or producer')
        result_defer.callback(False)
        return
    try:
        group_key_id, _ = my_keys.read_key_info(group_key_info)
    except:
        lg.exc()
        p2p_service.SendFail(request_packet, 'failed reading key info')
        result_defer.callback(False)
        return
    group_key_id = my_keys.latest_key_id(group_key_id)
    group_key_alias, group_creator_idurl = my_keys.split_key_id(group_key_id)
    if not group_key_alias or not group_creator_idurl:
        lg.warn('wrong group_key_id: %r' % group_key_id)
        p2p_service.SendFail(request_packet, 'invalid group_key_id')
        result_defer.callback(False)
        return
    if _Debug:
        lg.args(_DebugLevel, queue_id=queue_id, consumer_id=consumer_id, producer_id=producer_id, request_packet=request_packet)
    if not queue_id or queue_id not in streams():
        lg.warn('queue was not registered already: %r' % queue_id)
        p2p_service.SendAck(request_packet, 'accepted')
        result_defer.callback(True)
        return
    if consumer_id:
        if not stop_consumer(queue_id, consumer_id):
            lg.err('failed to stop consumer %r for the queue %r' % (consumer_id, queue_id))
            p2p_service.SendFail(request_packet, 'failed to stop consumer for the queue')
            result_defer.callback(False)
            return
        if not remove_consumer(queue_id, consumer_id):
            lg.err('failed to remove consumer %r for the queue %r' % (consumer_id, queue_id))
            p2p_service.SendFail(request_packet, 'consumer is not registered for the queue')
            result_defer.callback(False)
            return
    if producer_id:
        if not stop_producer(queue_id, producer_id):
            lg.err('failed to stop producer %r for the queue %r' % (producer_id, queue_id))
            p2p_service.SendFail(request_packet, 'failed to stop producer for the queue')
            result_defer.callback(False)
            return
        if not remove_producer(queue_id, producer_id):
            lg.err('failed to remove producer %r for the queue %r' % (producer_id, queue_id))
            p2p_service.SendFail(request_packet, 'producer is not registered for the queue')
            result_defer.callback(False)
            return
    if not streams()[queue_id]['consumers'] and not streams()[queue_id]['producers']:
        # at least one member must be in the group to keep it alive
        lg.info('no consumers and no producers left, closing queue %r' % queue_id)
        stop_stream(queue_id)
        close_stream(queue_id, erase_data=True)
    customer_idurl = global_id.GetGlobalQueueOwnerIDURL(queue_id)
    if customer_idurl in customers():
        if len(customers()[customer_idurl]) == 0:
            lg.info('no streams left for %r' % customer_idurl)
            # if my_keys.is_key_registered(group_key_id):
            #     lg.info('clean up group key %r' % group_key_id)
            #     my_keys.erase_key(group_key_id)
    p2p_service.SendAck(request_packet, 'accepted')
    result_defer.callback(True)


def on_group_creator_idurl_cache_failed(err, request_packet, result_defer):
    if _Debug:
        lg.args(_DebugLevel, err=err, request_packet=request_packet)
    p2p_service.SendFail(request_packet, 'group creator, consumer or producer idurl cache failed')
    result_defer.callback(False)
    return None


def on_identity_url_changed(evt):
    if _Debug:
        lg.args(_DebugLevel, **evt.data)
    old_idurl = evt.data['old_idurl']
    new_idurl = evt.data['new_idurl']
    if my_id.getIDURL().to_bin() in [new_idurl, old_idurl]:
        lg.warn('my IDURL was rotated, restarting all streams')
        stop_all_streams()
        p2p_queue.remove_message_processed_callback(on_message_processed)
        close_all_streams()
        check_rotate_queues()
        p2p_queue.add_message_processed_callback(on_message_processed)
        start_all_streams()
        return
    new_id = global_id.idurl2glob(new_idurl)
    queues_to_be_closed = []
    if id_url.is_in(old_idurl, customers().keys(), as_field=False):
        for queue_id in customers()[id_url.field(old_idurl)]:
            queues_to_be_closed.append(queue_id)
    do_close_streams(queues_to_be_closed, erase_key=False)
    for queue_id in streams().keys():
        rotated_consumers = []
        rotated_producers = []
        for cur_consumer_id in streams()[queue_id]['consumers']:
            consumer_idurl = global_id.glob2idurl(cur_consumer_id)
            if id_url.is_the_same(consumer_idurl, old_idurl) or id_url.is_the_same(consumer_idurl, new_idurl):
                rotated_consumers.append((cur_consumer_id, new_id))
        for cur_producer_id in streams()[queue_id]['producers']:
            producer_idurl = global_id.glob2idurl(cur_producer_id)
            if id_url.is_the_same(producer_idurl, old_idurl) or id_url.is_the_same(producer_idurl, new_idurl):
                rotated_producers.append((cur_producer_id, new_id))
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


#------------------------------------------------------------------------------


def do_connect_queue(request_packet, result_defer, consumer_id, producer_id, group_key_info, target_customer_idurl):
    try:
        target_customer_id = target_customer_idurl.to_id()
        target_queue_alias = group_key_info['alias']
        target_queue_id = global_id.MakeGlobalQueueID(
            queue_alias=target_queue_alias,
            owner_id=target_customer_id,
            supplier_id=my_id.getIDURL().to_id(),
        )
        known_customer_streams = customers().get(target_customer_idurl, [])
        if _Debug:
            lg.args(_DebugLevel, customer=target_customer_idurl, customer_streams=known_customer_streams)
        for current_queue_id in list(p2p_queue.queue().keys()):
            if current_queue_id == target_queue_id:
                continue
            queue_alias, customer_id, _ = global_id.SplitGlobalQueueID(current_queue_id, split_queue_alias=True)
            if target_queue_alias != queue_alias:
                continue
            if target_customer_id != customer_id:
                continue
            p2p_queue.rename_queue(current_queue_id, target_queue_id)
            if current_queue_id not in streams():
                raise Exception('rotated queue %r was not registered' % current_queue_id)
            if target_queue_id in streams():
                lg.warn('rotated queue %r was already registered' % target_queue_id)
            rename_stream(current_queue_id, target_queue_id)
        if target_queue_id not in streams():
            open_stream(target_queue_id)
        if not is_stream_active(target_queue_id):
            start_stream(target_queue_id)
        if consumer_id:
            add_consumer(target_queue_id, consumer_id)
            start_consumer(target_queue_id, consumer_id)
        if producer_id:
            add_producer(target_queue_id, producer_id)
            start_producer(target_queue_id, producer_id)
    except:
        lg.exc()
        p2p_service.SendFail(request_packet, 'failed connecting to the queue')
        result_defer.callback(False)
        return None
    p = {}
    p['queue_id'] = target_queue_id
    p2p_service.SendAck(request_packet, 'accepted:%s' % jsn.dumps(p, keys_to_text=True, values_to_text=True))
    result_defer.callback(True)
    return None


def do_restart_streams():
    loaded_queues = 0
    loaded_consumers = 0
    loaded_producers = 0
    to_be_started = set()
    service_dir = settings.ServiceDir('service_joint_postman')
    queues_dir = os.path.join(service_dir, 'queues')
    if not os.path.isdir(queues_dir):
        bpio._dirs_make(queues_dir)
    known_queues = os.listdir(queues_dir)
    if _Debug:
        lg.args(_DebugLevel, current=len(streams()), known=len(known_queues))
    for queue_id in known_queues:
        queue_info = global_id.ParseGlobalQueueID(queue_id)
        # this_customer_idurl = global_id.glob2idurl(queue_info['owner_id'])
        this_supplier_idurl = global_id.glob2idurl(queue_info['supplier_id'])
        if not this_supplier_idurl.is_latest():
            lg.err('found unclean rotated queue_id: %r' % queue_id)
            continue
        queue_dir = os.path.join(queues_dir, queue_id)
        consumers_dir = os.path.join(queue_dir, 'consumers')
        producers_dir = os.path.join(queue_dir, 'producers')
        if queue_id not in streams():
            customer_idurl = global_id.glob2idurl(queue_info['owner_id'])
            if not id_url.is_cached(customer_idurl):
                lg.err('customer %r IDURL still is not cached, not able to load stream %r' % (customer_idurl, queue_id))
                continue
            try:
                register_stream(queue_id)
            except:
                lg.exc()
                continue
            to_be_started.add(queue_id)
            loaded_queues += 1
        else:
            to_be_started.add(queue_id)
        for consumer_id in (os.listdir(consumers_dir) if os.path.isdir(consumers_dir) else []):
            if consumer_id in streams()[queue_id]['consumers']:
                lg.warn('consumer %r already exist in stream %r' % (consumer_id, queue_id))
                continue
            consumer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(consumers_dir, consumer_id)))
            if not consumer_info:
                lg.err('failed reading consumer info %r from %r' % (consumer_id, queue_id))
                continue
            streams()[queue_id]['consumers'][consumer_id] = consumer_info
            streams()[queue_id]['consumers'][consumer_id]['active'] = False
            start_consumer(queue_id, consumer_id)
            loaded_consumers += 1
        for producer_id in (os.listdir(producers_dir) if os.path.isdir(producers_dir) else []):
            if producer_id in streams()[queue_id]['producers']:
                lg.warn('producer %r already exist in stream %r' % (producer_id, queue_id))
                continue
            producer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(producers_dir, producer_id)))
            if not producer_info:
                lg.err('failed reading producer info %r from %r' % (producer_id, queue_id))
                continue
            streams()[queue_id]['producers'][producer_id] = producer_info
            streams()[queue_id]['producers'][producer_id]['active'] = False
            loaded_producers += 1
    for queue_id in to_be_started:
        if not is_stream_active(queue_id):
            start_stream(queue_id)
    if _Debug:
        lg.args(_DebugLevel, q=loaded_queues, c=loaded_consumers, p=loaded_producers, s=len(to_be_started))


def do_close_streams(queues_list, erase_key=False):
    if _Debug:
        lg.args(_DebugLevel, queues_list=queues_list)
    for queue_id in queues_list:
        if queue_id not in streams():
            continue
        if streams()[queue_id]['active']:
            for consumer_id in list(streams()[queue_id]['consumers']):
                if consumer_id:
                    if not stop_consumer(queue_id, consumer_id):
                        lg.warn('failed to stop consumer %r in for queue %r' % (consumer_id, queue_id))
                    if not remove_consumer(queue_id, consumer_id):
                        lg.warn('consumer %r is not registered for queue %r' % (consumer_id, queue_id))
            for producer_id in list(streams()[queue_id]['producers']):
                if producer_id:
                    if not stop_producer(queue_id, producer_id):
                        lg.warn('failed to stop producer %r in for queue %r' % (producer_id, queue_id))
                    if not remove_producer(queue_id, producer_id):
                        lg.warn('producer %r is not registered for queue %r' % (producer_id, queue_id))
        stop_stream(queue_id)
        close_stream(queue_id, erase_data=False)
        customer_idurl = global_id.GetGlobalQueueOwnerIDURL(queue_id)
        if customer_idurl in customers():
            if len(customers()[customer_idurl]) == 0:
                lg.info('no streams left for %r' % customer_idurl)
                # group_key_id = global_id.GetGlobalQueueKeyID(queue_id)
                # group_key_id = my_keys.latest_key_id(group_key_id)
                # if erase_key and my_keys.is_key_registered(group_key_id):
                #     lg.info('clean up group key %r' % group_key_id)
                #     my_keys.erase_key(group_key_id)


def do_cache_known_customers():
    service_dir = settings.ServiceDir('service_joint_postman')
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
        return do_restart_streams()
    d = identitycache.start_multiple(to_be_cached)
    d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='postman.do_cache_known_customers')
    d.addBoth(lambda _: do_restart_streams())
    return d
