#!/usr/bin/python
#local_fs.py
#
# <<<COPYRIGHT>>>
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

try:
    import lib.bpio as bpio
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))
    try:
        import lib.bpio as bpio
    except:
        sys.exit()

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






