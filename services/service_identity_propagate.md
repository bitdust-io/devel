# Сервис identity_propagate()


## Описание
Данная служба ответственна за поддержание identity файла пользователя в актуальном состоянии 
и распространении обновленных копий на другие узлы в сети.

Периодически ПО BitPie.NET запускает процедуру `propagate`:
1. обновленный identiy файл пользователя пересылается на те Identity сервера,
которые хранят этот файл и делают его доступным для всех остальных;
2. обновленный файл записывается в DHT сеть с ключом равным IDURL пользователя
3. с Identity серверов скачиваются identity файлы других пользователей, с которыми поддерживается
постоянный контакт
4. запускается процесс распространения обновленного файла на эти узлы, используя транспортные протоколы 
  
При отключении службы `identity_propagate()` будет прекращено обновление и распростарнение identity файла
пользователя и отключены многие службы нижних уровней, которые реализуют большинство функционала ПО.

Подробнее про систему идентификации пользователей в сети BitPie.NET вы можете прочитать в 
[этом](...) документе.


## Зависит от
* [gateway()](services/service_gateway.md)
* [tcp_connections()](services/service_tcp_connections.md)


## Влияет на
* [p2p_hookups()](services/service_p2p_hookups.md)


## Настройки сервиса
* services/identity-propagate/enabled - включение/выключение сервиса `identity_propagate()`


## Связанные файлы проекта
* [service_identity_propagate.py](services/service_identity_propagate.py)
* [p2p/propagate.py](p2p/propagate.py)
* [contacts/identitycache.py](contacts/identitycache.py)
* [contacts/contactsdb.py](contacts/contactsdb.py)


