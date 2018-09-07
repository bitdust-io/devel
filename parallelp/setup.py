#!/usr/bin/env python
# setup.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (setup.py) is part of BitDust Software.
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
from distutils.core import setup
import py2exe
import sys
import os

sys.argv.append('py2exe')

setup(
    options={'py2exe': {'includes': ["pp.ppworker"]}},
    console=["sum_primes.py"],
    data_files=[('', [r'C:\Python25\python.exe'])],
)

# We need to add the source code of the function into the library.zip modules
from zipfile import ZipFile
zip = ZipFile('dist/library.zip', 'a')
zip.write("primes.py")
