"""
BlockchainProtocol.py: contains the BlockchainProtocol class.

"""


import time
import traceback
import collections
import logging
from twisted.internet import reactor
from twisted.protocols.basic import LineReceiver

# Say that we can take up to 10 mb at a time
LineReceiver.MAX_LENGTH = 1024 * 1024 * 10

from pybc.Block import Block
from pybc.util import string2bytes, bytes2string


class BlockchainProtocol(LineReceiver):
    """
    This is a Twisted protocol that exchanges blocks with the peer at the other
    end, and floods valid non-block messages (transactons). Also lets state
    components be requested. Used by both servers and clients.

    It is a line-oriented protocol with occasional blocks of raw data.

    """

    def __init__(self, factory, remote_address, incoming=False):
        """
        Make a new protocol (i.e. connection handler) belonging to the given
        Factory, which in turn belongs to a Peer.

        remote_address should be the (host, port) tuple of the host we are
        talking to.

        incoming specifies whether this connection is incoming or not. If it's
        not incoming, the port they are using will be advertised. If incoming is
        true, this Protocol will kick off the connection by greeting the other
        peer.

        """

        # Keep the factory around, so we can talk to our Peer.
        self.factory = factory

        # Remember the address of the host we are talking to
        self.remote_address = remote_address

        # Remember if we're supposed to greet or not.
        self.incoming = incoming

        # Keep a queue of block hashes to download. Don't get too many at once.
        self.inv_queue = collections.deque()

        # Keep a set of things in the inv_queue.
        self.inv_queued = set()

        # Keep a watcher callLater to watch it
        self.inv_watcher = None

        # Keep a queue of Block objects we have been sent. Don't try and gove
        # too many to the blockchain at once.
        self.block_queue = collections.deque()

        # Keep a set of block hashes in the block queue
        self.block_queued = set()

        # Keep a watcher callLater to watch it
        self.block_watcher = None

    def connectionMade(self):
        """
        A connection has been made to the remote host. It may be a server or
        client.

        """

        # Let the peer know we are connected. It will tell us if we should keep
        # the connection or not.
        keep = self.factory.peer.made_connection(self)

        if not keep:
            # We alread have too many incoming connections. Drop the connection.
            logging.debug("Dropping unwanted connection")
            self.disconnect()
            return

        # logging.info("Made a connection!")

        if self.incoming:
            # They connected to us. Send a greeting, saying what network we're
            # in and our protocol version.
            self.send_message(["NETWORK", self.factory.peer.network,
                               self.factory.peer.version])

        # Make sure to process the inv_queue periodically, to download blocks we
        # want.
        self.inv_watcher = reactor.callLater(1, self.process_inv_queue)

        # Make sure to process the block_queue periodically, to verify (and
        # broadcast) blocks we got.
        self.block_watcher = reactor.callLater(1, self.process_block_queue)

    def connectionLost(self, reason):
        """
        This connection has been lost.
        """

        # We're no longer a connection that the peer should send things to.
        self.factory.peer.lost_connection(self)

        # logging.info("connection LOST with {}".format(self.remote_address))

        if self.inv_watcher is not None and self.inv_watcher.active():
            # Stop asking for blocks
            self.inv_watcher.cancel()
        if self.block_watcher is not None and self.block_watcher.active():
            # Stop processing downloaded blocks
            self.block_watcher.cancel()

    def disconnect(self):
        """
        Drop the connection from the Twisted thread.

        """

        reactor.callFromThread(self.transport.loseConnection)

        # TODO: Do something to stop us trying to send messages over this
        # connection.

    def send_message(self, parts):
        """
        Given a message as a list of parts, send it from the Twisted thread.

        """

        # Compose the message string and send it from the Twisted thread
        reactor.callFromThread(self.sendLine, " ".join(map(str, parts)))

    def handle_message(self, parts):
        """
        Given a message as a list of string parts, handle it. Meant to run non-
        blocking in its own thread.

        Schedules any reply and any actions to be taken to be done in the main
        Twisted thread.
        """

        try:
            if len(parts) == 0:
                # Skip empty lines
                return

            if parts[0] == "NETWORK":
                # This is a network command, telling us the network and version
                # of the remote host. If we like them (i.e. they are equal to
                # ours), send back an acknowledgement with our network info.
                # Also start requesting peers and blocks from them.

                if (parts[1] == self.factory.peer.network and
                        int(parts[2]) == self.factory.peer.version):
                    # We like their network and version number.
                    # Send back a network OK command with our own.
                    self.send_message(["NETWORK-OK", self.factory.peer.network,
                                       self.factory.peer.version])

                    # Ask them for peers
                    self.send_message(["GETADDR"])

                    # Ask them for the blocks we need, given our list of block
                    # locator hashes.
                    self.send_message(["GETBLOCKS"] +
                                      [bytes2string(block_hash) for block_hash in
                                       self.factory.peer.blockchain.get_block_locator()])

                    # Send all the pending transactions
                    for transaction_hash, _ in \
                            self.factory.peer.blockchain.get_transactions():

                        self.send_message(["TXINV", bytes2string(
                            transaction_hash)])

                else:
                    # Nope, we don't like them.

                    # Disconnect
                    self.disconnect()

            elif parts[0] == "NETWORK-OK":
                # This is a network OK command, telling us that they want to
                # talk to us, and giving us their network and version number. If
                # we like their network and version number too, we can start
                # exchanging peer info.

                if (parts[1] == self.factory.peer.network and
                        int(parts[2]) == self.factory.peer.version):

                    # We like their network and version number. Send them a
                    # getaddr message requesting a list of peers. The next thing
                    # they give us might be something completely different, but
                    # that's OK; they ought to send some peers eventually.
                    self.send_message(["GETADDR"])

                    # Ask them for the blocks we need, given our list of block
                    # locator hashes.
                    self.send_message(["GETBLOCKS"] +
                                      [bytes2string(block_hash) for block_hash in
                                       self.factory.peer.blockchain.get_block_locator()])

                    # Send all the pending transactions
                    for transaction_hash, _ in \
                            self.factory.peer.blockchain.get_transactions():

                        self.send_message(["TXINV", bytes2string(
                            transaction_hash)])
                else:
                    # We don't like their network and version. Drop them.

                    # Disconnect
                    self.disconnect()

            elif parts[0] == "GETADDR":
                # They want a list of all known peers.
                # Send them ADDR messages, one per known peer.

                for host, port, time_seen in self.factory.peer.get_peers():
                    if time_seen is None:
                        # This is a bootstrap peer
                        continue
                    # Send the peer's host and port in an ADDR message
                    self.send_message(["ADDR", host, port, time_seen])
            elif parts[0] == "ADDR":
                # They claim that there is a peer. Tell our peer the host and port
                # and time seen.
                self.factory.peer.peer_seen(parts[1], int(parts[2]),
                                            int(parts[3]))
            elif parts[0] == "GETBLOCKS":
                # They gave us a block locator. Work out the blocks they need,
                # and send INV messages about them.

                # Decode all the hex hashes to bytestring
                block_hashes = [string2bytes(part) for part in parts[1:]]

                for needed_hash in \
                    self.factory.peer.blockchain.blocks_after_locator(
                        block_hashes):

                    # They need this hash. Send an INV message about it.
                    # TODO: consolidate and limit these.
                    self.send_message(["INV", bytes2string(needed_hash)])
            elif parts[0] == "INV":
                # They have a block. If we don't have it, ask for it.

                # TODO: allow advertising multiple things at once.

                # Decode the hash they have
                block_hash = string2bytes(parts[1])

                if (self.factory.peer.blockchain.needs_block(block_hash) and
                    block_hash not in self.inv_queued and
                        block_hash not in self.block_queued):

                    # We need this block, and it isn't in any queues.
                    self.inv_queue.append(block_hash)
                    self.inv_queued.add(block_hash)

            elif parts[0] == "GETDATA":
                # They want the data for a block. Send it to them if we have
                # it.

                # Decode the hash they want
                block_hash = string2bytes(parts[1])

                if self.factory.peer.blockchain.has_block(block_hash):
                    # Get the block to send
                    block = self.factory.peer.blockchain.get_block(block_hash)

                    # Send them the block. TODO: This encoding is terribly
                    # inefficient, but we can't send it as binary without them
                    # switching out of line mode, and they don't know to do that
                    # because messages queue.
                    self.send_message(["BLOCK", bytes2string(block.to_bytes())])
                else:
                    logging.error("Can't send missing block: '{}'".format(
                        bytes2string(block_hash)))

            elif parts[0] == "BLOCK":
                # They have sent us a block. Add it if it is valid.

                # Decode the block bytes
                block_bytes = string2bytes(parts[1])

                # Make a Block object
                block = Block.from_bytes(block_bytes)

                if block.block_hash() not in self.block_queued:
                    # Queue it if it's not already queued. Because of the set it
                    # can only be queued once.
                    self.block_queue.append(block)
                    self.block_queued.add(block.block_hash())

            elif parts[0] == "TXINV":
                # They have sent us a hash of a transaction that they have. If
                # we don't have it, we should get it and pass it on.

                # Decode the hash they have
                transaction_hash = string2bytes(parts[1])

                if not self.factory.peer.blockchain.has_transaction(
                        transaction_hash):

                    # We need this transaction!
                    self.send_message(["GETTX", parts[1]])
            elif parts[0] == "GETTX":
                # They want a transaction from our blockchain.

                # Decode the hash they want
                transaction_hash = string2bytes(parts[1])

                if self.factory.peer.blockchain.has_transaction(transaction_hash):
                    # Get the transaction to send
                    transaction = self.factory.peer.blockchain.get_transaction(
                        transaction_hash)

                    if transaction is not None:
                        # We have it (still). Send them the block transaction.
                        self.send_message(["TX", bytes2string(transaction)])
                    else:
                        logging.error("Lost transaction: '{}'".format(
                            bytes2string(transaction_hash)))
                else:
                    logging.error("Can't send missing transaction: '{}'".format(
                        bytes2string(transaction_hash)))
            elif parts[0] == "TX":
                # They have sent us a transaction. Add it to our blockchain.

                # Decode the transaction bytes
                transaction_bytes = string2bytes(parts[1])

                logging.debug("Incoming transaction.")

                if self.factory.peer.blockchain.transaction_valid_for_relay(
                        transaction_bytes):

                    # This is a legal transaction to accept from a peer (not
                    # something like a block reward).
                    logging.debug("Transaction acceptable from peer.")

                    # Give it to the blockchain as bytes. The blockchain can
                    # determine whether to forward it on or not and call the
                    # callback with transaction hash and transaction status
                    # (True or False).
                    self.factory.peer.send_transaction(
                        transaction_bytes)

            elif parts[0] == "GETSTATE":
                # They're asking us for a StateComponent from our State, with
                # the given hash. We just serve these like a dumb server.

                # We assume this is under our current State. If it's not, we'll
                # return a nort found message and make them start over again
                # from the top.

                # What StateComponent do they want?
                state_hash = string2bytes(parts[1])

                # Go get it
                state_component = \
                    self.factory.peer.blockchain.get_state_component(state_hash)

                if state_component is None:
                    # Complain we don't have that. They need to start over from
                    # the state hash in the latest block.
                    logging.warning("Peer requested nonexistent StateComponent "
                                    "{} vs. root hash {}".format(parts[1],
                                                                 bytes2string(
                                        self.factory.peer.blockchain.get_state_hash())))
                    self.send_message(["NOSTATE", bytes2string(state_hash)])
                else:

                    logging.debug("Fulfilling request for StateComponent "
                                  "{}".format(parts[1]))

                    # Pack up the StateComponent's data as bytes and send it
                    # along. They'll know which one it was when they hash it.
                    self.send_message(["STATE",
                                       bytes2string(state_component.data)])

            elif parts[0] == "NOSTATE":
                # They're saying they don't have a StateComponent we asked for.
                logging.warning("Peer says they do not have StateComponent: "
                                "{}".format(parts[1]))

            elif parts[0] == "STATE":
                # They're sending us a StateComponent we probably asked for.

                # Unpack the data
                component_bytestring = string2bytes(parts[1])

                # Give it to the Blockchain. It knows how to handle these
                # things. TODO: Maybe put a queue here, since this potentially
                # does the whole state rebuilding operation.
                self.factory.peer.blockchain.add_state_component(
                    component_bytestring)

                # Tell the peer to request more StateComponents.
                # TODO: This is going to blow up.
                self.factory.peer.request_state_components()

            elif parts[0] == "ERROR":
                # The remote peer didn't like something.
                # Print debugging output.
                logging.error("Error from remote peer: {}".format(" ".join(
                    parts[1:])))

            else:
                # They're trying to send a command we don't know about.
                # Complain.
                logging.error("Remote host tried unknown command {}".format(
                    parts[1]))
                self.send_message(["ERROR", parts[0]])

            if not self.incoming:
                # We processed a valid message from a peer we connected out to.
                # Record that we've seen them for anouncement purposes.
                self.factory.peer.peer_seen(self.remote_address[0],
                                            self.remote_address[1], int(time.time()))

        except BaseException:
            logging.error("Exception processing command: {}".format(parts))
            logging.error(traceback.format_exc())

            # Disconnect from people who send us garbage
            self.disconnect()

    def lineReceived(self, data):
        """
        We got a command from the remote peer. Handle it.

        TODO: Enforce that any of these happen in the correct order.

        """

        # Split the command into parts on spaces.
        parts = [part.strip() for part in data.split()]

        # Handle it in its own thread. This is the only other thread that ever
        # runs.
        reactor.callInThread(self.handle_message, parts)

    def lineLengthExceeded(self, line):
        """
        The peer sent us a line that is too long.

        Complain about it so the user knows that's why we're dropping
        connections.

        """

        logging.error("Peer sent excessively long line.")

    def process_inv_queue(self):
        """
        Download some blocks from the queue of blocks we know we need.

        """

        for _ in xrange(100):
            # Only ask for 100 blocks at a time.
            if len(self.inv_queue) > 0:
                # Get the bytestring hash of the next block to ask for
                block_hash = self.inv_queue.popleft()
                self.inv_queued.remove(block_hash)

                if (self.factory.peer.blockchain.needs_block(block_hash) and
                        block_hash not in self.block_queued):
                    # We need this block and don't have it in our queue to add
                    # to the blockchain, so get it. TODO: Check to see if we
                    # requested it recently.

                    self.send_message(["GETDATA", bytes2string(block_hash)])

        # Process the inv_queue again.
        self.inv_watcher = reactor.callLater(1, self.process_inv_queue)

    def process_block_queue(self):
        """
        Try to verify some blocks from the block queue.

        """

        for i in xrange(10):
            if len(self.block_queue) > 0:
                # Get the Block object we need to check out.
                block = self.block_queue.popleft()
                self.block_queued.remove(block.block_hash())

                # Give it to the blockchain to add when it can. If it does get
                # added, we announce it.
                self.factory.peer.send_block(block)
            else:
                break

        # Process the block queue again.
        self.block_watcher = reactor.callLater(0.1, self.process_block_queue)
