"""
Database handler module for Bismuth nodes
"""

import time
import json
import sqlite3
import essentials
import threading
from quantizer import quantize_two
import functools
from fork import Fork
import sys
import traceback


_Debug = False


def sql_trace_callback(log, id, statement):
    line = f'SQL[{id}] {statement} in {threading.current_thread()}'
    log.warning(line)


class DbHandler:
    def __init__(self, index_db, ledger_path, hyper_path, ram, ledger_ram_file, logger, trace_db_calls=False):
        self.ram = ram
        self.ledger_ram_file = ledger_ram_file
        self.hyper_path = hyper_path
        self.logger = logger
        self.trace_db_calls = trace_db_calls
        self.index_db = index_db
        self.ledger_path = ledger_path

        self.dbs = {}

        sqlite3.threadsafety = 3

        # if trace_db_calls:
        #     sqlite3.enable_callback_tracebacks(True)

        self.index = sqlite3.connect(self.index_db, timeout=1)
        if self.trace_db_calls:
            self.index.set_trace_callback(functools.partial(sql_trace_callback, self.logger.app_log, 'INDEX'))
        self.index.text_factory = str
        self.index.execute('PRAGMA case_sensitive_like = 1;')
        self.index_cursor = self.index.cursor()
        self.dbs[str(self.index)] = self.index_db

        self.hdd = sqlite3.connect(self.ledger_path, timeout=1)
        if self.trace_db_calls:
            self.hdd.set_trace_callback(functools.partial(sql_trace_callback, self.logger.app_log, 'HDD'))
        self.hdd.text_factory = str
        self.hdd.execute('PRAGMA case_sensitive_like = 1;')
        self.h = self.hdd.cursor()
        self.dbs[str(self.hdd)] = self.ledger_path

        self.hdd2 = sqlite3.connect(self.hyper_path, timeout=1)
        if self.trace_db_calls:
            self.hdd2.set_trace_callback(functools.partial(sql_trace_callback, self.logger.app_log, 'HDD2'))
        self.hdd2.text_factory = str
        self.hdd2.execute('PRAGMA case_sensitive_like = 1;')
        self.h2 = self.hdd2.cursor()
        self.dbs[str(self.hdd2)] = self.hyper_path

        if self.ram:
            self.conn = sqlite3.connect(self.ledger_ram_file, uri=True, isolation_level=None, timeout=1)
        else:
            self.conn = sqlite3.connect(self.hyper_path, uri=True, timeout=1)
        self.dbs[str(self.conn)] = 'ram'

        if self.trace_db_calls:
            self.conn.set_trace_callback(functools.partial(sql_trace_callback, self.logger.app_log, 'CONN'))
        self.conn.execute('PRAGMA journal_mode = WAL;')
        self.conn.execute('PRAGMA case_sensitive_like = 1;')
        self.conn.text_factory = str
        self.c = self.conn.cursor()

        self.SQL_TO_TRANSACTIONS = 'INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)'
        self.SQL_TO_MISC = 'INSERT INTO misc VALUES (?,?)'

        if _Debug:
            try:
                cur_connections_src = open('/tmp/db_connections', 'r').read()
            except:
                cur_connections_src = '{"l":[]}'
            cur_connections = json.loads(cur_connections_src)
            cur_connections['l'].append(threading.current_thread().name)
            open('/tmp/db_connections', 'w').write(json.dumps(cur_connections))
            self.logger.app_log.warning(f'DB_HANDLER OPEN in {threading.current_thread().name} and currently have {len(cur_connections["l"])} opened')

    def last_block_hash(self):
        self.execute(self.c, 'SELECT block_hash FROM transactions WHERE reward != 0 ORDER BY block_height DESC LIMIT 1;')
        result = self.c.fetchone()[0]
        return result

    def pubkeyget(self, address):
        self.execute_param(self.c, 'SELECT public_key FROM transactions WHERE address = ? and reward = 0 LIMIT 1', (address, ))
        result = self.c.fetchone()[0]
        return result

    def addfromalias(self, alias):
        self.execute_param(self.index_cursor, 'SELECT address FROM aliases WHERE alias = ? ORDER BY block_height ASC LIMIT 1;', (alias, ))
        try:
            address_fetch = self.index_cursor.fetchone()[0]
        except:
            address_fetch = 'No alias'
        return address_fetch

    def tokens_user(self, tokens_address):
        self.index_cursor.execute('SELECT DISTINCT token FROM tokens WHERE address OR recipient = ?', (tokens_address, ))
        result = self.index_cursor.fetchall()
        return result

    def last_block_timestamp(self):
        self.execute(self.c, 'SELECT timestamp FROM transactions WHERE reward != 0 ORDER BY block_height DESC LIMIT 1;')
        return quantize_two(self.c.fetchone()[0])

    def difflast(self):
        self.execute(self.h, 'SELECT block_height, difficulty FROM misc ORDER BY block_height DESC LIMIT 1')
        difflast = self.h.fetchone()
        return difflast

    def annverget(self, node):
        try:
            self.execute_param(self.h, 'SELECT openfield FROM transactions WHERE address = ? AND operation = ? ORDER BY block_height DESC LIMIT 1', (
                node.genesis,
                'annver',
            ))
            result = self.h.fetchone()[0]
        except:
            result = '?'
        return result

    def annget(self, node):
        try:
            self.execute_param(self.h, 'SELECT openfield FROM transactions WHERE address = ? AND operation = ? ORDER BY block_height DESC LIMIT 1', (
                node.genesis,
                'ann',
            ))
            result = self.h.fetchone()[0]
        except:
            result = 'No announcement'
        return result

    def txsearch(self, address=None, recipient=None, operation=None, openfield=None, limit=10, offset=0, block_height_from=None):
        if not address and not recipient and not operation and not openfield:
            return []
        queries = []
        params = []
        if address:
            queries.append('address = ?')
            params.append(address)
        if recipient:
            queries.append('recipient = ?')
            params.append(recipient)
        if operation:
            queries.append('operation = ?')
            params.append(operation)
        if openfield:
            queries.append('openfield = ?')
            params.append(openfield)
        if block_height_from is not None:
            queries.append('block_height >= ?')
            params.append(block_height_from)
        params.append(offset)
        params.append(limit)
        sql = 'SELECT * FROM transactions WHERE '
        sql += ' AND '.join(queries)
        sql += ' ORDER BY block_height DESC LIMIT ?, ?;'
        try:
            # print('DB:txsearch', sql, params)
            self.execute_param(self.h, sql, tuple(params))
            result = self.h.fetchall()
        except:
            traceback.print_exc()
            return []
        return result

    def block_max_ram(self):
        self.execute(self.c, 'SELECT * FROM transactions ORDER BY block_height DESC LIMIT 1')
        return essentials.format_raw_tx(self.c.fetchone())

    def aliasget(self, alias_address):
        self.execute_param(self.index_cursor, 'SELECT alias FROM aliases WHERE address = ? ', (alias_address, ))
        result = self.index_cursor.fetchall()
        if not result:
            result = [[alias_address]]
        return result

    def aliasesget(self, aliases_request):
        results = []
        for alias_address in aliases_request:
            self.execute_param(self.index_cursor, ('SELECT alias FROM aliases WHERE address = ? ORDER BY block_height ASC LIMIT 1'), (alias_address, ))
            try:
                result = self.index_cursor.fetchall()[0][0]
            except:
                result = alias_address
            results.append(result)
        return results

    def block_height_from_hash(self, data):
        try:
            self.execute_param(self.h, 'SELECT block_height FROM transactions WHERE block_hash = ?;', (data, ))
            result = self.h.fetchone()[0]
        except:
            result = None

        return result

    def blocksync(self, block):
        blocks_fetched = []
        while sys.getsizeof(str(blocks_fetched)) < 500000:  # limited size based on txs in blocks
            # db_handler.execute_param(db_handler.h, ("SELECT block_height, timestamp,address,recipient,amount,signature,public_key,keep,openfield FROM transactions WHERE block_height > ? AND block_height <= ?;"),(str(int(client_block)),) + (str(int(client_block + 1)),))
            self.execute_param(self.h, ('SELECT timestamp,address,recipient,amount,signature,public_key,operation,openfield FROM transactions WHERE block_height > ? AND block_height <= ?;'), (
                str(int(block)),
                str(int(block + 1)),
            ))
            result = self.h.fetchall()
            if not result:
                break
            blocks_fetched.extend([result])
            block = int(block) + 1
        return blocks_fetched

    def block_height_max(self):
        self.h.execute('SELECT max(block_height) FROM transactions')
        return self.h.fetchone()[0]

    def block_height_max_diff(self):
        self.h.execute('SELECT max(block_height) FROM misc')
        return self.h.fetchone()[0]

    def block_height_max_hyper(self):
        self.h2.execute('SELECT max(block_height) FROM transactions')
        return self.h2.fetchone()[0]

    def block_height_max_diff_hyper(self):
        self.h2.execute('SELECT max(block_height) FROM misc')
        return self.h2.fetchone()[0]

    def backup_higher(self, block_height):
        'backup higher blocks than given, takes data from c, which normally means RAM'
        self.execute_param(self.c, 'SELECT * FROM transactions WHERE block_height >= ?;', (block_height, ))
        backup_data = self.c.fetchall()

        self.execute_param(self.c, 'DELETE FROM transactions WHERE block_height >= ? OR block_height <= ?', (block_height, -block_height))  #this belongs to rollback_under
        self.commit(self.conn)  #this belongs to rollback_under

        self.execute_param(self.c, 'DELETE FROM misc WHERE block_height >= ?;', (block_height, ))  #this belongs to rollback_under
        self.commit(self.conn)  #this belongs to rollback_under

        return backup_data

    def rollback_under(self, block_height):
        self.h.execute('DELETE FROM transactions WHERE block_height >= ? OR block_height <= ?', (
            block_height,
            -block_height,
        ))
        self.commit(self.hdd)

        self.h.execute('DELETE FROM misc WHERE block_height >= ?', (block_height, ))
        self.commit(self.hdd)

        self.h2.execute('DELETE FROM transactions WHERE block_height >= ? OR block_height <= ?', (
            block_height,
            -block_height,
        ))
        self.commit(self.hdd2)

        self.h2.execute('DELETE FROM misc WHERE block_height >= ?', (block_height, ))
        self.commit(self.hdd2)

    def rollback_to(self, block_height):
        # We don'tt need node to have the logger
        self.logger.app_log.error('rollback_to is deprecated, use rollback_under')
        self.rollback_under(block_height)

    def tokens_rollback(self, node, height):
        """Rollback Token index

        :param height: height index of token in chain

        Simply deletes from the `tokens` table where the block_height is
        greater than or equal to the :param height: and logs the new height

        returns None
        """
        try:
            self.execute_param(self.index_cursor, 'DELETE FROM tokens WHERE block_height >= ?;', (height, ))
            self.commit(self.index)

            node.logger.app_log.warning(f'Rolled back the token index below {(height)}')
        except Exception as e:
            node.logger.app_log.warning(f'Failed to roll back the token index below {(height)} due to {e}')

    def aliases_rollback(self, node, height):
        """Rollback Alias index

        :param height: height index of token in chain

        Simply deletes from the `aliases` table where the block_height is
        greater than or equal to the :param height: and logs the new height

        returns None
        """
        try:
            self.execute_param(self.index_cursor, 'DELETE FROM aliases WHERE block_height >= ?;', (height, ))
            self.commit(self.index)

            node.logger.app_log.warning(f'Rolled back the alias index below {(height)}')
        except Exception as e:
            node.logger.app_log.warning(f'Failed to roll back the alias index below {(height)} due to {e}')

    def dev_reward(self, node, block_array, miner_tx, mining_reward, mirror_hash):
        self.execute_param(self.c, self.SQL_TO_TRANSACTIONS, (-block_array.block_height_new, str(miner_tx.q_block_timestamp), 'Development Reward', str(node.genesis), str(mining_reward), '0', '0', mirror_hash, '0', '0', '0', '0'))
        self.commit(self.conn)

    def hn_reward(self, node, block_array, miner_tx, mirror_hash):
        fork = Fork()

        if node.is_testnet and node.last_block >= fork.POW_FORK_TESTNET:
            self.reward_sum = 24 - 10*(node.last_block + 5 - fork.POW_FORK_TESTNET)/3000000

        elif node.is_mainnet and node.last_block >= fork.POW_FORK:
            self.reward_sum = 24 - 10*(node.last_block + 5 - fork.POW_FORK)/3000000
        else:
            self.reward_sum = 24

        if self.reward_sum < 0.5:
            self.reward_sum = 0.5

        self.reward_sum = '{:.8f}'.format(self.reward_sum)

        self.execute_param(
            self.c, self.SQL_TO_TRANSACTIONS,
            (-block_array.block_height_new, str(miner_tx.q_block_timestamp), 'Hypernode Payouts', '3e08b5538a4509d9daa99e01ca5912cda3e98a7f79ca01248c2bde16', self.reward_sum, '0', '0', mirror_hash, '0', '0', '0', '0')
        )
        self.commit(self.conn)

    def to_db(self, block_array, diff_save, block_transactions):
        self.execute_param(self.c, 'INSERT INTO misc VALUES (?, ?)', (block_array.block_height_new, diff_save))
        self.commit(self.conn)

        # db_handler.execute_many(db_handler.c, self.SQL_TO_TRANSACTIONS, block_transactions)

        for transaction2 in block_transactions:
            self.execute_param(
                self.c, self.SQL_TO_TRANSACTIONS, (
                    str(transaction2[0]),
                    str(transaction2[1]),
                    str(transaction2[2]),
                    str(transaction2[3]),
                    str(transaction2[4]),
                    str(transaction2[5]),
                    str(transaction2[6]),
                    str(transaction2[7]),
                    str(transaction2[8]),
                    str(transaction2[9]),
                    str(transaction2[10]),
                    str(transaction2[11]),
                )
            )
            # secure commit for slow nodes
            self.commit(self.conn)

    def db_to_drive(self, node):
        def transactions_to_h(data):
            for x in data:  # we want to save to ledger.db
                self.execute_param(self.h, self.SQL_TO_TRANSACTIONS, (x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8], x[9], x[10], x[11]))
            self.commit(self.hdd)

        def misc_to_h(data):
            for x in data:  # we want to save to ledger.db from RAM/hyper.db depending on ram conf
                self.execute_param(self.h, self.SQL_TO_MISC, (x[0], x[1]))
            self.commit(self.hdd)

        def transactions_to_h2(data):
            for x in data:
                self.execute_param(self.h2, self.SQL_TO_TRANSACTIONS, (x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8], x[9], x[10], x[11]))
            self.commit(self.hdd2)

        def misc_to_h2(data):
            for x in data:
                self.execute_param(self.h2, self.SQL_TO_MISC, (x[0], x[1]))
            self.commit(self.hdd2)

        try:
            if node.is_regnet:
                node.hdd_block = node.last_block
                node.hdd_hash = node.last_block_hash
                self.logger.app_log.warning(f'Chain: Regnet simulated move to HDD')
                return
            node.logger.app_log.warning(f'Chain: Moving new data to HDD, {node.hdd_block + 1} to {node.last_block} in {threading.current_thread()}')

            self.execute_param(
                self.c,
                'SELECT * FROM transactions '
                'WHERE block_height > ? OR block_height < ? '
                'ORDER BY block_height ASC',
                (node.hdd_block, -node.hdd_block),
            )

            result1 = self.c.fetchall()

            transactions_to_h(result1)
            if node.ram:  # we want to save to hyper.db from RAM/hyper.db depending on ram conf
                transactions_to_h2(result1)

            self.execute_param(self.c, 'SELECT * FROM misc WHERE block_height > ? ORDER BY block_height ASC', (node.hdd_block, ))
            result2 = self.c.fetchall()

            misc_to_h(result2)
            if node.ram:  # we want to save to hyper.db from RAM
                misc_to_h2(result2)

            node.hdd_block = node.last_block
            node.hdd_hash = node.last_block_hash

            node.logger.app_log.warning(f'Chain: {len(result1)} txs moved to HDD')
        except Exception as e:
            node.logger.app_log.warning(f'Chain: Exception Moving new data to HDD: {e}')
            # app_log.warning("Ledger digestion ended")  # dup with more informative digest_block notice.

    def commit(self, connection):
        """Secure commit for slow nodes"""
        sleep_delay = 0.5
        while True:
            try:
                connection.commit()
                break
            except Exception as e:
                self.logger.app_log.warning(f'Database {self.dbs.get(str(connection), "???")} connection error {e} in {threading.current_thread()}')
                self.logger.app_log.warning(f'Current threads: {",".join(map(lambda t: t.name, threading.enumerate()))}')
                time.sleep(sleep_delay)
                # sleep_delay += 1

    def execute(self, cursor, query):
        """Secure execute for slow nodes"""
        self.logger.app_log.debug(f'Execute {query} in {threading.current_thread()}')
        sleep_delay = 0.5
        while True:
            try:
                cursor.execute(query)
                break
            except sqlite3.InterfaceError as e:
                self.logger.app_log.warning(f'Database query to abort: {cursor} {query[:100]}')
                self.logger.app_log.warning(f'Database abortion reason: {e} in {threading.current_thread()}')
                break
            except sqlite3.IntegrityError as e:
                self.logger.app_log.warning(f'Database query to abort: {cursor} {query[:100]}')
                self.logger.app_log.warning(f'Database abortion reason: {e} in {threading.current_thread()}')
                break
            except Exception as e:
                self.logger.app_log.warning(f'Database query: {cursor.connection} {query[:100]}')
                self.logger.app_log.warning(f'Database retry reason: {e} in {threading.current_thread()}')
                self.logger.app_log.warning(f'Current threads: {",".join(map(lambda t: t.name, threading.enumerate()))}')
                time.sleep(sleep_delay)
                # sleep_delay += 1

    def execute_param(self, cursor, query, param):
        """Secure execute w/ param for slow nodes"""
        self.logger.app_log.debug(f'Execute with param {query} in {threading.current_thread()}')
        sleep_delay = 0.5
        while True:
            try:
                cursor.execute(query, param)
                break
            except sqlite3.InterfaceError as e:
                self.logger.app_log.warning(f'Database query to abort: {cursor} {str(query)[:100]} {str(param)[:100]}')
                self.logger.app_log.warning(f'Database abortion reason: {e} in {threading.current_thread()}')
                break
            except sqlite3.IntegrityError as e:
                self.logger.app_log.warning(f'Database query to abort: {cursor} {str(query)[:100]}')
                self.logger.app_log.warning(f'Database abortion reason: {e} in {threading.current_thread()}')
                break
            except Exception as e:
                self.logger.app_log.warning(f'Database query: {cursor.connection} {str(query)[:100]} {str(param)[:100]}')
                self.logger.app_log.warning(f'Database retry reason: {e} in {threading.current_thread()}')
                self.logger.app_log.warning(f'Current threads: {",".join(map(lambda t: t.name, threading.enumerate()))}')
                time.sleep(sleep_delay)
                # sleep_delay += 1

    def fetchall(self, cursor, query, param=None):
        """Helper to simplify calling code, execute and fetch in a single line instead of 2"""
        if param is None:
            self.execute(cursor, query)
        else:
            self.execute_param(cursor, query, param)
        return cursor.fetchall()

    def fetchone(self, cursor, query, param=None):
        """Helper to simplify calling code, execute and fetch in a single line instead of 2"""
        if param is None:
            self.execute(cursor, query)
        else:
            self.execute_param(cursor, query, param)
        res = cursor.fetchone()
        if res:
            return res[0]
        return None

    def close(self):
        try:
            self.index.close()
            self.hdd.close()
            self.hdd2.close()
            self.conn.close()
        except:
            traceback.print_exc()

        if _Debug:
            try:
                cur_connections_src = open('/tmp/db_connections', 'r').read()
            except:
                cur_connections_src = '{"l":[]}'
            cur_connections = json.loads(cur_connections_src)
            if threading.current_thread().name in cur_connections['l']:
                cur_connections['l'].remove(threading.current_thread().name)
            else:
                self.logger.app_log.warning(f'NOT FOUND opened DB connection in {threading.current_thread().name}')
            open('/tmp/db_connections', 'w').write(json.dumps(cur_connections))
            self.logger.app_log.warning(f'DB_HANDLER CLOSED in {threading.current_thread().name} and currently have {len(cur_connections["l"])} opened')
