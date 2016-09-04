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

#------------------------------------------------------------------------------ 

from logs import lg

from userid import my_id

from broadcast import broadcaster_node
from broadcast import broadcast_listener

#------------------------------------------------------------------------------ 

def prepare_broadcast_message(creator, payload):
    tm = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    rnd = ''.join(random.choice(string.ascii_uppercase) for _ in range(4))
    msgid = '%s:%s:%s' % (tm, rnd, creator) 
    return {
        'creator': creator,
        'started': tm,
        'id': msgid,
        'payload': payload,
    }


def send_broadcast_message(payload):
    msg = prepare_broadcast_message(my_id.getLocalID(), payload)
    if broadcaster_node.A():
        broadcaster_node.A('new-outbound-message', msg)
    elif broadcast_listener.A():
        if broadcast_listener.A().state == 'OFFLINE':
            broadcast_listener.A('connect')
        broadcast_listener.A('outbound-message', msg)
    else:
        lg.warn('nor broadcaster_node(), nor broadcast_listener() exist')
        return None
    return msg


def on_incoming_broadcast_message(self, json_msg):
    lg.out(2, 'service_broadcasting._on_incoming_broadcast_message : %r' % json_msg)

#------------------------------------------------------------------------------ 

def main():
    pass

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    main()
