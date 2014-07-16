#!/usr/bin/python
#dirsize.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: dirsize

Here is a tool to calculate the whole folder size.
You start a thread and it will do the job and than remember that size.
Now you have a fast way to get the folder size, you can ask to scan same folder again.
"""

import os
import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in dirsize.py')

from twisted.internet import threads

import bpio
import diskspace

#------------------------------------------------------------------------------ 

_Jobs = {}
_Dirs = {}

#------------------------------------------------------------------------------ 

def ask(dirpath, callback=None, arg=None):
    """
    Start a thread to scan all sub folders and calculate total size of given directory.
        
        :param callback: set a callback function to get the folder size in your code
        :param arg: set some argument to put in the callback, so you can mark that result 
    """
    global _Jobs
    global _Dirs
    bpio.log(6, 'dirsize.ask %s' % dirpath)
    if _Jobs.has_key(dirpath):
        return 'counting size'
    if not os.path.isdir(dirpath):
        _Dirs[dirpath] = 'not exist'
        if callback:
            reactor.callLater(0, callback, 'not exist', arg)
        return 'not exist'
    d = threads.deferToThread(bpio.getDirectorySize, dirpath)
    d.addCallback(done, dirpath)
    _Jobs[dirpath] = (d, callback, arg)
    _Dirs[dirpath] = 'counting size'
    return 'counting size'
    
def done(size, dirpath):
    """
    This is called after you did ``ask`` of dir size.
    """
    global _Dirs
    global _Jobs
    bpio.log(6, 'dirsize.done %s %s' % (str(size), dirpath.decode(),))
    _Dirs[dirpath] = str(size)
    try:
        (d, cb, arg) = _Jobs.pop(dirpath, (None, None, None))
        if cb:
            cb(dirpath, size, arg)
    except:
        bpio.exception()
    
def get(dirpath, default=''):
    """
    Only return directory size stored in memory - after previous calls to ``ask`` procedure.
    """
    global _Dirs
    return _Dirs.get(dirpath, default)
    
def isjob(dirpath):
    """
    You can check if some work is still in progress to calculate given folder size.
    """
    global _Jobs
    return _Jobs.has_key(dirpath)

def getLabel(dirpath):
    """
    A very smart way to show folder size - can change units, must use ``ask`` first.
    """
    global _Dirs
    s = _Dirs.get(dirpath, '')
    if s not in ['counting size', 'not exist']:
        try:
            return diskspace.MakeStringFromBytes(int(s))
        except:
            return str(s)
    return str(s)
    
def getInBytes(dirpath, default=-1):
    """
    Return directory size in bytes, must use ``ask`` first.
    """
    return diskspace.GetBytesFromString(get(dirpath), default)     
        
#------------------------------------------------------------------------------ 

def main():
    """
    Run the test - use command line to pass a location.
    """
    def _done(path, sz, arg):
        print path, sz
        reactor.stop()
    bpio.init()
    ask(sys.argv[1], _done)
    reactor.run()

if __name__ == "__main__":
    main()
    
    
