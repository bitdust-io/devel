#!/usr/bin/env python
# run.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (run.py) is part of BitDust Software.
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
from twisted.internet import reactor  # @UnresolvedImport

try:
    from bitdust.logs import lg
except:
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))
from bitdust.logs import lg

#------------------------------------------------------------------------------


def run_tests():
    from bitdust.interface import api
    reactor.callLater(15, api.ping, 'http://p2p-id.com/atg314.xml')  # @UndefinedVariable


#------------------------------------------------------------------------------


def main():
    from bitdust.interface import api
    from bitdust.main import bpmain
    from bitdust.system import bpio
    lg.open_log_file('test_api.log')
    lg.set_debug_level(20)
    lg.life_begins()
    lg._NoOutput = True
    bpio.init()
    bpmain.init()
    reactor.callWhenRunning(run_tests)
    reactor.callLater(60, api.stop)
    bpmain.run_twisted_reactor()
    bpmain.shutdown()


if __name__ == '__main__':
    import coverage
    cov = coverage.Coverage()
    cov.start()
    main()
    cov.stop()
    cov.save()
    cov.report()
