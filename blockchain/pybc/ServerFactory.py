"""
ServerFactory.py: contains the ServerFactory class.

"""

import logging
from twisted.internet import protocol

from pybc.BlockchainProtocol import BlockchainProtocol


class ServerFactory(protocol.ServerFactory):
    """
    This is a Twisted server factory, responsible for taking incoming
    connections and starting Servers to serve them. It is part of a Peer.

    """

    def __init__(self, peer):
        """
        Make a new ServerFactory with a reference to the Peer it is handling
        incoming connections for.

        """

        # Keep the peer around
        self.peer = peer

    def buildProtocol(self, addr):
        """
        Make a new server protocol. It's talking to the given
        address.

        """

        logging.info("Server got connection from {}".format(addr))

        # Make a new BlockchainProtocol that knows we are its factory. It will
        # then talk to our peer.
        return BlockchainProtocol(self, (addr.host, addr.port), incoming=True)
