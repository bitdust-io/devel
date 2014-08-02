
"""
.. module:: callback

"""

from twisted.internet.defer import Deferred

from logs import lg

#------------------------------------------------------------------------------ 

_InterestedParties = {}
_InboxPacketCallbacksList = []
_OutboxPacketCallbacksList = []
_QueueItemStatusCallbacksList = []
_BeginFileSendingCallbacksList = []
_FinishFileSendingCallbacksList = []
_BeginFileReceivingCallbacksList = []
_FinishFileReceivingCallbacksList = []

#------------------------------------------------------------------------------ 

class InterestedParty:
    def __init__(self, CallBackFunctionOrDefer, CreatorID, PacketID):
        self.CallBackFunction = CallBackFunctionOrDefer # function(or Deferred)  to call when we see this packet
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
    lg.out(18, 'callback.register_interest %r' % newparty.ComboID)


def remove_interest(creator_id, packet_id):
    """
    cancel an interest
    """
    comboID = combine_IDs(creator_id, packet_id)
    if interested_parties().has_key(comboID):
        del interested_parties()[comboID]
    else:
        lg.out(10, 'callback.remove_interest WARNING  party %r not found' % comboID)


def find_interested_party(newpacket, info):
    ComboID = combine_IDs(newpacket.CreatorID, newpacket.PacketID)
    if ComboID not in interested_parties().keys():
        # lg.out(18, 'callback.find_interested_party not found : %r' % ComboID)
        # for combid in interested_parties().keys():
        #     lg.out(18, '        %s' % combid)
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
    lg.out(18, 'callback.find_interested_party found for %r other parties=%d' % (newpacket, len(interested_parties())))
    return True


def delete_backup_interest(BackupName):
    """
    Deal with removing any interest in any potential data file belonging to a backup we're deleting,
    we don't want to call something trying to rebuild a backup we're deleting.
    """
    found = False
    partystoremove = set()
    for combokey in interested_parties().keys():
        if (combokey.find(":"+BackupName) != -1): # if the interest is for packet belonging to a backup we're dealing with
            partystoremove.add(combokey)          # will remove party since got his callback
            found=True
    for combokey in partystoremove:                           #
        # lg.out(12, "transport_control.DeleteBackupInterest removing " + combokey)
        del interested_parties()[combokey]
    del partystoremove
    return found

#------------------------------------------------------------------------------ 

def add_inbox_callback(cb):
    """
    You can add a callback to receive incoming ``packets``.
    Callback will be called with such arguments::
  
        callback(newpacket, info, status, error_message).
    """
    global _InboxPacketCallbacksList
    if cb not in _InboxPacketCallbacksList:
        _InboxPacketCallbacksList.append(cb)
    
        
def remove_inbox_callback(cb):
    """
    """
    global _InboxPacketCallbacksList
    if cb in _InboxPacketCallbacksList:
        _InboxPacketCallbacksList.remove(cb)


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
    handled = False
    for cb in _InboxPacketCallbacksList:
        try:
            if cb(newpacket, info, status, error_message):
                handled = True
        except:
            lg.exc()
    return handled


def run_outbox_callbacks(pkt_out):
    """
    """
    global _OutboxPacketCallbacksList
    handled = False
    for cb in _OutboxPacketCallbacksList:
        try:
            if cb(pkt_out):
                handled = True
        except:
            lg.exc()
    return handled


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
    return handled
    
    
def run_begin_file_receiving_callbacks():
    """
    """    
    

def run_finish_file_receiving_callbacks():
    """
    """




