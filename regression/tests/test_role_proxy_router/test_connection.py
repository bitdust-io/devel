
import requests
from ..utils import tunnel_url


def test_ping_proxy_server_1_towards_proxy_server_2():
    response = requests.get(tunnel_url('proxy_server_1', 'user/ping/v1?id=proxy_server_2@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_proxy_server_2_towards_proxy_server_1():
    response = requests.get(tunnel_url('proxy_server_2', 'user/ping/v1?id=proxy_server_1@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_supplier_1_towards_supplier_2():
    response = requests.get(tunnel_url('supplier_1', 'user/ping/v1?id=supplier_2@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_supplier_2_towards_supplier_1():
    response = requests.get(tunnel_url('supplier_2', 'user/ping/v1?id=supplier_1@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_customer_1_towards_customer_2():
    response = requests.get(tunnel_url('customer_1', 'user/ping/v1?id=customer_2@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_customer_2_towards_customer_1():
    response = requests.get(tunnel_url('customer_2', 'user/ping/v1?id=customer_1@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_customer_1_towards_supplier_1():
    response = requests.get(tunnel_url('customer_1', 'user/ping/v1?id=supplier_1@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_customer_1_towards_supplier_2():
    response = requests.get(tunnel_url('customer_1', 'user/ping/v1?id=supplier_2@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_supplier_2_towards_customer_2():
    response = requests.get(tunnel_url('supplier_2', 'user/ping/v1?id=customer_2@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_supplier_2_towards_customer_1():
    response = requests.get(tunnel_url('supplier_2', 'user/ping/v1?id=customer_1@is_8084'))
    assert response.json()['status'] == 'OK', response.json()


def test_ping_supplier_1_towards_customer_2():
    response = requests.get(tunnel_url('supplier_1', 'user/ping/v1?id=customer_2@is_8084'))
    assert response.json()['status'] == 'OK', response.json()
