# Сервис stun_client()


## Описание
Сервис `stun_client()` предназначен для определения своего внешнего IP адреса и 
номер открытого UDP порта. 
Эти служебные данные используются для обеспечения возможности приема входящих UDP пакетов 
от других участников сети.
Для STUN процедуры, используются другие участники сети, у которых активен сетевой сервис 
[stun_server()](services/service_stun_server.md).


## Зависит от
* [entangled_dht()](services/service_entangled_dht.md)
* [udp_datagrams()](services/service_udp_datagrams.md)


## Влияет на
* [udp_transport()](services/service_udp_transport.md)


## Настройки сервиса
* services/stun-client/enabled - включение/выключение сервиса `stun_client()`


## Связанные файлы проекта
* [services/service_stun_client.py](services/service_stun_client.py)
* [stun/stun_client.py](stun/stun_client.py)


## Запуск автоматов
* [stun_client()](stun/stun_client.md)


