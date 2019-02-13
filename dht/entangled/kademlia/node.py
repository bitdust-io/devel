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
from .contact import Contact  # @UnresolvedImport


_Debug = False


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
                if _Debug: print('    [DHT NODE]    found "nodeState" key in local db and added %d contacts to routing table' % len(state[b'closestNodes']))
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
        self.refresher = twisted.internet.reactor.callLater(constants.checkRefreshInterval, self._refreshNode)  # IGNORE:E1101  @UndefinedVariable
        # twisted.internet.reactor.run()
        return self._joinDeferred

    def printContacts(self):
        if _Debug: print('\n\nNODE CONTACTS\n===============')
        for i in range(len(self._routingTable._buckets)):
            for contact in self._routingTable._buckets[i]._contacts:
                if _Debug: print(contact)
        if _Debug: print('==================================')
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
        collect_results = kwargs.pop('collect_results', False)
        ret = defer.Deferred()

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
                print('    [DHT NODE]    storeSuccess', key, ok)
            return ok

        def storeFailed(x, key):
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
                print('    [DHT NODE]    storeFailed', key, errmsg)
            return errmsg

        # Prepare a callback for doing "STORE" RPC calls

        def findNodeFailed(x):
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
                print('    [DHT NODE]    findNodeFailed', errmsg)
            return errmsg

        def storeRPCsCollected(store_results, store_nodes):
            if _Debug:
                print('    [DHT NODE]    storeRPCsCollected', store_results, store_nodes)
            ret.callback((store_nodes, store_results, ))
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
                print('    [DHT NODE]    storeRPCsFailed', errmsg)
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
                        ok = self.store(key, value, originalPublisherID=originalPublisherID,
                                        age=age, expireSeconds=expireSeconds, **kwargs)
                        l.append(defer.succeed(ok))
                    except Exception as exc:
                        if _Debug: traceback.print_exc()
                        l.append(defer.fail(exc))
            else:
                try:
                    ok = self.store(key, value, originalPublisherID=originalPublisherID,
                                    age=age, expireSeconds=expireSeconds, **kwargs)
                    l.append(defer.succeed(ok))
                except Exception as exc:
                    if _Debug: traceback.print_exc()
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

        def lookupFailed(x):
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
                print('    [DHT NODE]    iterativeFindValue.lookupFailed', errmsg)
            return errmsg

        def storeFailed(x):
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
                print('    [DHT NODE]    iterativeFindValue.storeFailed', errmsg)
            return errmsg

        def refreshRevisionSuccess(ok):
            if _Debug: print('    [DHT NODE]    iterativeFindValue.refreshRevisionSuccess', ok)

        def refreshRevisionFailed(x):
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
                print('    [DHT NODE]    iterativeFindValue.refreshRevisionFailed', errmsg)
            return errmsg

        def checkResult(result):
            if _Debug: print('    [DHT NODE]    iterativeFindValue.checkResult', result)
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
                        if _Debug: print('    [DHT NODE]    republish %s to closest node with %d expire seconds' % (key, expireSeconds))
                        contact.store(key, result[key], None, 0, expireSeconds, revision=latest_revision).addErrback(storeFailed)
                    if refresh_revision:
                        # need to refresh nodes who has old version of that value
                        for v in result['values']:
                            if v[1] < latest_revision:
                                _contact = Contact(encoding.to_text(v[2]), v[3][0], v[3][1], self._protocol)
                                if _Debug: print('    [DHT NODE]    will refresh revision %d on %r' % (latest_revision, _contact))
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
                            if _Debug: print('    [DHT NODE]    refresh %s : %r with %d to %r' % (key, item['value'], expireSeconds, contact))
                            contact.store(key, item['value'], None, 0, expireSeconds).addErrback(storeFailed)
                        outerDf.callback({
                            'key': item['value'],
                            'values': [(
                                item['value'],
                                item['revision'],
                                self.id,
                                (b'127.0.0.1', self.port),
                            ),],
                            'activeContacts': result['activeContacts'],
                        })
                    else:
                        # Ok, value does not exist in DHT at all
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
                        if _Debug: print('    [DHT NODE]    refresh %s : %r with %d to %r' % (key, item['value'], expireSeconds, contact))
                        contact.store(key, item['value'], None, 0, expireSeconds).addErrback(storeFailed)
                    outerDf.callback({
                        'key': item['value'],
                        'values': [(
                            item['value'],
                            item['revision'],
                            self.id,
                            (b'127.0.0.1', self.port),
                        ),],
                        'activeContacts': result['activeContacts'],
                    })
                else:
                    # Ok, value does not exist in DHT at all
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
        if _Debug: print('    [DHT NODE]    rpcmethod.store %r' % key)
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
        if _Debug: print('    [DHT NODE]    rpcmethod.findNode %r' % key)
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
        if self._counter:
            self._counter('rpc_node_findValue')
        if _Debug: print('    [DHT NODE]    rpcmethod.findValue %r' % key)
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
                print('    [DHT NODE]        found key in local dataStore %r' % self._dataStore[key])
            return {key: self._dataStore[key], 'expireSeconds': exp, 'originallyPublished': published, }
        else:
            if _Debug:
                print('    [DHT NODE]        NOT found key in local dataStore')
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
        if _Debug: print('    [DHT NODE]    _iterativeFind rpc=%r   key=%r  startupShortlist=%r' % (rpc, key, startupShortlist, ))
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
                if _Debug: print("    [DHT NODE]    This node doesn't know of any other nodes !!!!!")
                # This node doesn't know of any other nodes
                fakeDf = defer.Deferred()
                fakeDf.callback([])
                return fakeDf
        else:
            # This is used during the bootstrap process; node ID's are most probably fake
            shortlist = startupShortlist
        if _Debug: print('    [DHT NODE]    shortlist=%r' % shortlist)
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
        findValueResult = {'values': [], }
        slowNodeCount = [0]

        def extendShortlist(responseTuple):
            """ @type responseMsg: kademlia.msgtypes.ResponseMessage """
            # The "raw response" tuple contains the response message, and the originating address info
            responseMsg = responseTuple[0]
            originAddress = responseTuple[1]  # tuple: (ip adress, udp port)
            # Make sure the responding node is valid, and abort the operation if it isn't
            if _Debug: 
                print('    [DHT NODE]        extendShortlist', (responseMsg.nodeID, type(responseMsg.nodeID)))
            if responseMsg.nodeID in activeContacts or responseMsg.nodeID == self.id:
                if _Debug:
                    if responseMsg.nodeID == self.id:
                        print('    [DHT NODE]            response from my own node')
                    else:
                        print('    [DHT NODE]            response from active contact')
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
                if _Debug: print('    [DHT NODE]    removing %r' % deadContactID)
                shortlist.remove(deadContactID)
            return deadContactID

        def cancelActiveProbe(contactID):
            activeProbes.pop()
            if len(activeProbes) <= constants.alpha / 2 and len(pendingIterationCalls):
                # Force the iteration
                pendingIterationCalls[0].cancel()
                del pendingIterationCalls[0]
                if _Debug: print('    [DHT NODE]    forcing iteration =================')
                searchIteration()

        # Send parallel, asynchronous FIND_NODE RPCs to the shortlist of contacts
        def searchIteration():
            slowNodeCount[0] = len(activeProbes)
            # Sort the discovered active nodes from closest to furthest
            activeContacts.sort(key=lambda cont: self._routingTable.distance(cont.id, key))
            if _Debug: print('    [DHT NODE]    ==> searchiteration %r' % activeContacts)
            # This makes sure a returning probe doesn't force calling this function by mistake
            while len(pendingIterationCalls):
                del pendingIterationCalls[0]
            # See if should continue the search
            if key in findValueResult and not deep:
                if _Debug: print('    [DHT NODE]    ++++++++++++++ DONE (findValue found) +++++++++++++++\n\n')
                findValueResult['activeContacts'] = activeContacts
                outerDf.callback(findValueResult)
                return
            if len(activeContacts) and findValue == False:
                if (len(activeContacts) >= constants.k) or (activeContacts[0] == prevClosestNode[0] and len(activeProbes) == slowNodeCount[0]):
                    # TODO: Re-send the FIND_NODEs to all of the k closest nodes not already queried
                    # Ok, we're done; either we have accumulated k active contacts or no improvement in closestNode has been noted
                    if len(activeContacts) >= constants.k:
                        if _Debug: print('    [DHT NODE]    ++++++++++++++ DONE (test for k active contacts) +++++++++++++++\n\n')
                    else:
                        if _Debug: print('    [DHT NODE]    ++++++++++++++ DONE (test for closest node) +++++++++++++++\n\n')
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
                if _Debug: print('    [DHT NODE]    ----------- scheduling next call -------------')
                # Schedule the next iteration if there are any active calls (Kademlia uses loose parallelism)
                call = twisted.internet.reactor.callLater(constants.iterativeLookupDelay, searchIteration)  # IGNORE:E1101  @UndefinedVariable
                pendingIterationCalls.append(call)
            # Check for a quick contact response that made an update to the shortList
            elif prevShortlistLength < len(shortlist):
                # Ensure that the closest contacts are taken from the updated shortList
                searchIteration()
            else:
                if _Debug: print('    [DHT NODE]    ++++++++++++++ DONE (logically) +++++++++++++\n\n')
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
        if _Debug: print('    [DHT NODE]    _persistState id=%r state=%r' % (self.id, state, ))
        json_value = json.dumps(state)
        now = int(time.time())

        h = hashlib.sha1()
        h.update(b'nodeState')
        nodeStateKey = h.hexdigest()

        self._dataStore.setItem(nodeStateKey, json_value, now, now, self.id)
        return args

    def _joinNetworkFailed(self, err):
        if _Debug: print('    [DHT NODE]    failed joining DHT network')
        if _Debug: print(err)

    def _refreshNode(self):
        """
        Periodically called to perform k-bucket refreshes and data
        replication/republishing as necessary.
        """
        if self._counter:
            self._counter('_refreshNode')
        df = self._refreshRoutingTable()
        df.addCallback(self._republishData)
        df.addCallback(self._scheduleNextNodeRefresh)

    def _refreshRoutingTable(self):
        nodeIDs = self._routingTable.getRefreshList(0, False)
        if _Debug:
            print('    [DHT NODE]    _refreshRoutingTable', nodeIDs)

        outerDf = defer.Deferred()

        def searchFailed(err):
            if _Debug: print('    [DHT NODE]    searchFailed', err)

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
        if _Debug: print('    [DHT NODE]    republishData called, node: %r' % self.id)
        expiredKeys = []
        for key in self._dataStore.keys():
            if _Debug: print('    [DHT NODE]        %r' % key)
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
