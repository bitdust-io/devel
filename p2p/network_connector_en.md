# Automat network_connector()


## Description:    
![network_connector[1]](http://bitpie.net/bitpie/p2p/network_connector.png)
    
The ``network_connector()`` machine is needed to monitor status of the Internet connection
and start reconnect actions in different parts of software.

In ``CONNECTED`` state it will periodically checks for incoming traffic and decide about
current connection status.

Two key methods will manage the reconnection process:
    
    doSetUp()
    doSetDown()
    
If some network interfaces is active but software is still disconnected 
it will try to ping "http://bitpie.net" to know what is going on.


## Events:
    * :red:`all-network-transports-disabled`
    * :red:`all-network-transports-ready`
    * :red:`connection-done`
    * :red:`gateway-is-not-started`
    * :red:`got-network-info`
    * :red:`init`
    * :red:`internet-failed`
    * :red:`internet-success`
    * :red:`network-down`
    * :red:`network-transport-state-changed`
    * :red:`network-up`
    * :red:`reconnect`
    * :red:`timer-1hour`
    * :red:`timer-5sec`
    * :red:`upnp-done`