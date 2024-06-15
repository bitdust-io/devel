# optipoolware.py v 0.397 to be used with Python3.5 or later
# Bismuth pool mining software
# Copyright Hclivess, Maccaspacca 2017, 2018
# for license see LICENSE file
# .

import socketserver, connections, time, options, log, sqlite3, socks, random, re, essentials, base64, sys, os, math
from Cryptodome.Hash import SHA
from Cryptodome.Signature import PKCS1_v1_5
from Cryptodome.PublicKey import RSA
import threading
import json

import logging
import mining_heavy3 as mining

config = options.Get()
config.read()
port = config.port
node_ip_conf = config.node_ip
ledger_path_conf = 'static/ledger.db'
#tor_conf = config.tor
debug_level_conf = config.debug_level
version = config.version

if version == 'testnet':
    port = '2829'
    m_peer_file = 'peers_test.txt'
    ledger_path_conf = 'static/test.db'
else:
    m_peer_file = 'peers.txt'

print('Peers file: {}'.format(m_peer_file))

# print(version)

# load config

#key, public_key_readable, private_key_readable, _, _, public_key_hashed, address = essentials.keys_load ("privkey.der", "pubkey.der")
key, public_key_readable, private_key_readable, encrypted, unlocked, public_key_hashed, address, keyfile = essentials.keys_load('privkey.der', 'pubkey.der')

app_log = log.log('pool.log', debug_level_conf)

# This part is what goes on console.
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(funcName)s(%(lineno)d) %(message)s')
ch.setFormatter(formatter)
app_log.addHandler(ch)
new_time = 0
new_diff = 0

print('Pool Address: {}'.format(address))

# load config
try:

    lines = [line.rstrip('\n') for line in open('pool.txt')]
    for line in lines:
        try:
            if 'mine_diff=' in line:
                mdiff = int(line.split('=')[1])
        except Exception as e:
            mdiff = 65
        try:
            if 'min_payout=' in line:
                min_payout = float(line.split('=')[1])
        except Exception as e:
            min_payout = 1
        try:
            if 'pool_fee=' in line:
                pool_fee = float(line.split('=')[1])
        except Exception as e:
            pool_fee = 0
        try:
            if 'alt_fee=' in line:
                alt_fee = float(line.split('=')[1])
        except Exception as e:
            alt_fee = 0
        try:
            if 'worker_time=' in line:
                w_time = int(line.split('=')[1])
        except Exception as e:
            w_time = 10
        try:
            if 'alt_add=' in line:
                alt_add = str(line.split('=')[1])
        except Exception as e:
            alt_add = '1aae2cfe5d01acc8d7cbc90fcf8bb715ca24927504d0d8071c0979c7'

except Exception as e:
    min_payout = 1
    mdiff = 65
    pool_fee = 0
    alt_fee = 0
    w_time = 10
    alt_add = '1aae2cfe5d01acc8d7cbc90fcf8bb715ca24927504d0d8071c0979c7'
# load config

#m = socks.socksocket()
#m.connect((node_ip_conf, int(port)))  # connect to local node
#connections.send(m, "api_mempool", 10)
#tresult = connections.receive(m, 10)
#m.close()

#print(tresult)

bin_format_dict = dict((x, format(ord(x), '8b').replace(' ', '0')) for x in '0123456789abcdef')


def percentage(percent, whole):
    return int((percent*whole)/100)


def checkdb():
    shares = sqlite3.connect('shares.db')
    shares.text_factory = str
    s = shares.cursor()
    s.execute('SELECT * FROM shares')
    present = s.fetchall()

    if not present:
        return False
    else:
        return True


# payout processing


def payout(payout_threshold, myfee, othfee):
    global node_ip_conf
    global port

    print('Minimum payout is {} Bismuth'.format(str(payout_threshold)))
    print('Current pool fee is {} Percent'.format(str(myfee)))

    shares = sqlite3.connect('shares.db')
    shares.text_factory = str
    s = shares.cursor()

    conn = sqlite3.connect(ledger_path_conf, timeout=60.0)
    conn.text_factory = str
    c = conn.cursor()

    #get sum of all shares not paid
    s.execute('SELECT sum(shares) FROM shares WHERE paid != 1')
    shares_total = s.fetchone()[0]
    #get sum of all shares not paid

    #get block threshold
    try:
        s.execute('SELECT min(timestamp) FROM shares WHERE paid != 1')
        block_threshold = float(s.fetchone()[0])
    except:
        block_threshold = time.time()
    #get block threshold

    #get eligible blocks
    reward_list = []
    for row in c.execute('SELECT * FROM transactions WHERE address = ? AND CAST(timestamp AS INTEGER) >= ? AND reward != 0', (address, ) + (block_threshold, )):
        reward_list.append(float(row[9]))

    super_total = sum(reward_list)
    #get eligible blocks

    # so now we have sum of shares, total reward, block threshold

    # reduce total rewards by total fees percentage
    reward_total = '%.8f' % (((100 - (myfee + othfee))*super_total)/100)
    reward_total = float(reward_total)

    if reward_total > 0:

        # calculate alt address fee

        ft = super_total - reward_total
        try:
            at = '%.8f' % (ft*(othfee/(myfee + othfee)))
        except:
            at = 0

        # calculate reward per share
        reward_per_share = reward_total/shares_total

        # calculate shares threshold for payment

        shares_threshold = math.floor(payout_threshold/reward_per_share)

        #get unique addresses
        addresses = []
        for row in s.execute('SELECT * FROM shares'):
            shares_address = row[0]

            if shares_address not in addresses:
                addresses.append(shares_address)
        print('payout address', addresses)
        #get unique addresses

        # prepare payout address list with number of shares and new total shares
        payadd = []
        new_sum = 0
        for x in addresses:
            s.execute('SELECT sum(shares) FROM shares WHERE address = ? AND paid != 1', (x, ))
            shares_sum = s.fetchone()[0]

            if shares_sum == None:
                shares_sum = 0
            if shares_sum > shares_threshold:
                payadd.append([x, shares_sum])
                new_sum = new_sum + shares_sum
        #prepare payout address list with number of shares and new total shares

        # recalculate reward per share now we have removed those below payout threshold
        try:

            reward_per_share = reward_total/new_sum

        except:
            reward_per_share = 0

        print('reward_per_share', reward_per_share)

        paylist = []
        for p in payadd:
            payme = '%.8f' % (p[1]*reward_per_share)
            paylist.append([p[0], payme])

        if othfee > 0:
            paylist.append([alt_add, at])

        payout_passed = 0
        for r in paylist:
            print(r)
            recipient = r[0]
            claim = float(r[1])

            payout_passed = 1
            openfield = 'pool'
            keep = 0
            fee = float('%.8f' % float(0.01 + (float(len(openfield))/100000) + (keep)))  # 0.01 + openfield fee + keep fee
            #make payout

            timestamp = '%.2f' % time.time()
            transaction = (str(timestamp), str(address), str(recipient), '%.8f' % float(claim - fee), str(keep), str(openfield))  # this is signed
            # print transaction

            h = SHA.new(str(transaction).encode('utf-8'))
            signer = PKCS1_v1_5.new(key)
            signature = signer.sign(h)
            signature_enc = base64.b64encode(signature)
            print('Encoded Signature: {}'.format(signature_enc.decode('utf-8')))

            verifier = PKCS1_v1_5.new(key)
            if verifier.verify(h, signature) == True:
                print('The signature is valid, proceeding to send transaction')
                txid = signature_enc[:56]
                mytxid = txid.decode('utf-8')
                tx_submit = (str(timestamp), str(address), str(recipient), '%.8f' % float(claim - fee), str(signature_enc.decode('utf-8')), str(public_key_hashed.decode('utf-8')), str(keep), str(openfield))  #float kept for compatibility

                t = socks.socksocket()
                t.connect((node_ip_conf, int(port)))  # connect to local node

                connections.send(t, 'mpinsert', 10)
                connections.send(t, [tx_submit], 10)
                reply = connections.receive(t, 10)
            else:
                print('Invalid signature')
                reply = 'Invalid signature'

                print('Transaction sent with txid: {}'.format(mytxid))

            t.close()

            s.execute('UPDATE shares SET paid = 1 WHERE address = ?', (recipient, ))
            shares.commit()

        if payout_passed == 1:
            s.execute('UPDATE shares SET timestamp = ?', (time.time(), ))
            shares.commit()

        # calculate payouts
        #payout

        # archive paid shares
        s.execute('SELECT * FROM shares WHERE paid = 1')
        pd = s.fetchall()

        if pd == None:
            pass
        else:
            archive = sqlite3.connect('archive.db')
            archive.text_factory = str
            a = archive.cursor()

            for sh in pd:
                a.execute('INSERT INTO shares VALUES (?,?,?,?,?,?,?,?)', (sh[0], sh[1], sh[2], sh[3], sh[4], sh[5], sh[6], sh[7]))

            archive.commit()
            a.close()
        # archive paid shares

    # clear nonces
    s.execute('DELETE FROM nonces')
    s.execute('DELETE FROM shares WHERE paid = 1')
    shares.commit()
    s.execute('VACUUM')
    #clear nonces
    s.close()


def commit(cursor):
    # secure commit for slow nodes
    passed = 0
    while passed == 0:
        try:
            cursor.commit()
            passed = 1
        except Exception as e:
            app_log.warning('Retrying database execute due to ' + str(e))
            time.sleep(random.random())
            # secure commit for slow nodes


def execute(cursor, what):
    # secure execute for slow nodes
    passed = 0
    while passed == 0:
        try:
            # print cursor
            # print what

            cursor.execute(what)
            passed = 1
        except Exception as e:
            app_log.warning('Retrying database execute due to {}'.format(e))
            time.sleep(random.random())
            # secure execute for slow nodes
    return cursor


def execute_param(cursor, what, param):
    # secure execute for slow nodes
    passed = 0
    while passed == 0:
        try:
            # print cursor
            # print what
            cursor.execute(what, param)
            passed = 1
        except Exception as e:
            app_log.warning('Retrying database execute due to ' + str(e))
            time.sleep(0.1)
            # secure execute for slow nodes
    return cursor


def bin_convert(string):
    return ''.join(bin_format_dict[x] for x in string)


def bin_convert_orig(string):
    return ''.join(format(ord(x), '8b').replace(' ', '0') for x in string)


def s_test(testString):

    if testString.isalnum():
        if (re.search('[abcdef]', testString)):
            if len(testString) == 56:
                return True
    else:
        return False


def n_test(testString):

    if testString.isalnum():
        if (re.search('[abcdef]', testString)):
            if len(testString) < 129:
                return True
    else:
        return False


def paydb():
    global new_time
    while True:
        app_log.warning('Payout run finished')
        time.sleep(3601)
        #time.sleep(60) # test
        v = float('%.2f' % time.time())
        v1 = new_time
        v2 = v - v1

        if v2 < 100000:
            payout(min_payout, pool_fee, alt_fee)
            app_log.warning('Payout running...')
        else:
            app_log.warning('Node over 1 mins out: %r ...payout delayed' % v2)


def worker(s_time):
    global new_diff
    global new_hash
    global new_time
    doclean = 0

    n = socks.socksocket()
    n.connect((node_ip_conf, int(port)))  # connect to local node

    while True:

        time.sleep(s_time)
        #doclean +=1

        try:

            app_log.warning('Worker task...')
            connections.send(n, 'blocklast', 10)
            blocklast = connections.receive(n, 10)

            connections.send(n, 'diffget', 10)
            diff = connections.receive(n, 10)

            new_hash = blocklast[7]
            new_time = blocklast[1]
            new_diff = math.floor(diff[1])

            app_log.warning('Difficulty = {}'.format(str(new_diff)))
            app_log.warning('Blockhash = {}'.format(str(new_hash)))
            # print("Worker")

        except Exception as e:
            app_log.warning(str(e))
    n.close()


# TODO: for tests only
#os.remove('shares.db')
#os.remove('archive.db')

if not os.path.exists('shares.db'):
    # create empty shares
    shares = sqlite3.connect('shares.db')
    shares.text_factory = str
    s = shares.cursor()
    execute(s, 'CREATE TABLE IF NOT EXISTS shares (address, shares, timestamp, paid, rate, name, workers, subname)')
    execute(s, 'CREATE TABLE IF NOT EXISTS nonces (nonce)')  #for used hash storage
    app_log.warning('Created shares file')
    s.close()
    # create empty shares
if not os.path.exists('archive.db'):
    # create empty archive
    archive = sqlite3.connect('archive.db')
    archive.text_factory = str
    a = archive.cursor()
    execute(a, 'CREATE TABLE IF NOT EXISTS shares (address, shares, timestamp, paid, rate, name, workers, subname)')
    app_log.warning('Created archive file')
    a.close()
    # create empty archive
"""
if checkdb():
    payout(min_payout,pool_fee,alt_fee)
"""


class MyTCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global new_diff
        key = RSA.importKey(private_key_readable)

        self.allow_reuse_address = True

        peer_ip = self.request.getpeername()[0]

        try:
            data = connections.receive(self.request, 10)

            app_log.warning('Received: {} from {}'.format(data, peer_ip))  # will add custom ports later

            if data == 'getwork':  # sends the miner the blockhash and mining diff for shares

                work_send = []
                work_send.append((new_hash, mdiff, address, mdiff))

                connections.send(self.request, work_send, 10)

                print('Work package sent.... {}'.format(str(new_hash)))

            elif data == 'block':  # from miner to node

                # sock
                #s1 = socks.socksocket()
                #if tor_conf == 1:
                #	s1.setproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050)
                #s1.connect(("127.0.0.1", int(port)))  # connect to local node,
                # sock

                # receive nonce from miner
                miner_address = connections.receive(self.request, 10)

                if not s_test(miner_address):

                    app_log.warning('Bad Miner Address Detected - Changing to default')
                    miner_address = alt_add
                    #s1.close()

                else:

                    app_log.warning('Received a solution from miner {} ({})'.format(peer_ip, miner_address))

                    block_nonce = connections.receive(self.request, 10)
                    block_timestamp = (block_nonce[-1][0])
                    nonce = (block_nonce[-1][1])
                    mine_hash = ((block_nonce[-1][2]))  # block hash claimed
                    ndiff = ((block_nonce[-1][3]))  # network diff when mined
                    sdiffs = ((block_nonce[-1][4]))  # actual diff mined
                    mrate = ((block_nonce[-1][5]))  # total hash rate in khs
                    bname = ((block_nonce[-1][6]))  # base worker name
                    wnum = ((block_nonce[-1][7]))  # workers
                    wstr = ((block_nonce[-1][8]))  # worker number
                    wname = '{}{}'.format(bname, wstr)  # worker name

                    app_log.warning('Mined nonce details: {}'.format(block_nonce))
                    app_log.warning('Claimed hash: {}'.format(mine_hash))
                    app_log.warning('Claimed diff: {}'.format(sdiffs))

                    if not n_test(nonce):
                        app_log.warning('Bad Nonce Format Detected - Closing Connection')
                        self.close
                    app_log.warning('Processing nonce.....')

                    diff = new_diff
                    db_block_hash = mine_hash

                    real_diff = mining.diffme_heavy3(address, nonce, db_block_hash)
                    """
                    mining_hash = bin_convert_orig(hashlib.sha224((address + nonce + db_block_hash).encode("utf-8")).hexdigest())
                    mining_condition = bin_convert_orig(db_block_hash)[0:diff]

                    if mining_condition in mining_hash:
                    """
                    app_log.warning('Solution has {} difficulty, current difficulty is {}'.format(real_diff, diff))
                    if real_diff >= int(diff):

                        app_log.warning('Difficulty requirement satisfied for mining')
                        app_log.warning('Sending block to nodes')

                        cn = options.Get()
                        cn.read()
                        cport = cn.port
                        try:
                            cnode_ip_conf = cn.node_ip_conf
                        except:
                            cnode_ip_conf = cn.node_ip

                        #ctor_conf = cn.tor_conf
                        cversion = cn.version

                        if cversion == 'testnet':
                            cport = '2829'
                            m_peer_file = 'peers_test.txt'
                        else:
                            m_peer_file = 'peers.txt'

                        app_log.warning('Local node ip {} on port {}'.format(cnode_ip_conf, cport))

                        m = socks.socksocket()
                        m.connect((cnode_ip_conf, int(cport)))  # connect to local node
                        connections.send(m, 'api_mempool', 10)
                        result = connections.receive(m, 10)
                        app_log.warning('I have got to receive mempool')
                        m.close()

                        # include data
                        block_send = []
                        del block_send[:]  # empty
                        removal_signature = []
                        del removal_signature[:]  # empty

                        app_log.warning('prepare empty block and clear data')

                        for dbdata in result:
                            transaction = (str(dbdata[0]), str(dbdata[1][:56]), str(dbdata[2][:56]), '%.8f' % float(dbdata[3]), str(dbdata[4]), str(dbdata[5]), str(dbdata[6]), str(dbdata[7]))  # create tuple
                            block_send.append(transaction)  # append tuple to list for each run
                            removal_signature.append(str(dbdata[4]))  # for removal after successful mining

                        # claim reward
                        transaction_reward = tuple
                        transaction_reward = (str(block_timestamp), str(address[:56]), str(address[:56]), '%.8f' % float(0), '0', str(nonce))  # only this part is signed!
                        print('transaction_reward', transaction_reward)

                        h = SHA.new(str(transaction_reward).encode('utf-8'))
                        signer = PKCS1_v1_5.new(key)
                        signature = signer.sign(h)
                        signature_enc = base64.b64encode(signature)

                        if signer.verify(h, signature) == True:
                            app_log.warning('Signature valid')

                            block_send.append((str(block_timestamp), str(address[:56]), str(address[:56]), '%.8f' % float(0), str(signature_enc.decode('utf-8')), str(public_key_hashed.decode('utf-8')), '0', str(nonce)))  # mining reward tx
                            # app_log.warning('Block to send: {}'.format(block_send))

                            if not any(isinstance(el, list) for el in block_send):  # if it's not a list of lists (only the mining tx and no others)
                                new_list = []
                                new_list.append(block_send)
                                block_send = new_list  # make it a list of lists
                                app_log.warning(block_send)

                        global peer_dict
                        peer_dict = {}

                        with open(m_peer_file) as f:
                            peer_dict = json.load(f)

                            app_log.warning(peer_dict)

                            for k, v in peer_dict.items():
                                peer_ip = k
                                # app_log.info(HOST)
                                peer_port = int(v)
                                # app_log.info(PORT)
                                # connect to all nodes

                                try:
                                    s = socks.socksocket()
                                    s.settimeout(0.3)
                                    #if ctor_conf == 1:
                                    #    s.setproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050)
                                    s.connect((peer_ip, int(peer_port)))  # connect to node in peerlist
                                    app_log.warning('Connected')

                                    app_log.warning('Miner: Proceeding to submit mined block')

                                    connections.send(s, 'block', 10)
                                    #connections.send(s, address, 10)
                                    connections.send(s, block_send, 10)

                                    app_log.warning('Miner: Block submitted to {}'.format(peer_ip))
                                except Exception as e:
                                    app_log.warning('Miner: Could not submit block to {} because {}'.format(peer_ip, e))

                    if diff < mdiff:
                        diff_shares = diff
                    else:
                        diff_shares = mdiff

                    shares = sqlite3.connect('shares.db')
                    shares.text_factory = str
                    s = shares.cursor()

                    # protect against used share resubmission
                    execute_param(s, ('SELECT nonce FROM nonces WHERE nonce = ?'), (nonce, ))

                    try:
                        result = s.fetchone()[0]
                        app_log.warning('Miner trying to reuse a share, ignored')
                    except:
                        # protect against used share resubmission
                        """
                        mining_condition = bin_convert_orig(db_block_hash)[0:diff_shares] #floor set by pool
                        if mining_condition in mining_hash:
                        """
                        if real_diff >= diff_shares:
                            app_log.warning('Difficulty requirement satisfied for saving shares \n')

                            execute_param(s, ('INSERT INTO nonces VALUES (?)'), (nonce, ))
                            commit(shares)

                            timestamp = '%.2f' % time.time()

                            s.execute('INSERT INTO shares VALUES (?,?,?,?,?,?,?,?)', (str(miner_address), str(1), timestamp, '0', str(mrate), bname, str(wnum), wname))
                            shares.commit()

                        else:
                            app_log.warning('Difficulty requirement not satisfied for anything \n')

                    s.close()

            self.request.close()
        except Exception as e:
            app_log.error('Error: {}'.format(e))

    app_log.warning('Starting up...')


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


if __name__ == '__main__':

    mining.mining_open()

    try:
        # Disabling payouts
        # background_thread = threading.Thread(target=paydb)
        # background_thread.daemon = True
        # background_thread.start()

        worker_thread = threading.Thread(target=worker, args=(w_time, ))
        worker_thread.daemon = True
        worker_thread.start()
        app_log.warning('Starting up background tasks....')
        time.sleep(10)

        try:
            pool_port = int(sys.argv[1])
        except Exception as e:
            pool_port = 8525

        HOST, PORT = '0.0.0.0', pool_port

        # Create the server thread handler, binding to localhost on port above
        server = ThreadedTCPServer((HOST, PORT), MyTCPHandler)
        ip, server_port = server.server_address

        server_thread = threading.Thread(target=server.serve_forever)

        server_thread.daemon = True
        server_thread.start()
        server_thread.join()
        server.shutdown()
        server.server_close()
    finally:
        mining.mining_close()
