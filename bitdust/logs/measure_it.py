#!/usr/bin/python
# measure_it.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (measure_it.py) is part of BitDust Software.
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

module:: measure_it
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

from six.moves import range

import time

#------------------------------------------------------------------------------

_CallsIndex = {}

#------------------------------------------------------------------------------


def init():
    pass


def shutdown():
    global _CallsIndex
    _CallsIndex.clear()


def make_fqn(callabl, *args, **kwargs):
    fqn = ''
    nm = callabl.__class__.__name__
    if nm == 'function' or nm == 'instancemethod':
        fqn = '{}.{}'.format(callabl.__module__, callabl.__name__)
    elif nm == 'LoopingCall':
        fqn = '{}.{}'.format(callabl.f.__module__, callabl.f.__name__)
    elif nm == 'method':
        fqn = '{}.{}'.format(callabl.__func__.__module__, callabl.__func__.__name__)
    else:
        raise Exception('unexpected callable type: %r' % callabl)
    if fqn == 'transport.gateway._call':
        fqn += '.' + args[0]
    elif fqn == 'automats.automat.timerEvent':
        fqn += '.' + callabl.a[0]
    elif fqn == 'automats.automat.event':
        fqn += '.' + args[0]
    elif fqn == 'automats.automat.automat':
        fqn += '.' + args[0]
    return fqn


def top_calls(top_size=5):
    global _CallsIndex
    keys = list(_CallsIndex.keys())
    keys.sort(key=lambda cb: -_CallsIndex[cb][1])
    s = '    cumulative time:\n'
    for i in range(0, min(top_size, len(_CallsIndex))):
        cb = keys[i]
        s += '        %f sec. with %d calls : %s\n' % (_CallsIndex[cb][1], _CallsIndex[cb][0], cb)
    keys.sort(key=lambda cb: -_CallsIndex[cb][0])
    s += '    number of calls:\n'
    for i in range(0, min(top_size, len(_CallsIndex))):
        cb = keys[i]
        s += '        %f sec. with %d calls : %s\n' % (_CallsIndex[cb][1], _CallsIndex[cb][0], cb)
    return s


def run(callabl, *args, **kwargs):
    global _CallsIndex
    fqn = make_fqn(callabl, *args, **kwargs)
    tm = float(time.time())
    try:
        result = callabl(*args, **kwargs)
    except Exception as e:
        result = e
    exec_time = float(time.time()) - tm
    if fqn not in _CallsIndex:
        _CallsIndex[fqn] = [0, 0.0]
    _CallsIndex[fqn][0] += 1
    _CallsIndex[fqn][1] += exec_time
    return result, exec_time
