import time
import requests

from ..utils import tunnel_url


def test_customer_1_enough_suppliers():
    count = 0
    while True:
        if count > 10:
            assert False, 'customer failed to hire enough suppliers after many attempts'
            return 
        response = requests.get(url=tunnel_url('customer_1', 'supplier/list/v1'))
        assert response.status_code == 200
        print('supplier/list/v1 response: %r' % response.json())
        assert response.json()['status'] == 'OK', response.json()
        if len(response.json()['result']) == 2:
            print('OK found 2 suppliers in response')
            assert True
            break
        print('still waiting 2 suppliers, %d attempts made so far' % count)
        count += 1
        time.sleep(5)
