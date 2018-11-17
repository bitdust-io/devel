import pytest
import time
import json
import pprint

from .utils import run_ssh_command_and_wait, run_ssh_curl_and_wait

#------------------------------------------------------------------------------

def health_check(node):
    count = 0
    while True:
        if count > 5:
            assert False, 'node %r is not healthy after 5 seconds' % node
        try:
            process_health = run_ssh_curl_and_wait(node, url='localhost:8180/process/health/v1')
            if process_health['status'] == 'OK':
                break
        except:
            time.sleep(1)
            count += 1
    print('node [%s] health check : OK' % node)


def create_identity(node, identity_name):
    count = 0
    while True:
        if count > 3:
            assert False, 'node %s failed to create identity after 3 retries' % node
        identity_create = run_ssh_curl_and_wait(
            node,
            url='localhost:8180/identity/create/v1',
            body=json.dumps({
                'username': identity_name,
            }),
            method='POST',
        )
        if identity_create['status'] == 'ERROR' and identity_create['errors'][0] == 'network connection error':
            count += 1
            print('\nRETRY %d to create identity' % count)
            continue
        if identity_create['status'] == 'OK':
            pprint.pprint(identity_create)
            break
    print('node [%s] create identity with name %s : OK' % (node, identity_name, ))

#------------------------------------------------------------------------------

def start_daemon(node):
    bitdust_daemon = run_ssh_command_and_wait(node, 'bitdust daemon')
    print(bitdust_daemon[0])
    assert (
        bitdust_daemon[0].strip().startswith('main BitDust process already started') or
        bitdust_daemon[0].strip().startswith('new BitDust process will be started in daemon mode')
    )
    print('start_daemon [%s] OK\n' % node)


def start_identity_server(node):
    print('\nNEW IDENTITY SERVER at %r\n' % node)
    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')[0].strip())
    # enable required services
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441, dht_seed_3:14441, dht_seed_4:14441"')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-server/host %s' % node)[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-server/enabled true')[0].strip())
    # start BitDust daemon
    start_daemon(node)
    health_check(node)
    print('start_identity_server [%s] OK\n' % node)


def start_stun_server(node):
    print('\nNEW STUN SERVER at %r\n' % node)
    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')[0].strip())
    # enable required services
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441, dht_seed_3:14441, dht_seed_4:14441"')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/ip-port-responder/enabled true')[0].strip())
    # start BitDust daemon
    start_daemon(node)
    health_check(node)
    print('start_stun_server [%s] OK\n' % node)


def start_dht_seed(node):
    print('\nNEW DHT SEED at %r\n' % node)
    # configure DHT seed nodes
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441, dht_seed_3:14441, dht_seed_4:14441"')[0].strip())
    # starting DHT node in daemon mode
    bitdust_dhtseed_daemon = run_ssh_command_and_wait(node, 'bitdust dhtseed daemon')
    print(bitdust_dhtseed_daemon[0])
    assert (
        bitdust_dhtseed_daemon[0].strip().startswith('starting Distributed Hash Table seed node and detach main BitDust process') or
        bitdust_dhtseed_daemon[0].strip().startswith('BitDust is running at the moment, need to stop the software first')
    )
    print('start_dht_seed [%s] OK\n' % node)


def start_supplier(node, identity_name):
    print('\nNEW SUPPLIER %r at %r\n' % (identity_name, node, ))
    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0].strip())
    # configure ID servers
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/known-servers "is:8084:6661"')[0].strip())
    # configure DHT seed nodes
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441, dht_seed_3:14441, dht_seed_4:14441"')[0].strip())
    # set desired Proxy router
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/preferred-routers "http://is:8084/proxy_server_1.xml http://is:8084/proxy_server_2.xml"')[0].strip())
    # start BitDust daemon and create new identity for supplier
    start_daemon(node)
    health_check(node)
    create_identity(node, identity_name)
    print('start_supplier [%s] OK\n' % node)


def start_proxy_server(node, identity_name):
    print('\nNEW PROXY SERVER %r at %r\n' % (identity_name, node, ))
    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')[0].strip())
    # configure ID servers
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/known-servers "is:8084:6661"')[0].strip())
    # configure DHT seed nodes
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441, dht_seed_3:14441, dht_seed_4:14441"')[0].strip())
    # enable ProxyServer service
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled true')[0].strip())
    # start BitDust daemon and create new identity for proxy server
    start_daemon(node)
    health_check(node)
    create_identity(node, identity_name)
    print('start_proxy_server [%s] OK\n' % node)

#------------------------------------------------------------------------------

def start_all_seeds():
    # TODO: keep up to date with docker-compose links
    seeds = {
        'identity-servers': [
            'is',
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
 
    print('\nStarting Seed nodes\n') 

    for idsrv in seeds['identity-servers']:
        start_identity_server(idsrv)

    for stunsrv in seeds['stun-servers']:
        start_stun_server(stunsrv)

    for dhtseed in seeds['dht-seeds']:
        start_dht_seed(dhtseed)
 
    print('\nAll Seed nodes ready\n')
 

#------------------------------------------------------------------------------

@pytest.yield_fixture(scope='session', autouse=True)
def global_wrapper():
    _begin = time.time()

    start_all_seeds()
    
    print('\nStarting all roles and execute tests')
 
    yield

    print('\nTest suite completed in %4.3d seconds\n' % (time.time() - _begin))


#------------------------------------------------------------------------------

@pytest.fixture(scope='session', autouse=True)
def init_proxy_server_1(global_wrapper):
    return start_proxy_server('proxy_server_1', 'proxy_server_1')

@pytest.fixture(scope='session', autouse=True)
def init_proxy_server_2(global_wrapper):
    return start_proxy_server('proxy_server_2', 'proxy_server_2')

@pytest.fixture(scope='session', autouse=True)
def init_supplier_1(global_wrapper):
    return start_supplier('supplier_1', 'supplier_1')

@pytest.fixture(scope='session', autouse=True)
def init_supplier_2(global_wrapper):
    return start_supplier('supplier_2', 'supplier_2')

@pytest.fixture(scope='session', autouse=True)
def init_supplier_3(global_wrapper):
    return start_supplier('supplier_3', 'supplier_3')

@pytest.fixture(scope='session', autouse=True)
def init_supplier_4(global_wrapper):
    return start_supplier('supplier_4', 'supplier_4')

@pytest.fixture(scope='session', autouse=True)
def init_supplier_5(global_wrapper):
    return start_supplier('supplier_5', 'supplier_5')

@pytest.fixture(scope='session', autouse=True)
def init_supplier_6(global_wrapper):
    return start_supplier('supplier_6', 'supplier_6')

@pytest.fixture(scope='session', autouse=True)
def init_supplier_7(global_wrapper):
    return start_supplier('supplier_7', 'supplier_7')

@pytest.fixture(scope='session', autouse=True)
def init_supplier_8(global_wrapper):
    return start_supplier('supplier_8', 'supplier_8')

