

"""
.. module:: stun_server

BitPie.NET stun_server() Automat

EVENTS:
    * :red:`datagram-received`
    * :red:`start`
    * :red:`stop`
"""

import os
import sys

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from lib import bpio
from lib import settings
from lib import automat
from lib import udp

from dht import dht_service

#------------------------------------------------------------------------------
 
_StunServer = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _StunServer
    if _StunServer is None:
        # set automat name and starting state here
        _StunServer = StunServer('stun_server', 'AT_STARTUP', 6)
    if event is not None:
        _StunServer.automat(event, arg)
    return _StunServer


class StunServer(automat.Automat):
    """
    This class implements all the functionality of the ``stun_server()`` state machine.
    """

    def init(self):
        self.listen_port = None
        
    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state is 'AT_STARTUP':
            if event == 'start' :
                self.state = 'LISTEN'
                self.doInit(arg)
        #---LISTEN---
        elif self.state is 'LISTEN':
            if event == 'stop' :
                self.state = 'STOPPED'
                self.doStop(arg)
            elif event == 'datagram-received' and self.isSTUN(arg) :
                self.doSendYourIPPort(arg)
        #---STOPPED---
        elif self.state is 'STOPPED':
            if event == 'start' :
                self.state = 'LISTEN'
                self.doInit(arg)

    def isSTUN(self, arg):
        """
        Condition method.
        """
        try:
            datagram, address = arg
            command, payload = datagram
        except:
            return False
        return command == udp.CMD_STUN

    def doInit(self, arg):
        """
        Action method.
        """
        # udp.add_datagram_receiver_callback(self._datagramReceived)
        self.listen_port = arg
        udp.proto(self.listen_port).add_callback(self._datagramReceived)
        externalPort = bpio._read_data(settings.ExternalUDPPortFilename())
        try:
            externalPort = int(externalPort)
        except:
            externalPort = self.listen_port
        dht_service.set_node_data('stun_port', externalPort)

    def doStop(self, arg):
        """
        Action method.
        """
        udp.proto(self.listen_port).remove_callback(self._datagramReceived)

    def doSendYourIPPort(self, arg):
        """
        Action method.
        """
        try:
            datagram, address = arg
            command, payload = datagram
        except:
            return False
        youipport = '%s:%d' % (address[0], address[1])
        udp.send_command(self.listen_port, udp.CMD_MYIPPORT, youipport, address)

    def _datagramReceived(self, datagram, address):
        """
        """
        self.automat('datagram-received', (datagram, address))
        return False
        

def main():
    from twisted.internet import reactor
    bpio.init()
    dht_service.init(4000)
    udp.listen(8882)
    A('start', 8882)
    reactor.run()

if __name__ == '__main__':
    main()
    
    
    
    
