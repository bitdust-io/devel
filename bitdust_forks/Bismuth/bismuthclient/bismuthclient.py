"""
A all in one Bismuth Native client that connects to local or distant wallet servers
"""

import base64
import json
import logging
import threading
from time import time
import sys
import os
from datetime import timedelta

# from bismuthclient import async_client
from bismuthclient import bismuthapi
from bismuthclient.bismuthwallet import BismuthWallet
from bismuthclient.bismuthmultiwallet import BismuthMultiWallet
from bismuthclient import bismuthcrypto
from bismuthclient import rpcconnections
from bismuthclient import lwbench
from bismuthclient.bismuthformat import TxFormatter, AmountFormatter
from os import path, scandir

__version__ = '0.0.52'

# Hardcoded list of addresses that need a message, like exchanges.
# qtrade, tradesatoshi, old cryptopia, graviex
REJECT_EMPTY_MESSAGE_FOR = ['f6c0363ca1c5aa28cc584252e65a63998493ff0a5ec1bb16beda9bac',
                            '49ca873779b36c4a503562ebf5697fca331685d79fd3deef64a46888',
                            'edf2d63cdf0b6275ead22c9e6d66aa8ea31dc0ccb367fad2e7c08a25',
                            '14c1b5851634f0fa8145ceea1a52cabe2443dc10350e3febf651bd3a']
# for test
# REJECT_EMPTY_MESSAGE_FOR.append('0634b5046b1e2b6a69006280fbe91951d5bb5604c6f469baa2bcd840')


class BismuthClient():

    __slots__ = ('initial_servers_list', 'servers_list', 'app_log', '_loop', 'address', '_current_server',
                 'wallet_file', '_wallet', '_connection', '_cache', 'verbose', 'full_servers_list', 'time_drift',
                 '_alias_cache', '_alias_cache_file')

    def __init__(self, servers_list=None, app_log=None, loop=None, wallet_file='', verbose=False):
        """
        Init the main class.

        :param servers_list: list of "ip:port" wallet servers
        :param app_log:
        :param loop: None of an asyncio loop
        :param address:
        """
        self.verbose = verbose
        if not servers_list:
            servers_list = []
        self.initial_servers_list = servers_list
        if app_log:
            self.app_log = app_log
        elif logging.getLogger("tornado.application"):
            self.app_log = logging.getLogger("tornado.application")
        else:
            self.app_log = logging
        self._loop = loop
        self.wallet_file = None
        self._wallet = None
        self.address = None
        self.load_wallet(wallet_file)
        self.servers_list = servers_list
        self.full_servers_list = None
        self._current_server = None
        self._connection = None
        self._cache = {}
        # address: [alias, expiration_ts]
        self._alias_cache = {}
        self._alias_cache_file = None
        # Difference between local time and server time.
        self.time_drift = 0

    # Alias functions

    def set_alias_cache_file(self, filename:str):
        """Define an optional file for persistent storage of alias data"""
        self._alias_cache_file = filename
        # Try to load
        if path.isfile(filename):
            with open(filename) as f:
                self._alias_cache = json.load(f)

    def get_aliases_of(self, addresses: list) -> dict:
        """Get alias from a list of addresses. returns a dict {address:alias (or '')}"""
        # Filter out the ones from valid cache
        now = time()
        addresses = set(addresses)  # dedup
        cached = { address: self._alias_cache[address][0] for address in addresses if address in self._alias_cache and self._alias_cache[address][1] > now}
        # print("cached", cached)
        # Ask for the rest.
        unknown = [address for address in addresses if address not in cached]
        aliases = self.command("aliasesget", [unknown])
        # Returns a list of aliases (or addresses if no alias)
        # print("aliases", aliases)
        new = dict(zip(unknown, aliases))
        for address, alias in new.items():
            # cache empty ones for 1 hour, existing ones for a day.
            if address == alias:
                self._alias_cache[address] = [alias, now + 3600]
            else:
                self._alias_cache[address] = [alias, now + 3600 * 24]
        # save cache if alias_cache_file is defined
        if self._alias_cache_file:
            with open(self._alias_cache_file, 'w') as fp:
                json.dump(self._alias_cache, fp)
        # return merge
        return {**cached, **new}

    def has_alias(self, address):
        """Does this address have an alias? - not the most efficient, prefer get_aliases_of for batch ops."""
        return self.get_aliases_of([address]) != ''

    def alias_exists(self, alias):
        """Does this alias exists?"""
        # if we have in cache, it does.
        for address, info in self._alias_cache:
            if info[0] == alias:
                return True
        # if not, ask the chain (do not cache there)
        return self.command("aliascheck", [alias])

    # End of alias functions

    def _get_cached(self, key, timeout_sec=30):
        if key in self._cache:
            data = self._cache[key]
            if data[0] + timeout_sec >= time():
                """                
                if self.verbose:
                    self.app_log.info("Cache Hit on {}".format(key))
                    # print(data[1])
                """
                return data[1]
        return None

    def _set_cache(self, key, value):
        self._cache[key] = (time(), value)

    def clear_cache(self):
        self._cache = {}

    @property
    def current_server(self):
        return self._current_server

    @staticmethod
    def user_subdir(subdir):
        """Returns a path to subdir in the user data directory. Path will be created if it does not exist."""
        home = os.path.expanduser('~')
        location = os.path.join(home, subdir)
        if not os.path.isdir(location):
            os.makedirs(location, exist_ok=True)
        return location

    def list_wallets(self, scan_dir='wallets'):
        """
        Returns a list of dict for each wallet file found in the dir to scan.

        Each dict has the following keys: 'file', 'address', 'encrypted'

        :param scan_dir: string, the dir to scan for wallet (*.der files).
        """
        wallets = []
        for entry in scandir(scan_dir):
            # print(entry)
            if entry.name.endswith('.der') and entry.is_file():
                wallets.append(self._wallet.wallet_preview(entry.path))
        # TODO: sorts by name
        return wallets

    def latest_transactions(self, num=10, offset=0, for_display=False, mempool_included=False):
        """
        Returns the list of the latest num transactions for the current address.
        if mempool_inc is True, also return (in addition to num, start of the list) the tx currently in mempool.

        Each transaction is a dict with the following keys:
        `["block_height", "timestamp", "address", "recipient", "amount", "signature", "public_key", "block_hash", "fee", "reward", "operation", "openfield"]`
        """
        if not self.address or not self._wallet:
            return []
        try:
            key = "tx{}-{}".format(num, offset)
            cached = self._get_cached(key)
            if cached:
                return cached
            if offset == 0:
                transactions = self.command("addlistlim", [self.address, num])
            else:
                transactions = self.command("addlistlimfrom", [self.address, num, offset])
            if mempool_included:
                transactions_mempool = self.command("mpgetfor", [self.address])
                transactions_mempool.extend(transactions)
                transactions = transactions_mempool
            # print(transactions)
        except:
            # TODO: Handle retry, at least error message.
            transactions = []

        #json = [dict(zip(["block_height", "timestamp", "address", "recipient", "amount", "signature", "public_key", "block_hash", "fee", "reward", "operation", "openfield"], tx)) for tx in transactions]
        json = [TxFormatter(tx).to_json(for_display=for_display) for tx in transactions]
        # print(json)
        self._set_cache(key, json)
        return json

    def search_transactions(self, address=None, recipient=None, operation=None, openfield=None, limit=10, offset=0, block_height_from=None):
        key = "txsearch-{}-{}-{}-{}-{}-{}-{}".format(
            address or '*',
            recipient or '*',
            operation or '*',
            openfield or '*',
            limit,
            offset,
            block_height_from or 0,
        )
        cached = self._get_cached(key)
        if cached:
            return cached
        transactions = self.command("txsearch", [(address, recipient, operation, openfield, limit, offset, block_height_from, ), ])
        if self.verbose:
            print('Client: search transactions', key, transactions)
        json = [TxFormatter(tx).to_json(for_display=True) for tx in transactions]
        self._set_cache(key, json)
        return json

    def balance(self, for_display=False):
        """
        Returns the current balance for the current address.
        """
        if not self.address or not self._wallet:
            return 'N/A'
        try:
            balance = self._get_cached('balance')
            if not balance:
                balance = self.command("balanceget", [self.address])[0]
                self._set_cache('balance', balance)
                balance = self._get_cached('balance')
        except Exception as e:
            if self.verbose:
                print('Client: balance error', e)
            return 'N/A'
        if for_display:
            balance = AmountFormatter(balance).to_string(leading=0)
        if balance == '0E-8':
            balance = 0.000
        return balance

    def global_balance(self, for_display=False):
        """
        Returns the current global balance for all addresses of current multiwallet.
        """
        if not type(self._wallet) == BismuthMultiWallet:
            raise RuntimeWarning("Not a Multiwallet")
        if not self.address or not self._wallet:
            return 'N/A'
        try:
            address_list = [add['address'] for add in self._wallet._addresses]
            # print('al', address_list)
            balance = self.command("globalbalanceget", [address_list])
            # print('balance', balance)
            balance = balance[0]
        except:
            # TODO: Handle retry, at least error message.
            balance = -1  # -1 means "N/A" for AmountFormatter
        if for_display:
            balance = AmountFormatter(balance).to_string(leading=0)
        if balance == '0E-8':
            balance = 0.000
        return balance

    def all_balances(self, for_display=False) -> dict:
        """
        Returns the balance for every single addresses of current multiwallet.
        Time and resource consuming, avoid using this call for the moment!
        """
        if not type(self._wallet) == BismuthMultiWallet:
            raise RuntimeWarning("Not a Multiwallet")
        if not self.address or not self._wallet:
            return 'N/A'
        balances = {}
        for i in range(3):  # retries
            try:
                # balances = {add['address']: self.command("balanceget", [add['address']])[0] for add in self._wallet._addresses}
                for add in self._wallet._addresses:
                    if add['address'] not in balances:
                        balances[add['address']] = self.command("balanceget", [add['address']])[0]
            except Exception as e:
                # TODO: Handle retry, at least error message.
                if self.verbose:
                    print("Client: Error {} all_balances".format(str(e)))

        if for_display:
            balances = {address: AmountFormatter(balance).to_string(leading=0) for address, balance in balances.items()}
        return balances

    @classmethod
    def reject_empty_message_for(self, address: str) -> bool:
        """Hardcoded list."""
        return address in REJECT_EMPTY_MESSAGE_FOR

    def send(self, recipient: str, amount: float, operation: str='', data: str='', error_reply: list=None):
        """
        Sends the given tx
        """
        error_reply = [] if error_reply is None else error_reply
        try:
            timestamp = time()
            if self.time_drift > 0:
                # we are more advanced than server, fix and add 0.1 sec safety
                timestamp -= (self.time_drift + 0.1)
                # This is to avoid "rejected transaction because in the future
            # public_key_encoded = base64.b64encode(self._wallet.public_key.encode('utf-8'))
            public_key_encoded = self._wallet.get_encoded_pubkey()

            # signature_enc = bismuthcrypto.sign_with_key(timestamp, self.address, recipient, amount, operation, data, self._wallet.key)
            signature_enc = self._wallet.sign_encoded(timestamp, self.address, recipient, amount, operation, data)

            txid = signature_enc[:56]
            tx_submit = ( '%.2f' % timestamp, self.address, recipient, '%.8f' % float(amount),
                          signature_enc, public_key_encoded, operation, data)
            reply = self.command('mpinsert', [tx_submit])
            if self.verbose:
                print("Client: Server replied '{}'".format(reply))
            if reply[-1] != "Success":
                if self.verbose:
                    print("Client: Error '{}'".format(reply))
                error_reply.append(reply[-1])
                return None
            if not reply:
                if self.verbose:
                    print("Client: Server timeout")
                error_reply.append('Server timeout')
                return None
            return txid
        except Exception as e:
            error_reply.append(str(e))
            if self.verbose:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print('Client:', exc_type, fname, exc_tb.tb_lineno)
            return None

    def sign(self, message: str):
        """
        Signs the given message
        """
        try:
            signature = bismuthcrypto.sign_message_with_key(message, self._wallet.key)
            return signature
        except Exception as e:
            if self.verbose:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print('Client:', exc_type, fname, exc_tb.tb_lineno)
            raise

    def encrypt(self, message: str, recipient:str):
        """
        Encrypts the given message for the recipient
        """
        try:
            # Fetch the pubkey of the recipient
            pubkey = self.command('pubkeyget', [recipient])
            # print("pubkey", pubkey, recipient)
            encrypted = bismuthcrypto.encrypt_message_with_pubkey(message, pubkey)
            return encrypted
        except Exception as e:
            if self.verbose:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print('Client:', exc_type, fname, exc_tb.tb_lineno)
            raise

    def decrypt(self, message: str):
        """
        Decrypts the given message
        """
        try:
            decrypted = bismuthcrypto.decrypt_message_with_key(message, self._wallet.key)
            return decrypted
        except Exception as e:
            if self.verbose:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print('Client:', exc_type, fname, exc_tb.tb_lineno)
            raise

    def status(self):
        """
        Returns the current status of the wallet server
        """
        try:
            cached = self._get_cached('status')
            if cached:
                return cached
            status = self.command("statusjson")
            # print("getstatus", status)
            try:
                status['uptime_human'] = str(timedelta(seconds=status['uptime']))
            except Exception as e:
                status['uptime_human'] = 'N/A'
            try:
                status['extended'] = self.command("wstatusget")
            except:
                status['extended'] = None

            if 'server_timestamp' in status:
                self.time_drift = time() - float(status['server_timestamp'])
            else:
                self.time_drift = 0
            status['time_drift'] = self.time_drift

            self._set_cache('status', status)
        except Exception as e:
            # TODO: Handle retry, at least error message.
            if self.verbose:
                print('Client: Command status failed', e)
            status = {}
        return status

    def load_wallet(self, wallet_file='wallet.der'):
        """
        Tries to load the wallet file

        :param wallet_file: string, a wallet.der file
        """
        # Default values, fail
        self.wallet_file = None
        self.address = None
        self._wallet = None
        self._wallet = BismuthWallet(wallet_file, verbose=self.verbose)
        self.wallet_file = wallet_file
        if self.address != self._wallet.address:
            self.clear_cache()
        self.address = self._wallet.address

    # def load_multi_wallet(self, wallet_file='wallet.json'):
    #     """
    #     Tries to load the wallet file
    #
    #     :param wallet_file: string, a wallet.json file
    #     """
    #     # TODO: Refactor
    #     self.wallet_file = None
    #     self.address = None
    #     self._wallet = None
    #     self._wallet = BismuthMultiWallet(wallet_file, verbose=self.verbose)
    #     if len(self._wallet._data["addresses"]) == 0:
    #         # Create a first address by default
    #         self._wallet.new_address(label="default")
    #     self.wallet_file = wallet_file
    #     if self.address != self._wallet.address:
    #         self.clear_cache()
    #     self.address = self._wallet.address

    def set_address(self, address: str=''):
        if not type(self._wallet) == BismuthMultiWallet:
            raise RuntimeWarning("Not a Multiwallet")
        self._wallet.set_address(address)
        if self.address != self._wallet.address:
            self.clear_cache()
        self.address = self._wallet.address

    def new_wallet(self, wallet_file='wallet.der'):
        """
        Creates a new wallet if it does not already exists

        :param wallet_file: string, a wallet.der file
        """
        # Default values, fail
        wallet = BismuthWallet(wallet_file, verbose=self.verbose)
        return wallet.new(wallet_file)

    def wallet(self, full=False):
        """
        returns info about the currently loaded wallet

        if full is True, also force a check of the current balance.
        """
        return self._wallet.info()

    def info(self):
        """
        returns a dict with server info: ip, port, latest server status
        """
        connected = False
        if self._connection:
            connected = bool(self._connection.sdef)
        info = {"wallet": self.wallet_file, "address": self.address, "server": self._current_server,
                "servers_list": self.servers_list, "full_servers_list": self.full_servers_list,
                "connected": connected}
        return info

    def get_server(self):
        """
        Tries to find the best available server given the config and sets self._current_server for later use.

        Returns the first connectible server.
        """
        # Use the API or bench to get the best one.
        if not len(self.initial_servers_list):
            self.full_servers_list = bismuthapi.get_wallet_servers_legacy(self.initial_servers_list, self.app_log, minver='0.1.5', as_dict=True)
            self.servers_list=["{}:{}".format(server['ip'], server['port']) for server in self.full_servers_list]
            # print('Client: servers_list=%r full_servers_list=%r' % (self.servers_list, self.full_servers_list))
        else:
            self.servers_list = self.initial_servers_list
            self.full_servers_list = [{"ip": server.split(':')[0], "port": server.split(':')[1],
                                       'load':'N/A', 'height': 'N/A'} for server in self.servers_list]
            # print('Client: from initial servers_list=%r full_servers_list=%r' % (self.servers_list, self.full_servers_list))
        # Now try to connect
        if self.verbose:
            print("Client: servers list", self.servers_list)
        for server in self.servers_list:
            # if self.verbose:
            #     print("test server", server)
            if lwbench.connectible(server):
                self._current_server = server
                # TODO: if self._loop, use async version
                if self.verbose:
                    print("Client: connect server", server)
                self._connection = rpcconnections.Connection(server, verbose=self.verbose)
                if self.verbose:
                    print('Client: new connection %r to %r' % (self._connection, server))
                return server
        self._current_server = None
        self._connection = None
        # TODO: raise
        return None

    def refresh_server_list(self):
        """
        Gets info from api, add to previous config list.
        :return:
        """
        backup = list(self.full_servers_list)
        self.full_servers_list = bismuthapi.get_wallet_servers_legacy(self.initial_servers_list, self.app_log,
                                                                      minver='0.1.5', as_dict=True)
        for server in backup:
            is_there = False
            for present in self.full_servers_list:
                if server['ip'] == present['ip'] and server['port'] == present['port']:
                    is_there=True
            if not is_there:
                self.full_servers_list.append(server)
        self.servers_list = ["{}:{}".format(server['ip'], server['port']) for server in self.full_servers_list]
        if self.verbose:
            print('Client: refresh servers_list=%r full_servers_list=%r' % (self.servers_list, self.full_servers_list))

    def set_server(self, ipport):
        """
        Tries to connect and use the given server
        :param ipport:
        :return:
        """
        if not lwbench.connectible(ipport):
            self._current_server = None
            self._connection = None
            return False
        self._current_server = ipport
        # TODO: if self._loop, use async version
        # if self.verbose:
        #     print("connect server", ipport)
        self._connection = rpcconnections.Connection(ipport, verbose=self.verbose)
        return ipport

    def command(self, command, options=None):
        """
        Makes sure we have a connection, runs a command and sends back the result.

        :param command: the command as a string
        :param options: optional options to the command, as a list if needed
        :return: the result as a native structure
        """
        # if self.verbose:
        #     print('Sending Bismuth command', command, self._connection, id(self._connection), threading.current_thread())
        if not self._current_server:
            # TODO: failsafe if can't connect
            self.get_server()
        if not self._connection:
            raise Exception('Connection to Bismuth node was not opened')
        ret = self._connection.command(command, options)
        if self.verbose:
            print('Client: command=%s ret=%r options=%r' % (command, ret, options))
        self._connection.close()
        return ret
