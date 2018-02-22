"""
Block.py: contains the Block class.

"""

import hashlib
import struct
import time
import logging
import traceback

import pybc.util


class Block(object):
    """
    Represents a block in a blockchain. Can hold some data and calculate its own
    hash.

    Can be pruned down to just a proof chain header, discarding everything but
    previous hash, body hash, and nonce. The nonce isn't in the original mini-
    blockchain proposal, but having it lets us use a different proof of work
    scheme from the hash scheme used to identify blocks, which is a requirement
    of the PyBC PowAlgorithm architecture.

    """

    def __init__(self, previous_hash, body_hash=None, nonce=None):
        """
        Make a new block with the given previous block header hash. If you
        specify a body_hash, the block is allowed to remain as just a header
        (pervious hahs and body hash), with no actual body data.

        If you don't specify a body hash, or if you have new body data, you can
        use add_body() (or body_from_bytes()) to set it. If you don't, the block
        will serialize down to just a header. If you do, it will serialize to a
        whole block with payload.

        To remove the body again, call remove_body().

        A nonce can be specified if one is known; otherwise, one will have to be
        worked out from proof of work before the block will be serializeable.

        """

        # Save the previous hash
        self.previous_hash = previous_hash

        # Store the nonce if specified, or None if we still need to find a valid
        # nonce.
        self.nonce = nonce

        # Save the body hash
        self.body_hash = body_hash

        # Say we don't have a body yet
        self.has_body = False

        # Say we haven't had our body explicitly discarded locally yet
        self.body_discarded = False

    def add_body(self, target, height, state_hash, payload,
                 timestamp=int(time.time())):
        """
        Add a body to the block, by providing a difficulty target, block height,
        system state hash, payload, and timestamp. If no timestamp is provided,
        the current time is used.

        """

        # A body has been added
        self.has_body = True

        # Save the target
        self.target = target

        # Save the height
        self.height = height

        # Save the payload
        self.payload = payload

        # Save the state hash
        self.state_hash = state_hash

        # Save the timestamp
        self.timestamp = timestamp

        # Hash the body bytestring (which is now fully specified) and save that
        # hash in the header.
        self.body_hash = hashlib.sha512(self.body_to_bytes()).digest()

    def remove_body(self):
        """
        Remove all the body data from the block.

        """

        # We threw out the body on purpose.
        self.body_discarded = True

        if self.has_body:
            # The body fields are filled, so we can safely del them.
            self.has_body = False

            del self.target
            del self.height
            del self.payload
            del self.state_hash
            del self.timestamp

            # We keep the body hash, since we need that in the header.

    def body_to_bytes(self):
        """
        If the block has its body, return a bytestring containing the body data.
        Otherwise, if the body has been discarded, return None.

        You can't do this until you have a nonce for the block, or if the block
        hasn't had a body added.

        """

        # The block body has:
        # The block difficulty target (64 bytes)
        # The block height in the chain (8 bytes)
        # The block timestamp (8 bytes)
        # The hash of the current system state
        # The payload itself (unspecified length)

        return "".join([self.target, struct.pack(">Q", self.height),
                        struct.pack(">Q", self.timestamp), self.state_hash, self.payload])

    def body_from_bytes(self, bytestring):
        """
        Given a bytestring representing a packed block body (as from
        body_to_bytes), unpack the body and add it to the current block.

        """

        # Define the layout for the fixed-length data we're unpacking: an 8-byte
        # unsigned nonce, a 64-byte target string, an 8-byte unsigned height, an
        # 8-byte timestamp, and a 64-byte state hash
        layout = ">64sQQ64s"

        # Unpack the block body
        target, height, timestamp, state_hash = \
            struct.unpack_from(layout, bytestring)

        # Grab the payload
        payload = bytestring[struct.calcsize(layout):]

        # Add the block body, with all its fields. Order is different since
        # stuff we might leave optional (timestamp) is last in the argument
        # list.
        self.add_body(target, height, state_hash, payload, timestamp)

    def to_bytes(self):
        """
        Return the block as a byte string. Including the nonce, which must be
        filled in.

        Relies on the body_hash field having been filled in, either from
        previous deserialization or from having a body added.

        """

        # A block is a sequence of bytes with a header and a body.
        # The header has:
        # The nonce (8 bytes)
        # The hash of the previous block (SHA-512, 64 bytes)
        # The hash of the body (SHA-512, 64 bytes)
        # The body is serialized by body_to_bytes, and may not be present.

        # We put the nonce at the front so that the header happens to match what
        # the default PoW algorithm hashes, and thus our block hashes happen to
        # be the same as our PoW hashes when using that algorithm.

        # This holds all the parts to join up
        parts = [struct.pack(">Q", self.nonce), self.previous_hash,
                 self.body_hash]

        if self.has_body:
            # We need to add in the body data
            parts.append(self.body_to_bytes())

        return "".join(parts)

    @classmethod
    def from_bytes(cls, bytestring):
        """
        Make a new Block from the given bytestring. Uses the entire bytestring.

        Returns the Block, or None if the block could not be unpacked.

        """
        try:

            # Define the layout for the header we're unpacking: 8 byte unsigned
            # int (nonce) and two 64-byte strings (previous hash and body hash)
            layout = ">Q64s64s"

            # Unpack the block header
            nonce, previous_hash, body_hash = \
                struct.unpack_from(layout, bytestring)

            # Get the body data, which comes after the header and runs to the
            # end of the block.
            body_bytes = bytestring[struct.calcsize(layout):]

            # Make a new block with header filled in
            block = cls(previous_hash, body_hash=body_hash, nonce=nonce)

            if len(body_bytes) > 0:
                # We also have some data that must be the body. Unpack and add
                # that.
                block.body_from_bytes(body_bytes)

            # Give it back as our deserialized block
            return block

        except BaseException:            # Block is malformed and could not be unpacked

            logging.error("Malformed block")
            logging.error(traceback.format_exc())

            return None

    def block_hash(self):
        """
        Hash the header (including the body hash) to get the block's full hash,
        as referenced by other blocks. This is not always going to be the same
        as the PoW hash, depending on the PoW algorithm used, but that hash
        never actually has to be stored.

        """

        return hashlib.sha512("".join([struct.pack(">Q", self.nonce),
                                       self.previous_hash, self.body_hash])).digest()

    def do_work(self, algorithm):
        """
        Fill in the block's nonce by doing proof of work sufficient to meet the
        block's target (lower is harder) using the given PowAlgorithm. Fills in
        the block's nonce.

        """

        # Fill in the nonce so that hashing it with the previous hash and the
        # body hash will produce a proof of work hash that meets the target.
        self.nonce = algorithm.do_work(self.target, "".join([self.previous_hash,
                                                             self.body_hash]))

    def do_some_work(self, algorithm, iterations=10000):
        """
        Try to fill in the block's nonce, starting from the given placeholder,
        and doing at most the given number of iterations.

        Returns True if we succeed, or False if we need to run again.
        """

        if self.nonce is None:
            self.nonce = 0

        # Run the algorithm
        success, self.nonce = algorithm.do_some_work(self.target,
                                                     "".join([self.previous_hash, self.body_hash]),
                                                     placeholder=self.nonce, iterations=iterations)

        # TODO: we will pretend to be solved when we aren't in __str__, since we
        # set nonce to a number.

        # Return whether we succeeded
        return success

    def verify_work(self, algorithm):
        """
        Returns True if the block's currently set nonce is sufficient to meet
        the block's filled-in target under the given algorithm.

        This does not mean that the block is valid: you still need to make sure
        the block's payload is legal, and that the target the block uses is
        correct.

        """

        # Just ast the algorithm if the nonce is good enough for the target, on
        # our data_hash.
        return algorithm.verify_work(self.target, "".join([self.previous_hash,
                                                           self.body_hash]), self.nonce)

    def get_work_points(self, algorithm):
        """
        Returns the approximate number of proof-of-work "points" represented by
        this block. If the proof of work function is one that requires a hash
        below a threshold, this is probably going to be a function of the number
        of leading zeros, but we leave it up to the PowAlgorithm to do the
        actual calculation.

        Returns a long Python integer which may be quite big.

        """

        return algorithm.points("".join([self.previous_hash, self.body_hash]),
                                self.nonce)

    def __str__(self):
        """
        Print this block in a human-readable form.

        """

        # This holds all the lines we want to include
        lines = []

        if self.nonce is None:
            # Block hasn't been solved yet
            lines.append("----UNSOLVED BLOCK----")
        else:
            lines.append("----SOLVED BLOCK----")
            lines.append("Block hash: {}".format(
                pybc.util.bytes2string(self.block_hash())))
            lines.append("Nonce: {}".format(self.nonce))

        lines.append("Previous hash: {}".format(pybc.util.bytes2string(
            self.previous_hash)))
        lines.append("Body hash: {}".format(pybc.util.bytes2string(
            self.body_hash)))

        if self.has_body:
            # We can also put the body
            lines.append("Height {}".format(self.height))
            lines.append("Timestamp: {}".format(pybc.util.time2string(
                self.timestamp)))

            # Block hash isn't less than target. The hash of the block header under
            # the blockchain's POW algorithm is less than target. So don't line them
            # up and be misleading.
            lines.append("Target: {}".format("".join("{:02x}".format(ord(char))
                                                     for char in self.target)))

            lines.append("State hash: {}".format(pybc.util.bytes2string(
                self.state_hash)))

            # No need to dump the payload, probably.
            lines.append("<{} byte payload>".format(len(self.payload)))

        else:
            # We threw out the body of the block, keeping only the header.
            lines.append("<Body Trimmed>")

        return "\n".join(lines)
