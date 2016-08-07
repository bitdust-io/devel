import os
import sys

_Debug = True
_DebugLevel = 10


def out(msg, debug_level=_DebugLevel):
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
