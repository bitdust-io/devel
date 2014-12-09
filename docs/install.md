# Установка


## Windows

Скачайте файл [bitpie-stable.msi](http://bitpie.net/download/bitpie-stable.msi) 
и запустите его двойным щелчком мыши.

Это архив Windows Installer, программа BitPie.NET написана на языке [Python](http://python.org) и собрана под Windows 
с использованием утилиты [py2exe](http://www.py2exe.org/).

Программа BitPie.NET будет установлена на ваш персональный компьютер в папку 

  * `С:\Users\<имя пользователя>\.bitpie\` для Windows 8.1, Windows 7, и Windows Vista
  * `C:\Documents and Settings\<имя пользователя>\.bitpie\` для Windows XP и Windows 2000

## Ubuntu / Debian

Скачайте файл [bitpie-ubuntu-stable.deb](http://bitpie.net/download/bitpie-ubuntu-stable.deb) и запустите его.

Это автоматически установит пакет `bitpie` на ваш компьютер.

Запускаемые файлы программы BitPie.NET располагаются в папке `/usr/share/bitpie` 
в открытых исходных кодах на языке Python. 


## Из исходников

В Ubuntu нужно просто установить все зависимости используя менеджер пакетов:

    sudo apt-get update
    sudo apt-get install python python-twisted python-pyasn1 python-openssl python-crypto
    
Для графического интерфейса необходимо так же установить следующие пакеты:
    
    sudo apt-get install python-wxgtk2.8 python-imaging

Пользователи Windows могут использовать приведенные ниже ссылки для установки необходимых пакетов самостоятельно:

  * [python 2.6 или 2.7](http://python.org/download/releases) (python3 не поддерживается)
  * [twisted 12.0](http://twistedmatrix.com) (или более поздние версии)
  * [pyasn1](http://pyasn1.sourceforge.net)
  * [pyOpenSSL](https://launchpad.net/pyopenssl)
  * [pycrypto](https://www.dlitz.net/software/pycrypto/)
  * [PIL](http://www.pythonware.com/products/pil)
  * [wxgtk2.8](http://wiki.wxpython.org/InstallingOnUbuntuOrDebian)

Далее скачайте файл [bitpie.tar.gz](http://bitpie.net/download/bitpie.tar.gz) содержащий исходный код BitPie.NET. 
Распакуйте архив в любое удобное для вас место.

    wget http://bitpie.net/download/bitpie.tar.gz
    cd bitpie-0.1.14.879/
    cd bitpie

Еще один способ получить исходники это клонировать себе наш публичный Git репозиторий:

    sudo apt-get install git
    git clone http://gitlab.bitpie.net/devel/bitpie.git
    cd bitpie
    
В этом случае вы всегда сможете одной коммандой обновиться до самой свежей версии ПО:
    
    git pull
    
Я рекомендую сразу после получения исходников использовать следующую комманду, которая создаст
алиас для BitPie.NET в вашей ОС:

    sudo python bitpie.py integrate


## Запуск

Если вы установили программу BitPie.NET используя автоматический инсталлятор,
то просто кликните дважды по иконке BitPie.NET на рабочем столе. 
По умолчанию программа будет запущена автоматически после окончания работы инсталлятора.

При утсановке `deb` пакета в операционной системе Ubuntu доступ к программе через коммандную строку, 
возможен используя автоматически созданный алиас `bitpie`.

    bitpie show

Для запуска ПО BitPie.NET из исходников используйте следующую комманду
(если вы еще не выполнили команду `integrate`):

    cd bitpie
    python bitpie.py show


## Вход в сеть

Прежде чем начать взаимодействие с другими пользователями в сети вам необходимо сгенерировать
секретный ключ и свой публичный `identity` файл - программа предложит сделать это при первом запуске.

Введите предпочитаемое название файла - этот короткий псевдоним будет отображаться у других пользователей,
когда они соединяются с вами и ведется обмен данными. 

Если вы запускаете ПО в системе без графического интерфейса,
то вам нужно будет зарегистрироваться из командной строки самостоятельно:

    bitpie register <your_nickname>

Я рекомендую вам после входа в сеть создать еще одну копию секретного ключа в надежном месте. 
Так у вас будет возможность восстановить ваши данные и служебную информацию в будущем,
например если данные на вашем ПК были утеряны.

Вы можете сделать это из графического интерфейса или через коммандную строку:

    bitpie key copy <filename>


## Локальные данные

Все файлы, которые относятся к программе BitPie.NET, по умолчанию располагаются в папке 
`~/.bitpie`
Ваши настройки, копии локальных данных, файлы принадлежащие и локальные файлы сохраняются в папке .


## Справка

Используйте эту комманду что бы получить справочную информацию о программе:

    bitpie help


