#!/usr/bin/env python
# utime.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (utime.py) is part of BitDust Software.
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
"""
..

module:: utime
"""

from __future__ import absolute_import

#------------------------------------------------------------------------------

import sys
import time
import datetime
import calendar

#------------------------------------------------------------------------------

if sys.version_info < (3, 7):

    def old_fromisoformat(text):
        """ for python versions < 3.7 get datetime from isoformat """
        d, t = text.split('T')
        year, month, day = d.split('-')
        hours, minutes, seconds = t.split(':')
        seconds = float(seconds[0:-1])
        sec = int(seconds)
        microseconds = int((seconds - sec)*1e6)
        return datetime.datetime(int(year), int(month), int(day), int(hours), int(minutes), sec, microseconds)

    _fromisoformat = old_fromisoformat

else:
    _fromisoformat = datetime.datetime.fromisoformat

#------------------------------------------------------------------------------


def utc_timestamp(d):
    timestamp1 = calendar.timegm(d.timetuple())
    return datetime.datetime.utcfromtimestamp(timestamp1)


def local_timestamp(d):
    timestamp2 = time.mktime(d.timetuple())
    return datetime.datetime.fromtimestamp(timestamp2)


def datetime_to_sec1970(dt):
    """
    Converts datetime object to seconds since 1970 year.
    """
    return int(calendar.timegm(dt.timetuple()))


def sec1970_to_datetime_utc(seconds=-1):
    """
    Converts seconds since 1970 year to datetime object in UTC form.
    """
    if seconds is None:
        return None
    if seconds == -1:
        seconds = utcnow_to_sec1970()
    return datetime.datetime.utcfromtimestamp(seconds)


def utcnow_to_sec1970():
    """
    Returns how much seconds passed since 1970 till current moment counting from
    UTC timezone.
    """
    return datetime_to_sec1970(datetime.datetime.utcnow())


def get_sec1970():
    """
    Return how much seconds passed since 1970 using time.time() method, seems
    work in local time.
    TODO: extra methods for time synchronization across the network nodes to be added later
    """
    return int(time.time())


def make_timestamp():
    """
    Returns text string based on current time.
    """
    time_st = time.localtime()
    ampm = time.strftime('%p', time_st)
    if not ampm:
        ampm = 'AM' if time.time() % 86400 < 43200 else 'PM'
    return time.strftime('%Y%m%d%I%M%S', time_st) + ampm


def pack_time(seconds=-1, timespec='seconds'):
    """
    Converts seconds since 1970 year to ISO formatted string.
    """
    if seconds is None:
        return None
    return sec1970_to_datetime_utc(seconds).isoformat(timespec=timespec)


def unpack_time(text):
    """
    Converts ISO formatted string to seconds since 1970 year.
    """
    if text is None:
        return None
    return datetime_to_sec1970(_fromisoformat(text))
