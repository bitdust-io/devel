#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: stun

To detect my external IP and PORT I need to contact someone and ask for response.
This is a STUN server and client idea, very simple.

Every user starts own STUN server - he listen on UDP port for incoming datagrams.

Another user use DHT to pick a random peer in the network 
and tries to connect to his STUN server to detect own IP address. 
"""
