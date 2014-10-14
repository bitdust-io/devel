
import os
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred

sys.path.append(os.path.abspath('..'))

from logs import lg

def main():
    lg.set_debug_level(24)
    
    # TEST
    import transport.gateway
    transport.gateway.init(['tcp',])
    import userid.propagate
    userid.propagate.SendServers()
    reactor.run()


if __name__ == '__main__':
    main()
