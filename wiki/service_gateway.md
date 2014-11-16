Описание:
Служба gateway() является входной точкой для отправки и приема служебных пакетов данных и взаимодействия с внешними узлами в сети BitPie.NET. Это своего рода "ворота" через которые проходит весь полезный трафик для клиентского ПО. 
Основные два метода inbox() и outbox() обрабатывают входящие и исходящие пакеты, подписанные электронной подписью владельца данных. Тело пакета так же может быть зашифровано ключом владельца данных, перед тем как будет передано в метод outbox(). 
Обработчики событий вызывают методы в других сервисах клиентского ПО в момент приема и передачи пакетов. 
Сервис gateway() так же ведет подсчет полезного трафика.

Description:
The service gateway() is the entry point to send and receive service data packets and communicate with other nodes in the BitPie.NET network. This is a sort of "gates" - all useful traffic for client software is passed through it.
The main two methods inbox() and outbox() process incoming and outgoing packets, digitally signed by data owner. The package body can also be encrypted by owner key, before will be passed to the method oubox(). Event handlers call methods in other services of the client software when receiving and transmitting packets appears.
The service gateway() also counts the payload traffic of the software.

Связанные файлы проекта:
services/service_gateway.py 
transport/gateway.py
transport/packet_in.py
transport/packet_out.py 
transport/bandwidth.py 
transport/callback.py
transport/stats.py

