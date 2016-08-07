import os
import sys
import traceback


_Debug = True
_DebugLevel = 10


def out(msg, debug_level=_DebugLevel, getframe_depth=0):
    """
    The core method, most useful thing in any project :-)))
    Print a text line to the log file or console.  
    
    :param debug_level: lower values is count as more important messages. 
    I am using only even values from 0 to 18. 
    :param msg: message string to be printed
    :param nl: this string is added at the end, set to empty string to avoid new line.     
    """
    global _Debug
    if not _Debug:
        return

    cod = sys._getframe().f_back.f_code
    modul = os.path.basename(cod.co_filename).replace('.py', '') 
    caller = cod.co_name

    try:
        from logs import lg
        lg.out(debug_level, "%s.%s %s" % (modul, caller, str(msg)))
    except:
        print "%s.%s %s" % (modul, caller, str(msg))


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

def exc(exc_info=None, maxTBlevel=100):
    """
    This is second most common method in good error handling Python project :-)
    Print detailed info about last/given exception to the logs.
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
    out('Exception: <' + exception_name(value) + '>', getframe_depth=1)
    if excArgs:
        out('  args:' + excArgs, getframe_depth=1)
    for l in excTb:
        out(l.rstrip(), getframe_depth=1)

def exc_short(info=''):
    _, value, _ = sys.exc_info()
    out(exception_name(value) + ': ' + str(info), getframe_depth=2)
