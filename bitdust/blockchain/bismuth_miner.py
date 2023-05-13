import os
import math
import threading
import time
import socks
import hashlib
import random
import traceback
import multiprocessing

from Cryptodome.PublicKey import RSA

from twisted.internet.defer import Deferred
from twisted.internet import reactor

from bitdust_forks.Bismuth import mining_heavy3
from bitdust_forks.Bismuth import connections
from bitdust_forks.Bismuth import essentials

_DataDirPath = None
_MoreCoins = None

miner_address = None
miner_name = 'miner01'

mining_pool_port = 8525
mining_pool_ip = '127.0.0.1'

mining_threads = 1
nonce_time = 10
max_diff = 150
hashcount = 20000


def init(data_dir_path, mining_pool_address, verbose=False):
    global _DataDirPath
    # global _MoreCoins
    _DataDirPath = data_dir_path
    # _MoreCoins = threading. .Value('i', 0)
    # starting_defer = Deferred()
    reactor.callLater(0, run, mining_pool_address)  # @UndefinedVariable
    # node_thread = threading.Thread(target=run, args=(
    #     _MiningIsOn,
    #     starting_defer,
    #     data_dir_path,
    #     mining_pool_address,
    #     verbose,
    # ))
    # node_thread.start()
    # reactor.callLater(30, mine_one_coin)
    # reactor.callLater(40, mine_one_coin)
    # reactor.callLater(50, mine_one_coin)
    # reactor.callLater(60, mine_one_coin)
    return True


def shutdown():
    pass


def miner_thread(data_dir_path, mining_pool_ip, mining_pool_port, miner_address):
    if not mining_heavy3.RND_LEN:
        mining_heavy3.mining_open(os.path.join(data_dir_path, 'heavy3a.bin'))

    mined_coins = 0
    while True:
        if mined_coins > 0:
            break

        print('Starting active mining, requesting work from the mining pool %s:%s' % (
            mining_pool_ip,
            int(mining_pool_port)
        ))

        try:
            s = socks.socksocket()
            s.connect((
                mining_pool_ip,
                int(mining_pool_port)
            ))
            connections.send(s, 'getwork', 10)
            work_pack = connections.receive(s, 10)
            db_block_hash = (work_pack[-1][0])
            diff = int((work_pack[-1][1]))
            pool_address = (work_pack[-1][2])
            netdiff = int((work_pack[-1][3]))
            s.close()

            diff_hex = math.floor((diff/8) - 1)
            mining_condition = db_block_hash[0:diff_hex]

            # instances = range(int(mining_threads))
            # thr = int(mining_threads)

            # for q in instances:
            #     p = multiprocessing.Process(target=miner, args=(_MoreCoins, _DataDirPath, str(q + 1), miner_address, paddress, db_block_hash, diff, mining_condition, netdiff, hq, thr, dh))
            #     p.daemon = True
            #     p.start()

            # mined_coins = 0
            # process_mmap = False
            h1 = 1
        
            # if not mining_heavy3.RND_LEN:
            #     mining_heavy3.mining_open(os.path.join(data_dir_path, 'heavy3a.bin'))
                # process_mmap = True
        
            print('Miner instance started', miner_address, pool_address, db_block_hash, diff, mining_condition, netdiff)
        
            try:
                tries = 0
                try_arr = [('%0x' % random.getrandbits(32)) for _ in range(nonce_time * hashcount)]
                address = pool_address
                # timeout = time.time() + nonce_time
        
                while True:
                    if mined_coins > 0:
                        break

                    try:
                        t1 = time.time()
                        tries = tries + 1
                        # generate the "address" of a random backyard that we will sample in this try
                        seed = ('%0x' % random.getrandbits(128 - 32))
                        # this part won't change, so concat once only
                        prefix = pool_address + seed
                        # This is where the actual hashing takes place
                        # possibles = [nonce for nonce in try_arr if mining_condition in (sha224((prefix + nonce + db_block_hash).encode("utf-8")).hexdigest())]
                        possibles = [nonce for nonce in try_arr if mining_condition in (mining_heavy3.anneal3(mining_heavy3.MMAP, int.from_bytes(hashlib.sha224((prefix + nonce + db_block_hash).encode('utf-8')).digest(), 'big')))]
                        # hash rate calculation
                        try:
                            t2 = time.time()
                            h1 = int(((nonce_time * hashcount) / (t2 - t1)) / 1000)
                        except Exception as e:
                            print(e)
                            h1 = 1
                        if possibles:
                            # print(possibles)
                            for nonce in possibles:
                                # add the seed back to get a full 128 bits nonce
                                nonce = seed + nonce
                                # xdiffx = diffme(str(address[:56]),str(nonce),db_block_hash)
                                xdiffx = mining_heavy3.diffme_heavy3(address, nonce, db_block_hash)
                                if xdiffx < diff:
                                    pass

                                else:
                                    print('Solved work with difficulty {} in {} cycles - YAY!'.format(xdiffx, tries))
                                    wname = '{}{}'.format(miner_name, 0)
                                    print('{} running at {} kh/s'.format(wname, str(h1)))
                                    block_send = []
                                    del block_send[:]  # empty
                                    block_timestamp = '%.2f' % time.time()
                                    block_send.append((block_timestamp, nonce, db_block_hash, netdiff, xdiffx, 0, miner_name, 1, str(1)))
                                    print('Sending solution: {}'.format(block_send))
                                    tries = 0
                                    # submit mined nonce to pool
                                    try:
                                        s1 = socks.socksocket()
                                        s1.connect((
                                            mining_pool_ip,
                                            int(mining_pool_port),
                                        ))  # connect to pool
                                        print('Miner: connected to pool, proceeding to submit solution miner_address=%s' % miner_address)
                                        connections.send(s1, 'block', 10)
                                        connections.send(s1, miner_address, 10)
                                        connections.send(s1, block_send, 10)
                                        time.sleep(0.2)
                                        s1.close()
                                        mined_coins += 1
                                        print('Miner: solution submitted to pool', mined_coins)
                                        break
        
                                    except Exception as e:
                                        print('Miner: Could not submit solution to pool')
                    except Exception as e:
                        print(e)
                        time.sleep(0.1)
                        raise
                # hq.put(str(h1) + '_' + str(mined_coins))
        
            except:
                traceback.print_exc()

        except Exception as e:
            print(e)
            print('Miner: Unable to connect to pool check your connection or IP settings.')
            time.sleep(1)

    mining_heavy3.mining_close()


# def mine_coins(more_coins=1):
#     global _MoreCoins
#     with _MoreCoins.get_lock():
#         _MoreCoins.value += more_coins


def run(mining_pool_address):
    global _DataDirPath
    global mining_pool_port
    global mining_pool_ip
    global miner_address

    mining_pool_ip = mining_pool_address.split(':')[0]
    mining_pool_port = mining_pool_address.split(':')[1]

    if not os.path.exists(_DataDirPath):
        os.makedirs(_DataDirPath)

    miner_key_path = os.path.join(_DataDirPath, 'miner_key.der')

    if os.path.isfile(miner_key_path):
        print('Found %s key file' % miner_key_path)

    else:
        # generate key pair and an address
        key = RSA.generate(4096)
        private_key_readable = str(key.exportKey().decode('utf-8'))
        public_key_readable = str(key.publickey().exportKey().decode('utf-8'))
        address = hashlib.sha224(public_key_readable.encode('utf-8')).hexdigest()  # hashed public key
        essentials.keys_save(private_key_readable, public_key_readable, address, miner_key_path)

    key, public_key_readable, private_key_readable, encrypted, unlocked, public_key_hashed, miner_address, keyfile = essentials.keys_load(
        wallet_filename=miner_key_path,
    )

    print('Miner address: {}'.format(miner_address))

    # mining_heavy3.mining_open(os.path.join(_DataDirPath, 'heavy3a.bin'))

    miner_th = threading.Thread(target=miner_thread, args=(_DataDirPath, mining_pool_ip, mining_pool_port, miner_address, ))
    miner_th.start()

    print('Miner thread starting')

    # reactor.callFromThread(starting_defer.callback, True)  # @UndefinedVariable

    # runit()

    # mining_heavy3.mining_close()

    # print('Miner thread finished')


bin_format_dict = dict((x, format(ord(x), '8b').replace(' ', '0')) for x in '0123456789abcdef')
def bin_convert(string):
    return ''.join(bin_format_dict[x] for x in string)


def bin_convert_orig(string):
    return ''.join(format(ord(x), '8b').replace(' ', '0') for x in string)


def diffme(pool_address, nonce, db_block_hash):
    diff = 60
    diff_result = 0
    mining_hash = bin_convert(hashlib.sha224((pool_address + nonce + db_block_hash).encode('utf-8')).hexdigest())
    mining_condition = bin_convert(db_block_hash)
    while mining_condition[:diff] in mining_hash:
        diff_result = diff
        diff += 1
    return diff_result


# def miner(is_on, data_dir_path, q, miner_address, pool_address, db_block_hash, diff, mining_condition, netdiff, hq, thr, dh):
#     mined_coins = 0
#     process_mmap = False
#     h1 = 1
#
#     if not mining_heavy3.RND_LEN:
#         mining_heavy3.mining_open(os.path.join(data_dir_path, 'heavy3a.bin'))
#         process_mmap = True
#
#     print('Miner instance started', q, miner_address, pool_address, db_block_hash, diff, mining_condition, netdiff, thr, dh)
#
#     try:
#         tries = 0
#         try_arr = [('%0x' % random.getrandbits(32)) for _ in range(nonce_time*hashcount)]
#         address = pool_address
#         timeout = time.time() + nonce_time
#
#         while True:
#             if not is_on.is_set():
#                 print('Mining is OFF, stop instance %s' % q)
#                 break
#
#             try:
#                 t1 = time.time()
#                 tries = tries + 1
#                 # generate the "address" of a random backyard that we will sample in this try
#                 seed = ('%0x' % random.getrandbits(128 - 32))
#                 # this part won't change, so concat once only
#                 prefix = pool_address + seed
#                 # This is where the actual hashing takes place
#                 # possibles = [nonce for nonce in try_arr if mining_condition in (sha224((prefix + nonce + db_block_hash).encode("utf-8")).hexdigest())]
#                 possibles = [nonce for nonce in try_arr if mining_condition in (mining_heavy3.anneal3(mining_heavy3.MMAP, int.from_bytes(hashlib.sha224((prefix + nonce + db_block_hash).encode('utf-8')).digest(), 'big')))]
#                 # hash rate calculation
#                 try:
#                     t2 = time.time()
#                     h1 = int(((nonce_time*hashcount)/(t2 - t1))/1000)
#                 except Exception as e:
#                     print(e)
#                     h1 = 1
#                 if possibles:
#                     # print(possibles)
#                     for nonce in possibles:
#                         if not is_on.is_set():
#                             print('Mining is OFF, stop trying')
#                             break
#                         # add the seed back to get a full 128 bits nonce
#                         nonce = seed + nonce
#                         # xdiffx = diffme(str(address[:56]),str(nonce),db_block_hash)
#                         xdiffx = mining_heavy3.diffme_heavy3(address, nonce, db_block_hash)
#                         if xdiffx < diff:
#                             pass
#                         else:
#                             print('Thread {} solved work with difficulty {} in {} cycles - YAY!'.format(q, xdiffx, tries))
#                             wname = '{}{}'.format(miner_name, str(q))
#                             print('{} running at {} kh/s'.format(wname, str(h1)))
#                             block_send = []
#                             del block_send[:]  # empty
#                             block_timestamp = '%.2f' % time.time()
#                             block_send.append((block_timestamp, nonce, db_block_hash, netdiff, xdiffx, dh, miner_name, thr, str(q)))
#                             print('Sending solution: {}'.format(block_send))
#                             tries = 0
#                             # submit mined nonce to pool
#                             try:
#                                 s1 = socks.socksocket()
#                                 s1.connect((
#                                     mining_pool_ip,
#                                     int(mining_pool_port),
#                                 ))  # connect to pool
#                                 print('Miner: connected to pool, proceeding to submit solution miner_address=%s' % miner_address)
#                                 connections.send(s1, 'block', 10)
#                                 connections.send(s1, miner_address, 10)
#                                 connections.send(s1, block_send, 10)
#                                 time.sleep(0.2)
#                                 s1.close()
#                                 mined_coins += 1
#                                 print('Miner: solution submitted to pool', mined_coins)
#                                 is_on.set()
#                                 break
#
#                             except Exception as e:
#                                 print('Miner: Could not submit solution to pool')
#             except Exception as e:
#                 print(e)
#                 time.sleep(0.1)
#                 raise
#         hq.put(str(h1) + '_' + str(mined_coins))
#
#     except:
#         traceback.print_exc()
#
#     finally:
#         if process_mmap:
#             mining_heavy3.mining_close()


# def runit():
#     global _DataDirPath
#     global _MoreCoins
#     totoally_mined_coins = 0
#     dh = 0
#     hq = multiprocessing.Queue()
#
#     while True:
#
#         print('Starting active mining, requesting work from the mining pool %s:%s' % (
#             mining_pool_ip,
#             int(mining_pool_port),
#         ))
#
#         try:
#             s = socks.socksocket()
#             s.connect((
#                 mining_pool_ip,
#                 int(mining_pool_port),
#             ))  # connect to pool
#             connections.send(s, 'getwork', 10)
#             work_pack = connections.receive(s, 10)
#             db_block_hash = (work_pack[-1][0])
#             diff = int((work_pack[-1][1]))
#             paddress = (work_pack[-1][2])
#             netdiff = int((work_pack[-1][3]))
#             s.close()
#
#             diff_hex = math.floor((diff/8) - 1)
#             mining_condition = db_block_hash[0:diff_hex]
#
#             instances = range(int(mining_threads))
#             thr = int(mining_threads)
#
#             for q in instances:
#                 p = multiprocessing.Process(target=miner, args=(_MoreCoins, _DataDirPath, str(q + 1), miner_address, paddress, db_block_hash, diff, mining_condition, netdiff, hq, thr, dh))
#                 p.daemon = True
#                 p.start()
#
#             print('Started {} miners and searching for solutions at difficulty {} and condition {}'.format(mining_threads, str(diff), str(mining_condition)))
#
#             time.sleep(nonce_time)
#
#             for q in instances:
#                 p.join()
#                 p.terminate()
#
#             raw_results = [hq.get() for q in instances]
#             results = [int(r.split('_')[0]) for r in raw_results]
#             totoally_mined_coins += sum([int(r.split('_')[1]) for r in raw_results])
#             dh = sum(results)
#             print('Current total hash rate is {} kh/s : in total {} coins mined '.format(str(dh), totoally_mined_coins))
#
#         except Exception as e:
#             print(e)
#             print('Miner: Unable to connect to pool check your connection or IP settings.')
#             time.sleep(1)
