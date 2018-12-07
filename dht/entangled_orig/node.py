#!/usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

import hashlib

from twisted.internet import defer

import kademlia.node
from kademlia.node import rpcmethod


class EntangledNode(kademlia.node.Node):
    """ Entangled DHT node
    
    This is basically a Kademlia node, but with a few more (non-standard, but
    useful) RPCs defined.
    """
    def __init__(self, id=None, udpPort=4000, dataStore=None, routingTable=None, networkProtocol=None):
        kademlia.node.Node.__init__(self, id, udpPort, dataStore, routingTable, networkProtocol)
        self.invalidKeywords = []
        self.keywordSplitters = ['_', '.', '/']

    def searchForKeywords(self, keywords):
        """ The Entangled search operation (keyword-based)
        
        Call this to find keys in the DHT which contain the specified
        keyword(s).
        """
        if type(keywords) == str:
            for splitter in self.keywordSplitters:
                keywords = keywords.replace(splitter, ' ')
            keywords = keywords.lower().split()

        keyword = None
        for testWord in keywords:
            if testWord not in self.invalidKeywords:
                keyword = testWord
                break
        if keyword == None:
            df = defer.Deferred()
            df.callback([])
            return df
        
        keywords.remove(keyword)

        h = hashlib.sha1()
        h.update(keyword)
        key = h.digest()
        
        def checkResult(result):
            if type(result) == dict:
                # Value was found; this should be list of "real names" (not keys, in this implementation)
                index = result[key]
                filteredResults = list(index)
                # We found values containing our first keyword; Now filter for the rest
                for name in index:
                    for kw in keywords:
                        if name.lower().find(kw) == -1:
                            filteredResults.remove(name)
                index = filteredResults
            else:
                # Value wasn't found
                index = []
            return index
 
        df = self.iterativeFindValue(key)
        df.addCallback(checkResult)
        return df

    def publishData(self, name, data):
        """ The Entangled high-level data publishing operation
        
        Call this to store data in the Entangled DHT.
        
        @note: This will automatically create a hash of the specified C{name}
        parameter, and add the published data to the appropriate inverted
        indexes, to enable keyword-based searching. If this behaviour is not 
        wanted/needed, rather call the Kademlia base node's
        C{iterativeStore()} method directly.
        """
        h = hashlib.sha1()
        h.update(name)
        mainKey = h.digest()

        outerDf = defer.Deferred()

        def publishKeywords(deferredResult=None):        
            # Create hashes for the keywords in the name
            keywordKeys = self._keywordHashesFromString(name)
            # Update the appropriate inverted indexes
            df = self._addToInvertedIndexes(keywordKeys, name)
            df.addCallback(lambda _: outerDf.callback(None))

        # Store the main key, with its value...
        df = self.iterativeStore(mainKey, data)
        
        df.addCallback(publishKeywords)
        
        return outerDf

    def _addToInvertedIndexes(self, keywordKeys, indexLink):
        # Prepare a deferred result for this operation
        outerDf = defer.Deferred()

        kwIndex = [-1] # using a list for this counter because Python doesn't allow binding a new value to a name in an enclosing (non-global) scope

        # ...and now update the inverted indexes (or add them, if they don't exist yet)
        def addToInvertedIndex(results):
            kwKey = keywordKeys[kwIndex[0]]
            if type(results) == dict:
                # An index already exists; add our value to it
                index = results[kwKey]
                #TODO: this might not actually be an index, but a value... do some name-mangling to avoid this
                index.append(indexLink)
            else:
                # An index does not yet exist for this keyword; create one
                index = [indexLink]
            df = self.iterativeStore(kwKey, index)
            df.addCallback(storeNextKeyword)

        def storeNextKeyword(results=None):
            kwIndex[0] += 1
            if kwIndex[0] < len(keywordKeys):
                kwKey = keywordKeys[kwIndex[0]]
                # We use the find algorithm directly so that kademlia does not replicate the un-updated inverted index
                if kwKey in self._dataStore:
                    df = defer.Deferred()
                    df.callback({kwKey: self._dataStore[kwKey]})
                else:
                    df = self._iterativeFind(kwKey, rpc='findValue')
                df.addCallback(addToInvertedIndex)
            else:
                # We're done. Let the caller of the parent method know
                outerDf.callback(None)

        if len(keywordKeys) > 0:
            # Start the "keyword store"-cycle
            storeNextKeyword()
        else:
            outerDf.callback(None)

        return outerDf

    def removeData(self, name):
        """ The Entangled high-level data removal (delete) operation
        
        Call this to remove data from the Entangled DHT.
        
        @note: This will automatically create a hash of the specified C{name}
        parameter. It will also remove the published data from the appropriate
        inverted indexes, so as to maintain reliability of keyword-based
        searching. If this behaviour is not wanted/needed, rather call this
        node's C{iterativeDelete()} method directly.
        """
        h = hashlib.sha1()
        h.update(name)
        mainKey = h.digest()
        
        # Remove the main key
        self.iterativeDelete(mainKey)

        # Create hashes for the keywords in the name
        keywordKeys = self._keywordHashesFromString(name)
        
        # Update the appropriate inverted indexes
        df = self._removeFromInvertedIndexes(keywordKeys, name)
        return df

    def _removeFromInvertedIndexes(self, keywordKeys, indexLink):
        # Prepare a deferred result for this operation
        outerDf = defer.Deferred()
    
        kwIndex = [-1] # using a list for this counter because Python doesn't allow binding a new value to a name in an enclosing (non-global) scope

        # ...and now update the inverted indexes (or ignore them, if they don't exist yet)
        def removeFromInvertedIndex(results):
            kwKey = keywordKeys[kwIndex[0]]
            if type(results) == dict:
                # An index for this keyword exists; remove our value from it
                index = results[kwKey]
                #TODO: this might not actually be an index, but a value... do some name-mangling to avoid this
                try:
                    index.remove(indexLink)
                except ValueError:
                    df = defer.Deferred()
                    df.callback(None)
                else:
                    # Remove the index completely if it is empty, otherwise put it back
                    if len(index) > 0:
                        df = self.iterativeStore(kwKey, index)
                    else:
                        df = self.iterativeDelete(kwKey)
                df.addCallback(findNextKeyword)
            else:
                # No index exists for this keyword; skip it
                findNextKeyword()

        def findNextKeyword(results=None):
            kwIndex[0] += 1
            if kwIndex[0] < len(keywordKeys):
                kwKey = keywordKeys[kwIndex[0]]
                # We use the find algorithm directly so that kademlia does not replicate the un-updated inverted index
                if kwKey in self._dataStore:
                    df = defer.Deferred()
                    df.callback({kwKey: self._dataStore[kwKey]})
                else:
                    df = self._iterativeFind(kwKey, rpc='findValue')
                df.addCallback(removeFromInvertedIndex)
            else:
                # We're done. Let the caller of the parent method know
                outerDf.callback(None)
             
        if len(keywordKeys) > 0:
            # Start the "keyword store"-cycle
            findNextKeyword()

        return outerDf

    def iterativeDelete(self, key):
        """ The Entangled delete operation
        
        Call this to remove data from the DHT.
        
        The Entangled delete operation uses the basic Kademlia node lookup
        algorithm (same as Kademlia's search/retrieve). The algorithm behaves
        the same as when issueing the FIND_NODE RPC - the only difference is
        that the DELETE RPC (defined in C{delete()}) is used instead of
        FIND_NODE.
        
        @param key: The hashtable key of the data
        @type key: str
        """
        # Delete our own copy of the data
        if key in self._dataStore:
            del self._dataStore[key]
        df = self._iterativeFind(key, rpc='delete')
        return df

    @rpcmethod
    def delete(self, key, **kwargs):
        """ Deletes the the specified key (and it's value) if present in
        this node's data, and executes FIND_NODE for the key
        
        @param key: The hashtable key of the data to delete
        @type key: str
        
        @return: A list of contact triples closest to the specified key. 
                 This method will return C{k} (or C{count}, if specified)
                 contacts if at all possible; it will only return fewer if the
                 node is returning all of the contacts that it knows of.
        @rtype: list
        """
        # Delete our own copy of the data (if we have one)...
        if key in self._dataStore:
            del self._dataStore[key]
        # ...and make this RPC propagate through the network (like a FIND_VALUE for a non-existant value)
        return self.findNode(key, **kwargs)

    def _keywordHashesFromString(self, text):
        """ Create hash keys for the keywords contained in the specified text string """
        keywordKeys = []
        splitText = text.lower()
        for splitter in self.keywordSplitters:
            splitText = splitText.replace(splitter, ' ')
        for keyword in splitText.split():
            # Only consider keywords with 3 or more letters
            if len(keyword) >= 3 and keyword != text and keyword not in self.invalidKeywords:
                h = hashlib.sha1()
                h.update(keyword)
                key = h.digest()
                keywordKeys.append(key)
        return keywordKeys


if __name__ == '__main__':
    import twisted.internet.reactor
    from kademlia.datastore import SQLiteDataStore
    import sys, os
    if len(sys.argv) < 2:
        print 'Usage:\n%s UDP_PORT  [KNOWN_NODE_IP  KNOWN_NODE_PORT]' % sys.argv[0]
        print 'or:\n%s UDP_PORT  [FILE_WITH_KNOWN_NODES]' % sys.argv[0]
        print '\nIf a file is specified, it should containg one IP address and UDP port\nper line, seperated by a space.'
        sys.exit(1)
    try:
        int(sys.argv[1])
    except ValueError:
        print '\nUDP_PORT must be an integer value.\n'
        print 'Usage:\n%s UDP_PORT  [KNOWN_NODE_IP  KNOWN_NODE_PORT]' % sys.argv[0]
        print 'or:\n%s UDP_PORT  [FILE_WITH_KNOWN_NODES]' % sys.argv[0]
        print '\nIf a file is specified, it should contain one IP address and UDP port\nper line, seperated by a space.'
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

    if os.path.isfile('/tmp/dbFile%s.db' % sys.argv[1]):
        os.remove('/tmp/dbFile%s.db' % sys.argv[1])
    dataStore = SQLiteDataStore(dbFile = '/tmp/dbFile%s.db' % sys.argv[1])
    node = EntangledNode( udpPort=int(sys.argv[1]), dataStore=dataStore )
    #node = EntangledNode( udpPort=int(sys.argv[1]) )
    node.joinNetwork(knownNodes)
    twisted.internet.reactor.run()
