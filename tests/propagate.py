
import os
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred

sys.path.append(os.path.abspath('..'))

from logs import lg

def main():
    lg.set_debug_level(24)
    
    
    # TEST
    import transport.gate
    transport.gate.init(['tcp',])
    import userid.propagate
    userid.propagate.SendServers()
    # TEST
    
    
    reactor.run()

if __name__ == '__main__':
    main()
