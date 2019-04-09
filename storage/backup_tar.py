#!/usr/bin/python
# backup_tar.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

We want a pipe output or input so we don't need to store intermediate data.
Our backup code only takes data from this pipe when it is ready and form blocks one by one.

The class ``lib.nonblocking.Popen`` starts another process - that process can block but we don't.

We call that "tar" because standard TAR utility is used
to read data from files and folders and create a single data stream.
This data stream is passed via ``Pipe`` to the main process.

This module execute a sub process "bppipe" - pretty simple TAR compressor,
see ``p2p.bppipe`` module.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

import os
import sys
from io import open

#------------------------------------------------------------------------------

if __name__ == "__main__":
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

#------------------------------------------------------------------------------

from lib import strng

from logs import lg

from system import bpio
from system import child_process

#------------------------------------------------------------------------------


def backuptardir(directorypath, arcname=None, recursive_subfolders=True, compress=None):
    """
    Returns file descriptor for process that makes tar archive.

    In other words executes a child process and create a Pipe to
    communicate with it.
    """
    if not bpio.pathIsDir(directorypath):
        lg.out(1, 'backup_tar.backuptar ERROR %s not found' % directorypath)
        return None
    subdirs = 'subdirs'
    if not recursive_subfolders:
        subdirs = 'nosubdirs'
    if compress is None:
        compress = 'none'
    if arcname is None:
        arcname = os.path.basename(directorypath)
    # lg.out(14, "backup_tar.backuptar %s %s compress=%s" % (directorypath, subdirs, compress))
    if bpio.Windows():
        if bpio.isFrozen():
            commandpath = "bppipe.exe"
            cmdargs = [commandpath, subdirs, compress, directorypath, arcname]
        else:
            commandpath = "bppipe.py"
            cmdargs = [sys.executable, commandpath, subdirs, compress, directorypath, arcname]
    else:
        commandpath = "bppipe.py"
        cmdargs = [sys.executable, commandpath, subdirs, compress, directorypath, arcname]
    if not os.path.isfile(commandpath):
        lg.out(1, 'backup_tar.backuptar ERROR %s not found' % commandpath)
        return None
    cmdargs = [strng.to_text(a) for a in cmdargs]
    p = child_process.pipe(cmdargs)
    return p


def backuptarfile(filepath, arcname=None, compress=None):
    """
    Almost same - returns file descriptor for process that makes tar archive.
    But tar archive is created from single file, not folder.
    """
    if not os.path.isfile(filepath):
        lg.out(1, 'backup_tar.backuptarfile ERROR %s not found' % filepath)
        return None
    if compress is None:
        compress = 'none'
    if arcname is None:
        arcname = os.path.basename(filepath)
    # lg.out(14, "backup_tar.backuptarfile %s compress=%s" % (filepath, compress))
    if bpio.Windows():
        if bpio.isFrozen():
            commandpath = "bppipe.exe"
            cmdargs = [commandpath, 'nosubdirs', compress, filepath, arcname]
        else:
            commandpath = "bppipe.py"
            cmdargs = [sys.executable, commandpath, 'nosubdirs', compress, filepath, arcname]
    else:
        commandpath = "bppipe.py"
        cmdargs = [sys.executable, commandpath, 'nosubdirs', compress, filepath, arcname]
    if not os.path.isfile(commandpath):
        lg.out(1, 'backup_tar.backuptarfile ERROR %s not found' % commandpath)
        return None
    # lg.out(12, "backup_tar.backuptarfile going to execute %s" % str(cmdargs))
    # p = run(cmdargs)
    cmdargs = [strng.to_text(a) for a in cmdargs]
    p = child_process.pipe(cmdargs)
    return p


def extracttar(tarfile, outdir):
    """
    Opposite method, run bppipe to extract files and folders from ".tar" file.
    """
    if not os.path.isfile(tarfile):
        lg.out(1, 'backup_tar.extracttar ERROR %s not found' % tarfile)
        return None
    lg.out(6, "backup_tar.extracttar %s %s" % (tarfile, outdir))
    if bpio.Windows():
        if bpio.isFrozen():
            commandpath = 'bppipe.exe'
            cmdargs = [commandpath, 'extract', tarfile, outdir]
        else:
            commandpath = "bppipe.py"
            cmdargs = [sys.executable, commandpath, 'extract', tarfile, outdir]
    else:
        commandpath = "bppipe.py"
        cmdargs = [sys.executable, commandpath, 'extract', tarfile, outdir]
    if not os.path.isfile(commandpath):
        lg.out(1, 'backup_tar.extracttar ERROR %s is not found' % commandpath)
        return None
    # p = run(cmdargs)
    cmdargs = [strng.to_text(a) for a in cmdargs]
    p = child_process.pipe(cmdargs)
    return p


#------------------------------------------------------------------------------

def main():
    lg.set_debug_level(20)
    fout = open('out.tar', 'wb')

    def _read(p):
        from system import nonblocking
        # print 'read', p.state()
        if p.state() == nonblocking.PIPE_CLOSED:
            print('closed')
            fout.close()
            reactor.stop()
            return
        if p.state() == nonblocking.PIPE_READY2READ:
            v = p.recv(100)
            fout.write(v)
            if v == '':
                print('eof')
                fout.close()
                reactor.stop()
                return
        reactor.callLater(0, _read, p)

    def _go():
        p = backuptardir(sys.argv[1], arcname='asd')
        p.make_nonblocking()
        _read(p)

    from twisted.internet import reactor  # @UnresolvedImport
    reactor.callLater(0, _go)  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable


if __name__ == "__main__":
    main()
