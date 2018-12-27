import time
import requests

from ..utils import tunnel_url


def test_hire_suppliers_by_customer_1():
    count = 0
    while True:
        if count > 10:
            assert False, 'customer failed to hire enough suppliers after many attempts'
            return 
        response = requests.get(url=tunnel_url('customer_1', 'supplier/list/v1'))
        assert response.status_code == 200
        assert response.json()['status'] == 'OK', response.json()
        if len(response.json()['result']) == 2:
            assert True
            break
        count += 1
        time.sleep(5)
