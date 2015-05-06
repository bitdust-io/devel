#!/usr/bin/python
#log.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: lg

"""

import os
import sys
import time
import threading
import traceback

#------------------------------------------------------------------------------ 

_DebugLevel = 0
_LogLinesCounter = 0
_LogsEnabled = True
_RedirectStdOut = False
_NoOutput = False
_OriginalStdOut = None
_StdOutPrev = None
_LogFile = None
_LogFileName = None
_WebStreamFunc = None
_ShowTime = True
_LifeBeginsTime = 0
_TimePush = 0.0
_TimeTotalDict = {}
_TimeDeltaDict = {}
_TimeCountsDict = {}

#------------------------------------------------------------------------------ 

def out(level, msg, nl='\n'):
    """
    The core method, most used thing in the whole project.
    Print a line to the log file or console.  
    
    :param level: lower values is count as more important messages. I am using only even values from 0 to 18. 
    :param s: message string to be printed
    :param nl: this string is added at the end, set to empty string to avoid new line.     
    """
    global _WebStreamFunc
    global _LogFile
    global _RedirectStdOut
    global _ShowTime
    global _LifeBeginsTime
    global _NoOutput
    global _LogLinesCounter
    global _LogsEnabled
    global _DebugLevel
    if not _LogsEnabled:
        return
    s = '' + msg
    if isinstance(s, unicode):
        s = s.encode('utf-8')
    s_ = s
    if level % 2:
        level -= 1
    if level:
        s = ' ' * level + s
    if _ShowTime and level > 0:
        if _LifeBeginsTime != 0:
            dt = time.time() - _LifeBeginsTime
            mn = dt // 60
            sc = dt - mn * 60
            if _DebugLevel >= 10:
                s = ('%02d:%06.3f' % (mn, sc)) + s
            else:
                s = ('%02d:%02d' % (mn, sc)) + s
        else:
            s = time.strftime('%H:%M:%S') + s
    if is_debug(30):
        currentThreadName = threading.currentThread().getName()
        s = s + ' {%s}' % currentThreadName.lower()
    if is_debug(level):
        if _LogFile is not None:
            _LogFile.write(s + nl)
            _LogFile.flush()
        if not _RedirectStdOut and not _NoOutput:
#            if nl == '\n':
#                try:
#                    print s
#                except:
#                    open('1', 'wb').write(s)
#                    sys.exit()
#                    # pass
#            else:
            try:
                s = str(s) + nl
                sys.stdout.write(s)
            except:
                sys.stdout.write(format_exception() + '\n\n' + s)
                
    if _WebStreamFunc is not None:
        _WebStreamFunc(level, s_ + nl)
    _LogLinesCounter += 1
    if _LogLinesCounter % 10000 == 0:
        out(2, '[%s]' % time.asctime())


def warn(message, level=2):
    cod = sys._getframe().f_back.f_code
    modul = os.path.basename(cod.co_filename).replace('.py', '') 
    caller = cod.co_name
    # caller = inspect.
    out(level, '%s.%s WARNING %s' % (modul, caller, message))

def exc(msg=''):
    if msg:
        out(2, msg)
    return exception(0, 100, None)


def exception(level, maxTBlevel, exc_info):
    """
    This is second most common method in the project.
    Print detailed info about last exception to the logs.
    """
    global _LogFileName
    if exc_info is None:
        cla, value, trbk = sys.exc_info()
    else:
        cla, value, trbk = exc_info
    try:
        excArgs = value.__dict__["args"]
    except KeyError:
        excArgs = ''
    excTb = traceback.format_tb(trbk, maxTBlevel)    
    s = 'Exception: <' + exception_name(value) + '>\n'
    out(level, s.strip())
    if excArgs:
        s += '  args:' + excArgs + '\n'
        out(level, '  args:' + excArgs)
    s += '\n'
    # excTb.reverse()
    for l in excTb:
        out(level, l.replace('\n', ''))
        s += l + '\n'
    try:
        file = open(os.path.join(os.path.dirname(_LogFileName), 'exception.log'), 'w')
        file.write(s)
        file.close()
    except:
        pass
    return s


def format_exception(maxTBlevel=100, exc_info=None):
    """
    Return string with detailed info about last exception.  
    """
    if exc_info is None:
        cla, value, trbk = sys.exc_info()
    else:
        cla, value, trbk = exc_info
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
        excStr = unicode(value)
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
    Code will use ``level`` 2-4 for most important things and 10 for really minor stuff. 
    Level 14 and higher is for things we don't think we want to see again.
    Can set ``level`` to 0 for no debug messages at all.
    """
    global _DebugLevel
    if _DebugLevel > level:
        out(level, 'lg.SetDebug _DebugLevel=' + str(level))
    _DebugLevel = level


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
    Return True if something at this ``level`` should be reported given current _DebugLevel.
    """
    global _DebugLevel
    return _DebugLevel >= level


def out_globals(level, glob_dict):
    """
    Print all items from dictionary ``glob_dict`` to the logs if current _DebugLevel is higher than ``level``. 
    """
    global _DebugLevel
    if level > _DebugLevel:
        return
    keys = glob_dict.keys()
    keys.sort()
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
    if not _TimeTotalDict.has_key(t):
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
    if not _TimeTotalDict.has_key(t):
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
        out(2, 'total=%f sec. count=%d, avarage=%f: %s' % (total, counts, total/counts, t))


def exception_hook(type, value, traceback):
    """
    Callback function to print last exception.
    """
    out(0, 'uncaught exception:')
    exc(exc_info=(type, value, traceback))


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
    if not _LogFile:
        return
    _LogFile.flush()
    _LogFile.close()
    _LogFile = None


def log_file():
    global _LogFile
    return _LogFile


def log_filename():
    global _LogFileName
    return _LogFileName


def stdout_start_redirecting():
    """
    Replace sys.stdout with PATCHED_stdout so all output get logged.
    """
    global _RedirectStdOut
    global _StdOutPrev
    _RedirectStdOut = True
    _StdOutPrev = sys.stdout
    sys.stdout = PATCHED_stdout()


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
    Clear _LogsEnabled flag, so calls to ``log()`` and ``exc()`` will do nothing.
    Must be used in production release to increase performance.
    However I plan to comment all lines with ``lg.log()`` at all.  
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
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
    
    
def restore_original_stdout():
    """
    Restore original STDOUT, need to be called after ``setup_unbuffered_stdout`` to get back to default state.
    """
    global _OriginalStdOut
    if _OriginalStdOut is None:
        return
    try:
        _std_out = sys.stdout
        sys.stdout = _OriginalStdOut
        _std_out.close()
    except:
        traceback.print_last(file=open('bitdust.error', 'w'))


def set_weblog_func(webstreamfunc):
    """
    Set callback method to be called in Dprint, used to show logs in the WEB browser.
    See ``bitdust.lib.weblog`` module. 
    """
    global _WebStreamFunc
    _WebStreamFunc = webstreamfunc

#------------------------------------------------------------------------------ 

class PATCHED_stdout:
    """
    Emulate system STDOUT, useful to log any program output. 
    """
    softspace = 0
    def read(self): pass
    def write(self, s):
        out(0, unicode(s).rstrip())
    def flush(self): pass
    def close(self): pass


class STDOUT_black_hole:
    """
    Useful to disable any output to STDOUT.
    """
    softspace = 0
    def read(self): pass
    def write(self, s):  pass
    def flush(self): pass
    def close(self): pass
