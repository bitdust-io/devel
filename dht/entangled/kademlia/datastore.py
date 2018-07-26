#!/usr/bin/env python
# datastore.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (datastore.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
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
import six.moves.cPickle as pickle
import os

from . import constants


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

    def getItem(self, key):
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
                key=row[0],
                value=str(row[1]),
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=row[4],
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
                keys.append(row[0].decode('hex'))
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
        encodedKey = key.encode('hex')
        self._cursor.execute("select key from data where key=:reqKey", {'reqKey': encodedKey})
        if self._cursor.fetchone() is None:
            self._cursor.execute('INSERT INTO data(key, value, lastPublished, originallyPublished, originalPublisherID) VALUES (?, ?, ?, ?, ?)', (
                encodedKey, buffer(pickle.dumps(value, pickle.HIGHEST_PROTOCOL)), lastPublished, originallyPublished, originalPublisherID))
        else:
            self._cursor.execute('UPDATE data SET value=?, lastPublished=?, originallyPublished=?, originalPublisherID=? WHERE key=?', (
                buffer(pickle.dumps(value, pickle.HIGHEST_PROTOCOL)), lastPublished, originallyPublished, originalPublisherID, encodedKey))

    def _dbQuery(self, key, columnName, unpickle=False):
        try:
            self._cursor.execute("SELECT %s FROM data WHERE key=:reqKey" % columnName, {'reqKey': key.encode('hex')})
            row = self._cursor.fetchone()
            value = str(row[0])
        except TypeError:
            raise KeyError(key)
        else:
            if unpickle:
                return pickle.loads(value)
            else:
                return value

    def __getitem__(self, key):
        return self._dbQuery(key, 'value', unpickle=True)

    def __delitem__(self, key):
        self._cursor.execute("DELETE FROM data WHERE key=:reqKey", {'reqKey': key.encode('hex')})

    def getItem(self, key):
        try:
            self._cursor.execute("SELECT * FROM data WHERE key=:reqKey", {'reqKey': key.encode('hex')})
            row = self._cursor.fetchone()
            result = dict(
                key=row[0],
                value=str(row[1]),
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=row[4],
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
        encodedKey = key.encode('hex')
        self._cursor.execute("select key from data where key=:reqKey", {'reqKey': encodedKey})
        if self._cursor.fetchone() is None:
            self._cursor.execute('INSERT INTO data(key, value, lastPublished, originallyPublished, originalPublisherID, expireSeconds) VALUES (?, ?, ?, ?, ?, ?)', (
                encodedKey, buffer(pickle.dumps(value, pickle.HIGHEST_PROTOCOL)), lastPublished, originallyPublished, originalPublisherID, expireSeconds))
        else:
            self._cursor.execute('UPDATE data SET value=?, lastPublished=?, originallyPublished=?, originalPublisherID=?, expireSeconds=? WHERE key=?', (
                buffer(pickle.dumps(value, pickle.HIGHEST_PROTOCOL)), lastPublished, originallyPublished, originalPublisherID, expireSeconds, encodedKey))

    def getItem(self, key):
        try:
            self._cursor.execute("SELECT * FROM data WHERE key=:reqKey", {'reqKey': key.encode('hex')})
            row = self._cursor.fetchone()
            result = dict(
                key=row[0],
                value=str(row[1]),
                lastPublished=row[2],
                originallyPublished=row[3],
                originalPublisherID=row[4],
                expireSeconds=row[5],
            )
        except:
            return None
        return result

