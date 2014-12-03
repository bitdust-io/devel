# Сервис tcp_connections()


## Описание
Служебный трафик в сети BitPie.NET может передавться по стандартному протоколу TCP.
Сетевая служба `tcp_connections()` позволяет включать/отключать использование TCP соединений во всех модулях ПО.
В настройках службы пользователь может установить номер порта для приема входящих соединений от других узлов.
Утилита `miniupnpc` используется для настройки UPnP устройств и автоматической настройки port-mapping.


## Зависит от
* [network()](services/service_network.md)


## Влияет на
* [tcp_transport()](services/service_tcp_transport.md)
* [identity_propagate()](services/service_identity_propagate.md)
* [identity_server()](services/service_identity_server.md)


## Настройки сервиса
* services/tcp-connections/enabled - включение/выключение сервиса `tcp_connections()`
* services/tcp-connections/tcp-port - установка номера порта для входящих TCP соединений


## Связанные файлы проекта
* [service_tcp_connections.py](services/service_tcp_connections.py)



