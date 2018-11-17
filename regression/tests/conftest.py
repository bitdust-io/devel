import pytest
import subprocess
import time
import json
import os
import sys


#------------------------------------------------------------------------------

def run_ssh_command_and_wait(host, cmd):
    cmd = '''ssh -o StrictHostKeyChecking=no -p 22 root@%s "%s"''' % (host, cmd, )
    ssh_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    output, err = ssh_proc.communicate()
    if err:
        print('STDERR: %r' % err)
    # assert not err
    return output.decode(), err


def run_ssh_curl_and_wait(host, url, body=None, method='GET', *args, **kwargs):
    curl = 'curl -s -X %s ' % method
    if body:
        curl += "-d '%s' " % body
    curl += "'%s'" % url
    cmd = '''ssh -o StrictHostKeyChecking=no -p 22 root@%s %s''' % (host, curl, )
    print('%s' % curl)
    ssh_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    output, err = ssh_proc.communicate()
    print('CURL OUT: %s' % output.decode())
    print('CURL ERR: %r' % err)
    assert not err
    json_data = json.loads(output.decode())
    return json_data


#------------------------------------------------------------------------------

def bitdust_daemon(node):
    print('bitdust_daemon [%s]' % node)

    bitdust_daemon = run_ssh_command_and_wait(node, 'bitdust daemon')
    print(bitdust_daemon[0])
    assert (
        bitdust_daemon[0].strip().startswith('main BitDust process already started') or
        bitdust_daemon[0].strip().startswith('new BitDust process will be started in daemon mode')
    )

    print('bitdust_daemon [%s] OK\n' % node)


def bitdust_identity_server(node):
    print('bitdust_identity_server [%s]' % node)

    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')[0])

    # enable required services
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441, dht_seed_3:14441, dht_seed_4:14441"')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-server/host %s' % node)[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-server/enabled true')[0])

    bitdust_daemon(node)

    print('bitdust_identity_server [%s] OK\n' % node)


def bitdust_stun_server(node):
    print('bitdust_stun_server [%s]' % node)

    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')[0])

    # enable required services
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441, dht_seed_3:14441, dht_seed_4:14441"')[0])
    print(run_ssh_command_and_wait(node, 'bitdust set services/ip-port-responder/enabled true')[0])

    bitdust_daemon(node)

    print('bitdust_stun_server [%s] OK\n' % node)



def bitdust_dht_seed(node):
    print('bitdust_dht_seed [%s]' % node)

    # configure DHT seed nodes
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441, dht_seed_3:14441, dht_seed_4:14441"')[0])
    
    # TODO: must have special command like `bitdust dht-seed daemon`
    bitdust_daemon = run_ssh_command_and_wait(node, 'nohup /root/.bitdust/venv/bin/python /app/bitdust/dht/dht_service.py &')
    print(bitdust_daemon[0])

    print('bitdust_dht_seed [%s] OK\n' % node)



def start_all_seeds():
    # TODO: keep up to date with docker-compose links
    seeds = {
        'identity-servers': [
            'is',
            'isa',
            'isb',
        ],
        'stun-servers': [
            'stun_1',
            'stun_2',
        ],
        'dht-seeds': [
            'dht_seed_1',
            'dht_seed_2',
            'dht_seed_3',
            'dht_seed_4',
        ]
    }
 
    print('\Starting Seed nodes\n')
 
    for idsrv in seeds['identity-servers']:
        bitdust_identity_server(idsrv)

    for stunsrv in seeds['stun-servers']:
        bitdust_stun_server(stunsrv)

    for dhtseed in seeds['dht-seeds']:
        bitdust_dht_seed(dhtseed)
 
    print('\nAll Seed nodes ready\n')
 

#------------------------------------------------------------------------------

@pytest.yield_fixture(scope='session', autouse=True)
def global_wrapper():
    _begin = time.time()

    print('\nwaiting all nodes to be healthy')
    
    start_all_seeds()
    
    print('\nall nodes are ready')
 
    yield

    print('\ntest suite completed in %r sec\n' % (time.time() - _begin))


#------------------------------------------------------------------------------

@pytest.fixture(scope='session', autouse=True)
def identity_server_init(global_wrapper):
    bitdust_daemon('is', '')

@pytest.fixture(scope='session', autouse=True)
def stun_1_init(global_wrapper):
    bitdust_daemon('stun_1', '')

@pytest.fixture(scope='session', autouse=True)
def stun_2_init(global_wrapper):
    bitdust_daemon('stun_2', '')

@pytest.fixture(scope='session', autouse=True)
def dht_seed_1_init(global_wrapper):
    bitdust_daemon('dht_seed_1', '')

@pytest.fixture(scope='session', autouse=True)
def dht_seed_2_init(global_wrapper):
    bitdust_daemon('dht_seed_2', '')
