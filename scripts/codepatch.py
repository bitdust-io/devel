#!/usr/bin/env python
# codepatch.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (codepatch.py) is part of BitDust Software.
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
import os
import sys

for filename in os.listdir(sys.argv[1]):
    path = os.path.join(sys.argv[1], filename)
    if not filename.endswith('.py'):
        continue
    src = open(path).read()
    newsrc = ''
    lines = src.splitlines()

    for line in lines:
        words = line.split(' ')
        # if line.startswith('from lib import'):
        #     modul = words[3].strip()
        #     line = 'import lib.%s as %s' % (modul, modul)
        # if len(words)==4 and words[0] == 'from' and words[2]=='import':
        #     if words[1] in ['lib', 'userid', 'transport', 'stun', 'dht']:
        #         line = 'import %s.%s as %s' % (words[1], words[3], words[3])
        # line = line.replace('from bitdust.lib import dhnio', 'import lib.dhnio as dhnio')
        if len(words) == 4:
            if words[0] == 'import' and words[2] == 'as':
                pkg, modl = words[1].split('.')
                if modl == words[3]:
                    print(path, line)
                    line = 'from %s import %s' % (pkg, modl)
        newsrc += line + '\n'

#    doclines = False
#    for line in lines:
#        if line.strip() == '"""':
#            if not doclines:
#                doclines = True
#            else:
#                doclines = False
#            newsrc += line+'\n'
#        else:
#            if doclines:
#                newsrc += line.replace('`', '``')+'\n'
#            else:
#                newsrc += line+'\n'
#    newsrc = newsrc.replace('``', '``')

# lines = src.splitlines()
# first_docstring_pos = False
# for line in lines:
#     newsrc += line+'\n'
#     if line.startswith('"""') and first_docstring_pos is False:
#         first_docstring_pos = True
#         newsrc += '.. module:: %s\n\n' % (filename[:-3])
#         continue

    open(path, 'w').write(newsrc)
