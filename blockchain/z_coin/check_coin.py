import time
import os
import json
import hashlib
import re
import base64

from rsa import PublicKey, encrypt
from namespace import ns
from zlog import out

def check_coin(obj, data, name_space):
    """
        {"address":<addr>, "hash":<hash>, "starter":starter}
    """
    check = ns(name_space).db.find("coins", {"hash":data['hash']})
    if check:
        out("Coin already exists: " + data['hash']) 
        return
    check_addr = ns(name_space).nodes.find("nodes", {"address":data['address']})
    difficulty = ns(name_space).db.find("coins", "all")
    if not difficulty:
        difficulty = []
    difficulty = len(difficulty)/50500 + ns(name_space).base_difficulty
    if difficulty < ns(name_space).base_difficulty:
        difficulty = ns(name_space).base_difficulty

    if check_addr:
        c = check_addr[0]
        if len(data['hash']) == 128:
            check = str(data['starter'])
            if data.has_key('data') and data['data'] is not None:
                check += json.dumps(data['data'])
            if hashlib.sha512(check).hexdigest() == data['hash'] and data['hash'].startswith("1"*int(difficulty)):
                key = re.findall("([0-9]*)", c['public'])
                key = filter(None, key)
                key = PublicKey(int(key[0]), int(key[1]))
                data['plain'] = data['starter']
                data['starter'] = base64.b64encode(encrypt(str(data['starter']), key))
                obj.send(json.dumps({"response":"Coin Confirmed!"}))
                while os.path.exists("db.lock"):
                    time.sleep(0.1)
                open("db.lock", 'w').close()
                ns(name_space).db.insert("coins", {
                    "starter":data['starter'], 
                    "hash":data['hash'], 
                    "address":data['address'],
                    "data":data['data'], 
                    "difficulty":difficulty})
                ns(name_space).db.save()
                os.remove("db.lock")
            else:
                out("Invalid Coin: " + str(data))
        else:
            out("Hash not long enough")
    else:
        out("Addr invalid.")
        
