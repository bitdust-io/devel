import time
import requests

from ..utils import tunnel_url


def test_customer_family_published_for_customer_1():
    count = 0
    while True:
        if count > 10:
            assert False, 'customer failed to hire enough suppliers after many attempts'
            return 
        response = requests.get(url=tunnel_url('customer_1', 'supplier/list/dht/v1'))
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        if not response.json()['result']:
            count += 1
            time.sleep(5)
            continue
        if len(response.json()['result']['suppliers']) < 2:
            count += 1
            time.sleep(5)
            continue
        assert response.json()['result']['customer_idurl'] == 'http://is:8084/customer_1.xml', response.json()['result']['customer_idurl']
        assert response.json()['result']['ecc_map'] == 'ecc/2x2', response.json()['result']['ecc_map']
        break
