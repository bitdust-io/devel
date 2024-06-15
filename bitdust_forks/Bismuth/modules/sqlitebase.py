"""
A common ancestor for sqlite related storage objects.

Used by mempool and poschain
beware : module now shared by the wallet server.
"""

import aiosqlite3
# import aiosqlite as aiosqlite3
import time
import asyncio

__version__ = '0.0.3'


class SqliteBase:
    """
    Generic Sqlite storage backend.
    """
    def __init__(self, verbose=False, db_path='./data/', db_name='posmempool.db', app_log=None, ram=False):
        self.db_path = db_path + db_name
        self.db_name = db_name
        self.app_log = app_log
        self.verbose = verbose
        self.db = None
        self.legacy_db = True
        self.cursor = None
        self.check()
        self.async_db = None

    # ========================= Generic DB Handling Methods ====================

    def check(self):
        """
        Checks and creates db. This is not async yet, so we close afterward.
        :return:
        """
        # self.app_log.info("Virtual Method {} Check".format(self.db_name))
        pass

    def execute(self, sql, param=None, cursor=None, commit=False):
        """
        Safely execute the request
        :param sql:
        :param param:
        :param cursor: optional. will use the locked shared cursor if None
        :param commit: optional. will commit after sql
        :return:
        """
        if not self.db:
            raise ValueError('Closed {} DB'.format(self.db_name))
        tries = 0
        while True:
            try:
                if not cursor:
                    cursor = self.cursor
                if param:
                    cursor.execute(sql, param)
                else:
                    cursor.execute(sql)
                break
            except Exception as e:
                self.app_log.warning('Database query {}: {}'.format(self.db_name, sql))
                self.app_log.warning('Database retry reason: {}'.format(e))
                tries += 1
                if tries >= 10:
                    self.app_log.error('Database Error, closing')
                    raise ValueError('Too many retries')
                time.sleep(0.1)

        if commit:
            self.commit()
            cursor.close()
            cursor = None
        return cursor

    async def schema(self):
        """Connects to the db by asking sql"""
        await self.async_execute('SELECT sql FROM sqlite_master')
        await self.async_commit()

    async def async_execute(self, sql, param=None, commit=False):
        """
        Safely execute the request
        :param sql:
        :param param:
        :param commit: If True, will commit after the request.
        :return: a cursor async proxy, or None if commit. If not commit, cursor() has to be close.
        """
        if not self.async_db:
            # TODO: RAM Mode
            try:
                # open
                if self.verbose:
                    self.app_log.info('Opening async {} db'.format(self.db_name))
                self.async_db = await aiosqlite3.connect(self.db_path, loop=asyncio.get_event_loop())
                cursor = await self.async_db.cursor()
                await cursor.execute('PRAGMA case_sensitive_like = 1;')
                await cursor.close()
                # self.async_db.row_factory = sqlite3.Row
                self.async_db.text_factory = str
            except Exception as e:
                self.app_log.warning('async_execute {}: {}'.format(self.db_name, e))
        # TODO: add a try count and die if we lock
        max_tries = 10
        while max_tries:
            try:
                # print("temp await cursor")
                cursor = await self.async_db.cursor()
                # print("temp await execute")
                if param:
                    await cursor.execute(sql, param)
                else:
                    await cursor.execute(sql)
                break
            except Exception as e:
                self.app_log.warning('Database query: {} {}'.format(sql, param))
                self.app_log.warning('Database {} retry reason: {}'.format(self.db_name, e))
                await asyncio.sleep(0.1)
                max_tries -= 1
        if not max_tries:
            raise ValueError('Too many retries')
        if commit:
            await self.async_commit()
            await cursor.close()
            cursor = None
        return cursor

    def commit(self):
        """
        Safe commit
        :return:
        """
        if not self.db:
            raise ValueError('Closed {} DB'.format(self.db_name))
        while True:
            try:
                self.db.commit()
                break
            except Exception as e:
                self.app_log.warning('Database {} retry reason: {}'.format(self.db_name, e))
                time.sleep(0.1)

    async def async_commit(self):
        """
        Safe commit
        :return:
        """
        while True:
            try:
                await self.async_db.commit()
                break
            except Exception as e:
                self.app_log.warning('Database {} retry reason: {}'.format(self.db_name, e))
                await asyncio.sleep(0.1)

    async def async_fetchone(self, sql, param=None, as_dict=False):
        """
        Fetch one and Returns data
        :param sql:
        :param param:
        :return:
        """
        # print("temp fetch one 1")
        cursor = await self.async_execute(sql, param)
        # print("temp cursor fetch one")
        data = await cursor.fetchone()
        # print("temp cursor close")
        await cursor.close()
        if not data:
            return None
        if as_dict:
            return dict(data)
        return tuple(data)

    async def async_fetchall(self, sql, param=None):
        """
        Fetch all and Returns data
        :param sql:
        :param param:
        :return:
        """
        cursor = await self.async_execute(sql, param)
        data = await cursor.fetchall()
        await cursor.close()
        return data

    async def async_vacuum(self):
        """
        Maintenance
        :return:
        """
        await self.async_execute('VACUUM', commit=True)

    def close(self):
        if self.db:
            self.db.close()

    async def async_close(self):
        # TODO: make sure we call when closing.
        if self.async_db:
            await self.async_db.close()
        if self.verbose:
            self.app_log.info('Closed async {} db'.format(self.db_name))
