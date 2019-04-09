#!/usr/bin/python
# dirsize.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (dirsize.py) is part of BitDust Software.
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
#

"""
.. module:: dirsize.

Here is a tool to calculate the whole folder size. You start a thread
and it will do the job and than remember that size. Now you have a fast
way to get the folder size, you can ask to scan same folder again.
"""

from __future__ import absolute_import
from __future__ import print_function
import os
import sys

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in dirsize.py')

from twisted.internet import threads

from logs import lg

from lib import diskspace

from . import bpio

#------------------------------------------------------------------------------

_Jobs = {}
_Dirs = {}

#------------------------------------------------------------------------------


def ask(dirpath, callback=None, arg=None):
    """
    Start a thread to scan all sub folders and calculate total size of given
    directory.

    :param callback: set a callback function to get the folder size in your code
    :param arg: set some argument to put in the callback, so you can mark that result
    """
    global _Jobs
    global _Dirs
    lg.out(6, 'dirsize.ask %s' % dirpath)
    if dirpath in _Jobs:
        return 'counting size'
    if not os.path.isdir(dirpath):
        _Dirs[dirpath] = 'not exist'
        if callback:
            reactor.callLater(0, callback, 'not exist', arg)  # @UndefinedVariable
        return 'not exist'
    d = threads.deferToThread(bpio.getDirectorySize, dirpath)
    d.addCallback(done, dirpath)
    _Jobs[dirpath] = (d, callback, arg)
    _Dirs[dirpath] = 'counting size'
    return 'counting size'


def done(size, dirpath):
    """
    This is called after you did ``ask`` of dir size.
    """
    global _Dirs
    global _Jobs
    lg.out(6, 'dirsize.done %s %s' % (str(size), dirpath.decode(),))
    _Dirs[dirpath] = str(size)
    try:
        _, cb, arg = _Jobs.pop(dirpath, (None, None, None))
        if cb:
            cb(dirpath, size, arg)
    except:
        lg.exc()


def get(dirpath, default=''):
    """
    Only return directory size stored in memory - after previous calls to ``ask`` procedure.
    """
    global _Dirs
    return _Dirs.get(dirpath, default)


def isjob(dirpath):
    """
    You can check if some work is still in progress to calculate given folder
    size.
    """
    global _Jobs
    return dirpath in _Jobs


def getLabel(dirpath):
    """
    A very smart way to show folder size - can change units, must use ``ask`` first.
    """
    global _Dirs
    s = _Dirs.get(dirpath, '')
    if s not in ['counting size', 'not exist']:
        try:
            return diskspace.MakeStringFromBytes(int(s))
        except:
            return str(s)
    return str(s)


def getInBytes(dirpath, default=-1):
    """
    Return directory size in bytes, must use ``ask`` first.
    """
    return diskspace.GetBytesFromString(get(dirpath), default)

#------------------------------------------------------------------------------


def main():
    """
    Run the test - use command line to pass a location.
    """
    def _done(path, sz, *args, **kwargs):
        print(path, sz)
        reactor.stop()  # @UndefinedVariable
    bpio.init()
    ask(sys.argv[1], _done)
    reactor.run()  # @UndefinedVariable

if __name__ == "__main__":
    main()
