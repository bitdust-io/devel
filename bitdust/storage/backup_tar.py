#!/usr/bin/python
# backup_tar.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (backup_tar.py) is part of BitDust Software.
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
#
#
#
"""
.. module:: backup_tar.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import sys
from io import open

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet import threads
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.system import bpio

#------------------------------------------------------------------------------

# Bytes Loop States:
BYTES_LOOP_EMPTY = 0
BYTES_LOOP_READY2READ = 1
BYTES_LOOP_CLOSED = 2

#------------------------------------------------------------------------------


class BytesLoop:

    def __init__(self, s=b''):
        self._buffer = s
        self._reader = None
        self._last_read = -1
        self._finished = False
        self._closed = False

    def read_defer(self, n=-1):
        if self._reader:
            raise Exception('already reading')
        self._reader = (
            Deferred(),
            n,
        )
        if len(self._buffer) > 0:
            chunk = self.read(n=n)
            d = self._reader[0]
            self._reader = None
            d.callback(chunk)
            return d
        if self._finished:
            chunk = b''
            d = self._reader[0]
            self._reader = None
            d.callback(chunk)
            return d
        return self._reader[0]

    def read(self, n=-1):
        before_bytes = len(self._buffer)
        chunk = self._buffer[:n]
        self._buffer = self._buffer[n:]
        after_bytes = len(self._buffer)
        self._last_read = len(chunk)
        if _Debug:
            lg.args(_DebugLevel, before_bytes=before_bytes, after_bytes=after_bytes, chunk_bytes=len(chunk))
        return chunk

    def write(self, chunk):
        reactor.callFromThread(self._write, chunk)  # @UndefinedVariable

    def _write(self, chunk):
        self._buffer += chunk
        if _Debug:
            lg.args(_DebugLevel, buffer_bytes=len(self._buffer), chunk_bytes=len(chunk))
        if len(self._buffer) > 0:
            if self._reader:
                chunk = self.read(n=self._reader[1])
                d = self._reader[0]
                self._reader = None
                d.callback(chunk)

    def close(self):
        if self._reader:
            d = self._reader[0]
            self._reader = None
            d.callback(b'')
        self._closed = True
        self._buffer = b''

    def kill(self):
        self.close()

    def mark_finished(self):
        self._finished = True

    def state(self):
        if self._closed:
            return BYTES_LOOP_CLOSED
        if len(self._buffer) > 0:
            if self._reader:
                return BYTES_LOOP_EMPTY
            return BYTES_LOOP_READY2READ
        if self._last_read > 0:
            return BYTES_LOOP_READY2READ
        if self._finished:
            return BYTES_LOOP_EMPTY
        if not self._reader:
            return BYTES_LOOP_READY2READ
        return BYTES_LOOP_EMPTY


#------------------------------------------------------------------------------


def backuptarfile_thread(filepath, arcname=None, compress=None):
    """
    Makes tar archive of a folder inside a thread.
    Returns `BytesLoop` object instance which can be used to read produced data in parallel.
    """
    if not os.path.isfile(filepath):
        lg.err('file %s not found' % filepath)
        return None
    if arcname is None:
        arcname = os.path.basename(filepath)
    p = BytesLoop()

    def _run():
        from bitdust.storage import tar_file
        ret = tar_file.writetar(
            sourcepath=filepath,
            arcname=arcname,
            subdirs=False,
            compression=compress or 'none',
            encoding='utf-8',
            fileobj=p,
        )
        p.mark_finished()
        if _Debug:
            lg.out(_DebugLevel, 'backup_tar.backuptarfile_thread writetar() finished')
        return ret

    reactor.callInThread(_run)  # @UndefinedVariable
    return p


def backuptardir_thread(directorypath, arcname=None, recursive_subfolders=True, compress='bz2'):
    """
    Makes tar archive of a single file inside a thread.
    Returns `BytesLoop` object instance which can be used to read produced data in parallel.
    """
    if not bpio.pathIsDir(directorypath):
        lg.err('folder %s not found' % directorypath)
        return None
    if arcname is None:
        arcname = os.path.basename(directorypath)
    p = BytesLoop()

    def _run():
        from bitdust.storage import tar_file
        ret = tar_file.writetar(
            sourcepath=directorypath,
            arcname=arcname,
            subdirs=recursive_subfolders,
            compression=compress or 'none',
            encoding='utf-8',
            fileobj=p,
        )
        p.mark_finished()
        if _Debug:
            lg.out(_DebugLevel, 'backup_tar.backuptardir_thread writetar() finished')
        return ret

    reactor.callInThread(_run)  # @UndefinedVariable
    return p


def extracttar_thread(tarfile, outdir, mode='r:bz2'):
    """
    Opposite method, extract files and folders from ".tar" file inside a thread.
    """
    if not os.path.isfile(tarfile):
        lg.err('path %s not found' % tarfile)
        return None
    if _Debug:
        lg.out(_DebugLevel, 'backup_tar.extracttar_thread tarfile=%s' % tarfile)

    def _run():
        if _Debug:
            lg.out(_DebugLevel, 'backup_tar.extracttar_thread._run outdir=%s' % outdir)
        from bitdust.storage import tar_file
        ret = tar_file.readtar(
            archivepath=tarfile,
            outputdir=outdir,
            encoding='utf-8',
            mode=mode,
        )
        return ret

    return threads.deferToThread(_run)  # @UndefinedVariable


#------------------------------------------------------------------------------


def test_in_thread():
    fout = open('out.tar', 'wb')

    def _read(p):
        if p.state() == BYTES_LOOP_CLOSED:
            print('closed')
            fout.close()
            reactor.stop()  # @UndefinedVariable
            return
        if p.state() == BYTES_LOOP_EMPTY:
            print('empty')
            reactor.callLater(0, _read, p)  # @UndefinedVariable
            return
        chunk = p.read()
        fout.write(chunk)
        print(len(chunk))
        if not chunk:
            print('empty chunk')
            fout.close()
            reactor.stop()  # @UndefinedVariable
            return
        reactor.callLater(0, _read, p)  # @UndefinedVariable

    def _go():
        p = backuptarfile_thread(sys.argv[1], arcname='asd')
        _read(p)

    reactor.callLater(0, _go)  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable


if __name__ == '__main__':
    test_in_thread()
