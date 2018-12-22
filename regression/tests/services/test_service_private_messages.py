import os
import base64
from threading import Timer
import requests

from ..utils import tunnel_url


def send_message(random_message):
    response = requests.post(
        url=tunnel_url('customer_1', 'message/send/v1'),
        json={
            'id': 'master$customer_2@is_8084',
            'data': {
                'random_message': random_message,
            },
        }
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()


def test_customer_1_send_message_to_customer_2():
    random_message = base64.b32encode(os.urandom(20)).decode()

    #: send message in different thread to get one in blocked `receive` call
    t = Timer(2.0, send_message, [random_message, ])
    t.start()

    response = requests.get(
        url=tunnel_url('customer_2', 'message/receive/test_consumer/v1'),
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result'][0]['data']['random_message'] == random_message, response.json()
