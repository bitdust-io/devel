#WARNING: this file uses the old wallet structure, there is no need to update it at the moment

import hashlib
import sqlite3
import os
import sys
import time
import base64

from Cryptodome.PublicKey import RSA
from Cryptodome.Signature import PKCS1_v1_5
from Cryptodome.Hash import SHA

DIFFICULTY = 10

if os.path.isfile('privkey.der'):
    print('privkey.der found')
elif os.path.isfile('privkey_encrypted.der'):
    print('privkey_encrypted.der found')

else:
    # generate key pair and an address
    key = RSA.generate(4096)
    public_key = key.publickey()

    private_key_readable = str(key.exportKey().decode('utf-8'))
    public_key_readable = str(key.publickey().exportKey().decode('utf-8'))
    address = hashlib.sha224(public_key_readable.encode('utf-8')).hexdigest()  # hashed public key
    # generate key pair and an address

    print('Your address: {}'.format(address))
    print('Your private key:\n {}'.format(private_key_readable))
    print('Your public key:\n {}'.format(public_key_readable))

    with open('privkey.der', 'a') as f:
        f.write(str(private_key_readable))

    with open('pubkey.der', 'a') as f:
        f.write(str(public_key_readable))

    with open('address.txt', 'a') as f:
        f.write('{}\n'.format(address))

# import keys
key = RSA.importKey(open('privkey.der').read())
public_key = key.publickey()
private_key_readable = str(key.exportKey().decode('utf-8'))
public_key_readable = str(key.publickey().exportKey().decode('utf-8'))
address = hashlib.sha224(public_key_readable.encode('utf-8')).hexdigest()

print('Your address: {}'.format(address))
print('Your private key:\n {}'.format(private_key_readable))
print('Your public key:\n {}'.format(public_key_readable))
public_key_b64encoded = base64.b64encode(public_key_readable.encode('utf-8'))
# import keys

timestamp = str(time.time())
print('Timestamp: {}'.format(timestamp))
transaction = (timestamp, 'genesis', address, str(float(100000000)), 'genesis')
h = SHA.new(str(transaction).encode('utf-8'))
signer = PKCS1_v1_5.new(key)
signature = signer.sign(h)
signature_enc = base64.b64encode(signature)
print('Encoded Signature: {}'.format(signature_enc))
block_hash = hashlib.sha224(str((timestamp, transaction)).encode('utf-8')).hexdigest()  # first hash is simplified
print('Transaction Hash: {}'.format(block_hash))

if os.path.isfile('static/ledger.db'):
    print('You are beyond genesis')
else:
    # transaction processing
    cursor = None
    mem_cur = None
    try:
        conn = sqlite3.connect('static/ledger.db')
        cursor = conn.cursor()

        cursor.execute('CREATE TABLE IF NOT EXISTS "misc" ("block_height" INTEGER, "difficulty" TEXT)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS "transactions" ("block_height" INTEGER, "timestamp" NUMERIC, "address" TEXT, "recipient" TEXT, "amount" NUMERIC, "signature" TEXT, "public_key" TEXT, "block_hash" TEXT, "fee" NUMERIC, "reward" NUMERIC, "operation" TEXT, "openfield" TEXT)',
        )
        cursor.execute('CREATE INDEX "Timestamp Index" ON "transactions" ("timestamp")')
        cursor.execute('CREATE INDEX "Signature Index" ON "transactions" ("signature")')
        cursor.execute('CREATE INDEX "Reward Index" ON "transactions" ("reward")')
        cursor.execute('CREATE INDEX "Recipient Index" ON "transactions" ("recipient")')
        cursor.execute('CREATE INDEX "Openfield Index" ON "transactions" ("openfield")')
        cursor.execute('CREATE INDEX "Fee Index" ON "transactions" ("fee")')
        cursor.execute('CREATE INDEX "Block Height Index" ON "transactions" ("block_height")')
        cursor.execute('CREATE INDEX "Block Hash Index" ON "transactions" ("block_hash")')
        cursor.execute('CREATE INDEX "Amount Index" ON "transactions" ("amount")')
        cursor.execute('CREATE INDEX "Address Index" ON "transactions" ("address")')
        cursor.execute('CREATE INDEX "Operation Index" ON "transactions" ("operation")')
        cursor.execute('CREATE INDEX TXID4_Index ON transactions(substr(signature,1,4))')
        cursor.execute('CREATE INDEX "Misc Block Height Index" on misc(block_height)')
        # cursor.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
        #     '1', '1574712979.530888', 'genesis', 'bc33dfda25a44f11ad41875e8bac85a7e876436f1d308130e0bc00f6', '0',
        #     'cacdDgpCAvSa04B9De522kvGmGKL1HG85XInoEwlSEOCGLPTI+lMjdc6VHPFakmyPFT5fosnWhdHJx8rAJh5UUmmZgNd6jFf1N5hom/PAJLGVyDmXXbcH1YzNvBXUJdwBV/M3YtK+t5hWr9D10tw3ahywNwQddAO4IJj6jeFuc9ApJUhRNpMy7PIgyaisMIJPylBGvSU4Wbyxx2DDSXTJ2kLHn4vJgRtpcSCTHFlCtVwVF0GpeWkwilKA+AgcFtLRvB4ead1w68diX+SocLXNueccAzlDnYL5h5C/QaP9AG8cBquHh4VLruBoXcRzKXjONKMIqhJKAgOdjo0Tmtrp7XH8PGYfmHAVChXHyE3lHm3qadAW5AFWNQigNHd5imlTl1Tz8wjBI/W5epag7WCr/s+3HkwdNY7eLiHCvp1lrWIuFqnLDVASIjIjMKffv+j3VKKXVh7wLeM4VuOqs6EQnmUpyXqQvJPz8ZJvaTWVzyVnEXteqfzG5UbSYhjZV10pDUlhxVfx3IfvdFzm8viZPTaI+8HNy8VWED0tLQRwlz/147aC2rtz0CBgO7tM3NdD9SGJzQ3l0iB055i32YREH+DpE9QpM9mDv+tAStNjE/ZuHsNehtOC3CED15N410aHtXyXC0VvbxL6bKH7FKeJEq+HcAHxVq5+JxJzsIE5pE=',
        #     'LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQ0lqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FnOEFNSUlDQ2dLQ0FnRUF2OUpSSmJ0REJsMTc3OTBxWjB1TwpTRW0rVUZFOXU3SENIb2JlblFmc0RNWEFyZ3J1dTFmdlM0VUh0RW55VFI0dnJsNGpybUxJNmVhaCtDTjZHSno0CnRja1ZTV2FQOTNWVm5iNkpPTStTdzdTckd6MHlOR1E5KzVRMXI2NXZNVjZKWWQrK3VTNjJPUDdkZHN1MzJGMTcKK2d0UEV2OUIrNUZ6bm9ya25BRzh2SitEVmFHSTh1RGt3bzFZSXlHL0VNVCtXaVZJcGI4UWZFNzlxK2NKdHF6agpkNklEYWFhdjdSWEpxZU04Q2ZTR05rYWFvSEZ0YStBZFV3Q0syVHdtOW5JZjBqRWxwVENHcnNjMzRLYVlMRGh0CmVWbkZSRWVsbGhyR2FiMmgwR3M2azdPbmJ5TXoxYkFhb0dGNk9acG45MEkwYmVGRmZuN3dnWXZJWUMwanNIcVEKZGowZlhhUGo1bGRETGR4bHJmWVBwcTVacXRyVEcyeU1FTmhYRzZYbFEyOENZS0psRGR3SmRFMHRTWm1pc1lnVwoxVnlEYkxtUjUzQ3JSR1dTTENrY05BSWlSRHYrM2ZSRXlWV0d3MmM3bEEwVHFueFJyN01rZFhiTjZiRDJSTVhECk00ZFBHWTZzZllMVU9OZGFUYS82ZkduR0NqTXRBNVZGTXpuUEhBcmdjSmpJSzZDeGJ6aTYxVnA0QzFJRzF4bk8KYkJIM1BtSUE3Qmh0ZEtWUmxucWZ2M1p6d1g0RFVEWEdLTm5qNVlKQ2pvUm9pUFN4ZW85ajM2OFBkRnU5OHVLcgpRTGpqZFo3b1hFMTVxVW5TeWIrWjdXQjlHNnBQT3dtRjQ0T0dka2lkQjRCS1pzb2Fzb09oUVBlMUhpVTVLdGh3CmlNQ0UzZnJiUDlJSTBtMWNWYWZUbHlVQ0F3RUFBUT09Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQ==',
        #     'c5adf0949d1e678de1e9a8708045a474eb8022f8029bf01e7e975e5a', 0, 1, 1, 'genesis',
        # ))
        cursor.execute('INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', ('1', timestamp, 'genesis', address, '0', signature_enc.decode('utf-8'), public_key_b64encoded, block_hash, 0, 1, 1, 'genesis'))  # Insert a row of data
        cursor.execute('INSERT INTO misc (difficulty, block_height) VALUES ({},1)'.format(DIFFICULTY))
        conn.commit()  # Save (commit) the changes

        mempool = sqlite3.connect('mempool.db')
        mem_cur = mempool.cursor()
        mem_cur.execute('CREATE TABLE transactions (timestamp, address, recipient, amount, signature, public_key, operation, openfield)')
        mempool.commit()
        conn.close()
        mempool.close()
        cursor = None
        mem_cur = None

        print('Genesis created.')
    except sqlite3.Error as e:
        print('Error %s:' % e.args[0])
        sys.exit(1)
    finally:
        if cursor is not None:
            cursor.close()
        if mem_cur is not None:
            mem_cur.close()

if os.path.isfile('static/hyper.db'):
    print('You are beyond hyper genesis')
else:
    # transaction processing
    hyper_cursor = None
    try:
        hyper_conn = sqlite3.connect('static/hyper.db')
        hyper_cursor = hyper_conn.cursor()
        hyper_cursor.execute('CREATE TABLE transactions (block_height INTEGER, timestamp, address, recipient, amount, signature, public_key, block_hash, fee, reward, operation, openfield)')
        hyper_cursor.execute(
            'INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', ('1', timestamp, 'genesis', address, '0', signature_enc.decode('utf-8'), public_key_b64encoded, block_hash, 0, 1, 1, 'genesis')
        )  # Insert a row of data
        hyper_cursor.execute('CREATE TABLE misc (block_height INTEGER, difficulty TEXT)')
        hyper_cursor.execute('INSERT INTO misc (difficulty, block_height) VALUES ({},1)'.format(DIFFICULTY))
        # TODO: create indexes
        hyper_conn.commit()  # Save (commit) the changes

        hyper_conn.close()
        hyper_cursor = None

        print('Hyper Genesis created.')
    except sqlite3.Error as e:
        print('Error %s:' % e.args[0])
        sys.exit(1)
    finally:
        if hyper_cursor is not None:
            hyper_cursor.close()

if os.path.isfile('static/index.db'):
    print('Index already exists')
else:
    # transaction processing
    index_cursor = None
    try:
        index_conn = sqlite3.connect('static/index.db')
        index_cursor = index_conn.cursor()
        index_cursor.execute('CREATE TABLE tokens (block_height INTEGER, timestamp, token, address, recipient, txid, amount INTEGER)')
        index_cursor.execute('CREATE TABLE aliases (block_height INTEGER, address, alias)')
        index_cursor.execute('CREATE TABLE staking (block_height INTEGER, timestamp NUMERIC, address, balance, ip, port, pos_address)')
        # TODO: create indexes
        index_conn.commit()  # Save (commit) the changes

        index_conn.close()
        index_cursor = None

        print('Index table created.')
    except sqlite3.Error as e:
        print('Error %s:' % e.args[0])
        sys.exit(1)
    finally:
        if index_cursor is not None:
            index_cursor.close()
