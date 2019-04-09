#!/usr/bin/env python
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (bppipe.py) is part of BitDust Software.
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
.. module:: bppipe.

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

#------------------------------------------------------------------------------ 

from __future__ import absolute_import
import six
from io import open

#------------------------------------------------------------------------------

import os
import sys
import platform
import tarfile
import traceback

#------------------------------------------------------------------------------

AppData = ''
_ExcludeFunction = None

#------------------------------------------------------------------------------

if sys.version_info[0] == 3:
    text_type = str
    binary_type = bytes
else:
    text_type = unicode  # @UndefinedVariable
    binary_type = str

#------------------------------------------------------------------------------

def is_text(s):
    """
    Return `True` if `s` is a text value:
    + `unicode()` in Python2
    + `str()` in Python3
    """
    return isinstance(s, text_type)


def is_bin(s):
    """
    Return `True` if `s` is a binary value:
    + `str()` in Python2
    + `bytes()` in Python3
    """
    return isinstance(s, binary_type)


def is_string(s):
    """
    Return `True` if `s` is text or binary type (not integer, class, list, etc...)
    """
    return is_text(s) or is_bin(s)


def to_text(s, encoding='utf-8', errors='strict'):
    """
    If ``s`` is binary type - decode it to unicode - "text" type in Python3 terms.
    If ``s`` is not binary and not text calls `str(s)` to build text representation.
    """
    if s is None:
        return s
    if not is_string(s):
        s = text_type(s)
    if is_text(s):
        return s
    return s.decode(encoding=encoding, errors=errors)


def sharedPath(filename, subdir='logs'):
    global AppData
    if AppData == '':
        curdir = os.getcwd()  # os.path.dirname(os.path.abspath(sys.executable))
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
    A method to detect where is placed the log file for ``bppipe`` child
    process.
    """
    return sharedPath('bppipe.log')


def printlog(txt, mode='a'):
    """
    Write a line to the log file.
    """
    # try:
    LogFile = open(logfilepath(), mode)
    LogFile.write(to_text(txt))
    LogFile.close()
    # except:
    #     pass


def printexc():
    """
    Write exception info to the log file.
    """
    printlog('\n' + traceback.format_exc() + '\n')

#------------------------------------------------------------------------------

def LinuxExcludeFunction(source_path, tar_path):
    """
    Return True if given file must not be included in the backup. Filename
    comes in with the path relative to the start path, so:
    "dirbeingbackedup/photos/christmas2008.jpg".

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
    # if filename.count(".bitdust"):
    #     return True
    if not os.access(source_path, os.R_OK):
        return True
    return False  # don't exclude the file


def WindowsExcludeFunction(source_path, tar_path):
    """
    Same method for Windows platforms. Filename comes in with the path relative
    to the start path, so: "Local Settings/Application Data/Microsoft/Windows/UsrClass.dat"

    PREPRO: On windows I run into some files that Windows tells me I
    don't have permission to open (system files), I had hoped to use
    os.access(filename, os.R_OK) == False to skip a file if I couldn't
    read it, but I did not get it to work every time. DWC.
    """
    # TODO: - must do more smart checking
    # if source_path.lower().count(".bitdust"):
    #     return True
    if (source_path.lower().find("local settings\\temp") != -1):
        return True
    if not os.access(source_path, os.R_OK):
        return True
    return False  # don't exclude the file

#------------------------------------------------------------------------------

_ExcludeFunction = LinuxExcludeFunction
if platform.uname()[0] == 'Windows':
    _ExcludeFunction = WindowsExcludeFunction

#------------------------------------------------------------------------------

def writetar_filter(tarinfo, sourcepath):
    global _ExcludeFunction
    if _ExcludeFunction(sourcepath, tarinfo.name):
        return None
    return tarinfo

#------------------------------------------------------------------------------

def writetar(sourcepath, arcname=None, subdirs=True, compression='none', encoding=None):
    """
    Create a tar archive from given ``sourcepath`` location.
    """
    global _ExcludeFunction
    printlog('WRITE: %s arcname=%s, subdirs=%s, compression=%s, encoding=%s\n' % (
        sourcepath, arcname, subdirs, compression, encoding))
    mode = 'w|'
    if compression != 'none':
        mode += compression
    _, filename = os.path.split(sourcepath)
    if arcname is None:
        arcname = to_text(filename)
    else:
        arcname = to_text(arcname)
    # DEBUG: tar = tarfile.open('', mode, fileobj=open('out.tar', 'wb'), encoding=encoding)
    tar = tarfile.open('', mode, fileobj=sys.stdout, encoding=encoding)
    tar.add(
        name=sourcepath,
        arcname=arcname,
        recursive=subdirs,
        filter=lambda tarinfo: writetar_filter(tarinfo, sourcepath),
    )
    if not subdirs and os.path.isdir(sourcepath):
        # the True is for recursive, if we wanted to just do the immediate directory set to False
        for subfile in os.listdir(sourcepath):
            subpath = os.path.join(sourcepath, subfile)
            if not os.path.isdir(subpath):
                tar.add(
                    name=subpath,
                    arcname=to_text(os.path.join(arcname, subfile)),
                    recursive=False,
                    filter=lambda tarinfo: writetar_filter(tarinfo, subpath),
                )
    tar.close()

#------------------------------------------------------------------------------


def readtar(archivepath, outputdir, encoding=None):
    """
    Extract tar file from ``archivepath`` location into local ``outputdir``
    folder.
    """
    printlog('READ: %s to %s, encoding=%s\n' % (
        archivepath, outputdir, encoding))
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
    ostype = platform.uname()[0]

    if ostype == 'Windows':
        if six.PY3:
            sys.stdout = sys.stdout.buffer
        else:
            try:
                import msvcrt
                msvcrt.setmode(1, os.O_BINARY)  # @UndefinedVariable
            except:
                pass

    else:
        if six.PY3:
            sys.stdout = sys.stdout.buffer

    if len(sys.argv) < 4:
        printlog('bppipe extract <archive path> <output dir>\n')
        printlog('bppipe <subdirs / nosubdirs> <"none" / "bz2" / "gz"> <folder/file path> [archive filename]\n')
        return 2

    try:
        cmd = sys.argv[1].strip().lower()

        if cmd == 'extract':
            readtar(
                archivepath=sys.argv[2],
                outputdir=sys.argv[3],
                encoding='utf-8',
            )

        else:
            arcname = None
            if len(sys.argv) >= 5:
                arcname = sys.argv[4]
            writetar(
                sourcepath=sys.argv[3],
                arcname=arcname,
                subdirs=True if cmd == 'subdirs' else False,
                compression=sys.argv[2],
                encoding='utf-8',
            )
    except:
        printexc()
        return 1

    return 0

#------------------------------------------------------------------------------


if __name__ == "__main__":
    main()
