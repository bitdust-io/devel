"""
Peer.py: contains the Peer class.

"""

from __future__ import absolute_import
import random
import time
import threading
import logging
import socket

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet import endpoints

from pybc.ClientFactory import ClientFactory
from pybc.ServerFactory import ServerFactory
from pybc.util import time2string, bytes2string
import pybc.science

from . import sqliteshelf
import six
from six.moves import range


class Peer(object):
    """
    Represents a peer in the p2p blockchain network. Implements a protocol bsed
    on the Bitcoin p2p protocol. Keeps a Blockchain of valid blocks, and handles
    downloading new blocks and broadcasting new blocks to peers.
    """

    def __init__(self, network, version, blockchain, peer_file=":memory:",
                 external_address=None, port=8007, optimal_connections=10,
                 connections_per_batch=5, tick_period=60, peer_timeout=60 * 60 * 48):
        """
        Make a new Peer in the given network (identified by a string), with the
        given version integer, that keeps its blocks in the given Blockchain.
        Will only connect to other peers in the same network with the same
        version integer.

        network must be a printable string with no spaces or newlines.

        version must be an integer.

        peer_file gives a filename to store a persistent peer database in. It
        defaults to ":memory:", which keeps the database in memory where it
        isn't really persistent.

        external_address, if specified, gives an address or hostname at which we
        can announce our presence on every tick.

        port gives a port to listen on. If none is specified, a default
        port is used.

        optimal_connections is the number of connections we want to have. We
        will periodically try to get new connections or drop old ones.

        TODO: Actually drop connections if we have too many.

        tick_period is how often to tick and ping our peers/broadcast our
        address/try to make new connections/drop extra connections, in seconds.

        peer_timeout is how long to remember nodes sicne we last heard from
        them.

        The caller needs to run the Twisted reactor before this does anything.
        This can be doine through run().

        """

        # Remember our network name and version number
        self.network = network
        self.version = version

        # Save the blockchain
        self.blockchain = blockchain

        if external_address is not None:
            # We have an external address. Make sure it's an address and
            # remember it.
            self.external_address = socket.gethostbyname(external_address)
        else:
            # No external address known.
            self.external_address = None

        # Remember our port. We may need to tell people about it if we connect
        # to them.
        self.port = port

        # Remember our optimal number of connections
        self.optimal_connections = optimal_connections

        # And how many we should make per batch
        self.connections_per_batch = connections_per_batch

        # Remember our peer remembering timeout
        self.peer_timeout = peer_timeout

        # Make an endpoint to listen on
        self.endpoint = endpoints.TCP4ServerEndpoint(reactor, port)

        # Make a Twisted ServerFactory
        self.server = ServerFactory(self)

        # Make a Twisted ClientFactory to make outgoing connections
        self.client = ClientFactory(self)

        # Keep an sqliteshelf of known peers: from host to (port, last-seen)
        # tuples, as in BitMessage.
        self.known_peers = sqliteshelf.SQLiteShelf(peer_file, table="peers",
                                                   lazy=True)

        # Keep a set of IPs we have open, outgoing connections to
        self.outgoing_hosts = set()

        # And one of IPs we have active, incomming connections from
        self.incoming_hosts = set()

        # Keep a set of open connections (Protocol objects)
        self.connections = set()

        # Remember our tick frequency
        self.tick_period = tick_period

        # Make a lock so this whole thing can basically be a monitor
        self.lock = threading.RLock()

        # Remember if we need to repoll our peers for blocks
        self.repoll = False

        # Keep a set of recently requested StateComponents, so we don't ask for
        # the same one over and over again.
        # TODO: No other queueing stuff is in Peer. Should this be?
        self.recently_requested_state_components = set()

        # Remember our total tick count
        self.tick_count = 0

        # A little bit after we get the last block in a string of blocks, check
        # to see if we need StateComponents. This holds the Twisted callLater
        # call ID.
        self.state_download_timer = None

        # Listen with the endpoint, so we can get connections
        self.listener = self.endpoint.listen(self.server)

        # Schedule a tick right away.
        reactor.callLater(0, self.tick)

    def connect(self, host, port):
        """
        Make a new connection to the given host and port, as a client.

        """

        with self.lock:
            # Remember that we are connecting to this host
            self.outgoing_hosts.add(host)

            logging.info("Connecting to {} port {}".format(host, port))

            # Queue making a connection with our ClientFactory in the Twisted
            # reactor.
            reactor.connectTCP(host, port, self.client)

    def made_connection(self, connection):
        """
        Called when a connection is made. Add the connection to the set of
        connections.

        Returns True if the connection was added to the set and is to be kept,
        or False if we alread have too many connections and want to drop this
        one.

        """

        with self.lock:
            if (len(self.connections) > 2 * self.optimal_connections and
                    connection.incoming):
                # Don't accept this incoming connection, we have too many.
                return False
            else:
                # Add the connection to our list of connections
                self.connections.add(connection)

                if connection.incoming:
                    # Remember the host connecting in to us
                    self.incoming_hosts.add(connection.transport.getPeer().host)

                return True

    def lost_connection(self, connection):
        """
        Called when a connection is closed (either normally or abnormally).
        Remove the connection from our set of connections.

        """

        with self.lock:
            # Drop the connection from our list of connections
            self.connections.discard(connection)

            if connection.incoming:
                # This was a connection we got, so throw it out of that set.
                self.incoming_hosts.discard(connection.transport.getPeer().host)

    def lost_outgoing_connection(self, host):
        """
        Called when an outgoing connection is lost or fails.
        Removes that hostname from the list of open outgoing connections.

        """

        with self.lock:
            # No longer connecting to this host
            self.outgoing_hosts.discard(host)

    def get_peers(self):
        """
        Return a list of (host, port, time seen) tuples for all peers we know
        of.

        """

        with self.lock:
            return [(host, host_data[0], host_data[1]) for host, host_data in
                    six.iteritems(self.known_peers)]

    def peer_seen(self, host, port, time_seen):
        """
        Another peer has informed us of the existence of this peer. Remember it,
        and broadcast to to our peers.

        """

        with self.lock:

            if time_seen > int(time.time()) + 10 * 60:
                # Don't accept peers from more than 10 minutes into the future.
                return

            # Normalize host to an IPv4 address. TODO: do something to recognize
            # IPv6 addresses and pass them unchanged.
            if host.count(':'):
                host = host.split(':')[0]
            try:
                host = socket.gethostbyname(host)
            except:
                logging.exception('socket.gethostbyname failed, will use original host value')
            key = '{}:{}'.format(host, port)

            if key in self.known_peers:
                # We know of this peer, but we perhaps ought to update the last
                # heard from time

                # Get the port we know for that host, and the time we last saw
                # them
                known_port, our_time_seen = self.known_peers[key]

                if (our_time_seen is None or time_seen > our_time_seen):
                    # They heard from them more recently. Update our time last
                    # seen.
                    self.known_peers[key] = (known_port, time_seen)
                    logging.info('Known peer updated: {}:{}'.format(host, known_port))

            else:
                # This is a new peer.
                # Save it.
                logging.info('New peer added: {}:{}'.format(host, port))
                self.known_peers[key] = (port, time_seen)

                # Broadcast it
                for connection in self.connections:
                    connection.send_message(["ADDR", host, port, time_seen])

    def set_repoll(self):
        # We saw an unverifiable block. We may be out of date.
        # Next time we tick, do a getblocks to all our peers.

        # Too simple to need to lock
        self.repoll = True

    def tick(self):
        """
        See if we have the optimal number of outgoing connections. If we have
        too few, add some.
        """

        with self.lock:

            # How many connections do we have right now?
            current_connections = len(self.connections)
            logging.info("Tick {} from localhost port {}: {} of {} "
                         "connections".format(self.tick_count, self.port,
                                              current_connections, self.optimal_connections))

            for connection in self.connections:
                logging.info("\tTo {} port {}".format(
                    *connection.remote_address))

            logging.info("{} outgoing connections:".format(len(
                self.outgoing_hosts)))
            for host in self.outgoing_hosts:
                logging.info("\t To {}".format(host))

            logging.info("Blockchain height: {}".format(
                len(self.blockchain.hashes_by_height)))
            logging.info("Blocks known: {}".format(
                self.blockchain.get_block_count()))
            logging.info("Blocks pending: {}".format(
                len(self.blockchain.pending_callbacks)))
            logging.info("State available for verification and mining:"
                         " {}".format(self.blockchain.state_available))
            logging.info("Transactions pending: {}".format(len(
                self.blockchain.transactions)))

            # Calculate the average block time in seconds for the last few
            # blocks. It may be None, meaning we don't have enough history to
            # work it out.
            block_time = self.blockchain.get_average_block_time()
            if block_time is not None:
                logging.info("Average block time: {} seconds".format(
                    block_time))

            logging.info("Blockchain disk usage: {} bytes".format(
                self.blockchain.get_disk_usage()))

            if self.tick_count % 60 == 0:
                # Also log some science stats every 60 ticks (by default, 1 hour)
                pybc.science.log_event("chain_height",
                                       len(self.blockchain.hashes_by_height))
                pybc.science.log_event("pending_transactions",
                                       len(self.blockchain.transactions))
                pybc.science.log_event("connections", current_connections)
                if block_time is not None:
                    # We have an average block time, so record that.
                    pybc.science.log_event("block_time", block_time)

                # We want to log how much space our databases (block store and
                # state) take.
                pybc.science.log_event("blockchain_usage",
                                       self.blockchain.get_disk_usage())
                pybc.science.log_filesize("blockchain_file_usage",
                                          self.blockchain.store_filename)

            # Request whatever state components we need, egardless if whether we
            # recently requested them, in case our download got stalled
            self.recently_requested_state_components = set()
            self.request_state_components()

            if (len(self.outgoing_hosts) < self.optimal_connections and
                    len(self.known_peers) > 0):
                # We don't have enough outgoing connections, but we do know some
                # peers.

                for i in range(min(self.connections_per_batch,
                                    self.optimal_connections - len(self.outgoing_hosts))):
                    # Try several connections in a batch.

                    for _ in range(self.optimal_connections -
                                    len(self.outgoing_hosts)):

                        # For each connection we want but don't have

                        # Find a peer we aren't connected to and connect to them
                        key = random.sample(self.known_peers, 1)[0]
                        if key.count(':'):
                            host = key.split(':')[0]
                        else:
                            host = key

                        # Try at most 100 times to find a host we aren't
                        # connected to, and which isn't trivially obviously us.
                        attempt = 1
                        while (host in self.outgoing_hosts or
                               host in self.incoming_hosts or
                               host == self.external_address) and attempt < 100:
                            # Try a new host
                            key = random.sample(self.known_peers, 1)[0]
                            if key.count(':'):
                                host = key.split(':')[0]
                            else:
                                host = key

                            # Increment attempt
                            attempt += 1

                        # TODO: This always makes two attempts at least

                        if attempt < 100:
                            # We found one!
                            # Connect to it.

                            # Get the port (and discard the last heard from
                            # time)
                            port, _ = self.known_peers[key]

                            # Connect to it.
                            self.connect(host, port)
                        else:
                            # No more things we can try connecting to
                            break

            # Throw out peers that are too old. First compile a list of their
            # hostnames.
            too_old = []

            for key, (port, last_seen) in six.iteritems(self.known_peers):
                if last_seen is None:
                    # This is a bootstrap peer. Don't remove it.
                    continue

                if time.time() - last_seen > self.peer_timeout:
                    # We haven't heard from/about this node recently enough.
                    too_old.append(key)

            # Now drop all the too old hosts
            for key in too_old:
                del self.known_peers[key]

            # Broadcast all our hosts.
            logging.info("{} known peers".format(len(self.known_peers)))
            for key, (port, last_seen) in six.iteritems(self.known_peers):
                if last_seen is None:
                    # This is a bootstrap peer, so don't announce it.
                    continue
                if key.count(':'):
                    host, _ = key.split(':')
                logging.debug("\tPeer {} port {} last seen {}".format(host,
                                                                      port, time2string(last_seen)))
                for connection in self.connections:
                    connection.send_message(["ADDR", host, port, last_seen])

            if self.external_address is not None:
                # Broadcast ourselves, since we know our address.
                for connection in self.connections:
                    connection.send_message(["ADDR", self.external_address,
                                             self.port, int(time.time())])

            # Do we need to re-poll for blocks?
            if self.repoll:
                self.repoll = False
                logging.warning("Repolling due to unverifiable block.")

                # Compose just one message
                message = (["GETBLOCKS"] +
                           [bytes2string(block_hash) for block_hash in
                            self.blockchain.get_block_locator()])
                for connection in self.connections:
                    connection.send_message(message)

            logging.info("Saving...")
            # Keep track of how long this takes.
            save_start = time.clock()

            if self.tick_count % 60 == 0:
                pybc.science.start_timer("sync")

            # Sync the blockchain to disk. This needs to lock the blockchain, so
            # the blockchain must never wait on the peer while holding its lock.
            # Hence the complicated deferred callback system. TODO: replace the
            # whole business with events.
            self.blockchain.sync()

            # Sync the known peers to disk
            self.known_peers.sync()

            if self.tick_count % 60 == 0:
                pybc.science.stop_timer("sync")

            # How long did it take?
            save_end = time.clock()

            logging.info("Saved to disk in {:.2} seconds".format(save_end -
                                                                 save_start))

            # Count this tick as having happened
            self.tick_count += 1

            # Tick again later
            reactor.callLater(self.tick_period, self.tick)

            logging.info("Tick complete.")

    def announce_block(self, block_hash):
        """
        Tell all of our connected peers about a block we have.
        """

        with self.lock:
            for connection in self.connections:
                # Send an INV message with the hash of the thing we have, in
                # case they want it.
                connection.send_message(["INV", bytes2string(block_hash)])

    def announce_transaction(self, transaction_hash):
        """
        Tell all of our connected peers about a transaction we have.
        """

        with self.lock:
            for connection in self.connections:
                # Send a TXINV message with the hash of the thing we have, in
                # case they want it.
                connection.send_message(["TXINV", bytes2string(
                    transaction_hash)])

    def was_block_valid(self, block_hash, status):
        """
        Called when a block we received becomes verifiable. Takes the block
        hash and a status of True if the block was valid, or False if it
        wasn't.

        """

        if status:
            # Tell all our peers about this awesome new block
            self.announce_block(block_hash)
        else:
            # Re-poll for blocks when we get a chance. Maybe it was too far in
            # the future or something.
            self.set_repoll()

    def was_transaction_valid(self, transaction_hash, status):
        """
        Called when a transaction is verified and added to the Blockchain's
        collection of transactions (i.e. those which one might want to include
        in a block), or rejected. Status is True for valid transactions, and
        false for invalid ones.

        Broadcasts transactions which are valid.
        """

        if status:
            # The transaction was valid. Broadcast it.
            self.announce_transaction(transaction_hash)

    def send_block(self, block):
        """
        Given a (possibly new) block, will add it to our blockchain and send it
        on its way to all peers, if appropriate.

        """

        if self.blockchain.needs_block(block.block_hash()):
            # It's something the blockchain is interested in.
            # Queue the block, and, if valid, announce it
            self.blockchain.queue_block(block,
                                        callback=self.was_block_valid)

        if self.state_download_timer is not None:
            try:
                # We started a timer earlier. Cancel it if it hasn't run
                self.state_download_timer.cancel()
            except BaseException:                # It probably already happened
                pass

        # In a little bit, if thre are no new blocks before then, download
        # StateComponents that we need (if any)
        self.state_download_timer = reactor.callLater(0.5,
                                                      self.request_state_components)

    def send_transaction(self, transaction):
        """
        Given a transaction bytestring, will put it in our queue of transactions
        and send it off to our peers, if appropriate.

        """
        logging.info('Sending transaction of %d bytes:\n{}'.format(len(str(transaction))))
        # Add the transaction, and, if valid, announce it
        self.blockchain.add_transaction(transaction,
                                        callback=self.was_transaction_valid)

    def request_state_components(self):
        """
        Ask all our peers for any StateComponents that our Blockchain needs, and
        that we have not recently requested.

        """

        with self.lock:
            if not self.blockchain.state_available:
                # We need to ask for StateComponents from our peers until we get
                # all of them.
                for requested_component in \
                        self.blockchain.get_requested_state_components():

                    if (requested_component in
                            self.recently_requested_state_components):

                        # We just asked for this one
                        continue

                    logging.debug("Requesting StateComponent {} from all "
                                  "peers".format(bytes2string(requested_component)))

                    # Compose just one message per request
                    message = ["GETSTATE", bytes2string(requested_component)]

                    for connection in self.connections:
                        # Send it to all peers. Hopefully one or more of them
                        # will send us a StateComponent back.
                        connection.send_message(message)

                    # Remember having asked for this component
                    self.recently_requested_state_components.add(
                        requested_component)

    def run(self):
        """
        Run the Twisted reactor and actually make this peer do stuff. Never
        returns.

        Exists so people using our module don't need to touch Twisted directly.
        They can just do their own IPC and keep us in a separate process.

        """

        reactor.run()
