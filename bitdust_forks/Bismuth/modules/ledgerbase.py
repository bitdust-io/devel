from modules.sqlitebase import SqliteBase


class LedgerBase(SqliteBase):
    """
    Generic Sqlite storage backend.
    """
    def __init__(self, verbose=False, db_path='./data/', db_name='posmempool.db', app_log=None, ram=False):
        super().__init__(verbose=verbose, db_path=db_path, db_name=db_name, app_log=app_log, ram=ram)
        self.legacy_db = True

    async def check_db_version(self):
        schema = await self.async_fetchall("PRAGMA table_info('transactions')")
        # print(schema)
        """
        [(0, 'block_height', 'INTEGER', 0, None, 0),
        (1, 'timestamp', 'NUMERIC', 0, None, 0),
        (2, 'address', 'TEXT', 0, None, 0), (3, 'recipient', 'TEXT', 0, None, 0),
        (4, 'amount', 'INTEGER', 0, None, 0), (5, 'signature', 'BINARY', 0, None, 0),
        (6, 'public_key', 'BINARY', 0, None, 0), (7, 'block_hash', 'BINARY', 0, None, 0),
        (8, 'fee', 'INTEGER', 0, None, 0), (9, 'reward', 'INTEGER', 0, None, 0),
        (10, 'operation', 'TEXT', 0, None, 0), (11, 'openfield', 'TEXT', 0, None, 0)]
        """
        if schema[4][2] == 'INTEGER':
            self.legacy_db = False
            self.app_log.warning('V2 DB')
        else:
            self.app_log.warning('Legacy DB')
