import os
import time
import shutil
import threading
import socks
import sqlite3
import traceback

from twisted.internet.defer import Deferred
from twisted.internet import reactor

VERSION = '1.0.0.0'

_DataDirPath = None


def init(data_dir_path):
    global _DataDirPath
    _DataDirPath = data_dir_path
    starting_defer = Deferred()
    node_thread = threading.Thread(target=run, args=(data_dir_path, starting_defer, ))
    node_thread.start()
    return starting_defer


def shutdown():
    global _DataDirPath

    from bitdust_forks.Bismuth import options
    from bitdust_forks.Bismuth import connections

    config_path = os.path.join(_DataDirPath, 'config')
    custom_config_path = os.path.join(_DataDirPath, 'config_custom')

    config = options.Get()
    config.read(filename=config_path, custom_filename=custom_config_path)
    version = config.version

    s = socks.socksocket()
    port = config.port
    if 'testnet' in version:
        port = 2829
        print('tesnet mode')
    elif 'regnet' in version:
        print('Regtest mode')
        port = 3030

    count = 0
    while count < 3:
        try:
            s.connect(('127.0.0.1', port))
            print('Sending stop command...')
            connections.send(s, 'stop')
            print('Stop command delivered.')
            break
        except:
            print('Cannot reach node, retrying...')
            time.sleep(0.1)
            count += 1

    s.close()
    return True


def run(data_dir_path, starting_defer):
    global _DataDirPath

    from bitdust_forks.Bismuth import mempool
    from bitdust_forks.Bismuth import apihandler
    from bitdust_forks.Bismuth import dbhandler
    from bitdust_forks.Bismuth import log
    from bitdust_forks.Bismuth import options
    from bitdust_forks.Bismuth import peershandler
    from bitdust_forks.Bismuth import plugins
    # from bitdust_forks.Bismuth import mining_heavy3
    from bitdust_forks.Bismuth import node as bismuth_node
    from bitdust_forks.Bismuth.libs import node as _node, logger, keys
    from bitdust_forks.Bismuth.modules import config as modules_config

    _DataDirPath = data_dir_path
    if not os.path.exists(data_dir_path):
        os.makedirs(data_dir_path)

    config_path = os.path.join(data_dir_path, 'config')
    custom_config_path = os.path.join(data_dir_path, 'config_custom')

    if not os.path.isfile(config_path):
        create_config_file(data_dir_path)

    node = _node.Node()
    bismuth_node.node = node
    bismuth_node.bootstrap = bootstrap

    options.Get.defaults['heavy3_path'] = os.path.join(data_dir_path, 'heavy3a.bin')
    options.Get.defaults['mempool_path'] = os.path.join(data_dir_path, 'mempool.db')
    modules_config.Get.defaults['db_path'] = data_dir_path
    modules_config.Get.defaults['mempool_path'] = os.path.join(data_dir_path, 'mempool.db')

    node.data_dir_path = data_dir_path

    node.logger = logger.Logger()
    node.keys = keys.Keys()

    node.is_testnet = False
    node.is_regnet = False
    node.is_mainnet = True

    config = options.Get()
    config.read(filename=config_path, custom_filename=custom_config_path)

    node.app_version = VERSION

    node.version = config.version
    node.debug_level = config.debug_level
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
    node.heavy3_path = config.heavy3_path
    node.old_sqlite = config.old_sqlite
    node.heavy = config.heavy

    node.logger.app_log = log.log('node.log', node.debug_level, node.terminal_output)
    node.logger.app_log.warning('Configuration settings loaded')
    node.logger.app_log.warning(f'Python version: {node.py_version}')

    if not node.full_ledger and os.path.exists(node.ledger_path) and node.is_mainnet:
        os.remove(node.ledger_path)
        node.logger.app_log.warning('Removed full ledger for hyperblock mode')
    if not node.full_ledger:
        node.logger.app_log.warning('Cloning hyperblocks to ledger file')
        shutil.copy(node.hyper_path, node.ledger_path)

    try:
        node.plugin_manager = plugins.PluginManager(app_log=node.logger.app_log, config=config, init=True)
        extra_commands = {}
        extra_commands = node.plugin_manager.execute_filter_hook('extra_commands_prefixes', extra_commands)

        setup_net_type(bismuth_node.node, data_dir_path)
        bismuth_node.load_keys()

        node.logger.app_log.warning(f'Checking Heavy3 file, can take up to 5 minutes...')
        # mining_heavy3.mining_open(node.heavy3_path)
        node.logger.app_log.warning(f'Heavy3 file Ok!')

        node.logger.app_log.warning(f'Status: Starting node version {VERSION}')
        node.startup_time = time.time()
        try:

            node.peers = peershandler.Peers(node.logger.app_log, config=config, node=node)

            node.apihandler = apihandler.ApiHandler(node.logger.app_log, config)
            mempool.MEMPOOL = mempool.Mempool(node.logger.app_log, config, node.db_lock, node.is_testnet, trace_db_calls=node.trace_db_calls)

            check_db_for_bootstrap(node)

            db_handler_initial = dbhandler.DbHandler(node.index_db, node.ledger_path, node.hyper_path, node.ram, node.ledger_ram_file, node.logger, trace_db_calls=node.trace_db_calls)
            bismuth_node.db_handler_initial = db_handler_initial

            try:
                bismuth_node.ledger_check_heights(node, db_handler_initial)
            except:
                traceback.print_exc()

            bismuth_node.ram_init(db_handler_initial)
            bismuth_node.node_block_init(db_handler_initial)
            bismuth_node.initial_db_check()

            if not node.is_regnet:
                bismuth_node.sequencing_check(db_handler_initial)

            if node.verify:
                bismuth_node.verify(db_handler_initial)

            bismuth_node.add_indices(db_handler_initial)

            if not node.tor:
                host, port = '0.0.0.0', int(node.port)

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

            from bitdust_forks.Bismuth import connectionmanager
            connection_manager = connectionmanager.ConnectionManager(node, mempool)
            connection_manager.start()

        except Exception as e:
            node.logger.app_log.info(e)
            reactor.callFromThread(starting_defer.errback, e)  # @UndefinedVariable
            raise

    except Exception as e:
        node.logger.app_log.info(e)
        reactor.callFromThread(starting_defer.errback, e)  # @UndefinedVariable
        raise

    node.logger.app_log.warning('Status: Bismuth loop running.')

    reactor.callFromThread(starting_defer.callback, True)  # @UndefinedVariable

    while True:
        if node.IS_STOPPING:
            if node.db_lock.locked():
                time.sleep(0.5)
            else:
                # mining_heavy3.mining_close()
                node.logger.app_log.warning('Status: Securely disconnected main processes, subprocess termination in progress.')
                break
        time.sleep(0.1)
    node.logger.app_log.warning('Status: Clean Stop')


def create_config_file(data_dir_path):
    config_path = os.path.join(data_dir_path, 'config')
    config_src = '''debug=False
port=5658
verify=False
version=mainnet0001
version_allow=mainnet0001
thread_limit=64
rebuild_db=True
debug_level=DEBUG
purge=True
pause=6
hyper_path={hyper_path}
hyper_recompress=True
full_ledger=True
ledger_path={ledger_path}
ban_threshold=30
tor=False
allowed=127.0.0.1,192.168.0.1,any
ram=False
heavy=False
node_ip=127.0.0.1
light_ip={light_ip}
reveal_address=True
accept_peers=True
banlist=127.1.2.3
whitelist=127.0.0.1
nodes_ban_reset=5
mempool_allowed=1aae2cfe5d01acc8d7cbc90fcf8bb715ca24927504d0d8071c0979c7
terminal_output=False
gui_scaling=adapt
mempool_ram=False
egress=True
trace_db_calls=False
heavy3_path={heavy3_path}'''.format(
        hyper_path=os.path.join(data_dir_path, 'hyper.db'),
        ledger_path=os.path.join(data_dir_path, 'ledger.db'),
        heavy3_path=os.path.join(data_dir_path, 'heavy3a.bin'),
        light_ip='{"127.0.0.1": "5658"}',
    )
    fout = open(config_path, 'w')
    fout.write(config_src)
    fout.flush()
    fout.close()


def setup_net_type(node, data_dir_path):
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

    node.logger.app_log.warning(f'Testnet: {node.is_testnet}')
    node.logger.app_log.warning(f'Regnet : {node.is_regnet}')

    node.peerfile = os.path.join(data_dir_path, 'peers')
    node.ledger_ram_file = 'file:ledger?mode=memory&cache=shared'
    node.index_db = os.path.join(data_dir_path, 'index.db')


def bootstrap():
    global _DataDirPath
    from bitdust_forks.Bismuth import options

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
    print('Bootstrap successfully finished')


def check_db_for_bootstrap(node):
    upgrade = sqlite3.connect(node.ledger_path)
    u = upgrade.cursor()
    try:
        u.execute('SELECT * FROM transactions LIMIT 1;')
        result = u.fetchone()
        if not result:
            raise Exception()
        upgrade.close()
    except Exception as e:
        print(e)
        upgrade.close()
        print('Database needs upgrading, bootstrapping...')
        bootstrap()
