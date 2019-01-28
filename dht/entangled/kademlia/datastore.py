#!/usr/bin/env python
# datastore.py
#
# Copyright (C) 2007-2008 Francois Aucamp, Meraka Institute, CSIR
# See AUTHORS for all authors and contact information. 
# 
# License: GNU Lesser General Public License, version 3 or later; see COPYING
#          included in this archive for details.
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

from __future__ import absolute_import
import six
import traceback

try:
    from UserDict import DictMixin
except ImportError:
    from collections import MutableMapping as DictMixin

import sqlite3
import six.moves.cPickle as pickle
import os
import base64

from . import constants  # @UnresolvedImport
from . import encoding  # @UnresolvedImport


try:
    buffer = buffer  # @UndefinedVariable
except:
    buffer = memoryview


PICKLE_PROTOCOL = 2

_Debug = False


class DataStore(DictMixin):
    """
    Interface for classes implementing physical storage (for data published via
    the "STORE" RPC) for the Kademlia DHT.

    @note: This provides an interface for a dict-like object
    """

    def keys(self):
        """
        Return a list of the keys in this data store.
        """

    def lastPublished(self, key):
        """
        Get the time the C{(key, value)} pair identified by C{key} was last
        published.
        """

    def originalPublisherID(self, key):
        """
        Get the original publisher of the data's node ID.

        @param key: The key that identifies the stored data
        @type key: str

        @return: Return the node ID of the original publisher of the
        C{(key, value)} pair identified by C{key}.
        """

    def originalPublishTime(self, key):
        """
        Get the time the C{(key, value)} pair identified by C{key} was
        originally published.
        """

    def getItem(self, key):
        """
        """

    def setItem(self, key, value, lastPublished, originallyPublished, originalPublisherID, **kwargs):
        """
        Set the value of the (key, value) pair identified by C{key}; this
        should set the "last published" value for the (key, value) pair to the
        current time.
        """

    def __getitem__(self, key):
        """
        Get the value identified by C{key}
        """

    def __setitem__(self, key, value):
        """
        Convenience wrapper to C{setItem}; this accepts a tuple in the format:
        (value, lastPublished, originallyPublished, originalPublisherID)
        """
        self.setItem(key, *value)

    def __delitem__(self, key):
        """
        Delete the specified key (and its value)
        """

    def __iter__(self):
        """
        """
        return self

    def __next__(self):
        """
        """

    def __len__(self):
        """
        """


class DictDataStore(DataStore):
    """
    A datastore using an in-memory Python dictionary.
    """

    def __init__(self):
        # Dictionary format:
        # { <key>: (<value>, <lastPublished>, <originallyPublished> <originalPublisherID>) }
        self._dict = {}

    def keys(self):
        """
        Return a list of the keys in this data store.
        """
        return list(self._dict.keys())

    def lastPublished(self, key):
        """
        Get the time the C{(key, value)} pair identified by C{key} was last
        published.
        """
        return self._dict[key][1]

    def originalPublisherID(self, key):
        """
        Get the original publisher of the data's node ID.

        @param key: The key that identifies the stored data
        @type key: str

        @return: Return the node ID of the original publisher of the
        C{(key, value)} pair identified by C{key}.
        """
        return self._dict[key][3]

    def originalPublishTime(self, key):
        """
        Get the time the C{(key, value)} pair identified by C{key} was
        originally published.
        """
        return self._dict[key][2]

    def setItem(self, key, value, lastPublished, originallyPublished, originalPublisherID, **kwargs):
        """
        Set the value of the (key, value) pair identified by C{key}; this
        should set the "last published" value for the (key, value) pair to the
        current time.
        """
        self._dict[key] = (value, lastPublished, originallyPublished, originalPublisherID)

    def __getitem__(self, key):
        """
        Get the value identified by C{key}
        """
        return self._dict[key][0]

    def __delitem__(self, key):
        """
        Delete the specified key (and its value)
        """
        del self._dict[key]

    def getItem(self, key):
        try:
            row = self._dict[key]
            result = dict(
                key=row[0].encode(),
                value=row[1],
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=None if not row[4] else row[4].encode(),
            )
        except:
            return None
        return result


class SQLiteDataStore(DataStore):
    """
    Example of a SQLite database-based datastore.
    """

    def __init__(self, dbFile=':memory:'):
        """
        @param dbFile: The name of the file containing the SQLite database; if
                       unspecified, an in-memory database is used.
        @type dbFile: str
        """
        createDB = not os.path.exists(dbFile)
        self._db = sqlite3.connect(dbFile)
        self._db.isolation_level = None
        self._db.text_factory = str
        if createDB:
            self._db.execute('CREATE TABLE data(key, value, lastPublished, originallyPublished, originalPublisherID)')
        self._cursor = self._db.cursor()

    def keys(self):
        """
        Return a list of the keys in this data store.
        """
        keys = []
        try:
            self._cursor.execute("SELECT key FROM data")
            for row in self._cursor:
#                 key = row[0]
#                 if not isinstance(key, six.text_type):
#                     key = key.decode()
#                 decodedKey = codecs.decode(key, 'hex')            
#                 keys.append(decodedKey)
                # keys.append(row[0].decode('hex'))
                keys.append(encoding.decode_hex(row[0]))
        finally:
            return keys

    def keys64(self):
        """
        Return a list of the keys in this data store.
        """
        keys = []
        try:
            self._cursor.execute("SELECT key FROM data")
            for row in self._cursor:
                keys.append(base64.b64encode(encoding.decode_hex(row[0])))
        finally:
            return keys

    def lastPublished(self, key):
        """
        Get the time the C{(key, value)} pair identified by C{key} was last
        published.
        """
        return int(self._dbQuery(key, 'lastPublished'))

    def originalPublisherID(self, key):
        """
        Get the original publisher of the data's node ID.

        @param key: The key that identifies the stored data
        @type key: str

        @return: Return the node ID of the original publisher of the
        C{(key, value)} pair identified by C{key}.
        """
        return self._dbQuery(key, 'originalPublisherID')

    def originalPublishTime(self, key):
        """
        Get the time the C{(key, value)} pair identified by C{key} was
        originally published.
        """
        return int(self._dbQuery(key, 'originallyPublished'))

    def setItem(self, key, value, lastPublished, originallyPublished, originalPublisherID, **kwargs):
        # Encode the key so that it doesn't corrupt the database
        # encodedKey = key.encode('hex')
#         if not isinstance(key, six.binary_type):
#             key = key.encode()
#         encodedKey = codecs.encode(key, 'hex')
        encodedKey = encoding.encode_hex(key)
        self._cursor.execute("select key from data where key=:reqKey", {'reqKey': encodedKey})
        if self._cursor.fetchone() is None:
            self._cursor.execute('INSERT INTO data(key, value, lastPublished, originallyPublished, originalPublisherID) VALUES (?, ?, ?, ?, ?)', (
                encodedKey,
                buffer(pickle.dumps(value, PICKLE_PROTOCOL)),
                lastPublished,
                originallyPublished,
                originalPublisherID,
            ))
        else:
            self._cursor.execute('UPDATE data SET value=?, lastPublished=?, originallyPublished=?, originalPublisherID=? WHERE key=?', (
                buffer(pickle.dumps(value, PICKLE_PROTOCOL)),
                lastPublished,
                originallyPublished,
                originalPublisherID,
                encodedKey,
            ))

    def _dbQuery(self, key, columnName, unpickle=False):
        try:
            self._cursor.execute("SELECT %s FROM data WHERE key=:reqKey" % columnName, {
                'reqKey': encoding.encode_hex(key), 
            })
            row = self._cursor.fetchone()
            value = row[0]
        except TypeError:
            raise KeyError(key)
        else:
            if unpickle:
                if six.PY2:
                    if isinstance(value, buffer):
                        value = str(value)
                    return pickle.loads(value)
                else:
                    return pickle.loads(value, encoding='bytes')
            else:
                return value

    def __getitem__(self, key):
        return self._dbQuery(key, 'value', unpickle=True)

    def __delitem__(self, key):
        self._cursor.execute("DELETE FROM data WHERE key=:reqKey", {
            'reqKey': encoding.encode_hex(key),
        })

    def getItem(self, key, unpickle=False):
        try:
            self._cursor.execute("SELECT * FROM data WHERE key=:reqKey", {
                'reqKey': encoding.encode_hex(key),
            })
            row = self._cursor.fetchone()

            if unpickle:
                if six.PY2:
                    if isinstance(row[1], buffer):
                        value = str(row[1])
                    value = pickle.loads(row[1])
                else:
                    value = pickle.loads(value, encoding='bytes')
            else:
                value = row[1]

            result = dict(
                key=row[0].encode(),
                value=value,
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=None if not row[4] else row[4].encode(),
            )
        except:
            return None
        return result


class SQLiteExpiredDataStore(SQLiteDataStore):
    """
    Example of a SQLite database-based datastore.
    """

    def __init__(self, dbFile=':memory:'):
        """
        @param dbFile: The name of the file containing the SQLite database; if
                       unspecified, an in-memory database is used.
        @type dbFile: str
        """
        createDB = not os.path.exists(dbFile)
        self._db = sqlite3.connect(dbFile)
        self._db.isolation_level = None
        self._db.text_factory = str
        if createDB:
            self._db.execute('CREATE TABLE data(key, value, lastPublished, originallyPublished, originalPublisherID, expireSeconds)')
        self._cursor = self._db.cursor()
        
    def expireSeconds(self, key):
        """
        """
        return int(self._dbQuery(key, 'expireSeconds'))

    def setItem(self,
                key,
                value,
                lastPublished,
                originallyPublished,
                originalPublisherID,
                expireSeconds=constants.dataExpireSecondsDefaut,
                **kwargs):
        # Encode the key so that it doesn't corrupt the database
        # encodedKey = key.encode('hex')
#         if not isinstance(key, six.binary_type):
#             key = key.encode()
#         encodedKey = codecs.encode(key, 'hex')
        encodedKey = encoding.encode_hex(key)
        self._cursor.execute("select key from data where key=:reqKey", {'reqKey': encodedKey})
        if self._cursor.fetchone() is None:
            self._cursor.execute('INSERT INTO data(key, value, lastPublished, originallyPublished, originalPublisherID, expireSeconds) VALUES (?, ?, ?, ?, ?, ?)', (
                encodedKey,
                buffer(pickle.dumps(value, PICKLE_PROTOCOL)),
                lastPublished,
                originallyPublished,
                originalPublisherID,
                expireSeconds,
            ))
            if _Debug:
                print('stored new value for key %s' % base64.b64encode(key))
        else:
            self._cursor.execute('UPDATE data SET value=?, lastPublished=?, originallyPublished=?, originalPublisherID=?, expireSeconds=? WHERE key=?', (
                buffer(pickle.dumps(value, PICKLE_PROTOCOL)),
                lastPublished,
                originallyPublished,
                originalPublisherID,
                expireSeconds,
                encodedKey,
            ))
            if _Debug:
                print('updated existing value for key %s' % base64.b64encode(key))

    def getItem(self, key, unpickle=False):
        try:
            # if not isinstance(key, six.binary_type):
            #     key = key.encode()
            # encodedKey = codecs.encode(key, 'hex')            
            self._cursor.execute("SELECT * FROM data WHERE key=:reqKey", {
                # 'reqKey': key.encode('hex'),
                # 'reqKey': encodedKey,
                'reqKey': encoding.encode_hex(key),
            })
            row = self._cursor.fetchone()

            if unpickle:
                if six.PY2:
                    if isinstance(row[1], buffer):
                        value = str(row[1])
                    value = pickle.loads(row[1])
                else:
                    value = pickle.loads(value, encoding='bytes')
            else:
                value = row[1]
            
            result = dict(
                key=row[0].encode(),
                value=value,
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=None if not row[4] else row[4].encode(),
                expireSeconds=row[5],
            )
        except:
            if _Debug:
                print('returned None for key %s' % base64.b64encode(key))
            return None
        if _Debug:
            print('returned dict object for key %s' % base64.b64encode(key))
        return result

    def getAllItems(self, unpickle=False):
        self._cursor.execute("SELECT * FROM data")
        rows = self._cursor.fetchall()
        items = []
        for row in rows:
            value = row[1]
            if unpickle:
                if six.PY2:
                    if isinstance(value, buffer):
                        value = str(value)
                    value = pickle.loads(value)
                else:
                    value = pickle.loads(value, encoding='bytes')
            items.append(dict(
                key=row[0].encode(),
                key64=base64.b64encode(row[0].encode()),
                value=value,
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=None if not row[4] else row[4].encode(),
                expireSeconds=row[5],
            ))
        return items


class SQLiteVersionedDataStore(SQLiteExpiredDataStore):
    """
    """

    def __init__(self, dbFile=':memory:'):
        """
        @param dbFile: The name of the file containing the SQLite database; if
                       unspecified, an in-memory database is used.
        @type dbFile: str
        """
        createDB = not os.path.exists(dbFile)
        self._db = sqlite3.connect(dbFile)
        self._db.isolation_level = None
        self._db.text_factory = str
        if createDB:
            self._db.execute('CREATE TABLE data(key, value, lastPublished, originallyPublished, originalPublisherID, expireSeconds, revision)')
        self._cursor = self._db.cursor()

    def revision(self, key):
        """
        """
        try:
            return int(self._dbQuery(key, 'revision'))
        except KeyError:
            return 0

    def setItem(self,
                key,
                value,
                lastPublished,
                originallyPublished,
                originalPublisherID,
                expireSeconds=constants.dataExpireSecondsDefaut,
                **kwargs):
        # Encode the key so that it doesn't corrupt the database
        # encodedKey = key.encode('hex')
#         if not isinstance(key, six.binary_type):
#             key = key.encode()
#         encodedKey = codecs.encode(key, 'hex')
        encodedKey = encoding.encode_hex(key)
        new_revision = kwargs.get('revision', None)
        if new_revision is None:
            new_revision = self.revision(key) + 1
        self._cursor.execute("select key from data where key=:reqKey", {'reqKey': encodedKey})
        if self._cursor.fetchone() is None:
            self._cursor.execute('INSERT INTO data(key, value, lastPublished, originallyPublished, originalPublisherID, expireSeconds, revision) VALUES (?, ?, ?, ?, ?, ?, ?)', (
                encodedKey,
                buffer(pickle.dumps(value, PICKLE_PROTOCOL)),
                lastPublished,
                originallyPublished,
                encoding.encode_hex(originalPublisherID),
                expireSeconds,
                new_revision,
            ))
            if _Debug:
                print('stored new value for key %s' % base64.b64encode(key))
        else:
            self._cursor.execute('UPDATE data SET value=?, lastPublished=?, originallyPublished=?, originalPublisherID=?, expireSeconds=?, revision=? WHERE key=?', (
                buffer(pickle.dumps(value, PICKLE_PROTOCOL)),
                lastPublished,
                originallyPublished,
                encoding.encode_hex(originalPublisherID),
                expireSeconds,
                new_revision,
                encodedKey,
            ))
            if _Debug:
                print('updated existing value for key %s' % base64.b64encode(key))

    def getItem(self, key, unpickle=False):
        try:
            # if not isinstance(key, six.binary_type):
            #     key = key.encode()
            # encodedKey = codecs.encode(key, 'hex')            
            self._cursor.execute("SELECT * FROM data WHERE key=:reqKey", {
                # 'reqKey': key.encode('hex'),
                # 'reqKey': encodedKey,
                'reqKey': encoding.encode_hex(key),
            })
            row = self._cursor.fetchone()

            if unpickle:
                if six.PY2:
                    if isinstance(row[1], buffer):
                        value = str(row[1])
                    value = pickle.loads(row[1])
                else:
                    value = pickle.loads(value, encoding='bytes')
            else:
                value = row[1]
            
            result = dict(
                key=row[0].encode(),
                value=value,
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=None if not row[4] else encoding.decode_hex(row[4]),
                expireSeconds=row[5],
                revision=row[6],
            )
        except:
            if _Debug:
                print('returned None for key %s' % base64.b64encode(key))
            return None
        if _Debug:
            print('returned dict object for key %s' % base64.b64encode(key))
        return result

    def getAllItems(self, unpickle=False):
        self._cursor.execute("SELECT * FROM data")
        rows = self._cursor.fetchall()
        items = []
        for row in rows:
            value = row[1]
            if unpickle:
                if six.PY2:
                    if isinstance(value, buffer):
                        value = str(value)
                    value = pickle.loads(value)
                else:
                    value = pickle.loads(value, encoding='bytes')
            try:
                _k = encoding.decode_hex(row[0], as_string=True)
                _k64 = base64.b64encode(encoding.decode_hex(row[0])).decode()
                _opID = None if not row[4] else base64.b64encode(encoding.decode_hex(row[4])).decode()
            except:
                traceback.print_exc()
            items.append(dict(
                key=_k,
                key64=_k64,
                value=value,
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=_opID,
                expireSeconds=row[5],
                revision=row[6],
            ))
        return items
