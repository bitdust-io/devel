import pdb
import traceback
import threading

import sys
import random
import thread
import json
import time
import string
import socket
import select


import get_db
import get_version
import get_nodes
import coin_count
import register
import rsa
import get_difficulty
import check_coin
import send_coin
import miner

from namespace import ns, new
from zlog import out


class zCoin:
    def __init__(self, name_space):
        if ns(name_space) is None:
            new(name_space)
        self.name_space = name_space
        self.stopped = False
        self.sock = None
        self.cmds = {
            "get_db":get_db.get_db,
            "get_nodes":get_nodes.get_nodes,
            "get_version":get_version.get_version,
            "coin_count":coin_count.coin_count,
            "register":register.register,
            "get_difficulty":get_difficulty.get_difficulty,
            "check_coin":check_coin.check_coin,
            "send_coin":send_coin.send_coin,
            "get_nodes_count":get_nodes.count,
            }

    def firstrun(self, ip=None):
        out("Generating address...")
        pub, priv = rsa.newkeys(1024)
        address = "Z"+''.join([random.choice(string.uppercase+string.lowercase+string.digits) for _ in range(50)])
        out("Your address is: "+address)
        out("Getting nodes...")
        get_nodes.send(self.name_space, True)
        check = ns(self.name_space).nodes.find("nodes", "all")
        if not check:
            out("It looks like you are the first node on this network.")
            if ip is None:
                ip = raw_input("What is your IP address? ")
            ns(self.name_space).nodes.insert("nodes", {
                "public":str(pub),
                "address":address,
                "ip":ip,
                "relay":ns(self.name_space).relay,
                "port":ns(self.name_space).port,
            })
            ns(self.name_space).nodes.save()
            ns(self.name_space).db.insert("difficulty", {
                "difficulty": ns(self.name_space).base_difficulty,
            })
            ns(self.name_space).db.save()
        ns(self.name_space).wallet.insert("data", {
            "public":str(pub),
            "address":address,
            "private":str(priv),
        })
        ns(self.name_space).wallet.save()
        out("Registering...")
        register.send(self.name_space)
        out("Getting coins db...")
        get_db.send(self.name_space)
        out("Done!")

    def stop(self):
        out("zCoin[%s] stopping now" % self.name_space)
        self.stopped = True
            
    def relay(self):
        get_nodes.send(self.name_space)
        register.send(self.name_space)
        get_db.send(self.name_space)
        self.sock = socket.socket()
        # self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((ns(self.name_space).host, ns(self.name_space).port))
        self.sock.listen(5)
        while True:
            if self.stopped:
                break
            obj, conn = self.sock.accept()
            thread.start_new_thread(self.handle, (obj, conn[0]))
        out("zCoin[%s] relay thread stopped" % self.name_space)

    def relay_non_bocking(self):        
        out("zCoin[%s] relay thread started" % self.name_space)
        get_nodes.send(self.name_space)
        register.send(self.name_space)
        get_db.send(self.name_space)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((ns(self.name_space).host, ns(self.name_space).port))
        self.sock.listen(5)
        read_list = [self.sock,]
        while True:
            if self.stopped:
                break
            # out('zCoin[%s] select %s' % (self.name_space, self.sock))
            try:
                readable, writable, errored = select.select(read_list, [], [], 0.5)
            except:
                traceback.print_exc()
                self.stopped = True
                break
            if self.stopped:
                break
            # out('zCoin[%s] relay loop, select readable=%s' % (self.name_space, readable))
            if not readable:
                try:
                    time.sleep(0.05)
                except:
                    traceback.print_exc()
                    self.stopped = True
                    break
                continue
            for s in readable:
                if s is self.sock:
                    obj, conn = self.sock.accept()
                    thread.start_new_thread(self.handle, (obj, conn[0]))
        out("zCoin[%s] relay thread stopped" % self.name_space)

    def handle(self, obj, ip):
        data = obj.recv(10240)
        if data:
            try:
                data = json.loads(data)
            except:
                obj.close()
                return
            else:
                if "cmd" in data:
                    if data['cmd'] in self.cmds:
                        data['ip'] = ip
                        out('%s: %s' % (data['cmd'].upper(), data))
                        self.cmds[data['cmd']](obj, data, self.name_space)
                        obj.close()

    def normal(self):
        out("zCoin[%s] normal thread started" % self.name_space)
        if not ns(self.name_space).relay:
            get_db.send(self.name_space)
            register.send(self.name_space)
        while True:
            if self.stopped:
                break
            coin_count.send(self.name_space)
            get_nodes.count_send(self.name_space)
            # out('zCoin[%s] normal thread loop' % self.name_space)
            for _ in xrange(600):
                time.sleep(0.05)
                if self.stopped:
                    break
        out("zCoin[%s] normal thread stopped" % self.name_space)
    
    def mine_one_coin(self, json_data):
        return miner.mine(self.name_space, json_data)
            

def run(name_space, ip=None):
    zc = zCoin(name_space)
    check = ns(name_space).nodes.find("nodes", "all")
    if not check:
        zc.firstrun(ip)
    if ns(name_space).relay:
        out("zCoin[%s] started as a relay node on port %d." % (
            name_space, ns(name_space).port))
        normal = threading.Thread(target=zc.normal)
        normal.start()
        relay = threading.Thread(target=zc.relay_non_bocking)
        relay.start()
    else:
        out("zCoin[%s] started as a normal node." % name_space)
        zc.normal()
    return zc


def run_with_twisted_reactor(name_space, ip=None):
    from twisted.internet import reactor
    zc = zCoin(name_space)
    check = ns(name_space).nodes.find("nodes", "all")
    if not check:
        zc.firstrun(ip)
    if ns(name_space).relay:
        out("zCoin[%s] started as a relay node on port %d." % (
            name_space, ns(name_space).port))
        reactor.callInThread(zc.normal)
        reactor.callInThread(zc.relay_non_bocking)
    else:
        out("zCoin[%s] started as a normal node." % name_space)
        reactor.callInThread(zc.normal)
    reactor.addSystemEventTrigger('before', 'shutdown', zc.stop)
    return zc

    

if __name__ == "__main__":
    if True:
        zc = run('current')
        while True:
            try:
                time.sleep(1)
            except:
                zc.stop()
                sys.exit()
    else:
        from twisted.internet import reactor
        zc = run_with_twisted_reactor('current')
        reactor.run()
