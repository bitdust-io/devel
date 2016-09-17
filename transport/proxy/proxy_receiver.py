#!/usr/bin/env python
#proxy_receiver.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (proxy_receiver.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com


"""
.. module:: proxy_receiver
.. role:: red

BitDust proxy_receiver(at_startup) Automat

.. raw:: html

    <i>generated using <a href="http://bitdust.io/visio2python/" target="_blank">visio2python</a> tool</i><br>
    <a href="proxy_receiver.png" target="_blank">
    <img src="proxy_receiver.png" style="max-width:100%;">
    </a>

EVENTS:
    * :red:`inbox-packet`
    * :red:`init`
    * :red:`shutdown`
    * :red:`stop`
"""

#------------------------------------------------------------------------------ 

_Debug = True
_DebugLevel = 14

#------------------------------------------------------------------------------ 

from automats import automat

#------------------------------------------------------------------------------

_ProxyReceiver = None

#------------------------------------------------------------------------------

def A(event=None, arg=None):
    """
    Access method to interact with proxy_receiver machine.
    """
    global _ProxyReceiver
    if _ProxyReceiver is None:
        # set automat name and starting state here
        _ProxyReceiver = ProxyReceiver('proxy_receiver', 'AT_STARTUP')
    if event is not None:
        _ProxyReceiver.automat(event, arg)
    return _ProxyReceiver

#------------------------------------------------------------------------------

class ProxyReceiver(automat.Automat):
    """
    This class implements all the functionality of the ``proxy_receiver()`` state machine.
    """

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of proxy_receiver() machine.
        """

    def state_changed(self, oldstate, newstate, event, arg):
        """
        Method to catch the moment when proxy_receiver() state were changed.
        """

    def state_not_changed(self, curstate, event, arg):
        """
        This method intended to catch the moment when some event was fired in the proxy_receiver()
        but its state was not changed.
        """

    def A(self, event, arg):
        """
        The core proxy_receiver() code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'STOPPED'
                self.doInit(arg)
        #---RECEIVING---
        elif self.state == 'RECEIVING':
            if event == 'stop' :
                self.state = 'STOPPED'
                self.doStopListening(arg)
            elif event == 'shutdown' :
                self.state = 'CLOSED'
                self.doStopListening(arg)
                self.doDestroyMe(arg)
            elif event == 'inbox-packet' :
                self.doProcessInboxPacket(arg)
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass


    def doProcessInboxPacket(self, arg):
        """
        Action method.
        """

    def doInit(self, arg):
        """
        Action method.
        """

    def doStopListening(self, arg):
        """
        Action method.
        """

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        automat.objects().pop(self.index)
        global _ProxyReceiver
        del _ProxyReceiver
        _ProxyReceiver = None
        
#------------------------------------------------------------------------------



def main():
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'init')
    reactor.run()

if __name__ == "__main__":
    main()

