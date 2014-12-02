Описание:
Служба network() это базовый сервис, который влияет на все другие сетевые сервисы в клиентском ПО BitPie.NET. При её остановке, произойдет выключение всех активных на данный момент сервисов, будут закрыты все сессии и соединения с другими машинами и программа прекратит всякое взаимодействие с сетью.

Description:
Service network() is a basic service that affects all other network services in the BitPie.NET software. When it is stopped, all currently active services will be also stopped, all sessions and connections to other machines will be closed, and the program should stop any interaction with the network.

Связанные файлы проекта:
services/service_network.py 
p2p/network_connector.py 
p2p/run_upnpc.py

Вызываемые автоматы: 
network_connector()
