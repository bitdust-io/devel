#!/usr/bin/env python
# checksum.py
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (checksum.py) is part of BitDust Software.
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
from io import open

sys.path.append(os.path.join('..', '..'))
from lib import misc


def mkinfo(dirpath):
    r = ''
    for root, dirs, files in os.walk(dirpath):
        for fname in files:
            abspath = os.path.abspath(os.path.join(root, fname))
            relpath = os.path.join(root, fname)
            relpath = relpath.split(os.sep, 1)[1]
            txt = misc.file_hash(abspath) + ' ' + relpath + '\n'
            r += txt
    return r


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('checksum.py [source folder path] [output file]')
    else:
        src = mkinfo(sys.argv[1])
        fout = open(sys.argv[2], 'w')
        fout.write(src)
        fout.close()
        sys.stdout.write(misc.get_hash(src))
