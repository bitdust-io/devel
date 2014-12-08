# Сервис stun_server()


## Описание
Сетевая служба `stun_server()` позволяет другим участникам сети производить процедуру STUN, 
для определения собственного IP адреса и номра открытого UDP порта.

Она работает как простейший STUN сервер и отвечает на запрросы других узлов, у которых активна
служба [stun_client()](services/service_stun_client.md).
Обе эти службы работают в паре, но на разных машинах в сети.

Для поддержки других пользователей сети BitPie.NET настоятельно рекомендуется 
держать службу `stun_server()` активной, она включена по умолчанию.


## Зависит от
* [udp_datagrams()](services/service_udp_datagrams.md)
* [entangled_dht()](services/service_entangled_dht.md)


## Запуск автоматов
* [stun_server()](stun/stun_server.md)


## Настройки сервиса
* services/stun-server/enabled - включение/выключение сервиса `stun_server()`


## Связанные файлы проекта
* [service_stun_server.py](services/service_stun_server.py)
* [stun/stun_server.py](stun/stun_server.py)



