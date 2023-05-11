"""
A class encapsulating a Bismuth wallet (keys, address, crypto functions)

WIP
"""

from base64 import b64encode
import json
# import logging

from os import path
from bismuthclient import bismuthcrypto
from Cryptodome.PublicKey import RSA
# from Cryptodome.Signature import PKCS1_v1_5
# from Cryptodome.Hash import SHA
# import getpass
# import hashlib

__version__ = '0.0.41'


class BismuthWallet():

    __slots__ = ('_address', '_wallet_file', 'verbose', '_encrypted', '_infos', "verbose", "key", "public_key")

    def __init__(self, wallet_file='wallet.der', verbose=False):
        self._wallet_file = None
        self._address = None
        self._infos = None
        self.key = None
        self.public_key = ''
        self.verbose = verbose
        self.load(wallet_file)

    def wallet_preview(self, wallet_file='wallet.der'):
        """
        Returns info about a wallet without actually loading it.
        """
        info = {'file': wallet_file, 'address': '', 'encrypted': False}
        try:
            with open(wallet_file, 'r') as f:
                content = json.load(f)
            info['address'] = content['Address']  # Warning case change!!!
            try:
                key = RSA.importKey(content['Private Key'])
                info['encrypted'] = False
            except:  # encrypted
                info['encrypted'] = True
        except:
            pass
        return info

    def info(self):
        """
        Returns a dict with info about the current wallet.
        :return:
        """
        return self._infos

    def load(self, wallet_file='wallet.der'):
        """
        Loads the wallet.der file

        :param wallet_file: string, a wallet file path
        """
        if self.verbose:
            print("Load", wallet_file)
        self._wallet_file = None
        self._address = None
        self._infos = {"address": '', 'file': wallet_file, 'encrypted': False}
        if not path.isfile(wallet_file):
            return

        self._wallet_file = wallet_file
        with open(wallet_file, 'r') as f:
            content = json.load(f)
            self._infos['address'] = content['Address']  # Warning case change!!!
            self._address = content['Address']
        try:
            self.key = RSA.importKey(content['Private Key'])
            self.public_key = content['Public Key']
        except:  # encrypted
            self._infos['encrypted'] = True

    def new(self, wallet_file='wallet.der'):
        """
        Creates a new wallet - only if the given file does not exist yet.
        Does not load it.

        :param wallet_file: string, a wallet file path
        :return True or False depending on the op success
        """
        if self.verbose:
            print("create", wallet_file)
        if path.isfile(wallet_file):
            if self.verbose:
                print("{} Already exists, canceled".format(wallet_file))
            return False
        bismuthcrypto.keys_new(wallet_file)
        return True


    @property
    def address(self):
        """Returns the currently loaded address, or None"""
        return self._address

    def sign_encoded(self, timestamp: float, address: str, recipient: str, amount:float, operation: str, data: str) -> str:
        if address != self._address:
            raise RuntimeWarning("Address mismatch {} vs {}".format(address, self._address))
        signature_enc = bismuthcrypto.sign_with_key(timestamp, address, recipient, amount, operation, data, self.key)
        return signature_enc

    def get_encoded_pubkey(self) -> str:
        """Returns the pubkey encoded as the net wants it"""
        pubkey = b64encode(self.public_key.encode('utf-8')).decode("utf-8")
        return pubkey
