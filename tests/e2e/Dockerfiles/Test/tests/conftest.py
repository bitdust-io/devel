import pytest
import requests
import time
import asyncio
import aiohttp

loop = asyncio.get_event_loop()


@pytest.yield_fixture(scope='session', autouse=True)
def timeout_before_tests_to_activate_bitdust():
    links = [
        'supplier_1',
        'supplier_2',
        'customer_1',
        'customer_2',
        'proxy_server_1',
        'proxy_server_2',
        'stun_1',
        'identity-server',
    ]  #: keep up to date with docker-compose links

    print('\nRunning health checks\n')

    async def server_is_health(server):
        url = f'http://{server}:8180/process/health/v1'
        print('GET: ', url)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f'Done: {response.url} ({response.status})')

    tasks = [
        asyncio.ensure_future(server_is_health(l)) for l in links
    ]
    loop.run_until_complete(asyncio.wait(tasks))

    print('\nall containers are ready\n')

    yield
    
    print('\ntest suite finished\n')


def prepare_node(node, identity_name):
    for i in range(5):
        response_identity = requests.post(f'http://{node}:8180/identity/create/v1', json={'username': identity_name})
        assert response_identity.status_code == 200

        if response_identity.json()['status'] == 'OK':
            break
        else:
            assert response_identity.json()['errors'] == ['network connection error'], response_identity.json()

        print(f'{node}: network connection error, retry again in 1 sec')
        time.sleep(1)
    else:
        assert False

    response = requests.get(f'http://{node}:8180/network/connected/v1?wait_timeout=1')
    assert response.json()['status'] == 'ERROR'

    for i in range(5):
        response = requests.get(f'http://{node}:8180/network/connected/v1?wait_timeout=1')
        if response.json()['status'] == 'OK':
            print(f"{node}: got status OK")
            break

        print(f"{node}: sleep 1 sec")
        time.sleep(1)
    else:
        assert False


@pytest.fixture(scope='session', autouse=True)
def supplier_1_init(timeout_before_tests_to_activate_bitdust):
    prepare_node('supplier_1', 'supplier_1')


# @pytest.mark.asyncio
@pytest.fixture(scope='session', autouse=True)
def supplier_2_init(timeout_before_tests_to_activate_bitdust):
    prepare_node('supplier_2', 'supplier_2')


@pytest.fixture(scope='session', autouse=True)
def proxy_server_1_init(timeout_before_tests_to_activate_bitdust):
    prepare_node('proxy_server_1', 'proxy_server_1')


@pytest.fixture(scope='session', autouse=True)
def proxy_server_2_init(timeout_before_tests_to_activate_bitdust):
    prepare_node('proxy_server_2', 'proxy_server_2')


@pytest.fixture(scope='session', autouse=True)
def customer_1_init(timeout_before_tests_to_activate_bitdust):
    prepare_node('customer_1', 'customer_1')


@pytest.fixture(scope='session', autouse=True)
def customer_2_init(timeout_before_tests_to_activate_bitdust):
    prepare_node('customer_2', 'customer_2')
