#!/usr/bin/env python
# net_misc.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (net_misc.py) is part of BitDust Software.
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
import sys

from twisted.internet import reactor  # @UnresolvedImport

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..', '..')))


def main():

    def _ok(x):
        print('ok', x)
        reactor.stop()  # @UndefinedVariable

    def _fail(x):
        print('fail', x)
        reactor.stop()  # @UndefinedVariable

    from bitdust.lib import net_misc
    from bitdust.main import settings
    settings.init()
    settings.update_proxy_settings()
    url = 'http://localhost:8084'
    r = net_misc.getPageTwisted(url)
    r.addCallback(_ok)
    r.addErrback(_fail)
    reactor.run()  # @UndefinedVariable
    settings.shutdown()


if __name__ == '__main__':
    main()
