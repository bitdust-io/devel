#!/usr/bin/env python2.7
# token.py: a digital token implemented on top of pybc.coin
#

#------------------------------------------------------------------------------

from __future__ import absolute_import
import logging

#------------------------------------------------------------------------------

from . import json_coin
from . import transactions
from . import util

#------------------------------------------------------------------------------

def pack_token(token, payloads):
    """
    """
    return dict(
        t=token,
        p=payloads,
    )

def unpack_token(json_data):
    """
    """
    try:
        return json_data['t'], json_data['p']
    except (TypeError, KeyError):
        return None, None


class TokenRecord(object):
    """
    """

    def __init__(self, block_hash=None, transaction_hash=None):
        """
        """
        self.block_hash = block_hash
        self.transaction_hash = transaction_hash
        self.token_id = None
        self.amount = None
        self.address = None
        self.prev_transaction_hash = None
        self.prev_output_index = None
        self.prev_amount = None
        self.prev_address = None
        self.input_payloads = []
        self.output_payloads = []

    def __str__(self):
        return "'{}' with {} addressed from {} to {}".format(
            self.token_id,
            self.value(),
            util.bytes2string(self.prev_address or '') or '<own balance>',
            util.bytes2string(self.address or '') or '<own balance>',
        )

    def add_output(self, output_tuple):
        """
        """
        self.amount, self.address, _ = output_tuple
        output_token_id, self.output_payloads = unpack_token(output_tuple[2])
        if output_token_id is None:
            raise ValueError('output json data does not contain token record')
        if self.token_id is None:
            self.token_id = output_token_id
        if output_token_id != self.token_id:
            raise ValueError('output token ID does not match to input')

    def add_input(self, input_tuple):
        """
        """
        input_token_id, self.input_payloads = unpack_token(input_tuple[4])
        if input_token_id is None:
            raise ValueError('input json data does not contain token record')
        if self.token_id is None:
            self.token_id = input_token_id
        if input_token_id != self.token_id:
            raise ValueError('input token ID does not match to output')
        self.prev_transaction_hash, self.prev_output_index, self.prev_amount, self.prev_address, _ = input_tuple

    def value(self):
        """
        """
        return self.amount or self.prev_amount


class TokenProfile(object):
    """
    """
    def __init__(self, token_records=[]):
        self.token_id = None
        self.records = []
        for t_record in token_records:
            self.add_record(t_record)
        logging.info('\n{}'.format(str(self)))

    def __str__(self):
        """
        """
        lines = []
        lines.append("---TokenProfile {}---".format(self.token_id))
        lines.append("{} records".format(len(self.records)))
        for i, record in enumerate(self.records):
            lines.append("\t{}: {}".format(i, str(record)))
        lines.append('Owner: {}'.format(util.bytes2string(self.owner().address)))
        lines.append('Creator: {}'.format(util.bytes2string(self.creator().address)))
        return "\n".join(lines)

    def add_record(self, token_record):
        if token_record in self.records:
            raise ValueError('duplicated token record')
        if self.token_id is None:
            self.token_id = token_record.token_id
        if self.token_id != token_record.token_id:
            raise ValueError('invalid token ID, not matching with first record')
        if not self.records:
            self.records.append(token_record)
            return
        if token_record.prev_address is None:
            # this is "create new token" record
            self.records.insert(0, token_record)
            return
        if token_record.address is None:
            # this is "delete existing token" record
            self.records.append(token_record)
            return
        for i, existing_record in enumerate(self.records):
            if existing_record.prev_address is None:
                if existing_record.address == token_record.prev_address:
                    # put after the first record
                    self.records.insert(i + 1, token_record)
                    return
            if existing_record.address is None:
                if existing_record.prev_address == token_record.address:
                    # put before the last record
                    self.records.insert(i, token_record)
                    return
            if existing_record.address == token_record.prev_address:
                # put after matched record in the middle
                self.records.insert(i, token_record)
                return
            if existing_record.prev_address == token_record.address:
                # put before matched record in the middle
                self.records.insert(i, token_record)
                return
        # BAD CASE: put it just before the last record
        self.records.insert(-1, token_record)

    def creator(self):
        """
        """
        return self.records[0]

    def owner(self):
        """
        """
        return self.records[-1]


class TokenBlockchain(json_coin.JsonCoinBlockchain):
    """
    """

    def iterate_records(self, include_inputs=True):
        with self.lock:
            for block in self.longest_chain():
                for transaction_bytes in transactions.unpack_transactions(block.payload):
                    json_transaction = json_coin.JsonTransaction.from_bytes(transaction_bytes)
                    token_records = dict()
                    if include_inputs:
                        for tr_input in json_transaction.inputs:
                            token_id, _ = unpack_token(tr_input[4])
                            if not token_id:
                                continue
                            if token_id in token_records:
                                raise ValueError('duplicated token ID in transaction inputs')
                            token_records[token_id] = [tr_input, None, ]
                    for tr_output in json_transaction.outputs:
                        token_id, _ = unpack_token(tr_output[2])
                        if not token_id:
                            continue
                        if token_id not in token_records:
                            token_records[token_id] = [None, None, ]
                        token_records[token_id][1] = tr_output
                    for token_id, input_output in token_records.items():
                        tr_input, tr_output = input_output
                        token_record = TokenRecord(
                            block_hash=block.block_hash(),
                            transaction_hash=json_transaction.transaction_hash(),
                        )
                        if tr_input is not None:
                            try:
                                token_record.add_input(tr_input)
                            except ValueError:
                                logging.exception('Failed to add an input to the token record: {}'.format(tr_input))
                                continue
                        if tr_output is not None:
                            try:
                                token_record.add_output(tr_output)
                            except ValueError:
                                logging.exception('Failed to add an output to the token record: {}'.format(tr_output))
                                continue
                        yield token_record

    def iterate_records_by_address(self, address, include_inputs=True):
        """
        """
        with self.lock:
            for token_record in self.iterate_records(include_inputs=include_inputs):
                if token_record.address == address:
                    yield token_record

    def iterate_records_by_token(self, token_id, include_inputs=True):
        """
        """
        with self.lock:
            for token_record in self.iterate_records(include_inputs=include_inputs):
                if token_record.token_id == token_id:
                    yield token_record

    def get_records_by_token(self, token):
        """
        """
        with self.lock:
            return [t for t in self.iterate_records_by_token(token, include_inputs=True)]

    def is_records_for_address(self, address):
        """
        """
        with self.lock:
            for _ in self.iterate_records_by_address(address, include_inputs=False):
                return True
            return False

    def is_records_for_token(self, token):
        """
        """
        with self.lock:
            for _ in self.iterate_records_by_token(token, include_inputs=False):
                return True
            return False

    def get_token_profile(self, token):
        """
        """
        with self.lock:
            try:
                return TokenProfile(self.get_records_by_token(token))
            except ValueError:
                return None

    def get_token_profiles_by_owner(self, address):
        """
        """
        with self.lock:
            result = []
            related_token_ids = set()
            token_records_by_id = dict()
            for token_record in self.iterate_records(include_inputs=True):
                if token_record.token_id not in token_records_by_id:
                    token_records_by_id[token_record.token_id] = []
                token_records_by_id[token_record.token_id].append(token_record)
                if token_record.address == address:
                    related_token_ids.add(token_record.token_id)
            for token_id in related_token_ids:
                result.append(TokenProfile(token_records_by_id[token_id][:]))
            logging.info('{} tokens was found'.format(len(result)))
            return result


class TokenWallet(json_coin.JsonWallet):
    """
    """

    def tokens_list(self):
        return self.blockchain.get_token_profiles_by_owner(self.get_address())

    def token_create(self, token, value, address=None, fee=1, payload=None, auth_data=None):
        """
        """
        with self.lock:
            if self.blockchain.is_records_for_token(token):
                raise Exception('found existing token, but all tokens must be unique')
            return self.make_simple_transaction(
                value,
                address or self.get_address(),
                fee=fee,
                json_data=pack_token(token, [payload, ]),
                auth_data=auth_data,
                spendable_filter=self._skip_all_tokens,
            )

    def token_delete(self, token, address=None, fee=1, auth_data=None):
        """
        """
        with self.lock:
            token_profile = self.blockchain.get_token_profile(token)
            if not token_profile:
                raise Exception('this token is not exist')
            if token_profile.owner().address != self.get_address():
                raise Exception('this token is not belong to you')
            return self.make_simple_transaction(
                token_profile.owner().amount,
                address or self.get_address(),
                fee=fee,
                json_data=None,
                auth_data=auth_data,
                spendable_filter=lambda tr_input: self._skip_tokens_except_one(token, tr_input),
            )

    def token_transfer(self, token, new_address, new_value=None, fee=1, payload=None, payload_history=True, auth_data=None):
        """
        """
        with self.lock:
            token_profile = self.blockchain.get_token_profile(token)
            if not token_profile:
                raise Exception('this token is not exist')
            if token_profile.owner().address != self.get_address():
                raise Exception('this token is not belong to you')
            payloads = token_profile.owner().output_payloads
            if payload:
                if payload_history:
                    payloads += [payload, ]
                else:
                    payloads = [payload, ]
            new_value = new_value or token_profile.owner().amount
            return self.make_simple_transaction(
                new_value,
                new_address,
                fee=fee,
                json_data=pack_token(token, payloads),
                auth_data=auth_data,
                spendable_filter=lambda tr_input: self._skip_tokens_except_one(token, tr_input),
            )

    def _skip_all_tokens(self, tr_input):
        """
        Filter input tuple and return bool result.
        If input does not contain a token, then those coins are spendable.
        """
        token_id, _ = unpack_token(tr_input[4])
        return token_id is None

    def _skip_tokens_except_one(self, spendable_token, tr_input):
        """
        Filter input tuple and return bool result.
        If input does not contain a token or we want to "delete/sell" this token,
        then those coins are spendable.
        """
        token_id, _ = unpack_token(tr_input[4])
        return token_id is None or token_id == spendable_token
