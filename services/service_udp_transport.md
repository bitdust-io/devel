# Сервис udp_transport()


## Описание
Полезные данные между узлами в сети BitPie.NET передаются через так называемые сетевые транспортные протоколы.
Сервис `udp_transport()` реализует прямую передачу данных между машинами используя сетевой протокол UDP. 
В BitPie.NET реализован собственный метод потоковой передачи бинарных данных через UDP датаграммы.

По аналогии с протоколом TCP, создается отдельная сессия с каждым удаленным узлом. 
Общая пропускная способность баланисруется между всеми открытыми сессиями, 
в настройках сетевой службы `network()` пользователь имеет возможность настроить 
лимиты для входящего и исходящего канала (байт в секунду).

Этот сетевой транспорт позволяет соединять напрямую пользователей находящихся за NAT.
Поддерживается большинство из существующих типов конфигураций сетевого оборудования,
симметричный NAT на данный момент не поддерживается.

Для корректной работы программы BitPie.NET необходимо, 
что бы хотя бы один из сетевых транспортов был включен.
На данный момент поддерживаются два сетевых транспорта: 
+ `tcp_transport()`
+ `udp_transport()`

Соединение пользователя с удаленным узлом возможно только
если и обоих включен и корректно функционирует хотя бы один общий транспорт,
рекомендуется поддерживать активными все доступные сетевые транспорты.


## Зависит от
* [udp_datagrams()](services/service_udp_datagrams.md)
* [stun_client()](services/service_stun_client.md)
* [gateway()](services/service_gateway.md)


## Влияет на
* [p2p_hookups()](services/service_p2p_hookups.md)


## Настройки сервиса
* services/udp-transport/enabled - включение/выключение сервиса `udp_transport()`


## Связанные файлы проекта
* [service_udp_transport.py](services/service_udp_transport.py)
* [transport/udp/udp_node.py](transport/udp/udp_node.py)
* [transport/udp/udp_session.py](transport/udp/udp_session.py)
* [transport/udp/udp_connector.py](transport/udp/udp_connector.py)
* [transport/udp/udp_stream.py](transport/udp/udp_stream.py)
* [transport/udp/udp_file_queue.py](transport/udp/udp_file_queue.py)
* [transport/udp/udp_interface.py](transport/udp/udp_interface.py)


## Запуск автоматов
* [udp_node()](transport/udp/udp_node.md)
* [udp_session()](transport/udp/udp_session.md)
* [udp_connector()](transport/udp/udp_connector.md)
* [udp_stream()](transport/udp/udp_stream.md)

