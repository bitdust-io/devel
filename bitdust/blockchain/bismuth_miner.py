import os
import math
import threading
import time
import socks
import hashlib
import random
import traceback

from twisted.internet import reactor

from bitdust_forks.Bismuth import mining_heavy3
from bitdust_forks.Bismuth import connections

from bitdust.main import settings

from bitdust.blockchain import known_bismuth_nodes
from bitdust.blockchain import bismuth_wallet

from bitdust.services import driver

from bitdust.userid import my_id


_Debug = True
_DebugLevel = 10


_DataDirPath = None
_MinerWalletAddress = None
_MinerName = None

mining_threads = 1
nonce_time = 10
max_diff = 150
hashcount = 20000


def init():
    global _DataDirPath
    global _MinerName
    global _MinerWalletAddress
    _DataDirPath = settings.ServiceDir('bismuth_blockchain')
    _MinerWalletAddress = bismuth_wallet.my_wallet_address()
    _MinerName = my_id.getIDName()
    check_mine_own_coins()
    return True


def shutdown():
    pass


def check_mine_own_coins():
    cur_balance = bismuth_wallet.my_balance()
    print('My current balance is', cur_balance)
    if cur_balance == 'N/A':
        reactor.callLater(5, check_mine_own_coins)  # @UndefinedVariable
        return
    if cur_balance < 10:
        # mine_few_coins(needed_coins=(10 - bismuth_wallet.my_balance()))
        reactor.callLater(30, check_mine_own_coins)  # @UndefinedVariable


def mine_few_coins(needed_coins=1):
    reactor.callLater(0, run, needed_coins=needed_coins)  # @UndefinedVariable


def mine_non_empty_mempool():
    reactor.callLater(0, run, needed_coins=0)  # @UndefinedVariable


def get_random_mining_pool_host_port():
    if driver.is_enabled('service_bismuth_pool'):
        return '127.0.0.1', 18525
    one_item = random.choice(list(known_bismuth_nodes.mining_pools_by_host().items()))
    return one_item[0], one_item[1]


def run(needed_coins):
    global _MinerWalletAddress
    global _MinerName
    global _DataDirPath

    mining_pool_host, mining_pool_port = get_random_mining_pool_host_port()

    print('Miner address={} name={} next mining pool host:port is {}:{}'.format(
        _MinerWalletAddress, _MinerName, mining_pool_host, mining_pool_port,
    ))

    miner_th = threading.Thread(target=miner_thread, args=(
        needed_coins,
        mining_pool_host,
        mining_pool_port,
        _MinerWalletAddress,
        _MinerName,
        _DataDirPath,
    ))
    miner_th.start()
    print('Miner thread started')


def miner_thread(needed_coins, mining_pool_host, mining_pool_port, miner_address, miner_name, data_dir_path):
    if not mining_heavy3.RND_LEN:
        mining_heavy3.mining_open(os.path.join(data_dir_path, 'heavy3a.bin'))

    mined_coins = 0
    while True:
        if needed_coins and mined_coins >= needed_coins:
            print('Successfully mined %d coins, finishing' % mined_coins)
            break

        # print('Starting active mining, requesting work from the mining pool %s:%s' % (
        #     mining_pool_host,
        #     int(mining_pool_port)
        # ))

        try:
            s = socks.socksocket()
            s.connect((mining_pool_host, int(mining_pool_port)))
            connections.send(s, 'getwork', 10)
            work_pack = connections.receive(s, 10)
            mempool_size = (work_pack[-1][0])
            if not needed_coins and not mempool_size:
                print('Mempool is empty, no need to mine')
                time.sleep(30)
                continue
            db_block_hash = work_pack[-1][1]
            diff = int(work_pack[-1][2])
            pool_address = work_pack[-1][3]
            netdiff = int(work_pack[-1][4])
            s.close()

            diff_hex = math.floor((diff/8) - 1)
            mining_condition = db_block_hash[0:diff_hex]

            h1 = 1
        
            # print('Miner instance started', miner_address, pool_address, db_block_hash, diff, mining_condition, netdiff)
        
            try:
                tries = 0
                try_arr = [('%0x' % random.getrandbits(32)) for _ in range(nonce_time * hashcount)]
                address = pool_address
        
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
                            for nonce in possibles:
                                # add the seed back to get a full 128 bits nonce
                                nonce = seed + nonce
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
                                        s1.connect((mining_pool_host, int(mining_pool_port)))  # connect to pool
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
                        traceback.print_exc()
                        time.sleep(0.1)
                        raise
        
            except Exception as e:
                print(e)

        except Exception as e:
            print(e)
            print('Miner: Unable to connect to pool check your connection or IP settings.')
            time.sleep(1)

    mining_heavy3.mining_close()


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
