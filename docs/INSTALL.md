# Установка


## Из исходников

В Ubuntu нужно просто установить все зависимости одной командой:

    sudo apt-get install python python-twisted python-pyasn1 python-openssl python-crypto python-wxgtk2.8 python-imaging

Пользователи Windows могут использовать приведенные ниже ссылки для установки необходимых пакетов самостоятельно:

* [python 2.6 или 2.7](http://python.org/download/releases), python3 не поддерживается
* [twisted 12.0](http://twistedmatrix.com) (или более поздние версии)
* [pyasn1](http://pyasn1.sourceforge.net)
* [pyOpenSSL](https://launchpad.net/pyopenssl)
* [pycrypto](https://www.dlitz.net/software/pycrypto/)
* [PIL](http://www.pythonware.com/products/pil)
* [wxgtk2.8](http://wiki.wxpython.org/InstallingOnUbuntuOrDebian)

Далее скачайте [архив](http://bitpie.net/download/bitpie.tar.gz) с исходным кодом BitPie.NET. 
Распакуйте архив в любое удобное для вас место.


## Запуск

Для запуска ПО из коммандной строки используйте следующую комманду:

    cd bitpie
    python bitpie.py show
	
Вы должны будете сгенерировать свой файл `identity`, чтобы иметь возможность общаться с другими
пользователями сети - программа предложит сделать это при первом запуске.

Если вы запускаете ПО в системе без графического интерфейса,
вам нужно будет зарегистрироваться из командной строки самостоятельно:

    python bitpie.py register <your_nickname>

Я рекомендую вам создать еще одну копию секретного ключа в надежном месте, 
чтобы иметь возможность восстановить ваши данные в будущем.
Вы можете сделать это из графического интерфейса или через коммандную строку:

	python bitpie.py key copy <filename>

Ваши настройки и локальные файлы сохраняются в папке `~/.bitpie`.

Используйте эту комманду что бы получить больше информации:

	python bitpie.py help

