"""
Wallet server benchmarking functions - ported from gui wallet, converted to use the native api class.
"""


import collections
import logging
import socket
import time

from bismuthclient import rpcconnections

DEFAULT_PORT = 5658


def convert_ip_port(ip, some_port):
    """
    Helper: Get ip and port, but extract port from ip if ip was as ip:port

    :param ip:
    :param some_port: default port
    :return: (ip, port)
    """
    if ':' in ip:
        ip, some_port = ip.split(':')
    return ip, some_port


def connectible(ipport):
    """
    Helper: return True if the ip:port can be connected to, without sending any command.
    """
    try:
        s = socket.socket()
        s.settimeout(3)
        ip, local_port = convert_ip_port(ipport, DEFAULT_PORT)
        s.connect((ip, int(local_port)))
        return True
    except Exception as e:
        print(str(e))
        return False


def time_measure(light_ip_list, app_log=None):
    """
    Measure answer time for the servers in light_ip list

    :param light_ip_list: a list of "ip:port" wallet servers
    :param app_log: an optional logger
    :return: A sorted light_ip list
    """
    if not app_log:
        app_log = logging

    port = DEFAULT_PORT
    result_collection = {ip: [0, 0] for ip in light_ip_list}

    rpcconnections.LTIMEOUT = 3

    for address in result_collection:
        try:
            ip, local_port = convert_ip_port(address, port)
            app_log.info("Attempting to benchmark {}:{}".format(ip, local_port))

            client = rpcconnections.Connection("{}:{}".format(ip, local_port))

            if local_port == DEFAULT_PORT: #doesn't work if a node uses non standard port, bench in else-path - will fail
                #start benchmark
                timer_start = time.time()
                result = client.command("statusget")
                timer_result = (time.time() - timer_start) * 5 #penalty to prio Wallet-Servers before nodes. local node should be so fast, to be still fastest, else it is better that a wallet-server is chosen!
                result_collection[address] = timer_result, result[8][7]
                app_log.warning("Result for {}:{}, a normal node, penalty-factor *5 (real result time/5): {}".format(ip, local_port, timer_result))
                #finish benchmark
            else:
                #start benchmark
                timer_start = time.time()
                result = client.command("statusget")
                result_ws = client.command("wstatusget")
                timer_result = time.time() - timer_start
                #finish benchmark and load balance if too many clients
                ws_clients = result_ws.get('clients')
                if ws_clients > 300:
                    timer_result = timer_result + ws_clients/1000
                    app_log.warning("Result for {}:{}, modified due to high client load: {}".format(ip, local_port, timer_result))
                elif ws_clients > 150:
                    timer_result = timer_result + ws_clients/10000
                    app_log.warning("Result for {}:{}, modified due to client load: {}".format(ip, local_port, timer_result))
                else:
                    app_log.warning("Result for {}:{}, low load - unmodified: {}".format(ip, local_port, timer_result))
                result_collection[address] = timer_result, result[8][7]

        except Exception as e:
            app_log.warning("Cannot benchmark {}:{}".format(ip, local_port))

    # sort IPs for measured Time
    bench_result = collections.OrderedDict(sorted((value[0], key) for (key, value) in result_collection.items()))
    light_ip = list(bench_result.values())

    max_height_temp = list(result_collection.values())
    max_height = max(list(zip(*max_height_temp))[1])
    for key, value in result_collection.items():
        if int(value[1]) < (max_height - 5):
            try:
                light_ip.remove(key)
                light_ip.append(key)
            except Exception as e:
                pass
    return light_ip
