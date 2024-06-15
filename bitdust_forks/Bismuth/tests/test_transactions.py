# Basic transaction tests on regnet
# Run with: python3 -m pytest -v or pytest -v
# The regnet server is started by conftest.py

import sys
from time import sleep
# from base64 import b64encode
sys.path.append('../')
from common import get_client
from bismuthcore.transaction import Transaction
from polysign.signerfactory import SignerFactory


def test_amount_and_recipient(myserver, verbose=False):
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    client.send(recipient=client.address, amount=1.0)  # Tries to send 1.0 to self
    client.command(command='regtest_generate', options=[1])  # Mine the next block
    sleep(1)
    tx = client.latest_transactions(num=1)
    if verbose:
        print(f'latest_transactions returns {tx}')
    assert float(tx[0]['amount']) == 1.0
    assert tx[0]['recipient'] == client.address


def test_sender_and_recipient_balances(myserver, verbose=False):
    recipient = '8342c1610de5d7aa026ca7ae6d21bd99b1b3a4654701751891f08742'
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    client.clear_cache()

    balance_sender_before = float(client.balance())
    balance = client.command(command='balanceget', options=[recipient])
    if verbose:
        print(f'balanceget (before) returns {balance}')
    balance_recipient_before = float(balance[0])

    client.send(recipient=recipient, amount=1.0)
    sleep(1)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    client.clear_cache()

    tx = client.latest_transactions(num=2)
    balance_sender_after = float(client.balance())
    balance = client.command(command='balanceget', options=[recipient])
    if verbose:
        print(f'balanceget (after) returns {balance}')
    balance_recipient_after = float(balance[0])
    diff1 = balance_sender_after - balance_sender_before - float(tx[1]['reward']) + float(tx[0]['fee'])
    diff2 = balance_recipient_after - balance_recipient_before
    assert abs(diff1 + 1.0) < 1e-6
    assert diff2 == 1.0


def test_tx_id(myserver, verbose=False):
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    txid = client.send(recipient=client.address, amount=1.0)  # Tries to send 1.0 to self
    client.command(command='regtest_generate', options=[1])  # Mine the next block
    sleep(1)
    tx = client.latest_transactions(num=1)
    if verbose:
        print(f'latest_transactions returns {tx}')
    assert tx[0]['signature'][:56] == txid


def test_operation_and_openfield(myserver, verbose=False):
    operation = 'test:1'
    data = 'Bismuth'
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    client.send(recipient=client.address, amount=0.0, operation=operation, data=data)
    client.command(command='regtest_generate', options=[1])  # Mine the next block
    sleep(1)
    tx = client.latest_transactions(num=1)
    if verbose:
        print(f'latest_transactions returns {tx}')
    assert tx[0]['operation'] == operation
    assert tx[0]['openfield'] == data


def test_spend_entire_balance(myserver, verbose=False):
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    client.clear_cache()
    balance = float(client.balance())
    fee = 0.01
    recipient = '8342c1610de5d7aa026ca7ae6d21bd99b1b3a4654701751891f08742'
    client.send(recipient=recipient, amount=balance - fee)
    client.command(command='regtest_generate', options=[1])  # Mine the next block
    sleep(1)
    client.clear_cache()
    balance = float(client.balance())
    if verbose:
        print(f'balance returns {balance}')
    tx = client.latest_transactions(num=2)
    if verbose:
        print(f'tx returns {tx}')
    assert abs(balance - float(tx[1]['reward'])) < 1e-6


def test_send_more_than_owned(myserver, verbose=False):
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    client.clear_cache()
    balance = float(client.balance())
    recipient = '8342c1610de5d7aa026ca7ae6d21bd99b1b3a4654701751891f08742'
    client.send(recipient=recipient, amount=balance)
    client.command(command='regtest_generate', options=[1])  # Mine the next block
    sleep(1)
    client.clear_cache()
    balance = float(client.balance())
    if verbose:
        print(f'balance returns {balance}')
    assert balance > 1.0


def test_send_more_than_owned_in_two_transactions(myserver, verbose=False):
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    client.clear_cache()
    balance = float(client.balance())
    recipient = '8342c1610de5d7aa026ca7ae6d21bd99b1b3a4654701751891f08742'
    client.send(recipient=recipient, amount=1.0)
    client.send(recipient=recipient, amount=balance - 1.0)
    client.command(command='regtest_generate', options=[1])  # Mine the next block
    sleep(1)
    client.clear_cache()
    balance = float(client.balance())
    if verbose:
        print(f'balance returns {balance}')
    assert balance > 1.0


def test_fee(myserver, verbose=False):
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    data = '12345678901234567890123456789012345678901234567890'
    client.send(recipient=client.address, amount=0, data=data)
    client.command(command='regtest_generate', options=[1])  # Mine the next block
    sleep(1)
    tx = client.latest_transactions(num=1)
    if verbose:
        print(f'latest_transactions returns {tx}')
    assert float(tx[0]['fee']) == 0.01 + 1e-5*len(data)


def test_operation_length(myserver, verbose=False):
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block so we have some funds
    operation = '123456789012345678901234567890'
    client.send(recipient=client.address, amount=0, operation=operation)
    operation = '1234567890123456789012345678901'
    client.send(recipient=client.address, amount=0, operation=operation)
    client.command(command='regtest_generate', options=[1])  # Mine the next block
    sleep(1)
    tx = client.latest_transactions(num=2)
    if verbose:
        print(f'latest_transactions returns {tx}')
    assert len(tx[0]['operation']) == 30
    assert len(tx[1]['operation']) == 1


def test_tx_signature(myserver, verbose=False):
    client = get_client(verbose=verbose)
    client.command(command='regtest_generate', options=[1])  # Mine a block
    sleep(1)
    r = client.command(command='blocklast')
    if verbose:
        print(f'blocklast returns {r}')
    tx = Transaction.from_legacy_params(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11])
    buffer = tx.to_buffer_for_signing()
    db_signature_enc = r[5]
    db_public_key_b64encoded = r[6]  # For rsa, once decoded, this gives a properly formatted ---begin.... pubkey
    db_address = r[2]
    signed = True
    try:
        SignerFactory.verify_bis_signature(db_signature_enc, db_public_key_b64encoded, buffer, db_address)
    except Exception:
        signed = False
    assert signed


if __name__ == '__main__':
    test_amount_and_recipient(None, True)
    test_sender_and_recipient_balances(None, True)
    test_tx_id(None, True)
    test_operation_and_openfield(None, True)
    test_spend_entire_balance(None, True)
    test_send_more_than_owned(None, True)
    test_send_more_than_owned_in_two_transactions(None, True)
    test_fee(None, True)
    test_operation_length(None, True)
    test_tx_signature(None, True)
