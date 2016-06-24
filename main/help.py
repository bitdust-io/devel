#!/usr/bin/python
#help.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: help

A methods to just store text constants, used to print command-line instructions.
"""

def usage():
    return '''usage: bitdust [options] [command] [arguments]
    
Commands:
  start
  detach
  restart
  stop
  show
  integrate
  identity create <username> [private key size]
  identity restore <private key source file> [IDURL]
  identity erase
  key copy
  key backup <destination filename to write your private key>
  key print  
  get <option>
  set <option> [value]
  set list
  file list
  file idlist
  file bind <local file or folder>
  file add <local file or folder>
  file addtree <folder path>
  file start <local path or ID>
  file delete <local path, ID or full version ID>
  file delete local <full backup ID>
  file abort <path ID or full backup ID>
  file queue
  file progress
  file sync
  restore list
  restore start <backup ID> 
  restore start <backup ID> <destination folder>
  restore abort <backup ID>
  restore progress 
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
  chat
  chat send <IDURL> <"text message">
  api <method> [params]
  version
  help
  usage
'''      

#------------------------------------------------------------------------------ 

def help():
    return '''usage: bitdust [options] [command] [arguments]

Commands:
  [start]               start main BitDust process
  
  detach                start BitDust in as a daemon process
  
  restart               restart BitDust 

  stop                  stop BitDust

  show                  start BitDust and show the main window
  
  integrate             creates a `bitdust` alias in OS in
                        /usr/local/bin/bitdust or in 
                        ~/bin/bitdust if no access to /usr/local/ 

  identity create <nickname> [private key size]
                        generate a new private key and 
                        new identity file for you
                        key size can be 1024, 2048 or 4096

  identity restore <private key source file> [IDURL]
                        recover existing identity file
                        with your private key file
                        
  identity erase        delete local identity from this machine 

  key copy              copy private key to clipboard, use Ctrl+V to paste it
  
  key backup <a filename for copy of private key>
                        copy private key into file
                        
  key print             print private key to console
                        WARNING!!! do not publish your key  

  get <option>          print current value for given program setting

  set <option> [value]  assign a new value for program setting
  
  set list              print all available settings and values

  file list             show a full catalog of registered files and folders

  file idlist           show a list of items already uploaded on remote peers 

  file bind <local path>
                        add given path as a top level item in the catalog

  file add <local path>
                        replicate given path into the catalog,
                        this will add to catalog all parent folders too
  
  file addtree <local folder path>
                        replicate given folder with all sub folders to the catalog,
                        be aware if you add too much items to catalog
                        the software may operate inefficient

  file start <local path or ID>
                        start uploading a catalog item on to remote peers,
                        bind a new local file/folder if path is not yet
                        existing in the catalog
                        
  file delete <local path, ID or full backup ID>
                        remove a file or folder (with all sub folders)
                        from catalog or only erase a given remote copy

  file delete local <full backup ID>
                        remove only local copy of given backup,
                        keep remote copy on suppliers HDD
  
  file queue            show a list of paths to be uploaded
  
  file progress         show a list of currently running uploads
                        
  file sync             request all suppliers to check/restart uploads 
  
  restore list          show a list of items already uploaded on remote peers
  
  restore start <local path or ID> [destination path]
                        download personal data back to local machine
                        from remote peers, you can specify 
                        the destination path on your local drive,
                        WARNING! source path is default location,
                        so it will overwrite existing files by default                        
                        
  restore abort <backup ID>
                        abort currently running restore process of given item
                        
  restore progress      show currently running downloads 

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
  
  chat                  start a chat session, send/listen text
                        messages from other users
  
  chat send <IDURL> <"text message">
                        send a single text message to remote user
 
  api <method> [params] execute API method and return JSON response

  version               display current software version

  help                  print a detailed info about command line usage
  
  usage                 print a brief list of available commands

'''


# recover <private key filename> [idurl or username]
#                       recover existing account with your private key file
#                       
#  schedule <folder> [schedule in compact format]
#                        set or get a schedule for a folder to start backups automatically
#   help schedule         print format description to set scheduled backup
#  money                 show the financial status 
#
#  money transfer <username or idurl> <amount>
#                        transfer money to another user 
#
#  money receipts        show receipts history
#
#  money receipt <receipt ID>
#                        show single receipt info
#  
  

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
  set logs/stream-enabled False            turn off web server for program logs
  set list                                 list all available options

'''

