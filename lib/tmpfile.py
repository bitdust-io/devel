#!/usr/bin/python
#tmpfile.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: tmpfile

Keep track of temporary files created in the program.
The temp folder is placed in the BitPie.NET data directory. 
All files are divided into several sub folders.
"""

import os
import tempfile
import time


from twisted.internet import reactor, task


import io


_TempDirPath = None
_FilesDict = {}
_CollectorTask = None
_SubDirs = {

    'outbox':   60*60*1,
    # hold onto outbox files 1 hour
    # so we can handle resends if contact is off-line

    'tcp-in':   60*10,
    # 10 minutes for incoming tcp files
    
    'dhtudp-in': 60*10,
    
    'propagate': 60*10,
    # propagate happens often enough,
    # 10 minutes should be enough

    'backup':   60*10,
    # 10 minutes for backup files
    
    'restore':  60*10,
    # 10 minutes for restoring files

    'raid':   60*10,
    # 10 minutes for backup files
    
    'idsrv':  60, 
    # 1 minute for incoming xml identity files

    'other':    0,
    # other files. do not know when to remove
    # they can be even in another location
    # use register(name, filename)

    }



#------------------------------------------------------------------------------


def init(temp_dir_path=''):
    """
    Must be called before all other things here.
        - check existence and access mode of temp folder
        - creates a needed sub folders  
        - call ``startup_clean()``
        - starts collector task to call method ``collect()`` every 5 minutes
    """
    io.log(4, 'tmpfile.init')
    global _TempDirPath
    global _SubDirs
    global _FilesDict
    global _CollectorTask

    if _TempDirPath is None:
        if temp_dir_path != '':
            _TempDirPath = temp_dir_path
        else:
            os_temp_dir = tempfile.gettempdir()
            temp_dir = os.path.join(os_temp_dir, 'bitpie')

            if not os.path.exists(temp_dir):
                try:
                    os.mkdir(temp_dir)
                except:
                    io.log(2, 'tmpfile.init ERROR can not create ' + temp_dir)
                    io.exception()
                    temp_dir = os_temp_dir

            if not os.access(temp_dir, os.W_OK):
                io.log(2, 'tmpfile.init ERROR no write permissions to ' + temp_dir)
                temp_dir = os_temp_dir

            _TempDirPath = temp_dir
        io.log(6, 'tmpfile.init  _TempDirPath=' + _TempDirPath)

    for name in _SubDirs.keys():
        if not os.path.exists(subdir(name)):
            try:
                os.makedirs(subdir(name))
            except:
                io.log(2, 'tmpfile.init ERROR can not create ' + subdir(name))
                io.exception()

    for name in _SubDirs.keys():
        if not _FilesDict.has_key(name):
            _FilesDict[name] = {}

    startup_clean()

    if _CollectorTask is None:
        _CollectorTask = task.LoopingCall(collect)
        _CollectorTask.start(60*5)


def shutdown():
    """
    Do not need to remove any files here, just stop the collector task.
    """
    io.log(4, 'tmpfile.shutdown')
    global _CollectorTask
    if _CollectorTask is not None:
        _CollectorTask.stop()
        del _CollectorTask
        _CollectorTask = None


def subdir(name):
    """
    Return a path to given sub folder. 
    """
    global _TempDirPath
    if _TempDirPath is None:
        init()
    return os.path.join(_TempDirPath, name)


def register(filepath):
    """
    You can create a temp file in another place and call this method to be able to hadle this file later.
    """
    global _FilesDict
    subdir, filename = os.path.split(filepath)
    name = os.path.basename(subdir)
    if name not in _FilesDict.keys():
        name = 'other'
    _FilesDict[name][filepath] = time.time()


def make(name, extension='', prefix=''):
    """
    Make a new file under sub folder ``name`` and return a tuple of it's file descriptor and path.
    Remember you need to close the file descriptor by your self.
    The ``tmpfile`` module will remove it later - do not worry. This is a job for our collector.
    """
    global _TempDirPath
    global _FilesDict
    if _TempDirPath is None:
        init()
    if name not in _FilesDict.keys():
        name = 'other'
    try:
        fd, filename = tempfile.mkstemp(extension, prefix, subdir(name))
        _FilesDict[name][filename] = time.time()
    except:
        io.log(1, 'tmpfile.make ERROR creating file in sub folder ' + name)
        io.exception()
        return None, ''
    io.log(18, 'tmpfile.make ' + filename)
    return fd, filename


def erase(name, filename, why='no reason'):
    """
    However you can remove not needed file immediately, this is a good way also.
    But outside of this module you better use method ``throw_out``.
    """
    global _FilesDict
    if name in _FilesDict.keys():
        try:
            _FilesDict[name].pop(filename, '')
        except:
            io.log(4, 'tmpfile.erase WARNING we do not know about file %s in sub folder %s' %(filename, name))
    else:
        io.log(4, 'tmpfile.erase WARNING we do not know sub folder ' + name)

    if not os.path.exists(filename):
        io.log(6, 'tmpfile.erase WARNING %s not exist' % filename)
        return

    if not os.access(filename, os.W_OK):
        io.log(4, 'tmpfile.erase WARNING %s no write permissions' % filename)
        return

    try:
        os.remove(filename)
        # io.log(24, 'tmpfile.erase [%s] : "%s"' % (filename, why))
    except:
        io.log(2, 'tmpfile.erase ERROR can not remove [%s], we tried because %s' % (filename, why))
        #io.exception()


def throw_out(filepath, why='dont know'):
    """
    A more smart way to remove not needed temporary file, accept a full ``filepath``.
    """
    global _FilesDict
    global _SubDirs
    subdir, filename = os.path.split(filepath)
    name = os.path.basename(subdir)
    erase(name, filepath, why)


def collect():
    """
    Removes old temporary files.
    """
    # io.log(10, 'tmpfile.collect')
    global _FilesDict
    global _SubDirs
    erase_list = []
    for name in _FilesDict.keys():
        # for data and parity files we have special rules
        # we do not want to remove Data or Parity here.
        # backup_monitor should take care of this.
        if name == 'data-par':
            continue

        else:
            # how long we want to keep the file?
            lifetime = _SubDirs.get(name, 0)
            # if this is not set - keep forever
            if lifetime == 0:
                continue
            for filename, filetime in _FilesDict[name].items():
                # if file is too old - remove it
                if time.time() - filetime > lifetime:
                    erase_list.append((name, filename))

    for name, filename in erase_list:
        erase(name, filename, 'collected')

    io.log(6, 'tmpfile.collect %d files erased' % len(erase_list))

    del erase_list


def startup_clean():
    """
    At startup we want to scan all sub folders and remove the old files.
    We will get creation time with built-in ``os.stat`` method.
    """
    global _TempDirPath
    global _SubDirs
    io.log(6, 'tmpfile.startup_clean in %s' % _TempDirPath)
    if _TempDirPath is None:
        return
    counter = 0
    for name in os.listdir(_TempDirPath):
        # we want to scan only our folders
        # do not want to be responsible of other files
        if name not in _SubDirs.keys():
            continue

        # for data and parity files we have special rules
        # we do not want to remove Data or Parity here.
        # backup_monitor should take care of this.
        if name == 'data-par':
            pass

        else:
            lifetime = _SubDirs.get(name, 0)
            if lifetime == 0:
                continue
            for filename in os.listdir(subdir(name)):
                filepath = os.path.join(subdir(name), filename)
                filetime = os.stat(filepath).st_ctime
                if time.time() - filetime > lifetime:
                    erase(name, filepath, 'startup cleaning')
                    counter += 1
                    if counter > 200:
                        break

#------------------------------------------------------------------------------


if __name__ == '__main__':
    io.SetDebug(18)
    init()
    fd, filename = make('raid')
    os.write(fd, 'TEST FILE')
    os.close(fd)
    from twisted.internet import reactor
    reactor.run()




