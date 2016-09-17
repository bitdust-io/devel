#!/usr/bin/python
#local_fs.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (local_fs.py) is part of BitDust Software.
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
.. module:: local_fs

This module should be able to provide access to local file system.
The GUI needs to show all existing local files, just like in Explorer.
"""

import os
import sys
import stat

from logs import lg
        
from system import bpio

#------------------------------------------------------------------------------ 

_FileSystemIndexByName = {}

def fs():
    global _FileSystemIndexByName
    return _FileSystemIndexByName

#------------------------------------------------------------------------------ 

def TraverseLocalFileSystem(basedir, expanded_dirs, callback):
    def cb(realpath, subpath, name):
        if not os.access(realpath, os.R_OK):
            return False
        if os.path.isfile(realpath):
            callback(realpath, subpath, name)
            return False
        if subpath not in expanded_dirs:
            callback(realpath, subpath, name)
            return False
    bpio.traverse_dir_recursive(cb, basedir)






