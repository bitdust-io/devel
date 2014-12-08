# Сервис p2p_hookups()


## Описание
Сетевая служба `p2p_hookups()` является ключевым элементом в ПО BitPie.NET, 
она организует соединение пользователя с другими узлами в сети и 
поддерживает связь с активными контактами: хранителями, клиентами и др. 

При старте службы создается экземпляр автомата `p2p_connector()` и происходит
его инициализация.

Для каждого отдаленного узла, с которым поддерживается активный контакт,
будет создан экземпляр автомата `contact_status()`. 
Его задача отслеживать текущее состояние соединения с конкретным пользователем в сети BitPie.NET.

Сервис `p2p_hookups()` анализирует текущее состояние активных транспортных протоколов
и выстраивает их в порядке максимальной стабильности для текущего пользователя.
После этого, в identity файле пользователя происходит обновление его контактных данных, 
которые используются для непосредственной передачи входящих пакетов на его узел. 

Подробнее о работе транспортных протоколов вы можете прочитать в [этом](...) документе.

При отключении данного сервиса прекратится обновление identity файла пользователя, что
может привести рано или поздно к невозможности активного взаимодействия с другими узлами.


## Зависит от
* [gateway()](services/service_gateway.md)
* [identity_propagate()](services/service_identity_propagate.md)
* [tcp_transport()](services/service_tcp_transport.md)
* [udp_transport()](services/service_udp_transport.md)


## Влияет на
* [customer()](services/service_customer.md)


## Запуск автоматов
* [p2p_connector()](p2p/p2p_connector.md)
* [contact_status()](p2p/contact_status.md)


## Настройки сервиса
* services/p2p-hookups/enabled - включение/выключение сервиса `p2p_hookups()`


## Связанные файлы проекта
* [service/service_p2p_hookups.py](services/service_p2p_hookups.py)
* [p2p/p2p_connector.py](p2p/p2p_connector.py)
* [p2p/p2p_service.py](p2p/p2p_service.py)
* [p2p/contact_status.py](p2p/contact_status.py)
* [p2p/commands.py](p2p/commands.py)
* [p2p/ratings.py](p2p/ratings.py)



