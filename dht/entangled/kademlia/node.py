#!/usr/bin/env python
# node.py
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

from __future__ import absolute_import
from __future__ import print_function
import six
from six.moves import range
from io import open

import hashlib
import json
import random
import time
import traceback

from twisted.internet import defer
import twisted.internet.reactor
import twisted.internet.threads

from . import constants  # @UnresolvedImport
from . import routingtable  # @UnresolvedImport
from . import datastore  # @UnresolvedImport
from . import protocol  # @UnresolvedImport
from . import encoding  # @UnresolvedImport
from .contact import Contact, LayeredContact  # @UnresolvedImport

_Debug = False


def rpcmethod(func):
    """
    Decorator to expose Node methods as remote procedure calls.

    Apply this decorator to methods in the Node class (or a subclass) in
    order to make them remotely callable via the DHT's RPC mechanism.
    """
    func.rpcmethod = True
    return func


def storeSuccess(ok, key):
    try:
        if isinstance(ok, six.binary_type):
            try:
                ok = ok.decode()
            except:
                ok = ok.decode(errors='ignore')
        ok = str(ok)
    except:
        ok = 'Unknown Error'
    if _Debug:
        print('[DHT NODE]    storeSuccess', key, ok)
    return ok


def getErrorMessage(x):
    try:
        errmsg = x.value.subFailure.getErrorMessage()
    except:
        try:
            errmsg = x.getErrorMessage()
        except:
            try:
                errmsg = x.value
            except:
                try:
                    errmsg = str(x)
                except:
                    errmsg = 'Unknown Error'
    if isinstance(errmsg, six.binary_type):
        try:
            errmsg = errmsg.decode()
        except:
            errmsg = errmsg.decode(errors='ignore')
    return errmsg


def storeFailed(x, key):
    errmsg = getErrorMessage(x)
    if _Debug:
        print('[DHT NODE]    storeFailed', key, errmsg, x)
    return errmsg


def findNodeFailed(x):
    errmsg = getErrorMessage(x)
    if _Debug:
        print('[DHT NODE]    findNodeFailed', errmsg, x)
    return errmsg


def lookupFailed(x):
    errmsg = getErrorMessage(x)
    if _Debug:
        print('[DHT NODE]    lookupFailed', errmsg, x)
    return errmsg


class Node(object):
    """
    Local node in the Kademlia network.

    This class represents a single local node in a Kademlia network; in other
    words, this class encapsulates an Entangled-using application's "presence"
    in a Kademlia network.

    In Entangled, all interactions with the Kademlia network by a client
    application is performed via this class (or a subclass).
    """
    def __init__(self, udpPort=4000, dataStore=None, routingTable=None, networkProtocol=None, **kwargs):
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
        self.id = kwargs.get('id')
        if not self.id:
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
            self._routingTable = routingtable.TreeRoutingTable(self.id)
        else:
            self._routingTable = routingTable

        # Initialize this node's network access mechanisms
        if networkProtocol is None:
            self._protocol = protocol.KademliaProtocol(self)
        else:
            self._protocol = networkProtocol(self)
        # Initialize the data storage mechanism used by this node
        if dataStore is None:
            self._dataStore = datastore.DictDataStore()  # in memory only
        else:
            self._dataStore = dataStore
            # Try to restore the node's state...

            h = hashlib.sha1()
            h.update(b'nodeState')
            nodeStateKey = h.hexdigest()

            if nodeStateKey in self._dataStore:
                json_state = self._dataStore[nodeStateKey]
                state = json.loads(json_state)
                self.id = state['id']
                for contactTriple in state['closestNodes']:
                    contact = Contact(encoding.to_text(contactTriple[0]), contactTriple[1], contactTriple[2], self._protocol)
                    self._routingTable.addContact(contact)
                if _Debug:
                    print('[DHT NODE]    found "nodeState" key in local db and added %d contacts to routing table' % len(state['closestNodes']))
        self._counter = None

    def __del__(self):
        self._persistState()

    def listenUDP(self):
        self.listener = twisted.internet.reactor.listenUDP(self.port, self._protocol)  # IGNORE:E1101   @UndefinedVariable

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
        # if self._counter:
        #     self._counter('joinNetwork')
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
        self.refresher = twisted.internet.reactor.callLater(constants.checkRefreshInterval, self._refreshNode)  # IGNORE:E1101  @UndefinedVariable
        # twisted.internet.reactor.run()
        return self._joinDeferred

    def printContacts(self):
        if _Debug:
            print('\n\nNODE CONTACTS\n===============')
        for i in range(len(self._routingTable._buckets)):
            for contact in self._routingTable._buckets[i]._contacts:
                if _Debug:
                    print(contact)
        if _Debug:
            print('==================================')
        #twisted.internet.reactor.callLater(10, self.printContacts)

    def iterativeStore(self, key, value, originalPublisherID=None, age=0, expireSeconds=constants.dataExpireSecondsDefaut, **kwargs):
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
        # if self._counter:
        #     self._counter('iterativeStore')
        if originalPublisherID is None:
            originalPublisherID = self.id
        collect_results = kwargs.pop('collect_results', False)
        ret = defer.Deferred()

        # Prepare a callback for doing "STORE" RPC calls

        def storeRPCsCollected(store_results, store_nodes):
            if _Debug:
                print('[DHT NODE]    storeRPCsCollected', store_results, store_nodes)
            ret.callback((
                store_nodes,
                store_results,
            ))
            return None

        def storeRPCsFailed(x):
            try:
                errmsg = x.value.subFailure.getErrorMessage()
            except:
                try:
                    errmsg = x.getErrorMessage()
                except:
                    try:
                        errmsg = x.value
                    except:
                        try:
                            errmsg = str(x)
                        except:
                            errmsg = 'Unknown Error'
            if isinstance(errmsg, six.binary_type):
                try:
                    errmsg = errmsg.decode()
                except:
                    errmsg = errmsg.decode(errors='ignore')
            if _Debug:
                print('[DHT NODE]    storeRPCsFailed', errmsg)
            ret.errback(x)
            return errmsg

        def executeStoreRPCs(nodes):
            l = []
            if len(nodes) >= constants.k:
                # If this node itself is closer to the key than the last (furthest) node in the list,
                # we should store the value at ourselves as well
                if self._routingTable.distance(key, self.id) < self._routingTable.distance(key, nodes[-1].id):
                    nodes.pop()
                    try:
                        ok = self.store(key, value, originalPublisherID=originalPublisherID, age=age, expireSeconds=expireSeconds, **kwargs)
                        l.append(defer.succeed(ok))
                    except Exception as exc:
                        if _Debug:
                            traceback.print_exc()
                        l.append(defer.fail(exc))
            else:
                try:
                    ok = self.store(key, value, originalPublisherID=originalPublisherID, age=age, expireSeconds=expireSeconds, **kwargs)
                    l.append(defer.succeed(ok))
                except Exception as exc:
                    if _Debug:
                        traceback.print_exc()
                    l.append(defer.fail(exc))

            for contact in nodes:
                d = contact.store(key, value, originalPublisherID, age, expireSeconds, **kwargs)
                d.addCallback(storeSuccess, key)
                d.addErrback(storeFailed, key)
                l.append(d)

            if not collect_results:
                return nodes

            dl = defer.DeferredList(l, fireOnOneErrback=True, consumeErrors=True)
            dl.addCallback(storeRPCsCollected, nodes)
            dl.addErrback(storeRPCsFailed)
            return dl

        # Find k nodes closest to the key...
        df = self.iterativeFindNode(key)
        # ...and send them STORE RPCs as soon as they've been found
        df.addCallback(executeStoreRPCs)
        df.addErrback(findNodeFailed)

        if not collect_results:
            return df

        return ret

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

    def iterativeFindValue(self, key, rpc='findValue', refresh_revision=False):
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

        def refreshRevisionSuccess(ok):
            if _Debug:
                print('[DHT NODE]    iterativeFindValue.refreshRevisionSuccess', ok)

        def refreshRevisionFailed(x):
            errmsg = getErrorMessage(x)
            if _Debug:
                print('[DHT NODE]    iterativeFindValue.refreshRevisionFailed', errmsg)
            return errmsg

        def checkResult(result):
            if _Debug:
                print('[DHT NODE]    iterativeFindValue.checkResult key=%s' % key, result)
            if isinstance(result, dict):
                if key in result:
                    latest_revision = 0
                    for v in result['values']:
                        if v[1] > latest_revision:
                            latest_revision = v[1]
                    # We have found the value; now see who was the closest contact without it...
                    if 'closestNodeNoValue' in result:
                        # ...and store the key/value pair
                        contact = result['closestNodeNoValue']
                        expireSeconds = constants.dataExpireSecondsDefaut
                        if 'expireSeconds' in result:
                            expireSeconds = result['expireSeconds']
                        if _Debug:
                            print('[DHT NODE]    republish %s to closest node with %d expire seconds' % (key, expireSeconds))
                        contact.store(key, result[key], None, 0, expireSeconds, revision=latest_revision).addErrback(storeFailed)
                    if refresh_revision:
                        # need to refresh nodes who has old version of that value
                        for v in result['values']:
                            if v[1] < latest_revision:
                                _contact = Contact(encoding.to_text(v[2]), v[3][0], v[3][1], self._protocol)
                                if _Debug:
                                    print('[DHT NODE]    will refresh revision %d on %r' % (latest_revision, _contact))
                                d = _contact.store(key, result[key], None, 0, expireSeconds, revision=latest_revision)
                                d.addCallback(refreshRevisionSuccess)
                                d.addErrback(refreshRevisionFailed)
                    outerDf.callback(result)
                else:
                    # we was looking for value but did not found it
                    # Now, see if we have the value (it might seem wasteful to search on the network
                    # first, but it ensures that all values are properly propagated through the
                    # network
                    if key in self._dataStore:
                        # Ok, we have the value locally, so use that
                        item = self._dataStore.getItem(key)
                        expireSeconds = item.get('expireSeconds', constants.dataExpireSecondsDefaut)
                        # Send this value to the closest node without it
                        if len(result['activeContacts']) > 0:
                            contact = result['activeContacts'][0]
                            if _Debug:
                                print('[DHT NODE]    refresh %s : %r with %d to %r' % (key, item['value'], expireSeconds, contact))
                            contact.store(key, item['value'], None, 0, expireSeconds).addErrback(storeFailed)
                        outerDf.callback({
                            'key': item['value'],
                            'values': [
                                (
                                    item['value'],
                                    item['revision'],
                                    self.id,
                                    (b'127.0.0.1', self.port),
                                ),
                            ],
                            'activeContacts': result['activeContacts'],
                        })
                    else:
                        if _Debug:
                            print('[DHT NODE]    key %s does not exist in DHT' % key)
                        outerDf.callback(result)
            else:
                # The value wasn't found, but a list of contacts was returned
                # Now, see if we have the value (it might seem wasteful to search on the network
                # first, but it ensures that all values are properly propagated through the
                # network
                if key in self._dataStore:
                    # Ok, we have the value locally, so use that
                    item = self._dataStore.getItem(key)
                    expireSeconds = item.get('expireSeconds', constants.dataExpireSecondsDefaut)
                    # Send this value to the closest node without it
                    if len(result) > 0:
                        contact = result[0]
                        if _Debug:
                            print('[DHT NODE]    refresh %s on closest node : %r with %d to %r' % (key, item['value'], expireSeconds, contact))
                        contact.store(key, item['value'], None, 0, expireSeconds).addErrback(storeFailed)
                    ret = {
                        'key': item['value'],
                        'values': [
                            (
                                item['value'],
                                item['revision'],
                                self.id,
                                (b'127.0.0.1', self.port),
                            ),
                        ],
                        'activeContacts': result['activeContacts'],
                    }
                    if _Debug:
                        print('[DHT NODE]    key %s found in my local data store : %r' % (key, ret))
                    outerDf.callback(ret)
                else:
                    if _Debug:
                        print('[DHT NODE]    key %s does not exist in DHT' % key)
                    outerDf.callback(result)

        # Execute the search
        df = self._iterativeFind(key, rpc=rpc)
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
        # if self._counter:
        #     self._counter('addContact')
        self._routingTable.addContact(contact)

    def removeContact(self, contactID):
        """
        Remove the contact with the specified node ID from this node's table of
        known nodes. This is a simple wrapper for the same method in this
        object's RoutingTable object.

        @param contactID: The node ID of the contact to remove
        @type contactID: str
        """
        # if self._counter:
        #     self._counter('removeContact')
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
        # if self._counter:
        #     self._counter('findContact')
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
        # if self._counter:
        #     self._counter('rpc_node_ping')
        return 'pong'

    @rpcmethod
    def store(self, key, value, originalPublisherID=None, age=0, expireSeconds=constants.dataExpireSecondsDefaut, **kwargs):
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
        # if self._counter:
        #     self._counter('rpc_node_store')
        if _Debug:
            print('[DHT NODE]  SINGLE  rpcmethod.store %r' % key)
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
        # if self._counter:
        #     self._counter('rpc_node_findNode')
        if _Debug:
            print('[DHT NODE]  SINGLE rpcmethod.findNode %r' % key)
        # Get the sender's ID (if any)
        if '_rpcNodeID' in kwargs:
            rpcSenderID = kwargs['_rpcNodeID']
        else:
            rpcSenderID = None
        contacts = self._routingTable.findCloseNodes(key, constants.k, rpcSenderID)
        contactTriples = []
        for contact in contacts:
            contactTriples.append((contact.id, encoding.to_text(contact.address), contact.port))
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
        # if self._counter:
        #     self._counter('rpc_node_findValue')
        if _Debug:
            print('[DHT NODE] SINGLE rpcmethod.findValue %r' % key)
        if key in self._dataStore:
            exp = None
            expireSecondsCall = getattr(self._dataStore, 'expireSeconds')
            if expireSecondsCall:
                exp = expireSecondsCall(key)
            originalPublishTimeCall = getattr(self._dataStore, 'originalPublishTime')
            published = None
            if originalPublishTimeCall:
                published = originalPublishTimeCall(key)
            if _Debug:
                print('[DHT NODE]  SINGLE    found key in local dataStore %r' % self._dataStore[key])
            return {
                key: self._dataStore[key],
                'expireSeconds': exp,
                'originallyPublished': published,
            }
        if _Debug:
            print('[DHT NODE] SINGLE     NOT found key in local dataStore')
        return self.findNode(key, **kwargs)

    def _generateID(self):
        """
        Generates a 160-bit pseudo-random identifier.

        @return: A globally unique 160-bit pseudo-random identifier
        @rtype: str
        """
        hsh = hashlib.sha1()
        hsh.update(str(random.getrandbits(255)).encode())
        return hsh.hexdigest()

    def _iterativeFind(self, key, startupShortlist=None, rpc='findNode', deep=False):
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
        if _Debug:
            print('[DHT NODE]  SINGLE _iterativeFind rpc=%r   key=%r  startupShortlist=%r' % (
                rpc,
                key,
                startupShortlist,
            ))
        # if self._counter:
        #     self._counter('_iterativeFind')
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
                if _Debug:
                    print('[DHT NODE]  SINGLE  This node does not know of any other nodes !!!!!')
                # This node doesn't know of any other nodes
                fakeDf = defer.Deferred()
                fakeDf.callback([])
                return fakeDf
        else:
            # This is used during the bootstrap process; node ID's are most probably fake
            shortlist = startupShortlist
        if _Debug:
            print('[DHT NODE]  SINGLE  shortlist=%r' % shortlist)
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
        findValueResult = {
            'values': [],
        }
        slowNodeCount = [0]

        def extendShortlist(responseTuple):
            """ @type responseMsg: kademlia.msgtypes.ResponseMessage """
            # The "raw response" tuple contains the response message, and the originating address info
            responseMsg = responseTuple[0]
            originAddress = responseTuple[1]  # tuple: (ip adress, udp port)
            # Make sure the responding node is valid, and abort the operation if it isn't
            if _Debug:
                print('[DHT NODE]   SINGLE   extendShortlist', (responseMsg.nodeID, type(responseMsg.nodeID)))
            if responseMsg.nodeID in activeContacts or responseMsg.nodeID == self.id:
                if _Debug:
                    if responseMsg.nodeID == self.id:
                        print('[DHT NODE]   SINGLE       response from my own node')
                    else:
                        print('[DHT NODE]   SINGLE       response from active contact')
                return responseMsg.nodeID

            # Mark this node as active
            if responseMsg.nodeID in shortlist:
                # Get the contact information from the shortlist...
                aContact = shortlist[shortlist.index(responseMsg.nodeID)]
            else:
                # If it's not in the shortlist; we probably used a fake ID to reach it
                # - reconstruct the contact, using the real node ID this time
                aContact = Contact(encoding.to_text(responseMsg.nodeID), originAddress[0], originAddress[1], self._protocol)
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
                findValueResult['values'].append((
                    result[key],
                    result.get('revision', 0),
                    responseMsg.nodeID,
                    originAddress,
                ))
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
                        testContact = Contact(encoding.to_text(contactTriple[0]), contactTriple[1], contactTriple[2], self._protocol)
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
                if _Debug:
                    print('[DHT NODE]  SINGLE removing %r' % deadContactID)
                shortlist.remove(deadContactID)
            return deadContactID

        def cancelActiveProbe(contactID):
            activeProbes.pop()
            if len(activeProbes) <= int(constants.alpha/2.0) and len(pendingIterationCalls):
                # Force the iteration
                pendingIterationCalls[0].cancel()
                del pendingIterationCalls[0]
                if _Debug:
                    print('[DHT NODE] SINGLE forcing iteration =================')
                searchIteration()

        # Send parallel, asynchronous FIND_NODE RPCs to the shortlist of contacts
        def searchIteration():
            slowNodeCount[0] = len(activeProbes)
            # Sort the discovered active nodes from closest to furthest
            activeContacts.sort(key=lambda cont: self._routingTable.distance(cont.id, key))
            if _Debug:
                print('[DHT NODE] SINGLE ==> searchiteration %r' % activeContacts)
            # This makes sure a returning probe doesn't force calling this function by mistake
            while len(pendingIterationCalls):
                del pendingIterationCalls[0]
            # See if should continue the search
            if key in findValueResult and not deep:
                if _Debug:
                    print('[DHT NODE] SINGLE ++++++++++++++ DONE (findValue found) +++++++++++++++\n\n')
                findValueResult['activeContacts'] = activeContacts
                outerDf.callback(findValueResult)
                return
            if len(activeContacts) and findValue == False:
                if (len(activeContacts) >= constants.k) or (activeContacts[0] == prevClosestNode[0] and len(activeProbes) == slowNodeCount[0]):
                    # TODO: Re-send the FIND_NODEs to all of the k closest nodes not already queried
                    # Ok, we're done; either we have accumulated k active contacts or no improvement in closestNode has been noted
                    if len(activeContacts) >= constants.k:
                        if _Debug:
                            print('[DHT NODE] SINGLE ++++++++++++++ DONE (test for k active contacts) +++++++++++++++\n\n')
                    else:
                        if _Debug:
                            print('[DHT NODE] SINGLE ++++++++++++++ DONE (test for closest node) +++++++++++++++\n\n')
                    if findValue:
                        findValueResult['activeContacts'] = activeContacts
                        outerDf.callback(findValueResult)
                    else:
                        outerDf.callback(activeContacts)
                    return
            # The search continues...
            if len(activeContacts):
                prevClosestNode[0] = activeContacts[0]
            contactedNow = 0
            activeContacts.sort(key=lambda cont: self._routingTable.distance(cont.id, key))
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
                if _Debug:
                    print('[DHT NODE] SINGLE ----------- scheduling next call -------------')
                # Schedule the next iteration if there are any active calls (Kademlia uses loose parallelism)
                call = twisted.internet.reactor.callLater(constants.iterativeLookupDelay, searchIteration)  # IGNORE:E1101  @UndefinedVariable
                pendingIterationCalls.append(call)
            # Check for a quick contact response that made an update to the shortList
            elif prevShortlistLength < len(shortlist):
                # Ensure that the closest contacts are taken from the updated shortList
                searchIteration()
            else:
                if _Debug:
                    print('[DHT NODE] SINGLE ++++++++++++++ DONE (logically) +++++++++++++\n\n')
                # If no probes were sent, there will not be any improvement, so we're done
                if findValue:
                    findValueResult['activeContacts'] = activeContacts
                    outerDf.callback(findValueResult)
                else:
                    outerDf.callback(activeContacts)

        outerDf = defer.Deferred()
        # Start the iterations
        searchIteration()
        return outerDf

    def _persistState(self, *args):
        state = {
            'id': self.id,
            'closestNodes': self.findNode(self.id),
            'key': 'nodeState',
            'type': 'skip_validation',
        }
        if _Debug:
            print('[DHT NODE]  SINGLE _persistState id=%r state=%r' % (
                self.id,
                state,
            ))
        json_value = json.dumps(state)
        now = int(time.time())

        h = hashlib.sha1()
        h.update(b'nodeState')
        nodeStateKey = h.hexdigest()

        self._dataStore.setItem(nodeStateKey, json_value, now, now, self.id)
        return args

    def _joinNetworkFailed(self, err, **kwargs):
        if _Debug:
            print('[DHT NODE] SINGLE  failed joining DHT network', err)

    def _refreshNode(self):
        """
        Periodically called to perform k-bucket refreshes and data
        replication/republishing as necessary.
        """
        # if self._counter:
        #     self._counter('_refreshNode')
        df = self._refreshRoutingTable()
        df.addCallback(self._republishData)
        df.addCallback(self._scheduleNextNodeRefresh)

    def _refreshRoutingTable(self):
        nodeIDs = self._routingTable.getRefreshList(0, False)
        if _Debug:
            print('[DHT NODE] SINGLE _refreshRoutingTable', nodeIDs)

        outerDf = defer.Deferred()

        def searchFailed(err):
            if _Debug:
                print('[DHT NODE] SINGLE searchFailed', err)

        def searchForNextNodeID(dfResult=None):
            if len(nodeIDs) > 0:
                searchID = nodeIDs.pop()
                df = self.iterativeFindNode(searchID)
                df.addCallback(searchForNextNodeID)
                df.addErrback(searchFailed)
            else:
                # If this is reached, we have finished refreshing the routing table
                outerDf.callback(None)

        # Start the refreshing cycle
        searchForNextNodeID()
        return outerDf

    def _republishData(self, *args):
        df = twisted.internet.threads.deferToThread(self._threadedRepublishData)
        return df

    def _scheduleNextNodeRefresh(self, *args):
        self.refresher = twisted.internet.reactor.callLater(constants.checkRefreshInterval, self._refreshNode)  # @UndefinedVariable

    def _threadedRepublishData(self, *args):
        """
        Republishes and expires any stored data (i.e. stored C{(key, value
        pairs)} that need to be republished/expired.

        This method should run in a deferred thread
        """
        if _Debug:
            print('[DHT NODE]  SINGLE republishData called, node: %r' % self.id)
        expiredKeys = []
        for key in self._dataStore.keys():
            if _Debug:
                print('[DHT NODE]  SINGLE    %r' % key)
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
            if originalPublisherID == self.id:
                # This node is the original publisher; it has to republish
                # the data before it expires (24 hours in basic Kademlia)
                if age >= constants.dataExpireTimeout:
                    twisted.internet.reactor.callFromThread(  # @UndefinedVariable
                        self.iterativeStore,
                        key=key,
                        value=itemData['value'],
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
                    twisted.internet.reactor.callFromThread(  # @UndefinedVariable
                        self.iterativeStore,
                        key=key,
                        value=self._dataStore[key],
                        originalPublisherID=originalPublisherID,
                        age=age,
                        expireSeconds=expireSeconds,
                    )
        for key in expiredKeys:
            del self._dataStore[key]


class MultiLayerNode(Node):
    def __init__(self, udpPort=4000, dataStores=None, routingTables=None, networkProtocol=None, **kwargs):
        self._counter = None
        self.port = udpPort
        self.listener = None
        h = hashlib.sha1()
        h.update(b'nodeState')
        self.nodeStateKey = h.hexdigest()

        self._routingTables = {}
        self._dataStores = {}
        self.layers = {}
        self.refreshers = {}
        self.active_layers = set()
        self.attached_layers = set()

        self.rpc_calls = {}
        self.rpc_responses = {}
        self.packets_in = {}
        self.packets_out = {}
        self.bytes_in = 0
        self.bytes_out = 0

        # This will contain a deferred created when joining the network, to enable publishing/retrieving information from
        # the DHT as soon as the node is part of the network (add callbacks to this deferred if scheduling such operations
        # before the node has finished joining the network)
        self._joinDeferreds = {}

        # Initialize this node's network access mechanisms
        if networkProtocol is None:
            self._protocol = protocol.KademliaMultiLayerProtocol(self)
        else:
            self._protocol = networkProtocol(self)

        if dataStores:
            for layer_id, dataStore in dataStores.items():
                nodeID = None
                if layer_id == 0:
                    nodeID = kwargs.get('id')
                routingTable = None
                if routingTables:
                    routingTable = routingTables.get(layer_id, None)
                self.createLayer(layer_id, dataStore=dataStore, nodeID=nodeID, routingTable=routingTable)

        if not self._dataStores or 0 not in self._dataStores:
            self.createLayer(0, dataStore=datastore.DictDataStore())

        self.active_layers.add(0)
        self.attachLayer(0)

    def createLayer(self, layer_id, dataStore, nodeID=None, routingTable=None):
        if layer_id in self.layers or layer_id in self._dataStores or layer_id in self._routingTables:
            if _Debug:
                print('[DHT NODE]    createLayer : layer %d already exist' % layer_id)
            return False
        self._dataStores[layer_id] = dataStore
        self.layers[layer_id] = nodeID
        loaded = False
        if self.nodeStateKey in self._dataStores[layer_id]:
            json_state = self._dataStores[layer_id][self.nodeStateKey]
            state = json.loads(json_state)
            self.layers[layer_id] = state['id']
            if layer_id not in self._routingTables:
                self._routingTables[layer_id] = routingTable or routingtable.TreeRoutingTable(self.layers[layer_id], layerID=layer_id)
            for contactTriple in state['closestNodes']:
                contact = LayeredContact(encoding.to_text(contactTriple[0]), contactTriple[1], contactTriple[2], self._protocol, layerID=layer_id)
                self._routingTables[layer_id].addContact(contact)
            if _Debug:
                print('[DHT NODE]    createLayer : layer %d : found "nodeState" key in local db and added %d contacts to routing table' % (
                    layer_id,
                    len(state['closestNodes']),
                ))
            loaded = True
        if not self.layers[layer_id]:
            self.layers[layer_id] = self._generateID()
        if layer_id not in self._routingTables:
            self._routingTables[layer_id] = routingTable or routingtable.TreeRoutingTable(self.layers[layer_id], layerID=layer_id)
#         if layer_id != 0 and not loaded and warmUp:
#             loaded = self.warmUpLayer(layer_id)
        if _Debug:
            print('[DHT NODE]    createLayer : layer %d created,  loaded=%r' % (
                layer_id,
                loaded,
            ))
        return True

    def destroyLayer(self, layer_id):
        if layer_id == 0:
            return False
        if layer_id not in self.layers and layer_id not in self._dataStores and layer_id not in self._routingTables:
            if _Debug:
                print('[DHT NODE]    destroyLayer : layer %d not exist' % layer_id)
            return False
        self.detachLayer(layer_id)
        self.active_layers.discard(layer_id)
        self.layers.pop(layer_id, None)
        self._routingTables.pop(layer_id, None)
        self._dataStores.pop(layer_id, None)
        if _Debug:
            print('[DHT NODE]    destroyLayer : layer %d destroyed' % layer_id)
        return True

    def connectingTask(self, layerID=0):
        if layerID not in self._joinDeferreds:
            return None
        return self._joinDeferreds[layerID]

    def joinNetwork(self, knownNodeAddresses=None, layerID=0, attach=False, parallel_calls=None):
        if knownNodeAddresses is not None:
            bootstrapContacts = []
            for address, port in knownNodeAddresses:
                contact = LayeredContact(self._generateID(), address, port, self._protocol, layerID=layerID)
                bootstrapContacts.append(contact)
        else:
            bootstrapContacts = None
        if _Debug:
            print('[DHT NODE]    joinNetwork bootstrapContacts=%r  layerID=%r  attach=%r' % (bootstrapContacts, layerID, attach))
        self.active_layers.add(layerID)
        if attach:
            self.attachLayer(layerID)
        d = self._iterativeFind(
            key=self.layers[layerID],
            startupShortlist=bootstrapContacts,
            layerID=layerID,
            parallel_calls=parallel_calls,
        )
        d.addCallback(self._persistState, layerID=layerID)
        d.addErrback(self._joinNetworkFailed, layerID=layerID)
        self._joinDeferreds[layerID] = d
        if self.refreshers.get(layerID, None) and not self.refreshers[layerID].called:
            self.refreshers[layerID].cancel()
        self.refreshers[layerID] = twisted.internet.reactor.callLater(  # IGNORE:E1101  @UndefinedVariable
            constants.checkRefreshInterval + float(random.randint(0, 15)),
            self._refreshNode,
            layerID=layerID,
        )
        return self._joinDeferreds[layerID]

    def leaveNetwork(self, layerID):
        if not layerID in self.active_layers:
            return False
        if _Debug:
            print('[DHT NODE]    leaveNetwork layerID=%d' % layerID)
        if layerID != 0:
            self.active_layers.discard(layerID)
            self.detachLayer(layerID)
        if self.refreshers.get(layerID, None) and not self.refreshers[layerID].called:
            self.refreshers[layerID].cancel()
        self.refreshers.pop(layerID, None)
        return True

    def attachLayer(self, layerID):
        if _Debug:
            print('[DHT NODE]    attachLayer %d' % layerID)
        self.attached_layers.add(layerID)

    def detachLayer(self, layerID):
        if _Debug:
            print('[DHT NODE]    detachLayer %d' % layerID)
        self.attached_layers.discard(layerID)


#     def warmUpLayer(self, layerID):
#         if layerID == 0:
#             return True
#         if layerID not in self._routingTables:
#             return False
#         json_state = None
#         if self.nodeStateKey in self._dataStores[layerID]:
#             json_state = self._dataStores[layerID][self.nodeStateKey]
#         if not json_state and self.nodeStateKey in self._dataStores[0]:
#             json_state = self._dataStores[0][self.nodeStateKey]
#         if not json_state:
#             return False
#         state = json.loads(json_state)
#         if _Debug:
#             print('[DHT NODE]    warmUpLayer %d   found saved data: %r' % (layerID, state, ))
#         if not state['closestNodes']:
#             return False
#         self.layers[layerID] = state['id']
#         for contactTriple in state['closestNodes']:
#             contact = LayeredContact(encoding.to_text(contactTriple[0]), contactTriple[1], contactTriple[2], self._protocol, layerID=layerID)
#             self._routingTables[layerID].addContact(contact)
#         self.warm_layers.add(layerID)
#         if _Debug:
#             print('[DHT NODE]    warmUpLayer %d : found "nodeState" key in local db of layer 0 and added %d contacts to routing table' % (
#                 layerID, len(state['closestNodes']), ))
#         return True

    def iterativeStore(self, key, value, originalPublisherID=None, age=0, expireSeconds=constants.dataExpireSecondsDefaut, layerID=0, **kwargs):
        if originalPublisherID is None:
            originalPublisherID = self.layers[layerID]
        collect_results = kwargs.pop('collect_results', False)
        parallel_calls = kwargs.pop('parallel_calls', None)
        ret = defer.Deferred()
        if 'layerID' not in kwargs:
            kwargs['layerID'] = layerID

        if _Debug:
            print('[DHT NODE]   iterativeStore layerID=%d  key=%r' % (
                layerID,
                key,
            ))
        # Prepare a callback for doing "STORE" RPC calls

        def storeRPCsCollected(store_results, store_nodes):
            if _Debug:
                print('[DHT NODE]    iterativeStore.storeRPCsCollected', store_results, store_nodes)
            ret.callback((
                store_nodes,
                store_results,
            ))
            return None

        def storeRPCsFailed(x):
            errmsg = storeFailed(x)
            if _Debug:
                print('[DHT NODE]    iterativeStore.storeRPCsFailed', errmsg)
            ret.errback(x)
            return errmsg

        def executeStoreRPCs(nodes):
            l = []
            if len(nodes) >= constants.k:
                # If this node itself is closer to the key than the last (furthest) node in the list,
                # we should store the value at ourselves as well
                if self._routingTables[layerID].distance(key, self.layers[layerID]) < self._routingTables[layerID].distance(key, nodes[-1].id):
                    nodes.pop()
                    try:
                        ok = self.store(key, value, originalPublisherID=originalPublisherID, age=age, expireSeconds=expireSeconds, **kwargs)
                        l.append(defer.succeed(ok))
                    except Exception as exc:
                        if _Debug:
                            traceback.print_exc()
                        l.append(defer.fail(exc))
            else:
                try:
                    ok = self.store(key, value, originalPublisherID=originalPublisherID, age=age, expireSeconds=expireSeconds, **kwargs)
                    l.append(defer.succeed(ok))
                except Exception as exc:
                    if _Debug:
                        traceback.print_exc()
                    l.append(defer.fail(exc))

            for contact in nodes:
                d = contact.store(key, value, originalPublisherID, age, expireSeconds, **kwargs)
                d.addCallback(storeSuccess, key)
                d.addErrback(storeFailed, key)
                l.append(d)

            if not collect_results:
                return nodes

            dl = defer.DeferredList(l, fireOnOneErrback=True, consumeErrors=True)
            dl.addCallback(storeRPCsCollected, nodes)
            dl.addErrback(storeRPCsFailed)
            return dl

        # Find k nodes closest to the key...
        df = self.iterativeFindNode(key, layerID=layerID, parallel_calls=parallel_calls)
        # ...and send them STORE RPCs as soon as they've been found
        df.addCallback(executeStoreRPCs)
        df.addErrback(findNodeFailed)

        if not collect_results:
            return df

        return ret

    def iterativeFindNode(self, key, layerID=0, parallel_calls=None):
        return self._iterativeFind(key, layerID=layerID, parallel_calls=parallel_calls)

    def iterativeDelete(self, key, layerID=0, parallel_calls=None):
        # Delete our own copy of the data
        if key in self._dataStores[layerID]:
            del self._dataStores[layerID][key]
        df = self._iterativeFind(key, rpc='delete', layerID=layerID, parallel_calls=parallel_calls)
        return df

    def iterativeFindValue(self, key, rpc='findValue', refresh_revision=False, layerID=0, parallel_calls=None):
        outerDf = defer.Deferred()

        def storeFailed(x):
            errmsg = getErrorMessage(x)
            if _Debug:
                print('[DHT NODE]    iterativeFindValue.storeFailed', errmsg)
            return errmsg

        def refreshRevisionSuccess(ok):
            if _Debug:
                print('[DHT NODE]    iterativeFindValue.refreshRevisionSuccess', ok)

        def refreshRevisionFailed(x):
            errmsg = getErrorMessage(x)
            if _Debug:
                print('[DHT NODE]    iterativeFindValue.refreshRevisionFailed', errmsg)
            return errmsg

        def checkResult(result):
            if _Debug:
                print('[DHT NODE]    iterativeFindValue.checkResult key=%s' % key, result)
            if isinstance(result, dict):
                if key in result:
                    latest_revision = 0
                    for v in result['values']:
                        if v[1] > latest_revision:
                            latest_revision = v[1]
                    # We have found the value; now see who was the closest contact without it...
                    if 'closestNodeNoValue' in result:
                        # ...and store the key/value pair
                        contact = result['closestNodeNoValue']
                        expireSeconds = constants.dataExpireSecondsDefaut
                        if 'expireSeconds' in result:
                            expireSeconds = result['expireSeconds']
                        if _Debug:
                            print('[DHT NODE]    republish %s to closest node with %d expire seconds' % (key, expireSeconds))
                        contact.store(key, result[key], None, 0, expireSeconds, revision=latest_revision, layerID=layerID).addErrback(storeFailed)
                    if refresh_revision:
                        # need to refresh nodes who has old version of that value
                        for v in result['values']:
                            if v[1] < latest_revision:
                                _contact = LayeredContact(encoding.to_text(v[2]), v[3][0], v[3][1], self._protocol, layerID=layerID)
                                if _Debug:
                                    print('[DHT NODE]    will refresh revision %d on %r' % (latest_revision, _contact))
                                d = _contact.store(key, result[key], None, 0, expireSeconds, revision=latest_revision, layerID=layerID)
                                d.addCallback(refreshRevisionSuccess)
                                d.addErrback(refreshRevisionFailed)
                    outerDf.callback(result)
                else:
                    # we was looking for value but did not found it
                    # Now, see if we have the value (it might seem wasteful to search on the network
                    # first, but it ensures that all values are properly propagated through the
                    # network
                    if key in self._dataStores[layerID]:
                        # Ok, we have the value locally, so use that
                        item = self._dataStores[layerID].getItem(key)
                        expireSeconds = item.get('expireSeconds', constants.dataExpireSecondsDefaut)
                        # Send this value to the closest node without it
                        if len(result['activeContacts']) > 0:
                            contact = result['activeContacts'][0]
                            if _Debug:
                                print('[DHT NODE]    refresh %s : %r with %d to %r' % (key, item['value'], expireSeconds, contact))
                            contact.store(key, item['value'], None, 0, expireSeconds, layerID=layerID).addErrback(storeFailed)
                        outerDf.callback({
                            'key': item['value'],
                            'values': [
                                (
                                    item['value'],
                                    item['revision'],
                                    self.layers[layerID],
                                    (b'127.0.0.1', self.port),
                                ),
                            ],
                            'activeContacts': result['activeContacts'],
                        })
                    else:
                        if _Debug:
                            print('[DHT NODE]    key %s does not exist in DHT' % key)
                        outerDf.callback(result)
            else:
                # The value wasn't found, but a list of contacts was returned
                # Now, see if we have the value (it might seem wasteful to search on the network
                # first, but it ensures that all values are properly propagated through the
                # network
                if key in self._dataStores[layerID]:
                    # Ok, we have the value locally, so use that
                    item = self._dataStores[layerID].getItem(key)
                    expireSeconds = item.get('expireSeconds', constants.dataExpireSecondsDefaut)
                    # Send this value to the closest node without it
                    if len(result) > 0:
                        contact = result[0]
                        if _Debug:
                            print('[DHT NODE]    refresh %s on closest node : %r with %d to %r' % (key, item['value'], expireSeconds, contact))
                        contact.store(key, item['value'], None, 0, expireSeconds, layerID=layerID).addErrback(storeFailed)
                    ret = {
                        'key': item['value'],
                        'values': [
                            (
                                item['value'],
                                item['revision'],
                                self.layers[layerID],
                                (b'127.0.0.1', self.port),
                            ),
                        ],
                        'activeContacts': result['activeContacts'],
                    }
                    if _Debug:
                        print('[DHT NODE]    key %s found in my local data store : %r' % (key, ret))
                    outerDf.callback(ret)
                else:
                    if _Debug:
                        print('[DHT NODE]    key %s does not exist in DHT' % key)
                    outerDf.callback(result)

        # Execute the search
        df = self._iterativeFind(key, rpc=rpc, layerID=layerID, parallel_calls=parallel_calls)
        df.addCallback(checkResult)
        df.addErrback(lookupFailed)
        return outerDf

    def addContact(self, contact, layerID=0):
        self._routingTables[layerID].addContact(contact)

    def removeContact(self, contactID, layerID=0):
        self._routingTables[layerID].removeContact(contactID)

    def findContact(self, contactID, layerID=0, parallel_calls=None):
        try:
            contact = self._routingTables[layerID].getContact(contactID)
            df = defer.Deferred()
            df.callback(contact)
        except ValueError:

            def parseResults(nodes):
                if contactID in nodes:
                    contact = nodes[nodes.index(contactID)]
                    return contact
                else:
                    return None

            df = self.iterativeFindNode(contactID, layerID=layerID, parallel_calls=parallel_calls)
            df.addCallback(parseResults)
        return df

    @rpcmethod
    def store(self, key, value, originalPublisherID=None, age=0, expireSeconds=constants.dataExpireSecondsDefaut, **kwargs):
        if 'layerID' in kwargs:
            layerID = kwargs['layerID']
        else:
            layerID = 0
        if layerID not in self.active_layers:
            if _Debug:
                print('[DHT NODE]    rpcmethod.store %r layerID=%d SKIP because layer is not active' % (
                    key,
                    layerID,
                ))
            raise ValueError('Layer is not active')
        if _Debug:
            print('[DHT NODE]    rpcmethod.store %r layerID=%d' % (
                key,
                layerID,
            ))
        # Get the sender's ID (if any)
        if '_rpcNodeID' in kwargs:
            rpcSenderID = kwargs['_rpcNodeID']
        else:
            rpcSenderID = None
        if originalPublisherID is None:
            if rpcSenderID is not None:
                originalPublisherID = rpcSenderID
            else:
                raise TypeError('No publisher specified, and RPC caller ID not available. Data requires an original publisher.')
        now = int(time.time())
        originallyPublished = now - age
        self._dataStores[layerID].setItem(key, value, now, originallyPublished, originalPublisherID, expireSeconds=expireSeconds, **kwargs)
        return 'OK'

    @rpcmethod
    def delete(self, key, **kwargs):
        if 'layerID' in kwargs:
            layerID = kwargs['layerID']
        else:
            layerID = 0
        if layerID not in self.active_layers:
            if _Debug:
                print('[DHT NODE]    rpcmethod.delete %r layerID=%d SKIP because layer is not active' % (
                    key,
                    layerID,
                ))
            return []
        if _Debug:
            print('[DHT NODE]    rpcmethod.delete %r layerID=%d : %r' % (key, layerID, kwargs))
        # Delete our own copy of the data (if we have one)...
        if key in self._dataStores[layerID]:
            del self._dataStores[layerID][key]
        # ...and make this RPC propagate through the network (like a FIND_VALUE for a non-existant value)
        return self.findNode(key, **kwargs)

    @rpcmethod
    def findNode(self, key, **kwargs):
        if 'layerID' in kwargs:
            layerID = kwargs['layerID']
        else:
            layerID = 0
        if layerID not in self.active_layers:
            if _Debug:
                print('[DHT NODE]    rpcmethod.findNode %r layerID=%d SKIP because layer is not active' % (
                    key,
                    layerID,
                ))
            return []
        if _Debug:
            print('[DHT NODE]    rpcmethod.findNode %r layerID=%d : %r' % (key, layerID, kwargs))
        # Get the sender's ID (if any)
        if '_rpcNodeID' in kwargs:
            rpcSenderID = kwargs['_rpcNodeID']
        else:
            rpcSenderID = None
        if layerID not in self._routingTables:
            if _Debug:
                print('[DHT NODE]    layer %d not exist' % layerID)
            return []
        contacts = self._routingTables[layerID].findCloseNodes(key, constants.k, rpcSenderID)
        contactTriples = []
        for contact in contacts:
            contactTriples.append((contact.id, encoding.to_text(contact.address), contact.port, layerID))
        if _Debug:
            print('[DHT NODE]        result is %r' % contactTriples)
        return contactTriples

    @rpcmethod
    def findValue(self, key, **kwargs):
        if 'layerID' in kwargs:
            layerID = kwargs['layerID']
        else:
            layerID = 0
        if layerID not in self.active_layers:
            if _Debug:
                print('[DHT NODE]    rpcmethod.findValue %r layerID=%d SKIP because layer is not active' % (
                    key,
                    layerID,
                ))
            return []
        if _Debug:
            print('[DHT NODE]    rpcmethod.findValue %r layerID=%r : %r' % (key, layerID, kwargs))
        if key in self._dataStores[layerID]:
            exp = None
            expireSecondsCall = getattr(self._dataStores[layerID], 'expireSeconds')
            if expireSecondsCall:
                exp = expireSecondsCall(key)
            originalPublishTimeCall = getattr(self._dataStores[layerID], 'originalPublishTime')
            published = None
            if originalPublishTimeCall:
                published = originalPublishTimeCall(key)
            if _Debug:
                print('[DHT NODE]        found key in local dataStore %r' % self._dataStores[layerID][key])
            return {
                key: self._dataStores[layerID][key],
                'expireSeconds': exp,
                'originallyPublished': published,
            }
        if _Debug:
            print('[DHT NODE]        NOT found key in local dataStore')
        return self.findNode(key, **kwargs)

    def _iterativeFind(self, key, startupShortlist=None, rpc='findNode', deep=False, layerID=0, parallel_calls=None):
        if _Debug:
            print('[DHT NODE]    _iterativeFind   layerID=%d   rpc=%r   key=%r  startupShortlist=%r routingTables=%r parallel_calls=%r' % (layerID, rpc, key, startupShortlist, self._routingTables, parallel_calls))
        if rpc != 'findNode':
            findValue = True
        else:
            findValue = False
        shortlist = []
        if startupShortlist is None:
            shortlist = self._routingTables[layerID].findCloseNodes(key, parallel_calls or constants.alpha)
            if key != self.layers[layerID]:
                # Update the "last accessed" timestamp for the appropriate k-bucket
                self._routingTables[layerID].touchKBucket(key)
            if len(shortlist) == 0:
                if _Debug:
                    print('[DHT NODE]  layerID=%d   This node doesnt know of any other nodes !!!!!' % layerID)
                # This node doesn't know of any other nodes
                fakeDf = defer.Deferred()
                fakeDf.callback([])
                return fakeDf
        else:
            # This is used during the bootstrap process; node ID's are most probably fake
            shortlist = startupShortlist
        if _Debug:
            print('[DHT NODE]   _iterativeFind  shortlist=%r' % shortlist)
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
        findValueResult = {
            'values': [],
        }
        slowNodeCount = [0]

        def extendShortlist(responseTuple):
            """ @type responseMsg: kademlia.msgtypes.ResponseMessage """
            # The "raw response" tuple contains the response message, and the originating address info
            responseMsg = responseTuple[0]
            originAddress = responseTuple[1]  # tuple: (ip adress, udp port)
            # Make sure the responding node is valid, and abort the operation if it isn't
            if _Debug:
                print('[DHT NODE]        responseTuple:', responseTuple)
            if responseMsg.nodeID in activeContacts or responseMsg.nodeID == self.layers[layerID]:
                if _Debug:
                    if responseMsg.nodeID == self.layers[layerID]:
                        print('[DHT NODE]            response from my own node')
                    else:
                        print('[DHT NODE]            response from active contact')
                return responseMsg.nodeID

            # Mark this node as active
            if responseMsg.nodeID in shortlist:
                # Get the contact information from the shortlist...
                aContact = shortlist[shortlist.index(responseMsg.nodeID)]
            else:
                # If it's not in the shortlist; we probably used a fake ID to reach it
                # - reconstruct the contact, using the real node ID this time
                aContact = LayeredContact(encoding.to_text(responseMsg.nodeID), originAddress[0], originAddress[1], self._protocol, layerID=layerID)
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
                findValueResult['values'].append((
                    result[key],
                    result.get('revision', 0),
                    responseMsg.nodeID,
                    originAddress,
                ))
                if 'expireSeconds' in result:
                    findValueResult['expireSeconds'] = result['expireSeconds']
            else:
                if findValue:
                    # We are looking for a value, and the remote node didn't have it
                    # - mark it as the closest "empty" node, if it is
                    if 'closestNodeNoValue' in findValueResult:
                        if self._routingTables[layerID].distance(key, responseMsg.nodeID) < self._routingTables[layerID].distance(key, activeContacts[0].id):
                            findValueResult['closestNodeNoValue'] = aContact
                    else:
                        findValueResult['closestNodeNoValue'] = aContact
                for contactTriple in result:
                    try:
                        testContact = LayeredContact(encoding.to_text(contactTriple[0]), contactTriple[1], contactTriple[2], self._protocol, layerID=layerID)
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
                if _Debug:
                    print('[DHT NODE]    removing %r' % deadContactID)
                shortlist.remove(deadContactID)
            return deadContactID

        def cancelActiveProbe(contactID):
            activeProbes.pop()
            if len(activeProbes) <= int((parallel_calls or constants.alpha)/2.0) and len(pendingIterationCalls):
                # Force the iteration
                pendingIterationCalls[0].cancel()
                del pendingIterationCalls[0]
                if _Debug:
                    print('[DHT NODE]    forcing iteration =================')
                searchIteration()

        # Send parallel, asynchronous FIND_NODE RPCs to the shortlist of contacts
        def searchIteration():
            if not self._routingTables or layerID not in self._routingTables:
                if _Debug:
                    print('[DHT NODE]    ++++++++++++++ searchIteration INTERRUPTED +++++++++++++++\n\n')
                return
            slowNodeCount[0] = len(activeProbes)
            # Sort the discovered active nodes from closest to furthest
            activeContacts.sort(key=lambda cont: self._routingTables[layerID].distance(cont.id, key))
            if _Debug:
                print('[DHT NODE]    ==> searchIteration %r' % activeContacts)
            # This makes sure a returning probe doesn't force calling this function by mistake
            while len(pendingIterationCalls):
                del pendingIterationCalls[0]
            # See if should continue the search
            if key in findValueResult and not deep:
                if _Debug:
                    print('[DHT NODE]    ++++++++++++++ DONE (findValue found) +++++++++++++++\n\n')
                findValueResult['activeContacts'] = activeContacts
                outerDf.callback(findValueResult)
                return
            if len(activeContacts) and findValue == False:
                if (len(activeContacts) >= constants.k) or (activeContacts[0] == prevClosestNode[0] and len(activeProbes) == slowNodeCount[0]):
                    # TODO: Re-send the FIND_NODEs to all of the k closest nodes not already queried
                    # Ok, we're done; either we have accumulated k active contacts or no improvement in closestNode has been noted
                    if len(activeContacts) >= constants.k:
                        if _Debug:
                            print('[DHT NODE]    ++++++++++++++ DONE (test for k active contacts) +++++++++++++++\n\n')
                    else:
                        if _Debug:
                            print('[DHT NODE]    ++++++++++++++ DONE (test for closest node) +++++++++++++++\n\n')
                    if findValue:
                        findValueResult['activeContacts'] = activeContacts
                        outerDf.callback(findValueResult)
                    else:
                        outerDf.callback(activeContacts)
                    return
            # The search continues...
            if len(activeContacts):
                prevClosestNode[0] = activeContacts[0]
            contactedNow = 0
            activeContacts.sort(key=lambda cont: self._routingTables[layerID].distance(cont.id, key))
            # Store the current shortList length before contacting other nodes
            prevShortlistLength = len(shortlist)
            for contact in shortlist:
                if contact.id not in alreadyContacted:
                    activeProbes.append(contact.id)
                    rpcMethod = getattr(contact, rpc)
                    if _Debug:
                        print('[DHT NODE] calling RPC method %r with key=%r layerID=%d at %r' % (rpc, key, layerID, contact))
                    df = rpcMethod(
                        key,
                        rawResponse=True,
                        layerID=layerID,
                    )
                    df.addCallback(extendShortlist)
                    df.addErrback(removeFromShortlist)
                    df.addCallback(cancelActiveProbe)
                    alreadyContacted.append(contact.id)
                    contactedNow += 1
                if contactedNow == (parallel_calls or constants.alpha):
                    break
            if len(activeProbes) > slowNodeCount[0] \
                    or (len(shortlist) < constants.k and len(activeContacts) < len(shortlist) and len(activeProbes) > 0):
                if _Debug:
                    print('[DHT NODE]    ----------- scheduling next call -------------')
                # Schedule the next iteration if there are any active calls (Kademlia uses loose parallelism)
                call = twisted.internet.reactor.callLater(constants.iterativeLookupDelay, searchIteration)  # IGNORE:E1101  @UndefinedVariable
                pendingIterationCalls.append(call)
            # Check for a quick contact response that made an update to the shortList
            elif prevShortlistLength < len(shortlist):
                # Ensure that the closest contacts are taken from the updated shortList
                searchIteration()
            else:
                if _Debug:
                    print('[DHT NODE]    ++++++++++++++ DONE (logically) +++++++++++++\n\n')
                # If no probes were sent, there will not be any improvement, so we're done
                if findValue:
                    findValueResult['activeContacts'] = activeContacts
                    outerDf.callback(findValueResult)
                else:
                    outerDf.callback(activeContacts)

        outerDf = defer.Deferred()
        # Start the iterations
        searchIteration()
        return outerDf

    def _persistState(self, *args, **kwargs):
        layerID = kwargs.get('layerID', 0)
        self._joinDeferreds.pop(layerID, None)
        closestNodes = list(self.findNode(self.layers[layerID], **kwargs))
        state = {
            'id': self.layers[layerID],
            'closestNodes': closestNodes,
            'key': 'nodeState',
            'type': 'skip_validation',
        }
        if _Debug:
            print('[DHT NODE]    _persistState  layerID=%d id=%r closestNodes=%r state=%r' % (
                layerID,
                self.layers[layerID],
                closestNodes,
                state,
            ))
        json_value = json.dumps(state)
        now = int(time.time())
        self._dataStores[layerID].setItem(self.nodeStateKey, json_value, now, now, self.layers[layerID])
        return args

    def _joinNetworkFailed(self, err, **kwargs):
        layerID = kwargs.get('layerID', 0)
        self._joinDeferreds.pop(layerID, None)
        if _Debug:
            print('[DHT NODE]    failed joining DHT network layerID=%d ' % layerID, err)

    def _refreshNode(self, layerID=0):
        """
        Periodically called to perform k-bucket refreshes and data
        replication/republishing as necessary.
        """
        # if self._counter:
        #     self._counter('_refreshNode')
        if layerID not in self.layers:
            return
        df = self._refreshRoutingTable(layerID=layerID)
        df.addCallback(self._republishData, layerID=layerID)
        df.addCallback(self._scheduleNextNodeRefresh, layerID=layerID)

    def _refreshRoutingTable(self, layerID=0, parallel_calls=None):
        nodeIDs = self._routingTables[layerID].getRefreshList(0, False)
        if _Debug:
            print('[DHT NODE]    _refreshRoutingTable', nodeIDs)

        outerDf = defer.Deferred()

        def searchFailed(err):
            if _Debug:
                print('[DHT NODE]    searchFailed', err)

        def searchForNextNodeID(dfResult=None):
            if len(nodeIDs) > 0:
                searchID = nodeIDs.pop()
                df = self.iterativeFindNode(searchID, layerID=layerID, parallel_calls=parallel_calls)
                df.addCallback(searchForNextNodeID)
                df.addErrback(searchFailed)
            else:
                # If this is reached, we have finished refreshing the routing table
                outerDf.callback(None)

        # Start the refreshing cycle
        searchForNextNodeID()
        return outerDf

    def _republishData(self, *args, **kwargs):
        df = twisted.internet.threads.deferToThread(self._threadedRepublishData, *args, **kwargs)
        return df

    def _scheduleNextNodeRefresh(self, *args, **kwargs):
        if _Debug:
            print('[DHT NODE] will refresh layer %d in %d seconds' % (
                kwargs['layerID'],
                constants.checkRefreshInterval,
            ))
        self.refreshers[kwargs['layerID']] = twisted.internet.reactor.callLater(  # @UndefinedVariable
            constants.checkRefreshInterval,
            self._refreshNode,
            layerID=kwargs['layerID'],
        )  # @UndefinedVariable

    def _threadedRepublishData(self, *args, **kwargs):
        """
        Republishes and expires any stored data (i.e. stored C{(key, value
        pairs)} that need to be republished/expired.

        This method should run in a deferred thread
        """
        layerID = kwargs['layerID']
        if _Debug:
            print('[DHT NODE]    republishData called, node: %r' % self.layers[layerID])
        expiredKeys = []
        for key in self._dataStores[layerID].keys():
            if _Debug:
                print('[DHT NODE]        %r' % key)
            # Filter internal variables stored in the datastore
            if key == 'nodeState':
                continue

            now = int(time.time())
            itemData = self._dataStores[layerID].getItem(key)
            originallyPublished = itemData['originallyPublished']
            originalPublisherID = itemData['originalPublisherID']
            lastPublished = itemData['lastPublished']
            expireSeconds = itemData['expireSeconds']
            age = now - originallyPublished
            if originalPublisherID == self.layers[layerID]:
                # This node is the original publisher; it has to republish
                # the data before it expires (24 hours in basic Kademlia)
                if age >= constants.dataExpireTimeout:
                    twisted.internet.reactor.callFromThread(  # @UndefinedVariable
                        self.iterativeStore,
                        key=key,
                        value=itemData['value'],
                        expireSeconds=expireSeconds,
                        layerID=layerID,
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
                    twisted.internet.reactor.callFromThread(  # @UndefinedVariable
                        self.iterativeStore,
                        key=key,
                        value=self._dataStore[key],
                        originalPublisherID=originalPublisherID,
                        age=age,
                        expireSeconds=expireSeconds,
                        layerID=layerID,
                    )
        for key in expiredKeys:
            del self._dataStores[layerID][key]

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
    twisted.internet.reactor.run()  # @UndefinedVariable
