#!/usr/bin/python
# log.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (lg.py) is part of BitDust Software.
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
..

module:: lg
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import os
import sys
import time
import threading
import traceback
import platform
from io import open

#------------------------------------------------------------------------------

_GlobalDebugLevel = 0
_LogLinesCounter = 0
_LogsEnabled = True
_UseColors = None
_RedirectStdOut = False
_NoOutput = False
_OriginalStdOut = None
_StdOutPrev = None
_LogFile = None
_LogFileName = None
_AllLogFiles = {}
_StoreExceptionsEnabled = True
_WebStreamFunc = None
_ShowTime = True
_LifeBeginsTime = 0
_TimePush = 0.0
_TimeTotalDict = {}
_TimeDeltaDict = {}
_TimeCountsDict = {}

#------------------------------------------------------------------------------

def fqn(o):
    """
    """
    return o.__module__ + "." + o.__name__

#------------------------------------------------------------------------------

def out(level, msg, nl='\n', log_name='main', showtime=False):
    """
    The core method, most useful thing in any project :-))) Print a text line
    to the log file or console.

    :param level: lower values is count as more important messages.
                        Usually I am using only even values from 0 to 18.
    :param msg: message string to be printed
    :param nl: this string is added at the end,
               set to empty string to avoid new line.
    """
    global _WebStreamFunc
    global _LogFile
    global _RedirectStdOut
    global _ShowTime
    global _LifeBeginsTime
    global _NoOutput
    global _LogLinesCounter
    global _LogsEnabled
    global _UseColors
    global _GlobalDebugLevel
    global _AllLogFiles
    if not _LogsEnabled:
        return
    s = msg
    s_ = s
    if level < 0:
        level = 0
    if level % 2:
        level -= 1
    if level:
        s = ' ' * level + s
    if ( _ShowTime and level > 0 ) or showtime:
        tm_string = time.strftime('%H:%M:%S')
        if _LifeBeginsTime != 0:
            dt = time.time() - _LifeBeginsTime
            mn = dt // 60
            sc = dt - mn * 60
            if _GlobalDebugLevel >= 6:
                tm_string += '/%02d:%06.3f' % (mn, sc)
            else:
                tm_string += '/%02d:%02d' % (mn, sc)
        if _UseColors is None:
            _UseColors = platform.uname()[0] != 'Windows'
        if _UseColors:
            tm_string = '\033[2;32m%s\033[0m' % tm_string
        if level == 0:
            tm_string += '  '
        s = tm_string + s
    if is_debug(30):
        currentThreadName = threading.currentThread().getName()
        s = s + ' {%s}' % currentThreadName.lower()
    if is_debug(level):
        if log_name == 'main':
            if _LogFile is not None:
                o = s + nl
                if sys.version_info[0] == 3:
                    if not isinstance(o, str):
                        o = o.decode('utf-8')
                else:
                    if not isinstance(o, unicode):  # @UndefinedVariable
                        o = o.decode('utf-8')
                _LogFile.write(o)
                _LogFile.flush()
        else:
            if _LogFileName:
                if log_name not in _AllLogFiles:
                    filename = os.path.join(os.path.dirname(_LogFileName), log_name + '.log') 
                    if not os.path.isdir(os.path.dirname(os.path.abspath(filename))):
                        os.makedirs(os.path.dirname(os.path.abspath(filename)))
                    _AllLogFiles[log_name] = open(os.path.abspath(filename), 'w')
                o = s + nl
                if sys.version_info[0] == 3:
                    if not isinstance(o, str):
                        o = o.decode('utf-8')
                else:
                    if not isinstance(o, unicode):  # @UndefinedVariable
                        o = o.decode('utf-8')
                _AllLogFiles[log_name].write(o)
                _AllLogFiles[log_name].flush()
        if not _RedirectStdOut and not _NoOutput:
            if log_name == 'main':
                s = s + nl
                try:
                    sys.stdout.write(s)
                except:
                    try:
                        sys.stdout.write(format_exception() + '\n\n' + s)
                    except:
                        # very bad stuff... we can't write anything to std out
                        pass
    if _WebStreamFunc is not None:
        _WebStreamFunc(level, s_ + nl)
    _LogLinesCounter += 1
    if _LogLinesCounter % 10000 == 0:
        out(2, '[%s]' % time.asctime())
    return None


def dbg(message):
    cod = sys._getframe().f_back.f_code
    modul = os.path.basename(cod.co_filename).replace('.py', '')
    caller = cod.co_name
    funcname = '%s.%s' % (modul, caller)
    o = '%s' % funcname
    if message:
        o += ' : ' + message
    out(0, o)
    return o


def args(level, *args, **kwargs):
    cod = sys._getframe().f_back.f_code
    modul = os.path.basename(cod.co_filename).replace('.py', '')
    caller = cod.co_name
    message = kwargs.pop('message', None)
    funcargs = []
    for k, v in enumerate(args):
        funcargs.append('%s' % v)
    for k, v in kwargs:
        funcargs.append('%s=%s' % (k, v))
    funcname = '%s.%s' % (modul, caller)
    o = '%s(%s)' % (funcname, ','.join(funcargs), )
    if message:
        o += ' : ' + message
    out(level, o)
    return o


def info(message):
    global _UseColors
    cod = sys._getframe().f_back.f_code
    modul = os.path.basename(cod.co_filename).replace('.py', '')
    caller = cod.co_name
    if _UseColors is None:
        _UseColors = platform.uname()[0] != 'Windows'
    if _UseColors:
        output_string = '\033[6;37;42m INFO %s \033[0m in %s.%s()' % (message, modul, caller, )
    else:
        output_string = ' INFO %s in %s.%s()' % (message, modul, caller, )
    out(0, output_string)
    return message


def warn(message, level=2):
    global _UseColors
    cod = sys._getframe().f_back.f_code
    modul = os.path.basename(cod.co_filename).replace('.py', '')
    caller = cod.co_name
    if _UseColors is None:
        _UseColors = platform.uname()[0] != 'Windows'
    if _UseColors:
        output_string = '\033[0;35mWARNING %s\033[0m in %s.%s()' % (message, modul, caller, )
    else:
        output_string = 'WARNING %s in %s.%s()' % (message, modul, caller, )
    out(level, output_string)
    return message


def err(message, level=0):
    global _UseColors
    cod = sys._getframe().f_back.f_code
    modul = os.path.basename(cod.co_filename).replace('.py', '')
    caller = cod.co_name
    funcname = '%s.%s' % (modul, caller)
    if isinstance(message, Exception):
        message = str(message)
    if not message.count(funcname):
        message = ' in %s() : "%s"' % (funcname, message)
    if not message.count('ERROR'):
        message = 'ERROR!!!  ' + message
    message = '%s%s   ' % ((' ' * (level + 11)), message)
    if _UseColors is None:
        _UseColors = platform.uname()[0] != 'Windows'
    if _UseColors:
        message = '\033[6;37;41m%s\033[0m' % message
    out(level, message)
    return message


def exc(msg='', level=0, maxTBlevel=100, exc_info=None, exc_value=None, **kwargs):
    global _UseColors
    if _UseColors is None:
        _UseColors = platform.uname()[0] != 'Windows'
    if _UseColors:
        msg = '\033[1;31m%s\033[0m' % msg
    if msg:
        out(level, msg)
    if exc_value:
        return exception(level, maxTBlevel, exc_info=('', exc_value, []))
    return exception(level, maxTBlevel, exc_info)


def errback(*args, **kwargs):
    err('Error occurred during deferred operation:\n%s' % traceback.format_exc())
    #  args: %s   kwargs: %s' % (str(*args), str(**kwargs)))
    return None


def exception(level, maxTBlevel, exc_info):
    """
    This is second most common method in good error handling Python project :-)
    Print detailed info about last/given exception to the logs.
    """
    global _LogFileName
    global _StoreExceptionsEnabled
    global _UseColors
    if exc_info is None:
        _, value, trbk = sys.exc_info()
    else:
        _, value, trbk = exc_info
    try:
        excArgs = value.__dict__["args"]
    except KeyError:
        excArgs = ''
    if trbk:
        excTb = traceback.format_tb(trbk, maxTBlevel)
    else:
        excTb = []
    exc_name = exception_name(value)
    s = 'Exception: <' + exc_name + '>'
    if _UseColors is None:
        _UseColors = platform.uname()[0] != 'Windows'
    if _UseColors:
        out(level, '\033[1;31m%s\033[0m' % (s.strip()))
    else:
        out(level, s.strip())
    if excArgs:
        s += '  args:' + excArgs + '\n'
        if _UseColors:
            out(level, '\033[1;31m  args: %s\033[0m' % excArgs)
        else:
            out(level, '  args: %s' % excArgs)
    s += '\n'
    # excTb.reverse()
    for l in excTb:
        s += l + '\n'
        if _UseColors:
            out(level, '\033[1;31m%s\033[0m' % (l.replace('\n', '')))
        else:
            out(level, l.replace('\n', ''))
    if trbk:
        try:
            f_locals = str(repr(trbk.tb_next.tb_next.tb_frame.f_locals))[:1000]
        except:
            f_locals = ''
        if f_locals:
            out(level, 'locals: %s' % f_locals)
    if _StoreExceptionsEnabled and _LogFileName:
        exc_label = exc_name.lower().replace(' ', '_').replace('-', '_')[:80]
        exc_label = ''.join([c for c in exc_label if c in '0123456789abcdefghijklmnopqrstuvwxyz_'])
        exc_filename = os.path.join(os.path.dirname(_LogFileName), 'exception_' + exc_label + '.log')
        if os.path.isfile(exc_filename):
            fout = open(exc_filename, 'ab')
        else:
            fout = open(exc_filename, 'wb')
        if sys.version_info[0] == 3:
            if not isinstance(s, bytes):
                s = s.encode('utf-8')
        else:
            if not isinstance(s, str):
                s = s.encode('utf-8')
        s += b'==========================================================\n\n'
        fout.write(s)
        fout.close()
        out(level, 'saved to: %s' % exc_filename)
    return s


def format_exception(maxTBlevel=100, exc_info=None):
    """
    Return string with detailed info about last exception.
    """
    if exc_info is None:
        _, value, trbk = sys.exc_info()
    else:
        _, value, trbk = exc_info
    try:
        excArgs = value.__dict__["args"]
    except KeyError:
        excArgs = ''
    excTb = traceback.format_tb(trbk, maxTBlevel)
    tbstring = 'Exception: <' + exception_name(value) + '>\n'
    if excArgs:
        tbstring += '  args:' + excArgs + '\n'
    for s in excTb:
        tbstring += s + '\n'
    return tbstring


def exception_name(value):
    """
    Some tricks to extract the correct exception name from traceback string.
    """
    try:
        if sys.version_info[0] == 3:
            excStr = str(value)
        else:
            excStr = unicode(value)  # @UndefinedVariable
    except:
        try:
            excStr = repr(value)
        except:
            try:
                excStr = str(value)
            except:
                try:
                    excStr = value.message
                except:
                    excStr = type(value).__name__
    return excStr


def set_debug_level(level):
    """
    Code will use ``level`` 2-4 for most important things and 10 for really
    minor stuff.

    Level 14 and higher is for things we don't think we want to see
    again. Can set ``level`` to 0 for no debug messages at all.
    """
    global _GlobalDebugLevel
    level = int(level)
    if _GlobalDebugLevel > level:
        out(level, 'lg.SetDebug _GlobalDebugLevel=' + str(level))
    _GlobalDebugLevel = level


def get_debug_level():
    """

    """
    global _GlobalDebugLevel
    return _GlobalDebugLevel


def get_loging_level(level):
    """
    Find corresponding logging level related to BitDust log level:

        0 : CRITICAL
        1-2 : FATAL
        3-4 : ERROR
        5-6 : WARNING
        7-8 : INFO
        9-10 : DEBUG
        11... : NOTSET
    """
    import logging
    if level == 0:
        return logging.CRITICAL
    if level <= 2:
        return logging.FATAL
    if level <= 4:
        return logging.ERROR
    if level <= 6:
        return logging.WARNING
    if level <= 8:
        return logging.INFO
    if level <= 10:
        return logging.DEBUG
    return logging.NOTSET


def life_begins():
    """
    Start counting time in the logs from that moment.

    If not called the logs will contain current system time.
    """
    global _LifeBeginsTime
    _LifeBeginsTime = time.time()


def when_life_begins():
    global _LifeBeginsTime
    return _LifeBeginsTime


def is_debug(level):
    """
    Return True if something at this ``level`` should be reported given current
    _GlobalDebugLevel.
    """
    global _GlobalDebugLevel
    return _GlobalDebugLevel >= level


def out_globals(level, glob_dict):
    """
    Print all items from dictionary ``glob_dict`` to the logs if current
    _GlobalDebugLevel is higher than ``level``.
    """
    global _GlobalDebugLevel
    if level > _GlobalDebugLevel:
        return
    keys = sorted(glob_dict.keys())
    for k in keys:
        if k != '__builtins__':
            out(level, "%s : %s" % (k, glob_dict[k]))


def time_push(t):
    """
    Remember current system time and set ``t`` marker to that.

    Useful to count execution time of some parts of the code.
    """
    global _TimeTotalDict
    global _TimeDeltaDict
    global _TimeCountsDict
    tm = time.time()
    if t not in _TimeTotalDict:
        _TimeTotalDict[t] = 0.0
        _TimeCountsDict[t] = 0
    _TimeDeltaDict[t] = tm


def time_pop(t):
    """
    Count execution time for marker ``t``.
    """
    global _TimeTotalDict
    global _TimeDeltaDict
    global _TimeCountsDict
    tm = time.time()
    if t not in _TimeTotalDict:
        return
    dt = tm - _TimeDeltaDict[t]
    _TimeTotalDict[t] += dt
    _TimeCountsDict[t] += 1


def print_total_time():
    """
    Print total stats for all time markers.
    """
    global _TimeTotalDict
    global _TimeDeltaDict
    global _TimeCountsDict
    for t in _TimeTotalDict.keys():
        total = _TimeTotalDict[t]
        counts = _TimeCountsDict[t]
        out(2, 'total=%f sec. count=%d, avarage=%f: %s' % (total, counts, total / counts, t))


def exception_hook(typ, value, traceback):
    """
    Callback function to print last exception.
    """
    out(0, 'uncaught exception:')
    exc(exc_info=(typ, value, traceback))


def open_log_file(filename, append_mode=False):
    """
    Open a log file, so all logs will go here instead of STDOUT.
    """
    global _LogFile
    global _LogFileName
    if _LogFile:
        return
    try:
        if not os.path.isdir(os.path.dirname(os.path.abspath(filename))):
            os.makedirs(os.path.dirname(os.path.abspath(filename)))
        if append_mode:
            _LogFile = open(os.path.abspath(filename), 'a')
        else:
            _LogFile = open(os.path.abspath(filename), 'w')
        _LogFileName = os.path.abspath(filename)
    except:
        out(0, 'cant open ' + filename)
        exc()


def close_log_file():
    """
    Closes opened log file.
    """
    global _LogFile
    global _AllLogFiles
    if not _LogFile:
        return
    _LogFile.flush()
    _LogFile.close()
    _LogFile = None
    for logfile in _AllLogFiles.values():
        logfile.flush()
        logfile.close()
    _AllLogFiles.clear()


def log_file():
    global _LogFile
    return _LogFile


def log_filename():
    global _LogFileName
    return _LogFileName


def stdout_start_redirecting():
    """
    Replace sys.stdout with STDOUT_redirected so all output get logged.
    """
    global _RedirectStdOut
    global _StdOutPrev
    _RedirectStdOut = True
    _StdOutPrev = sys.stdout
    sys.stdout = STDOUT_redirected()


def stdout_stop_redirecting():
    """
    Restore sys.stdout after ``stdout_start_redirecting``.
    """
    global _RedirectStdOut
    global _StdOutPrev
    _RedirectStdOut = False
    if _StdOutPrev is not None:
        sys.stdout = _StdOutPrev


def disable_output():
    """
    Disable any output to sys.stdout.
    """
    global _RedirectStdOut
    global _StdOutPrev
    global _NoOutput
    _NoOutput = True
    _RedirectStdOut = True
    _StdOutPrev = sys.stdout
    sys.stdout = STDOUT_black_hole()


def disable_logs():
    """
    Clear _LogsEnabled flag, so calls to ``log()`` and ``exc()`` will do
    nothing.

    Must be used in production release to increase performance. However
    I plan to comment all lines with ``lg.log()`` at all.
    """
    global _LogsEnabled
    _LogsEnabled = False


def logs_enabled():
    global _LogsEnabled
    return _LogsEnabled


def setup_unbuffered_stdout():
    """
    This makes logs to be printed without delays in Linux - unbuffered output.
    Great thanks, the idea is taken from here:
        http://algorithmicallyrandom.blogspot.com/2009/10/python-tips-and-tricks-flushing-stdout.html
    """
    global _OriginalStdOut
    _OriginalStdOut = sys.stdout
    sys.stdout = STDUOUT_unbuffered(sys.stdout)


def restore_original_stdout():
    """
    Restore original STDOUT, need to be called after
    ``setup_unbuffered_stdout`` to get back to default state.
    """
    global _OriginalStdOut
    if _OriginalStdOut is None:
        return
    _std_out = sys.stdout
    sys.stdout = _OriginalStdOut
    _OriginalStdOut = None
    try:
        _std_out.close()
    except Exception as exc:
        pass


def set_weblog_func(webstreamfunc):
    """
    Set callback method to be called in Dprint, used to show logs in the WEB
    browser.

    See ``bitdust.lib.weblog`` module.
    """
    global _WebStreamFunc
    _WebStreamFunc = webstreamfunc

#------------------------------------------------------------------------------


class STDOUT_redirected(object):
    """
    Emulate system STDOUT, useful to log any program output.
    """
    softspace = 0

    def read(self): pass

    def write(self, s):
        out(0, s.rstrip())

    def flush(self): pass

    def close(self): pass


class STDOUT_black_hole(object):
    """
    Useful to disable any output to STDOUT.
    """
    softspace = 0

    def read(self): pass

    def write(self, s): pass

    def flush(self): pass

    def close(self): pass


class STDUOUT_unbuffered(object):

    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    def writelines(self, datas):
        self.stream.writelines(datas)
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)
