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
    return '''usage: python bitpie.py [options] [command] [arguments]
    
Commands:
  start
  detach
  restart
  stop
  show
  register <account name> [private key size]
  recover <private key filename> [idurl or username]
  key copy
  key copy <filename for copy of private key>
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
  money
  money transfer <username or idurl> <amount>
  money receipts 
  money receipt <receipt ID>
  set <option> [value]
  version
  help
'''    
#   schedule <folder> [schedule in compact format]


def help():
    return '''usage: python bitpie.py [options] [command] [arguments]

Commands:
  [start]               start BitPie.NET
  
  detach                start BitPie.NET in a child process
  
  restart               restart BitPie.NET 

  stop                  stop BitPie.NET

  show                  start BitPie.NET and show the main window

  register <account name> [private key size]
                        generate a new private key and register new account
                        key size can be 1024 or 2048

  recover <private key filename> [idurl or username]
                        recover existing account with your private key file
                        
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
                        replace a single supplier with new one, given by central server

  supplier change <username, number or idurl> <username or idurl>
                        ask to change one supplier to another, by your choice
                        
  customers             show list of your customers
  
  customers call        send a request packets to check out customers status
  
  customer remove <username or idurl>
                        remove a single customer
                        
  storage               print detailed info about needed and donated space

  reconnect             restart network connection

  states                print state machines info
  
  money                 show the financial status 

  money transfer <username or idurl> <amount>
                        transfer money to another user 

  money receipts        show receipts history

  money receipt <receipt ID>
                        show single receipt info
  
  set <option> [value]  to modify program setting

  version               display current software version

  help                  print this message
  
  help backups          print more info about catalog and backup IDs  
  
  help settings         print settings list

'''

#  schedule <folder> [schedule in compact format]
#                        set or get a schedule for a folder to start backups automatically
#   help schedule         print format description to set scheduled backup
  



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
  set general.general-backups 4            set number of backup copies for every folder
  set suppliers                            print number of your suppliers
  set logs.stream-enable False             turn off web server for program logs
  set list                                 list all available options

'''
