# Сервис network()


## Описание
Служба `network()` это базовый сервис, который влияет на все другие сетевые сервисы в клиентском ПО BitPie.NET. При её остановке, произойдет выключение всех активных на данный момент сервисов, будут закрыты все сессии и соединения с другими машинами и программа прекратит всякое взаимодействие с сетью.


## Влияет на
* [tcp_connections()](services/service_tcp_connections.md)
* [gateway()](services/service_gateway.md)
* [udp_datagrams()](services/service_udp_datagrams.md)


## Настройки сервиса
* services/network/enabled - включение/выключение сервиса network()


## Связанные файлы проекта
* [service_network.py](services/service_network)
* [p2p/network_connector.py](p2p/network_connector.py)


## Вызываемые автоматы
* [network_connector()](p2p/network_connector.md)
