#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011-2013 Codernity (http://codernity.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import absolute_import
import six

from CodernityDB3.index import (Index,
                               IndexException,
                               DocIdNotFound,
                               ElemNotFound,
                               TryReindexException,
                               IndexPreconditionsException)

import os
import hashlib
import marshal
import io
import struct
import shutil
import codecs

from CodernityDB3.storage import IU_Storage, DummyStorage

from CodernityDB3.env import cdb_environment

if cdb_environment.get('rlock_obj'):
    from CodernityDB3 import patch
    patch.patch_cache_rr(cdb_environment['rlock_obj'])

from CodernityDB3.rr_cache import cache1lvl


from CodernityDB3.misc import random_hex_32

try:
    from CodernityDB3 import __version__
except ImportError:
    from .__init__ import __version__


class IU_HashIndex(Index):
    """
    That class is for Internal Use only, if you want to use HashIndex just subclass the :py:class:`HashIndex` instead this one.

    That design is because main index logic should be always in database not in custom user indexes.
    """

    def __init__(self, db_path, name, entry_line_format='<32s{key}IIcI', hash_lim=0xfffff, storage_class=None, key_format='c'):
        """
        The index is capable to solve conflicts by `Separate chaining`
        :param db_path: database path
        :type db_path: string
        :param name: index name
        :type name: ascii string
        :param line_format: line format, `key_format` parameter value will replace `{key}` if present.
        :type line_format: string (32s{key}IIcI by default) {doc_id}{hash_key}{start}{size}{status}{next}
        :param hash_lim: maximum hash functon results (remember about birthday problem) count from 0
        :type hash_lim: integer
        :param storage_class: Storage class by default it will open standard :py:class:`CodernityDB3.storage.Storage` (if string has to be accesible by globals()[storage_class])
        :type storage_class: class name which will be instance of CodernityDB3.storage.Storage instance or None
        :param key_format: a index key format
        """
        # Fix types
        if isinstance(db_path, six.text_type):
            db_path = db_path.encode()
        if isinstance(name, six.text_type):
            name = name.encode()

        if key_format and '{key}' in entry_line_format:
            entry_line_format = entry_line_format.replace('{key}', key_format)
        super(IU_HashIndex, self).__init__(db_path, name)
        self.hash_lim = hash_lim
        if not storage_class:
            storage_class = IU_Storage
        if storage_class and not isinstance(storage_class, six.string_types):
            storage_class = storage_class.__name__
        self.storage_class = storage_class
        self.storage = None

        self.bucket_line_format = "<I"
        self.bucket_line_size = struct.calcsize(self.bucket_line_format)
        self.entry_line_format = entry_line_format
        self.entry_line_size = struct.calcsize(self.entry_line_format)

        cache = cache1lvl(100)
        self._find_key = cache(self._find_key)
        self._locate_doc_id = cache(self._locate_doc_id)
        self.bucket_struct = struct.Struct(self.bucket_line_format)
        self.entry_struct = struct.Struct(self.entry_line_format)
        self.data_start = (
            self.hash_lim + 1) * self.bucket_line_size + self._start_ind + 2

    def _fix_params(self):
        super(IU_HashIndex, self)._fix_params()
        self.bucket_line_size = struct.calcsize(self.bucket_line_format)
        self.entry_line_size = struct.calcsize(self.entry_line_format)
        self.bucket_struct = struct.Struct(self.bucket_line_format)
        self.entry_struct = struct.Struct(self.entry_line_format)
        self.data_start = (
            self.hash_lim + 1) * self.bucket_line_size + self._start_ind + 2

    def open_index(self):
        if not os.path.isfile(os.path.join(self.db_path, self.name + '_buck')):
            raise IndexException("Doesn't exists")
        self.buckets = io.open(
            os.path.join(self.db_path, self.name + "_buck"), 'r+b', buffering=0)
        self._fix_params()
        self._open_storage()

    def create_index(self):
        if os.path.isfile(os.path.join(self.db_path, self.name + '_buck')):
            raise IndexException('Already exists')
        with io.open(os.path.join(self.db_path, self.name + "_buck"), 'w+b') as f:
            props = dict(name=self.name,
                         bucket_line_format=self.bucket_line_format,
                         entry_line_format=self.entry_line_format,
                         hash_lim=self.hash_lim,
                         version=self.__version__,
                         storage_class=self.storage_class)
            f.write(marshal.dumps(props))
        self.buckets = io.open(
            os.path.join(self.db_path, self.name + "_buck"), 'r+b', buffering=0)
        self._create_storage()

    def destroy(self):
        super(IU_HashIndex, self).destroy()
        self._clear_cache()

    def _open_storage(self):
        s = globals()[self.storage_class]
        if not self.storage:
            self.storage = s(self.db_path, self.name)
        self.storage.open()

    def _create_storage(self):
        s = globals()[self.storage_class]
        if not self.storage:
            self.storage = s(self.db_path, self.name)
        self.storage.create()

    # def close_index(self):
    #     self.buckets.flush()
    #     self.buckets.close()
    #     self.storage.close()
#    @lfu_cache(100)
    def _find_key(self, key):
        """
        Find the key position

        :param key: the key to find
        """
        # print('IU_HashIndex._find_key %r' % key)
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()

        start_position = self._calculate_position(key)
        self.buckets.seek(start_position)
        curr_data = self.buckets.read(self.bucket_line_size)
        if curr_data:
            location = self.bucket_struct.unpack(curr_data)[0]
            if not location:
                return None, None, 0, 0, 'u'
            found_at, doc_id, l_key, start, size, status, _next = self._locate_key(
                key, location)
            if status == b'd' or status == 'd':  # when first record from many is deleted
                while True:
                    found_at, doc_id, l_key, start, size, status, _next = self._locate_key(
                        key, _next)
                    if status != b'd' and status != 'd':
                        break
            return doc_id, l_key, start, size, status
        else:
            return None, None, 0, 0, 'u'

    def _find_key_many(self, key, limit=1, offset=0):
        # print('IU_HashIndex._find_key_many %r' % key)
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()

        location = None
        start_position = self._calculate_position(key)
        self.buckets.seek(start_position)
        curr_data = self.buckets.read(self.bucket_line_size)
        if curr_data:
            location = self.bucket_struct.unpack(curr_data)[0]
        while offset:
            if not location:
                break
            try:
                found_at, doc_id, l_key, start, size, status, _next = self._locate_key(
                    key, location)
            except IndexException:
                break
            else:
                if status != b'd' and status != 'd':
                    if l_key == key:  # in case of hash function conflicts
                        offset -= 1
                location = _next
        while limit:
            if not location:
                break
            try:
                found_at, doc_id, l_key, start, size, status, _next = self._locate_key(
                    key, location)
            except IndexException:
                break
            else:
                if status != b'd' and status != 'd':
                    if l_key == key:  # in case of hash function conflicts
                        yield doc_id, start, size, status
                        limit -= 1
                location = _next

    def _calculate_position(self, key):
        # Fix types
        if isinstance(key, int):
            key = str(key)
        if isinstance(key, six.text_type):
            key = key.encode()
        pos = abs(int(hashlib.md5(key).hexdigest(), 16) & self.hash_lim) * self.bucket_line_size + self._start_ind
        # pos = abs(hash(key) & self.hash_lim) * self.bucket_line_size + self._start_ind
        # print('IU_HashIndex._calculate_position hash_lim=%r bucket_line_size=%r _start_ind=%r  %r -> %r' % (
        #     self.hash_lim, self.bucket_line_size, self._start_ind, key, pos))
        return pos

    # TODO add cache!
    def _locate_key(self, key, start):
        """
        Locate position of the key, it will iterate using `next` field in record
        until required key will be find.

        :param key: the key to locate
        :param start: position to start from
        """
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()

        location = start
        while True:
            self.buckets.seek(location)
            data = self.buckets.read(self.entry_line_size)
            # todo, maybe partial read there...
            try:
                doc_id, l_key, start, size, status, _next = self.entry_struct.unpack(data)
                # print('IU_HashIndex._locate_key key=%r %r doc_id=%r l_key=%r start=%r size=%r status=%r _next=%r' % (key, self.name, doc_id, l_key, start, size, status, _next))
            except struct.error:
                # print('ElemNotFound 1')
                raise ElemNotFound(
                    "Not found")  # not found but might be also broken
            if l_key == key:
                break
            else:
                if not _next:
                    # print('ElemNotFound 2')
                    # not found
                    raise ElemNotFound("Not found")
                else:
                    location = _next  # go to next record
        return location, doc_id, l_key, start, size, status, _next

#    @lfu_cache(100)
    def _locate_doc_id(self, doc_id, key, start):
        """
        Locate position of the doc_id, it will iterate using `next` field in record
        until required key will be find.

        :param doc_id: the doc_id to locate
        :param key: key value
        :param start: position to start from
        """
        # Fix types
        if isinstance(doc_id, six.text_type):
            doc_id = doc_id.encode()
        if isinstance(key, six.text_type):
            key = key.encode()

        location = start
        while True:
            self.buckets.seek(location)
            data = self.buckets.read(self.entry_line_size)
            try:
                l_doc_id, l_key, start, size, status, _next = self.entry_struct.unpack(data)
            except:
                raise DocIdNotFound(
                    "Doc_id %r for %r not found" % (doc_id, key))
            if l_doc_id == doc_id and l_key == key:  # added for consistency
                break
            else:
                if not _next:
                    # not found
                    raise DocIdNotFound(
                        "Doc_id %r for %r not found" % (doc_id, key))
                else:
                    location = _next  # go to next record
        return location, doc_id, l_key, start, size, status, _next

    def _find_place(self, start):
        """
        Find a place to where put the key. It will iterate using `next` field in record, until
        empty `next` found

        :param start: position to start from
        """
        location = start
        while True:
            self.buckets.seek(location)
            data = self.buckets.read(self.entry_line_size)
            # todo, maybe partial read there...
            doc_id, l_key, start, size, status, _next = self.entry_struct.unpack(data)
            if not _next or (status == b'd' or status == 'd'):
                return self.buckets.tell() - self.entry_line_size, doc_id, l_key, start, size, status, _next
            else:
                location = _next  # go to next record

    def update(self, doc_id, key, u_start=0, u_size=0, u_status='o'):
        # print('IU_HashIndex.update %r' % key)
        # Fix types
        if isinstance(doc_id, six.text_type):
            doc_id = doc_id.encode()
        if isinstance(key, six.text_type):
            key = key.encode()
        if isinstance(u_status, six.text_type):
            u_status = u_status.encode()

        start_position = self._calculate_position(key)
        self.buckets.seek(start_position)
        curr_data = self.buckets.read(self.bucket_line_size)
        # test if it's unique or not really unique hash
        if curr_data:
            location = self.bucket_struct.unpack(curr_data)[0]
        else:
            raise ElemNotFound("Location %r not found" % doc_id)
        found_at, _doc_id, _key, start, size, status, _next = self._locate_doc_id(doc_id, key, location)
        self.buckets.seek(found_at)
        self.buckets.write(self.entry_struct.pack(doc_id,
                                                  key,
                                                  u_start,
                                                  u_size,
                                                  u_status,
                                                  _next))
        self.flush()
        self._find_key.delete(key)
        self._locate_doc_id.delete(doc_id)
        return True

    def insert(self, doc_id, key, start, size, status='o'):
        # print('IU_HashIndex.insert %r' % key)
        # Fix types
        if isinstance(doc_id, six.text_type):
            doc_id = doc_id.encode()
        if isinstance(key, six.text_type):
            key = key.encode()
        if isinstance(status, six.text_type):
            status = status.encode()

        start_position = self._calculate_position(key)
        self.buckets.seek(start_position)
        curr_data = self.buckets.read(self.bucket_line_size)

        # conflict occurs?
        if curr_data:
            location = self.bucket_struct.unpack(curr_data)[0]
        else:
            location = 0
        if location:
            # last key with that hash
            try:
                found_at, _doc_id, _key, _start, _size, _status, _next = self._locate_doc_id(doc_id, key, location)
            except DocIdNotFound:
                found_at, _doc_id, _key, _start, _size, _status, _next = self._find_place(location)
                self.buckets.seek(0, 2)
                wrote_at = self.buckets.tell()
                self.buckets.write(self.entry_struct.pack(doc_id,
                                                          key,
                                                          start,
                                                          size,
                                                          status,
                                                          _next))
#                self.flush()
                self.buckets.seek(found_at)
                self.buckets.write(self.entry_struct.pack(_doc_id,
                                                          _key,
                                                          _start,
                                                          _size,
                                                          _status,
                                                          wrote_at))
            else:
                self.buckets.seek(found_at)
                self.buckets.write(self.entry_struct.pack(doc_id,
                                                          key,
                                                          start,
                                                          size,
                                                          status,
                                                          _next))
            self.flush()
            self._locate_doc_id.delete(doc_id)
            self._find_key.delete(_key)
            # self._find_key.delete(key)
            # self._locate_key.delete(_key)
            return True
            # raise NotImplementedError
        else:
            self.buckets.seek(0, 2)
            wrote_at = self.buckets.tell()

            # check if position is bigger than all hash entries...
            if wrote_at < self.data_start:
                self.buckets.seek(self.data_start)
                wrote_at = self.buckets.tell()

            self.buckets.write(self.entry_struct.pack(doc_id,
                                                      key,
                                                      start,
                                                      size,
                                                      status,
                                                      0))
#            self.flush()
            self._find_key.delete(key)
            self.buckets.seek(start_position)
            self.buckets.write(self.bucket_struct.pack(wrote_at))
            self.flush()
            return True

    def get(self, key):
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()
        doc_id, l_key, start, size, status = self._find_key(self.make_key(key))
        return doc_id, l_key, start, size, status

    def get_many(self, key, limit=1, offset=0):
        return self._find_key_many(self.make_key(key), limit, offset)

    def all(self, limit=-1, offset=0):
        # print('hash_index.all data_start=%r entry_line_size=%r key_format=%r' % (self.data_start, self.entry_line_size, self.key_format))
        self.buckets.seek(self.data_start)
        while offset:
            curr_data = self.buckets.read(self.entry_line_size)
            if not curr_data:
                break
            try:
                doc_id, key, start, size, status, _next = self.entry_struct.unpack(curr_data)
                # print('hash_index.all while offset doc_id=%r key=%r start=%r size=%r status=%r next=%r' % (doc_id, key, start, size, status, _next))
            except IndexException as exc:
                # print('IndexException while offset: %r' % exc)
                break
            else:
                if status != b'd' and status != 'd':
                    offset -= 1
        while limit:
            curr_data = self.buckets.read(self.entry_line_size)
            if not curr_data:
                break
            try:
                doc_id, key, start, size, status, _next = self.entry_struct.unpack(curr_data)
                # print('hash_index.all while limit doc_id=%r key=%r start=%r size=%r status=%r next=%r' % (doc_id, key, start, size, status, _next))
            except IndexException:
                # print('IndexException while limit: %r' % exc)
                break
            else:
                if status != b'd' and status != 'd':
                    yield doc_id, key, start, size, status
                    limit -= 1

    def _fix_link(self, key, pos_prev, pos_next):
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()

        # CHECKIT why I need that hack
        if pos_prev >= self.data_start:
            self.buckets.seek(pos_prev)
            data = self.buckets.read(self.entry_line_size)
            if data:
                doc_id, l_key, start, size, status, _next = self.entry_struct.unpack(data)
                self.buckets.seek(pos_prev)
                self.buckets.write(self.entry_struct.pack(doc_id,
                                                          l_key,
                                                          start,
                                                          size,
                                                          status,
                                                          pos_next))
                self.flush()
        if pos_next:
            self.buckets.seek(pos_next)
            data = self.buckets.read(self.entry_line_size)
            if data:
                doc_id, l_key, start, size, status, _next = self.entry_struct.unpack(data)
                self.buckets.seek(pos_next)
                self.buckets.write(self.entry_struct.pack(doc_id,
                                                          l_key,
                                                          start,
                                                          size,
                                                          status,
                                                          _next))
                self.flush()
        return

    def delete(self, doc_id, key, start=0, size=0):
        # print('IU_HashIndex.delete %r' % key)
        # Fix types
        if isinstance(doc_id, six.text_type):
            doc_id = doc_id.encode()
        if isinstance(key, six.text_type):
            key = key.encode()

        start_position = self._calculate_position(key)
        self.buckets.seek(start_position)
        curr_data = self.buckets.read(self.bucket_line_size)
        if curr_data:
            location = self.bucket_struct.unpack(curr_data)[0]
        else:
            # case happens when trying to delete element with new index key in data
            # after adding new index to database without reindex
            # print("failed to delete doc_id=%r  key=%r" % (doc_id, key))
            raise TryReindexException()
        found_at, _doc_id, _key, start, size, status, _next = self._locate_doc_id(doc_id, key, location)
        self.buckets.seek(found_at)
        self.buckets.write(self.entry_struct.pack(doc_id,
                                                  key,
                                                  start,
                                                  size,
                                                  b'd',
                                                  _next))
        self.flush()
        # self._fix_link(_key, _prev, _next)
        self._find_key.delete(key)
        self._locate_doc_id.delete(doc_id)
        return True

    def compact(self, hash_lim=None):

        if not hash_lim:
            hash_lim = self.hash_lim

        compact_ind = self.__class__(
            self.db_path, self.name + '_compact', hash_lim=hash_lim)
        compact_ind.create_index()

        gen = self.all()
        while True:
            try:
                doc_id, key, start, size, status = next(gen)
            except StopIteration:
                break
            self.storage._f.seek(start)
            value = self.storage._f.read(size)
            start_ = compact_ind.storage._f.tell()
            compact_ind.storage._f.write(value)
            compact_ind.insert(doc_id, key, start_, size, status)

        compact_ind.close_index()
        original_name = self.name
        # os.unlink(os.path.join(self.db_path, self.name + "_buck"))
        self.close_index()
        shutil.move(os.path.join(compact_ind.db_path, compact_ind.
                                 name + "_buck"), os.path.join(self.db_path, self.name + "_buck"))
        shutil.move(os.path.join(compact_ind.db_path, compact_ind.
                                 name + "_stor"), os.path.join(self.db_path, self.name + "_stor"))
        # self.name = original_name
        self.open_index()  # reload...
        self.name = original_name
        self._save_params(dict(name=original_name))
        self._fix_params()
        self._clear_cache()
        return True

    def make_key(self, key):
        if isinstance(key, six.text_type):
            return codecs.encode(key, 'utf-8')
        return key

    def make_key_value(self, data):
        return b'1', data

    def _clear_cache(self):
        self._find_key.clear()
        self._locate_doc_id.clear()

    def close_index(self):
        super(IU_HashIndex, self).close_index()
        self._clear_cache()


class IU_UniqueHashIndex(IU_HashIndex):
    """
    Index for *unique* keys! Designed to be a **id** index.

    That class is for Internal Use only, if you want to use UniqueHashIndex just subclass the :py:class:`UniqueHashIndex` instead this one.

    That design is because main index logic should be always in database not in custom user indexes.
    """

    def __init__(self, db_path, name, entry_line_format="<32s8sIIcI", *args, **kwargs):
        # Fix types
        if isinstance(db_path, six.text_type):
            db_path = db_path.encode()
        if isinstance(name, six.text_type):
            name = name.encode()

        if 'key' in kwargs:
            raise IndexPreconditionsException(
                "UniqueHashIndex doesn't accept key parameter'")
        super(IU_UniqueHashIndex, self).__init__(db_path, name,
                                                 entry_line_format, *args, **kwargs)
        self.create_key = random_hex_32  # : set the function to create random key when no _id given
        # self.entry_struct=struct.Struct(entry_line_format)

#    @lfu_cache(100)
    def _find_key(self, key):
        """
        Find the key position

        :param key: the key to find
        """
        # Fix types
        # print('IU_UniqueHashIndex._find_key %r' % key)
        if isinstance(key, six.text_type):
            key = key.encode()

        start_position = self._calculate_position(key)
        self.seek = self.buckets.seek(start_position)
        curr_data = self.buckets.read(self.bucket_line_size)
        if curr_data:
            location = self.bucket_struct.unpack(curr_data)[0]
            found_at, l_key, rev, start, size, status, _next = self._locate_key(
                key, location)

            # Fix types
            if isinstance(l_key, bytes):
                l_key = l_key.decode()
            if isinstance(rev, bytes):
                rev = rev.decode()
            if isinstance(status, bytes):
                status = status.decode()

            return l_key, rev, start, size, status
        else:
            return None, None, 0, 0, 'u'

    def _find_key_many(self, *args, **kwargs):
        raise NotImplementedError()

    def _find_place(self, start, key):
        """
        Find a place to where put the key. It will iterate using `next` field in record, until
        empty `next` found

        :param start: position to start from
        """
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()

        location = start
        while True:
            self.buckets.seek(location)
            data = self.buckets.read(self.entry_line_size)
            # todo, maybe partial read there...
            l_key, rev, start, size, status, _next = self.entry_struct.unpack(
                data)
            if l_key == key:
                raise IndexException("The %r key already exists" % key)
            if not _next or (status == b'd' or status == 'd'):
                return self.buckets.tell() - self.entry_line_size, l_key, rev, start, size, status, _next
            else:
                location = _next  # go to next record

    # @lfu_cache(100)
    def _locate_key(self, key, start):
        """
        Locate position of the key, it will iterate using `next` field in record
        until required key will be find.

        :param key: the key to locate
        :param start: position to start from
        """
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()

        location = start
        while True:
            self.buckets.seek(location)
            data = self.buckets.read(self.entry_line_size)
            # todo, maybe partial read there...
            try:
                l_key, rev, start, size, status, _next = self.entry_struct.unpack(data)
                # print('IU_UniqueHashIndex._locate_key %r key=%r start=%r location=%r l_key=%r rev=%r start=%r size=%r status=%r _next=%r' % (
                #     self.name, key, start, location, l_key, rev, start, size, status, _next))
            except struct.error:
                # print("Location %r not found 1" % key)
                raise ElemNotFound("Location %r not found" % key)
            if l_key == key:
                break
            else:
                if not _next:
                    # not found
                    # print("Location %r not found 2" % key)
                    raise ElemNotFound("Location %r not found" % key)
                else:
                    location = _next  # go to next record
        return self.buckets.tell() - self.entry_line_size, l_key, rev, start, size, status, _next

    def update(self, key, rev, u_start=0, u_size=0, u_status='o'):
        # print('IU_UniqueHashIndex.update %r' % key)
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()
        if isinstance(rev, six.text_type):
            rev = rev.encode()
        if isinstance(u_status, six.text_type):
            u_status = u_status.encode()

        start_position = self._calculate_position(key)
        self.buckets.seek(start_position)
        curr_data = self.buckets.read(self.bucket_line_size)
        # test if it's unique or not really unique hash

        if curr_data:
            location = self.bucket_struct.unpack(curr_data)[0]
        else:
            raise ElemNotFound("Location %r not found" % key)
        found_at, _key, _rev, start, size, status, _next = self._locate_key(
            key, location)
        if u_start == 0:
            u_start = start
        if u_size == 0:
            u_size = size
        self.buckets.seek(found_at)
        self.buckets.write(self.entry_struct.pack(key,
                                                  rev,
                                                  u_start,
                                                  u_size,
                                                  u_status,
                                                  _next))
        self.flush()
        self._find_key.delete(key)
        return True

    def insert(self, key, rev, start, size, status='o'):
        # print('IU_UniqueHashIndex.insert %r' % key)
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()
        if isinstance(rev, six.text_type):
            rev = rev.encode()
        if isinstance(status, six.text_type):
            status = status.encode()

        start_position = self._calculate_position(key)
        self.buckets.seek(start_position)
        curr_data = self.buckets.read(self.bucket_line_size)

        # conflict occurs?
        if curr_data:
            location = self.bucket_struct.unpack(curr_data)[0]
        else:
            location = 0
        if location:
            # last key with that hash
            found_at, _key, _rev, _start, _size, _status, _next = self._find_place(
                location, key)
            self.buckets.seek(0, 2)
            wrote_at = self.buckets.tell()

            # check if position is bigger than all hash entries...
            if wrote_at < self.data_start:
                self.buckets.seek(self.data_start)
                wrote_at = self.buckets.tell()

            self.buckets.write(self.entry_struct.pack(key,
                                                      rev,
                                                      start,
                                                      size,
                                                      status,
                                                      _next))

#            self.flush()
            self.buckets.seek(found_at)
            self.buckets.write(self.entry_struct.pack(_key,
                                                      _rev,
                                                      _start,
                                                      _size,
                                                      _status,
                                                      wrote_at))
            self.flush()
            self._find_key.delete(_key)
            # self._locate_key.delete(_key)
            return True
            # raise NotImplementedError
        else:
            self.buckets.seek(0, 2)
            wrote_at = self.buckets.tell()

            # check if position is bigger than all hash entries...
            if wrote_at < self.data_start:
                self.buckets.seek(self.data_start)
                wrote_at = self.buckets.tell()

            self.buckets.write(self.entry_struct.pack(key,
                                                      rev,
                                                      start,
                                                      size,
                                                      status,
                                                      0))

            self.buckets.seek(start_position)
            self.buckets.write(self.bucket_struct.pack(wrote_at))
            self.flush()
            self._find_key.delete(key)
            return True

    def all(self, limit=-1, offset=0):
        self.buckets.seek(self.data_start)
        while offset:
            curr_data = self.buckets.read(self.entry_line_size)
            if not curr_data:
                break
            try:
                doc_id, rev, start, size, status, next = self.entry_struct.unpack(curr_data)
                # print('IU_UniqueHashIndex.all while offset %r doc_id=%r rev=%r start=%r size=%r status=%r next=%r' % (self.name, doc_id, rev, start, size, status, next))
            except IndexException:
                break
            else:
                if status != b'd' and status != 'd':
                    offset -= 1

        while limit:
            curr_data = self.buckets.read(self.entry_line_size)
            if not curr_data:
                break
            try:
                doc_id, rev, start, size, status, next = self.entry_struct.unpack(curr_data)
                # print('IU_UniqueHashIndex.all while limit %r doc_id=%r rev=%r start=%r size=%r status=%r next=%r' % (self.name, doc_id, rev, start, size, status, next))
            except IndexException:
                break
            else:
                if status != b'd' and status != 'd':
                    if isinstance(rev, six.binary_type):
                        rev = rev.decode()
                    if isinstance(doc_id, six.binary_type):
                        doc_id = doc_id.decode()
                    yield doc_id, rev, start, size, status
                    limit -= 1

    def get_many(self, *args, **kwargs):
        raise NotImplementedError()

    def delete(self, key, start=0, size=0):
        # Fix types
        if isinstance(key, six.text_type):
            key = key.encode()
        self.update(key, '00000000', start, size, b'd')

    def make_key_value(self, data):
        _id = data['_id']
        try:
            _id = data['_id']
            if isinstance(_id, six.text_type):
                _id = _id.encode()
        except:
            raise IndexPreconditionsException(
                "_id must be valid string/bytes object")
        if not isinstance(_id, bytes) or len(_id) != 32:
            raise IndexPreconditionsException("Invalid _id type or lenght")
        del data['_id']
        del data['_rev']
        return _id, data

    def destroy(self):
        Index.destroy(self)
        self._clear_cache()

    def _clear_cache(self):
        self._find_key.clear()

    def insert_with_storage(self, _id, _rev, value):
        # Fix types
        if isinstance(_id, six.text_type):
            _id = _id.encode()
        if isinstance(_rev, six.text_type):
            _rev = _rev.encode()
        if value:
            start, size = self.storage.insert(value)
        else:
            start = 1
            size = 0
        return self.insert(_id, _rev, start, size)

    def update_with_storage(self, _id, _rev, value):
        # Fix types
        if isinstance(_id, six.text_type):
            _id = _id.encode()
        if isinstance(_rev, six.text_type):
            _rev = _rev.encode()

        if value:
            start, size = self.storage.insert(value)
        else:
            start = 1
            size = 0
        return self.update(_id, _rev, start, size)


class DummyHashIndex(IU_HashIndex):
    def __init__(self, db_path, name, entry_line_format="<32s4sIIcI", *args, **kwargs):
        super(DummyHashIndex, self).__init__(db_path, name,
                                             entry_line_format, *args, **kwargs)
        self.create_key = random_hex_32  # : set the function to create random key when no _id given
        # self.entry_struct=struct.Struct(entry_line_format)

    def update(self, *args, **kwargs):
        return True

    def insert(self, *args, **kwargs):
        return True

    def all(self, *args, **kwargs):
        raise StopIteration

    def get(self, *args, **kwargs):
        raise ElemNotFound

    def get_many(self, *args, **kwargs):
        raise StopIteration

    def delete(self, *args, **kwargs):
        pass

    def make_key_value(self, data):
        return '1', {'_': 1}

    def destroy(self):
        pass

    def _clear_cache(self):
        pass

    def _open_storage(self):
        if not self.storage:
            self.storage = DummyStorage()
        self.storage.open()

    def _create_storage(self):
        if not self.storage:
            self.storage = DummyStorage()
        self.storage.create()


class IU_MultiHashIndex(IU_HashIndex):
    """
    Class that allows to index more than one key per database record.

    It operates very well on GET/INSERT. It's not optimized for
    UPDATE operations (will always readd everything)
    """

    def __init__(self, *args, **kwargs):
        super(IU_MultiHashIndex, self).__init__(*args, **kwargs)

    def insert(self, doc_id, key, start, size, status='o'):
        if isinstance(key, (list, tuple)):
            key = set(key)
        elif not isinstance(key, set):
            key = set([key])
        ins = super(IU_MultiHashIndex, self).insert
        for curr_key in key:
            ins(doc_id, curr_key, start, size, status)
        return True

    def update(self, doc_id, key, u_start, u_size, u_status='o'):
        if isinstance(key, (list, tuple)):
            key = set(key)
        elif not isinstance(key, set):
            key = set([key])
        upd = super(IU_MultiHashIndex, self).update
        for curr_key in key:
            upd(doc_id, curr_key, u_start, u_size, u_status)

    def delete(self, doc_id, key, start=0, size=0):
        if isinstance(key, (list, tuple)):
            key = set(key)
        elif not isinstance(key, set):
            key = set([key])
        delete = super(IU_MultiHashIndex, self).delete
        for curr_key in key:
            delete(doc_id, curr_key, start, size)

    def get(self, key):
        return super(IU_MultiHashIndex, self).get(key)

    def make_key_value(self, data):
        raise NotImplementedError()


# classes for public use, done in this way because of
# generation static files with indexes (_index directory)


class HashIndex(IU_HashIndex):
    """
    That class is designed to be used in custom indexes.
    """
    pass


class UniqueHashIndex(IU_UniqueHashIndex):
    """
    That class is designed to be used in custom indexes. It's designed to be **id** index.
    """
    pass


class MultiHashIndex(IU_MultiHashIndex):
    """
    That class is designed to be used in custom indexes.
    """
