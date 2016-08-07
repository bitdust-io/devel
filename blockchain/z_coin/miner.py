import os
import time
import pprint
import random
import string
import json
import multiprocessing
import threading
from hashlib import sha512


import send_command

from namespace import ns, new
from zlog import out


def mine(name_space, data=None):
    while True:
        starter = ''.join([random.choice(string.uppercase+string.lowercase+string.digits) for _ in range(5)])    
        diff = send_command.send({"cmd":"get_difficulty"}, name_space, out=True)
        try:
            diff = json.loads(diff)['difficulty']
        except:
            pprint.pprint(diff)
            break
        on = 0
        while True:
            check = starter + str(on)
            if data is not None:
                check += json.dumps(data)
            hexdigest = sha512(check).hexdigest()
            if hexdigest.startswith("1"*diff):
                new_data = {
                    "cmd":"check_coin", 
                    "address":ns(name_space).wallet.find("data", "all")[0]['address'], 
                    "starter":starter+str(on), 
                    "hash":hexdigest,
                    "data": data,
                }
                new_coin = send_command.send(new_data, name_space,)
                if not new_coin:
                    continue
                try:
                    new_coin = json.loads(new_coin)
                except:
                    pprint.pprint(new_coin)
                    continue
                if new_coin['response'] != 'Coin Confirmed!':
                    continue
                out("Found Coin: " + hexdigest)
                return hexdigest
            else:
                on += 1


if __name__ == '__main__':
    new('current')
    for x in range(ns('current').mining_threads):
        if os.name != "nt":
            multiprocessing.Process(
                target=mine,
                args=('current', {
                    'text':'test data: ' + str(time.time()),
                })
            ).start()
        else:
            threading.Thread(target=mine,
                args=('current', {
                    'text':'test data: ' + str(time.time()),
                })
            ).start()
