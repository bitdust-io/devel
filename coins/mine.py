

from userid import my_id
from crypt import key


def sign_coin(data):
    coin_hash = key.Hash('.'.join([data[k] for k in sorted(data.keys())]), hexdigest=True)
    signature = key.Sign(coin_hash)
    data['signature'] = signature
    return data 


def sold_storage(partner, start, end, amount, price=1.0):
    """  
    + signer: idurl of this node
    + partner: idurl of given customer
    + type: sold_storage (can be also : buy_cpu, sell_traffic, buy_hosting, etc.)
    + start: time in UTC
    + end: time in UTC
    + amount: in megabytes
    + price: 1.0 by default 
    """
    data = {
        'signer': my_id.getLocalID(),
        'partner': partner,
        'type': 'sold_storage',
        'start': start,
        'end': end,
        'amount': amount,
        'price': price,
    }
    data = sign_coin(data)
    return data


def bought_storage(partner, ):
    pass











"""
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

"""