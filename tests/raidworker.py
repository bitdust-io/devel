
import os
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred

sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath('..'))

from logs import lg

def main():
    lg.set_debug_level(24)
    
    # TEST
    # call with parameters like that:
    # python raidworker.py C:\temp\joomla2.sql ecc/7x7 myID_ABC 1234 c:\temp\somedir
    tasks = {}
    def _cb(cmd, taskdata, result):
        print 'DONE!', cmd, taskdata, result
        tasks.pop(taskdata[3])
        if len(tasks) == 0:
            reactor.stop()
        else:
            print len(tasks), 'more'
    def _add(blocknum):
        tasks[blocknum] = (sys.argv[1], sys.argv[2], sys.argv[3], blocknum, sys.argv[5])
        raid_worker.A('new-task',
            ('make', (sys.argv[1], sys.argv[2], sys.argv[3], blocknum, sys.argv[5]), 
                _cb))
    from system import bpio 
    bpio.init()
    lg.set_debug_level(20)
    from raid import raid_worker
    reactor.callWhenRunning(raid_worker.A, 'init')
    start_block_num = int(sys.argv[4])
    reactor.callLater(0.01, _add, start_block_num)
    reactor.callLater(0.02, _add, start_block_num+1)
    reactor.callLater(0.03, _add, start_block_num+2)
    reactor.callLater(0.04, _add, start_block_num+3)
    reactor.callLater(0.05, _add, start_block_num+4)
    reactor.run()
    

if __name__ == '__main__':
    main()
