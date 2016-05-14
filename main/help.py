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
  backup list
  backup idlist
  backup add <local file or folder>
  backup addtree <folder path>
  backup start <local path or ID>
  backup delete <local path, ID or full version ID>
  backup delete local <full backup ID>
  backup abort <path ID or full backup ID>
  backup queue
  backup progress
  backup update
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
  ping <IDURL>
  set <option> [value]
  set list
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

  backup list           show a full catalog of registered files and folders

  backup idlist         show a list of items already uploaded on remote peers 

  backup add <local path>
                        add given path to the catalog
  
  backup addtree <local folder path>
                        add given folder (with all sub folders) to the catalog

  backup start <local path or ID>
                        start a new backup of the local file or folder 
                        or existing ID from catalog
                        
  backup delete <local path, ID or full backup ID>
                        remove a file or folder (with all sub folders)
                        from catalog or just delete a given backup

  backup delete local <full backup ID>
                        remove only local copy of given backup,
                        keep remote copy on suppliers HDD
                        
  backup update         request all suppliers to update info for all backups 
  
  backup queue          show a list of paths to be uploaded
  
  backup progress       show a list of currently running uploads
  
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

  ping <IDURL>          send Identity packet to this node
                        and wait Ack packet to check his status

  set <option> [value]  to get/set program setting
  
  set list              print all available settings and its values
  
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
    
    
    
    
    
#------------------------------------------------------------------------------ 
    
def usage0():
    return '''usage: bitdust [options] [command] [arguments]
    
Commands:
  start
  detach
  restart
  stop
  show
  identity create <username> [private key size]
  identity restore <private key source file> [IDURL]
  key copy
  key copy <destination filename to write your private key>
  key print
  backup list
  backup idlist
  backup add <local path>
  backup addtree <local folder>
  backup start <local path or ID>
  backup starttree <local folder or ID>
  backup delete <local path, ID or full backup ID>
  backup delete local <full backup ID>
  backup update
  restore <backup ID> 
  restore <backup ID> <destination folder> 
  stats <backup ID>
  stats remote <backup ID>
  stats local <backup ID>
  suppliers 
  suppliers call
  supplier replace <username, number or idurl>
  supplier change <username, number or idurl> <username or idurl>
  customers  
  customers call     
  customer remove <username or idurl>
  storage                                                         
  reconnect
  states
  cache
  cache clear
  messages list
  message send <username or idurl> <subject> <body>
  set <option> [value]
  version
  help
'''    
  




  
#  recover <private key filename> [idurl or username]
#  schedule <folder> [schedule in compact format]
#  money
#  money transfer <username or idurl> <amount>
#  money receipts 
#  money receipt <receipt ID>


def help0():
    return '''usage: bitdust [options] [command] [arguments]

Commands:
  [start]               start BitDust
  
  detach                start BitDust in a child process
  
  restart               restart BitDust 

  stop                  stop BitDust

  show                  start BitDust and show the main window

  identity create <username> [private key size]
                        generate a new private key and new identity file for you
                        key size can be 1024, 2048 or 4096

  identity restore <private key source file> [IDURL]
                        recover existing identity file with your private key file

  register <account name> [private key size] [preferred id server]

  key copy              copy private key to clipboard to paste with Ctrl+V somewhere 
  
  key copy <a filename for copy of private key>
                        copy private key into file to save it in a safe place
                        
  key print             print private key  

  backup list           show a catalog of files and folders

  backup idlist         show a list of backups

  backup add <local path>
                        add file or folder to the catalog, not start the backup
                        
  backup addtree <local path>
                        recursive add folder with all sub folders and files to the catalog,
                        not start the backup 

  backup start <local path or ID>
                        start a new backup of the local file or folder 
                        or existing ID from catalog
                        
  backup starttree <local folder or ID>
                        start a multiple backups of all files and sub folders 
                        of given local folder or using existing ID from catalog  

  backup delete <local path, ID or full backup ID>
                        remove a file or folder (with all subfolders) from catalog
                        or just delete a given backup

  backup delete local <full backup ID>
                        remove only local copy of given backup,
                        keep remote copy on suppliers HDD
                        
  backup update         request all suppliers to update info for all backups 

  restore <backup ID>   restore a backup into its original location
                        WARNING! this will overwrite existing files,
                        current files will be replaced with backed up copy
                        
  restore <backup ID> <destination folder>
                        restore a backed up data into given local folder
                        
  stats <backup ID>     show condition of given backup
  
  stats remote <backup ID>
                        show remote files stats for this backup

  stats local <backup ID>
                        show local files stats for this backup

  suppliers             show list of your suppliers

  suppliers call        send a request packets to check out suppliers status

  supplier replace <username, number or idurl>
                        replace a single supplier with new one

  supplier change <username, number or idurl> <username or idurl>
                        ask to change one supplier to another, by your choice
                        
  customers             show list of your customers
  
  customers call        send a request packets to check out customers status
  
  customer remove <username or idurl>
                        remove a single customer
                        
  storage               print detailed info about needed and donated space

  reconnect             restart network connection

  states                print state machines info
  
  cache                 show list of cached identities
  
  cache clear           erase all identities from the cache 

  messages list         list all messages

  message send <username or idurl> <subject> <body>
                        send a message to given user
  
  set <option> [value]  to modify program setting

  version               display current software version

  help                  print a detailed info about command line usage
  
  help backups          print more info about catalog and backup IDs  
  
  help settings         print settings list
  
  usage                 print a brief list of available commands

'''

