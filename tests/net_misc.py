import os
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

def main():
    def _ok(x):
        print 'ok', x
        reactor.stop()
    def _fail(x):
        print 'fail', x
        reactor.stop()        
    from lib import net_misc
    from main import settings
    settings.init()
    settings.update_proxy_settings()
    idurl = 'http://p2p-id.ru/atg314.xml'
    r = net_misc.getPageTwisted(idurl)
    r.addCallback(_ok)
    r.addErrback(_fail)
    reactor.run()

if __name__ == '__main__':
    main()