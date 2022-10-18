"""
A Tornado based wallet server for Bismuth.
EggdraSyl - June 2018


pip3 install -r requirements.txt
"""

import asyncio
import datetime
import json
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

import aioprocessing
import psutil
import tornado.gen
import tornado.log
import tornado.util
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.options import define, options
from tornado.tcpserver import TCPServer

# Bismuth specific modules
import modules.config as config
# from modules.helpers import *
from modules.sqlitebase import SqliteBase
from modules.ledgerbase import LedgerBase
from modules.node_interface import NodeInterface

__version__ = '0.1.22'

# Server
# -----------------------------------------------------------------------------


class WalletServer(TCPServer):
    """Tornado asynchronous TCP server."""
    clients = set()
    status_dict = {'version': __version__}
    node_interface = None

    async def handle_stream(self, stream, address):
        global access_log
        global app_log
        global stop_event
        global MAX_CLIENTS
        ip, fileno = address
        if len(self.clients) >= MAX_CLIENTS:
            access_log.info('Reached {} max clients, denying connection for {}.'.format(MAX_CLIENTS, ip))
            return
        WalletServer.clients.add(address)
        access_log.info('Incoming connection from {}:{} - {} Total Clients'.format(ip, fileno, len(self.clients)))
        while not stop_event.is_set():
            try:
                # print("waiting for command")
                await self.command(stream, ip)
            except StreamClosedError:
                WalletServer.clients.remove(address)
                access_log.info('Client {}:{} left  - {} Total Clients'.format(ip, fileno, len(self.clients)))
                break
            except ValueError:
                WalletServer.clients.remove(address)
                if options.verbose:
                    access_log.info('Client {}:{} Rejected  - {} Total Clients'.format(ip, fileno, len(self.clients)))
                stream.close()
                break
            except tornado.util.TimeoutError:
                WalletServer.clients.remove(address)
                access_log.info('Client {}:{} Timeout  - {} Total Clients'.format(ip, fileno, len(self.clients)))
                try:
                    stream.close()
                except Exception:
                    pass
                break
            except Exception as e:
                what = str(e)
                if 'OK' not in what:
                    app_log.error('handle_stream {} for ip {}:{}'.format(what, ip, fileno))
                    await asyncio.sleep(1)

    @staticmethod
    async def _receive(stream, ip):
        """
        Get a command, async version
        :param stream:
        :param ip:
        :return:
        """
        try:
            header = await tornado.gen.with_timeout(datetime.timedelta(seconds=35), stream.read_bytes(10), quiet_exceptions=tornado.iostream.StreamClosedError)
            data_len = int(header)
            data = await tornado.gen.with_timeout(datetime.timedelta(seconds=10), stream.read_bytes(data_len), quiet_exceptions=tornado.iostream.StreamClosedError)
            data = json.loads(data.decode('utf-8'))
            return data
        except Exception as e:
            app_log.error('_receive {} for ip {}'.format(str(e), ip))
            raise

    @staticmethod
    async def _send(data, stream, ip):
        """
        sends an object to the stream, async.
        :param data:
        :param stream:
        :param ip:
        :return:
        """
        global app_log
        try:
            data = str(json.dumps(data))
            header = str(len(data)).encode('utf-8').zfill(10)
            full = header + data.encode('utf-8')
            await stream.write(full)
        except Exception as e:
            app_log.error('_send {} for ip {}'.format(str(e), ip))
            raise

    async def command(self, stream, ip):
        global access_log
        data = await self._receive(stream, ip)
        if options.verbose:
            access_log.info('Command ' + data)

        # roles
        rights = await getrights(ip)

        if data == 'wstatusget':
            # Get wallet server status only
            await self._send(self.status_dict, stream, ip)
            return

        # Other commands are automagically deduced from the node interface.

        # how many params to get for that command?
        params_count = self.node_interface.param_count_of(data, rights)
        print('{} params'.format(params_count))
        if params_count == -1:
            raise ValueError('Unknown Command ' + data)

        params = [data]
        for i in range(params_count):
            param = await self._receive(stream, ip)
            params.append(param)
        res = await self.node_interface.call_user(params)
        await self._send(res, stream, ip)
        return
        """
        if data == "mpclear":
            # TODO: only for admin
            return

        # admin only
        if "admin" in rights:
            # TODO
            if data == 'status':
                return
            if data == 'setconfig':
                return
        """

    async def background(self):
        """
        This runs in a background coroutine and print out status
        :return:
        """
        global stop_event
        global app_log
        global process
        while not stop_event.is_set():
            try:
                app_log.info('STATUS: {} Connected clients.'.format(len(self.clients)))
                self.status_dict['clients'] = len(self.clients)
                self.status_dict['max_clients'] = MAX_CLIENTS
                if process:
                    of = len(process.open_files())
                    fd = process.num_fds()
                    co = len(process.connections(kind='tcp4'))
                    self.status_dict['of'], self.status_dict['fd'], self.status_dict['co'] = of, fd, co
                    app_log.info('STATUS: {} Open files, {} connections, {} FD used.'.format(of, co, fd))

                await asyncio.sleep(30)
            except Exception as e:
                app_log.error('Error background {}'.format(str(e)))


async def getrights(ip):
    global app_log
    global CONFIG
    try:
        result = ['none']
        if ip in CONFIG.allowed:
            result.append('admin')
        return result
    except Exception as e:
        app_log.warning('Error getrights {}'.format(str(e)))


def start_server(port):
    global app_log
    global stop_event
    global PORT
    global CONFIG
    mempool = SqliteBase(options.verbose, db_path=CONFIG.mempool_path.replace('mempool.db', ''), db_name='mempool.db', app_log=app_log)
    db_name = 'ledger.db'
    if CONFIG.testnet:
        db_name = 'test.db'
    ledger = LedgerBase(options.verbose, db_path=CONFIG.db_path + '/', db_name=db_name, app_log=app_log)

    node_interface = NodeInterface(mempool, ledger, CONFIG, app_log=app_log)
    server = WalletServer()
    server.node_interface = node_interface
    # attach mempool db
    # server.listen(port)
    io_loop = IOLoop.instance()

    if CONFIG.direct_ledger:
        try:
            # Force a db connection attempt and updates db version of ledger
            _ = io_loop.run_sync(ledger.check_db_version, 30)
        except Exception as e:
            app_log.error("Can't connect to ledger: {}".format(e))
            return
    else:
        app_log.info("Config: don't use direct ledger access")
    try:
        # Force a db connection attempt
        _ = io_loop.run_sync(mempool.schema, 30)
    except Exception as e:
        app_log.info("Can't connect to mempool: {}".format(e))
        return

    server.bind(port)
    server.start(1)  # Force one process only
    if options.verbose:
        app_log.info('Starting server on tcp://localhost:{}'.format(port))
    io_loop.spawn_callback(server.background)
    try:
        io_loop.start()
    except KeyboardInterrupt:
        stop_event.set()
        io_loop.stop()
        app_log.info('exited cleanly')


if __name__ == '__main__':
    CONFIG = config.Get()
    CONFIG.read('wallet_server.txt', 'wallet_server_custom.txt')
    #
    is_testnet = CONFIG.testnet
    PORT = CONFIG.port
    MAX_CLIENTS = CONFIG.max_clients

    define('port', default=PORT, help='port to listen on')
    define('verbose', default=False, help='verbose')
    options.parse_command_line()

    # TODO
    """
    if CONFIG.mempool_ram_conf:
        print("Incompatible setting detected.")
        print("Please edit config.txt, set mempool_ram_conf=False and restart node")
        sys.exit()
    """

    # TODO: print settings

    if not os.path.isfile(CONFIG.mempool_path):
        print('mempool.db not found at {}'.format(CONFIG.mempool_path))
        print("Please edit node's config.txt, check mempool_ram_conf=False and restart node.")
        sys.exit()

    start_time = time.time()

    stop_event = aioprocessing.AioEvent()  # Event()

    lock = aioprocessing.AioLock()

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    # formatter = logging.Formatter('%(asctime)s %(funcName)s(%(lineno)d) %(message)s')
    # ch.setFormatter(formatter)
    app_log = logging.getLogger('tornado.application')
    tornado.log.enable_pretty_logging()
    # app_log.addHandler(ch)
    logfile = os.path.abspath('wallet_app.log')
    # Rotate log after reaching 512K, keep 5 old copies.
    rotateHandler = RotatingFileHandler(logfile, 'a', 512*1024, 10)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    rotateHandler.setFormatter(formatter)
    app_log.addHandler(rotateHandler)

    access_log = logging.getLogger('tornado.access')
    tornado.log.enable_pretty_logging()
    logfile2 = os.path.abspath('wallet_access.log')
    rotateHandler2 = RotatingFileHandler(logfile2, 'a', 512*1024, 10)
    formatter2 = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    rotateHandler2.setFormatter(formatter2)
    access_log.addHandler(rotateHandler2)

    app_log.warning('Testnet: {}'.format(is_testnet))
    # fail safe
    if is_testnet and int(CONFIG.node_port) != 2829:
        app_log.warning('Testnet is active, but node_port set to {} instead of 2829. '
                        'Make sure!'.format(CONFIG.node_port), )
        time.sleep(2)

    if os.name == 'posix':
        process = psutil.Process()
        try:
            # Fails on alpine linux
            limit = process.rlimit(psutil.RLIMIT_NOFILE)
        except Exception:
            limit = (1024, -1)
        app_log.info('OS File limits {}, {}'.format(limit[0], limit[1]))
        if limit[0] < 1024:
            app_log.error('Too small ulimit, please tune your system.')
            sys.exit()
    else:
        process = None

    app_log.info('Wallet Server {} Starting on port {}.'.format(__version__, options.port))

    start_server(options.port)
