#!/usr/bin/env python
# mergecommits.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (mergecommits.py) is part of BitDust Software.
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
import sys
import os
import re
import time
import pprint

h1 = open(sys.argv[1]).read().splitlines()
h2 = open(sys.argv[2]).read().splitlines()
h1times = {}
h2times = {}

for commit1 in h1:
    dt1 = re.search('\[(.+?)\]', commit1)
    if dt1:
        dt1 = time.mktime(time.strptime(dt1.group(1)[:-6]))
        h1times[dt1] = commit1

for commit2 in h2:
    dt2 = re.search('\[(.+?)\]', commit2)
    if dt2:
        dt2 = time.mktime(time.strptime(dt2.group(1)[:-6]))
        h2times[dt2] = commit2

h1sorted = sorted(h1times.keys(), reverse=True)
h2sorted = sorted(h2times.keys(), reverse=True)

tcurr = time.time()

parts = {}
parts[-1] = []
parts[-1].append((tcurr, '123456 [date] !!! NOT PUBLISHED YET !!!'))

for i in xrange(len(h2sorted)):
    dt2 = h2sorted[i]
    commit2 = h2times[dt2]
    parts[i] = []
    parts[i].append((dt2, commit2))
    for dt1 in h1sorted:
        commit1 = h1times[dt1]
        if dt1 < tcurr and dt1 > dt2:
            parts[i - 1].append((dt1, commit1))
    tcurr = dt2

for i in sorted(parts.keys(), reverse=False):
    commits = parts[i]
    headcommit = commits.pop(0)
    print '[%s]' % time.asctime(time.localtime(headcommit[0]))
    print re.match('\w+? \[.+?\] (.+?)$', headcommit[1]).group(1)
    for dt, commit in commits:
        print '    [%s] %s' % (time.strftime('%c', time.localtime(dt)),
                               re.match('\w+? \[.+?\] (.+?)$', commit).group(1))
    print
