# Сервис ip_port_responder()


## Описание
Сетевая служба `ip_port_responder()` позволяет другим участникам сети производить процедуру STUN, 
для определения собственного IP адреса и номра открытого UDP порта.

Она работает как простейший STUN сервер и отвечает на запрросы других узлов, у которых активна
служба [my_ip_port()](services/service_my_ip_port.md).
Обе эти службы работают в паре, но на разных машинах в сети.

Для поддержки других пользователей сети BitPie.NET настоятельно рекомендуется 
держать службу `ip_port_responder()` активной, она включена по умолчанию.


## Зависит от
* [udp_datagrams()](services/service_udp_datagrams.md)
* [entangled_dht()](services/service_entangled_dht.md)


## Запуск автоматов
* [stun_server()](stun/stun_server.md)


## Настройки сервиса
* services/ip-port-responder/enabled - включение/выключение сервиса `ip_port_responder()`


## Связанные файлы проекта
* [service/service_ip_port_responder.py](services/service_ip_port_responder.py)
* [stun/stun_server.py](stun/stun_server.py)



