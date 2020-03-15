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
    * :red:`queue-connect`
    * :red:`queue-disconnect`
    * :red:`queues-loaded`
    * :red:`start`
    * :red:`stop`
"""


#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
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
from twisted.python import failure

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from crypt import my_keys

from main import events

from lib import jsn
from lib import strng

from system import bpio
from system import local_fs

from main import settings

from p2p import p2p_queue
from p2p import p2p_service

from userid import id_url
from userid import global_id

#------------------------------------------------------------------------------ 

_ActiveStreams = {}

_MessagePeddler = None

#------------------------------------------------------------------------------

def streams():
    global _ActiveStreams
    return _ActiveStreams

#------------------------------------------------------------------------------

def on_incoming_messages(json_messages):
    received = 0
    pushed = 0
    for json_message in json_messages:
        try:
            msg_type = json_message['type']
            msg_direction = json_message['dir']
            msg_data = json_message['data']
        except:
            lg.exc()
            continue
        if msg_type == 'queue_message' and msg_direction == 'incoming':
            continue
        queue_id = msg_data.get('queue_id')
        if queue_id not in streams():
            lg.warn('skipped incoming message, queue %r is not registered' % queue_id)
            continue
        if not streams()[queue_id]['active']:
            lg.warn('skipped incoming message, queue %r is not active' % queue_id)
            continue
        producer_id = json_message['data'].get('producer_id')
        if producer_id not in streams()[queue_id]['producers']:
            lg.warn('skipped incoming message, producer %r is not registered for queue %r' % (producer_id, queue_id, ))
            continue
        if not streams()[queue_id]['producers'][producer_id]['active']:
            lg.warn('skipped incoming message, producer %r is not active in queue %r' % (producer_id, queue_id, ))
            continue
        try:
            payload = json_message['data']['payload']
            created = json_message['data']['created']
        except:
            lg.exc()
            continue
        queued_json_message = save_incoming_message(queue_id, producer_id, payload, created)
        message_id = queued_json_message['id']
        streams()[queue_id]['messages'][message_id] = {
            'consumed': False,
            'pushed_id': None,
        }
        received += 1
        try:
            new_message = p2p_queue.push_message(
                producer_id=producer_id,
                queue_id=queue_id,
                data=queued_json_message,
                creation_time=created,
            )
        except:
            lg.exc()
            continue
        streams()[queue_id]['messages'][message_id]['pushed_id'] = new_message.message_id
        update_existing_message(queue_id, message_id)
        pushed += 1
    if received > pushed:
        lg.warn('some of received messages were queued but not pushed to the queue yet')
        return False
    return pushed > 0


def save_incoming_message(queue_id, producer_id, payload, created):
    last_message_id = streams()[queue_id]['last_message_id']
    new_message_id = strng.to_text(int(last_message_id) + 1)
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    message_path = os.path.join(messages_dir, new_message_id)
    queued_json_message = {
        'id': new_message_id,
        'created': created,
        'producer_id': producer_id,
        'payload': payload,
    }
    local_fs.WriteTextFile(message_path, jsn.dumps(queued_json_message))
    streams()[queue_id]['last_message_id'] = new_message_id
    return queued_json_message


def update_existing_message(queue_id, message_id):
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    messages_dir = os.path.join(queue_dir, 'messages')
    message_path = os.path.join(messages_dir, strng.to_text(message_id))
    queued_json_message = streams(queue_id)['messages'][message_id]
    local_fs.WriteTextFile(message_path, jsn.dumps(queued_json_message))
    return True

#------------------------------------------------------------------------------

def load_streams():
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    if not os.path.isdir(queues_dir):
        bpio._dirs_make(queues_dir)
    for queue_id in os.listdir(queues_dir):
        queue_dir = os.path.join(queues_dir, queue_id)
        messages_dir = os.path.join(queue_dir, 'messages')
        consumers_dir = os.path.join(queue_dir, 'consumers')
        producers_dir = os.path.join(queue_dir, 'producers')
        if queue_id not in streams():
            streams()[queue_id] = {
                'active': False,
                'consumers': {},
                'producers': {},
                'messages': [],
                'last_message_id': -1,
            }
        last_message_id = -1
        for message_id in os.listdir(messages_dir):
            streams()[queue_id]['messages']['message_id'] = {
                'consumed': False,
                'pushed_id': None,
            }
            if int(message_id) >= last_message_id:
                last_message_id = message_id
        streams()[queue_id]['last_message_id'] = last_message_id
        for consumer_id in os.listdir(consumers_dir):
            consumer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(consumers_dir, consumer_id)))
            if consumer_id in streams()[queue_id]['consumers']:
                lg.warn('consumer %r already exist in stream %r' % (consumer_id, queue_id))
                continue
            streams()[queue_id]['consumers'][consumer_id] = consumer_info
            streams()[queue_id]['consumers'][consumer_id]['active'] = False
        for producer_id in os.listdir(producers_dir):
            producer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(producers_dir, producer_id)))
            if producer_id in streams()[queue_id]['producers']:
                lg.warn('producer %r already exist in stream %r' % (producer_id, queue_id))
                continue
            streams()[queue_id]['producers'][producer_id] = producer_info
            streams()[queue_id]['producers'][producer_id]['active'] = False

#------------------------------------------------------------------------------

def open_stream(queue_id):
    if queue_id in streams():
        return False
    streams()[queue_id] = {
        'active': False,
        'consumers': {},
        'producers': {},
        'messages': [],
    }
    save_stream(queue_id)
    return True


def close_stream(queue_id):
    if queue_id not in streams():
        return False
    if streams()[queue_id]['active']:
        stop_stream(queue_id)
    streams().pop(queue_id)
    erase_stream(queue_id)
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
    return True


def erase_stream(queue_id):
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    queue_dir = os.path.join(queues_dir, queue_id)
    if os.path.isdir(queue_dir):
        bpio.rmdir_recursive(queue_dir, ignore_errors=True)
    return True

#------------------------------------------------------------------------------

def add_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        return False
    if consumer_id in streams()[queue_id]['consumers']:
        return False
    streams()[queue_id]['consumers'][consumer_id] = {
        'active': False,
        'last_message_id': -1,
    }
    save_consumer(queue_id, consumer_id)
    return True


def remove_consumer(queue_id, consumer_id):
    if queue_id not in streams():
        return False
    if consumer_id not in streams()[queue_id]['consumers']:
        return False
    if streams()[queue_id]['consumers'][consumer_id]['active']:
        if p2p_queue.is_consumer_subscribed(consumer_id, queue_id):
            p2p_queue.unsubscribe_consumer(consumer_id, queue_id)
    streams()[queue_id]['consumers'].pop(consumer_id)
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
    bpio._dirs_make(consumers_dir)
    consumer_path = os.path.join(consumers_dir, consumer_id)
    return local_fs.WriteTextFile(consumer_path, jsn.dumps(consumer_info))


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
    return True

#------------------------------------------------------------------------------

def add_producer(queue_id, producer_id):
    if queue_id not in streams():
        return False
    if producer_id in streams()[queue_id]['producers']:
        return False
    streams()[queue_id]['producers'][producer_id] = {
        'active': False,
        'last_message_id': -1,
    }
    save_producer(queue_id, producer_id)
    return True


def remove_producer(queue_id, producer_id):
    if queue_id not in streams():
        return False
    if producer_id not in streams()[queue_id]['producers']:
        return False
    if streams()[queue_id]['producers'][producer_id]['active']:
        if p2p_queue.is_producer_connected(producer_id, queue_id):
            p2p_queue.disconnect_producer(producer_id, queue_id)
    streams()[queue_id]['producers'].pop(producer_id)
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
    bpio._dirs_make(producers_dir)
    producer_path = os.path.join(producers_dir, producer_id)
    return local_fs.WriteTextFile(producer_path, jsn.dumps(producer_info))


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
    return True

#------------------------------------------------------------------------------

def start_all_streams():
    for queue_id, one_stream in streams().items():
        if not one_stream['active']:
            start_stream(queue_id)


def stop_all_streams():
    for queue_id, one_stream in streams().items():
        if one_stream['active']:
            stop_stream(queue_id)


def start_stream(queue_id):
    if not p2p_queue.is_queue_exist(queue_id):
        p2p_queue.open_queue(queue_id)
    for consumer_id in list(streams()[queue_id]['consumers'].keys()):
        consumer_idurl = global_id.glob2idurl(consumer_id)
        if not p2p_queue.is_consumer_exists(consumer_id):
            p2p_queue.add_consumer(consumer_id)
        if not p2p_queue.is_callback_method_registered(consumer_id, consumer_idurl):
            p2p_queue.add_callback_method(consumer_id, consumer_idurl)
        if not p2p_queue.is_consumer_subscribed(consumer_id, queue_id):
            p2p_queue.subscribe_consumer(consumer_id, queue_id)
        streams()[queue_id]['consumers'][consumer_id]['active'] = True
    for producer_id in list(streams()[queue_id]['producers'].keys()):
        if not p2p_queue.is_producer_exist(producer_id):
            p2p_queue.add_producer(producer_id)
        if not p2p_queue.is_producer_connected(producer_id, queue_id):
            p2p_queue.connect_producer(producer_id, queue_id)
        streams()[queue_id]['producers'][producer_id]['active'] = True
    streams()[queue_id]['active'] = True
    p2p_queue.touch_queues()
    return True


def stop_stream(queue_id):
    for producer_id in list(streams()[queue_id]['producers'].keys()):
        if p2p_queue.is_producer_connected(producer_id, queue_id):
            p2p_queue.disconnect_producer(producer_id, queue_id)
        streams()[queue_id]['producers'][producer_id]['active'] = False
    for consumer_id in list(streams()[queue_id]['consumers'].keys()):
        if p2p_queue.is_consumer_subscribed(consumer_id, queue_id):
            p2p_queue.unsubscribe_consumer(consumer_id, queue_id)
        streams()[queue_id]['consumers'][consumer_id]['active'] = False
    p2p_queue.close_queue(queue_id)
    streams()[queue_id]['active'] = False
    p2p_queue.touch_queues()
    return True

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
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doLoadKnownQueues(self, *args, **kwargs):
        """
        Action method.
        """
        load_streams()

    def doRunQueues(self, *args, **kwargs):
        """
        Action method.
        """
        start_all_streams()

    def doStopQueues(self, *args, **kwargs):
        """
        Action method.
        """
        stop_all_streams()

    def doStartJoinQueue(self, *args, **kwargs):
        """
        Action method.
        """
        group_key = kwargs['group_key']
        queue_id = kwargs['queue_id']
        consumer_id = kwargs['consumer_id']
        producer_id = kwargs['producer_id']
        request_packet = kwargs['request_packet']
        result_defer = kwargs['result_defer']
        # TODO: check/register group_key
        open_stream(kwargs['queue_id'])
        if consumer_id:
            add_consumer(queue_id, consumer_id)
        if producer_id:
            add_producer(queue_id, producer_id)
        start_stream(queue_id)
        p2p_service.SendAck(request_packet, 'accepted')
        result_defer.callback(True)

    def doLeaveStopQueue(self, *args, **kwargs):
        """
        Action method.
        """
        group_key = kwargs['group_key']
        queue_id = kwargs['queue_id']
        consumer_id = kwargs['consumer_id']
        producer_id = kwargs['producer_id']
        request_packet = kwargs['request_packet']
        result_defer = kwargs['result_defer']
        if queue_id not in streams():
            p2p_service.SendFail(request_packet, 'queue %r not registered' % queue_id)
            result_defer.callback(True)
            return
        # TODO: check/register group_key
        if consumer_id:
            if not remove_consumer(queue_id, consumer_id):
                p2p_service.SendFail(request_packet, 'consumer %r is not registered for queue %r' % (consumer_id, queue_id))
                result_defer.callback(True)
                return
        if producer_id:
            if not remove_producer(queue_id, producer_id):
                p2p_service.SendFail(request_packet, 'producer %r is not registered for queue %r' % (producer_id, queue_id))
                result_defer.callback(True)
                return
        if not streams()[queue_id]['consumers'] and not streams()[queue_id]['producers']:
            stop_stream(queue_id)
            close_stream(queue_id)
        p2p_service.SendAck(request_packet, 'accepted')
        result_defer.callback(True)

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

