# Сервис list_files()


## Описание
Cетевая служба `list_files()` ответственна за поддержание оперативного списка файлов,
принадлежащих пользователю, которые хранятся на машинах его хранителей. 

При старте сервиса, будет создан экземпляр автомата `list_files_orator()` и произойдет его инициализация.
Этот автомат запрашивает список хранимых файлов с машин хранителей
и поддерживает оперативные копии этих данных на жестком диске. 
Список файлов от каждого хранителя будет записан в локальный файл `.bitdust/supplier/[IDURL]/listfiles`.

При отключении службы `list_files()` станет невозможно получить информацию о хранимых в сети данных
и отключены сервисы нижних уровней реализующие распределенное хранение данных.


## Зависит от
* [customer()](services/service_customer.md)


## Влияет на
* [backup_db()](services/service_backup_db.md)
* [backups()](services/service_backups.md)


## Запуск автоматов
* [list_files_orator()](customer/list_files_orator.md)


## Настройки сервиса
* services/list-files/enabled - включение/выключение сервиса `list_files()`


## Связанные файлы проекта
* [services/service_list_files.py](services/service_list_files.py)
* [customer/list_files_orator.py](customer/list_files_orator.py)



