"""
Blockchain.py: contains the Blockchain class.

"""

from __future__ import absolute_import
import hashlib
import struct
import time
import threading
import collections
import logging
import traceback

from pybc.Block import Block
from pybc.State import State
from pybc.StateMachine import StateMachine
import pybc.util
import pybc.science
from . import sqliteshelf
import six
from six.moves import range


class Blockchain(object):
    """
    Represents a Blockchain that uses a particular PowAlgorithm. Starts with a
    genesis block (a block that has its previous hash set to 64 null bytes), and
    contains a list of blocks based on that genesis block. Responsible for
    verifying block payloads and that the rules respecting target updates are
    followed.

    We also keep an in-memory dict of transactions, represented as bytestrings.
    We include logic to verify transactions against the blockchain, but
    transactions are not actually put into blocks.

    We also keep a State that describes some collated state data over all
    previous blocks that new blocks might want to know about.

    """

    def __init__(self, algorithm, store_filename, state,
                 minification_time=None):
        """
        Given a PoW algorithm, a filename in which to store block data (which
        may get an extension appended to it) and a State object to use (which
        internally is responsible for loading itself from some file), make a
        Blockchain.

        If a minification_time is specified, minify blocks that are burried
        deeper than that number of blocks.

        """

        # Set up our retargeting logic. We retarget so that it takes
        # retarget_time to generate retarget_period blocks. This specifies a 1
        # minute blocktime.
        self.retarget_time = 600
        self.retarget_period = 10

        # Remember whether we're minifying blocks by discarding their bodies,
        # and, if so, at what depth
        self.minification_time = minification_time

        if not self.minification_time > self.retarget_period:
            # We won't have the block we need to retarget from when it's time to
            # retarget.
            logging.warning("Minification time of {} no greater than retarget "
                            " period of {}, so we will not be able to check difficulty "
                            "retargets or mine retarget blocks.".format(
                                self.minification_time, self.retarget_period))

        # Keep the PowAlgorithm around
        self.algorithm = algorithm

        # Keep a database of all blocks by block hash.
        self.blockstore = sqliteshelf.SQLiteShelf(store_filename,
                                                  table="blocks", lazy=True)

        # Keep a database for longest-fork data (really a table in the same
        # database; sqlite3 makes multiple accesses to the same database OK)
        self.fork_data = sqliteshelf.SQLiteShelf(store_filename,
                                                 table="fork", lazy=True)

        # Remember the store filename for periodic filesize checkups
        self.store_filename = store_filename

        # Keep the highest Block around, so we can easily get the top of the
        # highest fork.
        self.highest_block = None

        # We keep the highest block's hash in the fork database under "highest"
        if "highest" in self.fork_data:
            self.highest_block = self.blockstore[self.fork_data["highest"]]

        # Keep a list of block hashes by height in our current fork, for
        # efficient access by height.
        self.hashes_by_height = []

        # We keep that in the fork data too
        if "hashes_by_height" in self.fork_data:
            self.hashes_by_height = self.fork_data["hashes_by_height"]

        # We need a lock so we can be a monitor and thus thread-safe
        self.lock = threading.RLock()

        # This is a dict of lists of pending blocks by the hash we need to
        # verify them, and then by their own hash (to detect duplicates)
        self.pending_on = collections.defaultdict(dict)

        # This is a dict of callbacks by pending block hash
        self.pending_callbacks = {}

        # This holds our pending transactions as bytestrings by hash.
        self.transactions = {}

        # This keeps the State at the tip of the longest fork. It should have
        # automatically loaded itself from a file. TODO: What if the state gets
        # out of sync with the blockchain when we kill the program?
        self.state = state

        # This keeps a list of listener functions to call with block and state
        # changes.
        self.listeners = []

        # This keeps track of whether the state is actually correct, or whether
        # we had to cross a mini-block and need to redownload it. It starts out
        # available if we have no blocks.
        self.state_available = True

        if "state_available" in self.fork_data:
            self.state_available = self.fork_data["state_available"]

        # This holds a StateMachine that we will set up if our State ever
        # becomes unavailable. It will take the old, outdated State and download
        # the parts it is missing and bring it up to date. When our State is
        # available, this is None.
        self.state_machine = None

        if not self.state_available:
            # Our Sate was unavailable when we stopped last time, so we need to
            # invalidate it again to get a new StateMachine.
            self.invalidate_state()

            if self.highest_block is not None:
                # Tell the StateMachine to start downloading the state for our
                # current highest block, if we have one.
                self.state_machine.download(self.highest_block.state_hash)
            else:
                # Somehow we marked our State invalid even though we rightly
                # should have the pre-genesis State, since we know no highest
                # block.
                raise Exception("We know our State is invalid, but we don't "
                                "have a highest block that we need to get State for.")

        # This keeps the state at the tip of the longest fork, plus any pending
        # transactions.
        self.transaction_state = self.state.copy()

        # Start a timer measuring how long it takes us to download the
        # blockchain.
        pybc.science.start_timer("blockchain_download")

    def has_block(self, block_hash):
        """
        Return True if we have the given block, and False otherwise.

        """

        with self.lock:
            # Lock since sqliteshelf isn't thread safe
            return block_hash in self.blockstore

    def needs_block(self, block_hash):
        """
        Return True if we need to get the given block, False otherwise.

        We can have blocks and still need to get them if, for example, we only
        have the mini version and it hasn't been burried deeply enough.

        """

        with self.lock:
            if not self.has_block(block_hash):
                # We don't have this block, so we need it
                return True

            else:
                # Load the block
                block = self.blockstore[block_hash]

                if not block.has_body and not block.body_discarded:
                    # We don't have the body, but we didn't intentionally drop
                    # it. So we need it.
                    return True
                else:
                    # We used to have the body, but we threw it out.
                    return False

    def get_block(self, block_hash):
        """
        Return the block with the given hash. Raises an error if we don't have
        it.

        """

        with self.lock:
            # Lock since sqliteshelf isn't thread safe
            return self.blockstore[block_hash]

    def get_block_count(self):
        """
        Return the number of blocks we know about (not just the number in the
        longest chain).

        """

        return len(self.blockstore)

    def get_block_locator(self):
        """
        Returns a list of block hash bytestrings starting with the most recent
        block in the longest chain and going back, with exponentially fewer
        hashes the futher back we go. However, we make sure to include the 10
        most recent blocks.

        """

        # We do need to lock because this is a complicated traversal. We can't
        # for example, switch threads in the middle of this.
        with self.lock:

            # This holds the list of hashes we use
            locator = []

            # This holds the step we use for how far to go back after including
            # each block.
            step = 1

            # This holds our position in the longest chain, from the genesis
            # block
            position = len(self.hashes_by_height) - 1

            while position > 0:
                # Grab the hash
                locator.append(self.hashes_by_height[position])

                # Go back by the recommended step
                position -= step

                if len(locator) > 10:
                    # After the 10 most recent hashes, start doubling the step
                    # size.
                    step *= 2

            # Always include the genesis block, if available
            if len(self.hashes_by_height) > 0:
                locator.append(self.hashes_by_height[0])

            return locator

    def blocks_after_locator(self, locator_hashes):
        """
        Takes a "block locator" in the form of a list of hashes. The first
        hash is the most recent block that another node has, and subsequent
        hashes in the locator are the hashes of earlier blocks, with exponential
        backoff.

        We proceed back through our longest fork until we find a block that the
        remote node mentions (or we get to the genesis block), and return a list
        of the hashes of each of the blocks proceeding upwards from there, in
        forward order.

        """

        # Complicated traversal: need to lock.
        with self.lock:

            # Process the locator hashes into a set for easy membership checking
            mentioned = set(locator_hashes)

            # This holds whether we found a block they mentioned. If we do find
            # one, we can update them from there. If not, we will have to start
            # from our genesis block.
            found = False

            for block_hash, index_from_end in enumerate(reversed(
                    self.hashes_by_height)):

                # Go through the longest chain backwards
                if block_hash in mentioned:
                    # This block was mentioned by them. We can update them from
                    # here.
                    found = True
                    break

            if found:
                # Get the index from the start of the list of the earliest block
                # they have not heard of (the block after index_from_end).
                # Because of Python indexing, we don't need to add 1 here.
                index = len(self.longest_chain) - index_from_end
            else:
                # Start from our genesis block. We didn't find anything they
                # mentioned.
                index = 0

            # Return a list of all the hashes from that point onwards
            return self.hashes_by_height[index:]

    def make_block(self, next_state, payload):
        """
        Create a block that would, if solved, put the system into the given next
        state, and add the given payload onto the longest chain.

        Does not verify the payload.

        Returns None if the Blockchain is not up to date with the current system
        state and thus not able to mine.

        """

        with self.lock:

            if not self.state_available:
                # We can't mine without the latest State
                return None

            if not self.next_block_target_available(self.highest_block):
                # We're up to date with the blockchain, but we don't know what
                # the next target should be. Probably we don't have the block we
                # need the time from to compute retargeting.
                return None

            if self.highest_block is None:
                # This has to be a genesis block. Don't fill in a body hash or
                # nonce yet.
                new_block = Block("\0" * 64)

                # Now give it a body with the target, height, state hash, and
                # payload
                new_block.add_body(self.next_block_target(None), 0,
                                   next_state.get_hash(), payload)
            else:
                # We're adding on to an existing chain.

                # Even if our clock is behind the timestamp of the block, don't
                # try to generate a block timestamped older than the parent
                # block, because that would be invalid.
                min_timestamp = self.highest_block.timestamp

                # Make a new block without filling body hash or nonce
                new_block = Block(self.highest_block.block_hash())

                # Add the body, including previous block hash, height, state
                # hash, payload, and a timestamp that will hopefully be valid to
                # the network even if our clock is off.
                new_block.add_body(self.next_block_target(self.highest_block),
                                   self.highest_block.height + 1, next_state.get_hash(),
                                   payload, timestamp=max(int(time.time()), min_timestamp))

            return new_block

    def dump_block(self, block):
        """
        Turn a Block into a string. If your Blockchain has interesting info in
        the payload (like transactions), override this.

        """

        return str(block)

    def can_verify_block(self, next_block):
        """
        Return True if we can determine whether the given block is valid, based
        on the blocks we already have. Returns False if we don't have the parent
        blocks needed to verify this block.

        """

        with self.lock:
            # We're going to touch our databases, so we have to lock.

            if next_block.previous_hash == "\0" * 64:
                # It's a genesis block. We can always check those.
                return True

            # The block store never contains any blocks we can't verify, so if
            # we have the parent, we can verify this block.
            return next_block.previous_hash in self.blockstore

    def verify_block(self, next_block):
        """
        Return True if the given block is valid based on the parent block it
        references, and false otherwise. We can't just say new blocks are
        invalid if a longer chain exists, though, because we might be getting a
        new chain longer than the one we have.

        Do not call this unless can_verify_block() is true for the block.

        You probably want to override verify_payload instead of this.

        """

        with self.lock:

            if not next_block.has_body:
                # It's a mini-block.
                if self.minification_time is None:
                    # We aren't running with mini blocks. Don't accept any.
                    logging.warning("Mini-blocks not allowed in standard "
                                    "blockchain.")
                    return False

                elif next_block.previous_hash == "\0" * 64:
                    # We always need to accept mini genesis blocks
                    return True
                elif not self.blockstore[next_block.previous_hash].has_body:
                    # We also always need to accept mini-blocks on top of other
                    # mini-blocks
                    return True
                else:
                    # We can run a special set of checks to validate mini-
                    # blockchain blocks. They only have a nonce, previous_hash,
                    # and state_hash.

                    # Most of the time we need to assume mini-blocks are valid:
                    # we don't have their state changes, so we can't say their
                    # state hashes are wrong, and we don't have their
                    # difficulty, so we can't say their nonces aren't good
                    # enough. So if someone comes alogn with a new mini fork, we
                    # just have to keep it.

                    # TODO: We *could* check difficulty levels if it was within
                    # the retargeting period of somewhere where we know what the
                    # difficulty should be (a genesis mini-block, or a non-mini
                    # block). Check in those cases.

                    # However, we can say mini-bocks are invalid if they are on
                    # top of blocks that are too recent to have ben minified. If
                    # we are current with the latest full block, we shouldn't
                    # accept a mini-block on top of it. We should only accept a
                    # mini-block on top of a full block if we're plausibly a
                    # whole blockchain cycle behind.

                    # This check is necessarily heuristic, but it will only
                    # complain that mini-blocks are invalid for at most a bit
                    # less than a cycle's worth of real time. And it will only
                    # say legitimate mini-blocks are invalid if this node has
                    # gotten an entire cycle's-worth of time behind in much less
                    # time than a cycle should have taken. And if we do
                    # eventually say bogus mini-blocks are valid on top of real
                    # blocks, we will learn otherwise when we make contact with
                    # the main chain.

                    # Basically, this check prevents someone from broadcasting a
                    # bogus mini-block and then a real block saying whatever
                    # they want, and convincing all the miners currently mining
                    # that they have gotten behind and need to skip ahead to the
                    # new bogus block.

                    # How old does the parent block have to be before we believe
                    # there should be mini-blocks on top of it? Say half of a
                    # blockchain cycle if we're generating blocks at the optimum
                    # rate. If you go half a blockchain cycle's worth of time
                    # without any new blocks, too bad.
                    min_age_for_miniblocks = 0.5 * self.minification_time * \
                        self.retarget_time / self.retarget_period

                    now = int(time.time())

                    # How old is the parent?
                    parent_age = (now -
                                  self.blockstore[next_block.previous_hash].timestamp)

                    if parent_age < min_age_for_miniblocks:
                        # Parent too young to have a mini block on it.
                        logging.warning("Mini-block not allowed on parent that "
                                        "is only {}/{} seconds old".format(parent_age,
                                                                           min_age_for_miniblocks))
                        return False

                    else:
                        # The parent is old enough for a mini-block to be on top
                        # of it. Not really much else to check. TODO: minimum
                        # work?

                        return True

            # If we get here, we know we're not checking a mini-block.

            if ((next_block.height == 0) !=
                    (next_block.previous_hash == "\0" * 64)):
                # Genesis blocks must have height 0 and a previous hash of all
                # 0s. If we have exactly one of those things, the block is
                # invalid.
                logging.warning("Genesis block height and hash are mismatched.")
                return False

            # Get the previous block, or None if this is a genesis block
            previous_block = None
            if next_block.height != 0:
                # This isn't a genesis block, so load its parent, which we must
                # have. (Otherwise can_verify_block would be false.)
                previous_block = self.blockstore[next_block.previous_hash]

            # Get the state after it.
            state = self.state_after(previous_block)
            if state is not None:
                # We have the previous state, so we can check if this block steps
                # forwards correctly.
                try:
                    state.step_forwards(next_block)
                except BaseException:                    # We didn't get to the state we were supposed to
                    logging.warning(traceback.format_exc())
                    logging.warning("Block claims to move to incorrect state.")
                    return False

            now = int(time.time())
            if next_block.timestamp > (now + 10 * 60):
                # The block is from more than 10 minutes in the future.
                logging.warning("Block is from too far in the future: {} vs "
                                "{}".format(pybc.util.time2string(next_block.timestamp),
                                            pybc.util.time2string(now)))
                return False

            if (previous_block is not None and previous_block.has_body and
                    previous_block.timestamp > next_block.timestamp):
                # The block is trying to go back in time.
                logging.warning("Block is timestamped earlier than parent.")
                return False

            if (previous_block is not None and previous_block.has_body and
                    next_block.height != previous_block.height + 1):
                # The block is not at the correct height (1 above its parent)
                logging.warning("Block height incorrect.")
                return False

            if (self.next_block_target_available(previous_block) and
                    next_block.target != self.next_block_target(previous_block)):
                # We have some idea of what the target should be next, and this
                # block is lying about it.

                # The block isn't valid if it cheats at targeting.
                logging.warning("Block target incorrect. Should be {}".format(
                    pybc.util.bytes2hex(self.next_block_target(
                        previous_block))))
                return False

            if not next_block.verify_work(self.algorithm):
                # The block also isn't valid if the PoW isn't good enough
                logging.warning("Block PoW isn't correct.")
                return False

            if not self.verify_payload(next_block):
                # The block can't be valid if the payload isn't.
                logging.warning("Block payload is invalid.")
                return False

            # Block is valid
            logging.debug("Block is valid")
            return True

    def verify_payload(self, next_block):
        """
        Return True if the payload of the given next block is valid, and false
        otherwise.

        Should be overridden to define payload logic. The default implementation
        accepts any payloads.

        """

        return True

    def next_block_target_available(self, previous_block):
        """
        Return True if we can calculate the appropriate proof of work target for
        the block after the given Block, or False if we can't.

        If the given block is None, the next block is a genesis block, so we can
        calculate the target.

        Otherwise, we need previous_block to be unminified. And if
        previous_block is at a height that is a multiple of
        self.retarget_period, we need the block self.retarget_period blocks
        before that to be unminified.

        """

        if previous_block is None:
            # We know it for genesis blocks
            return True

        elif not previous_block.has_body:
            # Can't get block target on top of a mini block
            return False
        elif (previous_block.height > 0 and previous_block.height %
              self.retarget_period == 0):

            # We need to d a retargeting. We also need the block retarget_period
            # ago to be unminified.

            # Go get the time of the block retaregt_preiod blocks ago
            block = previous_block
            for _ in range(self.retarget_period):
                # Go back a block retarget_period times.
                # We always have all the blocks, so this will work.
                block = self.blockstore[block.previous_hash]

            if not block.has_body:
                # We won't be able to know how long the blocks took
                return False

        # If we get here, we have our parent unminified and, if needed, we also
        # have the block retarget_period before that unminified.
        return True

    def get_average_block_time(self):
        """
        Compute and return the average block time for the last retarget_period
        blocks, if possible. If not possible, return None.

        """

        with self.lock:

            if len(self.hashes_by_height) < self.retarget_period:
                # We don't have blocks old enough.

                return None

            # What block hash do we want to get the timestamp from?
            old_block_hash = self.hashes_by_height[-self.retarget_period]

            # What Block is it?
            old_block = self.blockstore[old_block_hash]

            if not old_block.has_body:
                # We dropped the timestamp, or don't have it
                return None

            # What time is it?
            now = int(time.time())

            # The average block time is the time since the first block divided
            # by the number of blocks. Return that.
            return float(now - old_block.timestamp) / self.retarget_period

    def next_block_target(self, previous_block):
        """
        Get the PoW target (64 bytes) that the next block must use, based on the
        given previous block Block object (or None).

        The prevous block may not be a mini-block.

        Should be overridden to define PoW difficulty update logic.
        """

        # Lock since we use the blockstore
        with self.lock:

            if previous_block is None:
                # No blocks yet, so this is the starting target. You get a 0 bit
                # as the first bit instead of a 1 bit every other hash. So to
                # get n leading 0 bits takes on average 2^n hashes. n leading
                # hex 0s takes on average 16^n hashes.
                return struct.pack(">Q", 0x00000fffffffffff) + "\xff" * 56
            else:
                # Easy default behavior: re-target every 10 blocks to a rate of
                # 10 block per minute, but don't change target by more than
                # 4x/0.25x

                if (previous_block.height > 0 and
                        previous_block.height % self.retarget_period == 0):
                    # This is a re-target block. It's on a multiple of
                    # retarget_period and not the genesis block.

                    # Go get the time of the block retaregt_preiod blocks ago
                    block = previous_block
                    for _ in range(self.retarget_period):
                        # Go back a block retarget_period times.
                        # We always have all the blocks, so this will work.
                        block = self.blockstore[block.previous_hash]

                    if not block.has_body:
                        # We can't measure how long the last set of blocks took,
                        # because the block before then has been minified and
                        # lost its timestamp.
                        raise Exception("Block {}, which we need to calculate "
                                        "retarget time, has been minified.".format(
                                            pybc.bytes2string(block.block_hash())))

                    old_time = block.timestamp
                    new_time = previous_block.timestamp

                    # We want new_time - old_time to be retarget_time seconds.
                    time_taken = new_time - old_time
                    ideal_time = self.retarget_time

                    logging.debug("{} blocks took {}, should have taken "
                                  "{}".format(self.retarget_period, time_taken,
                                              ideal_time))

                    # At constant hashrate, the generation rate scales linearly
                    # with the target. So if we took a factor of x too long,
                    # increasing the target by a factor of x should help with
                    # that.
                    factor = float(time_taken) / ideal_time

                    logging.debug("Want to scale generation rate by {}".format(
                        factor))

                    # Don't scale too sharply.
                    if factor > 4:
                        factor = 4
                    if factor < 0.25:
                        factor = 0.25

                    logging.debug("Will actually scale by: {}".format(factor))

                    # Load the target as a big int
                    old_target = pybc.util.bytes2long(previous_block.target)

                    logging.debug("{} was old target".format(
                        pybc.util.bytes2hex(previous_block.target)))

                    # Multiply it
                    new_target = int(old_target * factor)

                    logging.debug("new / old = {}".format(new_target /
                                                          old_target))
                    logging.debug("old / new = {}".format(old_target /
                                                          new_target))

                    new_target_bytes = pybc.util.long2bytes(new_target)

                    while len(new_target_bytes) < 64:
                        # Padd to the appropriate length with nulls
                        new_target_bytes = "\0" + new_target_bytes
                    if len(new_target_bytes) > 64:
                        # New target would be too long. Don't change
                        logging.debug("No change because new target is too "
                                      "long.")
                        return previous_block.target

                    logging.debug("{} is new target".format(pybc.util.bytes2hex(
                        new_target_bytes)))

                    return new_target_bytes

                else:
                    # If it isn't a retarget, don't change the target.
                    return previous_block.target

    def switch_forks(self, new_tip):
        """
        Switch forks from the current fork in self.highest_block and
        self.hashes_by_height to the one with the tip Block new_tip. The new
        fork may be higher or lower than the old one in absolute block count,
        but must be higher in work points.

        Make sure self.hashes_by_height has all the hashes of the blocks
        on the new fork, and that these changes are sent to the fork database.

        Also, change our State.

        If we need to cross mini-blocks in order to get to the new fork, we
        can't just walk our current state there. Our State will then be marked
        for re-download.

        """

        # Strategy:
        # Change our State.
        # Find the common ancestor of highest_block and new_tip
        # Make sure hashes_by_height has enough spots
        # Fill them in from new_tip back to the common ancestor.

        # This is incredibly complicated
        with self.lock:

            # Get the sate we should have. If the State can't be calculated,
            # this will return None
            new_state = self.state_after(new_tip, notify=True)

            if new_state is None:
                # We're trying to change forks over mini-blocks. We can't take
                # our state with us. Say we need to download a new state, and
                # that nobody should use this one until then.
                self.invalidate_state()
            else:
                # Keep the new state
                self.state = new_state

            # Find the common ancestor
            ancestor = self.common_ancestor(new_tip, self.highest_block)

            if ancestor is None:
                # Go back through the whole list, replacing the genesis block.
                ancestor_hash = "\0" * 64
            else:
                # Go back only to the block on top of the common ancestor.
                ancestor_hash = ancestor.block_hash()

            # Make sure hashes_by_height is big enough

            while len(self.hashes_by_height) <= new_tip.height:
                # Make empty spots in the hashes by height list until
                # hashes_by_height[new_tip.height] is a valid location.
                self.hashes_by_height.append(None)

            while len(self.hashes_by_height) > new_tip.height + 1:
                # We are switching over to a fork that's lower in actual blocks
                # but higher in points. Trim hashes_by_height to be exactly the
                # right height.
                self.hashes_by_height.pop()

            # Now go back through the blocks in the new fork, filling in
            # hashes_by_height.

            # This holds the block we are to put in next
            position = new_tip

            # And its height
            position_height = new_tip.height

            while (position is not None and
                   position.block_hash() != ancestor_hash):
                # For every block on the new fork back to the common ancestor,
                # stick its hash in the right place in hashes by height.
                self.hashes_by_height[position_height] = position.block_hash()

                if (self.minification_time is not None and
                    len(self.hashes_by_height) - position_height >
                        self.minification_time):
                    # This block (whether it's already mini or not) is deep
                    # enough for explicit minification. Record that.

                    logging.warning("Minifying block {} burried at height "
                                    "{} vs tip {}".format(
                                        pybc.bytes2string(position.block_hash()),
                                        position_height, len(self.hashes_by_height)))

                    # A block burried this deep ought to be minified, and this
                    # one isn't. Take care of that.
                    position.remove_body()
                    # Store the minified block back in the block store.
                    self.blockstore[position.block_hash()] = position

                if position.previous_hash != "\0" * 64:
                    # Go back to the previous block and do it
                    position = self.blockstore[position.previous_hash]
                    position_height -= 1
                else:
                    # We've processed the genesis block and are done.
                    position = None

            # Save our hashes by height changes to the fork database, pending a
            # sync.
            self.fork_data["hashes_by_height"] = self.hashes_by_height

    def queue_block(self, next_block, callback=None):
        """
        We got a block that we think goes in the chain, but we may not have all
        the previous blocks that we need to verify it yet.

        Put the block into a receiving queue.

        If the block is eventually verifiable, call the callback with the hash
        and True if it's good, or the hash and False if it's bad.

        If the same block is queued multiple times, and it isn't immediately
        verifiable, only the last callback for the block will be called.

        If the block is valid but we already have it, and the new block isn't an
        improvement on the version we have (i.e. it's a mini-block when we
        already have that mini-block, or it's a body for a block we threw out
        the body for), does not call the callback at all.

        """

        # This holds all the callbacks we need to call, so we can call them
        # while we're not holding the lock. It's a list of function, argument
        # tuple tuples.
        to_call = []

        with self.lock:

            if self.minification_time is None and not next_block.has_body:
                # We know right away that we don't want to accept this block.

                logging.debug("Rejecting mini-block on normal blockchain.")

                if callback is not None:
                    # Fire the callback off right away, since there's only one
                    callback(next_block.block_hash(), False)

                # Skip out on the rest of the function. Don't put it in the
                # queue, since even if we get its parent it won't be acceptable.
                return

            if self.has_block(next_block.block_hash()):
                # We already have a version of this block. Grab it.
                old_version = self.blockstore[next_block.block_hash()]

                if not next_block.has_body or old_version.body_discarded:
                    # Skip this block because either it's a mini-block for
                    # something we already have, or it's a body for a block we
                    # threw out the body of.

                    # Don't call the callback at all.
                    return

            # This is the stack of hashes that we have added to the blockchain.
            # We need to check what blocks are wauiting on them.
            added_hashes = []

            if self.can_verify_block(next_block):
                # We can verify it right now
                if self.verify_block(next_block):
                    # The block is good!
                    self.add_block(next_block)

                    if callback is not None:
                        # Later, call the callback.
                        to_call.append((callback, (next_block.block_hash(),
                                                   True)))

                    if next_block.has_body:
                        logging.info("Block height {} immediately verified: "
                                     "{}".format(next_block.height,
                                                 pybc.util.bytes2string(next_block.block_hash())))
                    else:
                        logging.info("Mini-block immediately verified: "
                                     "{}".format(pybc.util.bytes2string(
                                         next_block.block_hash())))

                    # Record that we added the block
                    added_hashes.append(next_block.block_hash())
                else:
                    logging.warning("Invalid block:\n{}".format(self.dump_block(
                        next_block)))
                    if callback is not None:
                        # Later, call the callback.
                        to_call.append((callback, (next_block.block_hash(),
                                                   False)))
            else:
                # Add this block to the pending blocks for its parent. If it's
                # already there, we just replace it
                self.pending_on[next_block.previous_hash][
                    next_block.block_hash()] = next_block
                # Remember the callback for this block, which chould be called
                # when it is verified.
                self.pending_callbacks[next_block.block_hash()] = callback

                if next_block.has_body:
                    # We can report the hash
                    logging.debug("Block height {}, hash {} pending on parent "
                                  "{}".format(next_block.height,
                                              pybc.util.bytes2string(next_block.block_hash()),
                                              pybc.util.bytes2string(next_block.previous_hash)))
                else:
                    # Say we have a pending mini-block
                    logging.debug("Mini-block hash {} pending on parent "
                                  "{}".format(
                                      pybc.util.bytes2string(next_block.block_hash()),
                                      pybc.util.bytes2string(next_block.previous_hash)))

            while len(added_hashes) > 0:
                # There are blocks that we have added, but we haven't checked
                # for other blocks pending on them. Do that.

                # Pop off a hash to check
                hash_added = added_hashes.pop()
                # Get the dict of waiters by waiter hash
                waiters = self.pending_on[hash_added]

                # Remove it
                del self.pending_on[hash_added]

                logging.debug("{} waiters were waiting on {}".format(
                    len(waiters), pybc.util.bytes2string(hash_added)))

                for waiter_hash, waiter in six.iteritems(waiters):
                    # We ought to be able to verify and add each waiter.

                    # Get the callback
                    waiter_callback = self.pending_callbacks[waiter_hash]

                    # Remove it from the collection of remaining callbacks
                    del self.pending_callbacks[waiter_hash]

                    if self.can_verify_block(waiter):
                        # We can verify the block right now (ought to always be
                        # true)
                        if self.verify_block(waiter):
                            # The block is good! Add it
                            self.add_block(waiter)

                            if waiter_callback is not None:
                                # Call the callback later
                                to_call.append((waiter_callback,
                                                (waiter_hash, True)))

                            if waiter.has_body:
                                logging.info("Queued block height {} verified: "
                                             "{}".format(waiter.height,
                                                         pybc.util.bytes2string(waiter_hash)))
                            else:
                                logging.info("Queued mini-block verified: "
                                             "{}".format(pybc.util.bytes2string(
                                                 waiter_hash)))

                            # Record that we added the pending block, so things
                            # pending on it can now be added
                            added_hashes.append(waiter_hash)
                        else:
                            # TODO: throw out blocks waiting on invalid blocks.
                            # If we have any of those, there's probablt a hard
                            # fork.

                            logging.warning("Queued block invalid: {}".format(
                                pybc.util.bytes2string(waiter_hash)))

                            if waiter_callback is not None:
                                # Call the callback later
                                to_call.append((waiter_callback, (waiter_hash,
                                                                  False)))
                    else:
                        # This should never happen
                        logging.error("Couldn't verify a waiting block {} when "
                                      "its parent came in!".format(
                                          pybc.util.bytes2string(waiter_hash)))

        # Now we're out of the locked section.
        logging.debug("Dispatching {} block validity callbacks.".format(len(
            to_call)))
        for callback, args in to_call:
            # Call all the callbacks, in case they need to get a lock that
            # another thread has and that thread is waiting on this thread.
            callback(*args)

    def state_after(self, block, notify=False):
        """
        Given that our State is currently up to date with our current
        highest_block, return a copy of our current State, walked to after the
        given block. This copy can be updated safely.

        block may be None, in which case we produce the State before the genesis
        block.

        Walks the blockchain from the tip of the highest fork to the given
        block, which must be in the block store.

        If notify is True, dispatches "backward" events for each block walked
        backward, and "forward" events for each block walked forward.

        If we need to cross mini-blocks to get to the given block, return None
        instead of a State.

        TODO: can we do real pathfinding?

        """

        with self.lock:

            if not self.state_available:
                # We have no State that we can walk anywhere.
                return None

            # What's the hash of the block?
            if block is not None:
                block_hash = block.block_hash()
            else:
                block_hash = "\0" * 64

            if self.highest_block is None:
                if block is None:
                    # We have no blocks, and we want the state after no blocks.
                    # This is easy.
                    return self.state.copy()
                elif block.has_body:
                    logging.debug("Making after-genesis state")
                    # Easy case: this must be a full genesis block. If it had
                    # any ancestors, they would be longer than our zero-length
                    # longest fork. Use the current (empty) state updated with
                    # the new block, which exists and has a body.
                    state = self.state.copy()
                    state.step_forwards(block)
                    if notify:
                        self.send_event("forward", block)
                    return state
                else:
                    # We have a mini-block on top of our genesis state. We don't
                    # know what the state after that should be.
                    return None

            if block_hash == self.highest_block.block_hash():
                logging.debug("Using current state.")
                # We already have the state after this
                return self.state.copy()

            if (block is not None and
                    block.previous_hash == self.highest_block.block_hash()):

                if block.has_body:
                    logging.debug("Using parent state")
                    # Special case: this new block comes directly after our old
                    # one.

                    # Advance the State
                    state = self.state.copy()
                    state.step_forwards(block)
                    if notify:
                        self.send_event("forward", block)

                    # Return it
                    return state
                else:
                    # Block comes directly after our old top block, but we can't
                    # take the state there because it's a mini-block.
                    return None

            logging.debug("Walking blockchain for state")
            # If we get here, we know we have a highest block, and that we need
            # to walk from there to the block we're being asked about.

            # How many blocks did we walk?
            blocks_walked = 0

            # Find the common ancestor of this block and the tip, where we have
            # a known State.
            ancestor = self.common_ancestor(block, self.highest_block)

            if ancestor is None:
                # This block we want the state after is on a completely
                # different genesis block.

                # Go back until the state after nothing, and then go forward
                # again.
                ancestor_hash = "\0" * 64
            else:
                # Go back until the state after the common ancestor, and then go
                # forward again.
                ancestor_hash = ancestor.block_hash()

            logging.debug("Rewinding to common ancestor {}".format(
                pybc.bytes2string(ancestor_hash)))

            # Walk the State back along the longest fork to the common ancestor
            # (which may be the current top block).

            # TODO: Is there a more efficient way to do this?

            # This holds our scratch state
            state = self.state.copy()

            # This holds the hash of the block we're on
            position = self.highest_block.block_hash()

            logging.debug("Starting from {}".format(pybc.bytes2string(
                position)))

            while position != ancestor_hash:
                # Until we reach the common ancestor...

                if not self.blockstore[position].has_body:
                    # We can't cros this mini-block with out State
                    logging.debug("Need to cross mini-block on our fork")
                    return None

                logging.debug("Walking back to {} at height {}".format(
                    pybc.bytes2string(self.blockstore[position].previous_hash),
                    self.blockstore[position].height - 1))

                # Undo the current block
                state.step_backwards(self.blockstore[position])

                if notify:
                    self.send_event("backward", self.blockstore[position])

                # Step back a block
                position = self.blockstore[position].previous_hash
                blocks_walked += 1

                if position != "\0" * 64 and self.blockstore[position].has_body:
                    # We can check the current State hash against the hash we're
                    # supposed to have.
                    if state.get_hash() != self.blockstore[position].state_hash:
                        # We stepped back and got an incorrect state. This
                        # should never happen because these blocks have already
                        # been validated.

                        self.state.audit()

                        raise Exception("Stepped back into wrong state after "
                                        "block {}".format(pybc.bytes2string(position)))

            # Now we've reverted to the post-common-ancestor state.

            # Now apply all the blocks from there to block in forwards order.
            # First get a list of them
            blocks_to_apply = []

            if block is None:
                # We want the state before any blocks, so start at no blocks and
                # go back to the common ancestor (which also ought to be no
                # blocks).
                position = "\0" * 64
            else:
                # We want the state after a given block, so we have to grab all
                # the blocks between it and the common ancestor, and then run
                # them forwards.
                position = block.block_hash()

            while position != ancestor_hash:
                # For each block back to the common ancestor... (We know we
                # won't go off the start of the blockchain, since ancestor is
                # known to actually be a common ancestor hash.)

                if not self.blockstore[position].has_body:
                    # We can't cros this mini-block with out State
                    logging.debug("Need to cross mini-block on other fork")
                    return None

                # Collect the blocks on the path from block to the common
                # ancestor.
                blocks_to_apply.append(self.blockstore[position])

                # Step back a block
                position = self.blockstore[position].previous_hash
                blocks_walked += 1

            # Flip the blocks that need to be applied into chronological order.
            blocks_to_apply.reverse()

            for block_to_apply in blocks_to_apply:

                logging.debug("Walking forwards to {} at height {}".format(
                    pybc.bytes2string(block_to_apply.block_hash()),
                    block_to_apply.height))

                # Apply the block to the state
                state.step_forwards(block_to_apply)

                if notify:
                    self.send_event("forward", block_to_apply)

            logging.info("Walked {} blocks".format(blocks_walked))

            # We've now updated to the state for after the given block.
            return state

    def genesis_block_for(self, block):
        """
        Return the genesis block for the given Block in the blockstore.

        """

        while block.previous_hash != "\0" * 64:
            # This isn't a genesis block. Go back.
            block = self.blockstore[block.previous_hash]

        return block

    def common_ancestor(self, block_a, block_b):
        """
        Get the most recent common ancestor of the two Blocks in the blockstore,
        or None if they are based on different genesis blocks.

        Either block_a or block_b may be None, in which case the common ancestor
        is None as well.

        """

        # This is incredibly complicated, so lock the blockchain data
        # structures.
        with self.lock:

            if block_a is None or block_b is None:
                # Common ancestor with None is always None (i.e. different
                # genesis blocks).
                return None

            # This holds our position on the a branch.
            position_a = block_a.block_hash()

            # This holds all the hashes we visited tracing back from a
            hashes_a = set(position_a)

            # This holds our position on the b branch.
            position_b = block_b.block_hash()

            # This holds all the hashes we visited tracing back from b
            hashes_b = set(position_b)

            # If we do get all the way back to independent genesis blocks, what
            # are they?
            genesis_a = None
            genesis_b = None

            while position_a != "\0" * 64 or position_b != "\0" * 64:
                # While we haven't traced both branches back to independent
                # genesis blocks...
                if position_a != "\0" * 64:
                    # Trace the a branch back further, since it's not off the
                    # end yet.

                    if self.blockstore[position_a].previous_hash == "\0" * 64:
                        # We found a's genesis block
                        genesis_a = self.blockstore[position_a]

                    # Move back a step on the a branch
                    position_a = self.blockstore[position_a].previous_hash
                    hashes_a.add(position_a)

                    if position_a != "\0" * 64 and position_a in hashes_b:
                        # We've found a common ancestor. Return the block.
                        return self.blockstore[position_a]

                if position_b != "\0" * 64:
                    # Trace the b branch back further, since it's not off the
                    # end yet.

                    if self.blockstore[position_b].previous_hash == "\0" * 64:
                        # We found b's genesis block
                        genesis_b = self.blockstore[position_b]

                    # Move back a step on the b branch
                    position_b = self.blockstore[position_b].previous_hash
                    hashes_b.add(position_b)

                    if position_b != "\0" * 64 and position_b in hashes_a:
                        # We've found a common ancestor. Return the block.
                        return self.blockstore[position_b]

            if genesis_a.block_hash() == genesis_b.block_hash():
                # Double-check the independence of the independent genesis
                # blocks.
                raise Exception("Stepped back all the way to independent "
                                "genesis blocks that were actually the same")

            # We've hit independent genesis blocks. There is no common
            # ancestor, so return None.
            return None

    def add_block(self, next_block):
        """
        Add a block as the most recent block in the blockchain. The block must
        be valid, or an Exception is raised.

        """

        # This is complicated. Lock the blockchain
        with self.lock:

            if self.verify_block(next_block):
                # Tag the block with its cumulative PoW difficulty, in points
                points = next_block.get_work_points(self.algorithm)

                if next_block.previous_hash != "\0" * 64:
                    # We need to add in the points from the block this is on top
                    # of. We know we added a cumulative points field already.
                    points += self.blockstore[next_block.previous_hash].points

                # Tack on the points field. It never goes over the network; we
                # just use it locally to work out which fork we belong on.
                next_block.points = points

                # Put the block in the block store
                self.blockstore[next_block.block_hash()] = next_block

                if (next_block.has_body and (self.highest_block is None or
                                             next_block.points > self.highest_block.points)):

                    # We know that this new block we just added is not a mini-
                    # block, so we can switch to it.

                    logging.debug("Switching to new top block")

                    # This new block is higher (in total work points) than the
                    # previously highest block. This means we want to change to
                    # it. Note that doing it this way creates a more well-
                    # defined way to resolve competing blocks hat both want to
                    # be the end of the chain: you should take the one with the
                    # most points. It also means that someone can come along
                    # with a super-great block that forks off hlfway down the
                    # chain and make everyone switch over to that. However, the
                    # expected work you would need to find that would be greater
                    # than all the work done on the old fork, so it's just as
                    # hard to do as coming along with a longer chain (i.e. still
                    # a 51% attack).

                    if (self.highest_block is not None and
                        next_block.previous_hash !=
                            self.highest_block.block_hash()):

                        logging.debug("Switching forks")

                        # We had an old highest block, but we need to switch
                        # forks away from it.

                        # This may involve replacing a big part of our
                        # hashes_by_height list and updating our State in a
                        # complex way. We have a function for this.
                        self.switch_forks(next_block)

                    elif (next_block.previous_hash != "\0" * 64 and
                          not self.blockstore[next_block.previous_hash].has_body):
                        # This is the first non-mini block since the genesis
                        # block. We need to fill in hashes_by_height, and note
                        # that we lack a valid State currently, since we had to
                        # cross mini-blocks to get from genesis to here.

                        logging.debug("Switching to first real block after "
                                      "mini-genesis block")

                        while (len(self.hashes_by_height) <
                               next_block.height + 1):
                            # Make enough slots in hashes_by_height
                            self.hashes_by_height.append(None)

                        # We need a position to walk back and fill in
                        # hashes_by_height.
                        position = next_block.block_hash()

                        # And a height since we're crossing mini-blocks
                        height = next_block.height

                        while position != "\0" * 64:
                            # Fill in the correct hashes_by_height spot
                            self.hashes_by_height[height] = position
                            # What block are we on now?
                            block = self.blockstore[position]
                            # Go to its parent
                            position = block.previous_hash
                            height -= 1

                        # Save the updated hashes_by_height
                        self.fork_data["hashes_by_height"] = \
                            self.hashes_by_height

                        # Say we lack a state
                        self.invalidate_state()

                    else:
                        # This is a direct child of the old highest block, or a
                        # new genesis block when we didn't have one before.

                        logging.debug("Switching to child of old top block")

                        # Put this block on the end of our hashes by height list
                        self.hashes_by_height.append(next_block.block_hash())
                        # And save that back to the fork database, pending a
                        # sync.
                        self.fork_data["hashes_by_height"] = \
                            self.hashes_by_height

                        if (self.minification_time is not None and
                            len(self.hashes_by_height) >
                                self.minification_time):

                            # There are enough blocks that we should start
                            # minifying old ones. What block should we minify?
                            to_minify = self.blockstore[self.hashes_by_height[
                                -self.minification_time - 1]]

                            logging.warning("Minifying block {} at depth "
                                            "{}".format(pybc.bytes2string(
                                                to_minify.block_hash()),
                                                self.minification_time))

                            # Minify the block
                            to_minify.remove_body()

                            # Save it back
                            self.blockstore[to_minify.block_hash()] = to_minify

                        if self.state_available:
                            # We know the last State, so we should keep it
                            # current.

                            # Update the State in place with a simple step.
                            # There can't be any other State copies floating
                            # around at this point (we don't call state_after,
                            # since we decided not to use switch_forks).
                            self.state.step_forwards(next_block)

                            # Notify our listeners of a new block
                            self.send_event("forward", next_block)

                    # Set the highest block to the new block.
                    self.highest_block = next_block

                    # Put the new highest block's hash into the fork database
                    # "under highest".
                    self.fork_data["highest"] = self.highest_block.block_hash()

                    # We sync to disk periodically; we want to avoid syncing to
                    # disk after every block. This means that States may need to
                    # use their slow shallow copy of shallow copy path for a
                    # while until the periodic commit timer ticks, but it's much
                    # faster than syncing on every downloaded block.

                    # TODO: Separate committing (get off the potentially
                    # O(updates since last commit) copy of copy path) and
                    # syncing (write all blocks, fork data, and state to disk).

                    if self.state_available:
                        # Now there is a new block on the longest chain, and we
                        # are up to date with its State. Throw out all
                        # transactions that are now invalid on top of it.

                        # First, make a clean new State for verifying
                        # transactions against.
                        self.transaction_state = self.state.copy()

                        # Keep a list of the hashes of invalid transactions that
                        # don't make it after this block. Note that transactions
                        # are tested in arbitrary order here, not the order we
                        # saw them or an order that will make the most valid or
                        # anything. This means everything may be slow if
                        # transactions on the same block can vary in validity by
                        # order.
                        invalid_transaction_hashes = []

                        for tr_hash, transaction in six.iteritems(self.transactions):
                            if not self.verify_transaction(transaction,
                                                           self.highest_block, self.transaction_state,
                                                           advance=True):

                                # We only see the transactions that don't make
                                # it. The others quietly update
                                # transaction_state, so when new transactions
                                # come in it will reflect the state they have to
                                # deal with.

                                # Mark this transaction as invalid.
                                invalid_transaction_hashes.append(tr_hash)

                        # Now self.transaction_state is up to date with all the
                        # queued transactions.

                        # Then, remove all the invalid transactions we found.
                        for transaction_hash in invalid_transaction_hashes:
                            del self.transactions[transaction_hash]

                        logging.info("Dropped {} invalid queued "
                                     "transactions".format(len(
                                         invalid_transaction_hashes)))

                    else:
                        # There is a new full block on the longest chain, but we
                        # aren't up to date with our State. Tell our
                        # StateMachine that it needs to download the State for
                        # this block, potentially interrupting its old download,
                        # but re-using some of its parts.
                        self.state_machine.download(
                            self.highest_block.state_hash)

                    # So now we have a new full top block. Can we call the
                    # blockchain "downloaded"?

                    # How old is he block
                    block_age = time.time() - next_block.timestamp

                    if (block_age < 2 * float(self.retarget_time) /
                            self.retarget_period):

                        # The block is less than two average block times old.
                        # Call the blockchain downloaded.
                        pybc.science.stop_timer("blockchain_download")

            else:
                # Block we tried to add failed verification. Complain.
                raise Exception("Invalid block (current state {}): {}".format(
                    pybc.util.bytes2string(self.state.get_hash()),
                    self.dump_block(next_block)))

    def sync(self):
        """
        Save all changes to the blockstore to disk. Since the blockstore is
        always in a consistent internal state when none of its methods are
        executing, just call this periodically to make sure things get saved.

        """

        with self.lock:
            # TODO: Implement a state after cache. Clear it here.

            # Save the state. Invalidates any shallow copies, and probably
            # confuses anyone iterating over it.
            self.state.commit()
            # Save the actual blocks. Hopefully these are in the same SQLite
            # database as the state, so they can't get out of sync.
            self.blockstore.sync()
            # Save the metadata about what fork we're on, which depends on
            # blocks. TODO: It's in the same database as the blockstore, so this
            # is redundant; everything goes through the same underlying
            # connection and uses the same transaction.
            self.fork_data.sync()

            # Tell all our listeners to save to disk so there is less risk of
            # getting out of sync with us and needing a reset.
            self.send_event("sync", None)

    def longest_chain(self):
        """
        An iterator that goes backwards through the currently longest chain to
        the genesis block.

        """
        # Locking things in generators is perfectly fine, supposedly.
        with self.lock:

            # This is the block we are currently on
            current_block = self.highest_block
            if current_block is None:
                return

            yield current_block

            # This holds the hash of the prevous block
            previous_hash = current_block.previous_hash

            while previous_hash != "\0" * 64:
                # While the previous hash is a legitimate block hash, keep
                # walking back.
                current_block = self.blockstore[previous_hash]
                yield current_block
                previous_hash = current_block.previous_hash

    def verify_transaction(self, transaction_bytes, chain_head, state,
                           advance=False):
        """
        Returns True if the given transaction is valid on top of the given block
        (which may be None), when the system is in the given State. Valid
        transactions are broadcast to peers, while invalid transactions are
        discarded.

        State may be None, in which case only the well-formedness of the
        transaction is verified.

        If advance is true, advances the State with the transaction, if the
        State supports it and the transaction is valid.

        *Technically* we really ought to only look at the state, but some things
        (like the current height) are easy to get from blocks.

        We need to be able to tell if a transaction is valid on non-longest
        forks, because otherwise we won't be able to verify transactions in
        blocks that are making up a fork that, once we get more blocks, will
        become the longest fork. (The default Blockchain implementation doesn't
        actually store transactions in blocks, but we need to have a design that
        supports it.)

        Along with verify_payload, subclasses probably ought to override this to
        specify application-specific behavior.

        """

        return True

    def transaction_valid_for_relay(self, transaction):
        """
        Returns True if we should accept transactions like the given transaction
        from peers, False otherwise.

        If you are making a system where block generators put special
        transactions into blocks, you don't want those transactions percolating
        through the network and stealing block rewards.

        """

        return True

    def get_transaction(self, transaction_hash):
        """
        Given a transaction hash, return the transaction (as a bytestring) with
        that hash. If we don't have the transaction, return None instead of
        throwing an error (in case the transaction gets removed, perhaps by
        being added to a block).

        """
        with self.lock:
            if transaction_hash in self.transactions:
                return self.transactions[transaction_hash]
            else:
                return None

    def get_transactions(self):
        """
        Iterate over all pending transactions as (hash, Transaction object)
        tuples.

        """

        with self.lock:
            for transaction_hash, transaction in six.iteritems(self.transactions):
                yield transaction_hash, transaction

    def has_transaction(self, transaction_hash):
        """
        Return True if we have the transaction with the given hash, and False
        otherwise. The transaction may go away before you can call
        get_transaction.

        """

        # No need to lock. This is atomic and hits against an in-memory dict
        # rather than a persistent one.
        return transaction_hash in self.transactions

    def add_transaction(self, transaction, callback=None):
        """
        Called when someone has a transaction to give to us. Takes the
        transaction as a string of bytes. Only transactions that are valid in
        light of currently queued transactions are acepted.

        Calls the callback, if specified, with the transaction's hash and its
        validity (True or False). If the transaction is not something we are
        interested in, doesn't call the callback at all.

        We don't queue transactions waiting on the blocks they depend on, like
        we do blocks, because it doesn't matter if we miss having one.

        If the transaction is valid, we will remember it by hash.

        If the blockchain is not up to date with the State for the current top
        block, no new transactions will be accepted.

        """

        with self.lock:
            # Hash the transaction
            transaction_hash = hashlib.sha512(transaction).digest()

            if transaction_hash in self.transactions:
                # We already know about this one. Don't bother trying to verify
                # it. It won't verify twice, and will just produce console spam.
                return

            if len(self.transactions) >= 100:
                # This is too many. TODO: make this configurable
                logging.info("Rejecting transaction due to full queue")
                return

            if not self.state_available:
                # We can't trust our stored state, or the transaction_state that
                # comes from it.
                verified = False
            elif self.verify_transaction(transaction, self.highest_block,
                                         self.transaction_state, advance=True):

                # The transaction is valid in our current fork.
                # Keep it around.
                self.transactions[transaction_hash] = transaction

                # Our transaction_state has automatically been advanced.

                # Record that it was verified
                verified = True

            else:
                # Record that it wasn't verified.
                verified = False
                logging.warn('Invalid transaction: {}'.format(pybc.util.bytes2string(transaction_hash)))

        # Notify the callback outside the critical section.
        if callback is not None:
            callback(transaction_hash, verified)

    def invalidate_state(self):
        """
        Mark the current State as unavailable, and set up a StateMachine that
        can be used to bring it up to date.

        While state_available is False, our State will not change, so it's OK
        for the StateMachine to use it as a local source of StateComponents
        during the download process.

        """
        with self.lock:
            # Mark the State as stale and unuseable by anyone
            self.state_available = False

            # Save this, pending a sync.
            self.fork_data["state_available"] = self.state_available

            # Make the old State make us a StateMachine that uses it as a local
            # store and uses the appropriate StateComponent for deserialization.
            self.state_machine = self.state.make_state_machine()

            # At some point we will need to fill in the root that we need to
            # download.
            logging.info("Invaidated current State; need to re-download")

    def validate_state(self):
        """
        Check that the current State is correct for the top block that we are
        on, and mark it as available, discarding any StateMachine we have. The
        current highest_block may not be None.

        """

        with self.lock:

            if self.state.get_hash() != self.highest_block.state_hash:
                logging.critical("Downloaded state hash: {}".format(
                    pybc.bytes2string(self.state.get_hash())))
                logging.critical("Expected state hash: {}".format(
                    pybc.bytes2string(self.highest_block.state_hash)))
                raise Exception("Downloaded invalid or wrong state!")

            # Say our State is valid
            self.state_available = True

            # Save that
            self.fork_data["state_available"] = self.state_available

            # Discard the StateMachine
            self.state_machine = None

            logging.info("Successfully updated to state {}".format(
                pybc.bytes2string(self.state.get_hash())))

            # Tell our listeners about our newly downloaded state
            self.send_event("reset", self.state)

    def get_requested_state_components(self):
        """
        If the State is currently unavailable, get a set of StateComponents that
        we need to download. This set is guaranteed not to be modified.

        Otherwise, return an empty set.

        """

        with self.lock:
            if self.state_available:
                # We catually don't need anything
                return set()

            # Let the StateMachine think about what it wants to download
            self.state_machine.tick()

            # Get the set of requests
            requests = self.state_machine.get_requests()

            logging.debug("Currently trying to get {} StateComponents".format(
                len(requests)))

            # Copy the set before returning it, in case new StateComponents come
            # in while the caller is working with it. It will never be very big.
            return set(requests)

    def get_state_hash(self):
        """
        Return the hash of the current State.

        """

        with self.lock:

            return self.state.get_hash()

    def get_state_component(self, component_hash):
        """
        Return the bytrestring for the component with the given hash, or None if
        we don't have one.

        """

        with self.lock:

            return self.state.get_component(component_hash)

    def add_state_component(self, component_bytestring):
        """
        Give a StateComponent bytestring to the Blockchain in order to try and
        re-build its out of date State.

        """

        with self.lock:

            if self.state_machine is not None:
                # Feed the component to the StateMachine
                self.state_machine.add_component(component_bytestring)

                # Let the StateMachine think about it, and potentially complete.
                self.state_machine.tick()

                if self.state_machine.is_done():
                    # The StateMachine is done! Re-build our State from it and
                    # get rid of it.

                    # The StateComponent must have been set to download the
                    # state for our current top block, which must exist.

                    # Update our State to be in sync with our current top block.
                    pybc.science.start_timer("state_update")
                    self.state.update_from_components(
                        self.state_machine.get_components(),
                        self.highest_block.state_hash)
                    pybc.science.stop_timer("state_update")

                    # Check it and save it as valid, discarding the StateMachine
                    self.validate_state()

            else:
                logging.warning("Disacrded StateComponent since we're not "
                                "downloading state.")

    def subscribe(self, listener):
        """
        Subscribe a listener to state changes on this Blockchain.

        Listener will be called with:
        "forward", block - State has been advanced forward with the given block

        "backward", block - State has been advanced backward with the given
        block

        "reset", state - State has been reset to a new, disconnected state

        "sync", None - Blockchain has saved state to disk, and things that
        depend on it should do likewise to avoid needing to walk all unspent
        outputs.

        The listener will be run under the Blockchain's lock, so it is safe to
        iterate over the state, if one is passed. However, it is not safe to
        look at fields of the Blockchain, as they may be in an inconsistent
        state.

        """

        with self.lock:
            # Add the listener to our list of listeners
            self.listeners.append(listener)

    def send_event(self, event, argument):
        """
        Dispatch an event to all listeners. Event should be an event name
        ("forward", "backward", "reset", or "sync") and argument should be a
        Block or State or None, as appropriate.

        """

        with self.lock:
            for listener in self.listeners:
                # Call the listener
                listener(event, argument)

    def get_disk_usage(self):
        """
        Return the disk uage of the Blockchain's blockstore database, in bytes.
        Generally, you also put your State's database in here too.

        """

        with self.lock:
            return self.blockstore.get_size()
