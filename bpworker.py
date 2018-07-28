#!/usr/bin/env python
# bpworker.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (bpworker.py) is part of BitDust Software.
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

from __future__ import absolute_import
if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.path.abspath(os.path.join('.', 'parallelp', 'pp')))
    from parallelp.pp.ppworker import _WorkerProcess
    wp = _WorkerProcess()
    wp.run()
