"""
Peers handler module for Bismuth nodes
@EggPoolNet
"""

import json
import os
import random
import shutil
# import re
import sys
import threading
from time import time

import socks

import connections
import regnet
from essentials import most_common_dict, percentage_in

__version__ = '0.0.19'

_LogStatusMessages = False


class Peers:
    """The peers manager. A thread safe peers manager"""

    __slots__ = (
        'app_log',
        'config',
        'logstats',
        'node',
        'peersync_lock',
        'startup_time',
        'reset_time',
        'warning_list',
        'stats',
        'connection_pool',
        'peer_opinion_dict',
        'consensus_percentage',
        'consensus',
        'tried',
        'peer_dict',
        'peerfile',
        'suggested_peerfile',
        'banlist',
        'whitelist',
        'ban_threshold',
        'ip_to_mainnet',
        'peers',
        'accept_peers',
        'peerlist_updated',
    )

    def __init__(self, app_log, config=None, logstats=True, node=None):
        self.app_log = app_log
        self.config = config
        self.logstats = logstats
        self.peersync_lock = threading.Lock()
        self.startup_time = time()
        self.reset_time = self.startup_time
        self.warning_list = []
        self.stats = []
        self.peer_opinion_dict = {}
        self.consensus_percentage = 0
        self.consensus = None
        self.tried = {}
        self.peer_dict = {}
        self.ip_to_mainnet = {}
        self.connection_pool = []
        # We store them apart from the initial config, could diverge somehow later on.
        self.banlist = config.banlist
        self.whitelist = config.whitelist
        self.ban_threshold = config.ban_threshold
        self.accept_peers = config.accept_peers

        self.peerfile = 'peers.txt'
        self.suggested_peerfile = 'suggested_peers.txt'
        self.peerlist_updated = False

        self.node = node

        if self.is_testnet:  # overwrite for testnet
            self.peerfile = 'peers_test.txt'
            self.suggested_peerfile = 'suggested_peers_test.txt'

        if self.is_regnet:  # regnet won't use any peer, won't connect. Kept for compatibility
            self.peerfile = regnet.REGNET_PEERS
            self.suggested_peerfile = regnet.REGNET_SUGGESTED_PEERS

    @property
    def is_testnet(self):
        """Helper to check if testnet or not. Only one place to change variable names and test"""
        if self.config.regnet:
            # regnet takes over testnet
            return False
        if self.config.testnet:
            return True
        return 'testnet' in self.config.version

    @property
    def is_regnet(self):
        """Helper to check if regnet or not. Only one place to change variable names and test"""
        if self.config.regnet:
            # regnet takes over testnet
            return True
        return 'regnet' in self.config.version

    def dict_shuffle(self, dictinary):
        l = list(dictinary.items())
        random.shuffle(l)
        return dict(l)

    def status_dict(self):
        """Returns a status as a dict"""
        status = {'version': self.config.VERSION, 'stats': self.stats}
        return status

    def store_mainnet(self, ip, version):
        """Stores the mainnet version of a peer. Can't change unless reconnects"""
        self.ip_to_mainnet[ip] = version

    def forget_mainnet(self, ip):
        """Peers disconnected, forget his mainnet version"""
        self.ip_to_mainnet.pop(ip, None)

    def version_allowed(self, ip, version_allow):
        """
        If we don't know the version for this ip, allow.
        If we know, check
        """
        if ip not in self.ip_to_mainnet:
            return True
        return self.ip_to_mainnet[ip] in version_allow

    def peers_test(self, file, peerdict: dict, strict=True):
        """Validates then adds a peer to the peer list on disk"""
        # called by Sync, should not be an issue, but check if needs to be thread safe or not.
        # also called by self.client_loop, which is to be reworked
        # Egg: Needs to be thread safe.
        self.peerlist_updated = False
        try:
            with open(file, 'r') as peer_file:
                peers_pairs = json.load(peer_file)
            # print('Peers file test', file, len(peers_pairs), len(peerdict))
            # TODO: rework, because this takes too much time and freezes the status thread.
            # to be done in a dedicated thread, with one peer per xx seconds, not all at once, and added properties.
            for ip, port in dict(peerdict).items():
                # I do create a new dict copy above, because logs showed that the dict can change while iterating
                if self.node.IS_STOPPING:
                    # Early exit if stopping
                    return
                try:
                    if ip not in peers_pairs:
                        self.app_log.debug(f'Testing connectivity to: {ip}:{port}')
                        s = socks.socksocket()
                        try:
                            # connect timeout
                            s.settimeout(5)
                            if self.config.tor:
                                s.setproxy(socks.PROXY_TYPE_SOCKS5, '127.0.0.1', 9050)
                            if strict:
                                s.connect((ip, int(port)))
                                connections.send(s, 'getversion')
                                versiongot = connections.receive(s, timeout=1)
                                if versiongot == '*':
                                    raise ValueError('peer busy')
                                if versiongot not in self.config.version_allow:
                                    raise ValueError(f'cannot save {ip}, incompatible protocol version {versiongot} '
                                                     f'not in {self.config.version_allow}', )
                                self.app_log.debug(f'Inbound: Distant peer {ip}:{port} responding: {versiongot}')
                            else:
                                s.connect((ip, int(port)))
                        finally:
                            # properly end the connection in all cases
                            try:
                                s.close()
                            except:
                                pass
                        peers_pairs[ip] = port
                        self.app_log.debug(f'Inbound: Peer {ip}:{port} saved to peers')
                        self.peerlist_updated = True
                    else:
                        self.app_log.debug('Distant peer already in peers')

                except Exception as e:
                    # exception for a single peer
                    self.app_log.debug(f'Inbound: Distant peer not connectible ({e})')

            if self.peerlist_updated:
                self.app_log.debug(f'{file} peerlist updated ({len(peers_pairs)}) total')  # the whole dict is saved
                with open(f'{file}.tmp', 'w') as peer_file:
                    json.dump(peers_pairs, peer_file)
                shutil.move(f'{file}.tmp', file)
            else:
                self.app_log.debug(f'{file} peerlist update skipped, no changes')

        except Exception as e:
            # Exception for the file itself.
            self.app_log.warning(f"Error reading {file}: '{e}'")

    def append_client(self, client):
        """
        :param client: a string "ip:port"
        :return:
        """
        # TODO: thread safe?
        self.connection_pool.append(client)
        self.del_try(client)

    def remove_client(self, client):
        # TODO: thread safe?
        if client in self.connection_pool:
            try:
                self.app_log.debug(f'Will remove {client} from active pool')
                self.connection_pool.remove(client)
            except:
                raise

    def unban(self, peer_ip):
        """Removes the peer_ip from the warning list"""
        # TODO: Not thread safe atm. Should use a thread aware list or some lock
        if peer_ip in self.warning_list:
            self.warning_list.remove(peer_ip)
            self.app_log.warning(f'Removed a warning for {peer_ip}')

    def warning(self, sdef, ip, reason, count):
        """Adds a weighted warning to a peer."""
        # TODO: Not thread safe atm. Should use a thread aware list or some lock
        if ip not in self.whitelist:
            # TODO: use a dict instead of several occurrences in a list
            for x in range(count):
                self.warning_list.append(ip)
            self.app_log.warning(f'Added {count} warning(s) to {ip}: {reason} '
                                 f'({self.warning_list.count(ip)} / {self.ban_threshold})', )
            if self.warning_list.count(ip) >= self.ban_threshold:
                self.banlist.append(ip)
                self.app_log.warning(f'{ip} is banned: {reason}')
                return True
            else:
                return False

    def peers_get(self, peer_file=''):
        """Returns a peer_file from disk as a dict {ip:port}"""
        peer_dict = {}
        try:
            if not peer_file:
                peer_file = self.peerfile
            if not os.path.exists(peer_file):
                with open(peer_file, 'w') as fp:
                    # was "a": append would risk adding stuff to a file create in the mean time.
                    self.app_log.warning(f'Peer file created in {peer_file}')
                    fp.write('{}')  # empty dict. An empty string is not json valid.
            else:
                with open(peer_file, 'r') as fp:
                    peer_dict = json.load(fp)
        except Exception as e:
            self.app_log.warning(f'Error peers_get {e} reading {peer_file}')
        return peer_dict

    def peer_list_disk_format(self):
        """Returns a peerfile as is, simple text format or json, as it is on disk"""
        # TODO: caching and format to handle here
        with open(self.peerfile, 'r') as peer_list:
            peers = peer_list.read()
        return peers

    @property
    def consensus_most_common(self):
        """Consensus vote"""
        try:
            return most_common_dict(self.peer_opinion_dict)
        except:
            # no consensus yet
            return 0

    @property
    def consensus_max(self):
        try:
            return max(self.peer_opinion_dict.values())
        except:
            # no consensus yet
            return 0

    @property
    def consensus_size(self):
        """Number of nodes in consensus"""
        return len(self.peer_opinion_dict)

    def is_allowed(self, peer_ip, command=''):
        """Tells if the given peer is allowed for that command"""
        # TODO: more granularity here later
        # Always allow whitelisted ip to post as block
        if 'block' == command and self.is_whitelisted(peer_ip):
            return True
        # always allowed commands, only required and non cpu intensive.
        if command in ('portget', ):
            return True
        # only allow local host for "stop" and addpeers command
        if command in ('stop', 'addpeers'):
            return peer_ip == '127.0.0.1'
        return peer_ip in self.config.allowed or 'any' in self.config.allowed

    def is_whitelisted(self, peer_ip, command=''):
        # TODO: could be handled later on via "allowed" and rights.
        return peer_ip in self.whitelist or '127.0.0.1' == peer_ip

    def is_banned(self, peer_ip) -> bool:
        return peer_ip in self.banlist

    def dict_validate(self, json_dict: str) -> str:
        """temporary fix for broken peerlists"""
        if json_dict.count('}') > 1:
            result = json_dict.split('}')[0] + '}'
        else:
            result = json_dict
        return result

    def peersync(self, subdata: str) -> int:
        """Got a peers list from a peer, process. From worker().
        returns the number of added peers, -1 if it was locked or not accepting new peers
        subdata is a dict, { 'ip': 'port'}"""
        # early exit to reduce future levels
        if not self.config.accept_peers:
            return -1
        if self.peersync_lock.locked():
            # TODO: means we will lose those peers forever.
            # TODO: buffer, and keep track of recently tested peers.
            self.app_log.debug('Outbound: Peer sync occupied')
            return -1
        # Temp fix: subdata is typed str, but we have a dict sometimes.
        if type(subdata) == dict:
            # Enforce expected type.
            self.app_log.warning('Enforced expected type for peersync subdata')
            subdata = json.dumps(subdata)
        with self.peersync_lock:
            try:
                total_added = 0

                subdata = self.dict_validate(subdata)
                data_dict = json.loads(subdata)

                self.app_log.debug(f'Received {len(data_dict)} peers.')
                # Simplified the log, every peers then has a ok or ko status anyway.
                for ip, port in data_dict.items():
                    if ip not in self.peer_dict:
                        self.app_log.debug(f'Outbound: {ip}:{port} is a new peer, saving if connectible')
                        try:
                            s_purge = socks.socksocket()
                            s_purge.settimeout(5)
                            if self.config.tor:
                                s_purge.setproxy(socks.PROXY_TYPE_SOCKS5, '127.0.0.1', 9050)
                            s_purge.connect((ip, int(port)))  # save a new peer file with only active nodes
                            s_purge.close()
                            # This only adds to our local dict, does not force save.
                            if ip not in self.peer_dict:
                                total_added += 1
                                self.peer_dict[ip] = port
                                self.app_log.debug(f'Inbound: Peer {ip}:{port} saved to local peers')
                        except:
                            self.app_log.debug('Not connectible')
                    else:
                        self.app_log.debug(f'Outbound: {ip}:{port} is not a new peer')
            except Exception as e:
                self.app_log.warning(e)
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                raise
        return total_added

    def consensus_add(self, peer_ip, consensus_blockheight, sdef, last_block):
        # obviously too old blocks, we have half a day worth of validated blocks after them
        # no ban, they can (should) be syncing but they can't possibly be in consensus list.
        too_old = last_block - 720
        try:
            if peer_ip not in self.peer_opinion_dict:
                if consensus_blockheight < too_old:
                    self.app_log.warning(f'{peer_ip} received block too old ({consensus_blockheight}) for consensus')
                    return

            self.app_log.debug(f'Updating {peer_ip} in consensus')
            self.peer_opinion_dict[peer_ip] = consensus_blockheight

            self.consensus = most_common_dict(self.peer_opinion_dict)

            self.consensus_percentage = percentage_in(self.peer_opinion_dict[peer_ip], self.peer_opinion_dict.values())

            if int(consensus_blockheight) > int(self.consensus) + 30 and self.consensus_percentage > 50 and len(self.peer_opinion_dict) > 10:
                if self.warning(sdef, peer_ip, f'Consensus deviation too high, {peer_ip} banned', 10):
                    return

        except Exception as e:
            self.app_log.warning(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            raise

    def consensus_remove(self, peer_ip):
        if peer_ip in self.peer_opinion_dict:
            try:
                self.app_log.debug(f'Will remove {peer_ip} from consensus pool {self.peer_opinion_dict}')
                self.peer_opinion_dict.pop(peer_ip, None)
            except:
                raise

    def can_connect_to(self, host, port):
        """
        Tells if we can connect to this host
        :param host:
        :param port:
        :return:
        """
        if host in self.banlist:
            return False  # Banned IP
        host_port = f'{host}:{port}'
        if host_port in self.connection_pool:
            return False  # Already connected to
        try:
            tries, timeout = self.tried[host_port]
        except:
            tries, timeout = 0, 0  # unknown host for now, never tried.
        if timeout > time():
            return False  # We tried before, timeout is not expired.
        if self.is_whitelisted(host):
            return True  # whitelisted peers are always connectible, without variability condition.
        # variability test.
        c_class = '.'.join(host.split('.')[:-1]) + '.'
        matching = [ip_port for ip_port in self.connection_pool if c_class in ip_port]
        # If we already have 2 peers from that C ip class in our connection pool, ignore.
        if len(matching) >= 2:
            # Temp debug
            self.app_log.warning(f'Ignoring {host_port} since we already have 2 ips of that C Class in our pool.')
            return False
        # Else we can
        return True

    def add_try(self, host, port):
        """
        Add the host to the tried dict with matching timeout depending on its state.
        :param host:
        :param port:
        :return:
        """
        host_port = f'{host}:{port}'
        try:
            tries, timeout = self.tried[host_port]
        except:
            tries, timeout = 0, 0
        if tries <= 0:  # First time can be temp, retry again
            delay = 30
        elif tries == 1:  # second time, give it 5 minutes
            delay = 5*60
        elif tries == 2:  # third time, give it 15 minutes
            delay = 15*60
        else:  # 30 minutes before trying again
            delay = 30*60
        tries += 1
        if tries > 3:
            tries = 3
        self.tried[host_port] = (tries, time() + delay)
        # Temp
        self.app_log.debug(f'Set timeout {delay} try {tries} for {host_port}')

    def del_try(self, host, port=None):
        """
        Remove the peer from tried list. To be called when we successfully connected.
        :param host: an ip as a string, or an "ip:port" string
        :param port: optional, port as an int
        :return:
        """
        try:
            if port:
                host_port = f'{host}:{port}'
            else:
                host_port = host
            if host_port in self.tried:
                del self.tried[host_port]
        except Exception as e:
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

    def reset_tried(self):
        """
        Remove the older timeouts from the tried list.
        Keep the recent ones or we end up trying the first ones again and again
        """
        limit = time() + 12*60  # matches 2.5 tries :)
        remove = [client for client in self.tried if self.tried[client][1] > limit]
        for client in remove:
            del self.tried[client]

    def client_loop(self, node, this_target):
        """Manager loop called every 30 sec. Handles maintenance"""
        try:
            for key, value in dict(self.dict_shuffle(self.peer_dict)).items():
                # The dict() above is not an error or a cast,
                # it's to make a copy of the dict and avoid "dictionary changed size during iteration"
                host = key
                port = int(value)
                if host == self.node.host:
                    self.app_log.debug(f'Skip connecting to {host}:{port}')
                    continue

                if self.is_testnet:
                    port = 2829
                if threading.active_count()/3 < self.config.thread_limit and self.can_connect_to(host, port):
                    self.app_log.debug(f'Will attempt to connect to {host}:{port}')
                    self.add_try(host, port)
                    t = threading.Thread(target=this_target, args=(host, port, node), name=f'out_{host}_{port}')  # threaded connectivity to nodes here
                    self.app_log.debug(f'---Starting a client thread {threading.currentThread()} ---')
                    t.daemon = True
                    t.start()

            if len(self.peer_dict) < 6 and int(time() - self.startup_time) > 30:
                # join in random peers after x seconds
                self.app_log.debug('Not enough peers in consensus, joining in peers suggested by other nodes')
                self.peer_dict.update(self.peers_get(self.suggested_peerfile))

            if len(self.connection_pool) < self.config.nodes_ban_reset and int(time() - self.startup_time) > 15:
                # do not reset before 30 secs have passed
                self.app_log.debug(f'Only {len(self.connection_pool)} connections active, resetting banlist')
                del self.banlist[:]
                self.banlist.extend(self.config.banlist)  # reset to config version
                del self.warning_list[:]

            if len(self.connection_pool) < 10:
                self.app_log.debug(f'Only {len(self.connection_pool)} connections active, '
                                     f'resetting the connection history', )
                # TODO: only reset large timeouts, or we end up trying the sames over and over if we never get to 10.
                # self.
                self.reset_tried()

            if self.config.nodes_ban_reset <= len(self.banlist) and len(self.connection_pool) <= len(self.banlist) \
                    and (time() - self.reset_time) > 60 * 10:
                # do not reset too often. 10 minutes here
                self.app_log.debug(f'Less active connections ({len(self.connection_pool)}) '
                                     f'than banlist ({len(self.banlist)}), resetting banlist and tried list', )
                del self.banlist[:]
                self.banlist.extend(self.config.banlist)  # reset to config version
                del self.warning_list[:]
                self.reset_tried()
                self.reset_time = time()

            # if _LogStatusMessages:
            #     self.app_log.debug('Status: Testing peers')
            self.peer_dict.update(self.peers_get(self.peerfile))
            # self.peer_dict.update(self.peers_get(self.suggested_peerfile))

            # TODO: this is not OK. client_loop is called every 30 sec and should NOT contain any lengthy calls.
            self.peers_test(self.suggested_peerfile, self.peer_dict, strict=False)
            self.peers_test(self.peerfile, self.peer_dict, strict=True)

        except Exception as e:
            self.app_log.warning(f'Status: peers client loop skipped due to error: {e}')
            # raise
            """We do not want to raise here, since the rest of the calling method would be skipped also.
            It's ok to skip this part only
            The calling method has other important subsequent calls that have to be done.
            """

    def status_log(self):
        """Prints the peers part of the node status"""
        if not _LogStatusMessages:
            return
        if self.banlist:
            self.app_log.warning(f'Status: Banlist: {self.banlist}')
            self.app_log.warning(f'Status: Banlist Count : {len(self.banlist)}')
        if self.whitelist:
            self.app_log.warning(f'Status: Whitelist: {self.whitelist}')

        self.app_log.warning(f'Status: Known Peers: {len(self.peer_dict)}')
        self.app_log.debug(f'Status: Tried: {self.tried}')
        self.app_log.debug(f'Status: Tried Count: {len(self.tried)}')
        self.app_log.debug(f'Status: List of Outbound connections: {self.connection_pool}')
        self.app_log.warning(f'Status: Number of Outbound connections: {len(self.connection_pool)}')
        if self.consensus:  # once the consensus is filled
            self.app_log.warning(f'Status: Consensus height: {self.consensus} = {self.consensus_percentage}%')
            self.app_log.warning(f'Status: Last block opinion: {self.peer_opinion_dict}')
            self.app_log.warning(f'Status: Total number of nodes: {len(self.peer_opinion_dict)}')
