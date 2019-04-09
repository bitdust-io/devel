#!/usr/bin/env python
# callback.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (callback.py) is part of BitDust Software.
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

"""
..

module:: callback
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

#------------------------------------------------------------------------------

# receiving callbacks
_InterestedParties = {}
_InboxPacketCallbacksList = []
_BeginFileReceivingCallbacksList = []
_FinishFileReceivingCallbacksList = []

# sending callbacks
_OutboxPacketCallbacksList = []
_OutboxPacketFilterCallbacksList = []
_QueueItemStatusCallbacksList = []
_BeginFileSendingCallbacksList = []
_FinishFileSendingCallbacksList = []

#------------------------------------------------------------------------------


class InterestedParty:

    def __init__(self, CallBackFunctionOrDefer, CreatorID, PacketID):
        self.CallBackFunction = CallBackFunctionOrDefer  # function(or Deferred) to call when we see this packet
        self.ComboID = combine_IDs(CreatorID, PacketID)

#------------------------------------------------------------------------------


def interested_parties():
    global _InterestedParties
    return _InterestedParties

#------------------------------------------------------------------------------


def combine_IDs(CreatorID, PacketID):
    return str(CreatorID) + ":" + str(PacketID)

#------------------------------------------------------------------------------


def append_inbox_callback(cb):
    """
    You can add a callback to receive incoming ``packets``. Callback will be
    called with such arguments::

    callback(newpacket, info, status, error_message).
    """
#     if _Debug:
#         lg.out(_DebugLevel, 'callback.append_inbox_callback new callback, current callbacks:')
    global _InboxPacketCallbacksList
    if cb not in _InboxPacketCallbacksList:
        _InboxPacketCallbacksList.append(cb)
#     if _Debug:
#         import pprint
#         lg.out(_DebugLevel, '        %s' % pprint.pformat(_InboxPacketCallbacksList))


def insert_inbox_callback(index, cb):
    """
    Same like ``append_inbox_callback(cb)`` but put the callback at the given
    position in the callbacks list. If you put your callback at the top you
    will catch the.

    inbox packet as soon as possible - before other callbacks.
    Callback will be called in a such way:

        callback(newpacket, info, status, error_message).
    """
#     if _Debug:
#         lg.out(_DebugLevel, 'callback.insert_inbox_callback new callback at position %d, current callbacks:' % index)
    global _InboxPacketCallbacksList
    if cb not in _InboxPacketCallbacksList:
        _InboxPacketCallbacksList.insert(index, cb)
#     if _Debug:
#         import pprint
#         lg.out(_DebugLevel, '        %s' % pprint.pformat(_InboxPacketCallbacksList))


def remove_inbox_callback(cb):
    """
    """
#     if _Debug:
#         lg.out(_DebugLevel, 'callback.remove_inbox_callback removing a callback, current callbacks:')
    global _InboxPacketCallbacksList
    if cb in _InboxPacketCallbacksList:
        _InboxPacketCallbacksList.remove(cb)
#     if _Debug:
#         import pprint
#         lg.out(_DebugLevel, '        %s' % pprint.pformat(_InboxPacketCallbacksList))


def append_outbox_filter_callback(cb):
    """
    You can add a callback to filter all outgoing traffic. Callback will be
    called with such arguments::

    callback(outpacket, wide, callbacks)
    """
    global _OutboxPacketFilterCallbacksList
    if cb not in _OutboxPacketFilterCallbacksList:
        _OutboxPacketFilterCallbacksList.append(cb)


def insert_outbox_filter_callback(index, cb):
    """
    Same like ``append_outbox_filter_callback(cb)`` but put the callback at the
    given position in the filters list. If you put your callback at the top you
    will catch the outgoing packet as soon as possible - before other callbacks.
    If callback returned True - all other callbacks will be skipped.
    Callback will be called in a such way:

        callback(outpacket, wide, callbacks).
    """
    global _OutboxPacketFilterCallbacksList
    if cb not in _OutboxPacketFilterCallbacksList:
        _OutboxPacketFilterCallbacksList.insert(index, cb)


def remove_outbox_filter_callback(cb):
    """
    """
    global _OutboxPacketFilterCallbacksList
    if cb in _OutboxPacketFilterCallbacksList:
        _OutboxPacketFilterCallbacksList.remove(cb)


def add_outbox_callback(cb):
    """
    You can add a callback to be notified when ``outbox()`` method was called.
    Useful when need to catch that event in third module. Arguments::

    callback(pkt_out)
    """
    global _OutboxPacketCallbacksList
    if cb not in _OutboxPacketCallbacksList:
        _OutboxPacketCallbacksList.append(cb)


def remove_outbox_callback(cb):
    """
    """
    global _OutboxPacketCallbacksList
    if cb in _OutboxPacketCallbacksList:
        _OutboxPacketCallbacksList.remove(cb)


def add_queue_item_status_callback(cb):
    """
    callback(pkt_out, status, error_message)
    """
    global _QueueItemStatusCallbacksList
    if cb not in _QueueItemStatusCallbacksList:
        _QueueItemStatusCallbacksList.append(cb)


def remove_queue_item_status_callback(cb):
    """
    """
    global _QueueItemStatusCallbacksList
    if cb in _QueueItemStatusCallbacksList:
        _QueueItemStatusCallbacksList.remove(cb)


def add_begin_file_sending_callback(cb):
    """
    cb(result_defer, remote_idurl, proto, host, filename, description, pkt_out)
    """
    global _BeginFileSendingCallbacksList
    if cb not in _BeginFileSendingCallbacksList:
        _BeginFileSendingCallbacksList.append(cb)


def add_finish_file_sending_callback(cb):
    """
    cb(pkt_out, item, status, size, error_message)
    """
    global _FinishFileSendingCallbacksList
    if cb not in _FinishFileSendingCallbacksList:
        _FinishFileSendingCallbacksList.append(cb)


def remove_finish_file_sending_callback(cb):
    """
    """
    global _FinishFileSendingCallbacksList
    if cb in _FinishFileSendingCallbacksList:
        _FinishFileSendingCallbacksList.remove(cb)


def add_begin_file_receiving_callback(cb):
    """
    cb(pkt_in)
    """
    global _BeginFileReceivingCallbacksList
    if cb not in _BeginFileReceivingCallbacksList:
        _BeginFileReceivingCallbacksList.append(cb)


def remove_begin_file_receiving_callback(cb):
    """
    """
    global _BeginFileReceivingCallbacksList
    if cb in _BeginFileReceivingCallbacksList:
        _BeginFileReceivingCallbacksList.remove(cb)


def add_finish_file_receiving_callback(cb, index=0):
    """
    cb(pkt_in, data)
    """
    global _FinishFileReceivingCallbacksList
    if cb not in _FinishFileReceivingCallbacksList:
        _FinishFileReceivingCallbacksList.insert(index, cb)

def remove_finish_file_receiving_callback(cb):
    """
    """
    global _FinishFileReceivingCallbacksList
    if cb in _FinishFileReceivingCallbacksList:
        _FinishFileReceivingCallbacksList.remove(cb)

#------------------------------------------------------------------------------


def run_inbox_callbacks(newpacket, info, status, error_message):
    """
    """
    global _InboxPacketCallbacksList
    if _Debug:
        lg.out(_DebugLevel, 'callback.run_inbox_callbacks for %s from %s' % (newpacket, info))
        # lg.out(_DebugLevel, '    %s' % _InboxPacketCallbacksList)
    handled = False
    for cb in _InboxPacketCallbacksList:
        try:
            if cb(newpacket, info, status, error_message):
                handled = True
        except:
            lg.exc()
            continue
        if not handled:
            if _Debug:
                lg.out(_DebugLevel, '    passed by %s' % lg.fqn(cb))
            continue
        if _Debug:
            lg.out(_DebugLevel, '    handled by %s' % lg.fqn(cb))
        break
    return handled


def run_outbox_callbacks(pkt_out):
    """
    """
    global _OutboxPacketCallbacksList
    if _Debug:
        lg.out(_DebugLevel, 'callback.run_outbox_callbacks for %s' % pkt_out)
        # lg.out(_DebugLevel, '    %s' % _OutboxPacketCallbacksList)
    handled = False
    for cb in _OutboxPacketCallbacksList:
        try:
            if cb(pkt_out):
                handled = True
        except:
            lg.exc()
        if not handled:
            if _Debug:
                lg.out(_DebugLevel, '    passed by %s' % lg.fqn(cb))
            continue
        if _Debug:
            lg.out(_DebugLevel, '    handled by %s' % lg.fqn(cb))
        break
    return handled


def run_outbox_filter_callbacks(outpacket, wide, callbacks, **kwargs):
    """
    """
    global _OutboxPacketFilterCallbacksList
    for cb in _OutboxPacketFilterCallbacksList:
        try:
            result = cb(outpacket, wide, callbacks, **kwargs)
        except:
            result = None
            lg.exc()
        if result is None:
            # sending was skipped in this filter, use next one
            continue
        if isinstance(result, Deferred):
            # filter was applied to outgoing data, but sending was delayed
            return result
        if result:
            # filter was applied, data was sent, return instance of packet_out.PacketOut
            return result
    lg.warn('no outbox filter was applied to : %s' % outpacket)
    return None


def run_queue_item_status_callbacks(pkt_out, status, error_message):
    """
    """
    global _QueueItemStatusCallbacksList
    handled = False
    for cb in _QueueItemStatusCallbacksList:
        try:
            if cb(pkt_out, status, error_message):
                handled = True
        except:
            lg.exc()
        if handled:
            break
    return handled


def run_begin_file_sending_callbacks(result_defer, remote_idurl, proto, host, filename, description, pkt_out):
    """
    """
    global _BeginFileSendingCallbacksList
    if _Debug:
        lg.out(_DebugLevel, 'callback.run_begin_file_sending_callbacks %s to %s:%s at %s' % (
            description, proto, host, remote_idurl))
    handled = False
    for cb in _BeginFileSendingCallbacksList:
        try:
            if cb(result_defer, remote_idurl, proto, host, filename, description, pkt_out):
                handled = True
        except:
            lg.exc()
        if handled:
            if _Debug:
                lg.out(_DebugLevel, '    handled by %s' % cb)
            break
    return handled


def run_finish_file_sending_callbacks(pkt_out, item, status, size, error_message):
    """
    """
    global _FinishFileSendingCallbacksList
    handled = False
    for cb in _FinishFileSendingCallbacksList:
        try:
            if cb(pkt_out, item, status, size, error_message):
                handled = True
        except:
            lg.exc()
        if handled:
            break
    return handled


def run_begin_file_receiving_callbacks(pkt_in):
    """
    """
    global _BeginFileReceivingCallbacksList
    if _Debug:
        lg.out(_DebugLevel, 'callback.run_begin_file_receiving_callbacks for %s' % pkt_in)
    handled = False
    for cb in _BeginFileReceivingCallbacksList:
        try:
            if cb(pkt_in):
                handled = True
        except:
            lg.exc()
        if handled:
            if _Debug:
                lg.out(_DebugLevel, '    handled by %s' % cb)
            break
    return handled


def run_finish_file_receiving_callbacks(info, data):
    """
    """
    global _FinishFileReceivingCallbacksList
    if _Debug:
        lg.out(_DebugLevel, 'callback.run_finish_file_receiving_callbacks %d bytes : %s' % (len(data), info, ))
    handled = False
    for cb in _FinishFileReceivingCallbacksList:
        try:
            if cb(info, data):
                handled = True
        except:
            lg.exc()
        if handled:
            if _Debug:
                lg.out(_DebugLevel, '    handled by %s' % cb)
            break
    return handled
