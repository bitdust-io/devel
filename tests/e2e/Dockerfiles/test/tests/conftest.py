import pytest
import asyncio
import aiohttp


@pytest.yield_fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.yield_fixture(scope='session', autouse=True)
def timeout_before_tests_to_activate_bitdust(event_loop):
    nodes = [
        'supplier_1',
        'supplier_2',
        'customer_1',
        'customer_2',
        'customer_3',
        'proxy_server_1',
        'proxy_server_2',
        # 'stun_1',  #: this node doesn't have healthcheck
        # 'identity-server',  #: this node doesn't have healthcheck
    ]  #: keep up to date with docker-compose links

    print('Running health checks', flush=True)

    async def server_is_health(node):
        url = f'http://{node}:8180/process/health/v1'
        print('GET: ', url, flush=True)
        async with aiohttp.ClientSession() as session:
            for i in range(5):
                try:
                    response = await session.get(url)
                except Exception as e:
                    print(f'Exception {url} {e}. Try again in sec.', flush=True)
                    await asyncio.sleep(1)
                else:
                    print(f'Done: {response.url} ({response.status})', flush=True)
                    break

    tasks = [
        asyncio.ensure_future(server_is_health(node)) for node in nodes
    ]
    event_loop.run_until_complete(asyncio.wait(tasks))

    print('all containers are ready', flush=True)

    yield
    
    print('test suite finished', flush=True)


async def prepare_node(node, identity_name, event_loop):
    client = aiohttp.ClientSession(loop=event_loop)
    for i in range(5):
        response_identity = await client.post(f'http://{node}:8180/identity/create/v1', json={'username': identity_name})
        assert response_identity.status == 200

        response_json = await response_identity.json()

        if response_json['status'] == 'OK':
            print(f'{node}: identity created', flush=True)
            break
        else:
            assert response_json['errors'] == ['network connection error'], response_json

        print(f'{node}: network connection error, retry again in 1 sec', flush=True)
        await asyncio.sleep(1)
    else:
        assert False

    response = await client.get(f'http://{node}:8180/network/connected/v1?wait_timeout=1')
    response_json = await response.json()
    assert response_json['status'] == 'ERROR'

    for i in range(5):
        response = await client.get(f'http://{node}:8180/network/connected/v1?wait_timeout=1')
        response_json = await response.json()
        if response_json['status'] == 'OK':
            print(f"{node}: got status OK", flush=True)
            break

        print(f"{node}: sleep 1 sec", flush=True)
        await asyncio.sleep(1)
    else:
        assert False


@pytest.fixture(scope='session', autouse=True)
async def supplier_1_init(timeout_before_tests_to_activate_bitdust, event_loop):
    return await prepare_node('supplier_1', 'supplier_1', event_loop)


@pytest.fixture(scope='session', autouse=True)
async def supplier_2_init(timeout_before_tests_to_activate_bitdust, event_loop):
    return await prepare_node('supplier_2', 'supplier_2', event_loop)


@pytest.fixture(scope='session', autouse=True)
async def proxy_server_1_init(timeout_before_tests_to_activate_bitdust, event_loop):
    return await prepare_node('proxy_server_1', 'proxy_server_1', event_loop)


@pytest.fixture(scope='session', autouse=True)
async def proxy_server_2_init(timeout_before_tests_to_activate_bitdust, event_loop):
    return await prepare_node('proxy_server_2', 'proxy_server_2', event_loop)


@pytest.fixture(scope='session', autouse=True)
async def customer_1_init(timeout_before_tests_to_activate_bitdust, event_loop):
    return await prepare_node('customer_1', 'customer_1', event_loop)


@pytest.fixture(scope='session', autouse=True)
async def customer_2_init(timeout_before_tests_to_activate_bitdust, event_loop):
    return await prepare_node('customer_2', 'customer_2', event_loop)
