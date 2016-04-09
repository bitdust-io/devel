
from twisted.internet.defer import Deferred
from twisted.internet import reactor

try:
    from logs import lg
except:
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))        
from logs import lg

#------------------------------------------------------------------------------ 

def run_tests():
    from interface import api
    reactor.callLater(15, api.ping, 'http://p2p-id.ru/atg314.xml')

#------------------------------------------------------------------------------ 

def main():
    from interface import api
    from main import settings
    from main import bpmain
    from system import bpio
    from services import driver
    lg.open_log_file('test_api.log')
    lg.set_debug_level(20)
    lg.life_begins()
    lg._NoOutput = True
    bpio.init()
    bpmain.init()
    reactor.callWhenRunning(run_tests)
    reactor.callLater(60, api.stop)
    bpmain.run_twisted_reactor()
    bpmain.shutdown()
    
if __name__ == '__main__':
    import coverage
    cov = coverage.Coverage()
    cov.start()
    main()
    cov.stop()
    cov.save()
    cov.report()
