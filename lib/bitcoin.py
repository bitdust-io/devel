#!/usr/bin/python
#bitcoin.py
#
# <<<COPYRIGHT>>>
#
#
#

"""
.. module:: bitcoin

A small interface between client code and BitCoind wallet using bitcoinrpc.
"""

import os
import sys

try:
    import bitcoinrpc
    _API_is_installed = True 
except:
    _API_is_installed = False 

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in bitcoin.py')
from twisted.internet.defer import Deferred, succeed

import io
import misc

#------------------------------------------------------------------------------ 

_Connection = None
_Accounts = {}
_Balance = None

#------------------------------------------------------------------------------ 

def installed():
    """
    If bitcoinrpc import were failed this is False.
    """
    return _API_is_installed

def init(username, password, host, port='8332', local=False, configfile=os.path.expanduser('~/.bitcoin/bitcoin.conf')):
    """
    Check bitcoinrpc is installed and create connection to BitCoin server - local or remote
    """
    if not installed():
        io.log(4, 'bitcoin.init WARNING module bitcoin-python is not installed, skip.')
        return
    io.log(4, 'bitcoin.init')
    global _Connection
    if _Connection is None:
        try:
            if local:
                if os.path.isfile(configfile):
                    io.log(4, 'bitcoin.init calling connect_to_local, config file is %s ' % configfile)
                    _Connection = bitcoinrpc.connect_to_local(configfile)
                else:
                    io.log(4, 'bitcoin.init ERROR config file %s not exist' % configfile)
            else:
                io.log(4, 'bitcoin.init calling connect_to_remote, args: %s' % str((username, password, host, port)))
                _Connection = bitcoinrpc.connect_to_remote(username, password, host, port)
        except Exception, e:
            io.log(4, 'bitcoin.init ERROR initializing connection: %s' % str(e))
            return
    io.log(4, 'bitcoin.init connection: %s' % str(_Connection))
    # update()

def shutdown():
    """
    Shutdown connection with BitCoin server
    """
    if not installed():
        io.log(4, 'bitcoin.shutdown WARNING module bitcoin-python is not installed, skip.')
        return
    io.log(4, 'bitcoin.shutdown')
    global _Connection
    if _Connection:
        del _Connection
    _Connection = None

def connection():
    """
    Return connection object to access XMLRPC interface with BitCoin server
    """
    if not installed():
        io.log(4, 'bitcoin.connection WARNING module bitcoin-python is not installed, skip.')
        raise Exception, 'module bitcoinrpc is not installed'
    global _Connection
    if _Connection is None:
        io.log(4, 'bitcoin.connection WARNING connection is not initialized, skip.')
        raise Exception, 'connection is not initialized'
    return _Connection

def update(callback=None):
    """
    Request current account balance from BitCoin server
    """
    global _Connection
    if _Connection is None:
        io.log(4, 'bitcoin.update WARNING connection is not initialized, skip.')
        if callback:
            callback(None)            
        return
    def go():
        global _Accounts
        global _Balance
        try:
            info = connection().getinfo() # listaccounts(as_dict=True)
            _Balance = float(info.balance) # long(round(float(info.balance)*1e8))
            io.log(6, 'bitcoin.update ' + str(_Balance))
        except Exception, e:
            io.log(6, 'bitcoin.update ERROR connection to RPC server: ' + str(e))
            _Balance = None
        if callback:
            reactor.callFromThread(callback, _Balance)
    reactor.callInThread(go)
    
def accounts():
    """
    Return a list of user's known BitCoin accounts
    """
    global _Accounts
    return _Accounts

def balance():
    """
    Return user's known BitCoin balance
    """
    if not installed():
        return 'not available'
    global _Balance
    if _Balance is None:
        return 'disconnected'
    try:
        return '%s BTC' % misc.float2str(_Balance)
    except:
        return 'error'

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    io.init()
    io.SetDebug(12)
    import sys
    def _x():
        io.log(4, 'balance is: ' + str(balance()))
        reactor.stop()
    reactor.callLater(0, init, sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    reactor.callLater(3, update, _x)
    reactor.run()
    
    
