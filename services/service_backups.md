# Сервис backups()


## Описание
В сетевой службе `backups()` собран функционал, реализующий хранение распределенных копий пользовательских
данных на машинах хранителей.

При старте сервиса происходит запуск экземпляра автомата `backup_monitor()`, он следит за уже
размещенными в сети данными. 

Автомат `backup()` управляет созданием новой резервной копии файла или папки с локального диска
пользователя. Будет создан новый экземпляр автомата для каждого активного процесса резервирования
данных. Сгенерированные файлы, сперва помещаются в подпапку `.bitpie/backups/`, а позже пересылаются
на машины хранителей. В настройках ПО можно настроить их автоматическое удаление после окончание
трансфера.

Подробнее о процессе резервирования данных читайте в разделе [...](...).

При отключении сервиса `backups()`, будет невозможна загрузка новых копий данных пользователя на его хранитлей,
а также прекращен процесс автоматического слежения за уже размещенными в сети данными - рано или поздно
это приведет к их полной утрате.


## Зависит от
* [list_files()](services/service_list_files.md)
* [fire_hire()](services/service_fire_hire.md)
* [rebuilding()](services/service_rebuilding.md)


## Влияет на
* [restores()](services/service_restores.md)


## Запуск автоматов
* [backup()](storage/backup.md)
* [backup_monitor()](storage/backup_monitor.md)


## Настройки сервиса
* services/backups/enabled - включение/выключение сервиса `backups()`


## Связанные файлы проекта
* [services/service_backups.py](services/service_backups.py)
* [storage/backup.py](storage/backup.py)
* [storage/backup_control.py](storage/backup_control.py)
* [storage/backup_fs.py](storage/backup_fs.py)
* [storage/backup_matrix.py](storage/backup_matrix.py)
* [storage/backup_monitor.py](storage/backup_monitor.py)
* [storage/backup_tar.py](storage/backup_tar.py)

