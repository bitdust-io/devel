#!/usr/bin/python
#broadcast_service.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: broadcast_service

@author: Veselin

"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------ 

# This is used to be able to execute this module directly from command line.
if __name__ == '__main__': 
    import sys, os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------ 

import datetime
import random
import string      
import json  

#------------------------------------------------------------------------------ 

from logs import lg

from lib import packetid

from crypt import signed
from crypt import key

from p2p import commands

from userid import my_id

#------------------------------------------------------------------------------ 

def prepare_broadcast_message(owner, payload):
    tm = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    rnd = ''.join(random.choice(string.ascii_uppercase) for _ in range(4))
    msgid = '%s:%s:%s' % (tm, rnd, owner)
    msg = [
        ('owner', owner),
        ('started', tm),
        ('id', msgid),
        ('payload', payload),
    ]
    # owner_sign = key.Sign(key.Hash(str(msg)))
    msg = {k:v for k, v in msg}
    # msg['owner_sign'] = owner_sign
    return msg


def read_message_from_packet(newpacket):
    try:
        msg = json.loads(newpacket.Payload)
    except:
        lg.exc()
        return None
    # TODO verify owner signature and creator ID
    return msg


def packet_for_broadcaster(broadcaster_idurl, json_data):
    if 'broadcaster' not in json_data:
        json_data['broadcaster'] = broadcaster_idurl
    return signed.Packet(commands.Broadcast(),
                         json_data['owner'],
                         json_data['owner'], 
                         json_data['id'],
                         json.dumps(json_data),
                         broadcaster_idurl,)


def packet_for_listener(listener_idurl, json_data):
    if 'broadcaster' not in json_data:
        json_data['broadcaster'] = my_id.getLocalID()
    return signed.Packet(commands.Broadcast(),
                         json_data['owner'],
                         my_id.getLocalID(), 
                         json_data['id'],
                         json.dumps(json_data),
                         listener_idurl,)

#------------------------------------------------------------------------------ 

def send_broadcast_message(payload):
    from broadcast import broadcaster_node
    from broadcast import broadcast_listener
    msg = prepare_broadcast_message(my_id.getLocalID(), payload)
    if broadcaster_node.A():
        broadcaster_node.A('new-outbound-message', (msg, None))
    elif broadcast_listener.A():
        if broadcast_listener.A().state == 'OFFLINE':
            broadcast_listener.A('connect')
        broadcast_listener.A('outbound-message', msg)
    else:
        lg.warn('nor broadcaster_node(), nor broadcast_listener() exist')
        return None
    return msg

#------------------------------------------------------------------------------ 

def on_incoming_broadcast_message(json_msg):
    lg.out(2, 'service_broadcasting._on_incoming_broadcast_message : %r' % json_msg)

#------------------------------------------------------------------------------ 

def main():
    pass

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    main()
