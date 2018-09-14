"""
transactions.py: Code for dealing with transactions, which at the Blockchainq
level are not real objects. Transactions are represented as bytestrings.

"""

from __future__ import absolute_import
import traceback
import struct
import logging
from six.moves import range


class InvalidPayloadError(Exception):
    """
    Thrown when a transaction list can't be decoded.

    """


def unpack_transactions(block_payload):
    """
    Given a block payload, parse it out into its constituent transactions.
    Yield each of them.

    The encoding we use is
    <4 byte transaction count>
    [<4 byte transaction byte length>
    <transaction bytes>]*

    May throw an InvalidPayloadError if the payload is not a properly
    encoded list.

    """
    try:
        # How many transactions do we need?
        (transaction_count,) = struct.unpack(">I", block_payload[0:4])
        # Where should we start the next record from?
        location = 4

        for _ in range(transaction_count):
            # How many bytes is the transaction?
            (transaction_length,) = struct.unpack(">I",
                                                  block_payload[location:location + 4])
            location += 4

            # Grab the transaction bytes
            transaction_bytes = block_payload[location:location +
                                              transaction_length]
            location += transaction_length

            yield transaction_bytes
    except GeneratorExit:
        # This is fine
        pass
    except BaseException:        # We broke while decoding a transaction.
        logging.error("Exception while unpacking transactions")
        logging.error(traceback.format_exc())
        raise InvalidPayloadError


def pack_transactions(transactions):
    """
    Encode the given list of transactions into a payload.

    The encoding we use is
    <4 byte transaction count>
    [<4 byte transaction byte length>
    <transaction bytes>]*

    """

    # Make a list of transaction records with their lengths at the
    # front.
    transactions_with_lengths = [struct.pack(">I", len(transaction)) +
                                 transaction for transaction in transactions]

    # Return the number of transaction records followed by the records.
    return (struct.pack(">I", len(transactions_with_lengths)) +
            "".join(transactions_with_lengths))
