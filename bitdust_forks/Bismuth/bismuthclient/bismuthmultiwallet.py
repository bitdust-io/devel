"""
A class encapsulating a Bismuth wallet (keys, address, crypto functions)

This is a wallet.json file that can embed many different addresses/keys and is globally encrypted by a master password.


"""

from base64 import b64encode, b64decode
import json
import random
from copy import deepcopy

from os import path
from time import time
from bismuthclient import bismuthcrypto
from bismuthclient.simplecrypt import encrypt, decrypt
from Cryptodome.PublicKey import RSA
# from Cryptodome.Signature import PKCS1_v1_5
# from Cryptodome.Hash import SHA256
# import getpass
# import hashlib
from hashlib import sha224
import os, sys

__version__ = '0.0.63'


class BismuthMultiWallet():

    __slots__ = ('_address', '_wallet_file', 'verbose', '_infos', "verbose", "key", "public_key",
                 '_addresses', '_locked', '_data', '_master_password', 'key_type')

    def __init__(self, wallet_file: str='wallet.json', verbose: bool=False, seed: str=None):
        self._wallet_file = None
        self._address = None
        self._infos = None
        self.key = None
        self.key_type = "RSA"
        self._data = None  # raw data
        self._locked = False
        self.public_key = ''
        self.verbose = verbose
        self._addresses = []  # clear data if unlocked
        self._master_password = ''
        self.load(wallet_file, seed=seed)

    def wallet_preview(self, wallet_file: str='wallet.der'):
        """
        Returns info about a LEGACY wallet without actually loading it.
        """
        """
        info = {'file': wallet_file, 'address': '', 'encrypted': False, 'count': 0}
        try:
            with open(wallet_file, 'r') as f:
                content = json.load(f)
            info['count'] = len(content['addresses'])
            info['encrypted'] = len(content['encrypted'])
        except:
            pass
        return info
        """
        info = {'file': wallet_file, 'address': '', 'encrypted': False, 'old': False}

        try:
            with open(wallet_file, 'r') as f:
                line1 = f.readline()
                if line1.startswith("-----BEGIN RSA PRIVATE KEY-----"):
                    print(wallet_file, "OLD")
                    info["old"] = True
            if info["old"]:
                with open(wallet_file, 'r') as f:
                    content = f.read()
                    key = RSA.importKey(content)
                    public_key_readable = key.publickey().exportKey().decode("utf-8")
                    address = sha224(public_key_readable.encode("utf-8")).hexdigest()  # hashed public key
                info["address"] = address
            else:
                with open(wallet_file, 'r') as f:
                    content = json.load(f)
                info['address'] = content['Address']  # Warning case change!!!
                try:
                    # This is a validity check, will break if not a proper rsa key
                    key = RSA.importKey(content['Private Key'])
                    info['encrypted'] = False
                except:  # encrypted
                    info['encrypted'] = True
        except Exception as e:
            print(f"Error reading {wallet_file}: {e}")
            print(e)
            pass
        return info

    def info(self):
        """
        Returns a dict with info about the current wallet.
        :return:
        """
        self._infos['count'] = len(self._data['addresses'])
        return self._infos

    def load(self, wallet_file: str='wallet.json', seed: str=None):
        """
        Loads the wallet.json file

        :param wallet_file: string, a wallet file path
        :param seed: None or string, an optional seed for reproducible tests. Do NOT use in prod.
        """
        if self.verbose:
            print("Load Multi", wallet_file)
        self._wallet_file = None
        self._address = None
        self._infos = {"address": '', 'file': wallet_file, 'encrypted': False}
        if seed:
            random.seed(seed)
        if not path.isfile(wallet_file):
            charset = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ&~#{([|-\_@)]=}+-*/<>!,;:.?%'
            salt = "".join(random.choice(charset) for x in range(random.randint(10, 20)))
            default = {"salt": salt, "spend": {"type": None, "value": None},
                       "version": __version__, "coin": "bis", "encrypted": False,
                       "addresses": []}
            with open(wallet_file, 'w') as f:
                json.dump(default, f)

        with open(wallet_file, 'r') as f:
            self._data = json.load(f)
            # No selected address by default.
            self._infos['address'] = ''
            self._address = ''
        self._infos['encrypted'] = self._data['encrypted']
        self._infos['spend'] = self._data['spend']
        self._wallet_file = wallet_file
        # If our wallet
        self._locked = self._data['encrypted']
        self._master_password = ''
        if not self._locked:
            self._addresses = deepcopy(self._data['addresses'])
            try:
                self._address = self._addresses[0]['address']
            except:
                self._address = None
        else:
            self._addresses = []
            self._address = None

    def save(self, wallet_file: str=None):
        if wallet_file is None:
            wallet_file = self._wallet_file
        with open(wallet_file, 'w') as f:
            json.dump(self._data, f, indent=4)

    def password_ok(self, password: str):
        return password == self._master_password

    def encrypt(self, password:str='', current_password:str=None):
        """Encrypt - or re-encrypt """
        if len(self._addresses) <= 0:
            raise RuntimeWarning("Can't encrypt empty wallet.")
        if self._locked:
            raise RuntimeWarning("Can't encrypt locked down wallet.")
        if self._infos['encrypted']:
            # TODO
            raise RuntimeWarning("TODO: decrypt and re-encrypt - WIP")
        encrypted_addresses = []
        try:
            for address in self._addresses:
                content = json.dumps(address)
                encrypted_addresses.append(b64encode(encrypt(password, content, level=1)).decode('utf-8'))
            encrypted = b64encode(encrypt(password, json.dumps(self._data['spend']), level=2)).decode('utf-8')

            self._data['addresses'] = encrypted_addresses
            self._data['encrypted'] = True
            self._data['spend'] = encrypted
            self.save()
            self._master_password = password
            self._infos['encrypted'] = True
            self._locked = False
        except:
            raise

    def lock(self):
        """Lock the wallet"""
        if not self._data['encrypted']:
            raise RuntimeWarning("You have to encrypt your wallet first to use this feature")
        if len(self._addresses) <= 0:
            raise RuntimeWarning("Can't lock empty wallet.")
        self._master_password = ''      # forget the pass
        self._locked = self._data['encrypted']
        if self._locked:
            # If wallet was encrypted, then forget the addresses also.
            self._addresses = []
            self._address = None

    def unlock(self, password:str):
        """Sets the master password and unlocks the wallet"""
        if not self._locked:
            return
        if not self._infos['encrypted']:
            return
        # decrypt the addresses and keys
        try:
            addresses = []
            for address in self._data['addresses']:
                decoded = json.loads(decrypt(password, b64decode(address.encode('utf-8'))).decode('utf-8'))
                addresses.append(decoded)
            self._addresses = addresses
            self._master_password = password
            self._locked = False
            # Now decode the spend
            decoded = json.loads(decrypt(password, b64decode(self._data['spend'].encode('utf-8'))).decode('utf-8'))
            self._infos['spend'] = decoded
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            raise RuntimeWarning("Password does not seem to match")

    def new(self, wallet_file='wallet.der'):
        """
        Creates a new wallet - only if the given file does not exist yet.
        Does not load it.

        :param wallet_file: string, a wallet file path
        :return True or False depending on the op success
        """
        raise RuntimeWarning("Not to be used in multi context")
        """
        if self.verbose:
            print("create", wallet_file)
        if path.isfile(wallet_file):
            if self.verbose:
                print("{} Already exists, canceled".format(wallet_file))
            return False
        bismuthcrypto.keys_new(wallet_file)
        return True
        """

    def new_address(self, label: str='', password: str='', salt: str='', type="RSA"):
        """
        Add a new address to the wallet (and save it)
        """
        if type != "RSA":
            raise RuntimeError("Only RSA is available for now")
        if self._infos['encrypted'] and self._locked:
            raise RuntimeError("Wallet must be unlocked")
        keys = bismuthcrypto.keys_gen(password=password, salt=salt)
        keys['label'] = label
        keys['timestamp'] = int(time())
        self._addresses.append(keys)
        if self._infos['encrypted']:
            content = json.dumps(keys)
            encrypted = b64encode(encrypt(self._master_password, content, level=1)).decode('utf-8')
            self._data['addresses'].append(encrypted)
        else:
            print('1')
            self._data['addresses'].append(keys)
        self.save()

    def set_label(self, address:str ='', label: str=''):
        """
        Set a label for given address
        """
        if self._infos['encrypted'] and self._locked:
            raise RuntimeError("Wallet must be unlocked")
        #print(self._data['addresses'])
        for i, single_address in enumerate(self._addresses):
            if single_address['address'] == address:
                #
                self._addresses[i]['label'] = label
                if self._infos['encrypted'] and self._master_password:
                    content = json.dumps(self._addresses[i])
                    encrypted = b64encode(encrypt(self._master_password, content, level=1)).decode('utf-8')
                    self._data['addresses'][i] = encrypted
                else:
                    self._data['addresses'][i]['label'] = label
        self.save()

    def set_spend(self, spend_type:str, spend_value: str, password: str=''):
        """Saves the spend protection if the pass is ok"""
        if not self.password_ok(password):
            raise RuntimeWarning("Password does not seem to match")
        if spend_type == 'None':
            spend_type = None
        spend = {'type': spend_type, 'value': spend_value}
        if self._infos['encrypted']:
            content = json.dumps(spend)
            encrypted = b64encode(encrypt(self._master_password, content, level=2)).decode('utf-8')
            self._data['spend'] = encrypted
        else:
            self._data['spend'] = spend
        self._infos['spend'] = spend
        self.save()

    def get_der_key(self, wallet_file: str='wallet.der', password: str=''):
        try:
            old = False
            with open(wallet_file, 'r') as f:
                line1 = f.readline()
                if line1.startswith("-----BEGIN RSA PRIVATE KEY-----"):
                    # print(wallet_file, "OLD")
                    old = True
            if old:
                with open(wallet_file, 'r') as f:
                    content = f.read()
                    key = RSA.importKey(content)
                    public_key_readable = key.publickey().exportKey().decode("utf-8")
                    address = sha224(public_key_readable.encode("utf-8")).hexdigest()  # hashed public key
                return {"private_key": content, "public_key": public_key_readable, "address": address, "label": '',
                        'timestamp': int(time())}
            else:
                with open(wallet_file, 'r') as f:
                    content = json.load(f)
                    if password:
                        content['Private Key'] = decrypt(password,b64decode(content['Private Key'])).decode('utf-8')
                    key = RSA.importKey(content['Private Key'])
                    public_key = content['Public Key']
                    private_key = content['Private Key']
                    address = content["Address"]
                    # TODO: check that address matches rebuilded pubkey
                    return {"private_key": private_key, "public_key": public_key, "address": address, "label":'',
                            'timestamp': int(time())}
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            # encrypted
            return None

    def set_address(self, address: str=''):
        """Select an address from the wallet"""
        if self._infos['encrypted'] and self._locked:
            # TODO: check could be done via a decorator
            raise RuntimeError("Wallet must be unlocked")
        if not self.is_address_in_wallet(address):
            raise RuntimeError("Duplicate address")
        key = self.get_key(address)
        # print("key", key)
        key_type = key.get('type', "RSA")
        if key_type == "RSA":
            self.key_type = "RSA"
            self.key = RSA.importKey(key['private_key'])
            self.public_key = key['public_key']
        elif key_type == "ECDSA":
            self.key_type = "ECDSA"
            self.key = key['private_key']
            self.public_key = key['public_key']
        else:
            raise RuntimeError("Unknown address type")
        self._address = address
        self._infos['address'] = address

    def is_address_in_wallet(self, address: str=''):
        if self._infos['encrypted'] and self._locked:
            # TODO: check could be done via a decorator
            raise RuntimeError("Wallet must be unlocked")
        for key in self._addresses:
            if address == key['address']:
                return True
        return False

    def get_key(self, address: str=''):
        if self._infos['encrypted'] and self._locked:
            # TODO: check could be done via a decorator
            raise RuntimeError("Wallet must be unlocked")
        for key in self._addresses:
            if address == key['address']:
                return key
        return None

    def import_der(self, wallet_der: str='wallet.der', label: str='', source_password: str=''):
        """Import an existing wallet.der like file into the wallet"""
        if self._infos['encrypted'] and self._locked:
            # TODO: check could be done via a decorator
            raise RuntimeError("Wallet must be unlocked")
        key = self.get_der_key(wallet_der, password=source_password)
        if not key:
            raise RuntimeWarning("Error importing the der file")
        key['label'] = label
        if self.is_address_in_wallet(key['address']):
            raise RuntimeError("Duplicate address")
        self._addresses.append(key)
        if self._infos['encrypted']:
            content = json.dumps(key)
            encrypted = b64encode(encrypt(self._master_password, content, level=1)).decode('utf-8')
            self._data['addresses'].append(encrypted)
        else:
            print('1')
            self._data['addresses'].append(key)
        self.save()

    def get_ecdsa_key(self, private_key: str):
        """
        Returns a key dict from an ecdsa privatekey
        :param private_key:
        :return:
        """
        # print(private_key, len(private_key))
        if len(private_key) != 64:
            raise RuntimeWarning("Error importing the ECDSA pk, len != 64")
        try:
            signer = bismuthcrypto.ecdsa_pk_to_signer(private_key)
            # print("signer", signer)
            public_key = signer['public_key']
            address = signer["address"]
            # TODO: check that address matches rebuilded pubkey
            return {"private_key": private_key, "public_key": public_key, "address": address, "label":'',
                    'timestamp': int(time())}
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            # encrypted
            return None

    def import_ecdsa_pk(self, private_key: str, label: str=''):
        """Import an existing wallet.der like file into the wallet"""
        if self._infos['encrypted'] and self._locked:
            # TODO: check could be done via a decorator
            raise RuntimeError("Wallet must be unlocked")
        key = self.get_ecdsa_key(private_key)
        if not key:
            raise RuntimeWarning("Error importing the ECDSA pk.")
        key['label'] = label
        key['type'] = 'ECDSA'
        if self.is_address_in_wallet(key['address']):
            raise RuntimeError("Duplicate address")
        self._addresses.append(key)
        if self._infos['encrypted']:
            content = json.dumps(key)
            encrypted = b64encode(encrypt(self._master_password, content, level=1)).decode('utf-8')
            self._data['addresses'].append(encrypted)
        else:
            print('1')
            self._data['addresses'].append(key)
        self.save()

    def sign_encoded(self, timestamp: float, address:str, recipient:str, amount:float, operation:str, data:str) -> str:
        if address != self._address:
            raise RuntimeWarning("Address mismatch {} vs {}".format(address, self._address))
        signature_enc = None
        if self.key_type == 'RSA':
            signature_enc = bismuthcrypto.sign_with_key(timestamp, address, recipient, amount, operation, data, self.key)
        elif self.key_type == 'ECDSA':
            signature_enc = bismuthcrypto.sign_with_ecdsa_key(timestamp, address, recipient, amount, operation, data, self.key)
        else:
            raise RuntimeWarning("Error unknown key type")
        return signature_enc

    def get_encoded_pubkey(self) -> str:
        """Returns the pubkey encoded as the net wants it, whatever the key format"""
        pubkey = None
        if self.key_type == 'RSA':
            pubkey = b64encode(self.public_key.encode('utf-8')).decode("utf-8")
        elif self.key_type == 'ECDSA':
            # public_key_hex = signer.to_dict()["public_key"]
            pubkey = b64encode(bytes.fromhex(self.public_key)).decode("utf-8")
        elif self.key_type == 'ED25519':
            # public_key_hex = signer.to_dict()["public_key"]
            pubkey = b64encode(bytes.fromhex(self.public_key)).decode("utf-8")
        else:
            raise RuntimeWarning("Error unknown key type")
        return pubkey

    @property
    def address(self):
        """Returns the currently loaded address, or None"""
        return self._address
