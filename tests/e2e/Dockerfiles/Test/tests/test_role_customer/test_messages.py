import os
import base64
import requests


def test_customer_1_send_message_to_customer_2():
    random_message = base64.b32encode(os.urandom(20)).encode()
    response = requests.post('http://customer_1:8180/message/send/v1', json={
        'id': 'messages$customer_2@is_8084',
        'data': {
            'random_message': random_message,
        },
    })
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()

    response = requests.get(
        'http://customer_2:8180/message/receive/test_consumer/v1'
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    assert response.json()['result'][0]['data']['random_message'] == random_message, response.json()
