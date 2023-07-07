"""
Common helpers for Bismuth
"""
import base64
import getpass
import hashlib
import json
import math
import os
import re
import time

import requests
# from Crypto import Random
from Cryptodome.PublicKey import RSA

from quantizer import quantize_eight
from decimal import Decimal
from simplecrypt import decrypt
from typing import Union
from polysign.signer import SignerType
from polysign.signerfactory import SignerFactory

__version__ = '0.0.7'
"""
0.0.7 : decrease checkpoint limit to 30 blocks at 1450000 (meaning max 59 blocks rollback)
"""
"""
For temp. code compatibility, dup code moved to polysign module
"""


DUST_FEE = 0.00001
OPENFIELD_SIZE = 100000


def address_validate(address: str) -> bool:
    return SignerFactory.address_is_valid(address)


def address_is_rsa(address: str) -> bool:
    return SignerFactory.address_is_rsa(address)


"""
End compatibility
"""


def format_raw_tx(raw: list) -> dict:
    transaction = dict()
    transaction['block_height'] = raw[0]
    transaction['timestamp'] = raw[1]
    transaction['address'] = raw[2]
    transaction['recipient'] = raw[3]
    transaction['amount'] = raw[4]
    transaction['signature'] = raw[5]
    transaction['txid'] = raw[5][:56]
    try:
        transaction['pubkey'] = base64.b64decode(raw[6]).decode('utf-8')
    except:
        transaction['pubkey'] = raw[6]  #support new pubkey schemes
    transaction['block_hash'] = raw[7]
    transaction['fee'] = raw[8]
    transaction['reward'] = raw[9]
    transaction['operation'] = raw[10]
    transaction['openfield'] = raw[11]
    return transaction


def percentage(percent, whole):
    return Decimal(percent)*Decimal(whole)/100


def replace_regex(string: str, replace: str) -> str:
    replaced_string = re.sub(r'^{}'.format(replace), '', string)
    return replaced_string


def download_file(url: str, filename: str) -> None:
    """Download a file from URL to filename

    :param url: URL to download file from
    :param filename: Filename to save downloaded data as

    returns `filename`
    """
    try:
        r = requests.get(url, stream=True)
        total_size = int(r.headers.get('content-length'))/1024

        with open(filename, 'wb') as fp:
            chunkno = 0
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    chunkno = chunkno + 1
                    # if chunkno % 10000 == 0:  # every x chunks
                    #     print(f'Downloaded {int(100 * (chunkno / total_size))} %')

                    fp.write(chunk)
                    fp.flush()
            # print('Downloaded 100 %')
    except:
        raise


def most_common(lst: list):
    """Used by consensus"""
    # TODO: factorize the two helpers in one. and use a less cpu hungry method (counter)
    return max(set(lst), key=lst.count)


def most_common_dict(a_dict: dict):
    """Returns the most common value from a dict. Used by consensus"""
    return max(a_dict.values())


def percentage_in(individual, whole):
    return (float(list(whole).count(individual)/float(len(whole))))*100


def round_down(number, order):
    return int(math.floor(number/order))*order


def checkpoint_set(node):
    limit = 30
    if node.last_block < 1450000:
        limit = 1000
    checkpoint = round_down(node.last_block, limit) - limit
    if checkpoint != node.checkpoint:
        node.checkpoint = checkpoint
        node.logger.app_log.warning(f'Checkpoint set to {node.checkpoint}')


def ledger_balance3(address, cache, db_handler):
    # Many heavy blocks are pool payouts, same address.
    # Cache pre_balance instead of recalc for every tx
    if address in cache:
        return cache[address]
    credit_ledger = Decimal(0)

    db_handler.execute_param(db_handler.c, 'SELECT amount, reward FROM transactions WHERE recipient = ?;', (address, ))
    entries = db_handler.c.fetchall()

    for entry in entries:
        credit_ledger += quantize_eight(entry[0]) + quantize_eight(entry[1])

    debit_ledger = Decimal(0)
    db_handler.execute_param(db_handler.c, 'SELECT amount, fee FROM transactions WHERE address = ?;', (address, ))
    entries = db_handler.c.fetchall()

    for entry in entries:
        debit_ledger += quantize_eight(entry[0]) + quantize_eight(entry[1])

    cache[address] = quantize_eight(credit_ledger - debit_ledger)
    return cache[address]


def sign_rsa(timestamp, address, recipient, amount, operation, openfield, key, public_key_b64encoded) -> Union[bool, tuple]:
    # TODO: move, make use of polysign module
    if not key:
        raise BaseException('The wallet is locked, you need to provide a decrypted key')
    try:
        transaction = (str(timestamp), str(address), str(recipient), '%.8f' % float(amount), str(operation), str(openfield))
        # this is signed, float kept for compatibility
        buffer = str(transaction).encode('utf-8')
        signer = SignerFactory.from_private_key(key.exportKey().decode('utf-8'), SignerType.RSA)
        signature_enc = signer.sign_buffer_for_bis(buffer)
        # Extra: recheck - Raises if Error
        SignerFactory.verify_bis_signature(signature_enc, public_key_b64encoded, buffer, address)
        full_tx = str(timestamp), str(address), str(recipient), '%.8f' % float(amount), \
                  str(signature_enc.decode('utf-8')), str(public_key_b64encoded.decode('utf-8')), \
                  str(operation), str(openfield)
        return full_tx
    except:
        return False


def keys_check(app_log, keyfile_name: str, data_dir='.') -> None:
    # TODO: move, make use of polysign module
    # key maintenance
    if os.path.isfile(os.path.join(data_dir, 'privkey.der')) is True:
        app_log.warning('privkey.der found')
    elif os.path.isfile(os.path.join(data_dir, 'privkey_encrypted.der')) is True:
        app_log.warning('privkey_encrypted.der found')
        os.rename(os.path.join(data_dir, 'privkey_encrypted.der'), os.path.join(data_dir, 'privkey.der'))

    elif os.path.isfile(keyfile_name) is True:
        app_log.warning('{} found'.format(keyfile_name))
    else:
        # generate key pair and an address
        key = RSA.generate(4096)
        # public_key = key.publickey()

        private_key_readable = key.exportKey().decode('utf-8')
        public_key_readable = key.publickey().exportKey().decode('utf-8')
        address = hashlib.sha224(public_key_readable.encode('utf-8')).hexdigest()  # hashed public key
        # generate key pair and an address

        app_log.info('Your address: {}'.format(address))
        app_log.info('Your public key: {}'.format(public_key_readable))

        # export to single file
        keys_save(private_key_readable, public_key_readable, address, keyfile_name)
        # export to single file


def keys_save(private_key_readable: str, public_key_readable: str, address: str, file) -> None:
    wallet_dict = dict()
    wallet_dict['Private Key'] = private_key_readable
    wallet_dict['Public Key'] = public_key_readable
    wallet_dict['Address'] = address
    if not isinstance(file, str):
        file = file.name
    with open(file, 'w') as keyfile:
        json.dump(wallet_dict, keyfile)


def keys_load(privkey_filename: str = 'privkey.der', pubkey_filename: str = 'pubkey.der', wallet_filename: str ='wallet.der'):
    keyfile = 'wallet.der'
    if wallet_filename and os.path.exists(wallet_filename):
        # print('Using modern wallet method')
        return keys_load_new(wallet_filename)

    else:
        # print("loaded",privkey, pubkey)
        # import keys
        try:  # unencrypted
            with open(privkey_filename) as fp:
                key = RSA.importKey(fp.read())
            private_key_readable = key.exportKey().decode('utf-8')
            # public_key = key.publickey()
            encrypted = False
            unlocked = True
        except:  # encrypted
            encrypted = True
            unlocked = False
            key = None
            with open(privkey_filename) as fp:
                private_key_readable = fp.read()

        # public_key_readable = str(key.publickey().exportKey())
        with open(pubkey_filename.encode('utf-8')) as fp:
            public_key_readable = fp.read()

        if len(public_key_readable) not in (271, 799):
            raise ValueError('Invalid public key length: {}'.format(len(public_key_readable)))

        public_key_b64encoded = base64.b64encode(public_key_readable.encode('utf-8'))
        address = hashlib.sha224(public_key_readable.encode('utf-8')).hexdigest()

        # print('Upgrading wallet')
        keys_save(private_key_readable, public_key_readable, address, wallet_filename or keyfile)

        return key, public_key_readable, private_key_readable, encrypted, unlocked, public_key_b64encoded, address, wallet_filename or keyfile


def keys_unlock(private_key_encrypted: str) -> tuple:
    password = getpass.getpass()
    encrypted_privkey = private_key_encrypted
    decrypted_privkey = decrypt(password, base64.b64decode(encrypted_privkey))
    key = RSA.importKey(decrypted_privkey)  # be able to sign
    private_key_readable = key.exportKey().decode('utf-8')
    return key, private_key_readable


def keys_load_new(keyfile='wallet.der'):
    # import keys

    with open(keyfile, 'r') as keyfile:
        wallet_dict = json.load(keyfile)

    private_key_readable = wallet_dict['Private Key']
    public_key_readable = wallet_dict['Public Key']
    address = wallet_dict['Address']

    try:  # unencrypted
        key = RSA.importKey(private_key_readable)
        encrypted = False
        unlocked = True

    except:  # encrypted
        encrypted = True
        unlocked = False
        key = None

    # public_key_readable = str(key.publickey().exportKey())
    if len(public_key_readable) not in (271, 799):
        raise ValueError('Invalid public key length: {}'.format(len(public_key_readable)))

    public_key_b64encoded = base64.b64encode(public_key_readable.encode('utf-8'))

    return key, public_key_readable, private_key_readable, encrypted, unlocked, public_key_b64encoded, address, keyfile


def fee_calculate(openfield: str, operation: str = '', block: int = 0) -> Decimal:
    # block var will be removed after HF
    fee = Decimal('{}'.format(DUST_FEE)) + (Decimal(len(openfield))/Decimal('{}'.format(OPENFIELD_SIZE)))  # dust + openfield cost
    if operation == 'token:issue':
        fee = Decimal(fee) + Decimal('10')
    if openfield.startswith('alias='):
        fee = Decimal(fee) + Decimal('1')
    #if operation == "alias:register": #add in the future, careful about forking
    #    fee = Decimal(fee) + Decimal("1")
    return quantize_eight(fee)


def execute_param_c(cursor, query, param, app_log):
    """Secure execute w/ param for slow nodes"""
    while True:
        try:
            cursor.execute(query, param)
            break
        except UnicodeEncodeError as e:
            app_log.warning('Database query: {} {} {}'.format(cursor, query, param))
            app_log.warning('Database skip reason: {}'.format(e))
            break
        except Exception as e:
            app_log.warning('Database query: {} {} {}'.format(cursor, query, param))
            app_log.warning('Database retry reason: {}'.format(e))
            time.sleep(0.1)
    return cursor


def is_sequence(arg) -> bool:
    # TODO: hard to read compound condition.
    return not hasattr(arg, 'strip') and hasattr(arg, '__getitem__') or hasattr(arg, '__iter__')
