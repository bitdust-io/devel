# Сервис entangled_dht()


## Описание
ПО BitPie.NET использует программный код проекта [Entangled](http://entangled.sourceforge.net) для реализации
[распределенной хэш таблицы](http://en.wikipedia.org/wiki/Distributed_hash_table). С помощью DHT реализовано 
полностью распределенное хранение служебной информации, обеспечивающей работоспособность BitPie.NET.

Все узлы в сети BitPie.NET, у которых активен сервис entangled_dht(), будут поддерживать другие машины, 
храня пары (ключ->значение) созданные другими, а так же иметь доступ к собственным служебным данным.

Более подробно об исользовании DHT в системе BitPie.NET читайте в [этом](dht.md) документе.


## Зависит от
* [udp_datagrams()](services/service_udp_datagrams.md)


## Влияет на
* [stun_server()](services/service_stun_server.md)
* [stun_client()](services/service_stun_client.md)
* [private_messages()](services/service_private_messages.md)


## Настройки сервиса
* services/entangled-dht/enabled


## Связанные файлы проекта
* [service_entangled_dht.py](services/service_entangled_dht)

