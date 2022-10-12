#!/usr/bin/env python
# timeprecision.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (timeprecision.py) is part of BitDust Software.
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
import time
from six.moves import range
# import timeit
# import platform


def _qpc():
    from ctypes import byref, c_int64, windll
    val = c_int64()
    windll.Kernel32.QueryPerformanceCounter(byref(val))
    return val.value


_InitTime = None
_TimeStart = None
_Frequency = None


def init():
    global _InitTime
    global _TimeStart
    global _Frequency
    _InitTime = time.time()
    # time.clock()
    from ctypes import byref, c_int64, windll
    time_start = c_int64()
    freq = c_int64()
    windll.Kernel32.QueryPerformanceCounter(byref(time_start))
    windll.Kernel32.QueryPerformanceFrequency(byref(freq))
    _TimeStart = float(time_start.value)
    _Frequency = float(freq.value)


def _time_windows():
    global _InitTime
    global _TimeStart
    global _Frequency
    from ctypes import byref, c_int64, windll
    time_now = c_int64()
    windll.Kernel32.QueryPerformanceCounter(byref(time_now))
    return _InitTime + ((_TimeStart - time_now.value) / _Frequency)


if sys.platform == 'win32':
    # On Windows, the best timer is time.clock()
    _time = _time_windows
    init()
else:
    # On most other platforms the best timer is time.time()
    _time = time.time

print('%f' % (time.time() - _time()))

for j in range(10):
    c = 0
    for i in range(9999999):
        c = i / float(i + 1)
        if str(i).count('0') == 6 and int(str(i)[0]) % 5:
            print('%f' % (time.time() - _time()))
