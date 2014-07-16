import os
import sys


try:
    import lib.bpio as bpio
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    try:
        import lib.bpio as bpio
    except:
        sys.exit()

from twisted.internet import reactor
        
import pp

import make

js = pp.Server()
tsks = range(20)
active = []

def _print():
    js.print_stats()

def _func(filename, eccmapname, backupId, blockNumber, targetDir):
    return make.do_in_memory(filename, eccmapname, backupId, blockNumber, targetDir)
    
def _cb(result, bnum):
    global active
    print 'cb', result, bnum, active
    active.remove(bnum)
    if len(tsks) == 0 and len(active) == 0:
        _print()
        reactor.stop()
    else:
        _more()

def _more():
    global js
    global tsks
    global active
    while len(tsks) > 0:
        if len(active) >= js.get_ncpus():
            break
        blockNumber = tsks.pop(0)
        active.append(blockNumber) 
        l = sys.argv[1:]
        l.insert(-1, str(blockNumber))
        args = tuple(l)
        js.submit(_func, args, modules=('make',), 
                  callback=lambda result: _cb(result, blockNumber), ) # callbackargs=(sys.argv[2],),)
        print 'more', tsks, active
        break
    reactor.callLater(0.01, _more)

_more()
reactor.run()

