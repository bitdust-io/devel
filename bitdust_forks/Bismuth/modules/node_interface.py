"""
Node interface class for both wallet server (tcp) and websocket wallet server
"""

import json
import time
import datetime
from inspect import signature
from tornado.tcpclient import TCPClient
import tornado
import tornado.gen
import tornado.iostream

from decimal import Decimal
from modules.helpers import replace_regex
from bismuthcore.compat import quantize_eight
from bismuthcore.helpers import fee_calculate, address_validate

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from modules.ledgerbase import LedgerBase

__version__ = '0.0.13'

# Hardcoded list of addresses that need a message, like exchanges.
# qtrade, tradesatoshi, old cryptopia, graviex, finexbox
REJECT_EMPTY_MESSAGE_FOR = [
    'f6c0363ca1c5aa28cc584252e65a63998493ff0a5ec1bb16beda9bac',
    '49ca873779b36c4a503562ebf5697fca331685d79fd3deef64a46888',
    'edf2d63cdf0b6275ead22c9e6d66aa8ea31dc0ccb367fad2e7c08a25',
    '14c1b5851634f0fa8145ceea1a52cabe2443dc10350e3febf651bd3a',
    '1a174d7fdc2036e6005d93cc985424021085cc4335061307985459ce',
]

# TODO: factorize all commands that are sent "as is" to the local node.

TX_KEYS = [
    'block_height',
    'timestamp',
    'address',
    'recipient',
    'amount',
    'signature',
    'public_key',
    'block_hash',
    'fee',
    'reward',
    'operation',
    'openfield',
]


def method_params_count(func):
    return len(signature(func).parameters)


class NodeInterface:
    def __init__(self, mempool, ledger: 'LedgerBase', config, app_log=None):
        self.mempool = mempool
        self.ledger = ledger
        self.cache = {}
        self.config = config
        self.app_log = app_log
        # print(getattr(self,"cached"))
        # print(self.__dict__)
        # print(locals())
        self.user_method_list = {func: method_params_count(getattr(self, func)) for func in dir(self) if callable(getattr(self, func)) and func.startswith('user_')}
        self.admin_method_list = {}
        # print(user_method_list)

    def param_count_of(self, method_name: str, rights):
        """
        returns the number of expected params for this command.
        returns -1 if the rights do not fit or unknown command
        """
        if method_name.startswith('XTRA_'):
            return 0
        if method_name.startswith('TOKEN_'):
            # Hardcoded param counts to avoid multiple calls and only use a forwarder.
            # Limits the possible calls to a single param however (but can be a dict)
            return 1
        if 'user_' + method_name in self.user_method_list:
            return self.user_method_list['user_' + method_name]
        if 'admin' in rights and 'admin_' + method_name in self.admin_method_list:
            return self.admin_method_list['admin_' + method_name]
        # No function or no right
        return -1

    async def call_user(self, args):
        method_name = args.pop(0)
        if method_name.startswith('XTRA_') or method_name.startswith('TOKEN_'):
            # forward_method = method_name.replace('user_', '')
            result = await self.forward(method_name, args)
            return result
        result = await getattr(self, 'user_' + method_name)(*args)
        return result

    async def forward(self, command, param):
        """
        Just forwards the command to the node and sends back the answer.
        Allows to transparently proxy answers from plugins (tokens, nfts)
        """
        # print("forward", command, param)
        stream = None
        try:
            stream = await self._node_stream()
            try:
                await self._send(command, stream)
                await self._send(param, stream)
                res = await self._receive(stream)
                return res
            except KeyboardInterrupt:
                stream.close()
        except Exception as e:
            print(e)
        finally:
            if stream:
                stream.close()

    def cached(self, key, timeout=30):
        if key in self.cache:
            if self.cache[key][0] > time.time() - timeout:
                return True
        return False

    def set_cache(self, key, value):
        self.cache[key] = (time.time(), value)

    async def _node_stream(self):
        return await TCPClient().connect(self.config.node_ip, self.config.node_port)

    async def _receive(self, stream):
        """
        Get a command, async version
        :param stream:
        :param ip:
        :return:
        """
        header = await tornado.gen.with_timeout(
            datetime.timedelta(seconds=35),
            stream.read_bytes(10),
            quiet_exceptions=tornado.iostream.StreamClosedError,
        )
        data_len = int(header)
        data = await tornado.gen.with_timeout(
            datetime.timedelta(seconds=10),
            stream.read_bytes(data_len),
            quiet_exceptions=tornado.iostream.StreamClosedError,
        )
        data = json.loads(data.decode('utf-8'))
        return data

    async def _send(self, data, stream):
        """
        sends an object to the stream, async.
        :param data:
        :param stream:
        :param ip:
        :return:
        """
        try:
            data = str(json.dumps(data))
            header = str(len(data)).encode('utf-8').zfill(10)
            full = header + data.encode('utf-8')
            await stream.write(full)
        except Exception as e:
            self.app_log.error('send_to_stream {}'.format(str(e)))
            raise

    async def user_statusget(self):
        # don't hammer the node, cache recent info
        if self.cached('status'):
            return self.cache['status'][1]
        stream = None
        try:
            # too old, ask the node
            # TODO: factorize all the node forwarding methods
            stream = await self._node_stream()
            try:
                await self._send('statusget', stream)
                res = await self._receive(stream)
                self.set_cache('status', res)
                return res
            except KeyboardInterrupt:
                stream.close()
        except Exception as e:
            print(e)
            # print(CONFIG.node_ip, CONFIG.node_port)
        finally:
            if stream:
                stream.close()

    async def user_statusjson(self):
        # don't hammer the node, cache recent info
        if self.cached('statusjson'):
            return self.cache['statusjson'][1]
        stream = None
        try:
            stream = await self._node_stream()
            try:
                await self._send('statusjson', stream)
                res = await self._receive(stream)
                self.set_cache('statusjson', res)
                return res
            except KeyboardInterrupt:
                stream.close()
        except Exception as e:
            print(e)
        finally:
            if stream:
                stream.close()

    async def user_diffget(self):
        node_status = await self.user_statusget()
        return node_status[8]

    async def user_aliasesget(self, addresses):
        # TODO: local cache of Addresses / Aliases => todo in the wallet ?.
        stream = await self._node_stream()
        try:
            await self._send('aliasesget', stream)
            await self._send(addresses, stream)
            res = await self._receive(stream)
            return res
        except KeyboardInterrupt:
            stream.close()
        finally:
            if stream:
                stream.close()

    async def user_addfromalias(self, alias_resolve):
        # TODO: cache
        stream = await self._node_stream()
        try:
            await self._send('addfromalias', stream)
            await self._send(alias_resolve, stream)
            res = await self._receive(stream)
            return res
        except KeyboardInterrupt:
            stream.close()
        finally:
            if stream:
                stream.close()

    async def user_aliascheck(self, alias_desired):
        stream = await self._node_stream()
        try:
            await self._send('aliascheck', stream)
            await self._send(alias_desired, stream)
            res = await self._receive(stream)
            return res
        except KeyboardInterrupt:
            stream.close()
        finally:
            if stream:
                stream.close()

    async def user_aliasget(self, address):
        # TODO: cache
        stream = await self._node_stream()
        try:
            await self._send('aliasget', stream)
            await self._send(address, stream)
            res = await self._receive(stream)
            return res
        except KeyboardInterrupt:
            stream.close()
        finally:
            if stream:
                stream.close()

    async def user_tokensget(self, address):
        stream = await self._node_stream()
        try:
            await self._send('tokensget', stream)
            await self._send(address, stream)
            res = await self._receive(stream)
            return res
        except KeyboardInterrupt:
            stream.close()
        finally:
            if stream:
                stream.close()

    async def user_mpinsert(self, mp_insert):
        # TODO: factorize with node_aliases above
        recipient = mp_insert[2]
        message = mp_insert[7]
        sig = mp_insert[4]
        if sig[:44] == 'MEQCIBsXIetxHzJFIeQZwqsB6Q0EkVpWm4tIaH1TsePv':
            # potentially buggy sig
            return ['Error: Your mobile wallet needs upgrading - See FAQ']
        # print(recipient, message, sig)
        # TODO: add validity and checksum address for recipient + sender from polysign?
        if len(message) < 5 and recipient in REJECT_EMPTY_MESSAGE_FOR:
            return ['Error: mandatory message for this recipient - See FAQ']
        stream = False
        try:
            stream = await self._node_stream()
            await self._send('mpinsert', stream)
            await self._send(mp_insert, stream)
            res = await self._receive(stream)
            return res
        except KeyboardInterrupt:
            stream.close()
        finally:
            if stream:
                stream.close()

    async def user_blocklast(self):
        if self.cached('blocklast', 30):
            return self.cache['blocklast'][1]
        if not self.ledger.legacy_db:
            raise RuntimeError('V2 BD, Asking user_blocklast')
        if self.config.direct_ledger:
            last = await self.ledger.async_fetchone('SELECT * FROM transactions WHERE reward > 0 '
                                                    'AND block_height = (SELECT max(block_height) FROM transactions) '
                                                    'LIMIT 1', )
        else:
            stream = await self._node_stream()
            try:
                await self._send('blocklast', stream)
                last = await self._receive(stream)
            except KeyboardInterrupt:
                stream.close()
            finally:
                if stream:
                    stream.close()
        self.set_cache('blocklast', last)
        return last

    async def user_mpget(self):
        if self.cached('mpget', 30):
            return self.cache['mpget'][1]
        # too old, really get
        mp = await self.mempool.async_fetchall('SELECT * FROM transactions ORDER BY amount DESC')
        self.set_cache('mpget', mp)
        return mp

    async def user_mpgetjson(self):
        mp = await self.user_mpget()
        return [dict(zip(TX_KEYS, tx)) for tx in mp]

    async def user_mpgetfor(self, address: str):
        """Like mpget, but returns only tx for the given address.
        Uses -1 as block height but keeps same format as real on chain txns"""
        key = 'mpget' + address
        if self.cached(key, 1):
            return self.cache[key][1]
        # too old, really get
        # TODO: make sure wallet server node uses mempool_ram false.
        mp = await self.mempool.async_fetchall(
            'SELECT -1, cast(timestamp as double), address, recipient, amount, '
            "signature, public_key, '', 0, 0, operation, openfield "
            'FROM transactions WHERE address=? or recipient=? '
            'ORDER BY timestamp ASC',
            (address, address),
        )
        self.set_cache(key, mp)
        return mp

    async def user_mpgetforjson(self, address: str):
        """Like mpgetjson, but returns only tx for the given address"""
        mp = await self.user_mpgetfor(address)
        return [dict(zip(TX_KEYS, tx)) for tx in mp]

    async def user_txget(self, transaction_id, addresses=None):
        # TODO: this is intensive. rate limit or cache, but needs a garbage collector in cache function then.
        # New: now also searches in mempool first
        """
        if self.cached("txget", 10):
            return self.cache['txget'][1]
        """
        addresses = [] is addresses is None
        if len(transaction_id) == 2:
            transaction_id, addresses = transaction_id
        if self.config.direct_ledger:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_txget')

            if len(addresses):
                for address in addresses:
                    if not address_validate(address):
                        return ['Ko', f'Error: bad address {address}']
                recipients = "('" + "','".join(addresses) + "')"
                tx = await self.mempool.async_fetchone(
                    'SELECT -1, cast(timestamp as double), address, recipient, amount, signature, public_key, '
                    "'', 0, 0, operation, openfield "
                    'FROM transactions WHERE +recipient IN {} '
                    'AND signature LIKE ?'.format(recipients),
                    (transaction_id + '%', ),
                )
                if tx is None:
                    tx = await self.ledger.async_fetchone('SELECT * FROM transactions WHERE +recipient IN {} AND signature LIKE ?'.format(recipients), (transaction_id + '%', ))
            else:
                tx = await self.mempool.async_fetchone(
                    'SELECT -1, cast(timestamp as double), address, recipient, amount, signature, public_key, '
                    "'', 0, 0, operation, openfield FROM transactions WHERE signature like ?",
                    (transaction_id + '%', ),
                )
                if tx is None:
                    tx = await self.ledger.async_fetchone('SELECT * FROM transactions WHERE signature like ?', (transaction_id + '%', ))
        else:
            return ['Ko', 'Non capable wallet server']
        if tx:
            return tx
        else:
            return ['Ko', 'No such TxId']

    async def user_txgetjson(self, transaction_id, addresses=None):
        tx = await self.user_txget(transaction_id, addresses)
        if len(tx) == 2:
            # error
            return tx
        return dict(zip(TX_KEYS, tx))

    async def user_annverget(self):
        if self.cached('annverget', 60*10):
            return self.cache['annverget'][1]
        ann_ver = ''
        if self.config.direct_ledger:
            ann_addr = self.config.genesis_conf
            try:
                result = await self.ledger.async_fetchone(
                    'SELECT openfield FROM transactions '
                    'WHERE address = ? AND operation = ? '
                    'ORDER BY block_height DESC limit 1',
                    (ann_addr, 'annver'),
                )
                ann_ver = replace_regex(result[0], 'annver=')
            except Exception:
                ann_ver = ''
        else:
            stream = await self._node_stream()
            try:
                await self._send('annverget', stream)
                ann_ver = await self._receive(stream)
            except KeyboardInterrupt:
                stream.close()
            finally:
                if stream:
                    stream.close()
        self.set_cache('annverget', ann_ver)
        return ann_ver

    # TODO: review this param thing.
    async def user_addlistlim(self, address, limit=10):
        offset = 0
        if len(address) == 3:
            address, limit, offset = address
        elif len(address) == 2:
            address, limit = address
        txs = []
        if self.config.direct_ledger and self.ledger.legacy_db:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_addlistlim')

            txs = await self.ledger.async_fetchall(
                'SELECT * FROM transactions WHERE (address = ? OR recipient = ?) '
                'ORDER BY block_height DESC LIMIT ?, ?',
                (address, address, offset, limit),
            )
        else:
            stream = await self._node_stream()
            try:
                await self._send('addlistlim', stream)
                await self._send(address, stream)
                await self._send(limit, stream)
                txs = await self._receive(stream)
            except KeyboardInterrupt:
                stream.close()
            finally:
                if stream:
                    stream.close()
        return txs

    async def user_addlistlimfrom(self, address, limit=10, offset=0):
        if len(address) == 3:
            address, limit, offset = address
        elif len(address) == 2:
            address, limit = address
        txs = []
        if self.config.direct_ledger:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_addlistlimfrom')

            txs = await self.ledger.async_fetchall(
                'SELECT * FROM transactions WHERE (address = ? OR recipient = ?) '
                'ORDER BY block_height DESC LIMIT ?, ?',
                (address, address, offset, limit),
            )
        else:
            stream = await self._node_stream()
            try:
                await self._send('addlistlim', stream)
                await self._send(address, stream)
                await self._send(limit, stream)
                txs = await self._receive(stream)
            except KeyboardInterrupt:
                stream.close()
            finally:
                if stream:
                    stream.close()
        return txs

    async def user_addlistop(self, address, op: str = '', amount: float = 0.0, desc: bool = True, sender: bool = True, start_time: float = 0.0, end_time: float = 9e10):
        """
        Returns tx matching given address, op, amount,
        order descending/ascending, sender/recipient, start and end timestamps
        """
        # TODO: cache
        if len(address) == 7:
            # address can be a string, or a list [address, op, desc, sender,
            # start_time, end_time]
            address, op, amount, desc, sender, start_time, end_time = address
        if desc:
            order = 'DESC'
        else:
            order = 'ASC'
        if sender:
            fromto = 'address'
        else:
            fromto = 'recipient'

        if self.config.direct_ledger:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_addlistop')

            txs = await self.ledger.async_fetchall(
                'SELECT * FROM transactions WHERE ' + fromto + ' = ? AND '
                'operation = ? AND timestamp > ? AND timestamp < ? AND '
                'amount >= ? ORDER BY block_height ' + order,
                (address, op, start_time, end_time, amount),
            )
        else:
            txs = {'Error': 'Need direct ledger access or capable node'}
            # TODO: add user_addlistop to node
        return txs

    async def user_addlistopfromto(self, address, recipient, op: str = '', amount: float = 0.0, desc: bool = True, start_time: float = 0.0, end_time: float = 9e10):
        """
        Returns tx matching given sender, recipient, op, amount,
        order descending/ascending, start and end timestamps
        """
        # TODO: cache
        if len(address) == 7:
            # address can be a string, or a list [sender, recipient, op,
            # desc, sender, start_time, end_time]
            sender, recipient, op, amount, desc, start_time, end_time = address
        if desc:
            order = 'DESC'
        else:
            order = 'ASC'

        if self.config.direct_ledger:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_addlistopfromto')

            txs = await self.ledger.async_fetchall(
                'SELECT * FROM transactions WHERE address = ? AND '
                'recipient = ? AND operation = ? AND timestamp > ? AND '
                'timestamp < ? AND amount >= ? ORDER BY block_height ' + order,
                (address, recipient, op, start_time, end_time, amount),
            )
        else:
            txs = {'Error': 'Need direct ledger access or capable node'}
            # TODO: add user_addlistopfromto to node
        return txs

    async def user_addlistopfrom(self, address, op: str = ''):
        """Returns tx matching given op and sender address"""
        # TODO: cache
        if len(address) == 2:
            # address can be a string, or a list [address, op]
            address, op = address
        if self.config.direct_ledger:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_addlistopfrom')

            txs = await self.ledger.async_fetchall(
                'SELECT * FROM transactions WHERE address = ? AND operation = ? '
                'ORDER BY block_height DESC',
                (address, op),
            )
        else:
            txs = {'Error': 'Need direct ledger access or capable node'}
            # TODO: add user_addlistopfrom to node
        return txs

    async def user_addlistoplikefrom(self, address, op: str = ''):
        """Returns tx matching like op% and sender address"""
        # TODO: cache
        if len(address) == 2:
            # address can be a string, or a list [address, op]
            address, op = address
        if self.config.direct_ledger:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_addlistoplikefrom')

            txs = await self.ledger.async_fetchall(
                'SELECT * FROM transactions WHERE address = ? AND operation LIKE ? '
                'ORDER BY block_height DESC',
                (address, '{}%'.format(op)),
            )
        else:
            txs = {'Error': 'Need direct ledger access or capable node'}
            # TODO: add user_addlistopfrom to node
        return txs

    async def user_listexactopdata(self, op, data: str = ''):
        """Returns tx matching given op and openfield"""

        if len(op) == 2:
            # address can be a string, or a list [address, op]
            op, data = op
        if self.config.direct_ledger:
            # Hard limit of 1000 most recent for safety.
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_listexactopdata')

            txs = await self.ledger.async_fetchall(
                'SELECT * FROM transactions WHERE operation = ? and openfield = ?'
                'ORDER BY block_height DESC LIMIT 1000',
                (op, data),
            )
        else:
            txs = {'Error': 'Need direct ledger access or capable node'}
            # TODO: add user_addlistopfrom to node
        return txs

    async def user_addlistlimjson(self, address, limit=10):
        txs = await self.user_addlistlim(address, limit)
        return [dict(zip(TX_KEYS, tx)) for tx in txs]

    async def user_addlistlimfromjson(self, address, limit=10, offset=0):
        txs = await self.user_addlistlimfrom(address, limit, offset)
        return [dict(zip(TX_KEYS, tx)) for tx in txs]

    async def user_addlistopjson(self, address, op: str = '', amount: float = 0.0, desc: bool = True, sender: bool = True, start_time: float = 0.0, end_time: float = 9e10):
        txs = await self.user_addlistop(address, op, amount, desc, sender, start_time, end_time)
        return [dict(zip(TX_KEYS, tx)) for tx in txs]

    async def user_addlistopfromtojson(self, address, recipient, op: str = '', amount: float = 0.0, desc: bool = True, start_time: float = 0.0, end_time: float = 9e10):
        txs = await self.user_addlistopfromto(address, recipient, op, amount, desc, start_time, end_time)
        return [dict(zip(TX_KEYS, tx)) for tx in txs]

    async def user_addlistopfromjson(self, address, op: str = '') -> list:
        txs = await self.user_addlistopfrom(address, op)
        return [dict(zip(TX_KEYS, tx)) for tx in txs]

    async def user_listexactopdatajson(self, op, data: str = '') -> list:
        txs = await self.user_listexactopdata(op, data)
        return [dict(zip(TX_KEYS, tx)) for tx in txs]

    async def user_pubkeyget(self, address: str) -> str:
        pubkey = ''
        if self.config.direct_ledger:
            res = await self.ledger.async_fetchone(
                'SELECT public_key FROM transactions '
                'WHERE address = ? and reward = 0 LIMIT 1',
                (address, ),
            )
            pubkey = res[0]
            # print("pubkey0", pubkey)
        else:
            stream = await self._node_stream()
            try:
                await self._send('pubkeyget', stream)
                await self._send(address, stream)
                pubkey = await self._receive(stream)
                # print("pubkey", pubkey)
            except KeyboardInterrupt:
                stream.close()
            finally:
                if stream:
                    stream.close()
        return pubkey

    async def user_addlist(self, address: str) -> list:
        txs = []
        if self.config.direct_ledger:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_addlist')

            txs = await self.ledger.async_fetchall(
                'SELECT * FROM transactions WHERE (address = ? OR recipient = ?) '
                'ORDER BY block_height DESC LIMIT 1000',
                (address, address),
            )
        else:
            stream = await self._node_stream()
            try:
                await self._send('addlist', stream)
                await self._send(address, stream)
                txs = await self._receive(stream)
            except KeyboardInterrupt:
                stream.close()
            finally:
                if stream:
                    stream.close()
        return txs

    async def user_annget(self) -> str:
        # TODO: factorize with annverget
        if self.cached('annget', 60*10):
            return self.cache['annget'][1]
        ann_addr = self.config.genesis_conf
        ann = ''
        if self.config.direct_ledger:
            try:
                result = await self.ledger.async_fetchone(
                    'SELECT openfield FROM transactions '
                    'WHERE address = ? AND operation = ?'
                    'ORDER BY block_height DESC limit 1',
                    (ann_addr, 'ann'),
                )
                ann = replace_regex(result[0], 'ann=')
            except Exception:
                ann = ''
        else:
            stream = await self._node_stream()
            try:
                await self._send('annget', stream)
                ann = await self._receive(stream)
            except KeyboardInterrupt:
                stream.close()
            finally:
                if stream:
                    stream.close()
        self.set_cache('annget', ann)
        return ann

    async def user_balanceget(self, balance_address):
        if self.config.direct_ledger and self.ledger.legacy_db:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_balanceget')

            base_mempool = await self.mempool.async_fetchall(
                'SELECT amount, openfield, operation FROM transactions '
                'WHERE address = ?',
                (balance_address, ),
            )
            # include mempool fees
            debit_mempool = 0
            if base_mempool:
                for x in base_mempool:
                    debit_tx = Decimal(x[0])
                    fee = fee_calculate(x[1], x[2], 700001)
                    debit_mempool = quantize_eight(debit_mempool + debit_tx + fee)
            else:
                debit_mempool = 0
            # include mempool fees
            credit_ledger = Decimal('0')
            for entry in await self.ledger.async_execute('SELECT amount FROM transactions WHERE recipient = ?', (balance_address, )):
                try:
                    credit_ledger = quantize_eight(credit_ledger) + quantize_eight(entry[0])
                    credit_ledger = 0 if credit_ledger is None else credit_ledger
                except Exception:
                    credit_ledger = 0

            fees = Decimal('0')
            debit_ledger = Decimal('0')

            for entry in await self.ledger.async_execute('SELECT fee, amount FROM transactions WHERE address = ?', (balance_address, )):
                try:
                    fees = quantize_eight(fees) + quantize_eight(entry[0])
                    fees = 0 if fees is None else fees
                except Exception:
                    fees = 0
                try:
                    debit_ledger = debit_ledger + Decimal(entry[1])
                    debit_ledger = 0 if debit_ledger is None else debit_ledger
                except Exception:
                    debit_ledger = 0

            debit = quantize_eight(debit_ledger + debit_mempool)

            rewards = Decimal('0')
            for entry in await self.ledger.async_execute('SELECT reward FROM transactions WHERE recipient = ?', (balance_address, )):
                try:
                    rewards = quantize_eight(rewards) + quantize_eight(entry[0])
                    rewards = 0 if rewards is None else rewards
                except Exception:
                    rewards = 0
            balance = quantize_eight(credit_ledger - debit - fees + rewards)
            balance_no_mempool = (float(credit_ledger) - float(debit_ledger) - float(fees) + float(rewards))
            # app_log.info("Mempool: Projected transction address balance: " + str(balance))
            return (
                str(balance),
                str(credit_ledger),
                str(debit),
                str(fees),
                str(rewards),
                str(balance_no_mempool),
            )
        else:
            stream = await self._node_stream()
            try:
                await self._send('balanceget', stream)
                await self._send(balance_address, stream)
                balance = await self._receive(stream)
                return balance
            except KeyboardInterrupt:
                stream.close()
            finally:
                if stream:
                    stream.close()

    async def user_globalbalanceget(self, addresses):
        """Return total balance amounts from a list of addresses"""
        # Sanitize, make sure addresses are addresses. Important here since we assemble the query by hand.
        for address in addresses:
            if not address_validate(address):
                return 'Error: bad address {}'.format(address)
        addresses = "('" + "','".join(addresses) + "')"
        # print("add", addresses)
        if self.config.direct_ledger:
            if not self.ledger.legacy_db:
                raise RuntimeError('V2 BD, Asking user_globalbalanceget')

            base_mempool = await self.mempool.async_fetchall('SELECT amount, openfield, operation FROM transactions '
                                                             'WHERE address in {}'.format(addresses), )
            # include mempool fees
            debit_mempool = 0
            if base_mempool:
                for x in base_mempool:
                    debit_tx = Decimal(x[0])
                    fee = fee_calculate(x[1], x[2], 700001)
                    debit_mempool = quantize_eight(debit_mempool + debit_tx + fee)
            else:
                debit_mempool = 0
            # include mempool fees
            credit_ledger = Decimal('0')
            for entry in await self.ledger.async_execute('SELECT amount FROM transactions WHERE recipient in{}'.format(addresses)):
                try:
                    credit_ledger = quantize_eight(credit_ledger) + quantize_eight(entry[0])
                    credit_ledger = 0 if credit_ledger is None else credit_ledger
                except Exception:
                    credit_ledger = 0

            fees = Decimal('0')
            debit_ledger = Decimal('0')

            for entry in await self.ledger.async_execute('SELECT fee, amount FROM transactions WHERE address in {}'.format(addresses)):
                try:
                    fees = quantize_eight(fees) + quantize_eight(entry[0])
                    fees = 0 if fees is None else fees
                except Exception:
                    fees = 0
                try:
                    debit_ledger = debit_ledger + Decimal(entry[1])
                    debit_ledger = 0 if debit_ledger is None else debit_ledger
                except Exception:
                    debit_ledger = 0

            debit = quantize_eight(debit_ledger + debit_mempool)

            rewards = Decimal('0')
            for entry in await self.ledger.async_execute('SELECT reward FROM transactions WHERE recipient in {}'.format(addresses)):
                try:
                    rewards = quantize_eight(rewards) + quantize_eight(entry[0])
                    rewards = 0 if rewards is None else rewards
                except Exception:
                    rewards = 0
            balance = quantize_eight(credit_ledger - debit - fees + rewards)
            balance_no_mempool = (float(credit_ledger) - float(debit_ledger) - float(fees) + float(rewards))
            # app_log.info("Mempool: Projected transction address balance: " + str(balance))
            return (
                str(balance),
                str(credit_ledger),
                str(debit),
                str(fees),
                str(rewards),
                str(balance_no_mempool),
            )
        else:
            return 'Error: Need direct ledger access or capable node'
            # TODO: add user_globalbalanceget to node

    async def user_balancegetjson(self, balance_address):
        values = await self.user_balanceget(balance_address)
        keys = [
            'balance',
            'total_credits',
            'total_debits',
            'total_fees',
            'total_rewards',
            'balance_no_mempool',
        ]
        return dict(zip(keys, values))

    async def user_globalbalancegetjson(self, addresses):
        values = await self.user_globalbalanceget(addresses)
        keys = [
            'balance',
            'total_credits',
            'total_debits',
            'total_fees',
            'total_rewards',
            'balance_no_mempool',
        ]
        return dict(zip(keys, values))
