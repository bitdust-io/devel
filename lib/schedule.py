#!/usr/bin/python
# schedule.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (schedule.py) is part of BitDust Software.
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
.. module:: schedule.

The code here is intended to operate with scheduled events. User should
be able to set a schedule to run backups at given moments. At the moment
all this code is disabled.
"""

from __future__ import absolute_import
import os
import sys
import time
import calendar
from six.moves import range

if __name__ == '__main__':
    sys.path.append(os.path.abspath('..'))

from logs import lg

from system import bpio
from lib import misc
from lib import maths

#------------------------------------------------------------------------------

all_types = {
    '0': 'none',
    '1': 'hourly',
    '2': 'daily',
    '3': 'weekly',
    '4': 'monthly',
    '5': 'continuously'}

all_labels = {
    'n': 'none',
    'h': 'hourly',
    'd': 'daily',
    'w': 'weekly',
    'm': 'monthly',
    'c': 'continuously', }


class Schedule:
    """
    
    """
    types = all_types
    labels = all_labels

    def __init__(self,
                 typ=None,
                 daytime=None,
                 interval=None,
                 details=None,
                 lasttime=None,
                 from_tupple=None,
                 from_string=None,
                 from_dict=None,
                 ):
        self.type = str(typ)
        if self.type in ['0', '1', '2', '3', '4', '5']:
            self.type = self.types.get(self.type, 'none')
        self.daytime = str(daytime)
        self.interval = str(interval)
        self.details = str(details)
        self.lasttime = ''
        if from_string is not None:
            self.from_dict(self.correct_dict(self.string_to_dict(from_string)))
        if from_tupple is not None:
            self.from_dict(self.correct_dict(self.tpple_to_dict(from_tupple)))
        if from_dict is not None:
            self.from_dict(self.correct_dict(from_dict))
        if 'None' in [self.daytime, self.interval, self.details]:
            if self.type is None:
                self.from_dict(self.blank_dict('none'))
            else:
                self.from_dict(self.blank_dict(self.type))

    def __repr__(self):
        return 'Schedule(%s, %s, %s, %s, %s)' % (
            self.type, self.daytime, self.interval, self.details, self.lasttime)

    def blank_dict(self, type):
        d = {'type': type}
        if type == 'none':
            d['interval'] = ''
            d['daytime'] = ''
            d['details'] = ''
            d['lasttime'] = ''
        elif type == 'continuously':
            d['interval'] = '600'
            d['daytime'] = ''
            d['details'] = ''
            d['lasttime'] = ''
        elif type == 'hourly':
            d['interval'] = '1'
            d['daytime'] = ''
            d['details'] = ''
            d['lasttime'] = ''
        elif type == 'daily':
            d['interval'] = '1'
            d['daytime'] = '12:00:00'
            d['details'] = ''
            d['lasttime'] = ''
        elif type == 'weekly':
            d['interval'] = '1'
            d['daytime'] = '12:00:00'
            d['details'] = 'Monday Tuesday Wednesday Thursday Friday Saturday Sunday'
            d['lasttime'] = ''
        elif type == 'monthly':
            d['interval'] = '1'
            d['daytime'] = '12:00:00'
            #d['details'] = 'January February March April May June July August September October November December'
            d['details'] = '1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31'
            d['lasttime'] = ''
        return d

    def string_to_dict(self, raw_data):
        l = raw_data.split('\n')
        typ = l[0].strip()
        if typ in ['0', '1', '2', '3', '4', '5']:
            typ = self.types.get(typ, 'none')
        if typ not in list(self.types.values()):
            typ = 'none'
        if len(l) < 3:
            return self.blank_dict(typ)
        return self.tpple_to_dict(l)

    def tpple_to_dict(self, tuppl):
        d = {}
        d['type'] = str(tuppl[0]).strip()
        d['daytime'] = str(tuppl[1] if len(tuppl) > 1 else '12:00:00').strip()
        d['interval'] = str(tuppl[2] if len(tuppl) > 2 else '1').strip()
        d['details'] = str(tuppl[3] if len(tuppl) > 3 else '').strip()
        d['lasttime'] = str(tuppl[4] if len(tuppl) > 4 else '').strip()
        return d

    def from_dict(self, d):
        self.type = d.get('type', 'none')
        self.daytime = d.get('daytime', '12:00:00')
        self.interval = d.get('interval', '1')
        self.details = d.get('details', '')
        self.lasttime = d.get('lasttime', '')

    def to_dict(self):
        d = {}
        d['type'] = self.type
        d['daytime'] = self.daytime
        d['interval'] = self.interval
        d['details'] = self.details
        d['lasttime'] = self.lasttime
        return d

    def to_string(self):
        s = ''
        s += self.type + '\n'
        s += self.daytime + '\n'
        s += self.interval + '\n'
        s += self.details + '\n'
        s += self.lasttime + '\n'
        return s

    def next_time(self):
        lasttime = self.lasttime
        if lasttime == '':
            # let it be one year ago (we can schedule 1 month maximum) and one day
            lasttime = str(time.time() - 366 * 24 * 60 * 60)

        try:
            # turned off - return -1
            if self.type in ['none', 'disabled']:
                return -1

            # every N seconds
            elif self.type == 'continuously':
                return maths.shedule_continuously(lasttime, int(self.interval),)

            # every N hours, exactly when hour begins, minutes and seconds are 0
            elif self.type == 'hourly':
                return maths.shedule_next_hourly(lasttime, int(self.interval),)

            # every N days, at given time
            elif self.type == 'daily':
                return maths.shedule_next_daily(lasttime, self.interval, self.daytime)

            # every N weeks, at given time and selected week days
            elif self.type == 'weekly':
                week_days = self.details.split(' ')
                week_day_numbers = []
                week_day_names = list(calendar.day_name)
                for week_label in week_days:
                    try:
                        i = week_day_names.index(week_label)
                    except:
                        continue
                    week_day_numbers.append(i)
                return maths.shedule_next_weekly(lasttime, self.interval, self.daytime, week_day_numbers)

            # monthly, at given time and day
            elif self.type == 'monthly':
                month_dates = self.details.split(' ')
                return maths.shedule_next_monthly(lasttime, self.interval, self.daytime, month_dates)

            # yearly, at given time and month, day, NOT DONE YET!
            elif self.type == 'yearly':
                months_labels = self.details.split(' ')
                months_numbers = []
                months_names = list(calendar.month_name)
                for month_label in months_labels:
                    try:
                        i = months_names.index(month_label)
                    except:
                        continue
                    months_numbers.append(i)
                return maths.shedule_next_monthly(lasttime, self.interval, self.daytime, months_numbers)

            else:
                lg.out(1, 'schedule.next_time ERROR wrong schedule type: ' + self.type)
                return None
        except:
            lg.exc()
            return None

    def correct_dict(self, d):
        if 'type' not in d:
            d['type'] = 'none'
        if d['type'] in ['0', '1', '2', '3', '4', '5']:
            d['type'] = self.types.get(d['type'], 'none')
        if 'daytime' not in d:
            d['daytime'] = '12:00:00'
        if 'interval' not in d:
            d['interval'] = '1'
        if 'details' not in d:
            d['details'] = ''
        if 'lasttime' not in d:
            d['lasttime'] = ''
        if d['type'] not in list(self.types.values()):
            d['type'] = self.types['0']
        try:
            d['interval'] = str(int(d['interval']))
        except:
            d['interval'] = '1'
        if d['daytime'] == '' or d['daytime'] is None or d['daytime'] == 'None':
            d['daytime'] = time.strftime('%H:%M:%S', time.localtime())
        time_parts = d['daytime'].split(':')
        if len(time_parts) == 1:
            d['daytime'] = misc.DigitsOnly(d['daytime'])
            if int(time_parts[0]) > 24:
                time_parts[0] = '0'
            time_parts.append('00')
        elif len(time_parts) > 1:
            time_parts[0] = misc.DigitsOnly(time_parts[0])
            time_parts[1] = misc.DigitsOnly(time_parts[1])
            if int(time_parts[0]) > 24:
                time_parts[0] = '0'
            if int(time_parts[1]) > 59:
                time_parts[1] = '00'
            if len(time_parts) > 2:
                time_parts[2] = misc.DigitsOnly(time_parts[2])
                if int(time_parts[2]) > 59:
                    time_parts[2] = '00'
        if len(time_parts) < 3:
            time_parts.append('00')
        d['daytime'] = '%02d:%02d:%02d' % (int(time_parts[0]), int(time_parts[1]), int(time_parts[2]))
        if d['type'] == 'weekly' and d['details'].strip() == '':
            d['details'] = 'Monday Tuesday Wednesday Thursday Friday Saturday Sunday'
        if d['type'] == 'monthly' and d['details'].strip() == '':
            d['details'] = 'January February March April May June July August September October November December'
        return d

    def description(self):
        if self.type == 'none':
            return 'not scheduled'
        if self.type == 'hourly':
            if self.interval == '1':
                return 'every hour'
            else:
                return 'every %s hours' % self.interval
        if self.type == 'continuously':
            return 'every %s seconds' % self.interval
        if self.type == 'daily':
            if self.interval == '1':
                return 'every day, at %s' % self.daytime
            else:
                return 'every %s days, at %s' % (self.interval, self.daytime)
        if self.type == 'weekly':
            if self.interval == '1':
                return 'every week, at %s, in %s' % (
                    self.daytime, self.details.strip().replace(' ', ','))
            else:
                return 'every %s weeks, at %s, in %s' % (
                    self.interval, self.daytime, self.details.strip().replace(' ', ', '))
        if self.type == 'monthly':
            return 'in day %s of %s, at %s' % (
                self.interval, self.details.strip().replace(' ', ', '), self.daytime)
        return 'incorrect schedule type'

    def html_description(self):
        if self.type == 'none':
            return 'not scheduled'
        if self.type == 'hourly':
            if self.interval == '1':
                return 'every hour'
            else:
                return 'every <b>%s</b> hours' % self.interval
        if self.type == 'continuously':
            return 'every <b>%s</b> seconds' % self.interval
        if self.type == 'daily':
            if self.interval == '1':
                return 'every day, at <b>%s</b>' % self.daytime
            else:
                return 'every <b>%s</b> days, at <b>%s</b>' % (self.interval, self.daytime)
        if self.type == 'weekly':
            if self.interval == '1':
                return 'every week, at <b>%s</b>, in <b>%s</b>' % (
                    self.daytime, self.details.strip().replace(' ', ','))
            else:
                return 'every <b>%s</b> weeks, at <b>%s</b>, in <b>%s</b>' % (
                    self.interval, self.daytime, self.details.strip().replace(' ', ', '))
        if self.type == 'monthly':
            return 'in <b>%s</b> dates of every <b>%s</b> month, at <b>%s</b>' % (
                self.details.strip().replace(' ', ', '), self.interval, self.daytime)
        return 'incorrect schedule type'

    def html_next_start(self):
        next = self.next_time()
        if next is None:
            return ''
        if next < 0:
            return ''
        try:
            # nextString = time.asctime(time.localtime(next))
            nextString = time.strftime('%A, %d %B %Y %H:%M:%S', time.localtime(next))
        except:
            lg.exc()
            return ''
        return 'next execution expected at <b>%s</b>' % nextString

#------------------------------------------------------------------------------


def format():
    return '''
Schedule compact format:
[mode].[interval].[time].[details]

mode:
  n-none, h-hourly, d-daily, w-weekly, m-monthly, c-continuously

interval:
  just a number - how often to restart the task, default is 1

time:
  [hour]:[minute]

details:
  for weeks: Mon Tue Wed Thu Fri Sat Sun
  for months: Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec

some examples:
  n.1..                   no schedule
  hourly.3                each 3 hours, for example 01:00:00, 04:00:00, 07:00:00, ...
  daily.4.10:15.          every 4th day at 10:15
  w.1.3:00.MonSat         every Monday and Saturday at 3:00 in the night
  weekly.4.18:45.MonTueWedThuFriSatSun
                          every day in each 4th week in 18:45
  m.5.12:34.JanJul        5th Jan and 5th July at 12:34
  c.300                   every 300 seconds (10 minutes)
'''


def default_dict():
    return {'type': 'daily',
            'daytime': '12:00:00',
            'interval': '1',
            'details': '',
            'lasttime': ''}


def default():
    return Schedule(from_dict=default_dict())


def empty():
    return Schedule('none', '', '', '')

#------------------------------------------------------------------------------


def from_compact_string(s):
    try:
        parts = s.split('.')
        parts += [''] * (4 - len(parts))
        (sh_type, sh_interval, sh_time, sh_details) = parts[0:4]
        sh_type = sh_type.lower()
        try:
            sh_interval = int(sh_interval)
        except:
            sh_interval = 1
        if sh_type not in ['n', 'none', 'h', 'hourly', 'c', 'continuously']:
            try:
                time.strptime(sh_time, '%H:%M')
            except:
                try:
                    time.strptime(sh_time, '%H:%M:%S')
                except:
                    lg.warn('incorrect schedule time: ' + s)
                    lg.exc()
                    return None
    except:
        lg.warn('incorrect schedule string: ' + s)
        lg.exc()
        return None
    if sh_type in list(all_labels.keys()):
        sh_type = all_labels[sh_type]
    if sh_type not in list(all_labels.values()):
        lg.warn('incorrect schedule type: ' + s)
        return None
    sh_details_new = ''
    for i in range(len(sh_details) / 3):
        label = sh_details[i * 3:i * 3 + 3]
        if sh_type == 'weekly' and not label in calendar.day_abbr:
            lg.warn('incorrect schedule details: ' + s)
            return None
        if sh_type == 'monthly' and not label in calendar.month_abbr:
            lg.warn('incorrect schedule details: ' + s)
            return None
        sh_details_new += label + ' '
    return Schedule(sh_type, str(sh_time), str(sh_interval), sh_details_new.strip())
