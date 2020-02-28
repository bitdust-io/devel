#!/usr/bin/python
# message_broker.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (message_broker.py) is part of BitDust Software.
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
.. module:: message_broker

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from logs import lg

from lib import jsn

from system import bpio
from system import local_fs

from main import settings

from p2p import p2p_queue

#------------------------------------------------------------------------------

_ActiveStreams = {}

#------------------------------------------------------------------------------

def init():
    if _Debug:
        lg.out(_DebugLevel, "message_broker.init")
    open_known_streams()


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, "message_broker.shutdown")

#------------------------------------------------------------------------------

def streams():
    global _ActiveStreams
    return _ActiveStreams

#------------------------------------------------------------------------------

def open_known_streams():
    service_dir = settings.ServiceDir('service_message_broker')
    queues_dir = os.path.join(service_dir, 'queues')
    consumers_dir = os.path.join(service_dir, 'consumers')
    producers_dir = os.path.join(service_dir, 'producers')

    for queue_id in os.listdir(queues_dir):
        stream_dirpath = os.path.join(queues_dir, queue_id)
        if queue_id not in streams():
            streams()[queue_id] = {
                'messages': [],
            }
        if not p2p_queue.is_queue_exist(queue_id):
            p2p_queue.open_queue(queue_id)
        for message_id in os.listdir(stream_dirpath):
            streams()[queue_id]['messages'].append({
                'message_id': message_id,
                # TODO: ...
            })

    for consumer_id in os.listdir(consumers_dir):
        consumer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(consumers_dir, consumer_id)))
        queue_id = consumer_info['queue_id']
        if queue_id not in streams():
            lg.warn('unknown stream %r for consumer %r' % (queue_id, consumer_id))
            continue 
        if not p2p_queue.is_consumer_exists(consumer_id):
            p2p_queue.add_consumer(consumer_id)
        p2p_queue.subscribe_consumer(consumer_id, queue_id)

    for producer_id in os.listdir(producers_dir):
        producer_info = jsn.loads_text(local_fs.ReadTextFile(os.path.join(producers_dir, producer_id)))
        queue_id = producer_info['queue_id']
        if queue_id not in streams():
            lg.warn('unknown stream %r for producer %r' % (queue_id, producer_id))
            continue 
        if not p2p_queue.is_producer_exist(producer_id):
            p2p_queue.add_producer(producer_id)
        p2p_queue.connect_producer(producer_id, queue_id)

#------------------------------------------------------------------------------

def publish_stream_in_dht(queue_id):
    #TODO: 
    return

    