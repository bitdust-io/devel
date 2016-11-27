#!/usr/bin/env python
# callback.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
.. module:: callback

"""

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 18

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
        self.CallBackFunction = CallBackFunctionOrDefer  # function(or Deferred)  to call when we see this packet
        self.ComboID = combine_IDs(CreatorID, PacketID)

#------------------------------------------------------------------------------


def interested_parties():
    global _InterestedParties
    return _InterestedParties

#------------------------------------------------------------------------------


def combine_IDs(CreatorID, PacketID):
    return str(CreatorID) + ":" + str(PacketID)


def register_interest(cb, creator_id, packet_id):
    """
    Idea is to have a list for each ComboID so that there might be more than one place called,
    but unique entries in that list.
    """
    newparty = InterestedParty(cb, str(creator_id), str(packet_id))
    if newparty.ComboID not in interested_parties().keys():
        interested_parties()[newparty.ComboID] = []
    interested_parties()[newparty.ComboID].append(newparty)
    if _Debug:
        lg.out(_DebugLevel, 'callback.register_interest %r' % newparty.ComboID)


def remove_interest(creator_id, packet_id):
    """
    cancel an interest
    """
    comboID = combine_IDs(creator_id, packet_id)
    if comboID in interested_parties():
        del interested_parties()[comboID]
    else:
        lg.warn(' party %r not found' % comboID)


def find_interested_party(newpacket, info):
    ComboID = combine_IDs(newpacket.CreatorID, newpacket.PacketID)
    if ComboID not in interested_parties().keys():
        if _Debug:
            lg.out(_DebugLevel, 'callback.find_interested_party not found : %r' % ComboID)
            for combid in interested_parties().keys():
                lg.out(_DebugLevel, '        %s' % combid)
        return False
    count = 0
    for party in interested_parties()[ComboID]:
        FuncOrDefer = party.CallBackFunction              # let him see the packet
        if isinstance(FuncOrDefer, Deferred):
            FuncOrDefer.callback(newpacket, info)
        else:
            FuncOrDefer(newpacket, info)
        count += 1
    del interested_parties()[ComboID]                 # We called all interested parties, remove entry in dictionary
    if _Debug:
        lg.out(_DebugLevel, 'callback.find_interested_party found for %r other parties=%d' % (newpacket, len(interested_parties())))
    return True


def delete_backup_interest(BackupName):
    """
    Deal with removing any interest in any potential data file belonging to a backup we're deleting,
    we don't want to call something trying to rebuild a backup we're deleting.
    """
    found = False
    partystoremove = set()
    for combokey in interested_parties().keys():
        if (combokey.find(":" + BackupName) != -1):  # if the interest is for packet belonging to a backup we're dealing with
            partystoremove.add(combokey)          # will remove party since got his callback
            found = True
    for combokey in partystoremove:                           #
        if _Debug:
            lg.out(_DebugLevel, "transport_control.DeleteBackupInterest removing " + combokey)
        del interested_parties()[combokey]
    del partystoremove
    return found

#------------------------------------------------------------------------------


def append_inbox_callback(cb):
    """
    You can add a callback to receive incoming ``packets``.
    Callback will be called with such arguments::

        callback(newpacket, info, status, error_message).
    """
    if _Debug:
        lg.out(_DebugLevel, 'callback.append_inbox_callback new callback, current callbacks:')
    global _InboxPacketCallbacksList
    if cb not in _InboxPacketCallbacksList:
        _InboxPacketCallbacksList.append(cb)
    if _Debug:
        import pprint
        lg.out(_DebugLevel, '        %s' % pprint.pformat(_InboxPacketCallbacksList))


def insert_inbox_callback(index, cb):
    """
    Same like ``append_inbox_callback(cb)`` but put the callback
    at the given position in the callbacks list.
    If you put your callback at the top you will catch the
    inbox packet as soon as possible - before other callbacks.
    Callback will be called in a such way:

        callback(newpacket, info, status, error_message).
    """
    if _Debug:
        lg.out(_DebugLevel, 'callback.insert_inbox_callback new callback at position %d, current callbacks:' % index)
    global _InboxPacketCallbacksList
    if cb not in _InboxPacketCallbacksList:
        _InboxPacketCallbacksList.insert(index, cb)
    if _Debug:
        import pprint
        lg.out(_DebugLevel, '        %s' % pprint.pformat(_InboxPacketCallbacksList))


def remove_inbox_callback(cb):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'callback.remove_inbox_callback removing a callback, current callbacks:')
    global _InboxPacketCallbacksList
    if cb in _InboxPacketCallbacksList:
        _InboxPacketCallbacksList.remove(cb)
    if _Debug:
        import pprint
        lg.out(_DebugLevel, '        %s' % pprint.pformat(_InboxPacketCallbacksList))


def append_outbox_filter_callback(cb):
    """
    You can add a callback to filter all outgoing traffic.
    Callback will be called with such arguments::

        callback(outpacket, wide, callbacks)
    """
    global _OutboxPacketFilterCallbacksList
    if cb not in _OutboxPacketFilterCallbacksList:
        _OutboxPacketFilterCallbacksList.append(cb)


def insert_outbox_filter_callback(index, cb):
    """
    Same like ``append_outbox_filter_callback(cb)`` but put the callback
    at the given position in the filters list.
    If you put your callback at the top you will catch the
    outgoing packet as soon as possible - before other callbacks.
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


def add_queue_item_status_callback(cb):
    """
    pkt_out, status, error_message
    """
    global _QueueItemStatusCallbacksList
    if cb not in _QueueItemStatusCallbacksList:
        _QueueItemStatusCallbacksList.append(cb)


def add_begin_file_sending_callback(cb):
    """
    """
    global _BeginFileSendingCallbacksList
    if cb not in _BeginFileSendingCallbacksList:
        _BeginFileSendingCallbacksList.append(cb)


def add_finish_file_sending_callback(cb):
    """
    pkt_out, item, status, size, error_message
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
    """
    global _BeginFileReceivingCallbacksList
    if cb not in _BeginFileReceivingCallbacksList:
        _BeginFileReceivingCallbacksList.append(cb)


def add_finish_file_receiving_callback(cb):
    """
    """
    global _FinishFileReceivingCallbacksList
    if cb not in _FinishFileReceivingCallbacksList:
        _FinishFileReceivingCallbacksList.append(cb)

#------------------------------------------------------------------------------


def run_inbox_callbacks(newpacket, info, status, error_message):
    """
    """
    global _InboxPacketCallbacksList
    if _Debug:
        lg.out(_DebugLevel, 'callback.run_inbox_callbacks for %s from %s' % (newpacket, info))
        lg.out(_DebugLevel, '    %s' % _InboxPacketCallbacksList)
    handled = False
    for cb in _InboxPacketCallbacksList:
        try:
            if cb(newpacket, info, status, error_message):
                handled = True
        except:
            lg.exc()
        if handled:
            if _Debug:
                lg.out(_DebugLevel, '    handled by %s' % cb)
            break
    return handled


def run_outbox_callbacks(pkt_out):
    """
    """
    global _OutboxPacketCallbacksList
    if _Debug:
        lg.out(_DebugLevel, 'callback.run_outbox_callbacks for %s' % pkt_out)
        lg.out(_DebugLevel, '    %s' % _OutboxPacketCallbacksList)
    handled = False
    for cb in _OutboxPacketCallbacksList:
        try:
            if cb(pkt_out):
                handled = True
        except:
            lg.exc()
        if handled:
            if _Debug:
                lg.out(_DebugLevel, '    handled by %s' % cb)
            break
    return handled


def run_outbox_filter_callbacks(outpacket, wide, callbacks, target=None, route=None):
    """
    """
    global _OutboxPacketFilterCallbacksList
    for cb in _OutboxPacketFilterCallbacksList:
        try:
            result = cb(outpacket, wide, callbacks, target, route)
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


def run_begin_file_sending_callbacks(outboxfile):
    """
    """


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


def run_begin_file_receiving_callbacks():
    """
    """


def run_finish_file_receiving_callbacks():
    """
    """
