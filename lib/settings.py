#!/usr/bin/python
#settings.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: settings

I think this is a most used module in the project.
Various parts of the code use this module to get the user settings and global constants.

TODO:
need to move out userconfig stuff from that file
"""

import os


import userconfig
import io
import eccmap
import maths
import diskspace
import nameurl


_BaseDirPath = ''   # location for ".bitpie" folder, lets keep all program DB in one place
                    # however you can setup your donated location in another place, second disk ...
                    # Linux: /home/$USER/.bitpie
                    # WindowsXP: c:\\Document and Settings\\[user]\\.bitpie
                    # Windows7: c:\\Users\\[user]\\.bitpie
_UserConfig = None  # user settings read from file .bitpie/metadata/userconfig
_OverrideDict = {}  # list of values to replace some of user settings 
_BandwidthLimit = None 
_BackupBlockSize = None
_BackupMaxBlockSize = None
_InitDone = False    

#------------------------------------------------------------------------------ 
#---INIT----------------------------------------------------------------------------

def init(base_dir=None):
    """
    Must be called before all other things here.
    """
    global _InitDone
    if _InitDone:
        return
    _InitDone = True
    _init(base_dir)

def _init(base_dir=None):
    """
    This is called only once, prepare a bunch of things:
        - Set the base folder where for program data
        - Check and create if not exist "metadata" directory 
        - Load settings from [BitPie.NET data dir]/metadata/userconfig or create a new, default settings
        - Check other "static" folders
        - Validate most important user settings
        - Check custom folders 
    """
    io.log(4, 'settings._init')
    _initBaseDir(base_dir)
    io.log(2, 'settings._init data location: ' + BaseDir())
    _checkMetaDataDirectory()
    uconfig()
    _checkStaticDirectories()
    _checkSettings()
    _checkCustomDirectories()

#------------------------------------------------------------------------------ 
#---USER CONFIG---------------------------------------------------------------------------

def uconfig(key=None):
    """
    An access function to user configuration.
    Load settings from local file or create a default set.
    
    If ``key`` is None - return the whole object, see ``lib.userconfig.UserConfig`` class.
        >>> import settings
        >>> settings.init()
        >>> settings.uconfig()
        <userconfig.UserConfig instance at 0x00BB6C10>
            
    Or you can pass a setting name to request it. 
        >>> settings.uconfig("logs.debug-level")
        '14'
    """
    global _UserConfig
    global _OverrideDict
    #init()
    if _UserConfig is None:
        if os.path.exists(os.path.join(MetaDataDir(),"user-config")) and not os.path.exists(os.path.join(MetaDataDir(),"userconfig")):
            io.log(4, 'settings.uconfig rename "user-config" to "userconfig"')
            try:
                os.rename(os.path.join(MetaDataDir(),"user-config"), os.path.join(MetaDataDir(),"userconfig"))
            except:
                pass
        io.log(6, 'settings.uconfig loading user configuration from: ' + UserConfigFilename())
        _UserConfig = userconfig.UserConfig(UserConfigFilename())
    if key is None:
        return _UserConfig
    else:
        if key in _OverrideDict:
            return _OverrideDict[key]
        res = _UserConfig.get(key)
        if res is None:
            return ''
        return res

def override(key, value):
    """
    This method can be used to redefine values in UserConfig without writing changes on disk.
    Useful when user pass some params via command line - they should override the local settings.
    """
    global _OverrideDict
    io.log(4, 'settings.override %s=%s' % (key, value))
    _OverrideDict[key] = value

def override_dict(d):
    """
    You can pass a dictionary of settings to override existing user config.
    """
    for key, value in d.items():
        override(key, value)
        
#------------------------------------------------------------------------------ 
#--- CONSTANTS ---------------------------------------------------------------------------

"""
Below is a set of global constants.
"""

def DefaultPrivateKeySize():
    """
    User can choose size of his Private Key during install.
    Can be 1024, 2048 or 4096.
    """
    return 4096

def BasePricePerGBmonth():
    """
    Dropbox have a 10$/month for 100-500 GB.
    So let's have 10$ for 1Tb. this is 0.01$.
    Definitely - this is not very important thing at the moment. :-)
    """
    return 0.01

def BasePricePerGBDay():
    """
    Almost the same.
    """
    return BasePricePerGBmonth() / 30.0

def defaultDebugLevel():
    """
    Default debug level, lower values produce less messages.
    """
    return 6

def IntSize():
    """
    This constant is used in the RAID code.
    The idea is to be able to optionally switch to 64 bit one day.  
    """
    return 4

def MinimumSendingDelay():
    """
    The lower limit of delay for repeated calls for sending processes.
    DO NOT SET TO 0 - the main process will be blocked.
    See ``lib.misc.LoopAttenuation`` method.
    """
    return 0.01

def MaximumSendingDelay():
    """
    The higher limit of delay for repeated calls for sending processes.
    Higher values should decrease the network speed, but save CPU resources.  
    """
    return 2.0 

def MinimumReceivingDelay():
    """
    Lower limit for receiving processes.
    """
    return 0.05

def MaximumReceivingDelay():
    """
    Higher limit for receiving processes.
    """
    return 4.0

def MaxPacketsOutstanding():
    """
    PREPRO
    Should be a function of disk space available 
    """
    return 100

def SendingSpeedLimit():
    """
    This is lower limit during file sending in Kilobytes per second.
    Used to calculate a packet timeout - bigger packets should have longer timeouts.
    If sending below this speed - we count this supplier as failed.
    If we sending too slow to all nodes - it's our problems, not suppliers.
    """
    return 5 * 1024 

def DefaultBandwidthInLimit():
    """
    Incoming bandwidth limit in Kilobytes per second, 0 - unlimited.
    """
    return 0

def DefaultBandwidthOutLimit():
    """
    Outgoing bandwidth limit in Kilobytes per second, 0 - unlimited.
    """
    return 0

def SendTimeOut():
    """
    A default timeout when sending packets.
    """
    return 10 

def MaxRetries():                 
    """
    The idea was to create some "exponential backoff" - 
    double each time. Set to 1 at the moment - so failed packets is ignored. 
    """
    return 1  

def DefaultSendTimeOutEmail():
    """
    Timeout for email sending, not used.
    """
    return 300                

def DefaultSendTimeOutHTTP():
    """
    Timeout for http sending, not used.
    """
    return 60                

def DefaultAlivePacketTimeOut():
    """
    Lets send alive packets to our contacts every hour.
    """
    return 60 * 60                  

def DefaultBandwidthReportTimeOut():
    """
    Send ``BandwidthReport`` packets every 24 hours.
    """
    return 60 * 60 * 24                

def DefaultNeedSuppliersPacketTimeOut():
    """
    If we need suppliers we will request it every 60 sec. from Central server. 
    """
    return 60                     

def DefaultDesiredSuppliers():
    """
    A starting number of suppliers for new users.
    Definitely we want to have 64 by default, but we need to have much more alive users to do that. 
    """
    return 4

def DefaultLocaltesterLoop():
    """
    The code in ``p2p.local_tester`` will check the customers files periodically.
    This constant controls that - seconds between two calls.
    """
    return 20              

def DefaultLocaltesterValidateTimeout():
    """
    A period in seconds to call ``Validate`` action of the local tester. 
    """
    return 120 * 60               

def DefaultLocaltesterUpdateCustomersTimeout():
    """
    A period in seconds to call ``UpdateCustomers`` action of the local tester. 
    """
    return 5 * 60               

def DefaultLocaltesterSpaceTimeTimeout():
    """
    A period in seconds to call ``SpaceTime`` action of the local tester. 
    """
    return 5 * 60          

def MinimumUsernameLength():
    """
    A minimum possible user name length.
    """
    return 3

def MaximumUsernameLength():
    """
    A maximum possible user name length.
    """
    return 20

def DefaultDonatedMb():
    """
    Default donated space value - user can set this at any moment in the settings.
    """
    return 8*1024

def DefaultNeededMb():
    """
    Default needed space value.
    """
    return 4*1024

def MinimumNeededMb():
    """
    Minimum needed Megabytes - I really do not want to allow user to set needed space to zero.
    So need to request at least 1Mb from the network.
    """
    return 1

def MinimumDonatedMb():
    """
    Minimum donated space amount in Megabytes - need to donate at least 2 Mb right now.
    """
    return 2

def DefaultBackupBlockSize():
    """
    Default block size in bytes, user can set this in settings.
    We split a backed up data into blocks of equal size and 
    perform RAID operation on every block - one by one.  
    """
    return 256 * 1024

def DefaultBackupMaxBlockSize():
    """
    The maximum default block size, user can set this in the settings.
    """
    return 10 * 1024 * 1024

def MinimumBandwidthInLimitKBSec():
    """
    Not used, idea was to limit the minimum bandwidth given to BitPie.NET.
    """
    return 10

def MinimumBandwidthOutLimitKBSec():
    """
    Not used.
    """
    return 10

def CentralKillNotAliveUserAfter():
    """
    Central server will remove 'dead' users from the network.
    This is a number of days which user can stay off line before he will be killed. 
    """
    return 60 

def FireHireMinimumDelay():
    """
    Really do not want to fire suppliers too often, so use 15 minutes interval.
    """
    return 60 * 15  

def BackupDBSynchronizeDelay():
    """
    Save backup index database no more than one time per every 5 min.
    """
    return 60 * 5 

def MaxDeletedBackupIDsToKeep():
    """
    How many deleted backup IDs do we want to hold on to in backup db.
    Not used.
    """
    return 100 

def DefaultBitCoinCostPerDHNCredit():
    """
    Let's calculate this.:
        1)  1 DHN ~ 1 US $ - this is our default exchange rate.
        2)  1 BTC ~ 130 $ US on 26 Sep 2013 and still going up - this  
        3)  so 1 DHN is about 0.00769 BTC if we want to keep DHN to $ US exchange rate
        4)  let's decrease it 10 times or even more so people can have flexible market
            and let's trade at least 1 DHN at once, lower values seems very small
            another one thing is that BitCoins have minimum transaction amount: 0.00005430 BTC
    """
    return 0.0005 

#------------------------------------------------------------------------------ 
#---CONSTANTS ( STRINGS ) ----------------------------------------------------------------------------

def ApplicationName():
    """
    May be one day we decide to do some rebranding - so this can be useful method. :-)
    But this is not used at the moment. 
    """
    return 'BitPie.NET'

def ListFilesFormat():         
    """
    Argument to ListFiles command to say format to return the data in.
    Can be "Text" or "Compressed".
    TODO: add "Encrypted" format 
    """
    return "Compressed"        

def DefaultEccMapName():
    """
    This is a ecc map name used by default - must comply with ``DefaultDesiredSuppliers()``. 
    """
    return 'ecc/4x4'

def HMAC_key_word():
    """
    I was playing with HMAC hash, this is a "secret password" :-)
    """
    return 'Vince+Veselin+Derek=BigMoneyAndSuccess'

def DefaultRepo(): 
    """
    BitPie.NET software can be updated from different "repositories".
    Right now we have three locations for Windows (testing, development and stable) 
    and one for Linux (going to add another one).
    This is to be able to run different code in the network and so be able to test new features
    without any chances to broke the whole network.
    """
    return 'devel'

def UpdateLocationURL(repo=DefaultRepo()):
    """
    Return a given repository location for Windows.
    """
    if repo == 'devel':
        return 'http://bitpie.net/devel/'
    elif repo == 'stable':
        return 'http://bitpie.net/stable/'
    else: 
        return 'http://bitpie.net/stable/'

def FilesDigestsFilename():
    """
    This file keeps MD5 checksum of all binary files for Windows release.
    Every Windows repository have such file, this is link for "stable" repo::
    
        http://bitpie.net/repo/stable/info.txt
        
    Local copy of this file is also stored in the file::
    
        [DHN data dir]/metadata/info.
        
    Our dhnstarter.exe read local copy and than can request a public copy and compare the content.
    If some files were changed or new files added to the repo - it will update the local binaries from repo.
    The idea is to update only modified files when new release will be published.
    """
    return 'info.txt'

def CurrentVersionDigestsFilename():
    """
    This file keeps a MD5 checksum of the file "info.txt", see ``FilesDigestsFilename()``.
    It is also placed in the Windows repository::
    
        http://bitpie.net/repo/stable/version.txt
            
    If some binary files have been changed - the file "info.txt" also changed and 
    its checksum also.
    Locally this is stored in the file::
        
        [DHN data dir]/metadata/version
        
    The software check "version.txt" first and if it is not the same - further download "info.txt". 
    """
    return 'version.txt'

def LegalUsernameChars():
    """
    A set of correct chars that can be used for user account names.
    """
    return set("abcdefghijklmnopqrstuvwxyz0123456789-_")

#------------------------------------------------------------------------------ 
#--- FOLDERS ----------------------------------------------------------------------------

def BaseDirDefault():
    """
    A default location for BitPie.NET data folder.
    All of the paths below should be under some base directory.
    """
    return os.path.join(os.path.expanduser('~'), '.bitpie')

def BaseDirLinux():
    """
    Default data folder location for Linux users.
    """
    return os.path.join(os.path.expanduser('~'), '.bitpie')

def BaseDirWindows():
    """
    Default data folder location for Windows users.
    """
    return os.path.join(os.path.expanduser('~'), '.bitpie')

def BaseDirMac():
    """
    Default data folder location for MacOS users.
    """
    return os.path.join(os.path.expanduser('~'), '.bitpie')

def GetBaseDir():
    """
    A portable method to get the default data folder location.  
    """
    if io.Windows():
        return BaseDirWindows()
    elif io.Linux():
        return BaseDirLinux()
    elif io.Mac():
        return BaseDirMac()
    return BaseDirDefault()

def BaseDir():
    """
    Return current data folder location, also call ``init()`` to be sure all things were configured.
    """
    global _BaseDirPath
    init()
    return _BaseDirPath

def BaseDirPathFileName():
    """
    You can configure BitPie.NET software to use another place for data folder.
    Say you want to store DHN files on another disk.
    In the binary folder file "basedir.txt" can be created and it will keep the path to the data folder. 
    """
    return os.path.join(io.getExecutableDir(), 'basedir.txt')

def RestoreDir():
    """
    Default location to place restored files and folders.
    """
    return os.path.expanduser('~')

def WindowsBinDir():
    """
    Under Windows executable files is placed in the [DHN data folder]/bin/.
    This is because Windows Vista and later not allow to write to "Program files" folder. 
    """
    return os.path.join(BaseDir(), 'bin')

def MetaDataDir():
    """
    Return current location of the "metadata" folder - most important config files is here.
    """
    return os.path.join(BaseDir(), "metadata")

def TempDir():
    """
    A place for temporary DHN files, we really need some extra disk space to operate.
    TODO: need to add some stuff to control how much extra space we use and be able limit that. 
    """
    return os.path.join(BaseDir(), "temp")

def IdentityCacheDir():
    """
    See ``lib.identitycache`` module, this is a place to store user's identity files to have them on hands.
    """
    return os.path.join(BaseDir(), "identitycache")

def IdentityServerDir():
    """
    """
    return os.path.join(BaseDir(), 'identityserver')

def BackupsDBDir():
    """
    When you run the backup the following actions occur: 
    
        - data is read from the local disk and compressed 
        - entire volume is divided into blocks 
        - blocks encrypted with user Key 
        - each block is divided into pieces with redundancy - through RAID procedure 
        - pieces of all blocks are stored on a local disk 
        - pieces are transferred to suppliers
        - optionally, local pieces can be removed after delivering to suppliers
         
    This returns a default local folder location where those pieces is stored.
    User can configure that in the settings. 
    """
    return os.path.join(BaseDir(), 'backups')

def MessagesDir():
    """
    A default folder to store sent/received messages.
    """
    return os.path.join(BaseDir(), 'messages')

def ReceiptsDir():
    """
    A default folder to store receipts.
    """
    return os.path.join(BaseDir(), 'receipts')

def Q2QDir():
    """
    I was playing with vertex protocol, this is a place for q2q config files.
    """
    return os.path.join(BaseDir(), 'q2qcerts')

def LogsDir():
    """
    Place for log files.
    """
    return os.path.join(BaseDir(), 'logs')

def SuppliersDir():
    """
    Local folder location to keep suppliers info files.
    """
    return os.path.join(BaseDir(), 'suppliers')

def BandwidthInDir():
    """
    Daily stats for incoming bandwidth is placed in that location.
    Those files is sent to Central server to report own stats.  
    """
    return os.path.join(BaseDir(),"bandin")

def BandwidthOutDir():
    """
    Daily stats for outgoing bandwidth is placed in that location.
    """
    return os.path.join(BaseDir(),"bandout")

def RatingsDir():
    """
    In that location DHN software keeps a rating stats for known users. 
    """
    return os.path.join(BaseDir(), 'ratings')

def CSpaceDir():
    """
    Location for CSpace config files.
    """
    return os.path.join(BaseDir(), 'cspace')

def CSpaceSettingsDir():
    """
    This is a CSpace settings folder location.
    """
    if io.Windows():
        return os.path.join(CSpaceDir(), '_CSpace', 'Settings')
    else:
        return os.path.join(CSpaceDir(), '.CSpace', 'Settings')

def CSpaceProfilesDir():
    """
    This is a CSpace profiles folder location.
    """
    if io.Windows():
        return os.path.join(CSpaceDir(), '_CSpaceProfiles')
    else:
        return os.path.join(CSpaceDir(), '.CSpaceProfiles')

#------------------------------------------------------------------------------ 
#--- FILES --------------------------------------------------------------------------- 

def KeyFileName():
    """
    Location of user's Private Key file.
    """
    return os.path.join(MetaDataDir(), "mykeyfile")

def KeyFileNameLocation():
    """
    User can set another location for his Private Key file - he can use USB stick to keep his Key.
    After DHN stars he can remove the USB stick and keep it in safe place.
    So DHN will keep user's key in the RAM only - this way you can have more protection for your Key. 
    If your machine is stolen - thief can not get your Private key. 
    But you must be sure that machine was switched off - the RAM is erased when power is off.
    This file keeps alternative location of your Private Key.
    """
    return KeyFileName() + '_location'

def SupplierIDsFilename():
    """
    IDs for places that store data for us. Keeps a list of IDURLs of our suppliers.
    """
    return os.path.join(MetaDataDir(), "supplierids")

def CustomerIDsFilename():
    """
    IDs for places we store data for, keeps a list of IDURLs of our customers.
    """
    return os.path.join(MetaDataDir(), "customerids")

def CorrespondentIDsFilename():
    """
    People we get messages from and other stuff not related to backup/restore process. 
    """
    return os.path.join(MetaDataDir(), "correspondentids")

def LocalIdentityFilename():
    """
    A local copy of user's identity file is stored here.
    When doing any changes in the identity file - this appear here firstly.
    Further local identity file is propagated to the identity server 
    and all our contacts so they got the fresh copy asap.
    """
    return os.path.join(MetaDataDir(), "localidentity")

def LocalIPFilename():
    """
    File contains string like "192.168.12.34" - local IP of that machine.
    """
    return os.path.join(MetaDataDir(), "localip")

def ExternalIPFilename():
    """
    File contains string like 201.42.133.2 - external IP of that machine.
    """
    return os.path.join(MetaDataDir(), "externalip")

def ExternalUDPPortFilename():
    """
    File contains external UDP port number of that machine - detected after STUN.
    """
    return os.path.join(MetaDataDir(), "externaludpport")

def DefaultTransportOrderFilename():
    """
    Location for file that keeps an order of used transports.
    """
    return os.path.join(MetaDataDir(), "torder")

def UserNameFilename():
    """
    File contains something like "guesthouse" - user account name.
    """
    return os.path.join(MetaDataDir(), "username")

def UserConfigFilename():
    """
    File to keep a configurable user settings in XML format.
    See ``lib.userconfig`` module.
    """
    return os.path.join(MetaDataDir(), "userconfig")

def GUIOptionsFilename():
    """
    A small file to keep GUI config.
    For example windows positions and sizes after last execution of the program.
    """
    return os.path.join(MetaDataDir(), "guioptions")

def UpdateSheduleFilename():
    """
    Under Windows the update process is done in the dhnstarter.exe file.
    Periodically, the main file dhnmain.exe request file "version.txt" (from currently used repository) 
    to check for new software release.
    Main process can restart itself thru dhnstarter to be able to update the binaries.
    User can set a schedule to check for updates in the settings. 
    """
    return os.path.join(MetaDataDir(), "updateshedule")

def LocalPortFilename():
    """
    This is a file to keep randomly generated port number 
    for HTTP server to provide a Web Access to DHN main process.
    See module ``p2p.webcontrol`` for more details.  
    """
    return os.path.join(MetaDataDir(), 'localport')

def BackupInfoFileNameOld():
    """
    Long time ago backup data base were stored in that file. Obsolete, see ``BackupIndexFileName()``..
    """
    return "backup_info.xml"

def BackupInfoFileName():
    """
    Obsolete, see ``BackupIndexFileName()``.
    """
    return 'backup_db'

def BackupInfoEncryptedFileName():
    """
    Obsolete, see ``BackupIndexFileName()``.
    """
    return 'backup_info'

def BackupIndexFileName():
    """
    This is backup data base index file location.
    This store folder and files names and locations with path ID's and some extra info.
    Located in the file [DHN data dir]/metadata/index.
    Also this file is saved on suppliers in encrypted state.
    
    TODO:
    - need to store files checksums
    - need to store file and folders access modes - just like in Linux
    - need to store user and group for files and folders - like in Linux 
    """
    return 'index'

def BackupInfoFileFullPath():
    """
    Obsolete.
    """
    return os.path.join(MetaDataDir(), BackupInfoFileName())

def BackupInfoFileFullPathOld():
    """
    Obsolete.
    """
    return os.path.join(MetaDataDir(), BackupInfoFileNameOld())

def BackupIndexFilePath():
    """
    A full local path for ``BackupIndexFileName`` file.
    """
    return os.path.join(MetaDataDir(), BackupIndexFileName()) 

def SupplierPath(idurl, filename=None):
    """
    A location to given supplie's data.
    If ``filename`` is provided - return a full path to that file.
    Currently those data are stored for every supplier:
    
        - "connected" : date and time when this man become our suppler 
        - "disconnected" : date and time when this suppler was fired
        - "listfiles" : a list of our local files stored on his machine  
    """
    if filename is not None:
        return os.path.join(SuppliersDir(), nameurl.UrlFilename(idurl), filename)
    return os.path.join(SuppliersDir(), nameurl.UrlFilename(idurl))

def SupplierListFilesFilename(idurl):
    """
    Return a "listfiles" file location for given supplier.
    """
    return os.path.join(SupplierPath(idurl), 'listfiles')

def SupplierServiceFilename(idurl):
    """
    Return a "service" file location for given supplier.
    """
    return os.path.join(SupplierPath(idurl), 'service')

def LocalTesterLogFilename():
    """
    A file name path where dhntester.py will write its logs.
    """
    return os.path.join(LogsDir(), 'dhntester.log')

def MainLogFilename():
    """
    A prefix for file names to store main process logs.
    """
    return os.path.join(LogsDir(), 'dhn')

def UpdateLogFilename():
    """
    A place to store logs from update porcess.
    """
    return os.path.join(LogsDir(), 'dhnupdate.log')

def CSpaceLogFilename():
    """
    Logs from ``lib.transport_cspace`` module goes here.
    """
    return os.path.join(LogsDir(), 'cspace.log')

def AutomatsLog():
    """
    All state machines logs in the main process is written here.
    """
    return os.path.join(LogsDir(), 'automats.log')

def RepoFile():
    """
    A file to store info about currently used repository. 
    """
    return os.path.join(MetaDataDir(), 'repo')

def VersionFile():
    """
    A place for local copy of "version.txt" file, see ``CurrentVersionDigestsFilename()``. 
    """
    return os.path.join(MetaDataDir(), 'version')

def InfoFile():
    """
    A place for local copy of "info.txt" file, see ``FilesDigestsFilename()``.
    """ 
    return os.path.join(MetaDataDir(), 'info')

def RevisionNumberFile():
    """
    We keep track of Subversion revision number and store it in the binary folder.
    This is a sort of "product version".
    Probably not very best idea, we need to use a widely used software version format. 
    """
    return os.path.join(io.getExecutableDir(), 'revnum.txt')

def CustomersSpaceFile():
    """
    This file keeps info about our customers - how many megabytes every guy takes from us. 
    """
    return os.path.join(MetaDataDir(), 'space')

def CustomersUsedSpaceFile():
    """
    """
    return os.path.join(MetaDataDir(), 'spaceused')

def BalanceFile():
    """
    This file keeps our current DHN balance - two values: 
        - transferable funds
        - not transferable funds 
    """
    return os.path.join(MetaDataDir(), 'balance')

def CertificateFiles():
    """
    The idea is to have a global certificate for BitPie.NET server, just like https works.
    """
    return [    os.path.join(MetaDataDir(), 'bitpie.cer'),
                os.path.join('.', 'bitpie.cer'),
                os.path.join(io.getExecutableDir() ,'bitpie.cer'),]

def CSpaceSavedProfileFile():
    """
    This file is used in the CSpace code.
    You can have different profiles and this points to currently used profile.
    """
    return os.path.join(CSpaceSettingsDir(), 'SavedProfile') 

def CSpaceSavedPasswordFile():
    """
    This file is used in the CSpace code.
    """
    return os.path.join(CSpaceSettingsDir(), 'SavedPassword') 

def CSpaceRememberKeyFile():
    """
    This file is used in the CSpace code.
    """
    return os.path.join(CSpaceSettingsDir(), 'RememberKey') 

def DHTDBFile():
    return os.path.join(MetaDataDir(), 'dhtdb')

#------------------------------------------------------------------------------ 
#--- BINARY FILES --------------------------------------------------------------------------- 

def WindowsStarterFileName():
    """
    Return a file name of the Windows starte: "dhnstarter.exe".
    """
    return 'dhnstarter.exe'

def WindowsStarterFileURL(repo=DefaultRepo()):
    """
    Return a public URL of the "dhnstarter.exe" file, according to given ``repo``.
    When we need to modify the starter code we place it in the repository along with other binaries.
    It will be downloaded by all users and updated.  
    """
    return UpdateLocationURL(repo) + 'windows/' + WindowsStarterFileName()

def getIconLaunchFilename():
    """
    Not used.
    For Windows platforms this should target to executable file to run when clicked on Desktop icon. 
    """
    return os.path.join(io.getExecutableDir(), 'dhnmain.exe')

def getIconLinkFilename():
    """
    A file name for Desktop icon for Windows users.
    """
    return 'Data Haven .NET.lnk'

def IconFilename():
    """
    Application icon file name.
    """
    return 'dhnicon.ico'

def IconsFolderPath():
    """
    A folder name where application icons is stored.

    PREPRO: 
    maybe we better use another name: "media",
    because we may need not only "icons" but also other data files
    """
    return os.path.join(io.getExecutableDir(), 'icons')

def FontsFolderPath():
    """
    A folder name where application "fons" is stored. 
    """
    return os.path.join(io.getExecutableDir(), 'fonts')

def FontImageFile():
    """
    A font to use to print text labels in the GUI.
    """
    return os.path.join(FontsFolderPath(), 'Arial_Narrow.ttf')

#------------------------------------------------------------------------------ 
#--- MERCHANT ID AND LINK ----------------------------------------------------------------------------

def MerchantID():
    """
    Our merchant ID to accept payments from credit cards. 
    """
    # return 'AXA_DH_TESTKEY1'
    return 'AXA_DH_02666084001'

def MerchantURL():
    """
    A URL of the 4CS Bank page to do payments.
    """
    # return 'https://merchants.4csonline.com/DevTranSvcs/tp.aspx'
    return 'https://merchants.4csonline.com/TranSvcs/tp.aspx'

#------------------------------------------------------------------------------ 
#---PORT NUMBERS----------------------------------------------------------------------------

def DefaultSSHPort():
    """
    A default port for ``lib.transport_ssh``.
    """
    return 5022

def IdentityServerPort():
    """
    Identity server stores identity files, it works in that way:
    
        1) anyone can request any stored identity file from any place in the world
        2) anyone can send his identity file over transport_tcp to identity server
        3) identity file must be digitaly signed, server should verify the signature
        4) if signature is fine - server will save (or overwrite existing) the file
        5) server should refuse incorrect or faked identities
        6) someone can store incorrect or faked identities on his own server, but nodes in network will refuse those identities
        7) you can use different ways to transfer your identity file to your own id server - do it by your self
           
    This is a port number of our identity file to receive identity files from users. 
    This should be same for all identity servers everywhere.
    """
    return 6661 # 7773

def IdentityWebPort():
    """
    Our public identity server use standard web port number to publish identity files - 80.
    """
    return 80

def MarketServerWebPort():
    """
    Market server Web port number.
    """
    return 8085

def MoneyServerPort():
    """
    Money server Web port number.
    """
    return 9898

def DefaultTCPPort():
    """
    A default port number for transport_tcp.
    """
    return 7771

def DefaultUDPPort():
    """
    A default port number for transport_udp.
    """
    return 8882

def DefaultDHTUDPPort():
    """
    A default UDP port number for transport_dhtudp.
    Set this to 0 to find a random port - seems more secure at a first view.
    However other ports are still a constant values - not a big deal :-).
    """
    return 9993

def DefaultDHTPort():
    """
    A default UDP port number for DHT network.
    """
    return 14441

def DefaultHTTPPort():
    """
    A default port number for transport_http, not used.
    """
    return 9786

def DefaultWebLogPort():
    """
    A port number for HTTP server to print program logs. 
    """
    return 9999

def DefaultWebTrafficPort():
    """
    A port number for HTTP server to print program packets traffic. 
    """
    return 9997

#------------------------------------------------------------------------------ 
#--- USER FOLDERS ----------------------------------------------------------------------------

def getCustomersFilesDir():
    """
    Alias to get a user donated location from settings. 
    """
    return uconfig('folder.folder-customers').strip()

def getCustomerFilesDir(idurl):
    """
    Alias to get a given customer's files inside our donated location from settings. 
    """
    return os.path.join(getCustomersFilesDir(), nameurl.UrlFilename(idurl))

def getLocalBackupsDir():
    """
    Alias to get local backups folder from settings, see ``BackupsDBDir()``.
    """
    return uconfig('folder.folder-backups').strip()

def getRestoreDir():
    """
    Alias for restore location, see ``RestoreDir()``.
    """
    return uconfig('folder.folder-restore').strip()

def getMessagesDir():
    """
    Alias to get from user config a folder location where messages is stored. 
    """
    return uconfig('folder.folder-messages').strip()

def getReceiptsDir():
    """
    Alias to get from user config a folder location where receipts is stored.
    """
    return uconfig('folder.folder-receipts').strip()

def getTempDir():
    """
    An alias for ``TempDir()``.
    """
    return TempDir()

#------------------------------------------------------------------------------ 
#--- PROXY SERVER OPTIONS ---------------------------------------------------------------------------

def enableProxy(enable=None):
    """
    Enable/disable using of proxy server.
    """
    if enable is None:
        return uconfig('network.network-proxy.network-proxy-enable').lower() == 'true'
    uconfig().set('network.network-proxy.network-proxy-enable', str(enable))
    uconfig().update()

def getProxyHost():
    """
    Return proxy server host from settings. 
    """
    return uconfig('network.network-proxy.network-proxy-host').strip()

def getProxyPort():
    """
    Return proxy server port number from settings. 
    """
    return uconfig('network.network-proxy.network-proxy-port').strip()

def setProxySettings(d):
    """
    Set proxy settings via dictionary, see ``lib.net_misc.detect_proxy_settings`` for more details.
    """
    if d.has_key('host'):
        uconfig().set('network.network-proxy.network-proxy-host', str(d.get('host','')))
    if d.has_key('port'):
        uconfig().set('network.network-proxy.network-proxy-port', str(d.get('port','')))
    if d.has_key('username'):
        uconfig().set('network.network-proxy.network-proxy-username', str(d.get('username','')))
    if d.has_key('password'):
        uconfig().set('network.network-proxy.network-proxy-password', str(d.get('password','')))
    if d.has_key('ssl'):
        uconfig().set('network.network-proxy.network-proxy-ssl', str(d.get('ssl','False')))
    uconfig().update()

def getProxySettingsDict():
    """
    Return a proxy settings from user config in dictionary.
    """
    return {
         'host':        uconfig('network.network-proxy.network-proxy-host').strip(),
         'port':        uconfig('network.network-proxy.network-proxy-port').strip(),
         'username':    uconfig('network.network-proxy.network-proxy-username').strip(),
         'password':    uconfig('network.network-proxy.network-proxy-password').strip(),
         'ssl':         uconfig('network.network-proxy.network-proxy-ssl').strip(), }

def update_proxy_settings():
    """
    Calls ``lib.net_misc.detect_proxy_settings()`` to check current system proxy server settings.
    """
    import net_misc
    net_misc.init()
    if enableProxy():
        if getProxyHost() == '' or getProxyPort() == '':
            d = net_misc.detect_proxy_settings()
            net_misc.set_proxy_settings(d)
            setProxySettings(d)
            enableProxy(d.get('host', '') != '')
            io.log(2, 'settings.update_proxy_settings UPDATED!!!')
        else:
            net_misc.set_proxy_settings(getProxySettingsDict())
        io.log(4, 'settings.update_proxy_settings')
        io.log(4, 'HOST:      ' + net_misc.get_proxy_host())
        io.log(4, 'PORT:      ' + str(net_misc.get_proxy_port()))
        io.log(4, 'USERNAME:  ' + net_misc.get_proxy_username())
        io.log(4, 'PASSWORD:  ' + ('*' * len(net_misc.get_proxy_password())))
        io.log(4, 'SSL:       ' + net_misc.get_proxy_ssl())

#------------------------------------------------------------------------------ 
#---OTHER USER CONFIGURATIONS---------------------------------------------------------------------------

def getBandOutLimit(): 
    """
    Get from user config current outgoing bandwidth limit in kilo bytes per second.
    """
    try:
        return int(uconfig('network.network-send-limit'))
    except:
        return 0

def getBandInLimit():
    """
    Get from user config current incoming bandwidth limit in kilo bytes per second.
    """
    try:
        return int(uconfig('network.network-receive-limit'))
    except:
        return 0

def enableIdServer(enable=None):
    """
    """
    if enable is None:
        return uconfig('id-server.id-server-enable').lower() == 'true'
    uconfig().set('id-server.id-server-enable', str(enable))
    uconfig().update()

def getIdServerHost():
    """
    """
    return uconfig("id-server.id-server-host").strip()

def setIdServerHost(hostname_or_ip):
    """
    """
    uconfig().set("id-server.id-server-host", hostname_or_ip)
    uconfig().update()

def getIdServerWebPort():
    """
    """
    return int(uconfig("id-server.id-server-web-port").strip())

def setIdServerWebPort(web_port):
    """
    """
    uconfig().set("id-server.id-server-web-port", str(web_port))
    uconfig().update()

def getIdServerTCPPort():
    """
    """
    return int(uconfig("id-server.id-server-tcp-port").strip())

def setIdServerTCPPort(tcp_port):
    """
    """
    uconfig().set("id-server.id-server-tcp-port", str(tcp_port))
    uconfig().update()

def getTransportPort(proto):
    """
    Get a port number for some tranports from user config.  
    """
    if proto == 'tcp':
        return getTCPPort()
    if proto == 'udp':
        return getUDPPort()
    raise

def getTCPPort():
    """
    Get a port number for tranport_tcp from user config.  
    """
    return uconfig("transport.transport-tcp.transport-tcp-port")

def setTCPPort(port):
    """
    Set a port number for tranport_tcp in the user config.  
    """
    uconfig().set("transport.transport-tcp.transport-tcp-port", str(port))
    uconfig().update()

def enableTCP(enable=None):
    """
    Switch on/off transport_tcp in the settings or get current state.
    Note : transport_tcp is always available for identites to id server.
    """
    if enable is None:
        return uconfig('transport.transport-tcp.transport-tcp-enable').lower() == 'true'
    uconfig().set('transport.transport-tcp.transport-tcp-enable', str(enable))
    uconfig().update()

def enableTCPsending(enable=None):
    """
    Switch on/off sending over transport_tcp in the settings or get current state.
    """
    if enable is None:
        return uconfig('transport.transport-tcp.transport-tcp-sending-enable').lower() == 'true'
    uconfig().set('transport.transport-tcp.transport-tcp-sending-enable', str(enable))
    uconfig().update()
    
def enableTCPreceiving(enable=None):
    """
    Switch on/off receiving over transport_tcp in the settings or get current state.
    """
    if enable is None:
        return uconfig('transport.transport-tcp.transport-tcp-receiving-enable').lower() == 'true'
    uconfig().set('transport.transport-tcp.transport-tcp-receiving-enable', str(enable))
    uconfig().update()

def getUDPPort():
    """
    Get a port number for tranport_udp from user config.  
    """
    return uconfig("transport.transport-udp.transport-udp-port")

def setUDPPort(port):
    """
    Set a port number for tranport_udp in the user config.  
    """
    uconfig().set("transport.transport-udp.transport-udp-port", str(port))
    uconfig().update()

def enableUDP(enable=None):
    """
    Switch on/off transport_udp in the settings or get current state.
    """
    if enable is None:
        return uconfig('transport.transport-udp.transport-udp-enable').lower() == 'true'
    uconfig().set('transport.transport-udp.transport-udp-enable', str(enable))
    uconfig().update()

def enableDHTUDP(enable=None):
    """
    Switch on/off dhtudp transport in the settings or get current state.
    """
    if enable is None:
        return uconfig('transport.transport-dhtudp.transport-dhtudp-enable').lower() == 'true'
    uconfig().set('transport.transport-dhtudp.transport-dhtudp-enable', str(enable))
    uconfig().update()

def enableDHTUDPsending(enable=None):
    """
    Switch on/off sending over dhtudp in the settings or get current state.
    """
    if enable is None:
        return uconfig('transport.transport-dhtudp.transport-dhtudp-sending-enable').lower() == 'true'
    uconfig().set('transport.transport-dhtudp.transport-dhtudp-sending-enable', str(enable))
    uconfig().update()
    
def enableDHTUDPreceiving(enable=None):
    """
    Switch on/off receiving over dhtudp in the settings or get current state.
    """
    if enable is None:
        return uconfig('transport.transport-dhtudp.transport-dhtudp-receiving-enable').lower() == 'true'
    uconfig().set('transport.transport-dhtudp.transport-dhtudp-receiving-enable', str(enable))
    uconfig().update()

def getDHTPort():
    """
    Get a UDP port number for entangled "DHT" network.  
    """
    return uconfig("transport.transport-dhtudp.transport-dht-port")

def setDHTPort(port):
    """
    Set a UDP port number for entangled "DHT" network.  
    """
    uconfig().set("transport.transport-dhtudp.transport-dht-port", str(port))
    uconfig().update()
    
def getDHTUDPPort():
    """
    Get a main UDP port number for dhtudp transport.  
    """
    return uconfig("transport.transport-dhtudp.transport-dhtudp-port")

def setDHTUDPPort(port):
    """
    Set a main UDP port number for dhtudp transport.  
    """
    uconfig().set("transport.transport-dhtudp.transport-dhtudp-port", str(port))
    uconfig().update()
    
def enableTransport(proto, enable=None):
    """
    Return a current state of given transport or set set a new state.
    """
    key = 'transport.transport-%s.transport-%s-enable' % (proto, proto)
    if uconfig(key) is None:
        return False
    if enable is None:
        return uconfig(key).lower() == 'true'
    uconfig().set(key, str(enable))
    uconfig().update()

def transportIsEnabled(proto):
    """
    Alias for ``enableTransport()``.
    """
    return enableTransport(proto)

def transportIsInstalled(proto):
    """
    This should return True if given transport have been configured and all needed config info is available.
    """
    return True

def transportReceivingIsEnabled(proto):
    """
    Return True if receiving over given transport is switched on. 
    """
    key = 'transport.transport-%s.transport-%s-receiving-enable' % (proto, proto)
    if uconfig(key) is None:
        return False
    return uconfig(key).lower() == 'true'

def transportSendingIsEnabled(proto):
    """
    Return True if sending over given transport is switched on. 
    """
    key = 'transport.transport-%s.transport-%s-sending-enable' % (proto, proto)
    if uconfig(key) is None:
        return False
    return uconfig(key).lower() == 'true'

def getDebugLevelStr(): 
    """
    This is just for checking if it is set, the int() would throw an error.
    """
    return uconfig("logs.debug-level")

def getDebugLevel():
    """
    Return current debug level.
    """
    try:
        res = int(getDebugLevelStr())
    except:
        res = io.DebugLevel
    return res

def setDebugLevel(level):
    """
    Set debug level.
    """
    uconfig().set("logs.debug-level", str(level))
    uconfig().update()

def enableWebStream(enable=None):
    """
    Get current state or enable/disable using of HTTP server to print logs,
    need to restart DHN to take place changes.
    """
    if enable is None:
        return uconfig('logs.stream-enable').lower() == 'true'
    uconfig().set('logs.stream-enable', str(enable))
    uconfig().update()

def enableWebTraffic(enable=None):
    """
    Get current state or enable/disable using of HTTP server to print packets traffic, 
    need to restart DHN to take place changes.
    """
    if enable is None:
        return uconfig('logs.traffic-enable').lower() == 'true'
    uconfig().set('logs.traffic-enable', str(enable))
    uconfig().update()

def getWebStreamPort():
    """
    Get port number of HTTP server to print logs.
    """
    try:
        return int(uconfig('logs.stream-port'))
    except:
        return DefaultWebLogPort()

def getWebTrafficPort():
    """
    Get port number of HTTP server to print packets traffic.
    """
    try:
        return int(uconfig('logs.traffic-port'))
    except:
        return DefaultWebTrafficPort()
    
def enableMemoryProfile(enable=None):
    """
    Get current state or enable/disable using of HTTP server to momory profiling.
    """
    if enable is None:
        return uconfig('logs.memprofile-enable').lower() == 'true'
    uconfig().set('logs.memprofile-enable', str(enable))
    uconfig().update()

def getECC():
    """
    Get ecc map name from current suppliers number. 
    """
    snum = getCentralNumSuppliers()
    if snum < 0:
        return DefaultEccMapName()
    ecc = eccmap.GetEccMapName(snum)
    if isValidECC(ecc):
        return ecc
    else:
        return DefaultEccMapName()

def getECCSuppliersNumbers():
    """
    List of available suppliers numbers.
    """
    return [2, 4, 7, 13]
    # return eccmap.SuppliersNumbers()

def getCentralNumSuppliers():
    """
    Get suppliers number from user settings.
    """
    try:
        return int(uconfig('central-settings.desired-suppliers'))
    except:
        return -1

def getCentralMegabytesNeeded():
    """
    Get needed space in megabytes from user settings.
    """
    return uconfig('central-settings.needed-megabytes')

def getCentralMegabytesDonated():
    """
    Get donated space in megabytes from user settings.
    """
    return uconfig('central-settings.shared-megabytes')

def getEmergencyEmail():
    """
    Get a user email address from settings. 
    User can set that to be able to receive email notification in case of some troubles with his backups.
    """
    return uconfig('emergency.emergency-email')

def getEmergencyPhone():
    """
    Get a user phone number from settings. 
    """
    return uconfig('emergency.emergency-phone')

def getEmergencyFax():
    """
    Get a user fax number from settings. 
    """
    return uconfig('emergency.emergency-fax')

def getEmergencyOther():
    """
    Get a other address info from settings. 
    """
    return uconfig('emergency.emergency-text')

def getEmergency(method):
    """
    Get a given user emergensy method from settings. 
    """
    if method not in getEmergencyMethods():
        return ''
    return uconfig('emergency.emergency-' + method)

def getEmergencyFirstMethod():
    """
    Get a first method to use when need to contact with user. 
    """
    return uconfig('emergency.emergency-first')

def getEmergencySecondMethod():
    """
    Get a second method to use when need to contact with user. 
    """
    return uconfig('emergency.emergency-second')

def getEmergencyMethods():
    """
    Return a list of available methods to contact with user.
    """
    return (
        'email',
        'phone',
        'fax',
        'other',)

def getUpdatesMode():
    """
    User can set different modes to update the DHN software.
    """
    return uconfig('updates.updates-mode')

def getUpdatesModeValues():
    """
    List of available update modes.
    """
    return  (
        'install automatically',
#        'ask before install',
        'only notify',
        'turn off updates', )

def getUpdatesSheduleData():
    """
    Return update schedule from settings.
    """
    return uconfig('updates.updates-shedule')

def setUpdatesSheduleData(raw_shedule):
    """
    Set update schedule in the settings. 
    """
    uconfig().set('updates.updates-shedule', raw_shedule)
    uconfig().update()

def getGeneralBackupsToKeep():
    """
    Return a number of copies to keep for every backed up data.
    The oldest copies (over that amount) will be removed from data base and remote suppliers. 
    """
    try:
        return int(uconfig('general.general-backups'))
    except:
        return 2

def getGeneralLocalBackups():
    """
    Return True if user wish to keep local backups.
    """
    return uconfig('general.general-local-backups-enable').lower() == 'true'

def getGeneralWaitSuppliers():
    """
    Return True if user want to be sure that suppliers are reliable enough before removing the local backups. 
    """
    return uconfig('general.general-wait-suppliers-enable').lower() == 'true'

def getGeneralAutorun():
    """
    Return True if user want to start DHN at system start up.
    """
    return uconfig('general.general-autorun').lower() == 'true'

def getGeneralDisplayMode():
    """
    Get current GUI display mode from settings. 
    """
    return uconfig('general.general-display-mode')

def getGeneralDisplayModeValues():
    """
    List available display modes.
    """
    return ('iconify window', 'normal window', 'maximized window',)

##def getGeneralShowProgress():
##    return uconfig('general.general-show-progress').lower() == 'true'

def getGeneralDesktopShortcut():
    """
    Not used.
    """
    return uconfig('general.general-desktop-shortcut').lower() == 'true'

def getGeneralStartMenuShortcut():
    """
    Not used.
    """
    return uconfig('general.general-start-menu-shortcut').lower() == 'true'

def getBackupBlockSize():
    """
    Get backup block size from settings.
    """
    global _BackupBlockSize
    if _BackupBlockSize is None:
        try:
            _BackupBlockSize = int(uconfig('backup.backup-block-size'))
        except:
            _BackupBlockSize = DefaultBackupBlockSize()
    return _BackupBlockSize

def getBackupMaxBlockSize():
    """
    Get the maximum backup block size from settings.
    """
    global _BackupMaxBlockSize
    if _BackupMaxBlockSize is None:
        try:
            _BackupMaxBlockSize = int(uconfig('backup.backup-max-block-size'))
        except:
            _BackupMaxBlockSize = DefaultBackupMaxBlockSize()
    return _BackupMaxBlockSize

def setBackupBlockSize(block_size):
    """
    Set current backup block size in the memory to have fast access.
    """
    global _BackupBlockSize
    _BackupBlockSize = int(block_size)

def setBackupMaxBlockSize(block_size):
    """
    Set current maximum backup block size in the memory to have fast access.
    """
    global _BackupMaxBlockSize
    _BackupMaxBlockSize = int(block_size)
     
def getPrivateKeySize():
    """
    Return Private Key size from settings, but typically Private Key is generated only once during install stage.
    """
    try:
        return int(uconfig('backup.private-key-size'))
    except:
        return DefaultPrivateKeySize()
    
def setPrivateKeySize(pksize):
    """
    Set Private Key size in the settings.
    """
    uconfig().set('backup.private-key-size', str(pksize))
    uconfig().update()
     
def enableUPNP(enable=None):
    """
    Return True if user want to try to config his router to config port forwarding automatically.
    If ``enable`` is not None - rewrite current value in the settings.
    """
    if enable is None:
        return uconfig('other.upnp-enabled').lower() == 'true'
    uconfig().set('other.upnp-enabled', str(enable))
    uconfig().update()

def getUPNPatStartup():
    """
    User have an option to check UPNP port forwarding every time DHN software starts up.
    But this slow down the start up process.
    """
    return uconfig('other.upnp-at-startup').lower() == 'true'

def setUPNPatStartup(enable):
    """
    Enable or disable checking UPNP devices at start up.
    """
    uconfig().set('other.upnp-at-startup', str(enable))
    uconfig().update()

def isValidECC(ecc):
    """
    Return True if ``ecc`` is a correct ecc map name.
    """
    if ecc in eccmap.EccMapNames():
        return True
    else:
        return False

def getBitCoinServerHost():
    """
    Get a bitcoin server host name from settings. 
    """
    return uconfig('other.bitcoin.bitcoin-host')

def getBitCoinServerPort():
    """
    Get a bitcoin server port number from settings. 
    """
    return uconfig('other.bitcoin.bitcoin-port')

def getBitCoinServerUserName():
    """
    Get a bitcoin server user name from settings. 
    """
    return uconfig('other.bitcoin.bitcoin-username')

def getBitCoinServerPassword():
    """
    Get a bitcoin server user password from settings. 
    """
    return uconfig('other.bitcoin.bitcoin-password')

def getBitCoinServerIsLocal():
    """
    Get a bitcoin server mode from settings: local or remote server. 
    """
    return uconfig('other.bitcoin.bitcoin-server-is-local').lower() == 'true' 

def getBitCoinServerConfigFilename():
    """
    Get a bitcoin server config file name from settings. 
    """
    return uconfig('other.bitcoin.bitcoin-config-filename')

#------------------------------------------------------------------------------ 
#--- INITIALIZE BASE DIR ----------------------------------------------------------------------------

def RenameBaseDir(newdir):
    """
    The idea was to be able to move BitPie.NET data folder to another place if user want that.
    Not used.
    """
    global _BaseDirPath
    olddir = _BaseDirPath
    try:
#        os.renames(_BaseDirPath, newdir) # - this not fit for us.
        import shutil
        shutil.copytree(olddir, newdir)
    except:
        io.exception()
        return False
    _BaseDirPath = newdir
    io.log(2, 'settings.RenameBaseDir  directory was copied,  BaseDir='+BaseDir())
    pathfilename = BaseDirPathFileName()
    io.WriteFile(pathfilename, _BaseDirPath)
    io.log(4, 'settings.RenameBaseDir  BaseDir path was saved to ' + pathfilename)
    logfilename = io.LogFileName
    io.CloseLogFile()
    try:
        io.rmdir_recursive(olddir, True)
        io.log(4, 'settings.RenameBaseDir  old directory was removed: ' + olddir)
    except:
        io.exception()
    io.OpenLogFile(logfilename, True)
    return True

def _initBaseDir(base_dir=None):
    """
    Do some validation and create needed data folders if they are not exist yet.
    You can specify another location for data files.
    """
    global _BaseDirPath
    
    # if we already know the place - we are done
    if base_dir is not None:
        _BaseDirPath = base_dir
        if not os.path.exists(_BaseDirPath):
            io._dirs_make(_BaseDirPath)
        return

    # if we have a file 'basedir.txt' in current folder - take the place from there
    if os.path.isfile(BaseDirPathFileName()):
        path = io.ReadBinaryFile(BaseDirPathFileName())
        if os.path.isdir(path):
            _BaseDirPath = path
            if not os.path.exists(_BaseDirPath):
                io._dirs_make(_BaseDirPath)
            return

    # get the default place for thet machine
    default_path = GetBaseDir()

    # we can use folder ".bitpie" placed on the same level with binary folder:
    # /..
    #   /.bitpie - data files
    #   /bitpie  - binary files
    path1 = str(os.path.abspath(os.path.join(io.getExecutableDir(), '..', '.bitpie')))
    # and default path will have lower priority
    path2 = default_path
    
    # if default path exists - use it
    if os.path.isdir(path2):
        _BaseDirPath = path2
    # but .bitpie on same level will have bigger priority
    if os.path.isdir(path1):
        _BaseDirPath = path1

    # if we did not found "metadata" subfolder - use default path, new copy of DHN
    if not os.path.isdir(MetaDataDir()):
        _BaseDirPath = path2
        if not os.path.exists(_BaseDirPath):
            io._dirs_make(_BaseDirPath)
        return
    
    # if we did not found our key - use default path, new copy of DHN
    if not os.access(KeyFileName(), os.R_OK) or not os.access(KeyFileNameLocation(), os.R_OK):
        _BaseDirPath = path2
        if not os.path.exists(_BaseDirPath):
            io._dirs_make(_BaseDirPath)
        return
    
    # if we did not found our identity - use default path, new copy of DHN
    if not os.access(LocalIdentityFilename(), os.R_OK):
        _BaseDirPath = path2
        if not os.path.exists(_BaseDirPath):
            io._dirs_make(_BaseDirPath)
        return

    # if we did not found our config - use default path, new copy of DHN
    if not os.access(UserConfigFilename(), os.R_OK):
        _BaseDirPath = path2
        if not os.path.exists(_BaseDirPath):
            io._dirs_make(_BaseDirPath)
        return

    # if we did not found our suppliers - use default path, new copy of DHN
    if not os.access(SupplierIDsFilename(), os.R_OK):
        _BaseDirPath = path2
        if not os.path.exists(_BaseDirPath):
            io._dirs_make(_BaseDirPath)
        return

    # if we did not found our customers - use default path, new copy of DHN
    if not os.access(CustomerIDsFilename(), os.R_OK):
        _BaseDirPath = path2
        if not os.path.exists(_BaseDirPath):
            io._dirs_make(_BaseDirPath)
        return

#------------------------------------------------------------------------------ 
#--- USER SETTINGS VALIDATION --------------------------------------------------------------------------- 

def _checkMetaDataDirectory():
    """
    Check that the metadata directory exists.
    """
    if not os.path.exists(MetaDataDir()): 
        io.log(8, 'settings.init want to create metadata folder: ' + MetaDataDir())
        #io._dirs_make(MetaDataDir())
        os.makedirs(MetaDataDir())

def _checkSettings():
    """
    Validate some most important user settings.
    """
    if getCentralNumSuppliers() < 0:
        uconfig().set("central-settings.desired-suppliers", str(DefaultDesiredSuppliers()))

    if getCentralMegabytesDonated() == '':
        uconfig().set("central-settings.shared-megabytes", str(DefaultDonatedMb())+' Mb')
    donatedV, donatedS = diskspace.SplitString(getCentralMegabytesDonated())
    if not donatedS:
        uconfig().set("central-settings.shared-megabytes", str(getCentralMegabytesDonated())+' Mb')

    if getCentralMegabytesNeeded() == '':
        uconfig().set("central-settings.needed-megabytes", str(DefaultNeededMb())+' Mb')
    neededV, neededS = diskspace.SplitString(getCentralMegabytesNeeded())
    if not neededS:
        uconfig().set("central-settings.needed-megabytes", str(getCentralMegabytesNeeded())+' Mb')

    if getDebugLevelStr() == "":
        uconfig().set("logs.debug-level", str(defaultDebugLevel()))

#    if SendTimeOutEmail() == "":
#        uconfig().set("other.emailSendTimeout", str(DefaultSendTimeOutEmail()))

#    if ReceiveTimeOutEmail() == "":
#        uconfig().set("other.emailReceiveTimeout", str(DefaultReceiveTimeOutEmail()))

    if getTCPPort() == "":
        uconfig().set("transport.transport-tcp.transport-tcp-port", str(DefaultTCPPort()))

    if getUDPPort() == "":
        uconfig().set("transport.transport-udp.transport-udp-port", str(DefaultUDPPort()))

    if getDHTUDPPort() == "":
        uconfig().set("transport.transport-dhtudp.transport-dhtudp-port", str(DefaultDHTUDPPort()))

    if getDHTPort() == "":
        uconfig().set("transport.transport-dhtudp.transport-dht-port", str(DefaultDHTPort()))

#    if getSSHPort() == "":
#        uconfig().set("transport.transport-ssh.transport-ssh-port", str(DefaultSSHPort()))

#    if getHTTPPort() == "":
#        uconfig().set("transport.transport-http.transport-http-port", str(DefaultHTTPPort()))

    if getUpdatesMode().strip() not in getUpdatesModeValues():
        uconfig().set('updates.updates-mode', getUpdatesModeValues()[0])

    if getGeneralDisplayMode().strip() not in getGeneralDisplayModeValues():
        uconfig().set('general.general-display-mode', getGeneralDisplayModeValues()[0])

    if getEmergencyFirstMethod() not in getEmergencyMethods():
        uconfig().set('emergency.emergency-first', getEmergencyMethods()[0])

    if getEmergencySecondMethod() not in getEmergencyMethods():
        uconfig().set('emergency.emergency-second', getEmergencyMethods()[1])

    if getEmergencyFirstMethod() == getEmergencySecondMethod():
        methods = list(getEmergencyMethods())
        methods.remove(getEmergencyFirstMethod())
        uconfig().set('emergency.emergency-second', methods[0])

    uconfig().update()


def _checkStaticDirectories():
    """
    Check existance of static data folders.
    """
#    # check that the base directory exists
#    if not os.path.isdir(BaseDir()):
#        io.log(8, 'settings.init want to create folder: ' + BaseDir())
#        io._dirs_make(BaseDir())
#        if io.Windows(): # ??? !!!
#            _initBaseDir()  # ??? !!!

    if not os.path.exists(TempDir()):
        io.log(6, 'settings.init want to create folder: ' + TempDir())
        os.makedirs(TempDir())

    if not os.path.exists(BandwidthInDir()):
        io.log(6, 'settings.init want to create folder: ' + BandwidthInDir())
        os.makedirs(BandwidthInDir())

    if not os.path.exists(BandwidthOutDir()):
        io.log(6, 'settings.init want to create folder: ' + BandwidthOutDir())
        os.makedirs(BandwidthOutDir())

    if not os.path.exists(LogsDir()):
        io.log(6, 'settings.init want to create folder: ' + LogsDir())
        os.makedirs(LogsDir())

    if not os.path.exists(IdentityCacheDir()):
        io.log(6, 'settings.init want to create folder: ' + IdentityCacheDir())
        os.makedirs(IdentityCacheDir())

    if not os.path.exists(SuppliersDir()):
        io.log(6, 'settings.init want to create folder: ' + SuppliersDir())
        os.makedirs(SuppliersDir())

    if not os.path.exists(RatingsDir()):
        io.log(6, 'settings.init want to create folder: ' + RatingsDir())
        os.makedirs(RatingsDir())

    if not os.path.exists(CSpaceDir()):
        io.log(6, 'settings.init want to create folder: ' + CSpaceDir())
        os.makedirs(CSpaceDir())


def _checkCustomDirectories():
    """
    Check existance of user configurable folders.
    """
    if getCustomersFilesDir() == '':
        uconfig().set('folder.folder-customers', os.path.join(BaseDir(), "customers"))
    if not os.path.exists(getCustomersFilesDir()):
        io.log(6, 'settings.init want to create folder: ' + getCustomersFilesDir())
        os.makedirs(getCustomersFilesDir())

    if getLocalBackupsDir() == '':
        uconfig().set('folder.folder-backups', BackupsDBDir())
    if not os.path.exists(getLocalBackupsDir()):
        io.log(6, 'settings.init want to create folder: ' + getLocalBackupsDir())
        os.makedirs(getLocalBackupsDir())

    if getMessagesDir() == '':
        uconfig().set('folder.folder-messages', MessagesDir())
    if not os.path.exists(getMessagesDir()):
        io.log(6, 'settings.init want to create folder: ' + getMessagesDir())
        os.makedirs(getMessagesDir())

    if getReceiptsDir() == '':
        uconfig().set('folder.folder-receipts', ReceiptsDir())
    if not os.path.exists(getReceiptsDir()):
        io.log(6, 'settings.init want to create folder: ' + getReceiptsDir())
        os.makedirs(getReceiptsDir())

    if getRestoreDir() == '':
        uconfig().set('folder.folder-restore', RestoreDir())

#-------------------------------------------------------------------------------

if __name__ == '__main__':
    init()





