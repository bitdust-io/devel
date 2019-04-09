#!/usr/bin/python
# control.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (control.py) is part of BitDust Software.
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
..

module:: control
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 14

#------------------------------------------------------------------------------

import six
import os
import sys
import time
import pprint
import random
import webbrowser

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred  # @UnresolvedImport
from twisted.web import wsgi  # @UnresolvedImport
from twisted.web import server  # @UnresolvedImport
from twisted.web import resource  # @UnresolvedImport
from twisted.web import static  # @UnresolvedImport
from twisted.python import threadpool  # @UnresolvedImport

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(
        0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

#------------------------------------------------------------------------------

_UpdateFlag = None
_UpdateItems = {}

#------------------------------------------------------------------------------

def init():
    if _Debug:
        lg.out(_DebugLevel, 'control.init')
    request_update()
    if _Debug:
        lg.out(_DebugLevel + 6, '    \n' + pprint.pformat(sys.path))


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'control.shutdown')

#------------------------------------------------------------------------------


def on_suppliers_changed(current_suppliers):
    request_update()


def on_backup_stats(backupID):
    request_update([('backupID', backupID), ])


def on_read_local_files():
    request_update()


def stop_updating():
    global _UpdateFlag
    global _UpdateItems
    if _Debug:
        lg.out(_DebugLevel, 'control.stop_updating  _UpdateFlag=None, current items: %s' % str(_UpdateItems))
    _UpdateFlag = None
    _UpdateItems.clear()
    _UpdateItems['stop'] = int(time.time())


def set_updated():
    global _UpdateFlag
    global _UpdateItems
    if _Debug:
        lg.out(_DebugLevel, 'control.set_updated  _UpdateFlag=False, current items: %s' % str(_UpdateItems))
    _UpdateFlag = False
    _UpdateItems.clear()


def get_update_flag():
    global _UpdateFlag
    return _UpdateFlag


def get_update_items():
    global _UpdateItems
    return _UpdateItems


def request_update(items=None):
    global _UpdateFlag
    global _UpdateItems
    if _Debug:
        lg.out(_DebugLevel, 'control.request_update  _UpdateFlag=True, new items=%s' % str(items))
    _UpdateFlag = True
    _UpdateItems['refresh'] = int(time.time())
    if items is not None:
        for item in items:
            if isinstance(item, six.string_types):
                _UpdateItems[item] = int(time.time())
            elif isinstance(item, tuple) and len(item) == 2:
                key, value = item
                if key not in _UpdateItems:
                    _UpdateItems[key] = []
                _UpdateItems[key].append(value)
            else:
                for item in items:
                    _UpdateItems.update(item)

#------------------------------------------------------------------------------

if __name__ == "__main__":
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
