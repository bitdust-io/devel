# Сервис entangled_dht()


## Описание
ПО BitDust использует программный код проекта [Entangled](http://entangled.sourceforge.net) для реализации
[распределенной хэш таблицы](http://en.wikipedia.org/wiki/Distributed_hash_table). С помощью DHT реализовано 
полностью распределенное хранение служебной информации, обеспечивающей работоспособность сети BitDust.

Все узлы в BitDust, у которых активен сервис `entangled_dht()`, будут поддерживать другие машины, 
храня пары `(ключ->значение)` созданные другими участниками сети, 
а так же иметь доступ к собственным служебным данным.

Более подробно об исользовании DHT в системе BitDust читайте в [этом](dht/dht.md) документе.


## Зависит от
* [udp_datagrams()](services/service_udp_datagrams.md)


## Влияет на
* [stun_server()](services/service_stun_server.md)
* [stun_client()](services/service_stun_client.md)
* [private_messages()](services/service_private_messages.md)


## Настройки сервиса
* services/entangled-dht/enabled - включение/выключение сервиса `entangled_dht()`


## Связанные файлы проекта
* [service_entangled_dht.py](services/service_entangled_dht.py)

