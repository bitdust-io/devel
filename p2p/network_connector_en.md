# Automat network_connector()


![network_connector[1]](http://bitdust.io/bitdust/p2p/network_connector.png)


## Description:    
    
The __network_connector()__ machine is needed to monitor status of the Internet connection
and start reconnect actions in different parts of software.

In __CONNECTED__ state it will periodically checks for incoming traffic and decide about
current connection status.

Two key methods will manage the reconnection process and start/stop some key network services:
    
    * doSetUp() 
    * doSetDown()
    
If some network interfaces is active but software is still disconnected 
it will try to ping "http://bitdust.io" to know what is going on.


## Events:
    * all-network-transports-disabled
    * all-network-transports-ready
    * connection-done
    * gateway-is-not-started
    * got-network-info
    * init
    * internet-failed
    * internet-success
    * network-down
    * network-transport-state-changed
    * network-up
    * reconnect
    * timer-1hour
    * timer-5sec
    * upnp-done