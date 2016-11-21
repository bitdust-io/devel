#!/usr/bin/env python
# test.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (test.py) is part of BitDust Software.
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
import os
import sys


try:
    from system import bpio
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    try:
        from system import bpio
    except:
        sys.exit()

from twisted.internet import reactor

import pp

import make

js = pp.Server()
tsks = range(20)
active = []


def _print():
    js.print_stats()


def _func(filename, eccmapname, backupId, blockNumber, targetDir):
    return make.do_in_memory(
        filename,
        eccmapname,
        backupId,
        blockNumber,
        targetDir)


def _cb(result, bnum):
    global active
    print 'cb', result, bnum, active
    active.remove(bnum)
    if len(tsks) == 0 and len(active) == 0:
        _print()
        reactor.stop()
    else:
        _more()


def _more():
    global js
    global tsks
    global active
    while len(tsks) > 0:
        if len(active) >= js.get_ncpus():
            break
        blockNumber = tsks.pop(0)
        active.append(blockNumber)
        l = sys.argv[1:]
        l.insert(-1, str(blockNumber))
        args = tuple(l)
        js.submit(
            _func, args, modules=(
                'make',), callback=lambda result: _cb(
                result, blockNumber), )  # callbackargs=(sys.argv[2],),)
        print 'more', tsks, active
        break
    reactor.callLater(0.01, _more)

_more()
reactor.run()
