import os
import re
import base64
import time
import uuid

from rsa import PrivateKey, PublicKey, encrypt, decrypt
from namespace import ns
from zlog import out

import send_command


def send(address, amount, name_space):
    """
        { "cmd":"send_coin", 
          "for":<address>, 
          "hash":<hash>, 
          "starter":<encrypted new one>}
    """
    amount = int(amount)
    check = ns(name_space).nodes.find("nodes", {"address":address})
    if not check:
        out("Address does not exist")
        return False    
    check = check[0]
    my_key = ns(name_space).wallet.find("data", "all")[0]
    my_address = my_key['address']
    my_key = my_key['private']
    key = check['public']
    key = re.findall("([0-9]*)", key)
    key = filter(None, key)
    key = PublicKey(int(key[0]), int(key[1]))
    my_key = re.findall("([0-9]*)", my_key)
    my_key = filter(None, my_key)
    my_key = PrivateKey(int(my_key[0]), 
                        int(my_key[1]), 
                        int(my_key[2]), 
                        int(my_key[3]), 
                        int(my_key[4]))
    cc = ns(name_space).db.find("coins", {"address":my_address})
    if len(cc) < amount:
        out("You have insufficient funds.")
        return False
    cc = cc[:amount]
    transactionid = uuid.uuid4().hex
    sent_ = 0
    for x in cc:
        starter, hash_ = x['starter'], x['hash']
        starter = base64.b64encode(
                      encrypt(
                      decrypt(
                      base64.b64decode(starter), my_key), key))
        out_s = {'cmd': 'send_coin',
                'for': address,
                "transid":transactionid,
                'starter': starter,
                'hash': hash_,
                "from":my_address,
                "amount_sent":amount,
                "plain":x['starter'],
                "difficulty":x['difficulty'],
                }
        send_command.send(out_s, name_space)
        sent_ += 1
    out(str(sent_)+" coins sent to "+address)
    return True


def send_coin(obj, data, name_space):
    db_lock_file_name = ns(name_space).db.db + '.lock'
    if not ns(ns(name_space)).db.find("transactions", {"transid":data['transid']}):
        ns(ns(name_space)).db.insert("transactions", {
            "to":data['for'], 
            "from":data['from'], 
            "amount":data['amount_sent'], 
            "transid":data['transid'],
        })
        while os.path.exists(db_lock_file_name):
            time.sleep(0.1)
        open(db_lock_file_name, 'w').close()
        ns(name_space).db.save()
        os.remove(db_lock_file_name)
    while os.path.exists(db_lock_file_name):
        time.sleep(0.1)
    open(db_lock_file_name, 'w').close()
    check = ns(name_space).db.find("coins", {"hash":data['hash']})
    for x in check:
        ns(name_space).db.remove("coins", x)
        ns(name_space).db.save()
    ns(name_space).db.insert("coins",{
        "address":data['for'], 
        "starter":data['starter'], 
        "hash":data['hash'],
        "data":data['data'],
        "difficulty":data['difficulty'],
    })
    ns(name_space).db.save()
    os.remove(db_lock_file_name)

