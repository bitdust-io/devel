#!/usr/bin/python
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: bppipe

This python code can be used to replace the Unix tar command
and so be portable to non-unix machines.
There are other python tar libraries, but this is included with Python.
So that file is starter as child process of BitDust to prepare data for backup.

.. warning:: Note that we should not print things here because tar output goes to standard out.
             If we print anything else to stdout the .tar file will be ruined.
             We must also not print things in anything this calls.

Inspired from examples here:

* `http://docs.python.org/lib/tar-examples.html`
* `http://code.activestate.com/recipes/299412`

TODO: 
If we kept track of how far we were through a list of files, and broke off
new blocks at file boundaries, we could restart a backup and continue
were we left off if a crash happened while we were waiting to send a block
(most of the time is waiting so good chance).
"""

import os
import sys
import platform
import tarfile
import traceback

#------------------------------------------------------------------------------ 

AppData = ''

#------------------------------------------------------------------------------ 

def sharedPath(filename, subdir='logs'):
    global AppData
    if AppData == '':
        curdir = os.getcwd() # os.path.dirname(os.path.abspath(sys.executable))
        if os.path.isfile(os.path.join(curdir, 'appdata')):
            try:
                appdata = os.path.abspath(open(os.path.join(curdir, 'appdata'), 'rb').read().strip()) 
            except:
                appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
            if not os.path.isdir(appdata):
                appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
        else: 
            appdata = os.path.join(os.path.expanduser('~'), '.bitdust')
        AppData = appdata
    return os.path.join(AppData, subdir, filename)

def logfilepath():
    """
    A method to detect where is placed the log file for ``bppipe`` child process.
    """
#    logspath = os.path.join(os.path.expanduser('~'), '.bitdust', 'logs')
#    if not os.path.isdir(logspath):
#        return 'bppipe.log'
#    return os.path.join(logspath, 'bppipe.log')
    return sharedPath('bppipe.log')

def printlog(txt, mode='a'):
    """
    Write a line to the log file.
    """
    try:
        LogFile = open(logfilepath(), mode)
        LogFile.write(txt)
        LogFile.close()
    except:
        pass
    
def printexc():
    """
    Write exception info to the log file.
    """
    printlog('\n'+traceback.format_exc()+'\n')

#------------------------------------------------------------------------------ 

def _LinuxExcludeFunction(filename):
    """
    Return True if given file must not be included in the backup.  
    Filename comes in with the path relative to the start path, so: 
        "dirbeingbackedup/photos/christmas2008.jpg"
        
    PREPRO:
    On linux we should test for the attribute meaning "nodump" or "nobackup"
    This is set with:
        chattr +d <file>
    And listed with: 
        lsattr <file>
    Also should test that the file is readable and maybe that directory is executable. 
    If tar gets stuff it can not read - it just stops and we the whole process is failed.
    """
    # TODO: - must do more smart checking 
    if filename.count(".bitdust"):
        return True
    if not os.access(filename, os.R_OK):
        return True
    return False # don't exclude the file

def _WindowsExcludeFunction(filename):
    """
    Same method for Windows platforms.
    Filename comes in with the path relative to the start path, so: 
        "Local Settings\Application Data\Microsoft\Windows\UsrClass.dat"
    
    PREPRO:
    On windows I run into some files that Windows tells me 
    I don't have permission to open (system files), 
    I had hoped to use 
        os.access(filename, os.R_OK) == False 
    to skip a file if I couldn't read it, but I did not get it to work every time. DWC.
    """
    if (filename.lower().find("local settings\\temp") != -1) or (filename.lower().find(".bitdust") != -1) :
        return True
    if sys.version_info[:2] == (2, 7):
        if not os.access(filename, os.R_OK):
            return True
    # printlog(filename+'\n') 
    return False # don't exclude the file

_ExcludeFunction = _LinuxExcludeFunction
if platform.uname()[0] == 'Windows':
    _ExcludeFunction = _WindowsExcludeFunction

#------------------------------------------------------------------------------
 
def writetar(sourcepath, subdirs=True, compression='none', encoding=None):
    """
    Create a tar archive from given ``sourcepath`` location.
    """
    # printlog(os.path.abspath(sourcepath))
    mode = 'w|'
    if compression != 'none':
        mode += compression
    basedir, filename = os.path.split(sourcepath)
    tar = tarfile.open('', mode, fileobj=sys.stdout, encoding=encoding)
    # if we have python 2.6 then we can use an exclude function, filter parameter is not available
    if sys.version_info[:2] == (2, 6):
        tar.add(sourcepath, unicode(filename), subdirs, _ExcludeFunction) 
        if not subdirs and os.path.isdir(sourcepath): # the True is for recursive, if we wanted to just do the immediate directory set to False
            for subfile in os.listdir(sourcepath):
                subpath = os.path.join(sourcepath, subfile)
                if not os.path.isdir(subpath): 
                    tar.add(subpath, unicode(os.path.join(filename, subfile)), subdirs, _ExcludeFunction)
    # for python 2.7 we should have a filter parameter, which should be used instead of exclude function 
    elif sys.version_info[:2] == (2, 7):
        def _filter(tarinfo, basedir):
            global _ExcludeFunction
            if _ExcludeFunction(os.path.join(basedir,tarinfo.name)):
                return None
            return tarinfo
        # printlog(sourcepath+'\n')
        tar.add(sourcepath, unicode(filename), subdirs, filter=lambda tarinfo: _filter(tarinfo, basedir)) 
        if not subdirs and os.path.isdir(sourcepath):
            # the True is for recursive, if we wanted to just do the immediate directory set to False
            for subfile in os.listdir(sourcepath):
                subpath = os.path.join(sourcepath, subfile)
                # printlog(subpath+'\n')
                if not os.path.isdir(subpath): 
                    tar.add(subpath, unicode(os.path.join(filename, subfile)), subdirs, filter=_filter) 
    # otherwise no exclude function
    else: 
        tar.add(sourcepath, unicode(filename), subdirs)
        if not subdirs and os.path.isdir(sourcepath):
            for subfile in os.listdir(sourcepath):
                subpath = os.path.join(sourcepath, subfile)
                if not os.path.isdir(subpath): 
                    tar.add(subpath, unicode(os.path.join(filename, subfile)), subdirs)
    tar.close()

#------------------------------------------------------------------------------ 

def readtar(archivepath, outputdir, encoding=None):
    """
    Extract tar file from ``archivepath`` location into local ``outputdir`` folder.
    """
    mode = 'r:*'
    tar = tarfile.open(archivepath, mode, encoding=encoding)
    tar.extractall(outputdir)
    tar.close()

#------------------------------------------------------------------------------ 

def main():
    """
    The entry point of the ``bppipe`` child process. 
    Use command line arguments to get the command from ``bpmain``. 
    """
    try:
        import msvcrt
        msvcrt.setmode(1, os.O_BINARY)
    except:
        pass

    try:
        import sys
        reload(sys)
        if hasattr(sys, "setdefaultencoding"):
            import locale
            denc = locale.getpreferredencoding()
            if denc != '':
                sys.setdefaultencoding(denc)
    except:
        pass

    # printlog('sys.argv: %s\n' % str(sys.argv), 'w')

    if len(sys.argv) < 4:
        printlog('bppipe ["subdirs"/"nosubdirs"/"extract"] ["none"/"bz2"/"gz"] [folder path]\n')
        return 2

    try:
        cmd = sys.argv[1].strip().lower()
        if cmd == 'extract':
            readtar(sys.argv[2], sys.argv[3])
        else:
            writetar(sys.argv[3], cmd == 'subdirs', sys.argv[2], encoding=locale.getpreferredencoding())
    except:
        printexc()
        return 1
    
    return 0

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    main()


