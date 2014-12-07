# Сервис identity_server()


## Описание
При включенной службе `identity_server()` в момент запуска ПО на машине пользователя
будет поднят простой Web сервер, который хранит identity файлы других пользателей сети.
Эти файлы хранятся в подпапке `.bitpie/identityserver/` в формате XML и доступны для всех 
в сети Интернет. 

Эту сетевую службу имеет смысл запускать только если пользователь имеет постоянный глобальный IP адрес.
Если машина пользователя имеет доменное, то глобальные адреса identity файлов пользователей будут иметь более 
читаемый формат, иначе глобальный IP адрес машины пользователя будет фигурировать в IDURL адресах.

Служба `identity_server()` по умолчанию выключена, если вы желаете поддержать сеть BitPie.NET и 
хранить у себя identity файлы других пользователей свяжитесь с нами - мы добавим ваш хост в
глобальный список активных Identity серверов.

Читайте подробнее про Identity сервера в BitPie.NET в [этом]() документе.


## Зависит от
* [tcp_connections()](services/service_tcp_connections.md)


## Настройки сервиса
* services/id-server/enabled - включение/выключение сервиса `identity_server()`
* services/id-server/host - доменное имя машины пользователя, если значение не задано то будет использован внешний IP адрес
* services/id-server/tcp-port - номер TCP порта для приема входящих соединений и получения identiy файлов от других пользователей
* services/id-server/web-port - номер WEB порта, на котором будет запущен Identity сервер


## Связанные файлы проекта
* [services/service_identity_server.py](services/service_identity_server.py)
* [userid/identity_server.py](userid/identity_server.py)


## Запуск автоматов
* [identity_server()](userid/identity_server.md)

