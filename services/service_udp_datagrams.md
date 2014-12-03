# Сервис udp_datagrams()


## Описание
Служебный трафик в сети BitPie.NET может передавться по UDP протоколу.
Сетевая служба `udp_datagrams()` позволяет включать/отключать использование UDP датаграм для общения с другими узлами.
В настройках службы пользователь может установить номер порта, который будет использован для приема UDP пакетов.


## Зависит от
* [network()](services/service_network.md)


## Влияет на
* [entangled_dht()](services/service_entangled_dht.md)
* [udp_transport()](services/service_udp_transport.md)
* [stun_server()](services/service_stun_server.md)
* [stun_client()](services/service_stun_client.md)


## Настройки сервиса
* services/udp-datagrams/enabled - включение/выключение сервиса `udp_datagrams()`
* services/udp-datagrams/udp-port - установка номера порта для входящих UDP соединений


## Связанные файлы проекта
* [service_udp_datagrams.py](services/service_udp_datagrams.py)



## Запуск автоматов
