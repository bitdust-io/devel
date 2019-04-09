#!/usr/bin/python
# help.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (help.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#

"""
.. module:: help.

A methods to just store text constants, used to print command-line
instructions.
"""


def usage_text():
    return '''usage: bitdust [options] [command] [arguments]

Commands:
  install
  start
  detach
  restart
  stop
  show
  alias
  id
  idurl
  identity create <username> [private key size]
  identity backup [private key file path]
  identity restore <private key file path> [IDURL]
  identity erase
  identity show
  identity server [start | stop]
  key list
  key create <key id>
  key delete <key id>
  key get [key_id]
  key copy [key id]
  key backup <key id> <filename>
  get <option>
  set <option> [value]
  set list
  file sync
  file list
  file create <remote path>
  file delete <remote path>
  dir create <remote path>
  dir delete <remote path>
  file upload <local path> <remote path>
  file download <remote path> <local path>
  file cancel <upload | download> <remote path>
  file progress [upload | download]
  supplier list
  supplier replace <IDURL or position>
  supplier change <IDURL or position> <new IDURL>
  supplier ping
  customer list
  customer remove <IDURL>
  customer ping
  storage
  automat list
  service list
  service <service name>
  ping <IDURL>
  dhtseed
  chat
  chat send <IDURL> "<text message>"
  api <method> [params]
  version
  help
  usage
'''

#------------------------------------------------------------------------------


def help_text():
    return '''usage: bitdust [options] [command] [arguments]

Commands:
  install               create virtual environment and deploy
                        Python2.7 dependencies in ~/.bitdust/venv/

  [start]               start main BitDust process

  detach                start BitDust in as a daemon process

  restart               restart BitDust

  stop                  stop BitDust

  show                  start BitDust and show the main window

  alias                 helper to create a binary command-alias in OS,
                        you can put it in /usr/local/bin/bitdust for ex.

  id                    print your global ID in BitDust network

  idurl                 print your global IDURL: global address of
                        your identity file in the Internet

  identity create <nickname> [private key size]
                        generate a new private key and
                        new identity file for you
                        key size can be 1024, 2048 or 4096

  identity backup [private key file path]
                        backup your IDURL and private key to the file,
                        to be able to restore your data in case of lost
                        ATTENTION! always keep a backup copy of your
                        master key in safe place, this is the only
                        possible way to recover access to your lost data

  identity restore <private key file path> [IDURL]
                        recover existing identity file
                        with your private key file

  identity erase        delete local identity from this machine

  identity show         displays your current identity file content

  identity server start|stop
                        start/stop stand alone identity server on that machine

  key list              list details for known private keys

  key create <key_id> [size]
                        generate a new private key with given ID

  key delete <key_id>
                        erase given private key
                        WARNING!!! all data encrypted with that key will be lost

  key get [key_id]      prints private key details to console
                        WARNING!!! never publish your "master" key

  key copy [key_id]     copy given private key to clipboard, use Ctrl+V to paste it
                        WARNING!!! never publish your "master" key

  key backup <key_id> <filename>
                        copy private key into file

  get <option>          print current value for given program setting

  set <option> [value]  assign a new value for program setting

  set list              print all available options and current values

  file sync             ping all suppliers and recheck/restart uploads

  file list             show a list of known files and folders on remote peers

  file create <remote path>
                        creates "virtual" remote file in the catalog,
                        "remote path" have such format in all commands:
                        {key_alias}${user_name}@{id_host}:{remote_path}

  file delete <remote path>
                        remove give file from the catalog and remote suppliers

  dir create <remote path>
                        create "virtual" remote folder in the catalog

  dir delete <remote path>
                        erase folder and all sub-folders from the catalog
                        and remote suppliers

  file upload <local path> <remote path>
                        start uploading a file or folder to remote suppliers,
                        first you need to create "remote path" in the catalog

  file download <remote path> [local path]
                        download file or folder from remote peers to local drive
                        save to current folder if "local path" was not set

  file cancel <upload | download> <remote path>
                        abort currently running file upload or download process

  file progress <upload | download>
                        show a list of currently running uploads or/and downloads

  supplier list         show list of your suppliers
                        nodes who stores your data on own machines

  supplier replace <IDURL or position>
                        execute a fire/hire process for given supplier,
                        another random node will replace him

  supplier change <IDURL or position> <new IDURL>
                        replace a supplier by given node

  supplier ping         send Identity packet to all suppliers
                        and wait Ack packets to check their statuses

  customer list         show list of your customers
                        nodes who stores own data on your machine

  customer remove <IDURL>
                        reject supporting given customer and
                        remove all local files stored for him

  customer ping         send Identity packet to all customers
                        and wait Ack packets to check their statuses

  storage               show donated/needed storage statistic

  automat list          list all running state machines and current states

  service list          list all registered services

  service <service name>
                        print detailed info for given service

  ping <IDURL>          send Identity packet to this node
                        and wait Ack packet to check his status

  dhtseed               start stand alone Distributed Hash Table seed node

  chat                  start a chat session, send/listen text
                        messages from other users

  chat send <IDURL> "<text message>"
                        send a single text message to remote user

  api <method> [params] execute API method and return JSON response

  version               display current software version

  help                  print a detailed info about command line usage

  usage                 print a brief list of available commands

'''

#------------------------------------------------------------------------------


def schedule_format():
    return '''
Schedule compact format:
[mode].[interval].[time].[details]

mode:
  n-none, h-hourly, d-daily, w-weekly, m-monthly, c-continuously

interval:
  just a number - how often to restart the task, default is 1

time:
  [hour]:[minute]

details:
  for weeks: Mon Tue Wed Thu Fri Sat Sun
  for months: Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec

some examples:
  none                    no schedule
  hourly.3                each 3 hours
  daily.4.10:15.          every 4th day at 10:15
  w.1.3:00.MonSat         every Monday and Saturday at 3:00 in the night
  weekly.4.18:45.MonTueWedThuFriSatSun
                          every day in each 4th week in 18:45
  m.5.12:34.JanJul        5th Jan and 5th July at 12:34
  c.300                   every 300 seconds (10 minutes)
'''


def settings_help():
    return '''set [option] [value]

examples:
  set donated 4GB                          set donated space
  set needed                               print your needed space size
  set services/backups/max-copies 4        set number of backup copies for every folder
  set services/customer/suppliers-number   print number of your suppliers
  set list                                 list all available options

'''
