#!/usr/bin/env python
# raidworker.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (raidworker.py) is part of BitDust Software.
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

from __future__ import absolute_import
from __future__ import print_function
import os
import sys

from twisted.internet import reactor  # @UnresolvedImport

sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath('..'))

from bitdust.logs import lg


def main():
    lg.set_debug_level(24)

    # TEST
    # call with parameters like that:
    # python raidworker.py ./somefile ecc/7x7 myID_ABC 1234 ./somefolder/
    tasks = {}

    def _cb(cmd, taskdata, result):
        print('DONE!', cmd, taskdata, result)
        tasks.pop(taskdata[3])
        if len(tasks) == 0:
            reactor.stop()
        else:
            print(len(tasks), 'more')

    def _add(blocknum):
        tasks[blocknum] = (sys.argv[1], sys.argv[2], sys.argv[3], blocknum, sys.argv[5])
        raid_worker.A('new-task', ('make', (sys.argv[1], sys.argv[2], sys.argv[3], blocknum, sys.argv[5]), _cb))

    from bitdust.system import bpio
    bpio.init()
    lg.set_debug_level(20)
    from bitdust.raid import raid_worker
    reactor.callWhenRunning(raid_worker.A, 'init')
    start_block_num = int(sys.argv[4])
    reactor.callLater(0.01, _add, start_block_num)
    reactor.callLater(0.02, _add, start_block_num + 1)
    reactor.callLater(0.03, _add, start_block_num + 2)
    reactor.callLater(0.04, _add, start_block_num + 3)
    reactor.callLater(0.05, _add, start_block_num + 4)
    reactor.run()


if __name__ == '__main__':
    main()
