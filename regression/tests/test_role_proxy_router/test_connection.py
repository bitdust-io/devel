import requests
import time


# def test_ping_proxy_server_1_towards_proxy_server_2():
#     response = requests.get(
#         'http://proxy_server_1:8180/user/ping/v1?id=proxy_server_2@is_8084',
#         # timeout=(2, 10, ),
#     )
#     assert response.status_code == 200
# 
# 
# def test_ping_proxy_server_2_towards_proxy_server_1():
#     response = requests.get(
#         'http://proxy_server_1:8180/user/ping/v1?id=proxy_server_2@is_8084',
#         # timeout=(2, 10, ),
#     )
#     assert response.status_code == 200
# 
# 
# def test_ping_supplier_1_towards_supplier_2():
#     response = requests.get(
#         'http://supplier_1:8180/user/ping/v1?id=supplier_2@is_8084',
#         # timeout=(2, 10, ),
#     )
#     assert response.status_code == 200
# 
# 
# def test_ping_supplier_2_towards_supplier_1():
#     response = requests.get(
#         'http://supplier_2:8180/user/ping/v1?id=supplier_1@is_8084',
#         # timeout=(2, 10, ),
#     )
#     assert response.status_code == 200
