
from ..utils import run_ssh_curl_and_wait


def test_customer_1_enough_suppliers():
    response = run_ssh_curl_and_wait(
        host='customer_1',
        url='localhost:8180/user/ping/v1?id=proxy_server_1@is_8084',
    )
    assert response['status'] == 'OK'
