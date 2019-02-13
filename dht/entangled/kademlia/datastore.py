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

try:
    from UserDict import DictMixin
except ImportError:
    from collections import MutableMapping as DictMixin

import sqlite3
import os
import json

from . import constants  # @UnresolvedImport
from . import encoding  # @UnresolvedImport


try:
    buffer = buffer  # @UndefinedVariable
except:
    buffer = memoryview


PROTOCOL_VERSION = 1

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



class SQLiteVersionedJsonDataStore(DataStore):
    """
    SQLite database-based datastore.
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
        self._db.text_factory = encoding.to_text
        if createDB:
            self.create_table()
            if _Debug:
                print('[DHT DB]   Created empty table for DHT records')
        self._cursor = self._db.cursor()

    def _dbQuery(self, key, columnName):
        try:
            self._cursor.execute("SELECT %s FROM data WHERE key=:reqKey" % columnName, {
                'reqKey': key,
            })
            row = self._cursor.fetchone()
            value = row[0]
        except:
            raise KeyError(key)
        else:
            return value

    def __getitem__(self, key):
        v = self._dbQuery(key, 'value')
        v = json.loads(v)
        return v['d']

    def __delitem__(self, key):
        self._cursor.execute("DELETE FROM data WHERE key=:reqKey", {
            'reqKey': key,
        })

    def create_table(self):
        self._db.execute('CREATE TABLE data(key, value, lastPublished, originallyPublished, originalPublisherID, expireSeconds, revision)')

    def keys(self):
        """
        Return a list of the keys in this data store.
        """
        keys = []
        try:
            self._cursor.execute("SELECT key FROM data")
            for row in self._cursor:
                keys.append(row[0])
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

    def expireSeconds(self, key):
        """
        """
        return int(self._dbQuery(key, 'expireSeconds'))

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
        key_hex = encoding.to_text(key)
        new_revision = kwargs.get('revision', None)
        if new_revision is None:
            new_revision = self.revision(key) + 1
        self._cursor.execute("select key from data where key=:reqKey", {'reqKey': key_hex})
        opID = originalPublisherID or None
        if self._cursor.fetchone() is None:
            self._cursor.execute('INSERT INTO data(key, value, lastPublished, originallyPublished, originalPublisherID, expireSeconds, revision) VALUES (?, ?, ?, ?, ?, ?, ?)', (
                key_hex,
                json.dumps({'k': key_hex, 'd': value, 'v': PROTOCOL_VERSION, }, ),
                lastPublished,
                originallyPublished,
                opID,
                expireSeconds,
                new_revision,
            ))
            if _Debug:
                print('[DHT DB]       setItem  stored new value for key [%s] with revision %d' % (key, new_revision))
        else:
            self._cursor.execute('UPDATE data SET value=?, lastPublished=?, originallyPublished=?, originalPublisherID=?, expireSeconds=?, revision=? WHERE key=?', (
                json.dumps({'k': key_hex, 'd': value, 'v': PROTOCOL_VERSION, }, ),
                lastPublished,
                originallyPublished,
                opID,
                expireSeconds,
                new_revision,
                key_hex,
            ))
            if _Debug:
                print('[DHT DB]        setItem  updated existing value for key [%s] with revision %d' % (key, new_revision))

    def getItem(self, key):
        key_hex = key
        key_hex = encoding.to_text(key)
        self._cursor.execute("SELECT * FROM data WHERE key=:reqKey", {
            'reqKey': key_hex,
        })

        row = self._cursor.fetchone()
        if not row:
            if _Debug:
                print('[DHT DB]         getItem [%s]  return None : did not found key in dataStore' % key)
            return None

        v = row[1]
        if isinstance(v, buffer):
            v = encoding.to_text(v)

        v = json.loads(v)
        
        # TODO: check / verify v['k'] against key_hex
        # TODO: check / verify v['v'] against PROTOCOL_VERSION

        value = v['d']

        key_orig = row[0]

        # TODO: check / verify key_orig against key

        opID = row[4] or None

        result = dict(
            key=key_orig,
            value=value,
            lastPublished=row[2],
            originallyPublished=row[3],
            originalPublisherID=opID,
            expireSeconds=row[5],
            revision=row[6],
        )

        if _Debug:
            print('[DHT DB]               getItem   found one record for key [%s], revision is %d' % (key, row[6]))
        return result

    def getAllItems(self):
        self._cursor.execute("SELECT * FROM data")
        rows = self._cursor.fetchall()
        items = []
        for row in rows:

            v = row[1]
            if isinstance(v, buffer):
                v = encoding.to_text(v)

            v = json.loads(v)
            
            # TODO: check / verify v['k'] against key_hex
            # TODO: check / verify v['v'] against PROTOCOL_VERSION
    
            value = v['d']

            _k = row[0]
            _opID = row[4] or None

            items.append(dict(
                value=value,
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=_opID,
                expireSeconds=row[5],
                revision=row[6],
            ))
        return items
