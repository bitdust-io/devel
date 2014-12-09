# Сервис supplier()


## Описание
Служба `supplier()` позволяет другим узлам в сети BitPie.NET использовать машину самого пользователя
как хранилище для их собственных данных. 
Зашифрованные файлы, закачанные с других машин, по умолчанию сохраняются 
в папку `.bitpie/customers/[IDURL владельца]`. 





## Зависит от
* [gateway()](services/service_gateway.md)


## Влияет на
* [customers_rejector()](services/service_customers_rejector.md)


## Запуск автоматов


## Настройки сервиса
* services/supplier/enabled
* services/customer/donated-space - объем отданного в сеть пространства, которое может быть использовано другими пользователями



## Связанные файлы проекта
* [service_supplier.py](services/service_supplier.py)



