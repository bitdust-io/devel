"""
TransactionalBlockchain.py: contains the TransactionalBlockchain class.

"""

import hashlib
import traceback
import struct
import logging

from pybc.Blockchain import Blockchain
from pybc.transactions import pack_transactions, unpack_transactions
from pybc.transactions import InvalidPayloadError
import pybc.util


class TransactionalBlockchain(Blockchain):
    """
    A Blockchain where the Blocks are just lists of transactions. All
    Blockchains use transactions, but TransactionalBlockchains have blocks where
    payloads consist only of transaction lists.

    """

    def verify_payload(self, next_block):
        """
        Verify the payload by verifying all the transactions in this block's
        payload against the parent block of this block.

        """

        with self.lock:
            try:

                if self.has_block(next_block.previous_hash):
                    # This holds the block that this block is based on, or None if
                    # it's a genesis block.
                    parent_block = self.get_block(next_block.previous_hash)
                else:
                    # Don't check whether the parent block makes sense here. Just
                    # say we're checking a genesis block.
                    parent_block = None

                # Get a State (a copy) to verify transactions against. This
                # State may be None, but verify_transaction knows how to deal
                # with that.
                state = self.state_after(parent_block)

                for transaction in unpack_transactions(next_block.payload):
                    if not self.verify_transaction(transaction, parent_block,
                                                   state, advance=True):
                        # We checked the the next transaction against the
                        # blockchain and all previous transactions in the block.

                        # This transaction is invalid
                        return False

                # We have now verified all the the transactions in this block.
                return True

            except InvalidPayloadError:
                # Parsing the transactions broke, so the payload is invalid.
                return False
