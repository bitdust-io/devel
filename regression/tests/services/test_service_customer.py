import time
import requests

from ..utils import tunnel_url


def test_customer_1_enough_suppliers():
    count = 0
    while True:
        if count > 10:
            assert False, 'customer failed to hire enough suppliers' 
        response = requests.get(url=tunnel_url('customer_1', 'supplier/list/v1'))
        if response.json()['status'] == 'OK' and response.json()['result'] == 2:
            break
        count += 1
        time.sleep(3)
