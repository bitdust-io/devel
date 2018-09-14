#!/usr/bin/env python
# node.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (node.py) is part of BitDust Software.
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
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

from __future__ import absolute_import
from __future__ import print_function
import hashlib
import random
import time

from twisted.internet import defer

from . import constants
from . import routingtable
from . import datastore
from . import protocol
import twisted.internet.reactor
import twisted.internet.threads
from .contact import Contact
from six.moves import range
from io import open


def rpcmethod(func):
    """
    Decorator to expose Node methods as remote procedure calls.

    Apply this decorator to methods in the Node class (or a subclass) in
    order to make them remotely callable via the DHT's RPC mechanism.
    """
    func.rpcmethod = True
    return func


class Node(object):
    """
    Local node in the Kademlia network.

    This class represents a single local node in a Kademlia network; in other
    words, this class encapsulates an Entangled-using application's "presence"
    in a Kademlia network.

    In Entangled, all interactions with the Kademlia network by a client
    application is performed via this class (or a subclass).
    """

    def __init__(self, udpPort=4000, dataStore=None, routingTable=None, networkProtocol=None):
        """
        @param dataStore: The data store to use. This must be class inheriting
                          from the C{DataStore} interface (or providing the
                          same API). How the data store manages its data
                          internally is up to the implementation of that data
                          store.
        @type dataStore: entangled.kademlia.datastore.DataStore
        @param routingTable: The routing table to use. Since there exists some
                             ambiguity as to how the routing table should be
                             implemented in Kademlia, a different routing table
                             may be used, as long as the appropriate API is
                             exposed.
        @type routingTable: entangled.kademlia.routingtable.RoutingTable
        @param networkProtocol: The network protocol to use. This can be
                                overridden from the default to (for example)
                                change the format of the physical RPC messages
                                being transmitted.
        @type networkProtocol: entangled.kademlia.protocol.KademliaProtocol
        """
        self.id = self._generateID()
        self.port = udpPort
        self.listener = None
        self.refresher = None
        # This will contain a deferred created when joining the network, to enable publishing/retrieving information from
        # the DHT as soon as the node is part of the network (add callbacks to this deferred if scheduling such operations
        # before the node has finished joining the network)
        self._joinDeferred = None
        # Create k-buckets (for storing contacts)
        if routingTable is None:
            self._routingTable = routingtable.OptimizedTreeRoutingTable(self.id)

        # Initialize this node's network access mechanisms
        if networkProtocol is None:
            self._protocol = protocol.KademliaProtocol(self)
        else:
            self._protocol = networkProtocol(self)
        # Initialize the data storage mechanism used by this node
        if dataStore is None:
            self._dataStore = datastore.DictDataStore()
        else:
            self._dataStore = dataStore
            # Try to restore the node's state...
            if 'nodeState' in self._dataStore:
                state = self._dataStore['nodeState']
                self.id = state['id']
                for contactTriple in state['closestNodes']:
                    contact = Contact(contactTriple[0], contactTriple[1], contactTriple[2], self._protocol)
                    self._routingTable.addContact(contact)
        self._counter = None

    def __del__(self):
        self._persistState()

    def listenUDP(self):
        self.listener = twisted.internet.reactor.listenUDP(self.port, self._protocol)  # IGNORE:E1101

    def joinNetwork(self, knownNodeAddresses=None):
        """
        Causes the Node to join the Kademlia network; normally, this should be
        called before any other DHT operations.

        @param knownNodeAddresses: A sequence of tuples containing IP address
                                   information for existing nodes on the
                                   Kademlia network, in the format:
                                   C{(<ip address>, (udp port>)}
        @type knownNodeAddresses: tuple
        """
        if self._counter:
            self._counter('joinNetwork')
        # Prepare the underlying Kademlia protocol
        # Create temporary contact information for the list of addresses of known nodes
        if knownNodeAddresses is not None:
            bootstrapContacts = []
            for address, port in knownNodeAddresses:
                contact = Contact(self._generateID(), address, port, self._protocol)
                bootstrapContacts.append(contact)
        else:
            bootstrapContacts = None
        # Initiate the Kademlia joining sequence - perform a search for this node's own ID
        self._joinDeferred = self._iterativeFind(self.id, bootstrapContacts)
#        #TODO: Refresh all k-buckets further away than this node's closest neighbour
#        def getBucketAfterNeighbour(*args):
#            for i in range(160):
#                if len(self._buckets[i]) > 0:
#                    return i+1
#            return 160
#        df.addCallback(getBucketAfterNeighbour)
#        df.addCallback(self._refreshKBuckets)
        #protocol.reactor.callLater(10, self.printContacts)
        self._joinDeferred.addCallback(self._persistState)
        self._joinDeferred.addErrback(self._joinNetworkFailed)
        # Start refreshing k-buckets periodically, if necessary
        self.refresher = twisted.internet.reactor.callLater(constants.checkRefreshInterval, self._refreshNode)  # IGNORE:E1101
        # twisted.internet.reactor.run()

    def printContacts(self):
        print('\n\nNODE CONTACTS\n===============')
        for i in range(len(self._routingTable._buckets)):
            for contact in self._routingTable._buckets[i]._contacts:
                print(contact)
        print('==================================')
        #twisted.internet.reactor.callLater(10, self.printContacts)

    def iterativeStore(self, key, value, originalPublisherID=None,
                       age=0, expireSeconds=constants.dataExpireSecondsDefaut, **kwargs):
        """
        The Kademlia store operation.

        Call this to store/republish data in the DHT.

        @param key: The hashtable key of the data
        @type key: str
        @param value: The actual data (the value associated with C{key})
        @type value: str
        @param originalPublisherID: The node ID of the node that is the
                                    B{original} publisher of the data
        @type originalPublisherID: str
        @param age: The relative age of the data (time in seconds since it was
                    originally published). Note that the original publish time
                    isn't actually given, to compensate for clock skew between
                    different nodes.
        @type age: int
        """
        if self._counter:
            self._counter('iterativeStore')
        if originalPublisherID is None:
            originalPublisherID = self.id

        def storeFailed(x):
            pass
        # Prepare a callback for doing "STORE" RPC calls

        def executeStoreRPCs(nodes):
            # print '        .....execStoreRPCs called'
            if len(nodes) >= constants.k:
                # If this node itself is closer to the key than the last (furthest) node in the list,
                # we should store the value at ourselves as well
                if self._routingTable.distance(key, self.id) < self._routingTable.distance(key, nodes[-1].id):
                    nodes.pop()
                    self.store(key, value, originalPublisherID=originalPublisherID,
                               age=age, expireSeconds=expireSeconds, **kwargs)
            else:
                self.store(key, value, originalPublisherID=originalPublisherID,
                           age=age, expireSeconds=expireSeconds, **kwargs)
            for contact in nodes:
                d = contact.store(key, value, originalPublisherID, age, expireSeconds, **kwargs)
                d.addErrback(storeFailed)
            return nodes
        # Find k nodes closest to the key...
        df = self.iterativeFindNode(key)
        # ...and send them STORE RPCs as soon as they've been found
        df.addCallback(executeStoreRPCs)
        return df

    def iterativeFindNode(self, key):
        """
        The basic Kademlia node lookup operation.

        Call this to find a remote node in the P2P overlay network.

        @param key: the 160-bit key (i.e. the node or value ID) to search for
        @type key: str

        @return: This immediately returns a deferred object, which will return
                 a list of k "closest" contacts (C{kademlia.contact.Contact}
                 objects) to the specified key as soon as the operation is
                 finished.
        @rtype: twisted.internet.defer.Deferred
        """
        return self._iterativeFind(key)

    def iterativeFindValue(self, key):
        """
        The Kademlia search operation (deterministic)

        Call this to retrieve data from the DHT.

        @param key: the 160-bit key (i.e. the value ID) to search for
        @type key: str

        @return: This immediately returns a deferred object, which will return
                 either one of two things:
                     - If the value was found, it will return a Python
                     dictionary containing the searched-for key (the C{key}
                     parameter passed to this method), and its associated
                     value, in the format:
                     C{<str>key: <str>data_value}
                     - If the value was not found, it will return a list of k
                     "closest" contacts (C{kademlia.contact.Contact} objects)
                     to the specified key
        @rtype: twisted.internet.defer.Deferred
        """
        # Prepare a callback for this operation
        outerDf = defer.Deferred()

        def lookupFailed(x):
            print('lookupFailed', x)

        def storeFailed(x):
            print('storeFailed', x)

        def checkResult(result):
            if isinstance(result, dict):
                # We have found the value; now see who was the closest contact without it...
                if 'closestNodeNoValue' in result:
                    # ...and store the key/value pair
                    contact = result['closestNodeNoValue']
                    expireSeconds = constants.dataExpireSecondsDefaut
                    if 'expireSeconds' in result:
                        expireSeconds = result['expireSeconds']
                    print('republish %s with %d' % (result[key], expireSeconds))
                    contact.store(key, result[key], None, 0, expireSeconds).addErrback(storeFailed)
                outerDf.callback(result)
            else:
                # The value wasn't found, but a list of contacts was returned
                # Now, see if we have the value (it might seem wasteful to search on the network
                # first, but it ensures that all values are properly propagated through the
                # network
                if key in self._dataStore:
                    # Ok, we have the value locally, so use that
                    value = self._dataStore[key]
                    expireSeconds = constants.dataExpireSecondsDefaut
                    expireSecondsCall = getattr(self._dataStore, 'expireSeconds')
                    if expireSecondsCall:
                        expireSeconds = expireSecondsCall(key)
                    # Send this value to the closest node without it
                    if len(result) > 0:
                        contact = result[0]
                        print('refresh %s with %d' % (value, expireSeconds))
                        contact.store(key, value, None, 0, expireSeconds).addErrback(storeFailed)
                    outerDf.callback({key: value})
                else:
                    # Ok, value does not exist in DHT at all
                    outerDf.callback(result)

        # Execute the search
        df = self._iterativeFind(key, rpc='findValue')
        df.addCallback(checkResult)
        df.addErrback(lookupFailed)
        return outerDf

    def addContact(self, contact):
        """
        Add/update the given contact; simple wrapper for the same method in
        this object's RoutingTable object.

        @param contact: The contact to add to this node's k-buckets
        @type contact: kademlia.contact.Contact
        """
        if self._counter:
            self._counter('addContact')
        self._routingTable.addContact(contact)

    def removeContact(self, contactID):
        """
        Remove the contact with the specified node ID from this node's table of
        known nodes. This is a simple wrapper for the same method in this
        object's RoutingTable object.

        @param contactID: The node ID of the contact to remove
        @type contactID: str
        """
        if self._counter:
            self._counter('removeContact')
        self._routingTable.removeContact(contactID)

    def findContact(self, contactID):
        """
        Find a entangled.kademlia.contact.Contact object for the specified
        cotact ID.

        @param contactID: The contact ID of the required Contact object
        @type contactID: str

        @return: Contact object of remote node with the specified node ID
        @rtype: twisted.internet.defer.Deferred
        """
        if self._counter:
            self._counter('findContact')
        try:
            contact = self._routingTable.getContact(contactID)
            df = defer.Deferred()
            df.callback(contact)
        except ValueError:
            def parseResults(nodes):
                if contactID in nodes:
                    contact = nodes[nodes.index(contactID)]
                    return contact
                else:
                    return None
            df = self.iterativeFindNode(contactID)
            df.addCallback(parseResults)
        return df

    @rpcmethod
    def ping(self):
        """
        Used to verify contact between two Kademlia nodes.

        @rtype: str
        """
        if self._counter:
            self._counter('rpc_node_ping')
        return 'pong'

    @rpcmethod
    def store(self, key, value, originalPublisherID=None,
              age=0, expireSeconds=constants.dataExpireSecondsDefaut, **kwargs):
        """
        Store the received data in this node's local hash table.

        @param key: The hashtable key of the data
        @type key: str
        @param value: The actual data (the value associated with C{key})
        @type value: str
        @param originalPublisherID: The node ID of the node that is the
                                    B{original} publisher of the data
        @type originalPublisherID: str
        @param age: The relative age of the data (time in seconds since it was
                    originally published). Note that the original publish time
                    isn't actually given, to compensate for clock skew between
                    different nodes.
        @type age: int

        @rtype: str

        @todo: Since the data (value) may be large, passing it around as a buffer
               (which is the case currently) might not be a good idea... will have
               to fix this (perhaps use a stream from the Protocol class?)
        """
        if self._counter:
            self._counter('rpc_node_store')
        # Get the sender's ID (if any)
        if '_rpcNodeID' in kwargs:
            rpcSenderID = kwargs['_rpcNodeID']
        else:
            rpcSenderID = None

        if originalPublisherID is None:
            if rpcSenderID is not None:
                originalPublisherID = rpcSenderID
            else:
                raise TypeError('No publisher specifed, and RPC caller ID not available. Data requires an original publisher.')

        now = int(time.time())
        originallyPublished = now - age
        self._dataStore.setItem(key, value, now, originallyPublished, originalPublisherID, expireSeconds=expireSeconds, **kwargs)
        return 'OK'

    @rpcmethod
    def findNode(self, key, **kwargs):
        """
        Finds a number of known nodes closest to the node/value with the
        specified key.

        @param key: the 160-bit key (i.e. the node or value ID) to search for
        @type key: str

        @return: A list of contact triples closest to the specified key.
                 This method will return C{k} (or C{count}, if specified)
                 contacts if at all possible; it will only return fewer if the
                 node is returning all of the contacts that it knows of.
        @rtype: list
        """
        if self._counter:
            self._counter('rpc_node_findNode')
        # Get the sender's ID (if any)
        if '_rpcNodeID' in kwargs:
            rpcSenderID = kwargs['_rpcNodeID']
        else:
            rpcSenderID = None
        contacts = self._routingTable.findCloseNodes(key, constants.k, rpcSenderID)
        contactTriples = []
        for contact in contacts:
            contactTriples.append((contact.id, contact.address, contact.port))
        return contactTriples

    @rpcmethod
    def findValue(self, key, **kwargs):
        """
        Return the value associated with the specified key if present in this
        node's data, otherwise execute FIND_NODE for the key.

        @param key: The hashtable key of the data to return
        @type key: str

        @return: A dictionary containing the requested key/value pair,
                 or a list of contact triples closest to the requested key.
        @rtype: dict or list
        """
        if self._counter:
            self._counter('rpc_node_findValue')
        if key in self._dataStore:
            exp = None
            expireSecondsCall = getattr(self._dataStore, 'expireSeconds')
            if expireSecondsCall:
                exp = expireSecondsCall(key)
            return {key: self._dataStore[key], 'expireSeconds': exp, }
        else:
            return self.findNode(key, **kwargs)

#    def _distance(self, keyOne, keyTwo):
#        """ Calculate the XOR result between two string variables
#
#        @return: XOR result of two long variables
#        @rtype: long
#        """
#        valKeyOne = long(keyOne.encode('hex'), 16)
#        valKeyTwo = long(keyTwo.encode('hex'), 16)
#        return valKeyOne ^ valKeyTwo

    def _generateID(self):
        """
        Generates a 160-bit pseudo-random identifier.

        @return: A globally unique 160-bit pseudo-random identifier
        @rtype: str
        """
        hash = hashlib.sha1()
        hash.update(str(random.getrandbits(255)))
        return hash.digest()

    def _iterativeFind(self, key, startupShortlist=None, rpc='findNode'):
        """
        The basic Kademlia iterative lookup operation (for nodes/values)

        This builds a list of k "closest" contacts through iterative use of
        the "FIND_NODE" RPC, or if C{findValue} is set to C{True}, using the
        "FIND_VALUE" RPC, in which case the value (if found) may be returned
        instead of a list of contacts

        @param key: the 160-bit key (i.e. the node or value ID) to search for
        @type key: str
        @param startupShortlist: A list of contacts to use as the starting
                                 shortlist for this search; this is normally
                                 only used when the node joins the network
        @type startupShortlist: list
        @param rpc: The name of the RPC to issue to remote nodes during the
                    Kademlia lookup operation (e.g. this sets whether this
                    algorithm should search for a data value (if
                    rpc='findValue') or not. It can thus be used to perform
                    other operations that piggy-back on the basic Kademlia
                    lookup operation (Entangled's "delete" RPC, for instance).
        @type rpc: str

        @return: If C{findValue} is C{True}, the algorithm will stop as soon
                 as a data value for C{key} is found, and return a dictionary
                 containing the key and the found value. Otherwise, it will
                 return a list of the k closest nodes to the specified key
        @rtype: twisted.internet.defer.Deferred
        """
        if self._counter:
            self._counter('_iterativeFind')
        if rpc != 'findNode':
            findValue = True
        else:
            findValue = False
        shortlist = []
        if startupShortlist is None:
            shortlist = self._routingTable.findCloseNodes(key, constants.alpha)
            if key != self.id:
                # Update the "last accessed" timestamp for the appropriate k-bucket
                self._routingTable.touchKBucket(key)
            if len(shortlist) == 0:
                # This node doesn't know of any other nodes
                fakeDf = defer.Deferred()
                fakeDf.callback([])
                return fakeDf
        else:
            # This is used during the bootstrap process; node ID's are most probably fake
            shortlist = startupShortlist

        # List of active queries; len() indicates number of active probes
        # - using lists for these variables, because Python doesn't allow binding a new value to a name in an enclosing (non-global) scope
        activeProbes = []
        # List of contact IDs that have already been queried
        alreadyContacted = []
        # Probes that were active during the previous iteration
        # A list of found and known-to-be-active remote nodes
        activeContacts = []
        # This should only contain one entry; the next scheduled iteration call
        pendingIterationCalls = []
        prevClosestNode = [None]
        findValueResult = {}
        slowNodeCount = [0]

        def extendShortlist(responseTuple):
            """ @type responseMsg: kademlia.msgtypes.ResponseMessage """
            # The "raw response" tuple contains the response message, and the originating address info
            responseMsg = responseTuple[0]
            originAddress = responseTuple[1]  # tuple: (ip adress, udp port)
            # Make sure the responding node is valid, and abort the operation if it isn't
            if responseMsg.nodeID in activeContacts or responseMsg.nodeID == self.id:
                return responseMsg.nodeID

            # Mark this node as active
            if responseMsg.nodeID in shortlist:
                # Get the contact information from the shortlist...
                aContact = shortlist[shortlist.index(responseMsg.nodeID)]
            else:
                # If it's not in the shortlist; we probably used a fake ID to reach it
                # - reconstruct the contact, using the real node ID this time
                aContact = Contact(responseMsg.nodeID, originAddress[0], originAddress[1], self._protocol)
            activeContacts.append(aContact)
            # This makes sure "bootstrap"-nodes with "fake" IDs don't get queried twice
            if responseMsg.nodeID not in alreadyContacted:
                alreadyContacted.append(responseMsg.nodeID)
            # Now grow extend the (unverified) shortlist with the returned contacts
            result = responseMsg.response
            # TODO: some validation on the result (for guarding against attacks)
            # If we are looking for a value, first see if this result is the value
            # we are looking for before treating it as a list of contact triples
            if findValue and isinstance(result, dict):
                # We have found the value
                findValueResult[key] = result[key]
                if 'expireSeconds' in result:
                    findValueResult['expireSeconds'] = result['expireSeconds']
            else:
                if findValue:
                    # We are looking for a value, and the remote node didn't have it
                    # - mark it as the closest "empty" node, if it is
                    if 'closestNodeNoValue' in findValueResult:
                        if self._routingTable.distance(key, responseMsg.nodeID) < self._routingTable.distance(key, activeContacts[0].id):
                            findValueResult['closestNodeNoValue'] = aContact
                    else:
                        findValueResult['closestNodeNoValue'] = aContact
                for contactTriple in result:
                    try:
                        testContact = Contact(contactTriple[0], contactTriple[1], contactTriple[2], self._protocol)
                    except:
                        continue
                    if testContact not in shortlist:
                        shortlist.append(testContact)
            return responseMsg.nodeID

        def removeFromShortlist(failure):
            """ @type failure: twisted.python.failure.Failure """
            failure.trap(protocol.TimeoutError)
            deadContactID = failure.getErrorMessage()
            if deadContactID in shortlist:
                shortlist.remove(deadContactID)
            return deadContactID

        def cancelActiveProbe(contactID):
            activeProbes.pop()
            if len(activeProbes) <= constants.alpha / 2 and len(pendingIterationCalls):
                # Force the iteration
                pendingIterationCalls[0].cancel()
                del pendingIterationCalls[0]
                # print 'forcing iteration ================='
                searchIteration()

        # Send parallel, asynchronous FIND_NODE RPCs to the shortlist of contacts
        def searchIteration():
            # print '==> searchiteration'
            slowNodeCount[0] = len(activeProbes)
            # Sort the discovered active nodes from closest to furthest
            activeContacts.sort(lambda firstContact, secondContact, targetKey=key: cmp(self._routingTable.distance(firstContact.id, targetKey), self._routingTable.distance(secondContact.id, targetKey)))
            # This makes sure a returning probe doesn't force calling this function by mistake
            while len(pendingIterationCalls):
                del pendingIterationCalls[0]
            # See if should continue the search
            if key in findValueResult:
                # print '++++++++++++++ DONE (findValue found) +++++++++++++++\n\n'
                outerDf.callback(findValueResult)
                return
            elif len(activeContacts) and findValue == False:
                if (len(activeContacts) >= constants.k) or (activeContacts[0] == prevClosestNode[0] and len(activeProbes) == slowNodeCount[0]):
                    # TODO: Re-send the FIND_NODEs to all of the k closest nodes not already queried
                    # Ok, we're done; either we have accumulated k active contacts or no improvement in closestNode has been noted
                    # if len(activeContacts) >= constants.k:
                    #    print '++++++++++++++ DONE (test for k active contacts) +++++++++++++++\n\n'
                    # else:
                    #    print '++++++++++++++ DONE (test for closest node) +++++++++++++++\n\n'
                    outerDf.callback(activeContacts)
                    return
            # The search continues...
            if len(activeContacts):
                prevClosestNode[0] = activeContacts[0]
            contactedNow = 0
            shortlist.sort(lambda firstContact, secondContact, targetKey=key: cmp(self._routingTable.distance(firstContact.id, targetKey), self._routingTable.distance(secondContact.id, targetKey)))
            # Store the current shortList length before contacting other nodes
            prevShortlistLength = len(shortlist)
            for contact in shortlist:
                if contact.id not in alreadyContacted:
                    activeProbes.append(contact.id)
                    rpcMethod = getattr(contact, rpc)
                    df = rpcMethod(key, rawResponse=True)
                    df.addCallback(extendShortlist)
                    df.addErrback(removeFromShortlist)
                    df.addCallback(cancelActiveProbe)
                    alreadyContacted.append(contact.id)
                    contactedNow += 1
                if contactedNow == constants.alpha:
                    break
            if len(activeProbes) > slowNodeCount[0] \
                    or (len(shortlist) < constants.k and len(activeContacts) < len(shortlist) and len(activeProbes) > 0):
                # print '----------- scheduling next call -------------'
                # Schedule the next iteration if there are any active calls (Kademlia uses loose parallelism)
                call = twisted.internet.reactor.callLater(constants.iterativeLookupDelay, searchIteration)  # IGNORE:E1101
                pendingIterationCalls.append(call)
            # Check for a quick contact response that made an update to the shortList
            elif prevShortlistLength < len(shortlist):
                # Ensure that the closest contacts are taken from the updated shortList
                searchIteration()
            else:
                # print '++++++++++++++ DONE (logically) +++++++++++++\n\n'
                # If no probes were sent, there will not be any improvement, so we're done
                outerDf.callback(activeContacts)

        outerDf = defer.Deferred()
        # Start the iterations
        searchIteration()
        return outerDf

#    def _kbucketIndex(self, key):
#        """ Calculate the index of the k-bucket which is responsible for the
#        specified key
#
#        @param key: The key for which to find the appropriate k-bucket index
#        @type key: str
#
#        @return: The index of the k-bucket responsible for the specified key
#        @rtype: int
#        """
#        distance = self._distance(self.id, key)
#        bucketIndex = int(math.log(distance, 2))
#        return bucketIndex

#    def _randomIDInBucketRange(self, bucketIndex):
#        """ Returns a random ID in the specified k-bucket's range
#
#        @param bucketIndex: The index of the k-bucket to use
#        @type bucketIndex: int
#        """
#        def makeIDString(distance):
#            id = hex(distance)[2:]
#            if id[-1] == 'L':
#                id = id[:-1]
#            if len(id) % 2 != 0:
#                id = '0' + id
#            id = id.decode('hex')
#            id = (20 - len(id))*'\x00' + id
#            return id
#        min = math.pow(2, bucketIndex)
#        max = math.pow(2, bucketIndex+1)
#        distance = random.randrange(min, max)
#        distanceStr = makeIDString(distance)
#        randomID = makeIDString(self._distance(distanceStr, self.id))
#        return randomID

#    def _refreshKBuckets(self, startIndex=0, force=False):
#        """ Refreshes all k-buckets that need refreshing, starting at the
#        k-bucket with the specified index
#
#        @param startIndex: The index of the bucket to start refreshing at;
#                           this bucket and those further away from it will
#                           be refreshed. For example, when joining the
#                           network, this node will set this to the index of
#                           the bucket after the one containing it's closest
#                           neighbour.
#        @type startIndex: index
#        @param force: If this is C{True}, all buckets (in the specified range)
#                      will be refreshed, regardless of the time they were last
#                      accessed.
#        @type force: bool
#        """
#        #print '_refreshKbuckets called with index:',startIndex
#        bucketIndex = []
#        bucketIndex.append(startIndex + 1)
#        outerDf = defer.Deferred()
#        def refreshNextKBucket(dfResult=None):
#            #print '  refreshNexKbucket called; bucketindex is', bucketIndex[0]
#            bucketIndex[0] += 1
#            while bucketIndex[0] < 160:
#                if force or (int(time.time()) - self._buckets[bucketIndex[0]].lastAccessed >= constants.refreshTimeout):
#                    searchID = self._randomIDInBucketRange(bucketIndex[0])
#                    self._buckets[bucketIndex[0]].lastAccessed = int(time.time())
#                    #print '  refreshing bucket',bucketIndex[0]
#                    df = self.iterativeFindNode(searchID)
#                    df.addCallback(refreshNextKBucket)
#                    return
#                else:
#                    bucketIndex[0] += 1
#            # If this is reached, we have refreshed all the buckets
#            #print '  all buckets refreshed; initiating outer deferred callback'
#            outerDf.callback(None)
#        #print '_refreshKbuckets starting cycle'
#        refreshNextKBucket()
#        #print '_refreshKbuckets returning'
#        return outerDf

    def _persistState(self, *args):
        state = {'id': self.id,
                 'closestNodes': self.findNode(self.id)}
        now = int(time.time())
        self._dataStore.setItem('nodeState', state, now, now, self.id)

    def _joinNetworkFailed(self, err):
        print('failed joining DHT network')
        print(err)

    def _refreshNode(self):
        """
        Periodically called to perform k-bucket refreshes and data
        replication/republishing as necessary.
        """
        # print 'refreshNode called'
        if self._counter:
            self._counter('_refreshNode')
        df = self._refreshRoutingTable()
        df.addCallback(self._republishData)
        df.addCallback(self._scheduleNextNodeRefresh)

    def _refreshRoutingTable(self):
        nodeIDs = self._routingTable.getRefreshList(0, False)
        outerDf = defer.Deferred()

        def searchForNextNodeID(dfResult=None):
            if len(nodeIDs) > 0:
                searchID = nodeIDs.pop()
                df = self.iterativeFindNode(searchID)
                df.addCallback(searchForNextNodeID)
            else:
                # If this is reached, we have finished refreshing the routing table
                outerDf.callback(None)
        # Start the refreshing cycle
        searchForNextNodeID()
        return outerDf

    def _republishData(self, *args):
        # print '---republishData() called'
        df = twisted.internet.threads.deferToThread(self._threadedRepublishData)
        return df

    def _scheduleNextNodeRefresh(self, *args):
        # print '==== sheduling next refresh'
        self.refresher = twisted.internet.reactor.callLater(constants.checkRefreshInterval, self._refreshNode)

    def _threadedRepublishData(self, *args):
        """
        Republishes and expires any stored data (i.e. stored C{(key, value
        pairs)} that need to be republished/expired.

        This method should run in a deferred thread
        """
        # print '== republishData called, node:',ord(self.id[0])
        expiredKeys = []
        for key in self._dataStore:
            # Filter internal variables stored in the datastore
            if key == 'nodeState':
                continue
            now = int(time.time())
            itemData = self._dataStore.getItem(key)
            originallyPublished = itemData['originallyPublished']
            originalPublisherID = itemData['originalPublisherID']
            lastPublished = itemData['lastPublished']
            expireSeconds = itemData['expireSeconds']
            age = now - originallyPublished
            # originalPublisherID = self._dataStore.originalPublisherID(key)
            # age = now - self._dataStore.originalPublishTime(key)
            # expireSeconds = self._dataStore.expireSeconds(key)
            # print '  node:',ord(self.id[0]),'key:',ord(key[0]),'orig publishing time:',self._dataStore.originalPublishTime(key),'now:',now,'age:',age,'lastPublished age:',now - self._dataStore.lastPublished(key),'original pubID:', ord(originalPublisherID[0])
            if originalPublisherID == self.id:
                # This node is the original publisher; it has to republish
                # the data before it expires (24 hours in basic Kademlia)
                if age >= constants.dataExpireTimeout:
                    # print '    REPUBLISHING key:', key
                    twisted.internet.reactor.callFromThread(
                        self.iterativeStore,
                        key=key,
                        value=self._dataStore[key],
                        expireSeconds=expireSeconds,
                    )
            else:
                # This node needs to replicate the data at set intervals,
                # until it expires, without changing the metadata associated with it
                # First, check if the data has expired
                if age >= constants.dataExpireTimeout:
                    # This key/value pair has expired (and it has not been republished by the original publishing node
                    # - remove it
                    expiredKeys.append(key)
                elif now - lastPublished >= constants.replicateInterval:
                    # ...data has not yet expired, and we need to replicate it
                    # print '    replicating key:', key,'age:',age
                    twisted.internet.reactor.callFromThread(
                        self.iterativeStore,
                        key=key,
                        value=self._dataStore[key],
                        originalPublisherID=originalPublisherID,
                        age=age,
                        expireSeconds=expireSeconds,
                    )
        for key in expiredKeys:
            # print '    expiring key:', key
            del self._dataStore[key]
        # print 'done with threadedDataRefresh()'


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage:\n%s UDP_PORT  [KNOWN_NODE_IP  KNOWN_NODE_PORT]' % sys.argv[0])
        print('or:\n%s UDP_PORT  [FILE_WITH_KNOWN_NODES]' % sys.argv[0])
        print('\nIf a file is specified, it should containg one IP address and UDP port\nper line, seperated by a space.')
        sys.exit(1)
    try:
        usePort = int(sys.argv[1])
    except ValueError:
        print('\nUDP_PORT must be an integer value.\n')
        print('Usage:\n%s UDP_PORT  [KNOWN_NODE_IP  KNOWN_NODE_PORT]' % sys.argv[0])
        print('or:\n%s UDP_PORT  [FILE_WITH_KNOWN_NODES]' % sys.argv[0])
        print('\nIf a file is specified, it should contain one IP address and UDP port\nper line, seperated by a space.')
        sys.exit(1)

    if len(sys.argv) == 4:
        knownNodes = [(sys.argv[2], int(sys.argv[3]))]
    elif len(sys.argv) == 3:
        knownNodes = []
        f = open(sys.argv[2], 'r')
        lines = f.readlines()
        f.close()
        for line in lines:
            ipAddress, udpPort = line.split()
            knownNodes.append((ipAddress, int(udpPort)))
    else:
        knownNodes = None

    node = Node(udpPort=usePort)
    node.joinNetwork(knownNodes)
    twisted.internet.reactor.run()
