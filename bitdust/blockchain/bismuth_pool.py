import os
import re
import random
import hashlib
import threading
import traceback
import time
import json
import math
import sqlite3
import base64
import socks
import socketserver

from Cryptodome.PublicKey import RSA
from Cryptodome.Hash import SHA
from Cryptodome.Signature import PKCS1_v1_5

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred
from twisted.internet import reactor

#------------------------------------------------------------------------------

from bitdust_forks.Bismuth import connections  # @UnresolvedImport
from bitdust_forks.Bismuth import essentials  # @UnresolvedImport
from bitdust_forks.Bismuth import mining_heavy3  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.main import settings
from bitdust.main import config

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

_DataDirPath = None
_PoolHost = None
_PoolPort = None

#------------------------------------------------------------------------------

# TODO: find solution here, need to create some default address
alt_add = '1aae2cfe5d01acc8d7cbc90fcf8bb715ca24927504d0d8071c0979c7'

mdiff = 10
min_payout = 1
pool_fee = 0
alt_fee = 0
worker_time = 10

new_time = 0
new_diff = 0
new_hash = None

address = None
node_ip = None
node_port = None
# ledger_path_conf = None
key = None
public_key_hashed = None
private_key_readable = None
m_peer_file = None

mempool_db_path = None
shares_db_path = None
archive_db_path = None

#------------------------------------------------------------------------------


def init():
    global _DataDirPath
    global _PoolHost
    global _PoolPort
    _DataDirPath = settings.ServiceDir('bismuth_blockchain')
    _PoolHost = config.conf().getString('services/bismuth-pool/host', '127.0.0.1')
    _PoolPort = config.conf().getInt('services/bismuth-pool/tcp-port', 18525)
    node_host_port = '{}:{}'.format(
        config.conf().getString('services/bismuth-node/host', '127.0.0.1'),
        config.conf().getInt('services/bismuth-node/tcp-port', 15658),
    )
    starting_defer = Deferred()
    node_thread = threading.Thread(target=run, args=(starting_defer, _DataDirPath, node_host_port, _Debug))
    node_thread.start()
    if _Debug:
        lg.args(_DebugLevel, data_dir_path=_DataDirPath)
    return starting_defer


def shutdown():
    if _Debug:
        lg.dbg(_DebugLevel, '')
    return True


#------------------------------------------------------------------------------


def run(starting_defer, data_dir_path, node_address, verbose=False):
    global _DataDirPath
    global _PoolHost
    global _PoolPort
    # global ledger_path_conf
    global node_ip
    global node_port
    global address
    global key
    global public_key_hashed
    global private_key_readable
    global m_peer_file
    global mempool_db_path
    global shares_db_path
    global archive_db_path

    _DataDirPath = data_dir_path
    if not os.path.exists(data_dir_path):
        os.makedirs(data_dir_path)

    pool_key_path = os.path.join(data_dir_path, 'wallet_key.json')

    m_peer_file = os.path.join(data_dir_path, 'peers.json')

    mempool_db_path = os.path.join(data_dir_path, 'mempool.db')
    shares_db_path = os.path.join(data_dir_path, 'shares.db')
    archive_db_path = os.path.join(data_dir_path, 'archive.db')

    node_ip = node_address.split(':')[0]
    node_port = node_address.split(':')[1]

    if os.path.isfile(pool_key_path):
        if _Debug:
            lg.dbg(_DebugLevel, 'found %s key file' % pool_key_path)

    else:
        # generate key pair and an address
        key = RSA.generate(4096)
        private_key_readable = str(key.exportKey().decode('utf-8'))
        public_key_readable = str(key.publickey().exportKey().decode('utf-8'))
        address = hashlib.sha224(public_key_readable.encode('utf-8')).hexdigest()  # hashed public key
        essentials.keys_save(private_key_readable, public_key_readable, address, pool_key_path)
        if _Debug:
            lg.dbg(_DebugLevel, 'generated new %s key file' % pool_key_path)

    key, public_key_readable, private_key_readable, encrypted, unlocked, public_key_hashed, address, keyfile = essentials.keys_load(wallet_filename=pool_key_path)

    if _Debug:
        lg.args(_DebugLevel, pool_wallet_address=address)

    if not os.path.exists(shares_db_path):
        shares = sqlite3.connect(shares_db_path)
        shares.text_factory = str
        s = shares.cursor()
        execute(s, 'CREATE TABLE IF NOT EXISTS shares (address, shares, timestamp, paid, rate, name, workers, subname)')
        execute(s, 'CREATE TABLE IF NOT EXISTS nonces (nonce)')
        s.close()
        if _Debug:
            lg.dbg(_DebugLevel, 'created shares DB in %r' % shares_db_path)

    if not os.path.exists(archive_db_path):
        archive = sqlite3.connect(archive_db_path)
        archive.text_factory = str
        a = archive.cursor()
        execute(a, 'CREATE TABLE IF NOT EXISTS shares (address, shares, timestamp, paid, rate, name, workers, subname)')
        a.close()
        if _Debug:
            lg.dbg(_DebugLevel, 'created archive DB in %r' % archive_db_path)

    try:
        # background_thread = threading.Thread(target=paydb)
        # background_thread.daemon = True
        # background_thread.start()

        worker_thread = threading.Thread(target=worker, args=(worker_time, ))
        worker_thread.daemon = True
        worker_thread.start()
        time.sleep(10)

        attempts = 0
        server = None
        while True:
            if attempts > 30:
                raise Exception('not able to start mining pool server')
            try:
                server = ThreadedTCPServer((_PoolHost, _PoolPort), TCPHandler)
            except Exception as e:
                lg.warn(e)
                time.sleep(10)
                attempts += 1
                continue
            break
        server_ip, server_port = server.server_address
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        if _Debug:
            lg.dbg(_DebugLevel, 'started mining pool server at %s:%d' % (server_ip, server_port))

        # print('Server thread is ready')

        # reactor.callFromThread(paydb_single)  # @UndefinedVariable

        reactor.callFromThread(starting_defer.callback, True)  # @UndefinedVariable

        server_thread.join()

        if _Debug:
            lg.dbg(_DebugLevel, 'mining pool server finished')

        server.shutdown()
        server.server_close()

    except Exception as e:
        lg.exc()
        reactor.callFromThread(starting_defer.errback, e)  # @UndefinedVariable


def percentage(percent, whole):
    return int((percent*whole)/100)


def read_mempool():
    mempool_db = sqlite3.connect(mempool_db_path)
    try:
        mempool_db.text_factory = str
        mp = mempool_db.cursor()
        mp.execute('SELECT * FROM transactions ORDER BY amount DESC')
        present = mp.fetchall()
    except:
        traceback.print_exc()
        present = None
    try:
        mempool_db.close()
    except:
        traceback.print_exc()
    return present


def payout(payout_threshold, myfee, othfee):
    global node_ip
    global node_port

    # print('Minimum payout is {} Bismuth'.format(str(payout_threshold)))
    # print('Current pool fee is {} Percent'.format(str(myfee)))
    # did_payout = False

    shares = sqlite3.connect(shares_db_path)
    shares.text_factory = str
    s = shares.cursor()

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
    # print('Pool: block_threshold', block_threshold, 'shares_total', shares_total, 'address', address)

    #get eligible blocks
    # conn = sqlite3.connect(ledger_path_conf)
    # conn.text_factory = str
    # c = conn.cursor()
    # reward_list = []
    # for row in c.execute('SELECT * FROM transactions WHERE address = ? AND CAST(timestamp AS INTEGER) >= ? AND reward != 0', (address, ) + (block_threshold, )):
    #     reward_list.append(float(row[9]))
    # c.close()

    t = socks.socksocket()
    t.connect((node_ip, int(node_port)))  # connect to local node
    connections.send(t, 'listreward', 10)
    connections.send(t, address, 10)
    connections.send(t, str(block_threshold), 10)
    listreward_reply = connections.receive(t, 10)
    t.close()
    reward_list = []
    for row in listreward_reply:
        reward_list.append(float(row[9]))

    # print('reward_list', reward_list)

    super_total = sum(reward_list)
    # print('Pool: super_total', super_total, 'reward_list', reward_list)
    #get eligible blocks

    # so now we have sum of shares, total reward, block threshold

    # reduce total rewards by total fees percentage
    reward_total = '%.8f' % (((100 - (myfee + othfee))*super_total)/100)
    reward_total = float(reward_total)

    print('Pool: reward_total=%r' % reward_total)

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

        # print('reward_per_share1', reward_per_share, 'shares_threshold', shares_threshold)
        #get unique addresses
        addresses = []
        for row in s.execute('SELECT * FROM shares'):
            shares_address = row[0]

            if shares_address not in addresses:
                addresses.append(shares_address)
        # print('payout address', addresses)
        #get unique addresses

        # prepare payout address list with number of shares and new total shares
        payadd = []
        new_sum = 0
        for x in addresses:
            s.execute('SELECT sum(shares) FROM shares WHERE address = ? AND paid != 1', (x, ))
            shares_sum = s.fetchone()[0]

            if shares_sum == None:
                shares_sum = 0
            print(x, shares_sum, shares_threshold)
            if shares_sum > shares_threshold:
                payadd.append([x, shares_sum])
                new_sum = new_sum + shares_sum
        #prepare payout address list with number of shares and new total shares
        # print('payadd', payadd)

        # recalculate reward per share now we have removed those below payout threshold
        try:
            reward_per_share = reward_total/new_sum

        except:
            reward_per_share = 0

        # print('reward_per_share2', reward_per_share)

        paylist = []
        for p in payadd:
            payme = '%.8f' % (p[1]*reward_per_share)
            paylist.append([p[0], payme])

        if othfee > 0:
            paylist.append([alt_add, at])

        # print('paylist', paylist)
        payout_passed = 0
        for r in paylist:
            # print(r)
            recipient = r[0]
            claim = float(r[1])

            payout_passed = 1
            openfield = 'pool'
            keep = 0
            fee = 0
            # fee = float('%.8f' % float(0.01 + (float(len(openfield))/100000) + (keep)))  # 0.01 + openfield fee + keep fee
            #make payout

            timestamp = '%.2f' % time.time()
            transaction = (str(timestamp), str(address), str(recipient), '%.8f' % float(claim - fee), str(keep), str(openfield))  # this is signed
            # print transaction

            h = SHA.new(str(transaction).encode('utf-8'))
            signer = PKCS1_v1_5.new(key)
            signature = signer.sign(h)
            signature_enc = base64.b64encode(signature)
            # print('Encoded Signature: {}'.format(signature_enc.decode('utf-8')))

            verifier = PKCS1_v1_5.new(key)
            if verifier.verify(h, signature) == True:
                # print('The signature is valid, proceeding to send transaction')
                txid = signature_enc[:56]
                mytxid = txid.decode('utf-8')
                tx_submit = (str(timestamp), str(address), str(recipient), '%.8f' % float(claim - fee), str(signature_enc.decode('utf-8')), str(public_key_hashed.decode('utf-8')), str(keep), str(openfield))  #float kept for compatibility

                t = socks.socksocket()
                t.connect((node_ip, int(node_port)))  # connect to local node

                connections.send(t, 'mpinsert', 10)
                connections.send(t, [tx_submit], 10)
                reply = connections.receive(t, 10)
                t.close()
                # did_payout = True
                if _Debug:
                    lg.dbg(_DebugLevel, 'transaction {} sent with reply {}'.format(tx_submit, reply))
            else:
                # print('Pool: Invalid signature')
                reply = 'Invalid signature'

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
            archive = sqlite3.connect(archive_db_path)
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

    # if did_payout:
    #     reactor.callFromThread(paydb_single, delay=10)  # @UndefinedVariable


def commit(cursor):
    # secure commit for slow nodes
    passed = 0
    while passed == 0:
        try:
            cursor.commit()
            passed = 1
        except Exception as e:
            lg.exc()
            # print('Retrying database execute due to ' + str(e))
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
            lg.exc()
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
            lg.exc()
            time.sleep(0.1)
            # secure execute for slow nodes
    return cursor


bin_format_dict = dict((x, format(ord(x), '8b').replace(' ', '0')) for x in '0123456789abcdef')


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

    # disabled
    return True

    time.sleep(30)
    while True:
        # time.sleep(3601)
        # time.sleep(60 * 5)
        # v = float('%.2f' % time.time())
        # v1 = new_time
        # v2 = v - v1
        # if v2 < 100000:
        # print('Payout running...')
        payout(min_payout, pool_fee, alt_fee)
        # else:
        # print('Node over 1 mins out: %r ...payout delayed' % v2)
        time.sleep(60*5)


# def paydb_single(delay=0):
#     # print('Pool: paydb_single')
#     time.sleep(delay)
#     # reactor.callLater(delay, payout, min_payout, pool_fee, alt_fee)  # @UndefinedVariable
#     background_paydb_single_thread = threading.Thread(target=payout, args=(min_payout, pool_fee, alt_fee))
#     background_paydb_single_thread.daemon = True
#     background_paydb_single_thread.start()


def worker(s_time):
    global new_diff
    global new_hash
    global new_time
    global node_ip
    global node_port

    if _Debug:
        lg.dbg(_DebugLevel, 'about to connect to node at {}:{} from {}'.format(node_ip, node_port, threading.current_thread()))

    while True:

        time.sleep(s_time)

        try:

            n = socks.socksocket()
            n.connect((node_ip, int(node_port)))  # connect to local node

            connections.send(n, 'blocklast', 10)
            blocklast = connections.receive(n, 10)

            connections.send(n, 'diffget', 10)
            diff = connections.receive(n, 10)

            new_hash = blocklast[7]
            new_time = blocklast[1]
            new_diff = math.floor(diff[1])

            n.close()
            # print('Pool: difficulty={} blockhash={}'.format(str(new_diff), str(new_hash)))

        except Exception as e:
            traceback.print_exc()

        finally:
            try:
                n.close()
            except:
                traceback.print_exc()


class TCPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        global new_diff
        global node_ip
        global node_port
        global _DataDirPath

        block_submitted = False
        share_added = False

        key = RSA.importKey(private_key_readable)

        self.allow_reuse_address = True

        peer_ip, peer_port = self.request.getpeername()

        try:
            try:
                data = connections.receive(self.request, 10)
            except:
                data = ''
                lg.warn('failed reading data from %r: %r' % (self.client_address, self.request))

            # if _Debug:
            #     lg.args(_DebugLevel, data=data, peer_ip=peer_ip, peer_port=peer_port)
            # print('Pool: received {} from {}:{}'.format(data, peer_ip, peer_port))  # will add custom ports later

            if data == 'getwork':  # sends the miner the blockhash and mining diff for shares

                result = read_mempool()
                # m = socks.socksocket()
                # m.connect((node_ip, int(node_port)))  # connect to local node
                # connections.send(m, 'api_mempool', 10)
                # result = connections.receive(m, 10)
                # m.close()

                work_send = []
                work_send.append((len(result), new_hash, mdiff, address, mdiff))

                connections.send(self.request, work_send, 10)
                # print('Work package sent.... {}'.format(work_send))

            elif data == 'block':  # from miner to node

                # sock
                #s1 = socks.socksocket()
                #if tor_conf == 1:
                #    s1.setproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050)
                #s1.connect(("127.0.0.1", int(port)))  # connect to local node,
                # sock

                # receive nonce from miner
                miner_address = connections.receive(self.request, 10)
                # print('miner_address', miner_address)

                if not s_test(miner_address):
                    lg.err(_DebugLevel, 'bad miner address detected - changing to default')
                    miner_address = alt_add
                    #s1.close()

                else:

                    if _Debug:
                        lg.dbg(_DebugLevel, 'received a solution from miner {} ({})'.format(peer_ip, miner_address))

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

                    # print('Pool: Mined nonce details: {}'.format(block_nonce))
                    # print('Pool: Claimed hash: {}'.format(mine_hash))
                    # print('Pool: Claimed diff: {}'.format(sdiffs))

                    if not n_test(nonce):
                        lg.err('bad nonce format detected - closing connection')
                        self.close()
                    # print('Pool: Processing nonce.....')

                    diff = new_diff
                    db_block_hash = mine_hash

                    heavy3_path = os.path.join(_DataDirPath, 'heavy3a.bin')
                    mining_heavy3.mining_open(heavy3_path)
                    real_diff = mining_heavy3.diffme_heavy3(address, nonce, db_block_hash)
                    # mining_heavy3.mining_close()
                    """
                    mining_hash = bin_convert_orig(hashlib.sha224((address + nonce + db_block_hash).encode("utf-8")).hexdigest())
                    mining_condition = bin_convert_orig(db_block_hash)[0:diff]

                    if mining_condition in mining_hash:
                    """
                    # print('Pool: Solution has {} difficulty, current difficulty is {}'.format(real_diff, diff))
                    if real_diff >= int(diff):

                        # print('Pool: Difficulty requirement satisfied for mining')
                        # print('Pool: Sending block to nodes')

                        # cn = options.Get()
                        # cn.read()
                        # cport = cn.port
                        # try:
                        #     cnode_ip_conf = cn.node_ip_conf
                        # except:
                        #     cnode_ip_conf = cn.node_ip

                        #ctor_conf = cn.tor_conf
                        # cversion = cn.version

                        # print('Pool: Local node ip {} on port {}'.format(node_ip, node_port))

                        result = read_mempool()
                        # m = socks.socksocket()
                        # m.connect((node_ip, int(node_port)))  # connect to local node
                        # connections.send(m, 'api_mempool', 10)
                        # result = connections.receive(m, 10)
                        # print('I have got to receive mempool')
                        # m.close()

                        # include data
                        block_send = []
                        del block_send[:]  # empty
                        removal_signature = []
                        del removal_signature[:]  # empty

                        for dbdata in result:
                            transaction = (str(dbdata[0]), str(dbdata[1][:56]), str(dbdata[2][:56]), '%.8f' % float(dbdata[3]), str(dbdata[4]), str(dbdata[5]), str(dbdata[6]), str(dbdata[7]))  # create tuple
                            block_send.append(transaction)  # append tuple to list for each run
                            removal_signature.append(str(dbdata[4]))  # for removal after successful mining

                        # claim reward
                        transaction_reward = (str(block_timestamp), str(address[:56]), str(address[:56]), '%.8f' % float(0), '0', str(nonce))  # only this part is signed!
                        # print('transaction_reward', transaction_reward)

                        h = SHA.new(str(transaction_reward).encode('utf-8'))
                        signer = PKCS1_v1_5.new(key)
                        signature = signer.sign(h)
                        signature_enc = base64.b64encode(signature)

                        if signer.verify(h, signature) == True:
                            # print('Pool: Signature valid')

                            block_send.append((str(block_timestamp), str(address[:56]), str(address[:56]), '%.8f' % float(0), str(signature_enc.decode('utf-8')), str(public_key_hashed.decode('utf-8')), '0', str(nonce)))  # mining reward tx
                            # print('Pool: Block to send: {}'.format(block_send))

                            if not any(isinstance(el, list) for el in block_send):  # if it's not a list of lists (only the mining tx and no others)
                                new_list = []
                                new_list.append(block_send)
                                block_send = new_list  # make it a list of lists
                                # print(block_send)

                        peer_dict = {}
                        # peer_dict[node_ip] = node_port

                        # if True:
                        with open(m_peer_file) as f:
                            peer_dict = json.load(f)

                            if '127.0.0.1' in peer_dict:
                                peer_dict = {'127.0.0.1': peer_dict['127.0.0.1']}

                            for k, v in peer_dict.items():
                                peer_ip = k
                                # app_log.info(HOST)
                                peer_port = int(v)
                                # app_log.info(PORT)
                                # connect to all nodes
                                # print('Pool: Proceeding to submit mined block to {}:{}'.format(peer_ip, peer_port))
                                try:
                                    s = socks.socksocket()
                                    s.settimeout(0.3)
                                    #if ctor_conf == 1:
                                    #    s.setproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050)
                                    s.connect((peer_ip, int(peer_port)))  # connect to node in peerlist

                                    connections.send(s, 'block', 10)
                                    #connections.send(s, address, 10)
                                    connections.send(s, block_send, 10)
                                    block_submitted = True
                                    if _Debug:
                                        lg.dbg(_DebugLevel, 'block submitted to {}:{}'.format(peer_ip, peer_port))
                                except Exception as e:
                                    lg.exc()
                                    # print('Pool: Could not submit block to {}:{} because {}'.format(peer_ip, peer_port, e))
                                finally:
                                    s.close()

                    if diff < mdiff:
                        diff_shares = diff
                    else:
                        diff_shares = mdiff

                    shares = sqlite3.connect(shares_db_path)
                    shares.text_factory = str
                    s_cur = shares.cursor()

                    # protect against used share resubmission
                    execute_param(s_cur, ('SELECT nonce FROM nonces WHERE nonce = ?'), (nonce, ))

                    try:
                        result = s_cur.fetchone()[0]
                        lg.err('Pool: Miner trying to reuse a share, ignored')

                    except:
                        # protect against used share resubmission
                        """
                        mining_condition = bin_convert_orig(db_block_hash)[0:diff_shares] #floor set by pool
                        if mining_condition in mining_hash:
                        """
                        if real_diff >= diff_shares and address != miner_address:
                            # print('Pool: Difficulty requirement satisfied for saving shares')

                            execute_param(s, ('INSERT INTO nonces VALUES (?)'), (nonce, ))
                            commit(shares)

                            timestamp = '%.2f' % time.time()

                            s_cur.execute('INSERT INTO shares VALUES (?,?,?,?,?,?,?,?)', (str(miner_address), str(1), timestamp, '0', str(mrate), bname, str(wnum), wname))
                            shares.commit()
                            share_added = True

                            if _Debug:
                                lg.dbg(_DebugLevel, 'added new share for %r' % miner_address)

                        # else:
                        # print('Pool: Difficulty requirement not satisfied for anything')

                    s_cur.close()

            self.request.close()
        except Exception as e:
            lg.exc()
            # print('Pool: Error: {}'.format(e))

        # if block_submitted and share_added:
        # background_paydb_single_thread = threading.Thread(target=paydb_single)
        # background_paydb_single_thread.daemon = True
        # background_paydb_single_thread.start()
        # reactor.callFromThread(paydb_single, delay=1)  # @UndefinedVariable

        # if _Debug:
        #     lg.args(_DebugLevel, block_submitted=block_submitted, share_added=share_added)

        # else:
        # print('Pool: block_submitted=%r share_added=%r' % (block_submitted, share_added))

    # print('Pool: Starting up...')


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass
