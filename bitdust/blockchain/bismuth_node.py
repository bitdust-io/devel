import os
import time
import threading
import socks
import sqlite3
import traceback
import logging
import json

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred
from twisted.internet import reactor

#------------------------------------------------------------------------------

from bitdust_forks.Bismuth import node as bismuth_node  # @UnresolvedImport
from bitdust_forks.Bismuth import connectionmanager  # @UnresolvedImport
from bitdust_forks.Bismuth import mempool as mp  # @UnresolvedImport
from bitdust_forks.Bismuth import apihandler  # @UnresolvedImport
from bitdust_forks.Bismuth import dbhandler  # @UnresolvedImport
from bitdust_forks.Bismuth import connections  # @UnresolvedImport
from bitdust_forks.Bismuth import options  # @UnresolvedImport
from bitdust_forks.Bismuth import peershandler  # @UnresolvedImport
from bitdust_forks.Bismuth import plugins  # @UnresolvedImport
from bitdust_forks.Bismuth.libs import node as _node  # @UnresolvedImport
from bitdust_forks.Bismuth.libs import logger  # @UnresolvedImport
from bitdust_forks.Bismuth.libs import keys  # @UnresolvedImport
from bitdust_forks.Bismuth.modules import config as modules_config  # @UnresolvedImport
from bitdust_forks.Bismuth.bismuthclient import rpcconnections  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.main import settings
from bitdust.main import config as main_conf

from bitdust.blockchain import known_bismuth_nodes

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

#------------------------------------------------------------------------------

VERSION = '1.0.0.0'

_DataDirPath = None

#------------------------------------------------------------------------------


def init():
    global _DataDirPath
    _DataDirPath = settings.ServiceDir('bismuth_blockchain')
    create_config_file(_DataDirPath)
    starting_defer = Deferred()
    node_thread = threading.Thread(target=run, args=(_DataDirPath, starting_defer))
    node_thread.start()
    return starting_defer


def shutdown():
    global _DataDirPath

    config_path = os.path.join(_DataDirPath, 'config')
    custom_config_path = os.path.join(_DataDirPath, 'config_custom')

    config = options.Get()
    config.read(filename=config_path, custom_filename=custom_config_path)

    s = socks.socksocket()
    port = config.port

    count = 0
    while count < 1:
        try:
            s.connect(('127.0.0.1', int(port)))
            # print('Sending stop command...')
            connections.send(s, 'stop')
            # print('Stop command delivered.')
            break
        except Exception as e:
            lg.exc()
            # print('Cannot reach node', e)
            # time.sleep(0.1)
            count += 1

    s.close()
    return True


#------------------------------------------------------------------------------


def nod():
    return bismuth_node.node


#------------------------------------------------------------------------------


def run(data_dir_path, starting_defer):
    global _DataDirPath

    rpcconnections.LTIMEOUT = 20

    _DataDirPath = data_dir_path
    if not os.path.exists(data_dir_path):
        os.makedirs(data_dir_path)

    config_path = os.path.join(data_dir_path, 'config')
    custom_config_path = os.path.join(data_dir_path, 'config_custom')

    bismuth_node.node = _node.Node()
    node = bismuth_node.node
    bismuth_node.bootstrap = bootstrap

    node.app_version = VERSION

    node.FOUNDATION_MINERS = known_bismuth_nodes.foundation_miners()

    options.Get.defaults['heavy3_path'] = os.path.join(data_dir_path, 'heavy3a.bin')
    options.Get.defaults['mempool_path'] = os.path.join(data_dir_path, 'mempool.db')
    modules_config.Get.defaults['db_path'] = data_dir_path
    modules_config.Get.defaults['mempool_path'] = os.path.join(data_dir_path, 'mempool.db')

    node.data_dir_path = data_dir_path

    node.keys = keys.Keys()

    node.is_testnet = False
    node.is_regnet = False
    node.is_mainnet = True

    config = options.Get()
    config.read(filename=config_path, custom_filename=custom_config_path)

    node.version = config.version
    node.debug_level = config.debug_level

    node.logger = logger.Logger()
    if _Debug:
        # node.logger.app_log = custom_log(level_input=lg.get_loging_level(max(0, lg.get_debug_level() - 6), return_name=True))
        node.logger.app_log = custom_log(level_input=lg.get_loging_level(_DebugLevel - 6, return_name=True))
        # node.logger.app_log = custom_log(level_input='DEBUG')
    else:
        node.logger.app_log = custom_log(level_input='CRITICAL')
    node.logger.app_log.critical(f'Python version: {node.py_version}')

    node.host = config.node_ip
    node.port = config.port
    node.verify = config.verify
    node.thread_limit = config.thread_limit
    node.rebuild_db = config.rebuild_db
    node.debug = config.debug
    node.debug_level = config.debug_level
    node.pause = config.pause
    node.ledger_path = config.ledger_path
    node.hyper_path = config.hyper_path
    node.hyper_recompress = config.hyper_recompress
    node.tor = config.tor
    node.ram = config.ram
    node.version_allow = config.version_allow
    node.reveal_address = config.reveal_address
    node.terminal_output = config.terminal_output
    node.egress = config.egress
    node.genesis = config.genesis
    node.accept_peers = config.accept_peers
    node.full_ledger = config.full_ledger
    node.trace_db_calls = config.trace_db_calls
    node.old_sqlite = config.old_sqlite
    node.heavy = config.heavy
    node.heavy3_path = config.heavy3_path

    # node.logger.app_log.warning('Configuration settings loaded')

    # if not node.full_ledger and os.path.exists(node.ledger_path) and node.is_mainnet:
    #     os.remove(node.ledger_path)
    #     node.logger.app_log.warning('Removed full ledger for hyperblock mode')
    # if not node.full_ledger:
    #     node.logger.app_log.warning('Cloning hyperblocks to ledger file')
    #     shutil.copy(node.hyper_path, node.ledger_path)

    try:
        node.plugin_manager = plugins.PluginManager(app_log=node.logger.app_log, config=config, init=True)
        extra_commands = {}
        extra_commands = node.plugin_manager.execute_filter_hook('extra_commands_prefixes', extra_commands)

        setup_net_type(bismuth_node.node, data_dir_path, node.logger.app_log)

        bismuth_node.load_keys(data_dir=data_dir_path, wallet_filename=os.path.join(data_dir_path, 'node_key.json'))

        # node.logger.app_log.warning(f'Checking Heavy3 file, can take up to 5 minutes...')
        t_now = time.time()

        from bitdust_forks.Bismuth import mining_heavy3  # @UnresolvedImport
        # from bitdust_forks.Bismuth import digest  # @UnresolvedImport

        mining_heavy3.mining_open(node.heavy3_path)
        # digest.mining_heavy3.MMAP = mining_heavy3.MMAP
        # digest.mining_heavy3.RND_LEN = mining_heavy3.RND_LEN
        node.logger.app_log.warning(f'Heavy3 file is OK, loaded in %s seconds' % (time.time() - t_now))

        # node.logger.app_log.warning(f'Status: Starting node version {VERSION}')
        node.startup_time = time.time()
        try:

            node.peers = peershandler.Peers(node.logger.app_log, config=config, node=bismuth_node.node)
            node.peers.peerfile = bismuth_node.node.peerfile  # @UndefinedVariable
            node.peers.suggested_peerfile = bismuth_node.node.peerfile_suggested  # @UndefinedVariable

            node.apihandler = apihandler.ApiHandler(node.logger.app_log, config)
            mp.MEMPOOL = mp.Mempool(node.logger.app_log, config, bismuth_node.node.db_lock, bismuth_node.node.is_testnet, trace_db_calls=bismuth_node.node.trace_db_calls)
            bismuth_node.mp.MEMPOOL = mp.MEMPOOL

            check_db_for_bootstrap(bismuth_node.node)

            db_handler_initial = dbhandler.DbHandler(
                bismuth_node.node.index_db, bismuth_node.node.ledger_path, bismuth_node.node.hyper_path, bismuth_node.node.ram, bismuth_node.node.ledger_ram_file, node.logger, trace_db_calls=bismuth_node.node.trace_db_calls
            )
            bismuth_node.db_handler_initial = db_handler_initial

            try:
                bismuth_node.ledger_check_heights(bismuth_node.node, db_handler_initial)
            except:
                traceback.print_exc()

            if node.recompress:
                #todo: do not close database and move files, swap tables instead
                db_handler_initial.close()
                bismuth_node.recompress_ledger(bismuth_node.node)
                db_handler_initial = dbhandler.DbHandler(
                    bismuth_node.node.index_db, bismuth_node.node.ledger_path, bismuth_node.node.hyper_path, bismuth_node.node.ram, bismuth_node.node.ledger_ram_file, node.logger, trace_db_calls=bismuth_node.node.trace_db_calls
                )
                bismuth_node.db_handler_initial = db_handler_initial

            bismuth_node.ram_init(db_handler_initial)
            bismuth_node.node_block_init(db_handler_initial)
            bismuth_node.initial_db_check()

            if not node.is_regnet:
                bismuth_node.sequencing_check(db_handler_initial)

            if node.verify:
                bismuth_node.verify(db_handler_initial)

            bismuth_node.add_indices(db_handler_initial)

            db_handler_initial.close()

            if not node.tor:
                host = '0.0.0.0'
                port = int(node.port)

                bismuth_node.ThreadedTCPServer.allow_reuse_address = True
                bismuth_node.ThreadedTCPServer.daemon_threads = True
                bismuth_node.ThreadedTCPServer.timeout = 60
                bismuth_node.ThreadedTCPServer.request_queue_size = 100

                server = bismuth_node.ThreadedTCPServer((host, port), bismuth_node.ThreadedTCPRequestHandler)
                ip, node.port = server.server_address

                server_thread = threading.Thread(target=server.serve_forever)
                server_thread.daemon = True
                server_thread.start()

                node.logger.app_log.warning(f'Status: Server loop running on {ip}:{node.port}')

            else:
                node.logger.app_log.warning('Status: Not starting a local server to conceal identity on Tor network')

            connection_manager = connectionmanager.ConnectionManager(bismuth_node.node, mp)
            connection_manager.start()

        except Exception as e:
            node.logger.app_log.info(e)
            reactor.callFromThread(starting_defer.errback, e)  # @UndefinedVariable
            raise

    except Exception as e:
        node.logger.app_log.info(e)
        reactor.callFromThread(starting_defer.errback, e)  # @UndefinedVariable
        raise

    # node.logger.app_log.warning('Status: Bismuth loop running.')

    reactor.callFromThread(starting_defer.callback, True)  # @UndefinedVariable

    while True:
        if node.IS_STOPPING:
            if node.db_lock.locked():
                time.sleep(0.5)
            else:
                mining_heavy3.mining_close()
                node.logger.app_log.warning('Status: Securely disconnected main processes, subprocess termination in progress.')
                break
        time.sleep(0.1)

    try:
        bismuth_node.db_handler_initial.close()
    except:
        pass

    node.logger.app_log.warning('Status: Clean Stop')


def create_config_file(data_dir_path):
    config_path = os.path.join(data_dir_path, 'config')
    node_host = main_conf.conf().getString('services/bismuth-node/host', '127.0.0.1')
    node_port = main_conf.conf().getInt('services/bismuth-node/tcp-port', 15658)
    if _Debug:
        lg.args(_DebugLevel, node_host=node_host, node_port=node_port)
    config_src = '''debug=False
port={port}
verify=False
version=mainnet0001
version_allow=mainnet0001
thread_limit=64
rebuild_db=True
debug_level=DEBUG
purge=True
pause=5
hyper_path={hyper_path}
hyper_recompress=True
full_ledger=True
ledger_path={ledger_path}
ban_threshold=30
tor=False
allowed=127.0.0.1,192.168.0.1,any
ram=False
heavy=False
node_ip={node_ip}
light_ip={light_ip}
reveal_address=True
accept_peers=True
banlist=
whitelist=
nodes_ban_reset=5
terminal_output=False
gui_scaling=adapt
mempool_ram=False
egress=True
trace_db_calls={trace_db_calls}
heavy3_path={heavy3_path}'''.format(
        port=node_port,
        node_ip=node_host,
        hyper_path=os.path.join(data_dir_path, 'hyper.db'),
        ledger_path=os.path.join(data_dir_path, 'ledger.db'),
        heavy3_path=os.path.join(data_dir_path, 'heavy3a.bin'),
        light_ip='{"%s": "%d"}' % (node_host, node_port),
        trace_db_calls='True' if (_Debug and _DebugLevel >= 16) else 'False',
    )
    fout = open(config_path, 'w')
    fout.write(config_src)
    fout.flush()
    fout.close()


def setup_net_type(node, data_dir_path, app_log):
    """
    Adjust globals depending on mainnet, testnet or regnet
    """
    node.is_mainnet = True
    node.is_testnet = False
    node.is_regnet = False

    if 'testnet' in node.version or node.is_testnet:
        node.is_testnet = True
        node.is_mainnet = False
        node.version_allow = 'testnet'

    if 'regnet' in node.version or node.is_regnet:
        node.is_regnet = True
        node.is_testnet = False
        node.is_mainnet = False

    node.peerfile = os.path.join(data_dir_path, 'peers.json')
    node.peerfile_suggested = os.path.join(data_dir_path, 'suggested_peers.json')
    node.ledger_ram_file = 'file:ledger?mode=memory&cache=shared'
    node.index_db = os.path.join(data_dir_path, 'index.db')
    peerfile_data = known_bismuth_nodes.nodes_by_host().copy()
    app_log.warning(f'node host: {node.host} peerfile_data: {peerfile_data}')
    peerfile_data.pop(node.host, None)
    open(node.peerfile_suggested, 'w').write(json.dumps(peerfile_data))
    open(node.peerfile, 'w').write(json.dumps({'127.0.0.1': node.port}))
    # open(node.peerfile, 'w').write(json.dumps({}))


def bootstrap():
    global _DataDirPath

    try:
        hyper_path = os.path.join(_DataDirPath, 'hyper.db')
        ledger_path = os.path.join(_DataDirPath, 'ledger.db')
        index_path = os.path.join(_DataDirPath, 'index.db')

        INITIAL_DIFFICULTY = 10
        INITIAL_HYPER_DIFFICULTY = 10

        hdd = sqlite3.connect(ledger_path, timeout=1)
        hdd.text_factory = str
        hdd.execute('PRAGMA case_sensitive_like = 1;')
        hdd_cursor = hdd.cursor()
        hdd_cursor.execute('CREATE TABLE IF NOT EXISTS "misc" ("block_height" INTEGER, "difficulty" TEXT)')
        hdd_cursor.execute(
            'CREATE TABLE IF NOT EXISTS "transactions" ("block_height" INTEGER, "timestamp" NUMERIC, "address" TEXT, "recipient" TEXT, "amount" NUMERIC, "signature" TEXT, "public_key" TEXT, "block_hash" TEXT, "fee" NUMERIC, "reward" NUMERIC, "operation" TEXT, "openfield" TEXT)',
        )
        hdd_cursor.execute('CREATE INDEX "Timestamp Index" ON "transactions" ("timestamp")')
        hdd_cursor.execute('CREATE INDEX "Signature Index" ON "transactions" ("signature")')
        hdd_cursor.execute('CREATE INDEX "Reward Index" ON "transactions" ("reward")')
        hdd_cursor.execute('CREATE INDEX "Recipient Index" ON "transactions" ("recipient")')
        hdd_cursor.execute('CREATE INDEX "Openfield Index" ON "transactions" ("openfield")')
        hdd_cursor.execute('CREATE INDEX "Fee Index" ON "transactions" ("fee")')
        hdd_cursor.execute('CREATE INDEX "Block Height Index" ON "transactions" ("block_height")')
        hdd_cursor.execute('CREATE INDEX "Block Hash Index" ON "transactions" ("block_hash")')
        hdd_cursor.execute('CREATE INDEX "Amount Index" ON "transactions" ("amount")')
        hdd_cursor.execute('CREATE INDEX "Address Index" ON "transactions" ("address")')
        hdd_cursor.execute('CREATE INDEX "Operation Index" ON "transactions" ("operation")')
        hdd_cursor.execute('CREATE INDEX TXID4_Index ON transactions(substr(signature,1,4))')
        hdd_cursor.execute('CREATE INDEX "Misc Block Height Index" on misc(block_height)')
        hdd_cursor.execute('INSERT INTO misc (difficulty, block_height) VALUES ({},1)'.format(INITIAL_DIFFICULTY))
        hdd_cursor.execute(
            'INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
                '1',
                '1683400177.01208',
                'genesis',
                options.GENESIS_ADDRESS,
                '0',
                'c5QPId20zONTTyIYKB7zIiCu+FqrtI9dXs/NFS7cCzW56Khd+6s1+TKu/54vEREnt35yl7AhgRPK8gCuQkN6iwKHXMPZTUvt7FLS28558Y1Au3Tlo2tIj394L/Zu+jQcRxI85QOH+u00kcPaDSmkj/38btUPvxW1o/BibZ3mfNCVkVVwLdoAgNdMXGStBnwmFrvf9odWEDT/bIK7cxmAXJgvXfKtmgQFMCBglGByRE51ZkGKrFMvzY42JY/MvT5q7mAvbAcENWe7KbSjLgOVHCaZf2FIfJRLGfncjKI+Z/jPasvzelAtFTtHK39aLO4KGqC36kr5/VAGqfGDOYZCMOwdYu9KNOmTfVaV7LWyX7I5DYIV1QOTd8+20gEN5AdDulbw9Bp2o/v6dJpcC4HceZNiWtaVovH5bHAWrgY9piNCtirkV/mwqiBnprzYYz34PVbm4KkPD3d9tnwWEz/eGZnMm5AjLx/fhetaCjyfZUPiXVQ8eP+mE0ukIjOrvNemB+MP/FqYDa5SzyJI34WlWu6S/BOCn0D0YlkWLywk48lbBs1J/guHQu7DxH+0PPTD0gi6jnPLio8Ch5A78riSVgLV1xhUxMSzJ7AFKZy2V17r2L1D7qDImTprCBGqihze9hRGXgZNCS0XiT4AGuVhnRNFzsC/mTUlaBHxfbig6tY=',
                'LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQ0lqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FnOEFNSUlDQ2dLQ0FnRUFuNmVjMVBmZjVWbDJ0QlJoY3RtSgp5TVVndG92QUQzcnBNVjcwWlp1Ukk2N0llUGJiYkoveVBnSVU4S0h4RkNEZ0h1eDJOQy9CU1VkNWpyTENQZzE2CktIcVZkbHR2SUwxcWduTmNpWTJOS0VoVkxRMGppQXpBTDgvWE9NNGhMUUtjbnk2dFRpUGVjMHk1ZG5BY2UxekoKNzhCVG1FRDJLVFVQdmJLblFJMS81NlNpU2QrU1Evcnp5aStlK2MwWllFaExTMk50TzVUd0oyV3IrNlY0VW5YcgpjT0U0UysrLzR3THIyTW5GR3d6dWNlWWVOa0NIT2N5ODZmbmFpQmVsbHY1YUN0Y3V4bHFjalFQdzFDU29MaUlICkN5MnhKYkZSeHJYU21qSlRxNG1WWFlmNlFKa0s0WDZPNEtpT2NZMDNRd2tuK1dkczk0c1M4Ny9QZ3NwZEFsSzYKcEF6MU9NZFlvSWJxUUlNR3NOaS9CSlh6VHpTYTF5UnpZZnB6LzlyOUxSYm5RS3hUSzlVSWlrYlY0Ri9JdU80NApBQ29SN3BWY29FQVlJYjRUcVFDUkFYS0VRQ2trRm9RZmNZaVBaOURTbjRiMjNtSEhMWENCWUJpek5wQVdxcXZxCnlSbzVxMVhRM3lKVXVlaVNEUnVZNldEa0MyaWlFWTdYTHlzWnErYnAxS1JjSENjNDBGMnNQU2RrWWozTGJZTUgKaWJsOFd0Q21NY0lFekVKOWdwWmU4RFNrV0tTVkNjNVg3YWpoODVFVU9zaG9KTWdSMGdaQ1FkRGFkaFh5S2xKQQpvZDcvV0JFWVhMa3ZSNWl1Tkk5aHl4Y3VYWkdEaWhNeUxLMmtXaWlIRDN0M3Zadjg4MjlJbDc5NURwTm9rNmhaCnUyS0F4UmtHR1U4aFBjR1hvVVF4eEdFQ0F3RUFBUT09Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQ==',
                'fbc6d3d091d7c5ed745f499c548c103f03b96354c7bb3b3e982a128c',
                0,
                1,
                1,
                'genesis',
            )
        )
        hdd.commit()
        hdd.close()

        hyp = sqlite3.connect(hyper_path, timeout=1)
        hyp.text_factory = str
        hyp.execute('PRAGMA case_sensitive_like = 1;')
        hyp_cursor = hyp.cursor()
        hyp_cursor.execute('CREATE TABLE IF NOT EXISTS "misc" ("block_height" INTEGER, "difficulty" TEXT)')
        hyp_cursor.execute(
            'CREATE TABLE IF NOT EXISTS "transactions" ("block_height" INTEGER, "timestamp" NUMERIC, "address" TEXT, "recipient" TEXT, "amount" NUMERIC, "signature" TEXT, "public_key" TEXT, "block_hash" TEXT, "fee" NUMERIC, "reward" NUMERIC, "operation" TEXT, "openfield" TEXT)',
        )
        hyp_cursor.execute('CREATE INDEX "Timestamp Index" ON "transactions" ("timestamp")')
        hyp_cursor.execute('CREATE INDEX "Signature Index" ON "transactions" ("signature")')
        hyp_cursor.execute('CREATE INDEX "Reward Index" ON "transactions" ("reward")')
        hyp_cursor.execute('CREATE INDEX "Recipient Index" ON "transactions" ("recipient")')
        hyp_cursor.execute('CREATE INDEX "Openfield Index" ON "transactions" ("openfield")')
        hyp_cursor.execute('CREATE INDEX "Fee Index" ON "transactions" ("fee")')
        hyp_cursor.execute('CREATE INDEX "Block Height Index" ON "transactions" ("block_height")')
        hyp_cursor.execute('CREATE INDEX "Block Hash Index" ON "transactions" ("block_hash")')
        hyp_cursor.execute('CREATE INDEX "Amount Index" ON "transactions" ("amount")')
        hyp_cursor.execute('CREATE INDEX "Address Index" ON "transactions" ("address")')
        hyp_cursor.execute('CREATE INDEX "Operation Index" ON "transactions" ("operation")')
        hyp_cursor.execute('CREATE INDEX TXID4_Index ON transactions(substr(signature,1,4))')
        hyp_cursor.execute('CREATE INDEX "Misc Block Height Index" on misc(block_height)')
        hyp_cursor.execute('INSERT INTO misc (difficulty, block_height) VALUES ({},1)'.format(INITIAL_HYPER_DIFFICULTY))
        hyp_cursor.execute(
            'INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
                '1',
                '1683400177.0120773',
                'genesis',
                options.GENESIS_ADDRESS,
                '0',
                'c5QPId20zONTTyIYKB7zIiCu+FqrtI9dXs/NFS7cCzW56Khd+6s1+TKu/54vEREnt35yl7AhgRPK8gCuQkN6iwKHXMPZTUvt7FLS28558Y1Au3Tlo2tIj394L/Zu+jQcRxI85QOH+u00kcPaDSmkj/38btUPvxW1o/BibZ3mfNCVkVVwLdoAgNdMXGStBnwmFrvf9odWEDT/bIK7cxmAXJgvXfKtmgQFMCBglGByRE51ZkGKrFMvzY42JY/MvT5q7mAvbAcENWe7KbSjLgOVHCaZf2FIfJRLGfncjKI+Z/jPasvzelAtFTtHK39aLO4KGqC36kr5/VAGqfGDOYZCMOwdYu9KNOmTfVaV7LWyX7I5DYIV1QOTd8+20gEN5AdDulbw9Bp2o/v6dJpcC4HceZNiWtaVovH5bHAWrgY9piNCtirkV/mwqiBnprzYYz34PVbm4KkPD3d9tnwWEz/eGZnMm5AjLx/fhetaCjyfZUPiXVQ8eP+mE0ukIjOrvNemB+MP/FqYDa5SzyJI34WlWu6S/BOCn0D0YlkWLywk48lbBs1J/guHQu7DxH+0PPTD0gi6jnPLio8Ch5A78riSVgLV1xhUxMSzJ7AFKZy2V17r2L1D7qDImTprCBGqihze9hRGXgZNCS0XiT4AGuVhnRNFzsC/mTUlaBHxfbig6tY=',
                'LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQ0lqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FnOEFNSUlDQ2dLQ0FnRUFuNmVjMVBmZjVWbDJ0QlJoY3RtSgp5TVVndG92QUQzcnBNVjcwWlp1Ukk2N0llUGJiYkoveVBnSVU4S0h4RkNEZ0h1eDJOQy9CU1VkNWpyTENQZzE2CktIcVZkbHR2SUwxcWduTmNpWTJOS0VoVkxRMGppQXpBTDgvWE9NNGhMUUtjbnk2dFRpUGVjMHk1ZG5BY2UxekoKNzhCVG1FRDJLVFVQdmJLblFJMS81NlNpU2QrU1Evcnp5aStlK2MwWllFaExTMk50TzVUd0oyV3IrNlY0VW5YcgpjT0U0UysrLzR3THIyTW5GR3d6dWNlWWVOa0NIT2N5ODZmbmFpQmVsbHY1YUN0Y3V4bHFjalFQdzFDU29MaUlICkN5MnhKYkZSeHJYU21qSlRxNG1WWFlmNlFKa0s0WDZPNEtpT2NZMDNRd2tuK1dkczk0c1M4Ny9QZ3NwZEFsSzYKcEF6MU9NZFlvSWJxUUlNR3NOaS9CSlh6VHpTYTF5UnpZZnB6LzlyOUxSYm5RS3hUSzlVSWlrYlY0Ri9JdU80NApBQ29SN3BWY29FQVlJYjRUcVFDUkFYS0VRQ2trRm9RZmNZaVBaOURTbjRiMjNtSEhMWENCWUJpek5wQVdxcXZxCnlSbzVxMVhRM3lKVXVlaVNEUnVZNldEa0MyaWlFWTdYTHlzWnErYnAxS1JjSENjNDBGMnNQU2RrWWozTGJZTUgKaWJsOFd0Q21NY0lFekVKOWdwWmU4RFNrV0tTVkNjNVg3YWpoODVFVU9zaG9KTWdSMGdaQ1FkRGFkaFh5S2xKQQpvZDcvV0JFWVhMa3ZSNWl1Tkk5aHl4Y3VYWkdEaWhNeUxLMmtXaWlIRDN0M3Zadjg4MjlJbDc5NURwTm9rNmhaCnUyS0F4UmtHR1U4aFBjR1hvVVF4eEdFQ0F3RUFBUT09Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQ==',
                'fbc6d3d091d7c5ed745f499c548c103f03b96354c7bb3b3e982a128c',
                0,
                1,
                1,
                'genesis',
            )
        )
        hyp.commit()
        hyp.close()

        index = sqlite3.connect(index_path, timeout=1)
        index.text_factory = str
        index.execute('PRAGMA case_sensitive_like = 1;')
        index_cursor = index.cursor()
        index_cursor.execute('CREATE TABLE tokens (block_height INTEGER, timestamp, token, address, recipient, txid, amount INTEGER)')
        index_cursor.execute('CREATE TABLE aliases (block_height INTEGER, address, alias)')
        index_cursor.execute('CREATE INDEX "Alias Index" ON "aliases" ("block_height", "address","alias")')
        index_cursor.execute('CREATE INDEX "Token Index" ON "tokens" ("block_height","timestamp","token","address","recipient","txid","amount")')
        index_cursor.execute('CREATE TABLE staking (block_height INTEGER, timestamp NUMERIC, address, balance, ip, port, pos_address)')
        index.commit()
        index.close()

        time.sleep(2)
    except:
        traceback.print_exc()
        raise
    # print('Bootstrap successfully finished')


def check_db_for_bootstrap(node):
    upgrade = sqlite3.connect(node.ledger_path, timeout=1)
    u = upgrade.cursor()
    try:
        u.execute('SELECT * FROM transactions LIMIT 1;')
        result = u.fetchone()
        if not result:
            raise Exception()
        upgrade.close()
    except Exception as e:
        lg.warn(str(e))
        upgrade.close()
        lg.warn('Database needs upgrading, bootstrapping...')
        bootstrap()


#------------------------------------------------------------------------------


class CustomLogHandler(logging.Handler):

    def emit(self, record):
        try:
            if _Debug:
                lg.out(lg.get_debug_level() - 6, self.format(record))  # record.getMessage()
        except RecursionError:  # See issue 36272
            raise
        except Exception:
            self.handleError(record)

    def handleError(self, record):
        lg.err(self.format(record))


def custom_log(level_input='NOTSET'):
    if level_input == 'NOTSET':
        level = logging.NOTSET
    if level_input == 'DEBUG':
        level = logging.DEBUG
    if level_input == 'INFO':
        level = logging.INFO
    if level_input == 'WARNING':
        level = logging.WARNING
    if level_input == 'ERROR':
        level = logging.ERROR
    if level_input == 'CRITICAL':
        level = logging.CRITICAL

    log_formatter = logging.Formatter('%(module)s.%(funcName)s %(levelname)s %(message)s')
    my_handler = CustomLogHandler(level=level)
    my_handler.setFormatter(log_formatter)

    app_log = logging.getLogger('root')
    app_log.setLevel(level)
    app_log.addHandler(my_handler)

    return app_log
