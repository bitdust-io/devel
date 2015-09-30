#!/usr/bin/python
#known_servers.py
#
# <<<COPYRIGHT>>>
#
#
#

def by_host():
    """
    Here is a well known identity servers to support the network.
    Values are ``Web port`` and ``TCP port`` numbers.
    Keys are domain names or global IP address of the server.
    """
    return {
        'p2p-machines.net' :        (80, 6661), # 37.18.255.32
        'p2p-id.ru':                (80, 6661), # 37.18.255.33
        'veselin-p2p.ru':           (80, 6661), # 37.18.255.34
        'bitdust.io':               (8084, 6661),
        }
