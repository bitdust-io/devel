# Сервис tcp_transport()


## Описание
Полезные данные между узлами в сети BitDust передаются через так называемые транспортные протоколы.
Сервис `tcp_transport()` реализует прямую передачу данных между машинами используя стандартный 
сетевой протокол TCP. 

В момент запуска службы будет создан экземпляр автомата `network_connector()` - 
его задача состоит в управлении жизненным циклом отдельно взятого сетевого транспорта.

Когда сервис `tcp_transport()` активен, на машине пользователя будет запущен TCP сервер,
который принимает входящие соединения и поддерживает открытыми TCP сессии с активными узлами.
Экземпляр автомата `tcp_connection()` создается для каждой вновь открытой сессии - он
отрабатывает запуск/остановку подключения и потока данных к/от удаленному узлу.

Номер порта для TCP сервера пользовватель может указать в настройках службы, 
по умолчанию используется порт `7771`.

Для корректной работы программы BitDust необходимо, 
что бы хотя бы один из сетевых транспортов был включен.
На данный момент поддерживаются два сетевых транспорта: 

+ `tcp_transport()`

+ `udp_transport()`

Соединение пользователя с удаленным узлом возможно только
если и обоих включен и корректно функционирует хотя бы один общий транспорт,
рекомендуется поддерживать активными все доступные сетевые транспорты.


## Зависит от
* [tcp_connections()](services/service_tcp_connections.md)
* [gateway()](services/service_gateway.md)


## Влияет на
* [p2p_hookups()](services/service_p2p_hookups.md)


## Запуск автоматов
* [network_transport()](transport/network_transport.md)
* [tcp_connection()](transport/tcp/tcp_connection.md)


## Настройки сервиса
* services/tcp-transport/enabled - включение/выключение сервиса `tcp_transport()`


## Связанные файлы проекта
* [services/service_tcp_transport.py](services/service_tcp_transport.py)
* [transport/network_transport.py](transport/network_transport.py)
* [transport/tcp/tcp_connection.py](transport/tcp/tcp_connection.py)
* [transport/tcp/tcp_interface.py](transport/tcp/tcp_interface.py)
* [transport/tcp/tcp_node.py](transport/tcp/tcp_node.py)
* [transport/tcp/tcp_stream.py](transport/tcp/tcp_stream.py)





