#!/usr/bin/env python
# constants.py
#
# Copyright (C) 2007-2008 Francois Aucamp, Meraka Institute, CSIR
# See AUTHORS for all authors and contact information.
#
# License: GNU Lesser General Public License, version 3 or later; see COPYING
#          included in this archive for details.
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net
"""
This module defines the charaterizing constants of the Kademlia network.

C{checkRefreshInterval} and C{udpDatagramMaxSize} are implementation-
specific constants, and do not affect general Kademlia operation.
"""

######### KADEMLIA CONSTANTS ###########

#: Small number Representing the degree of parallelism in network calls
alpha = 4

#: Maximum number of contacts stored in a bucket; this should be an even number
k = 4

#: Timeout for network operations (in seconds)
rpcTimeout = 10

# Delay between iterations of iterative node lookups (for loose parallelism)  (in seconds)
iterativeLookupDelay = rpcTimeout/2

#: If a k-bucket has not been used for this amount of time, refresh it (in seconds)
refreshTimeout = 600  # 10 min
#: The interval at which nodes replicate (republish/refresh) data they are holding
replicateInterval = refreshTimeout
# The time it takes for data to expire in the network; the original publisher of the data
# will also republish the data at this time if it is still valid
dataExpireTimeout = 86400  # 24 hours
# Default value for all records to be expired
dataExpireSecondsDefaut = 60*60*12  # 12 hours

######## IMPLEMENTATION-SPECIFIC CONSTANTS ###########

#: The interval in which the node should check its whether any buckets need refreshing,
#: or whether any data needs to be republished (in seconds)
checkRefreshInterval = refreshTimeout/5

#: Max size of a single UDP datagram, in bytes. If a message is larger than this, it will
#: be spread accross several UDP packets.
udpDatagramMaxSize = 8192  # 8 KB
