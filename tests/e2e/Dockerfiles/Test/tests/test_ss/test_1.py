import requests
import time


def test_ping_proxy_server_1_towards_proxy_server_2():
    time.sleep(10)
    id = 'proxy_server_2@is_8084'
    response = requests.get('http://proxy_server_1:8180/user/ping/v1?id=%s' % id)

    assert response.status_code == 200
    print(response.content)


def test_ping_supplier_1_towards_supplier_2():
    id = 'supplier_2@is_8084'
    response = requests.get('http://supplier_1:8180/user/ping/v1?id=%s' % id)

    assert response.status_code == 200
    print(response.content)

    time.sleep(1)

    response = requests.get('http://supplier_1:8180/user/ping/v1?id=%s' % id)

    assert response.status_code == 200
    print(response.content)
