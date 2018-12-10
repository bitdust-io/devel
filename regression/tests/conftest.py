import pytest
import time
import requests

from .utils import run_ssh_command_and_wait, open_tunnel, close_all_tunnels, tunnel_url

#------------------------------------------------------------------------------

DHT_SEED_NODES = 'is:14441, stun_1:14441, stun_2:14441, dht_seed_1:14441, dht_seed_2:14441'
PROXY_ROUTERS = 'http://is:8084/proxy_server_1.xml http://is:8084/proxy_server_2.xml'

#------------------------------------------------------------------------------

def health_check(node):
    count = 0
    while True:
        if count > 5:
            assert False, 'node %r is not healthy after 5 seconds' % node
        try:
            response = requests.get(tunnel_url(node, 'process/health/v1'))
        except Exception as exc:
            print('[%s] retry %d   GET:process/health/v1  :  %s' % (node, count, exc, ))
            response = None
        if response and response.status_code == 200 and response.json()['status'] == 'OK':
            break
        time.sleep(1)
        count += 1
    print('health_check [%s] : OK\n' % node)


def create_identity(node, identity_name):
    count = 0
    while True:
        if count > 10:
            assert False, 'node %s failed to create identity after 10 retries' % node
        response = requests.post(
            url=tunnel_url(node, 'identity/create/v1'),
            json={'username': identity_name, },
        )
        if response.json()['status'] == 'OK':
            print('\n' + response.json()['result'][0]['xml'] + '\n')
            break
        if not response.status_code == 200 or (response.json()['status'] == 'ERROR' and response.json()['errors'][0] == 'network connection error'):
            count += 1
            print('[%s] retry %d   POST:identity/create/v1  username=%s     network connection error' % (node, count, identity_name, ))
            continue
        assert False, '[%s] bad response from /identity/create/v1' % node
    print('create_identity [%s] with name %s : OK\n' % (node, identity_name, ))


def connect_network(node):
    count = 0
    while True:
        if count > 5:
            assert False, 'node %s failed to connect to the network after 5 retries' % node
        response = requests.get(tunnel_url(node, 'network/connected/v1?wait_timeout=1'))
        if response.json()['status'] == 'OK':
            break
        count += 1
        print('[%s] retry %d   GET:network/connected/v1' % (node, count, ))
        time.sleep(1)
    print('connect_network [%s] : OK\n' % node)

#------------------------------------------------------------------------------

def start_daemon(node):
    bitdust_daemon = run_ssh_command_and_wait(node, 'bitdust daemon')
    print('\n' + bitdust_daemon[0].strip())
    assert (
        bitdust_daemon[0].strip().startswith('main BitDust process already started') or
        bitdust_daemon[0].strip().startswith('new BitDust process will be started in daemon mode')
    )
    print('start_daemon [%s] OK\n' % node)


def start_identity_server(node):
    print('\nNEW IDENTITY SERVER at [%s]\n' % node)
    # use short key to run tests faster
    print(run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')[0].strip())
    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')[0].strip())
    # enable DHT service
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "%s"' % DHT_SEED_NODES)[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')[0].strip())
    # configure and enable ID server
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-server/host %s' % node)[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-server/enabled true')[0].strip())
    # start BitDust daemon
    start_daemon(node)
    open_tunnel(node)
    health_check(node)
    print('\nSTARTED IDENTITY SERVER [%s]\n' % node)


def start_dht_seed(node):
    print('\nNEW DHT SEED at [%s]\n' % node)
    # use short key to run tests faster
    print(run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')[0].strip())
    # enable DHT service
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "%s"' % DHT_SEED_NODES)[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')[0].strip())
    # starting DHT node in daemon mode
    bitdust_dhtseed_daemon = run_ssh_command_and_wait(node, 'bitdust dhtseed daemon')
    print(bitdust_dhtseed_daemon[0])
    assert (
        bitdust_dhtseed_daemon[0].strip().startswith('starting Distributed Hash Table seed node and detach main BitDust process') or
        bitdust_dhtseed_daemon[0].strip().startswith('BitDust is running at the moment, need to stop the software first')
    )
    print('\nSTARTED DHT SEED [%s]\n' % node)


def start_stun_server(node):
    print('\nNEW STUN SERVER at [%s]\n' % node)
    # use short key to run tests faster
    print(run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')[0].strip())
    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')[0].strip())
    # enable DHT service
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "%s"' % DHT_SEED_NODES)[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')[0].strip())
    # enable Stun server
    print(run_ssh_command_and_wait(node, 'bitdust set services/ip-port-responder/enabled true')[0].strip())
    # start BitDust daemon
    open_tunnel(node)
    start_daemon(node)
    health_check(node)
    print('\nSTARTED STUN SERVER [%s]\n' % node)


def start_proxy_server(node, identity_name):
    print('\nNEW PROXY SERVER %r at [%s]\n' % (identity_name, node, ))
    # use short key to run tests faster
    print(run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')[0].strip())
    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')[0].strip())
    # configure ID servers
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/min-servers 1')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/max-servers 1')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/known-servers "is:8084:6661"')[0].strip())
    # configure DHT seed nodes
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "%s"' % DHT_SEED_NODES)[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')[0].strip())
    # enable ProxyServer service
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled true')[0].strip())
    # start BitDust daemon and create new identity for proxy server
    open_tunnel(node)
    start_daemon(node)
    health_check(node)
    create_identity(node, identity_name)
    connect_network(node)
    print('\nSTARTED PROXY SERVER [%s]\n' % node)


def start_supplier(node, identity_name):
    print('\nNEW SUPPLIER %r at [%s]\n' % (identity_name, node, ))
    # use short key to run tests faster
    print(run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')[0].strip())
    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')[0].strip())
    # configure ID servers
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/min-servers 1')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/max-servers 1')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/known-servers "is:8084:6661"')[0].strip())
    # configure DHT seed nodes
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "%s"' % DHT_SEED_NODES)[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')[0].strip())
    # set desired Proxy router
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/preferred-routers "%s"' % PROXY_ROUTERS)[0].strip())
    # enable supplier service
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled true')[0].strip())
    # start BitDust daemon and create new identity for supplier
    open_tunnel(node)
    start_daemon(node)
    health_check(node)
    create_identity(node, identity_name)
    connect_network(node)
    print('\nSTARTED SUPPLIER [%s]\n' % node)


def start_customer(node, identity_name):
    print('\nNEW CUSTOMER %r at [%s]\n' % (identity_name, node, ))
    # use short key to run tests faster
    print(run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')[0].strip())
    # disable unwanted services
    print(run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')[0].strip())
    # configure ID servers
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/min-servers 1')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/max-servers 1')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/known-servers "is:8084:6661"')[0].strip())
    # configure DHT seed nodes
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/known-nodes "%s"' % DHT_SEED_NODES)[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')[0].strip())
    # set desired Proxy router
    print(run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/preferred-routers "%s"' % PROXY_ROUTERS)[0].strip())
    # enable customer service and prepare tests
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled true')[0].strip())
    print(run_ssh_command_and_wait(node, 'bitdust set services/customer/suppliers-number 2')[0].strip())
    # create randomized file to test file upload/download
    print(run_ssh_command_and_wait(node, f'dd bs=1024 count=1 skip=0 if=/dev/urandom of=/{node}/file_{node}.txt'))
    # start BitDust daemon and create new identity for supplier
    open_tunnel(node)
    start_daemon(node)
    health_check(node)
    create_identity(node, identity_name)
    connect_network(node)
    print('\nSTARTED CUSTOMER [%s]\n' % node)

#------------------------------------------------------------------------------

def start_all_seeds():
    # TODO: keep up to date with docker-compose links
    seeds = {
        'dht-seeds': [
            'dht_seed_1',
            'dht_seed_2',
        ],
        'identity-servers': [
            'is',
        ],
        'stun-servers': [
            'stun_1',
            'stun_2',
        ],
        'proxy-servers': [
            'proxy_server_1',
            'proxy_server_2',
        ],
    }
 
    print('\nStarting Seed nodes\n') 

    for dhtseed in seeds['dht-seeds']:
        start_dht_seed(dhtseed)

    for idsrv in seeds['identity-servers']:
        start_identity_server(idsrv)

    for stunsrv in seeds['stun-servers']:
        start_stun_server(stunsrv)

    for proxysrv in seeds['proxy-servers']:
        start_proxy_server(proxysrv, proxysrv)

    print('\nAll Seed nodes ready\n')
 
 
def stop_all_nodes():
    # TODO: keep up to date with docker-compose links
    nodes = [
        'customer_1',
        'customer_2',
        'customer_3',
        'supplier_1',
        'supplier_2',
        'supplier_3',
        'supplier_4',
        'supplier_5',
        'supplier_6',
        'supplier_7',
        'supplier_8',
        'proxy_server_1',
        'proxy_server_2',
        'stun_1',
        'stun_2',
        'is',
        'dht_seed_1',
        'dht_seed_2',
    ]
    for node in nodes:
        print('Shutdown %s' % node)
        bitdust_stop = run_ssh_command_and_wait(node, 'bitdust stop')
        print(bitdust_stop[0].strip())
        run_ssh_command_and_wait(node, 'pkill -e sshd')
    print('All nodes stopped')

#------------------------------------------------------------------------------

@pytest.yield_fixture(scope='session', autouse=True)
def global_wrapper():
    _begin = time.time()

    start_all_seeds()
    
    print('\nStarting all roles and execute tests')
 
    yield

    close_all_tunnels()

    print('\nTest suite completed in %5.3f seconds\n' % (time.time() - _begin))

    # stop_all_nodes()

    print('\nFinished. All operations completed in %5.3f seconds\n' % (time.time() - _begin))

#------------------------------------------------------------------------------

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

#------------------------------------------------------------------------------

@pytest.fixture(scope='session', autouse=True)
def init_customer_1(global_wrapper):
    return start_customer('customer_1', 'customer_1')

@pytest.fixture(scope='session', autouse=True)
def init_customer_2(global_wrapper):
    return start_customer('customer_2', 'customer_2')

#------------------------------------------------------------------------------
