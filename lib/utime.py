#!/usr/bin/env python
# utime.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
import time
import datetime
import calendar


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
    return int(time.mktime(dt.timetuple()))


def sec1970_to_datetime_utc(seconds=-1):
    """
    Converts seconds since 1970 year to datetime object in UTC form.
    """
    if seconds == -1:
        seconds = utcnow_to_sec1970()
    return datetime.datetime.utcfromtimestamp(seconds)


def utcnow_to_sec1970():
    """
    Returns how much seconds passed since 1970 till current moment depend on
    UTC timezone.
    """
    return datetime_to_sec1970(datetime.datetime.utcnow())


def get_sec1970():
    """
    Return how much seconds passed since 1970 using time.time() method, seems
    work in local time.
    TODO: extra methods for time synchronization accross the nodes to be added here
    """
    return int(time.time())
