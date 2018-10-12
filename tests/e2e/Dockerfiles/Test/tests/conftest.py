import pytest
import requests
import time
import asyncio
import aiohttp


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

    loop = asyncio.get_event_loop()
    tasks = [
        asyncio.ensure_future(server_is_health(l)) for l in links
    ]
    loop.run_until_complete(asyncio.wait(tasks))

    print('\nall done!\n')

    yield
    
    print('\ntests finished\n')


@pytest.fixture(scope='session', autouse=True)
def supplier_1_init(timeout_before_tests_to_activate_bitdust):
    #: TODO:
    #: implement helper to re-use it
    for i in range(5):
        response_identity = requests.post('http://supplier_1:8180/identity/create/v1', json={'username': 'supplier_1'})
        assert response_identity.status_code == 200

        if response_identity.json()['status'] == 'OK':
            break
        else:
            assert response_identity.json()['errors'] == ['network connection error'], response_identity.json()

        print('supplier_1_init: network connection error, retry again in 1 sec')
        time.sleep(1)
    else:
        assert False

    response = requests.get('http://supplier_1:8180/network/connected/v1?wait_timeout=1')
    assert response.json()['status'] == 'ERROR'

    for i in range(5):
        response = requests.get('http://supplier_1:8180/network/connected/v1?wait_timeout=1')
        if response.json()['status'] == 'OK':
            print("supplier_1_init: got status OK")
            break

        print("supplier_1_init: sleep 1 sec")
        time.sleep(1)
    else:
        assert False


@pytest.fixture(scope='session', autouse=True)
def supplier_2_init(timeout_before_tests_to_activate_bitdust):
    for i in range(5):
        response_identity = requests.post('http://supplier_2:8180/identity/create/v1', json={'username': 'supplier_2'})
        assert response_identity.status_code == 200

        if response_identity.json()['status'] == 'OK':
            break
        else:
            assert response_identity.json()['errors'] == ['network connection error'], response_identity.json()

        print('supplier_2_init: network connection error, retry again in 1 sec')
        time.sleep(1)
    else:
        assert False

    response = requests.get('http://supplier_2:8180/network/connected/v1?wait_timeout=1')
    assert response.json()['status'] == 'ERROR'

    for i in range(5):
        response = requests.get('http://supplier_2:8180/network/connected/v1?wait_timeout=1')
        if response.json()['status'] == 'OK':
            print("supplier_2_init: got status OK")
            break

        print("supplier_2_init: sleep 1 sec")
        time.sleep(1)
    else:
        assert False


@pytest.fixture(scope='session', autouse=True)
def proxy_server_1_init(timeout_before_tests_to_activate_bitdust):
    for i in range(5):
        response_identity = requests.post('http://proxy_server_1:8180/identity/create/v1', json={'username': 'proxy_server_1'})
        assert response_identity.status_code == 200

        if response_identity.json()['status'] == 'OK':
            break
        else:
            assert response_identity.json()['errors'] == ['network connection error'], response_identity.json()

        print('proxy_server_1_init: network connection error, retry again in 1 sec')
        time.sleep(1)
    else:
        assert False

    response = requests.get('http://proxy_server_1:8180/network/connected/v1?wait_timeout=1')
    assert response.json()['status'] == 'ERROR'

    for i in range(5):
        response = requests.get('http://proxy_server_1:8180/network/connected/v1?wait_timeout=1')
        if response.json()['status'] == 'OK':
            print("proxy_server_1_init: got status OK")
            break

        print("proxy_server_1_init: sleep 1 sec")
        time.sleep(1)
    else:
        assert False


@pytest.fixture(scope='session', autouse=True)
def proxy_server_2_init(timeout_before_tests_to_activate_bitdust):
    for i in range(5):
        response_identity = requests.post('http://proxy_server_2:8180/identity/create/v1', json={'username': 'proxy_server_2'})
        assert response_identity.status_code == 200

        if response_identity.json()['status'] == 'OK':
            break
        else:
            assert response_identity.json()['errors'] == ['network connection error'], response_identity.json()

        print('proxy_server_2_init: network connection error, retry again in 1 sec')
        time.sleep(1)
    else:
        assert False

    response = requests.get('http://proxy_server_2:8180/network/connected/v1?wait_timeout=1')
    assert response.json()['status'] == 'ERROR'

    for i in range(5):
        response = requests.get('http://proxy_server_2:8180/network/connected/v1?wait_timeout=1')
        if response.json()['status'] == 'OK':
            print("proxy_server_2_init: got status OK")
            break

        print("proxy_server_2_init: sleep 1 sec")
        time.sleep(1)
    else:
        assert False


@pytest.fixture(scope='session', autouse=True)
def customer_1_init(timeout_before_tests_to_activate_bitdust):
    for i in range(5):
        response_identity = requests.post('http://customer_1:8180/identity/create/v1', json={'username': 'customer_1'})
        assert response_identity.status_code == 200

        if response_identity.json()['status'] == 'OK':
            break
        else:
            assert response_identity.json()['errors'] == ['network connection error'], response_identity.json()

        print('customer_1_init: network connection error, retry again in 1 sec')
        time.sleep(1)
    else:
        assert False

    response = requests.get('http://customer_1:8180/network/connected/v1?wait_timeout=1')
    assert response.json()['status'] == 'ERROR'

    for i in range(5):
        response = requests.get('http://customer_1:8180/network/connected/v1?wait_timeout=1')
        if response.json()['status'] == 'OK':
            print("customer_1_init: got status OK")
            break

        print("customer_1_init: sleep 1 sec")
        time.sleep(1)
    else:
        assert False


@pytest.fixture(scope='session', autouse=True)
def customer_2_init(timeout_before_tests_to_activate_bitdust):
    for i in range(5):
        response_identity = requests.post('http://customer_2:8180/identity/create/v1', json={'username': 'customer_2'})
        assert response_identity.status_code == 200

        if response_identity.json()['status'] == 'OK':
            break
        else:
            assert response_identity.json()['errors'] == ['network connection error'], response_identity.json()

        print('customer_2_init: network connection error, retry again in 1 sec')
        time.sleep(1)
    else:
        assert False

    response = requests.get('http://customer_2:8180/network/connected/v1?wait_timeout=1')
    assert response.json()['status'] == 'ERROR'

    for i in range(5):
        response = requests.get('http://customer_2:8180/network/connected/v1?wait_timeout=1')
        if response.json()['status'] == 'OK':
            print("customer_2_init: got status OK")
            break

        print("customer_2_init: sleep 1 sec")
        time.sleep(1)
    else:
        assert False
