# Сервис stun_client()


## Описание
Сервис `stun_client()` предназначен для определения внешнего IP адреса и 
номер открытого UDP порта машины пользователя. 

Эти служебные данные используются для обеспечения возможности приема входящих TCP соединений и 
UDP датаграмм от других узлов сети BitPie.NET.

Для STUN процедуры, используются другие машины сети, у которых активен сетевой сервис 
`stun_server()`.

При отключении данной службы станет неактивным сетевой транспорт UDP.
Он использует автомат `stun_client()`, экземпляр которого создается при запуске службы,
для подготовки процедуры прохода через NAT.


## Зависит от
* [entangled_dht()](services/service_entangled_dht.md)
* [udp_datagrams()](services/service_udp_datagrams.md)


## Влияет на
* [udp_transport()](services/service_udp_transport.md)


## Запуск автоматов
* [stun_client()](stun/stun_client.md)


## Настройки сервиса
* services/stun-client/enabled - включение/выключение сервиса `stun_client()`


## Связанные файлы проекта
* [services/service_stun_client.py](services/service_stun_client.py)
* [stun/stun_client.py](stun/stun_client.py)




