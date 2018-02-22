#!/usr/bin/env python2.7
# coin.py: a coin implemented on top of pybc

if __name__ == '__main__':
    import os.path as _p, sys
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

import struct
import hashlib
import traceback
import time
import threading
import logging
import itertools
import sys

try:
    import pyelliptic
except BaseException:    # pyelliptic didn't load. Either it's not installed or it can't find OpenSSL
    import emergency_crypto_munitions as pyelliptic

import util
import sqliteshelf
from AuthenticatedDictionary import AuthenticatedDictionary
from AuthenticatedDictionary import AuthenticatedDictionaryStateComponent
from State import State
from StateMachine import StateMachine
from TransactionalBlockchain import TransactionalBlockchain
from PowAlgorithm import PowAlgorithm
from transactions import pack_transactions, unpack_transactions


class Transaction(object):
    """
    Represents a transaction on the blockchain.

    A transaction is a list of inputs (represented by transaction hash, output
    index), a list of outputs (represented by amounts and destination public key
    hash), and a list of authorizations (public key, signature) signing the
    previous two lists. It also has a timestamp, so that two generation
    transactions to the same destination address won't have the same hash. (If
    you send two block rewards to the same address, make sure to use different
    timestamps!)

    Everything except public keys are hashed sha512 (64 bytes). Public keys are
    hashed sha256 (32 bytes).

    A transaction is properly authorized if all of the inputs referred to have
    destination hashes that match public keys that signed the transaction.

    A generation transaction (or fee collection transaction) is a transaction
    with no inputs. It thus requires no authorizations.

    Any input not sent to an output is used as a transaction fee, and added to
    the block reward.

    Has a to_bytes and a from_bytes like Blocks do.

    """

    def __init__(self):
        """
        Make a new Transaction with no inputs or outputs.

        """

        # Set the timestamp to the transaction's creation time (i.e. now).
        # Nobody actually verifies it, so it's really 8 arbitrary bytes.
        self.timestamp = int(time.time())

        # Make a list of input tuples (transaction hash, output index, amount,
        # destination).
        self.inputs = []

        # Make a list of output tuples (amount, destination public key hash)
        self.outputs = []

        # Make a list of authorization tuples (public key, signature of inputs
        # and outputs)
        self.authorizations = []

    def __str__(self):
        """
        Represent this transaction as a string.

        """

        # These are the lines we will return
        lines = []

        lines.append("---Transaction {}---".format(util.time2string(
            self.timestamp)))
        lines.append("{} inputs".format(len(self.inputs)))
        for transaction, index, amount, destination in self.inputs:
            # Put every input (another transaction's output)
            lines.append("\t{} addressed to {} from output {} of {}".format(
                amount, util.bytes2string(destination), index,
                util.bytes2string(transaction)))
        lines.append("{} outputs".format(len(self.outputs)))
        for amount, destination in self.outputs:
            # Put every output (an amount and destination public key hash)
            lines.append("\t{} to {}".format(amount,
                                             util.bytes2string(destination)))
        lines.append("{} authorizations".format(len(self.authorizations)))
        for public_key, signature in self.authorizations:
            # Put every authorizing key and signature.
            lines.append("\tKey: {}".format(util.bytes2string(public_key)))
            lines.append("\tSignature: {}".format(
                util.bytes2string(signature)))

        # Put the hash that other transactions use to talk about this one
        lines.append("Hash: {}".format(util.bytes2string(
            self.transaction_hash())))

        return "\n".join(lines)

    def transaction_hash(self):
        """
        Return the SHA512 hash of this transaction, by which other transactions
        may refer to it.

        """

        return hashlib.sha512(self.to_bytes()).digest()

    def add_input(self, transaction_hash, output_index, amount, destination):
        """
        Take the coins from the given output of the given transaction as input
        for this transaction. It is necessary to specify and store the amount
        and destination public key hash of the output, so that the blockchain
        can be efficiently read backwards.

        """

        self.inputs.append((transaction_hash, output_index, amount,
                            destination))

    def add_output(self, amount, destination):
        """
        Send the given amount of coins to the public key with the given hash.

        """

        self.outputs.append((amount, destination))

    def add_authorization(self, public_key, signature):
        """
        Add an authorization to this transaction by the given public key. The
        given signature is that key's signature of the transaction header data
        (inputs and outputs).

        Both public key and signature must be bytestrings.

        """

        self.authorizations.append((public_key, signature))

    def get_leftover(self):
        """
        Return the sum of all inputs minus the sum of all outputs.
        """

        # This is where we store our total
        leftover = 0

        for _, _, amount, _ in self.inputs:
            # Add all the inputs on the + side
            leftover += amount

        for amount, _ in self.outputs:
            # Add all the outputs on the - side
            leftover -= amount

        return leftover

    def verify_authorizations(self):
        """
        Returns True if, for every public key hash in the transaction's inputs,
        there is a valid authorization signature of this transaction by a public
        key with that hash.

        """

        # Get the bytestring that verifications need to sign
        message_to_sign = self.header_bytes()

        # This holds SHA256 hashes of all the pubkeys with valid signatures
        valid_signers = set()

        for public_key, signature in self.authorizations:
            # Check if each authorization is valid.
            if pyelliptic.ECC(pubkey=public_key).verify(signature,
                                                        message_to_sign):

                # The signature is valid. Remember the public key hash.
                valid_signers.add(hashlib.sha256(public_key).digest())

            else:
                logging.warning("Invalid signature!")
                # We're going to ignore extra invalid signatures on
                # transactions. What could go wrong?

        for _, _, _, destination in self.inputs:
            if destination not in valid_signers:
                # This input was not properly unlocked.
                return False

        # If we get here, all inputs were to destination pubkey hashes that has
        # authorizing signatures attached.
        return True

    def pack_inputs(self):
        """
        Return the inputs as a bytestring.

        """

        # Return the 4-byte number of inputs, followed by a 64-byte transaction
        # hash, a 4-byte output index, an 8 byte amount, and a 32 byte
        # destination public key hash for each input.
        return struct.pack(">I", len(self.inputs)) + "".join(
            struct.pack(">64sIQ32s", *source) for source in self.inputs)

    def unpack_inputs(self, bytestring):
        """
        Set this transaction's inputs to those encoded by the given bytestring.

        """

        # Start with a fresh list of inputs.
        self.inputs = []

        # How many inputs are there?
        (input_count,) = struct.unpack(">I", bytestring[0:4])

        # Where are we in the string
        index = 4

        for _ in xrange(input_count):
            # Unpack that many 108-byte records of 64-byte transaction hashes,
            # 4-byte output indices, 8-byte amounts, and 32-byte destination
            # public key hashes.
            self.inputs.append(struct.unpack(">64sIQ32s",
                                             bytestring[index:index + 108]))
            index += 108

    def pack_outputs(self):
        """
        Return the outputs as a bytestring.

        """

        # Return the 4-byte number of outputs, followed by an 8-byte amount and
        # a 32-byte destination public key hash for each output
        return struct.pack(">I", len(self.outputs)) + "".join(
            struct.pack(">Q32s", *destination) for destination in self.outputs)

    def unpack_outputs(self, bytestring):
        """
        Set this transaction's outputs to those encoded by the given bytestring.

        """

        # Start with a fresh list of outputs.
        self.outputs = []

        # How many outputs are there?
        (output_count,) = struct.unpack(">I", bytestring[0:4])

        # Where are we in the string
        index = 4

        for _ in xrange(output_count):
            # Unpack that many 40-byte records of 8-byte amounts and 32-byte
            # destination public key hashes.
            self.outputs.append(struct.unpack(">Q32s",
                                              bytestring[index:index + 40]))
            index += 40

    def pack_authorizations(self):
        """
        Return a bytestring of all the authorizations for this transaction.

        """

        # We have a 4-byte number of authorization records, and then pairs of 4
        # -byte-length and n-byte-data strings for each record.

        # This holds all our length-delimited bytestrings as we make them
        authorization_bytestrings = []

        for public_key, signature in self.authorizations:
            # Add the public key
            authorization_bytestrings.append(struct.pack(">I",
                                                         len(public_key)) + public_key)
            # Add the signature
            authorization_bytestrings.append(struct.pack(">I",
                                                         len(signature)) + signature)

        # Send back the number of records and all the records.
        return (struct.pack(">I", len(self.authorizations)) +
                "".join(authorization_bytestrings))

    def unpack_authorizations(self, bytestring):
        """
        Set this transaction's authorizations to those encoded by the given
        bytestring.

        """

        # Start with a fresh list of authorizations.
        self.authorizations = []

        # How many outputs are there?
        (authorization_count,) = struct.unpack(">I", bytestring[0:4])

        # Where are we in the string
        index = 4

        for _ in xrange(authorization_count):
            # Get the length of the authorization's public key
            (length,) = struct.unpack(">I", bytestring[index:index + 4])
            index += 4

            # Get the public key itself
            public_key = bytestring[index: index + length]
            index += length

            # Get the length of the authorization's signature
            (length,) = struct.unpack(">I", bytestring[index:index + 4])
            index += 4

            # Get the signature itself
            signature = bytestring[index: index + length]
            index += length

            # Add the authorization
            self.authorizations.append((public_key, signature))

    def header_bytes(self):
        """
        Convert the inputs and outputs to a bytestring, for signing and for use
        in our encoding.

        Packs timestamp in 8 bytes, length of the inputs in 4 bytes, inputs
        bytestring, length of the outputs in 4 bytes, outputs bytestring.

        """

        # Pack up the inputs
        inputs_packed = self.pack_inputs()
        # And pack up the outputs
        outputs_packed = self.pack_outputs()

        # Return both as length-delimited strings
        return "".join([struct.pack(">QI", self.timestamp, len(inputs_packed)),
                        inputs_packed, struct.pack(">I", len(outputs_packed)),
                        outputs_packed])

    def to_bytes(self):
        """
        Return this Transaction as a bytestring.

        Packs the inputs, outputs, and authorizations bytestrings as length-
        delimited strings.

        """

        # Pack the authorizations
        authorizations_packed = self.pack_authorizations()

        # Return the packed inputs and outputs length-delimited strings with one
        # for authorizations on the end.
        return "".join([self.header_bytes(), struct.pack(">I",
                                                         len(authorizations_packed)), authorizations_packed])

    @classmethod
    def from_bytes(cls, bytestring):
        """
        Make a new Transaction object from a transaction bytestring, as encoded
        by to_bytes.

        """

        # Make the transaction
        transaction = cls()

        # This holds the index we're unpacking the bytestring at
        index = 0

        # Get the timestamp
        (transaction.timestamp,) = struct.unpack(">Q",
                                                 bytestring[index:index + 8])
        index += 8

        # Get the length of the inputs bytestring
        (length,) = struct.unpack(">I", bytestring[index:index + 4])
        index += 4

        # Get the inputs bytestring
        inputs_bytestring = bytestring[index: index + length]
        index += length

        # Get the length of the outputs bytestring
        (length,) = struct.unpack(">I", bytestring[index:index + 4])
        index += 4

        # Get the outputs bytestring
        outputs_bytestring = bytestring[index: index + length]
        index += length

        # Get the length of the authorizations bytestring
        # TODO: It just runs until the end, so we don't really need this.
        (length,) = struct.unpack(">I", bytestring[index:index + 4])
        index += 4

        # Get the authorizations bytestring
        authorizations_bytestring = bytestring[index: index + length]
        index += length

        # Unpack all the individual bytestrings
        transaction.unpack_inputs(inputs_bytestring)
        transaction.unpack_outputs(outputs_bytestring)
        transaction.unpack_authorizations(authorizations_bytestring)

        # Return the complete Transaction
        return transaction


class CoinState(State):
    """
    A State that keeps track of all unused outputs in blocks. Can also be used
    as a generic persistent set of output tuples.

    """

    def __init__(self, unused_outputs=None, filename=None, table=None):
        """
        Make a new CoinState. If unused_outputs is specified, use that
        AuthenticatedDictionary to store the state. Otherwise, filename and
        table must be specified; load the state from an AuthenticatedDictionary
        with that database filename and table name.

        The AuthenticatedDictionary is used to store unused outputs. Unused
        outputs are internally identified by the hash of the transaction that
        created them (SHA512), the index of the output (int), the amount of the
        output (long), and the hash of the destination public key (SHA256);
        since these are all fixed length, they are just packed together into a
        single bytestring key. Outwardly, these are represented as tuples of the
        above.

        """

        if unused_outputs is not None:
            # This holds the set of unused outputs. Since it's an
            # AuthenticatedDictionary, we can cheaply copy it. And the copy has
            # already been supplied for us.
            self.unused_outputs = unused_outputs
        elif filename is not None and table is not None:
            # We need to make a new AuthenticatedDictionary pointing to the
            # appropriate database and table.
            self.unused_outputs = AuthenticatedDictionary(filename=filename,
                                                          table=table)
        else:
            # We need to get our data from somewhere.
            raise Exception("Cannot make a CoinState without either an "
                            "AuthenticatedDictionary to use or a database filename and "
                            "table name to load an AuthenticatedDictionary from.")

    def output2bytes(self, output):
        """
        Turn an unused output tuple of (transaction hash, output index, output
        amount, destination) into a bytestring.

        The transaction hash is a SHA512 hash of the transaction (64 bytes), the
        output index is an integer (4 bytes), the output amount is a long (8
        bytes), and the destination is a SHA256 hash (32 bytes).

        """

        return struct.pack(">64sIQ32s", *output)

    def bytes2output(self, bytes):
        """
        Turn a bytestring into a tuple of (transaction hash, output index,
        output amount, destination).

        The transaction hash is a SHA512 hash of the transaction (64 bytes), the
        output index is an integer (4 bytes), the output amount is a long (8
        bytes), and the destination is a SHA256 hash (32 bytes).

        """

        return struct.unpack(">64sIQ32s", bytes)

    def add_unused_output(self, output):
        """
        Add the given output tuple as an unused output.

        """

        # Add a record for it to the set of unspent outputs. We're using the
        # AuthenticatedDictionary as a set, so insert the value "".
        self.unused_outputs.insert(self.output2bytes(output), "")

    def remove_unused_output(self, output):
        """
        Remove the given output tuple as an unused output.

        """

        # Turn it into its unique bytestring and remove it.
        self.unused_outputs.remove(self.output2bytes(output))

    def apply_transaction(self, transaction):
        """
        Update this state by applying the given Transaction object. The
        transaction is assumed to be valid.

        """

        # Get the hash of the transaction
        transaction_hash = transaction.transaction_hash()

        logging.debug("Applying transaction {}".format(util.bytes2string(
            transaction_hash)))

        for spent_output in transaction.inputs:
            # The inputs are in exactly the same tuple format as we use.
            # Remove each of them from the unused output set.

            if not self.has_unused_output(spent_output):
                logging.error("Trying to remove nonexistent output: {} {} {} "
                              "{}".format(util.bytes2string(spent_output[0]),
                                          spent_output[1], spent_output[2],
                                          util.bytes2string(spent_output[3])))

                self.audit()

                # See if things just work out
            else:
                self.remove_unused_output(spent_output)

        for i, output in enumerate(transaction.outputs):
            # Unpack each output tuple
            amount, destination = output

            # Make a tupe for the full unused output
            unused_output = (transaction_hash, i, amount, destination)

            if self.has_unused_output(unused_output):
                logging.error("Trying to create duplicate output: {} {} {} "
                              "{}".format(util.bytes2string(unused_output[0]),
                                          unused_output[1], unused_output[2],
                                          util.bytes2string(unused_output[3])))

                self.audit()

                # See if things just work out
            else:
                self.add_unused_output(unused_output)

    def remove_transaction(self, transaction):
        """
        Update this state by removing the given Transaction object.

        """

        # Get the hash of the transaction
        transaction_hash = transaction.transaction_hash()

        logging.debug("Reverting transaction {}".format(util.bytes2string(
            transaction_hash)))

        for spent_output in transaction.inputs:
            # The inputs are in exactly the same tuple format as we use. Add
            # them back to the unused output set, pointing to our useless value
            # of "".

            if self.has_unused_output(spent_output):
                logging.error("Trying to create duplicate output: {} {} {} "
                              "{}".format(util.bytes2string(spent_output[0]),
                                          spent_output[1], spent_output[2],
                                          util.bytes2string(spent_output[3])))

                self.audit()

                # See if things just work out
            else:
                self.add_unused_output(spent_output)

        for i, output in enumerate(transaction.outputs):
            # Unpack each output tuple
            amount, destination = output

            # Make a tupe for the full unused output
            unused_output = (transaction_hash, i, amount, destination)

            if not self.has_unused_output(unused_output):
                logging.error("Trying to remove nonexistent output: {} {} {} "
                              "{}".format(util.bytes2string(unused_output[0]),
                                          unused_output[1], unused_output[2],
                                          util.bytes2string(unused_output[3])))

                # Audit ourselves
                self.audit()

                # See if things just work out
            else:
                # Remove its record from the set of unspent outputs
                self.remove_unused_output(unused_output)

    def step_forwards(self, block):
        """
        Add any outputs of this block's transactions to the set of unused
        outputs, and consume all the inputs.

        Updates the CoinState in place.
        """

        for transaction_bytes in unpack_transactions(
                block.payload):

            # Parse the transaction
            transaction = Transaction.from_bytes(transaction_bytes)

            self.apply_transaction(transaction)

        if self.get_hash() != block.state_hash:
            # We've stepped forwards incorrectly
            raise Exception("Stepping forward to state {} instead produced "
                            "state {}.".format(util.bytes2string(block.state_hash),
                                               util.bytes2string(self.get_hash())))

    def step_backwards(self, block):
        """
        Add any inputs from this block to the set of unused outputs, and remove
        all the outputs.

        Updates the CoinState in place.
        """

        if self.get_hash() != block.state_hash:
            # We're trying to step back the wrong block
            raise Exception("Stepping back block for state {} when actually in "
                            "state {}.".format(util.bytes2string(block.state_hash),
                                               util.bytes2string(self.get_hash())))

        logging.debug("Correctly in state {} before going back.".format(
            util.bytes2string(self.get_hash())))

        for transaction_bytes in reversed(list(unpack_transactions(
                block.payload))):

            # Parse the transaction
            transaction = Transaction.from_bytes(transaction_bytes)

            self.remove_transaction(transaction)

    def get_unused_outputs(self):
        """
        Yield each unused output, as a (transaction hash, index, amount,
        destination) tuple.

        Internally, goes through our AuthenticatedDict and parses out our key
        format.

        """

        for key in self.unused_outputs.iterkeys():
            yield self.bytes2output(key)

    def has_unused_output(self, output):
        """
        Returns true if the given unised output tuple of of (transaction hash,
        output index, output amount, destination) is in the current set of
        unused outputs, and false otherwise.

        """
        return self.unused_outputs.find(self.output2bytes(output)) is not None

    def copy(self):
        """
        Return a copy of the CoinState that can be independently operated on.
        This CoinState must have had no modifications made to it since its
        creation or last commit() operation. Modifications made to this
        CoinState will invalidate the copy and its descendents.

        """

        # Make a new CoinState, with its AuthenticatedDictionary a child of
        # ours.
        return CoinState(unused_outputs=self.unused_outputs.copy())

    def clear(self):
        """
        Reset the CoinState to no unused outputs. Works quickly, but
        invalidates all other copies of the CoinState.

        """

        # Clear the AuthenticatedDictionary so it will now be empty.
        self.unused_outputs.clear()

    def get_hash(self):
        """
        The hash for this state is just the root Merkle hash of the
        AuthenticatedDictionary.

        """

        return self.unused_outputs.get_hash()

    def get_component(self, component_hash):
        """
        Return the StateComponent with the given hash from this State, or None
        if no StateComponent with that hash exists in the State.

        All StateComponents are descendants of a StateComponent with the same
        hash as the State itself.

        """

        logging.debug("Getting component {}".format(util.bytes2string(
            component_hash)))

        # Get the node pointer for that StateComponent
        pointer = self.unused_outputs.get_node_by_hash(component_hash)

        if pointer is None:
            # We don't have anything with that hash.
            return None

        logging.debug("Pointer is {}".format(pointer))

        # Go get a StateComponent for the appropriate node.
        component = self.unused_outputs.node_to_state_component(pointer)

        for child_pointer, child_hash in itertools.izip(
                self.unused_outputs.get_node_children(pointer),
                component.get_child_list()):

            if (child_pointer is None) != (child_hash is None):
                raise Exception("Child without hash, or visa versa")

            if child_pointer is not None:
                logging.debug("Child pointer {} should have hash {}".format(
                    child_pointer, util.bytes2string(child_hash)))

                logging.debug("Actually has hash: {}".format(util.bytes2string(
                    self.unused_outputs.get_node_hash(child_pointer))))

                logging.debug("Actual pointer for hash: {}".format(
                    self.unused_outputs.get_node_by_hash(child_hash)))

        for child_hash in component.get_dependencies():
            if self.unused_outputs.get_node_by_hash(child_hash) is None:
                # We have a corrupted AuthenticatedDictionary which has nodes
                # but not their children.
                raise Exception("Node {} mising child {}".format(
                    util.bytes2string(component_hash),
                    util.bytes2string(child_hash)))

        # The component checks out. Return it.
        return component

    def update_from_components(self, state_components, root_hash):
        """
        Update the CoinState to the given rot hash, using the given dict by hash
        of extra StateComponents.

        """

        # Just pass the state components and root hash along to our
        # AuthenticatedDictionary.
        self.unused_outputs.update_from_state_components(state_components,
                                                         root_hash)

    def make_state_machine(self):
        """
        Create a StateMachine that knows how to deserialize StateCOmponents of
        the type we produce, and which uses us as a local StateComponent store.

        """

        return StateMachine(AuthenticatedDictionaryStateComponent, self)

    def audit(self):
        """
        Make sure the State is internally consistent.

        """

        # Audit our AuthenticatedDictionary
        self.unused_outputs.audit()

    def commit(self):
        """
        Mark this CoinState as the CoinState from which all future CoinStstes
        will be derived.

        """

        # Commit the underlying AuthenticatedDictionary
        self.unused_outputs.commit()


class CoinBlockchain(TransactionalBlockchain):
    """
    Represents a Blockchain for a Bitcoin-like currency.

    """

    def __init__(self, block_store, minification_time=None, state=None):
        """
        Make a new CoinBlockchain that stores blocks and state in the specified
        file. If a minification_time is specified, accept mini-blocks and throw
        out the bodies of blocks burried deeper than the minification time.

        """

        # Just make a new Blockchain using the default POW algorithm and a
        # CoinState to track unspent outputs. Store/load the state to/from the
        # "state" table of the blockstore database. Because the state and the
        # other blockstore components use the same database, they can't get out
        # of sync; the Blockchain promises never to sync its databases without
        # committing its State.
        super(CoinBlockchain, self).__init__(PowAlgorithm(), block_store,
                                             state=state or CoinState(filename=block_store, table="state"),
                                             minification_time=minification_time)

        # Set up the blockchain for 1 minute blocks, retargeting every 10
        # blocks
        # This is in blocks
        self.retarget_period = 10
        # This is in seconds
        self.retarget_time = self.retarget_period * 60

    def transaction_valid_for_relay(self, transaction_bytes):
        """
        Say that normal transactions can be accepted from peers, but generation
        and fee collection transactions cannot.

        """

        if len(Transaction.from_bytes(transaction_bytes).inputs) > 0:
            # It has an input, so isn't a reward.
            return True

        # No inputs. Shouldn't accept this, even if it's valid. It will steal
        # our fees.
        return False

    def get_block_reward(self, previous_block):
        """
        Get the block reward for a block based on the given previous block,
        which may be None.

        """

        # Easy example: 50 coins forever

        # Get the height of this block
        if previous_block is not None:
            height = previous_block.height + 1
        else:
            height = 0

        # How many coins should we generate? We could do something based on
        # height, but just be easy.
        coins = 50

        # Return the number of coins to generate
        return coins

    def verify_payload(self, next_block):
        """
        Verify all the transactions in the block as a group. Each individually
        gets validated the normal way with verify_transaction, but after that's
        done we make sure that the total excess coin spent exactly equals the
        amount that's supposed to be generated.

        """

        if not super(CoinBlockchain, self).verify_payload(next_block):
            # Some transaction failed basic per-transaction validation.
            return False

        # How much left-over coin do we have in this block so far? Start with
        # the block reward.
        block_leftover = self.get_block_reward(next_block)

        for transaction_bytes in unpack_transactions(next_block.payload):
            # Parse a Transaction object out
            transaction = Transaction.from_bytes(transaction_bytes)

            # Add (or remove) the transaction's leftover coins from the block's
            # leftover coins
            block_leftover += transaction.get_leftover()

        if block_leftover == 0:
            # All the fees and rewards went to the exact right places. Only
            # transactions with no inputs can take from the fees at all (as per
            # verify_transaction).
            return True
        else:
            # Reject the block if its transactions have uncollected
            # fees/rewards, or if it tries to give out more in fees and rewards
            # than it deserves.
            logging.warning("Block disburses rewards/fees incorrectly.")
            return False

    def verify_transaction(self, transaction_bytes, chain_head, state,
                           advance=False):
        """
        If the given Transaction is valid on top of the given chain head block
        (which may be None), in the given State (which may be None), return
        True. Otherwise, return False. If advance is True, and the transaction
        is valid, advance the State in place.

        Ensures that:

        The transaction's inputs are existing unspent outputs that the other
        transactions didn't use.

        The transaction's outputs are not already present as unspent outputs
        (in case someone tries to put in the same generation transaction twice).

        The transaction's authorizations are sufficient to unlock its inputs.
        from pybc.transactions import pack_transactions, unpack_transactions
        The transaction's outputs do not excede its inputs, if it has inputs.

        """

        try:
            # This holds our parsed transaction
            transaction = Transaction.from_bytes(transaction_bytes)
        except BaseException:            # The transaction is uninterpretable
            logging.warning("Uninterpretable transaction.")
            traceback.print_exc()
            return False

        for i, (amount, destination) in enumerate(transaction.outputs):
            if amount == 0:
                logging.warning("Transaction trying to send a 0 output.")
                return False

            # What unused output tuple would result from this? They all need to
            # be unique.
            unused_output = (transaction.transaction_hash(), i, amount,
                             destination)

            if state is not None:
                if state.has_unused_output(unused_output):
                    # We have a duplicate transaction. Probably a generation
                    # transaction, since all others need unspent inputs.
                    logging.warning("Transaction trying to create a duplicate unused output")
                    return False
            else:
                # If the State is None, we have to skip verifying that these
                # outputs are unused

                logging.debug("Not checking for duplicate output, since we have no State.")

        # Outputs can never be negative since they are unsigned. So we don't
        # need to check that.

        if len(transaction.inputs) == 0:
            # This is a fee-collecting/reward-collecting transaction. We can't
            # verify them individually, but we can make sure the total they come
            # to is not too big or too small in verify_payload.

            if advance and state is not None:
                # We're supposed to advance the state since transaction is valid
                state.apply_transaction(transaction)

            return True

        # Now we know the transaction has inputs. Check them.

        for source in transaction.inputs:
            if state is not None:
                # Make sure each input is accounted for by a previous unused
                # output.
                if not state.has_unused_output(source):
                    # We're trying to spend something that doesn't exist or is
                    # already spent.
                    logging.warning("Transaction trying to use spent or nonexistent input")
                    return False
            else:
                logging.debug("Not checking for re-used input, since we have no State.")

        if transaction.get_leftover() < 0:
            # Can't spend more than is available to the transaction.
            logging.warning("Transaction trying to output more than it inputs")
            return False

        if not transaction.verify_authorizations():
            # The transaction isn't signed properly.
            logging.warning("Transaction signature(s) invalid")
            return False

        # If we get here, the transaction must be valid. All its inputs are
        # authorized, and its outputs aren't too large.

        if advance and state is not None:
            # We're supposed to advance the state since transaction is valid
            state.apply_transaction(transaction)

        return True

    def make_block(self, destination, min_fee=1):
        """
        Override the ordinary Blockchain make_block with a make_block that
        incorporates pending transactions and sends fees to the public key hash
        destination.

        min_fee specifies the minimum trnasaction fee to require.

        Returns None if the Blockchain is not up to date with a State for the
        top Block, and thus unable to mine on top of it.

        """

        # Don't let anybody mess with our transactions and such until we've made
        # the block. It can still be rendered invalid after that, though.
        with self.lock:

            logging.debug("Making a block")

            if not self.state_available:
                # We can't mine without the latest State
                logging.debug("Can't make block without State")
                return None

            # This holds the list of Transaction objects to include
            to_include = []

            # This holds the total fee available, starting with the block
            # reward.
            total_fee = self.get_block_reward(self.highest_block)

            # This holds the state that we will move to when we apply all these
            # transactions. We already know none of the transactions in
            # self.transactions conflict, and that none of them depend on each
            # other, so we can safely advance the State with them.
            next_state = self.state.copy()

            # How many bytes of transaction data have we used?
            transaction_bytes_used = 0

            for transaction_bytes in self.transactions.values():
                # Parse this transaction out.
                transaction = Transaction.from_bytes(transaction_bytes)

                # Get how much it pays
                fee = transaction.get_leftover()

                if fee >= min_fee:
                    # This transaction pays enough. Use it.

                    if self.verify_transaction(transaction_bytes,
                                               self.highest_block, next_state, advance=True):

                        # The transaction is OK to go in the block. We checked
                        # it earlier, but we should probably check it again.
                        to_include.append(transaction)
                        total_fee += fee
                        transaction_bytes_used += len(transaction_bytes)

                if transaction_bytes_used >= 1024 * 1024:
                    # Don't make blocks bigger than 1 MB of transaction data
                    logging.info("Hit block size limit for generation.")
                    break

            # Add a transaction that gives all the generated coins and fees to
            # us.
            reward_transaction = Transaction()
            reward_transaction.add_output(total_fee, destination)

            # This may match exactly the reward transaction in the last block if
            # we just made and solved that. What unused output does the
            # generation transaction produce?

            if not self.verify_transaction(reward_transaction.to_bytes(),
                                           self.highest_block, next_state, advance=True):

                # Our reward-taking transaction is invalid for some reason. We
                # probably already generated a block this second or something.

                logging.info("Reward transaction would be invalid (maybe "
                             "already used). Skipping block creation.")

                return None

            to_include.append(reward_transaction)

            # Make a block moving to the state we have after we apply all those
            # transactions, with the transaction packed into its payload
            block = super(CoinBlockchain, self).make_block(next_state,
                                                           pack_transactions(
                                                               [transaction.to_bytes() for transaction in to_include]))

            if block is None:
                logging.debug("Base class cound not make block")
            return block

            # next_state gets discarded without being committed, which is
            # perfectly fine. It won't touch the database at all, not even by
            # making unsynced changes, unless we commit.

    def dump_block(self, block):
        """
        Return a string version of the block, with string versions of all the
        Transactions appended, for easy viewing.

        """

        # Keep a list of all the parts to join
        parts = [str(block)]

        if block.has_body:
            for transaction_bytes in unpack_transactions(
                    block.payload):

                parts.append(str(Transaction.from_bytes(transaction_bytes)))

        return "\n".join(parts)


class Wallet(object):
    """
    Represents a Wallet that holds keypairs. Interrogates the blockchain to
    figure out what coins are available to spend, and manages available unspent
    outputs and change sending so that you can send transactions for arbitrary
    amounts to arbitrary addresses.

    TODO: This isn't thread safe at all.

    """

    def __init__(self, blockchain, filename, state=None):
        """
        Make a new Wallet, working on the given Blockchain, and storing keypairs
        in the given Wallet file.

        """

        # Use a database to keep pyelliptic ECC objects for our addresses.
        # keypairs are stored by public key hash.
        self.keystore = sqliteshelf.SQLiteShelf(filename, table="wallet",
                                                lazy=True)

        # Keep a wallet metadata table, really just fof frecording what
        # Blockchain state the wallet is up to date with. If they get out of
        # sync we force a reset event.
        self.wallet_metadata = sqliteshelf.SQLiteShelf(filename,
                                                       table="metadata", lazy=True)

        # Keep a persistent set of spendable outputs. We use a CoinState because
        # it has methods that easily take and yield output tuples.
        self.spendable = state or CoinState(filename=filename, table="spendable")

        # Keep a copy of that that holds the transactions we should draw upon
        # when making our next transaction. This lets us use different unspent
        # outputs for different transactions.
        self.willing_to_spend = self.spendable.copy()

        # Keep the blockchain
        self.blockchain = blockchain

        # Listen to it
        self.blockchain.subscribe(self.blockchain_event)

        # We need a lock to protect our keystore from multithreaded access.
        # TODO: Shrink the critical sections.
        self.lock = threading.RLock()

        # Make sure we are in sync with the blockchain
        if ("blockchain_state" not in self.wallet_metadata or
            self.wallet_metadata["blockchain_state"] !=
                self.blockchain.state.get_hash()):

            # We're not in sync with the blockchain. Get in sync.
            with self.blockchain.lock:
                # TODO: Don't steal the blockchain's lock. Write a "tell
                # everyone your state" method in Blockchain.

                # This should work even if state_available isn't true. When it
                # becomes true, we'll be given the new State to replace this
                # one.
                self.blockchain.send_event("reset", self.blockchain.state)
        else:
            logging.info("Wallet is in sync with blockchain.")

    def blockchain_event(self, event, argument):
        """
        Called by the Blockchain, with the Blockchain's lock, when an event
        happens. The Blockchain is probably in an intermediate state, so only
        look at the arguments and not the Blockchain itself.

        """

        # TODO: Track balance as an int for easy getting.

        with self.lock:
            if event == "forward":
                logging.debug("Advancing wallet forward")
                # We've advanced forward a block. Get any new spendable outputs.
                for transaction_bytes in unpack_transactions(
                        argument.payload):

                    # Parse the transaction
                    transaction = Transaction.from_bytes(transaction_bytes)

                    transaction_hash = transaction.transaction_hash()

                    for spent_output in transaction.inputs:
                        if self.spendable.has_unused_output(spent_output):
                            # This output we had available got spent
                            self.spendable.remove_unused_output(spent_output)

                    for i, output in enumerate(transaction.outputs):
                        # Unpack each output tuple
                        amount, destination = output

                        if destination in self.keystore:
                            # This output is spendable by us
                            self.spendable.add_unused_output((transaction_hash,
                                                              i, amount, destination))

                # Re-set our set of transactions we should draw upon to all the
                # transactions available
                self.willing_to_spend = self.spendable.copy()

            elif event == "backward":
                # We've gone backward a block

                logging.debug("Advancing wallet backward")

                for transaction_bytes in unpack_transactions(
                        argument.payload):

                    # Parse the transaction
                    transaction = Transaction.from_bytes(transaction_bytes)

                    transaction_hash = transaction.transaction_hash()

                    for spent_output in transaction.inputs:
                        if spent_output[3] in self.keystore:
                            # This output we spent got unspent
                            self.spendable.add_unused_output(spent_output)

                    for i, output in enumerate(transaction.outputs):
                        # Unpack each output tuple
                        amount, destination = output

                        # Make an output tuple in the full format
                        spent_output = (transaction_hash, i, amount,
                                        destination)

                        if self.spendable.has_unused_output(spent_output):
                            # This output we had available to spend got un-made
                            self.spendable.remove_unused_output(spent_output)

                # Re-set our set of transactions we should draw upon to all the
                # transactions available
                self.willing_to_spend = self.spendable.copy()

            elif event == "reset":
                # Argument is a CoinState that's not really related to our
                # previous one.

                logging.info("Rebuilding wallet's index of spendable outputs.")

                # Throw out our current idea of our spendable outputs.
                self.spendable.clear()

                # How many outputs are for us?
                found = 0
                # And how much are they worth?
                balance = 0

                for unused_output in argument.get_unused_outputs():
                    if unused_output[3] in self.keystore:
                        # This output is addressed to us. Say it's spendable
                        self.spendable.add_unused_output(unused_output)
                        logging.debug("\t{} to {}".format(unused_output[2],
                                                          util.bytes2string(unused_output[3])))
                        found += 1
                        balance += unused_output[2]

                logging.info("{} outputs available, totaling {}".format(found,
                                                                        balance))

                # Re-set our set of transactions we should draw upon to all the
                # transactions available
                self.willing_to_spend = self.spendable.copy()

            elif event == "sync":
                # Save anything to disk that depends on the blockchain. This
                # doesn't guarantee that we won't get out of sync with the
                # blockchain, but it helps.

                # TODO: We happen to know it's safe to look at state here, but
                # in general it's not. Also, the state may be invalid or the top
                # block, but if that's true we'll get a reset when we have a
                # better state.

                logging.info("Saving wallet")

                # Save the blockchain state that we are up to date with.
                self.wallet_metadata["blockchain_state"] = \
                    self.blockchain.state.get_hash()

                self.spendable.commit()
                self.keystore.sync()
            else:
                logging.warning("Unknown event {} from blockchain".format(
                    event))

    def generate_address(self):
        """
        Make a new address and add it to our keystore.

        We won't know about coins to this address sent before it was generated.

        """
        with self.lock:
            # This holds the new keypair as a pyelliptic ECC
            keypair = pyelliptic.ECC()

            # Save it to the keystore
            self.keystore[hashlib.sha256(keypair.get_pubkey()).digest()] = \
                keypair

            # Sync it to disk. TODO: this is an easy way to get out of sync with
            # the saved Blockchain state.
            self.keystore.sync()

    def get_address(self):
        """
        Return the public key hash of an address that we can receive on.

        """

        with self.lock:
            if len(self.keystore) == 0:
                # We need to make an address
                self.generate_address()

            # Just use the first address we have
            return self.keystore.keys()[0]

    def get_balance(self):
        """
        Return the total balance of all spendable outputs.

        """

        # This holds the balance so far
        balance = 0

        for _, _, amount, _ in self.spendable.get_unused_outputs():
            # Sum up the amounts over all spendable outputs
            balance += amount

        return balance

    def make_simple_transaction(self, amount, destination, fee=1):
        """
        Return a Transaction object sending the given amount to the given
        destination, and any remaining change back to ourselves, leaving the
        specified miner's fee unspent.

        If we don't have enough in outputs that we're willing to spend (i.e.
        which we haven't used to make transactiona already, and which aren't
        change that hasn't been confirmed yet), return None.

        If the amount isn't strictly positive, also returns None, since such a
        transaction would be either useless or impossible depending on the
        actual value.

        Destination must be a 32-byte public key SHA256 hash.

        A negative fee can be passed, but the resulting transaction will not be
        valid.

        """

        with self.lock:

            if not amount > 0:
                # Transaction is unreasonable: not sending any coins anywhere.
                return None

            # Make a transaction
            transaction = Transaction()

            # This holds how much we have accumulated from the spendable outputs
            # we've added to the transaction's inputs.
            coins_collected = 0

            # This holds the set of public key hashes that we need to sign the
            # transaction with.
            key_hashes = set()

            # This holds our willing_to_spend set with updates
            willing_to_spend = self.willing_to_spend.copy()

            # This holds our outputs we need to take out of
            # willing_to_spend when done iterating over it.
            spent = []

            for spendable in willing_to_spend.get_unused_outputs():
                # Unpack the amount we get from this as an input, and the key we
                # need to use to spend it.
                _, _, input_amount, key_needed = spendable

                # Add the unspent output as an input to the transaction
                transaction.add_input(*spendable)

                # Say we've collected that many coins
                coins_collected += input_amount

                # Say we need to sign with the appropriate key
                key_hashes.add(key_needed)

                # Say we shouldn't spend this again in our next transaction.
                spent.append(spendable)

                if coins_collected >= amount + fee:
                    # We have enough coins.
                    break

            for output in spent:
                # Mark all the outputs we just tried to spend as used until a
                # block comes along either confirming or denying this.
                willing_to_spend.remove_unused_output(output)

            if coins_collected < amount + fee:
                # We couldn't find enough money for this transaction!
                # Maybe wait until some change transactions get into blocks.
                return None

            # We're going through with the transaction. Don't re-use these
            # inputs until after the next block comes in.
            self.willing_to_spend = willing_to_spend

            # We've made a transaction with enough inputs!
            # Add the outputs.
            # First the amount we actually wanted to send.
            transaction.add_output(amount, destination)

            if coins_collected - amount - fee > 0:
                # Then the change, if any, back to us at some address we can
                # receive on.
                transaction.add_output(coins_collected - amount - fee,
                                       self.get_address())
                # The fee should be left over.

            # Now do the authorizations. What do we need to sign?
            to_sign = transaction.header_bytes()

            for key_hash in key_hashes:
                # Load the keypair
                keypair = self.keystore[key_hash]

                # Grab the public key
                public_key = keypair.get_pubkey()

                # Make the signature
                signature = keypair.sign(to_sign)

                # Add the authorization to the transaction
                transaction.add_authorization(public_key, signature)

            # TODO: If we have a change output, put it in the willing to spend
            # set so we can immediately spend from it.

            # Now the transaction is done!
            return transaction


if __name__ == "__main__":
    # Do a transaction test

    def generate_block(blockchain, destination, min_fee=1):
        """
        Given a blockchain, generate a block (synchronously!), sending the
        generation reward to the given destination public key hash.

        min_fee specifies the minimum fee to charge.

        TODO: Move this into the Blockchain's get_block method.

        """

        # Make a block with the transaction as its payload
        block = blockchain.make_block(destination, min_fee=min_fee)

        # Now unpack and dump the block for debugging.
        print "Block will be:\n{}".format(block)

        for transaction in unpack_transactions(block.payload):
            # Print all the transactions
            print "Transaction: {}".format(Transaction.from_bytes(transaction))

        # Do proof of work on the block to mine it.
        block.do_work(blockchain.algorithm)

        print "Successful nonce: {}".format(block.nonce)

        # See if the work really is enough
        print "Work is acceptable: {}".format(block.verify_work(
            blockchain.algorithm))

        # See if the block is good according to the blockchain
        print "Block is acceptable: {}".format(blockchain.verify_block(block))

        # Add it to the blockchain through the complicated queueing mechanism
        blockchain.queue_block(block)

    # Make a blockchain
    blockchain = CoinBlockchain("coin.blocks")

    # Make a wallet that hits against it
    wallet = Wallet(blockchain, "coin.wallet")

    print "Receiving address: {}".format(util.bytes2string(
        wallet.get_address()))

    # Make a block that gives us coins.
    generate_block(blockchain, wallet.get_address())

    # Send some coins to ourselves
    print "Sending ourselves 10 coins..."
    transaction = wallet.make_simple_transaction(10, wallet.get_address())
    print transaction
    blockchain.add_transaction(transaction.to_bytes())

    # Make a block that confirms that transaction.
    generate_block(blockchain, wallet.get_address())
