#!/usr/bin/env python2.7
# json_coin.py: a coin implemented on top of pybc.coin
#               with addition json_data field for transactions

from __future__ import absolute_import
from __future__ import print_function
import six
from six.moves import range
if __name__ == '__main__':
    import os.path as _p, sys
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

import struct
import hashlib
import traceback
import logging
import json

try:
    import pyelliptic
except BaseException:    # pyelliptic didn't load. Either it's not installed or it can't find OpenSSL
    from . import emergency_crypto_munitions as pyelliptic
from . import util
from .transactions import pack_transactions, unpack_transactions
from .coin import Transaction, CoinState, CoinBlockchain, Wallet


class JsonTransaction(Transaction):
    """
    Represents a transaction on the blockchain with Json data field.

    A transaction is:
    1. a list of inputs represented by:
        (transaction_hash, output_index, amount, destination, json_data)
    2. a list of outputs represented by:
        (amounts, destination public key hash, json_data)
    3. a list of authorizations signing the previous two lists:
        (public key, signature, json_data)
    It also has a timestamp, so that two generation
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

    def __repr__(self):
        return str(self)

    def __str__(self):
        """
        Represent this transaction as a string.

        """

        # These are the lines we will return
        lines = []

        lines.append("---JsonTransaction {}---".format(util.time2string(
            self.timestamp)))
        lines.append("{} inputs".format(len(self.inputs)))
        for transaction, index, amount, destination, json_data in self.inputs:
            # Put every input (another transaction's output)
            lines.append("\t{} addressed to {} from output {} of {} with {}".format(
                amount, util.bytes2string(destination), index,
                util.bytes2string(transaction), json.dumps(json_data)))
        lines.append("{} outputs".format(len(self.outputs)))
        for amount, destination, json_data in self.outputs:
            # Put every output (an amount and destination public key hash)
            lines.append("\t{} to {} with {}".format(amount, util.bytes2string(destination),
                                                     json.dumps(json_data)))
        lines.append("{} authorizations".format(len(self.authorizations)))
        for public_key, signature, json_data in self.authorizations:
            # Put every authorizing key and signature.
            lines.append("\tKey: {}".format(util.bytes2string(public_key)))
            lines.append("\tSignature: {}".format(
                util.bytes2string(signature)))
            lines.append("\tJSON data: {}".format(json.dumps(json_data)))

        # Put the hash that other transactions use to talk about this one
        lines.append("Hash: {}".format(util.bytes2string(
            self.transaction_hash())))

        return "\n".join(lines)

    def add_input(self, transaction_hash, output_index, amount, destination, json_data=None):
        """
        Take the coins from the given output of the given transaction as input
        for this transaction. It is necessary to specify and store the amount
        and destination public key hash of the output, so that the blockchain
        can be efficiently read backwards.
        Optional json_data field can be passed to store some data in the transaction.
        """
        self.inputs.append((transaction_hash, output_index, amount, destination, json_data))

    def add_output(self, amount, destination, json_data=None):
        """
        Send the given amount of coins to the public key with the given hash.
        Optional json_data field can be passed to store some data in the transaction.
        """
        self.outputs.append((amount, destination, json_data))

    def add_authorization(self, public_key, signature, json_data=None):
        """
        Add an authorization to this transaction by the given public key. The
        given signature is that key's signature of the transaction header data
        (inputs and outputs).
        Both public key and signature must be bytestrings.
        Optional json_data field can be passed to store some data in the transaction.
        """
        self.authorizations.append((public_key, signature, json_data))

    def get_leftover(self):
        """
        Return the sum of all inputs minus the sum of all outputs.
        """

        # This is where we store our total
        leftover = 0

        for _, _, amount, _, _ in self.inputs:
            # Add all the inputs on the + side
            leftover += amount

        for amount, _, _ in self.outputs:
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

        for public_key, signature, _ in self.authorizations:
            # Check if each authorization is valid.
            if pyelliptic.ECC(pubkey=public_key).verify(signature, message_to_sign):

                # The signature is valid. Remember the public key hash.
                valid_signers.add(hashlib.sha256(public_key).digest())

            else:
                logging.warning("Invalid signature!")
                # We're going to ignore extra invalid signatures on
                # transactions. What could go wrong?

        for _, _, _, destination, _ in self.inputs:
            if destination not in valid_signers:
                # This input was not properly unlocked.
                return False

        # If we get here, all inputs were to destination pubkey hashes that has
        # authorizing signatures attached.
        return True

    def pack_input(self, transaction_hash, output_index, amount, destination, json_data):
        """
        Return packet input as a bytestring.
        """
        jdata = json.dumps(json_data)
        return struct.pack(
            ">64sIQ32sI",
            transaction_hash,
            output_index,
            amount,
            destination,
            len(jdata)) + jdata

    def pack_inputs(self):
        """
        Return the inputs as a bytestring.

        """

        # Return the 4-byte number of inputs, followed by a 64-byte transaction
        # hash, a 4-byte output index, an 8 byte amount, and a 32 byte
        # destination public key hash for each input.
        # also added json data for every input:
        # 4-byte length and n-bytes string
        return struct.pack(">I", len(self.inputs)) + "".join(
            self.pack_input(*inpt) for inpt in self.inputs)

    def unpack_input(self, bytestring, offset=0):
        """
        Extract single transaction input from bytestring.
        """
        transaction_hash, output_index, amount, destination, json_data_len = struct.unpack(
            ">64sIQ32sI", bytestring[offset:offset + 112])
        json_data = json.loads(bytestring[offset + 112:offset + 112 + json_data_len])
        return 112 + json_data_len, transaction_hash, output_index, amount, destination, json_data

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

        for _ in range(input_count):
            # Unpack that many 108-byte records of 64-byte transaction hashes,
            # 4-byte output indices, 8-byte amounts, and 32-byte destination
            # public key hashes.
            parts = self.unpack_input(bytestring, index)
            self.inputs.append(parts[1:])
            index += parts[0]

    def pack_output(self, amount, destination, json_data):
        """
        Pack single output ite as a bytestring.
        """
        jdata = json.dumps(json_data)
        return struct.pack(">Q32sI", amount, destination, len(jdata)) + jdata

    def pack_outputs(self):
        """
        Return the outputs as a bytestring.

        """

        # Return the 4-byte number of outputs, followed by an 8-byte amount and
        # a 32-byte destination public key hash for each output
        # also added json data for every input:
        # 4-byte length and n-bytes string

        return struct.pack(">I", len(self.outputs)) + "".join(
            self.pack_output(*outpt) for outpt in self.outputs)

    def unpack_output(self, bytestring, offset=0):
        amount, destination, json_data_len = struct.unpack(
            ">Q32sI", bytestring[offset:offset + 44])
        json_data = json.loads(bytestring[offset + 44:offset + 44 + json_data_len])
        return 44 + json_data_len, amount, destination, json_data

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

        for _ in range(output_count):
            # Unpack that many 40-byte records of 8-byte amounts and 32-byte
            # destination public key hashes.
            parts = self.unpack_output(bytestring, index)
            self.outputs.append(parts[1:])
            index += parts[0]

    def pack_authorizations(self):
        """
        Return a bytestring of all the authorizations for this transaction.

        """

        # We have a 4-byte number of authorization records, and then pairs of 4
        # -byte-length and n-byte-data strings for each record.

        # This holds all our length-delimited bytestrings as we make them
        authorization_bytestrings = []

        for public_key, signature, json_data in self.authorizations:
            # Add the public key
            authorization_bytestrings.append(struct.pack(">I",
                                                         len(public_key)) + public_key)
            # Add the signature
            authorization_bytestrings.append(struct.pack(">I",
                                                         len(signature)) + signature)
            # Add json data
            jdata = json.dumps(json_data)
            authorization_bytestrings.append(struct.pack(">I",
                                                         len(jdata)) + jdata)

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

        for _ in range(authorization_count):
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

            # Get the length of the json data
            (length,) = struct.unpack(">I", bytestring[index:index + 4])
            index += 4

            # Get the signature itself
            jdata = bytestring[index: index + length]
            index += length
            json_data = json.loads(jdata)

            # Add the authorization
            self.authorizations.append((public_key, signature, json_data))


class JsonCoinState(CoinState):
    """
    A State that keeps track of all unused outputs in blocks. Can also be used
    as a generic persistent set of output tuples.
    Keep track of Json data stored in the transactions.
    """

    def json_output2bytes(self, output):
        """
        Turn an unused output tuple into a bytestring:
            (transaction hash, output index, output amount, destination, json_data)
        """
        as_list = list(output)
        json_data = as_list[4]
        jdata = json.dumps(json_data)
        as_list[4] = len(jdata)
        result = struct.pack(">64sIQ32sI", *as_list) + jdata
        del as_list
        return result

    def bytes2json_output(self, rawbytes):
        """
        Turn a bytestring into a tuple of:
            (transaction hash, output index, output amount, destination, json_data)
        """
        output = list(struct.unpack(">64sIQ32s", rawbytes[:108]))
        json_data = None
        if len(rawbytes) == 108:
            output += [json_data, ]
            return tuple(output)
        json_data_length = struct.unpack(">I", rawbytes[108:112])
        json_data_raw = rawbytes[112:112 + json_data_length]
        json_data = json.loads(json_data_raw)
        output += [json_data, ]
        return tuple(output)

    def add_unused_json_output(self, output):
        """
        Add the given output tuple as an unused output.
        Store json data (last element of the tuple) as a value,
        and exclude it from key string.
        """
        key = self.output2bytes(list(output)[:4])
        value = json.dumps(output[4])
        self.unused_outputs.insert(key, value)

    def remove_unused_json_output(self, output):
        """
        Remove the given output tuple as an unused output.
        Last element storing json data will be excluded from key string.
        """
        key = self.output2bytes(list(output)[:4])
        self.unused_outputs.remove(key)

    def get_unused_json_outputs(self):
        """
        Yield each unused output, as a tuple:
            (transaction hash, index, amount, destination, json_data)
        """
        for key, value in six.iteritems(self.unused_outputs):
            output4 = list(self.bytes2output(key))
            output = tuple(output4 + [json.loads(value), ])
            yield output

    def has_unused_json_output(self, output):
        """
        Returns true if the given unised output tuple of of is in the current set of
        unused outputs, and false otherwise:
            (transaction hash, output index, output amount, destination, json_data)
        """
        key = self.output2bytes(list(output)[:4])
        return self.unused_outputs.find(key) is not None

    def apply_transaction(self, transaction):
        """
        Update this state by applying the given Transaction object. The
        transaction is assumed to be valid.

        """
        # Get the hash of the transaction
        transaction_hash = transaction.transaction_hash()

        logging.debug("Applying transaction {}".format(util.bytes2string(transaction_hash)))

        for spent_output in transaction.inputs:
            # The inputs are in exactly the same tuple format as we use.
            # Remove each of them from the unused output set.

            if not self.has_unused_json_output(spent_output):
                logging.error("Trying to remove nonexistent output: {} {} {} "
                              "{}".format(util.bytes2string(spent_output[0]),
                                          spent_output[1], spent_output[2],
                                          util.bytes2string(spent_output[3])))

                self.audit()

                # See if things just work out
            else:
                self.remove_unused_json_output(spent_output)

        for i, output in enumerate(transaction.outputs):
            # Unpack each output tuple
            if len(output) == 3:
                amount, destination, json_data = output
            else:
                raise Exception('Wrong output: {}'.format(output))

            # Make a tupe for the full unused output
            unused_output = (transaction_hash, i, amount, destination, json_data)

            if self.has_unused_json_output(unused_output):
                logging.error("Trying to create duplicate output: {} {} {} "
                              "{}".format(util.bytes2string(unused_output[0]),
                                          unused_output[1], unused_output[2],
                                          util.bytes2string(unused_output[3])))

                self.audit()

                # See if things just work out
            else:
                self.add_unused_json_output(unused_output)

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

            if self.has_unused_json_output(spent_output):
                logging.error("Trying to create duplicate output: {} {} {} "
                              "{}".format(util.bytes2string(spent_output[0]),
                                          spent_output[1], spent_output[2],
                                          util.bytes2string(spent_output[3])))

                self.audit()

                # See if things just work out
            else:
                self.add_unused_json_output(spent_output)

        for i, output in enumerate(transaction.outputs):
            # Unpack each output tuple
            amount, destination, json_data = output

            # Make a tuple for the full unused output
            unused_output = (transaction_hash, i, amount, destination, json_data)

            if not self.has_unused_json_output(unused_output):
                logging.error("Trying to remove nonexistent output: {} {} {} "
                              "{}".format(util.bytes2string(unused_output[0]),
                                          unused_output[1], unused_output[2],
                                          util.bytes2string(unused_output[3])))

                # Audit ourselves
                self.audit()

                # See if things just work out
            else:
                # Remove its record from the set of unspent outputs
                self.remove_unused_json_output(unused_output)

    def step_forwards(self, block):
        """
        Add any outputs of this block's transactions to the set of unused
        outputs, and consume all the inputs.

        Updates the CoinState in place.
        """

        for transaction_bytes in unpack_transactions(block.payload):

            # Parse the transaction
            json_transaction = JsonTransaction.from_bytes(transaction_bytes)

            self.apply_transaction(json_transaction)

        if self.get_hash() != block.state_hash:
            # We've stepped forwards incorrectly
            raise Exception("Stepping forward to state {} instead produced state {}.".format(
                util.bytes2string(block.state_hash),
                util.bytes2string(self.get_hash())))

    def step_backwards(self, block):
        """
        Add any inputs from this block to the set of unused outputs, and remove
        all the outputs.

        Updates the CoinState in place.
        """

        if self.get_hash() != block.state_hash:
            # We're trying to step back the wrong block
            raise Exception("Stepping back block for state {} when actually in state {}.".format(
                util.bytes2string(block.state_hash),
                util.bytes2string(self.get_hash())))

        logging.debug("Correctly in state {} before going back.".format(
            util.bytes2string(self.get_hash())))

        for transaction_bytes in reversed(list(unpack_transactions(block.payload))):
            # Parse the transaction
            json_transaction = JsonTransaction.from_bytes(transaction_bytes)
            self.remove_transaction(json_transaction)

    def copy(self):
        """
        Return a copy of the CoinState that can be independently operated on.
        This CoinState must have had no modifications made to it since its
        creation or last commit() operation. Modifications made to this
        CoinState will invalidate the copy and its descendents.

        """

        # Make a new  JsonCoinState, with its AuthenticatedDictionary a child of
        # ours.
        return JsonCoinState(unused_outputs=self.unused_outputs.copy())


class JsonCoinBlockchain(CoinBlockchain):
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
        super(JsonCoinBlockchain, self).__init__(
            block_store,
            minification_time=minification_time,
            state=state or JsonCoinState(filename=block_store, table="state"),
        )

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

        if len(JsonTransaction.from_bytes(transaction_bytes).inputs) > 0:
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
        # How many coins should we generate? We could do something based on
        # height, but just be easy.
        coins = 5
        logging.debug("Block reward is {} coins".format(coins))
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
            json_transaction = JsonTransaction.from_bytes(transaction_bytes)

            # Add (or remove) the transaction's leftover coins from the block's
            # leftover coins
            block_leftover += json_transaction.get_leftover()

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

    def verify_transaction(self, transaction_bytes, chain_head, state, advance=False):
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
            json_transaction = JsonTransaction.from_bytes(transaction_bytes)
        except BaseException:            # The transaction is uninterpretable
            logging.warning("Uninterpretable transaction.")
            traceback.print_exc()
            return False

        for i, (amount, destination, json_data) in enumerate(json_transaction.outputs):
            if amount == 0:
                logging.warning("Transaction trying to send a 0 output.")
                return False

            # What unused output tuple would result from this? They all need to
            # be unique.
            unused_output = (json_transaction.transaction_hash(), i, amount, destination, json_data)

            if state is not None:
                if state.has_unused_json_output(unused_output):
                    # We have a duplicate transaction. Probably a generation
                    # transaction, since all others need unspent inputs.
                    logging.warning("Transaction trying to create a duplicate unused output")
                    logging.info("{}".format(json_transaction))
                    return False
            else:
                # If the State is None, we have to skip verifying that these
                # outputs are unused

                logging.debug("Not checking for duplicate output, since we have no State.")

        # Outputs can never be negative since they are unsigned. So we don't
        # need to check that.

        if len(json_transaction.inputs) == 0:
            # This is a fee-collecting/reward-collecting transaction. We can't
            # verify them individually, but we can make sure the total they come
            # to is not too big or too small in verify_payload.

            if advance and state is not None:
                # We're supposed to advance the state since transaction is valid
                state.apply_transaction(json_transaction)

            return True

        # Now we know the transaction has inputs. Check them.

        for source in json_transaction.inputs:
            if state is not None:
                # Make sure each input is accounted for by a previous unused
                # output.
                if not state.has_unused_json_output(source):
                    # We're trying to spend something that doesn't exist or is
                    # already spent.
                    logging.warning("Transaction trying to use spent or nonexistent input")
                    return False
            else:
                logging.debug("Not checking for re-used input, since we have no State.")

        if json_transaction.get_leftover() < 0:
            # Can't spend more than is available to the transaction.
            logging.warning("Transaction trying to output more than it inputs")
            return False

        if not json_transaction.verify_authorizations():
            # The transaction isn't signed properly.
            logging.warning("Transaction signature(s) invalid")
            return False

        # If we get here, the transaction must be valid. All its inputs are
        # authorized, and its outputs aren't too large.

        if advance and state is not None:
            # We're supposed to advance the state since transaction is valid
            state.apply_transaction(json_transaction)

        return True

    def make_block(self, destination, min_fee=1, json_data=None, with_inputs=False):
        """
        Override CoinBlockchain make_block with a additional json_data parameter.
        """
        # Don't let anybody mess with our transactions and such until we've made
        # the block. It can still be rendered invalid after that, though.
        with self.lock:

            logging.debug("Making a block with JSON: {}".format(json_data))

            if not self.state_available:
                # We can't mine without the latest State
                logging.debug("Can't make block without State")
                return None

            if with_inputs and not self.transactions:
                logging.debug("No transactions found, skip block generation")
                return None

            # This holds the list of Transaction objects to include
            to_include = []
            all_inputs = []

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
                json_transaction = JsonTransaction.from_bytes(transaction_bytes)

                # Get how much it pays
                fee = json_transaction.get_leftover()

                if fee >= min_fee:
                    # This transaction pays enough. Use it.

                    if self.verify_transaction(transaction_bytes, self.highest_block, next_state, advance=True):

                        # The transaction is OK to go in the block. We checked
                        # it earlier, but we should probably check it again.
                        to_include.append(json_transaction)
                        total_fee += fee
                        transaction_bytes_used += len(transaction_bytes)
                        all_inputs.extend(json_transaction.inputs)
                    else:
                        logging.info('INVALID TRANSACTION:\n{}'.format(str(json_transaction)))

                if transaction_bytes_used >= 1024 * 1024:
                    # Don't make blocks bigger than 1 MB of transaction data
                    logging.info("Hit block size limit for generation.")
                    break

            # Add a transaction that gives all the generated coins and fees to
            # us.
            reward_transaction = JsonTransaction()
            reward_json = {'j': json_data, 'f': total_fee, }
            reward_transaction.add_output(total_fee, destination, reward_json)

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
            block = super(CoinBlockchain, self).make_block(
                next_state, pack_transactions(
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
            for transaction_bytes in unpack_transactions(block.payload):

                parts.append(str(JsonTransaction.from_bytes(transaction_bytes)))

        return "\n".join(parts)

    def iterate_transactions_by_address(self, address, include_inputs=True, include_outputs=True):
        for block in self.longest_chain():
            for transaction_bytes in unpack_transactions(block.payload):
                tr = JsonTransaction.from_bytes(transaction_bytes)
                tr.block_hash = block.block_hash()
                related = False
                if include_inputs:
                    for inpt in tr.inputs:
                        if inpt[3] == address:
                            related = True
                            break
                if include_outputs:
                    for outp in tr.outputs:
                        if outp[1] == address:
                            related = True
                            break
                if related:
                    yield tr


class JsonWallet(Wallet):
    """
    """

    def __init__(self, blockchain, filename, state=None):
        """
        """
        super(JsonWallet, self).__init__(
            blockchain,
            filename,
            state=state or JsonCoinState(filename=filename, table="spendable"),
        )

    def blockchain_event(self, event, argument):
        """
        """

        # TODO: Track balance as an int for easy getting.

        with self.lock:
            if event == "forward":
                logging.debug("Advancing wallet forward")
                # We've advanced forward a block. Get any new spendable outputs.
                for transaction_bytes in unpack_transactions(argument.payload):

                    # Parse the transaction
                    json_transaction = JsonTransaction.from_bytes(transaction_bytes)

                    transaction_hash = json_transaction.transaction_hash()

                    for spent_output in json_transaction.inputs:
                        if self.spendable.has_unused_json_output(spent_output):
                            # This output we had available got spent
                            self.spendable.remove_unused_json_output(spent_output)

                    for i, output in enumerate(json_transaction.outputs):
                        # Unpack each output tuple
                        amount, destination, json_data = output

                        if destination in self.keystore:
                            # This output is spendable by us
                            self.spendable.add_unused_json_output((
                                transaction_hash, i, amount, destination, json_data,
                            ))

                # Re-set our set of transactions we should draw upon to all the
                # transactions available
                self.willing_to_spend = self.spendable.copy()

            elif event == "backward":
                # We've gone backward a block

                logging.debug("Advancing wallet backward")

                for transaction_bytes in unpack_transactions(argument.payload):

                    # Parse the transaction
                    json_transaction = JsonTransaction.from_bytes(transaction_bytes)

                    transaction_hash = json_transaction.transaction_hash()

                    for spent_output in json_transaction.inputs:
                        if spent_output[3] in self.keystore:
                            # This output we spent got unspent
                            self.spendable.add_unused_json_output(spent_output)

                    for i, output in enumerate(json_transaction.outputs):
                        # Unpack each output tuple
                        amount, destination, json_data = output

                        # Make an output tuple in the full format
                        spent_output = (transaction_hash, i, amount, destination, json_data)

                        if self.spendable.has_unused_json_output(spent_output):
                            # This output we had available to spend got un-made
                            self.spendable.remove_unused_json_output(spent_output)

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

                for unused_output in argument.get_unused_json_outputs():
                    if unused_output[3] in self.keystore:
                        # This output is addressed to us. Say it's spendable
                        self.spendable.add_unused_json_output(unused_output)
                        logging.debug("\t{} to {}".format(unused_output[2],
                                                          util.bytes2string(unused_output[3])))
                        found += 1
                        balance += unused_output[2]

                logging.info("{} outputs available, totaling {}".format(found, balance))

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
                self.wallet_metadata["blockchain_state"] = self.blockchain.state.get_hash()

                self.spendable.commit()
                self.keystore.sync()

            else:
                logging.warning("Unknown event {} from blockchain".format(event))

    def get_balance(self):
        """
        Return the total balance of all spendable outputs.

        """

        # This holds the balance so far
        balance = 0

        for _, _, amount, _, _ in self.spendable.get_unused_json_outputs():
            # Sum up the amounts over all spendable outputs
            balance += amount

        return balance

    def make_simple_transaction(self, amount, destination, fee=1,
                                json_data=None, auth_data=None, spendable_filter=None):
        """
        Return a JsonTransaction object sending the given amount to the given
        destination, and any remaining change back to ourselves, leaving the
        specified miner's fee unspent.

        Optional json_data field can be passed as JSON to the transaction output.
        Optional auth_data field can be passed as JSON to the authorization.

        If we don't have enough in outputs that we're willing to spend (i.e.
        which we haven't used to make transaction already, and which aren't
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
            json_transaction = JsonTransaction()

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

            for spendable in willing_to_spend.get_unused_json_outputs():
                if spendable_filter and not spendable_filter(spendable):
                    continue
                # Unpack the amount we get from this as an input, and the key we
                # need to use to spend it.
                _, _, input_amount, key_needed, _ = spendable
                # Add the unspent output as an input to the transaction
                json_transaction.add_input(*spendable)

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
                willing_to_spend.remove_unused_json_output(output)

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
            json_transaction.add_output(amount, destination, json_data)

            if coins_collected - amount - fee > 0:
                # Then the change, if any, back to us at some address we can
                # receive on.
                json_transaction.add_output(
                    amount=coins_collected - amount - fee,
                    destination=self.get_address(),
                    json_data={'f': fee, 'c': coins_collected, },
                )
                # The fee should be left over.

            # Now do the authorizations. What do we need to sign?
            to_sign = json_transaction.header_bytes()

            for key_hash in key_hashes:
                # Load the keypair
                keypair = self.keystore[key_hash]

                # Grab the public key
                public_key = keypair.get_pubkey()

                # Make the signature
                signature = keypair.sign(to_sign)

                # Add the authorization to the transaction
                json_transaction.add_authorization(public_key, signature, auth_data)

            # TODO: If we have a change output, put it in the willing to spend
            # set so we can immediately spend from it.

            # Now the transaction is done!
            return json_transaction


if __name__ == "__main__":
    # Do a transaction test

    def generate_block(blockchain, destination, min_fee=1, json_data=None):
        """
        Given a blockchain, generate a block (synchronously!), sending the
        generation reward to the given destination public key hash.

        min_fee specifies the minimum fee to charge.

        TODO: Move this into the Blockchain's get_block method.

        """

        # Make a block with the transaction as its payload
        block = blockchain.make_block(destination, min_fee=min_fee, json_data=json_data)

        # Now unpack and dump the block for debugging.
        print("Block will be:\n{}".format(block))

        for transaction in unpack_transactions(block.payload):
            # Print all the transactions
            print("JsonTransaction: {}".format(JsonTransaction.from_bytes(transaction)))

        # Do proof of work on the block to mine it.
        block.do_work(blockchain.algorithm)

        print("Successful nonce: {}".format(block.nonce))

        # See if the work really is enough
        print("Work is acceptable: {}".format(block.verify_work(blockchain.algorithm)))

        # See if the block is good according to the blockchain
        print("Block is acceptable: {}".format(blockchain.verify_block(block)))

        # Add it to the blockchain through the complicated queueing mechanism
        blockchain.queue_block(block)

    # Make a blockchain
    blockchain = JsonCoinBlockchain("coin.blocks")

    # Make a wallet that hits against it
    wallet = JsonWallet(blockchain, "coin.wallet")

    print("Receiving address: {}".format(util.bytes2string(wallet.get_address())))

    # Make a block that gives us coins.
    import time
    generate_block(blockchain, wallet.get_address(), json_data=dict(
        test=123,
        time=int(time.time()),
    ))

    # Send some coins to ourselves
    print("Sending ourselves 10 coins...")
    transaction = wallet.make_simple_transaction(
        10,
        wallet.get_address(),
        json_data=dict(
            test=456,
            time=int(time.time()),
        ),
        auth_data=dict(k='test123'),
    )
    print(transaction)
    blockchain.add_transaction(transaction.to_bytes())

    # Make a block that confirms that transaction.
    generate_block(blockchain, wallet.get_address(), json_data=dict(
        test=789,
        time=int(time.time()),
    ))
