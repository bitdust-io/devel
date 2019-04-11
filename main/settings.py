#!/usr/bin/python
# settings.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (settings.py) is part of BitDust Software.
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
.. module:: settings.

I think this is a most used module in the project.
Various parts of the code use this module to get the user settings and global constants.

TODO:
need to move out userconfig stuff from that file
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
import os
import random

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio
from system import deploy

from lib import diskspace

from main import config

#------------------------------------------------------------------------------

_UserConfig = None  # user settings read from file .bitdust/metadata/userconfig
_OverrideDict = {}  # list of values to replace some of user settings
_InitDone = False

#------------------------------------------------------------------------------

_BandwidthLimit = None
_BackupBlockSize = None
_BackupMaxBlockSize = None

#------------------------------------------------------------------------------
#---INIT-----------------------------------------------------------------------
#------------------------------------------------------------------------------


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
    - Load settings from [BitDust data dir]/metadata/userconfig or create a new, default settings
    - Check other "static" folders
    - Validate most important user settings
    - Check custom folders
    """
    lg.out(2, 'settings.init')
    deploy.init_base_dir(base_dir)
    lg.out(2, 'settings.init data location: ' + BaseDir())
    _checkMetaDataDirectory()
    _checkConfigDirectory()
    # if not os.path.isdir(ConfigDir()):
    #     uconfig()
    #     bpio._dir_make(ConfigDir())
    #     convert_configs()
    _setUpDefaultSettings()
    _checkRandomizePortNumbers()
    _createNotExisingSettings()
    _checkStaticDirectories()
    _checkCustomDirectories()

#------------------------------------------------------------------------------
#---USER CONFIG----------------------------------------------------------------
#------------------------------------------------------------------------------

def override(key, value):
    """
    This method can be used to redefine values in UserConfig without writing
    changes on disk.

    Useful when user pass some params via command line - they should override the local settings.
    """
    global _OverrideDict
    lg.out(4, 'settings.override %s=%s' % (key, value))
    _OverrideDict[key] = value


def override_dict(d):
    """
    You can pass a dictionary of settings to override existing user config.
    """
    for key, value in d.items():
        override(key, value)


def convert_key(key):
    # try:
    key = key.replace('.', '/')
    key = key.replace('-enable', '-enabled')
    p = key.split('/')
    if len(p) == 1:
        return key
    if len(p) >= 3 and p[2].startswith(p[1] + '-'):
        p[2] = p[2].replace(p[1] + '-', '')
    if len(p) >= 2 and p[1].startswith(p[0] + '-'):
        p[1] = p[1].replace(p[0] + '-', '')
    if p[0] == 'folder':
        p[0] = 'paths'
    elif p[0] == 'backup':
        p[0] = 'services/backups'
        if p[1] == 'private-key-size':
            p[0] = 'personal'
    elif p[0] == 'general':
        p[0] = 'services/backups'
        if p[1] == 'backups':
            p[1] = 'max-copies'
        elif p[1] == 'local-backups-enabled':
            p[1] = 'keep-local-copies-enabled'
    elif p[0] == 'id-server':
        p[0] = 'services/identity-server'
    elif p[0] == 'identity-server':
        p[0] = 'services/identity-server'
    elif p[0] == 'network':
        p[0] = 'services/network'
        if p[1] == 'dht-port':
            p[0] = 'services/entangled-dht'
            p[1] = 'udp-port'
    elif p[0] == 'storage':
        if p[1] == 'donated':
            p[0] = 'services/supplier'
            p[1] = 'donated-space'
        elif p[1] == 'needed':
            p[0] = 'services/customer'
            p[1] = 'needed-space'
        elif p[1] == 'suppliers':
            p[0] = 'services/customer'
            p[1] = 'suppliers-number'
    elif p[0] == 'transport':
        if p[1] == 'tcp':
            p[0] = 'services'
            p[1] = 'tcp-transport'
            if len(p) > 2:
                if p[2] == 'port':
                    p[1] = 'tcp-connections'
                    p[2] = 'tcp-port'
        elif p[1] == 'udp':
            p[0] = 'services'
            p[1] = 'udp-transport'
            if len(p) > 2:
                if p[2] == 'port':
                    p[1] = 'udp-datagrams'
                    p[2] = 'udp-port'
    key = '/'.join(p)
    return key


"""
Below is a set of global constants.
"""

#------------------------------------------------------------------------------
#--- LOGS --------------------------------------------------------------------
#------------------------------------------------------------------------------


def MainLogFilename():
    """
    A prefix for file names to store main process logs.
    """
    # return os.path.join(LogsDir(), 'bitdust')
    return os.path.join(LogsDir(), 'main.log')


def UpdateLogFilename():
    """
    A place to store logs from update porcess.
    """
    return os.path.join(LogsDir(), 'software_update.log')


def AutomatsLog():
    """
    All state machines logs in the main process is written here.
    """
    return os.path.join(LogsDir(), 'automats.log')


def TransportLog():
    """
    Every x seconds will log stats about current transfers.
    """
    return os.path.join(LogsDir(), 'transport.log')


def ParallelPLogFilename():
    """
    Log from parallelp workers goes here, raid code is executed inside child processes.
    """
    return os.path.join(LogsDir(), 'parallelp.log')


def LocalTesterLogFilename():
    """
    A file name path where bptester.py will write its logs.
    """
    return os.path.join(LogsDir(), 'bptester.log')


#------------------------------------------------------------------------------
#--- CONSTANTS (NUMBERS) ------------------------------------------------------
#------------------------------------------------------------------------------


def MinimumIdentitySources():
    """
    You need to host your identity (piblic key, signature and contacts) at least in one place.
    By default you will use identiy servers hard-coded in BitDust source code.
    But you can start your own identity server and host your identiy there, set those settings:

        services/identity-propagate/known-servers
        services/identity-propagate/preferred-servers
        services/identity-propagate/min-servers
        services/identity-propagate/max-servers

    before you run identiy register process.
    """
    return 1


def MaximumIdentitySources():
    """
    You can host your identity in many places, up to 10 identity servers allowed.
    You do not need to mirror your identity too much, this is just to keep users
    consuming sufficient amount of network resousrces.
    """
    return 10


def DefaultPrivateKeySize():
    """
    User can choose size of his Private Key during install.

    Can be 1024, 2048 or 4096.
    """
    return 2048


def BasePricePerGBmonth():
    """
    Dropbox have a 10$/month for 100-500 GB. So let's have 10$ for 1Tb. this is
    0.01$.

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
    return 10


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

    Higher values should decrease the network speed, but save CPU
    resources.
    """
    return 4.0


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
    PREPRO Should be a function of disk space available.
    """
    return 100


def SendingSpeedLimit():
    """
    This is lower limit during file sending in bytes per second.

    Used to calculate a packet timeout - bigger packets should have longer timeouts.
    If sending below this speed - we count this supplier as failed.
    If we sending too slow to all nodes - it's our problems, not suppliers.
    """
    return 3 * 1024


def ReceivingSpeedLimit():
    return 3 * 1024


def DefaultBandwidthInLimit():
    """
    Incoming bandwidth limit in bytes per second, 0 - unlimited.
    """
    # 1 Mbps = 125000 B/s ~ 122 KB/s
    return 100 * 1250000


def DefaultBandwidthOutLimit():
    """
    Outgoing bandwidth limit in bytes per second, 0 - unlimited.
    """
    # 1 Mbps = 125000 B/s ~ 122 KB/s
    return 100 * 125000


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
    If we need suppliers we will request it every 60 sec.

    Not used right now.
    """
    return 60


def DefaultEccMapName():
    """
    This is a ecc map name used by default.
    Must comply with ``DefaultDesiredSuppliers()``.
    """
    return 'ecc/2x2'


def DefaultDesiredSuppliers():
    """
    A starting number of suppliers for new users.

    Definitely we want to have 64 by default, but we need to have much
    more alive users to do that.

    Must comply with ``DefaultEccMapName()``
    """
    return 2


def DefaultLocaltesterLoop():
    """
    The code in ``p2p.local_tester`` will check the customers files
    periodically.

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


def DefaultDonatedBytes():
    """
    Default donated space value. User can set this at any moment in the settings.
    """
    return 8 * 1024 * 1024 * 1024  # 8 GB


def DefaultNeededBytes():
    """
    Default needed space value. User can set this at any moment in the settings.
    """
    return 256 * 1024 * 1024  # 256 MB


def MinimumDonatedBytes():
    """
    Minimum donated space amount in Megabytes - need to donate at least 2 Mb right now.
    """
    return 64 * 1024 * 1024  # 64 MB


def MinimumNeededBytes():
    return 32 * 1024 * 1024  # 32 MB - minimum 1 MB will be taken from every supplier


def DefaultBackupBlockSize():
    """
    Default block size in bytes, user can set this in settings. We split a
    backed up data into blocks of equal size and.

    perform RAID operation on every block - one by one.
    """
    return 4 * 1024 * 1024  # 4 MB


def DefaultBackupMaxBlockSize():
    """
    The maximum default block size, user can set this in the settings.
    """
    return 16 * 1024 * 1024  # 16 MB is fine


def MinimumBandwidthInLimitKBSec():
    """
    Not used, idea was to limit the minimum bandwidth given to BitDust.
    """
    return 10


def MinimumBandwidthOutLimitKBSec():
    """
    Not used.
    """
    return 10


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

#------------------------------------------------------------------------------
#---CONSTANTS ( STRINGS ) -----------------------------------------------------
#------------------------------------------------------------------------------


def ApplicationName():
    """
    May be one day we decide to do some rebranding - so this can be useful method. :-)
    But this is not used at the moment.
    """
    return 'BitDust'


def ListFilesFormat():
    """
    Argument to ListFiles command to say format to return the data in.

    Can be "Text" or "Compressed". TODO: add "Encrypted" format
    """
    return "Compressed"


def DefaultRepo():
    """
    BitDust software can be updated from different "repositories".

    Right now we have three locations for Windows (testing, development
    and stable) and one for Linux (going to add another one). This is to
    be able to run different code in the network and so be able to test
    new features without any chances to broke the whole network.
    """
    return 'stable'


def DefaultRepoURL(repo='stable'):
    """
    Return a given repository location for Windows.
    """
    if repo == 'stable':
        return 'https://bitdust.io/repo/stable/'
    elif repo == 'devel':
        return 'https://bitdust.io/repo/devel/'
    else:
        return 'https://bitdust.io/repo/test/'


def FilesDigestsFilename():
    """
    This file keeps MD5 checksum of all binary files for Windows release. Every
    Windows repository have such file, this is link for "stable" repo::

        https://bitdust.io/repo/stable/files

    Local copy of this file is also stored in the file::

        .bitdust/bin/files

    Our bitstarter.exe read local copy and than can request a public copy and compare the content.
    If some files were changed or new files added to the repo - it will update the local binaries from repo.
    The idea is to update only modified files when new release will be published.
    """
    return 'files'


def CurrentVersionDigestsFilename():
    """
    This file keeps a MD5 checksum of the file "files", see
    ``FilesDigestsFilename()``. It is also placed in the Windows repository::

        https://bitdust.io/repo/stable/checksum

    If some binary files have been changed - the file "files" also changed and
    its checksum also.
    Locally this is stored in the file::

        .bitdust/bin/checksum

    The software check "checksum" file first and if it is not the same - further download "files".
    """
    return 'checksum'


def LegalUsernameChars():
    """
    A set of correct chars that can be used for user account names.
    """
    return set("abcdefghijklmnopqrstuvwxyz0123456789-_")


def LegalNickNameChars():
    """
    A set of correct chars that can be used for user account names.
    """
    return set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.,{}[]()@!$^&*=+")


#------------------------------------------------------------------------------
#--- FOLDERS ------------------------------------------------------------------
#------------------------------------------------------------------------------

def BaseDir():
    """
    Return current data folder location, also call ``init()`` to be sure all
    things were configured.
    """
    init()
    return deploy.current_base_dir()


def BaseDirPathFileName():
    """
    You can configure BitDust software to use another place for data folder.

    Say you want to store BitDust files on another disk. In the binary
    folder file "appdata" can be created and it will keep the path to
    the data folder.
    """
    return os.path.join(bpio.getExecutableDir(), "appdata")


def DefaultRestoreDir():
    """
    Default location to place restored files and folders.
    """
    return os.path.expanduser('~')


def WindowsBinDir():
    """
    Under Windows executable files is placed in the [BitDust data folder]/bin/.

    This is because Windows Vista and later not allow to write to
    "Program files" folder.
    """
    return os.path.join(BaseDir(), 'bin')


def MetaDataDir():
    """
    Return current location of the "metadata" folder - most important config files is here.
    """
    return os.path.join(BaseDir(), "metadata")


def ConfigDir():
    """
    
    """
    return os.path.join(BaseDir(), 'config')


def TempDir():
    """
    A place for temporary BitDust files, we really need some extra disk space
    to operate.

    TODO: need to add some stuff to control how much extra space we use
    and be able limit that.
    """
    return os.path.join(BaseDir(), "temp")


def IdentityCacheDir():
    """
    See ``lib.identitycache`` module, this is a place to store user's identity
    files to have them on hands.
    """
    return os.path.join(BaseDir(), "identitycache")


def IdentityServerDir():
    """
    
    """
    return os.path.join(BaseDir(), 'identityserver')


def DefaultBackupsDBDir():
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


def DefaultCustomersDir():
    """
    Here will be placed files uploaded by other users.

    Your customers will user your HDD to keep their personal data.
    """
    return os.path.join(BaseDir(), "customers")


def DefaultMessagesDir():
    """
    A default folder to store sent/received messages.
    """
    return os.path.join(BaseDir(), 'messages')


def DefaultMessagesHistoryDir():
    """
    A default folder to store sent/received messages.
    """
    return os.path.join(BaseDir(), 'messages', 'history')


def DefaultReceiptsDir():
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
    """
    return os.path.join(BaseDir(), "bandin")


def BandwidthOutDir():
    """
    Daily stats for outgoing bandwidth is placed in that location.
    """
    return os.path.join(BaseDir(), "bandout")


def RatingsDir():
    """
    In that location BitDust software keeps a rating stats for known users.
    """
    return os.path.join(BaseDir(), 'ratings')


def ContractChainDir():
    """
    """
    return os.path.join(BaseDir(), 'contracts')


def ChatChannelsDir():
    """
    """
    return os.path.join(BaseDir(), 'messages', 'channels')


def ChatHistoryDir():
    """
    """
    return os.path.join(BaseDir(), 'messages', 'history')


def KeyStoreDir():
    """
    """
    return os.path.join(BaseDir(), 'keys')


def BlockchainDir():
    """
    """
    return os.path.join(BaseDir(), 'blockchain')

#------------------------------------------------------------------------------
#--- FILES --------------------------------------------------------------------
#------------------------------------------------------------------------------


def NetworkFileName():
    """
    Location of the file where selected network name is stored.
    It is possible to have multiple independent BitDust networks:
    Main network, Test network, local Docker network, Private networks, etc...
    They are defined in networks.json file and each network must have a unique name.
    NetworkFileName() defines text file location, where network name is stored.
    If that file is not exists, BitDust will try to connect to the main network by default.    
    """
    return os.path.join(MetaDataDir(), "networkname")


def KeyFileName():
    """
    Location of user's Private Key file.
    """
    return os.path.join(MetaDataDir(), "mykeyfile")


def KeyFileNameLocation():
    """
    User can set another location for his Private Key file - he can use USB stick to keep his Key.
    After BitDust stars he can remove the USB stick and keep it in safe place.
    So BitDust will keep user's key in the RAM only - this way you can have more protection for your Key.
    If your machine is stolen - thief can not get your Private key.
    But you must be sure that machine was switched off - the RAM is erased when power is off.
    This file keeps alternative location of your Private Key.
    """
    return KeyFileName() + '_location'


def CustomerIDsFilename():
    """
    IDs for places we store data for, keeps a list of IDURLs of our customers.
    """
    return os.path.join(MetaDataDir(), "customerids")


def CustomersMetaInfoFilename():
    """
    Keeps a list of known ECCMaps and other info of my customers.
    """
    return os.path.join(MetaDataDir(), "customersmetainfo")


def CorrespondentIDsFilename():
    """
    People we get messages from and other stuff not related to backup/restore
    process.
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


def GUIOptionsFilename():
    """
    A small file to keep GUI config.

    For example windows positions and sizes after last execution of the
    program.
    """
    return os.path.join(MetaDataDir(), "guioptions")


def UpdateSheduleFilename():
    """
    Under Windows software update process is made by bitstarter.exe file.
    Obsolete.
    """
    return os.path.join(MetaDataDir(), "updateshedule")


def LocalPortFilename():
    """
    This is a file to keep randomly generated port number for HTTP server to
    provide a Web Access to BitDust main process.

    See module ``web.webcontrol`` for more details. This is old stuff,
    will be removed soon!
    """
    return os.path.join(MetaDataDir(), 'localport')


def LocalWSGIPortFilename():
    """
    This is a file to keep randomly generated port number for Django WSGI
    server.

    This stuff creates a User Interface to the BitDust main process. See
    module ``web.control`` for more details.
    """
    return os.path.join(MetaDataDir(), 'localwsgiport')


def LocalXMLRPCPortFilename():
    """
    
    """
    return os.path.join(MetaDataDir(), 'localxmlrpcport')


def LocalJsonRPCPortFilename():
    """
    
    """
    return os.path.join(MetaDataDir(), 'localjsonrpcport')


def BackupInfoFileNameOld():
    """
    Long time ago backup data base were stored in that file.

    Obsolete, see ``BackupIndexFileName()``..
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
    This is backup data base index file location. This store folder and files
    names and locations with path ID's and some extra info. Located in the
    file.

    .bitdust/metadata/index . Also this file is saved on suppliers in encrypted
    state.

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


def SupplierPath(supplier_idurl, customer_idurl, filename=None):
    """
    A location to given supplier's data.

    If ``filename`` is provided - return a full path to that file.
    Currently those data are stored for every supplier:

        - "connected" : date and time when this man become our suppler
        - "disconnected" : date and time when this suppler was fired
        - "listfiles" : a list of our local files stored on his machine
    """
    from userid import global_id
    from lib import nameurl
    customer = global_id.UrlToGlobalID(customer_idurl)
    if filename is not None:
        return os.path.join(SuppliersDir(), customer, nameurl.UrlFilename(supplier_idurl), filename)
    return os.path.join(SuppliersDir(), customer, nameurl.UrlFilename(supplier_idurl))


def SupplierListFilesFilename(supplier_idurl, customer_idurl):
    """
    Return a "listfiles" file location for given supplier.
    """
    return os.path.join(SupplierPath(supplier_idurl, customer_idurl), 'listfiles')


def SupplierServiceFilename(supplier_idurl, customer_idurl):
    """
    Return a "service" file location for given supplier.
    """
    return os.path.join(SupplierPath(supplier_idurl, customer_idurl), 'service')


def RepoFile():
    """
    A file to store info about currently used repository.
    """
    return os.path.join(MetaDataDir(), 'repo')


def VersionFile():
    """
    A place for local copy of "checksum" file, see
    ``CurrentVersionDigestsFilename()``.
    """
    return os.path.join(MetaDataDir(), 'checksum')


def InfoFile():
    """
    A place for local copy of "files" file, see ``FilesDigestsFilename()``.
    """
    # return os.path.join(MetaDataDir(), 'files')
    return os.path.join(bpio.getExecutableDir(), 'files')


def RevisionNumberFile():
    """
    We keep track of Subversion revision number and store it in the binary
    folder. This is a sort of "product version". Probably not very best idea,
    we need to use a widely used software version format.

    This is not used anymore - switched to ``VersionNumberFile()``.
    """
    return os.path.join(bpio.getExecutableDir(), 'revnum')


def VersionNumberFile():
    """
    
    """
    return os.path.join(bpio.getExecutableDir(), 'version')


def CheckSumFile():
    """
    
    """
    return os.path.join(bpio.getExecutableDir(), 'checksum')


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
    This file keeps our current BitDust balance - two values:
        - transferable funds
        - not transferable funds
    """
    return os.path.join(MetaDataDir(), 'balance')


def CertificateFiles():
    """
    The idea is to have a global certificate for BitDust server, just like
    https works.
    """
    return [os.path.join(MetaDataDir(), 'bitdust.cer'),
            os.path.join('.', 'bitdust.cer'),
            os.path.join(bpio.getExecutableDir(), 'bitdust.cer'), ]


def DHTDBFile():
    """
    """
    return os.path.join(MetaDataDir(), 'dhtdb')


def FTPServerCredentialsFile():
    """
    """
    return os.path.join(MetaDataDir(), 'ftpcredentials')

#------------------------------------------------------------------------------
#--- BINARY FILES -------------------------------------------------------------
#------------------------------------------------------------------------------


def WindowsStarterFileName():
    """
    Return a file name of the Windows starter: "bitstarter.exe".
    Obsolete.
    """
    return 'bitstarter.exe'


def WindowsMainScriptFileName():
    """
    Return a file name of the root Windows executable script : "BitDustNode.exe".
    """
    return 'BitDustNode.exe'


def getIconLaunchFilename():
    """
    Not used.

    For Windows platforms this should target to executable file to run
    when clicked on Desktop icon.
    """
    return os.path.join(bpio.getExecutableDir(), 'bitdustnode.exe')


def getIconLinkFilename():
    """
    A file name for Desktop icon for Windows users.
    """
    return 'Data Haven .NET.lnk'


def IconFilename():
    """
    Application icon file name.
    """
    return 'desktop.ico'


def StyleSheetsFilename():
    """
    
    """
    return 'styles.css'


def StyleSheetsPath():
    """
    
    """
    return os.path.join(bpio.getExecutableDir(), 'html', StyleSheetsFilename())


def IconsFolderPath():
    """
    A folder name where application icons is stored.

    PREPRO: maybe we better use another name: "media", because we may
    need not only "icons" but also other data files
    """
    return os.path.join(bpio.getExecutableDir(), 'icons')


def FontsFolderPath():
    """
    A folder name where application "fons" is stored.
    """
    return os.path.join(bpio.getExecutableDir(), 'fonts')


def FontImageFile():
    """
    A font to use to print text labels in the GUI.
    """
    return os.path.join(FontsFolderPath(), 'Arial_Narrow.ttf')

#------------------------------------------------------------------------------
#---PORT NUMBERS---------------------------------------------------------------
#------------------------------------------------------------------------------


def DefaultXMLRPCPort():
    """
    Only Local! Never expose to outside of localhost.
    Obsolete. To be removed.
    """
    return 8082


def DefaultJsonRPCPort():
    """
    Only Local! Never expose to outside of localhost.
    """
    return 8083


def DefaultRESTHTTPPort():
    """
    Only Local! Never expose to outside of localhost.
    """
    return 8180


def DefaultFTPPort():
    """
    Only Local! Never expose to outside of localhost.
    """
    return 8021


def IdentityServerPort():
    """
    Identity server stores identity files, it works in that way:

        1) anyone can request any stored identity file from any place in the world
        2) anyone can send his identity file over transport_tcp to identity server
        3) identity file must be digitaly signed, server should verify the signature
        4) if signature is fine - server will save (or overwrite existing) the file
        5) server should refuse incorrect or faked identities
        6) someone can store incorrect or faked identities on his own server, but nodes in network will refuse those identities
        7) you can use different ways to transfer your identity file to your own id server - do it by your own.

    This is a port number of our identity file to receive identity files from users.
    Must accept external incoming connections.
    """
    return 6661  # 7773


def IdentityWebPort():
    """
    Our public identity servers use standard web port number to publish
    identity files.
    Must accept external incoming connections.
    Normally you would add port 8084 to port 80 routing using Apache2 or Nginx web server.
    """
    return 8084


def DefaultTCPPort():
    """
    A default port number for transport_tcp.
    Must accept external incoming connections.
    """
    return 7771


def DefaultUDPPort():
    """
    A default port number for transport_udp.
    Must accept external incoming connections.
    """
    return 8882


def DefaultDHTPort():
    """
    A default UDP port number for DHT network.
    Must accept external incoming connections.
    """
    return 14441


def DefaultHTTPPort():
    """
    A default port number for transport_http.
    Must accept external incoming connections.
    """
    return 9993


def DefaultWebLogPort():
    """
    A port number for HTTP server to print program logs.
    Only Local! Never expose to outside of localhost.
    """
    return 9999


def DefaultWebTrafficPort():
    """
    A port number for HTTP server to print program packets traffic.
    Only Local! Never expose to outside of localhost.
    """
    return 9997

#------------------------------------------------------------------------------
#--- USER FOLDERS -------------------------------------------------------------
#------------------------------------------------------------------------------


def getCustomersFilesDir():
    """
    Alias to get a user donated location from settings.
    """
    return config.conf().getString('paths/customers', default=DefaultCustomersDir()).strip()


def getCustomerFilesDir(idurl):
    """
    Alias to get a given customer's files inside our donated location from
    settings.
    """
    from userid import global_id
    return os.path.join(getCustomersFilesDir(), global_id.UrlToGlobalID(idurl))


def getLocalBackupsDir():
    """
    Alias to get local backups folder from settings, see
    ``DefaultBackupsDBDir()``.
    """
    return config.conf().getString('paths/backups', default=DefaultBackupsDBDir()).strip()


def getRestoreDir():
    """
    Alias for restore location, see ``DefaultRestoreDir()``.
    """
    return config.conf().getString('paths/restore', default=DefaultRestoreDir()).strip()


def getReceiptsDir():
    """
    Alias to get from user config a folder location where receipts is stored.
    """
    return config.conf().getString('paths/receipts', default=DefaultReceiptsDir()).strip()


def getTempDir():
    """
    An alias for ``TempDir()``.
    """
    return TempDir()

#------------------------------------------------------------------------------
#--- OS PROXY SERVER OPTIONS --------------------------------------------------
#------------------------------------------------------------------------------


def enableLocalProxy(enable=None):
    """
    Enable/disable using of proxy server.
    """
    if enable is None:
        return config.conf().getBool('services/network/proxy/enabled')
    config.conf().setData('services/network/proxy/enabled', str(enable))


def getProxyHost():
    """
    Return proxy server host from settings.
    """
    return config.conf().getData('services/network/proxy/host').strip()


def getProxyPort():
    """
    Return proxy server port number from settings.
    """
    return config.conf().getData('services/network/proxy/port').strip()


def setProxySettings(d):
    """
    Set proxy settings via dictionary, see
    ``lib.net_misc.detect_proxy_settings`` for more details.
    """
    if 'host' in d:
        config.conf().setData('services/network/proxy/host', str(d.get('host', '')))
    if 'port' in d:
        config.conf().setData('services/network/proxy/port', str(d.get('port', '')))
    if 'username' in d:
        config.conf().setData('services/network/proxy.network-proxy-username', str(d.get('username', '')))
    if 'password' in d:
        config.conf().setData('services/network/proxy/password', str(d.get('password', '')))
    if 'ssl' in d:
        config.conf().setData('services/network/proxy/ssl', str(d.get('ssl', 'False')))


def getProxySettingsDict():
    """
    Return a proxy settings from user config in dictionary.
    """
    return {
        'host': config.conf().getData('services/network/proxy/host').strip(),
        'port': config.conf().getData('services/network/proxy/port').strip(),
        'username': config.conf().getData('services/network/proxy/username').strip(),
        'password': config.conf().getData('services/network/proxy/password').strip(),
        'ssl': config.conf().getData('services/network/proxy/ssl').strip(), }


def update_proxy_settings():
    """
    Calls ``lib.net_misc.detect_proxy_settings()`` to check current system
    proxy server settings.
    """
    from lib import net_misc
    net_misc.init()
    if enableLocalProxy():
        if getProxyHost() == '' or getProxyPort() == '':
            d = net_misc.detect_proxy_settings()
            # setProxySettings(d)
            # enableLocalProxy(d.get('host', '') != '')
            lg.out(2, 'settings.update_proxy_settings : loaded from ENVIRONMENT')
        else:
            d = getProxySettingsDict()
            lg.out(2, 'settings.update_proxy_settings : loaded from settings')
        net_misc.set_proxy_settings(d)
        lg.out(2, '    HOST:      ' + net_misc.get_proxy_host())
        lg.out(2, '    PORT:      ' + str(net_misc.get_proxy_port()))
        lg.out(2, '    USERNAME:  ' + net_misc.get_proxy_username())
        lg.out(2, '    PASSWORD:  ' + ('*' * len(net_misc.get_proxy_password())))
        lg.out(2, '    SSL:       ' + net_misc.get_proxy_ssl())

#------------------------------------------------------------------------------
#---OTHER USER CONFIGURATIONS--------------------------------------------------
#------------------------------------------------------------------------------


def getBandOutLimit():
    """
    This is a current outgoing bandwidth limit in bytes per second.
    """
    return config.conf().getInt('services/network/send-limit', DefaultBandwidthOutLimit())


def getBandInLimit():
    """
    This is a current incoming bandwidth limit in bytes per second.
    """
    return config.conf().getInt('services/network/receive-limit', DefaultBandwidthInLimit())


def enableIdServer(enable=None):
    """
    """
    if enable is None:
        return config.conf().getBool('services/identity-server/enabled')
    config.conf().setData('services/identity-server/enabled', str(enable))


def enableRESTHTTPServer(enable=None):
    """
    """
    if enable is None:
        return config.conf().getBool('interface/api/rest-http-enabled')
    config.conf().setData('interface/api/rest-http-enabled', str(enable))


def enableJsonRPCServer(enable=None):
    """
    """
    if enable is None:
        return config.conf().getBool('interface/api/json-rpc-enabled')
    config.conf().setData('interface/api/json-rpc-enabled', str(enable))


def enableFTPServer(enable=None):
    """
    """
    if enable is None:
        return config.conf().getBool('interface/ftp/enabled')
    config.conf().setData('interface/ftp/enabled', str(enable))


def getIdServerHost():
    """
    """
    return config.conf().getData("services/identity-server/host").strip()


def setIdServerHost(hostname_or_ip):
    """
    """
    return config.conf().setData("services/identity-server/host", hostname_or_ip)


def getIdServerWebPort():
    """
    """
    return config.conf().getInt("services/identity-server/web-port", IdentityWebPort())


def setIdServerWebPort(web_port):
    """
    """
    return config.conf().setInt("services/identity-server/web-port", web_port)


def getIdServerTCPPort():
    """
    """
    return config.conf().getInt("services/identity-server/tcp-port", IdentityServerPort())


def setIdServerTCPPort(tcp_port):
    """
    """
    return config.conf().setInt("services/identity-server/tcp-port", tcp_port)


def getRESTHTTPServerPort():
    """
    """
    return config.conf().getInt('interface/api/rest-http-port', DefaultRESTHTTPPort())


def setRESTHTTPServerPort(rest_http_port):
    """
    """
    return config.conf().setInt("interface/api/rest-http-port", rest_http_port)


def getJsonRPCServerPort():
    """
    """
    return config.conf().getInt('interface/api/json-rpc-port', DefaultJsonRPCPort())


def setJsonRPCServerPort(json_rpc_port):
    """
    """
    return config.conf().setInt("interface/api/json-rpc-port", json_rpc_port)


def getFTPServerPort():
    """
    """
    return config.conf().getInt('interface/ftp/port', DefaultFTPPort())


def setFTPServerPort(ftp_port):
    """
    """
    return config.conf().setInt("interface/ftp/port", ftp_port)


def getTransportPort(proto):
    """
    Get a port number for some tranports from user config.
    """
    if proto == 'tcp':
        return getTCPPort()
    if proto == 'udp':
        return getUDPPort()
    if proto == 'http':
        return getHTTPPort()
    raise


def enableTCP(enable=None):
    """
    Switch on/off transport_tcp in the settings or get current state.

    Note : transport_tcp is always available for identites to id server.
    """
    if enable is None:
        return config.conf().getBool('services/tcp-transport/enabled')
    config.conf().setData('services/tcp-transport/enabled', str(enable))


def enableTCPsending(enable=None):
    """
    Switch on/off sending over transport_tcp in the settings or get current
    state.
    """
    if enable is None:
        return config.conf().getBool('services/tcp-transport/sending-enabled')
    config.conf().setData('services/tcp-transport/sending-enabled', str(enable))


def enableTCPreceiving(enable=None):
    """
    Switch on/off receiving over transport_tcp in the settings or get current
    state.
    """
    if enable is None:
        return config.conf().getBool('services/tcp-transport/receiving-enabled')
    config.conf().setData('services/tcp-transport/receiving-enabled', str(enable))


def getTCPPort():
    """
    Get a port number for tranport_tcp from user config.
    """
    return config.conf().getInt("services/tcp-connections/tcp-port", DefaultTCPPort())


def setTCPPort(port):
    """
    Set a port number for tranport_tcp in the user config.
    """
    config.conf().setData("services/tcp-connections/tcp-port", str(port))


def enableUDP(enable=None):
    """
    Switch on/off transport_udp in the settings or get current state.
    """
    if enable is None:
        return config.conf().getBool('services/udp-transport/enabled')
    config.conf().setData('services/udp-transport/enabled', str(enable))


def enableUDPsending(enable=None):
    """
    Switch on/off sending over udp in the settings or get current state.
    """
    if enable is None:
        return config.conf().getBool('services/udp-transport/sending-enabled')
    config.conf().setData('services/udp-transport/sending-enabled', str(enable))


def enableUDPreceiving(enable=None):
    """
    Switch on/off receiving over udp in the settings or get current state.
    """
    if enable is None:
        return config.conf().getBool('services/udp-transport/receiving-enabled')
    config.conf().setData('services/udp-transport/receiving-enabled', str(enable))


def getUDPPort():
    """
    Get a port number for tranport_udp from user config.
    """
    return config.conf().getInt("services/udp-datagrams/udp-port", DefaultUDPPort())


def setUDPPort(port):
    """
    Set a port number for tranport_udp in the user config.
    """
    config.conf().setData("services/udp-datagrams/udp-port", str(port))


def getDHTPort():
    """
    Get a UDP port number for entangled "DHT" network.
    """
    return config.conf().getInt("services/entangled-dht/udp-port", DefaultDHTPort())


def enablePROXY(enable=None):
    """
    Switch on/off transport_proxy in the settings or get its current state.
    """
    if enable is None:
        return config.conf().getBool('services/proxy-transport/enabled')
    config.conf().setData('services/proxy-transport/enabled', str(enable))


def enablePROXYsending(enable=None):
    """
    Switch on/off sending over proxy transport in the settings or get current
    state.
    """
    if enable is None:
        return config.conf().getBool('services/proxy-transport/sending-enabled')
    config.conf().setData('services/proxy-transport/sending-enabled', str(enable))


def enablePROXYreceiving(enable=None):
    """
    Switch on/off receiving over proxy transport in the settings or get current
    state.
    """
    if enable is None:
        return config.conf().getBool('services/proxy-transport/receiving-enabled')
    config.conf().setData('services/proxy-transport/receiving-enabled', str(enable))


def enableHTTP(enable=None):
    """
    Switch on/off transport_http in the settings or get current state.
    """
    if enable is None:
        return config.conf().getBool('services/http-transport/enabled')
    config.conf().setData('services/http-transport/enabled', str(enable))


def enableHTTPsending(enable=None):
    """
    Switch on/off sending over transport_http in the settings or get current
    state.
    """
    if enable is None:
        return config.conf().getBool('services/http-transport/sending-enabled')
    config.conf().setData('services/http-transport/sending-enabled', str(enable))


def enableHTTPreceiving(enable=None):
    """
    Switch on/off receiving over transport_http in the settings or get current
    state.
    """
    if enable is None:
        return config.conf().getBool('services/http-transport/receiving-enabled')
    config.conf().setData('services/http-transport/receiving-enabled', str(enable))


def getHTTPPort():
    """
    Get a port number for tranport_http from user config.
    """
    return config.conf().getInt("services/http-connections/http-port", DefaultTCPPort())


def setHTTPPort(port):
    """
    Set a port number for tranport_http in the user config.
    """
    config.conf().setData("services/http-connections/http-port", str(port))


def getTransportPriority(proto):
    """
    """
    return config.conf().getInt('services/%s-transport/priority' % proto, 1)


def setTransportPriority(proto, value):
    """
    """
    return config.conf().setInt('services/%s-transport/priority' % proto, value)


def setDHTPort(port):
    """
    Set a UDP port number for entangled "DHT" network.
    """
    config.conf().setData("services/entangled-dht/udp-port", str(port))


def enableTransport(proto, enable=None):
    """
    Return a current state of given network transport or set a new state.
    """
    # key = 'transport.transport-%s.transport-%s-enable' % (proto, proto)
    key = 'services/%s-transport/enabled' % proto
    if config.conf().getData(key) is None:
        return False
    if enable is None:
        return config.conf().getBool(key)
    config.conf().setData(key, str(enable))


def transportIsEnabled(proto):
    """
    Alias for ``enableTransport()``.
    """
    return enableTransport(proto)


def transportIsInstalled(proto):
    """
    This should return True if given transport have been configured and all
    needed config info is available.
    """
    return True


def transportReceivingIsEnabled(proto):
    """
    Return True if receiving over given transport is switched on.
    """
    # key = 'transport.transport-%s.transport-%s-receiving-enable' % (proto, proto)
    key = 'services/%s-transport/receiving-enabled' % proto
    if config.conf().getData(key) is None:
        return False
    return config.conf().getBool(key)


def transportSendingIsEnabled(proto):
    """
    Return True if sending over given transport is switched on.
    """
    # key = 'transport.transport-%s.transport-%s-sending-enable' % (proto, proto)
    key = 'services/%s-transport/sending-enabled' % proto
    if config.conf().getData(key) is None:
        return False
    return config.conf().getBool(key)


def enableProxyServer(enable=None):
    """
    """
    if enable is None:
        return config.conf().getBool('services/proxy-server/enabled')
    config.conf().setData('services/proxy-server/enabled', str(enable))


def getDebugLevelStr():
    """
    This is just for checking if it is set, the int() would throw an error.
    """
    return config.conf().getData("logs/debug-level")


def getDebugLevel():
    """
    Return current debug level.
    """
    return config.conf().getInt('logs/debug-level', lg._GlobalDebugLevel)


def setDebugLevel(level):
    """
    Set debug level.
    """
    config.conf().setData("logs/debug-level", str(level))


def enableWebStream(enable=None):
    """
    Get current state or enable/disable using of HTTP server to print logs,
    need to restart BitDust to take place changes.
    """
    if enable is None:
        return config.conf().getBool('logs/stream-enabled')
    config.conf().setData('logs/stream-enabled', str(enable))


def enableWebTraffic(enable=None):
    """
    Get current state or enable/disable using of HTTP server to print packets
    traffic, need to restart BitDust to take place changes.
    """
    if enable is None:
        return config.conf().getBool('logs/traffic-enabled')
    config.conf().setData('logs/traffic-enabled', str(enable))


def getWebStreamPort():
    """
    Get port number of HTTP server to print logs.
    """
    return config.conf().getInt('logs/stream-port', DefaultWebLogPort())


def getWebTrafficPort():
    """
    Get port number of HTTP server to print packets traffic.
    """
    return config.conf().getInt('logs/traffic-port')


def enableMemoryProfile(enable=None):
    """
    Get current state or enable/disable using of HTTP server to momory
    profiling.
    """
    if enable is None:
        return config.conf().getBool('logs/memprofile-enabled')
    return config.conf().setData('logs/memprofile-enabled', str(enable))


def getECCSuppliersNumbers():
    """
    List of available suppliers numbers.
    """
    return [2, 4, 7, 13]
    # return eccmap.SuppliersNumbers()


def getSuppliersNumberDesired():
    """
    Get suppliers number from user settings.
    """
    return config.conf().getInt('services/customer/suppliers-number', -1)


def getNeededString():
    """
    Get needed space in megabytes from user settings.
    """
    return config.conf().getData('services/customer/needed-space')


def getNeededBytes():
    """
    """
    return diskspace.GetBytesFromString(getNeededString())


def getDonatedString():
    """
    Get donated space in megabytes from user settings.
    """
    return config.conf().getData('services/supplier/donated-space')


def getDonatedBytes():
    """
    """
    return diskspace.GetBytesFromString(getDonatedString())


def getEmergencyEmail():
    """
    Get a user email address from settings.

    User can set that to be able to receive email notification in case
    of some troubles with his backups.
    """
    # return config.conf().getData('emergency/email')
    # TODO: remove this after get rid of webcontrol.py
    return ''


def getEmergencyPhone():
    """
    Get a user phone number from settings.
    """
    # return config.conf().getData('emergency/phone')
    # TODO: remove this after get rid of webcontrol.py
    return ''


def getEmergencyFax():
    """
    Get a user fax number from settings.
    """
    # return config.conf().getData('emergency/fax')
    # TODO: remove this after get rid of webcontrol.py
    return ''


def getEmergencyOther():
    """
    Get a other address info from settings.
    """
    # return config.conf().getData('emergency/text')
    # TODO: remove this after get rid of webcontrol.py
    return ''


def getEmergency(method):
    """
    Get a given user emergensy method from settings.
    """
    # if method not in getEmergencyMethods():
    #     return ''
    # return config.conf().getData('emergency/' + method)
    # TODO: remove this after get rid of webcontrol.py
    return ''


def getEmergencyFirstMethod():
    """
    Get a first method to use when need to contact with user.
    """
    # return config.conf().getData('emergency/first')
    # TODO: remove this after get rid of webcontrol.py
    return ''


def getEmergencySecondMethod():
    """
    Get a second method to use when need to contact with user.
    """
    # return config.conf().getData('emergency/second')
    # TODO: remove this after get rid of webcontrol.py
    return ''


def getEmergencyMethods():
    """
    Return a list of available methods to contact with user.
    """
    # TODO: remove this after get rid of webcontrol.py
    return (
        'email',
        'phone',
        'fax',
        'other',)


def getNickName():
    """
    """
    return config.conf().getData('personal/nickname')


def setNickName(nickname):
    """
    """
    config.conf().setData('personal/nickname', nickname.strip())


def getEmail():
    """
    """
    return config.conf().getData('personal/email')


def setEmail(nickname):
    """
    """
    config.conf().setData('personal/email', nickname.strip())


def getUpdatesMode():
    """
    User can set different modes to update the BitDust software.
    """
    # TODO: remove this after get rid of webcontrol.py
    return 'turn off updates'


def setUpdatesMode(mode):
    """
    """
    # TODO: remove this after get rid of webcontrol.py


def getUpdatesModeValues():
    """
    List of available update modes.
    """
    # TODO: remove this after get rid of webcontrol.py
    return (
        'install automatically',
        'only notify',
        'turn off updates', )


def getUpdatesSheduleData():
    """
    Return update schedule from settings.
    """
    return config.conf().getData('updates/shedule')


def setUpdatesSheduleData(raw_shedule):
    """
    Set update schedule in the settings.
    """
    config.conf().setData('updates/shedule', raw_shedule)


def getBackupsMaxCopies():
    """
    Return a number of copies to keep for every backed up data.

    The oldest copies (over that amount) will be removed from data base
    and remote suppliers.
    """
    return config.conf().getInt('services/backups/max-copies', 2)


def getBackupsKeepLocalCopies():
    """
    Return True if user wish to keep local backups.
    """
    return config.conf().getBool('services/backups/keep-local-copies-enabled')


def getGeneralWaitSuppliers():
    """
    Return True if user want to be sure that suppliers are reliable enough
    before removing the local backups.
    """
    return config.conf().getBool('services/backups/wait-suppliers-enabled')


def getBackupBlockSizeStr():
    """
    """
    return config.conf().getData('services/backups/block-size')


def getBackupBlockSize():
    """
    Get backup block size from settings.
    """
    return diskspace.GetBytesFromString(getBackupBlockSizeStr())


def getBackupMaxBlockSizeStr():
    """
    """
    return config.conf().getData('services/backups/max-block-size')


def getBackupMaxBlockSize():
    """
    Get the maximum backup block size from settings.
    """
    return diskspace.GetBytesFromString(getBackupMaxBlockSizeStr())


def setBackupBlockSize(block_size):
    """
    Set current backup block size in the memory to have fast access.
    """
    return config.conf().setData('services/backups/block-size', diskspace.MakeStringFromBytes(block_size))


def setBackupMaxBlockSize(block_size):
    """
    Set current maximum backup block size in the memory to have fast access.
    """
    return config.conf().setData('services/backups/max-block-size', diskspace.MakeStringFromBytes(block_size))


def getPrivateKeySize():
    """
    Returns your preferred Private Key size from settings.
    Your Master Private Key is generated only once during install stage.
    Other Private Keys also will be generated when necessary:
    for customer-supplier interactions, for private messages, for blockchain service, etc.
    """
    return config.conf().getInt('personal/private-key-size')


def setPrivateKeySize(pksize):
    """
    Set Private Key size in the settings.
    """
    config.conf().setInt('personal/private-key-size', pksize)


def enableUPNP(enable=None):
    """
    Return True if user want to try to config his router to config port
    forwarding automatically.

    If ``enable`` is not None - rewrite current value in the settings.
    """
    if enable is None:
        return config.conf().getBool('services/tcp-connections/upnp-enabled')
    config.conf().setData('services/tcp-connections/upnp-enabled', str(enable))


def enableService(svc_name, enable=None):
    if enable is None:
        return config.conf().getBool('services/%s/enabled' % svc_name)
    config.conf().setBool('services/%s/enabled' % svc_name, enable)


def enableBroadcastRouting(enable=None):
    if enable is None:
        return config.conf().getBool('services/broadcasting/routing-enabled')
    config.conf().setBool('services/broadcasting/routing-enabled', enable)

#------------------------------------------------------------------------------
#--- INITIALIZE BASE DIR ------------------------------------------------------
#------------------------------------------------------------------------------


def RenameBaseDir(newdir):
    """
    The idea was to be able to move BitDust data folder to another place if
    user want that.

    Not used.
    """
    olddir = deploy.current_base_dir()
    try:
        import shutil
        shutil.copytree(olddir, newdir)
    except:
        lg.exc()
        return False
    deploy.set_base_dir(newdir)
    lg.out(2, 'settings.RenameBaseDir  directory was copied,  BaseDir=' + BaseDir())
    pathfilename = BaseDirPathFileName()
    bpio.WriteTextFile(pathfilename, deploy.current_base_dir())
    lg.out(4, 'settings.RenameBaseDir  BaseDir path was saved to ' + pathfilename)
    logfilename = lg.log_filename()
    lg.close_log_file()
    try:
        bpio.rmdir_recursive(olddir, True)
        lg.out(4, 'settings.RenameBaseDir  old directory was removed: ' + olddir)
    except:
        lg.exc()
    lg.open_log_file(logfilename, True)
    return True

#------------------------------------------------------------------------------
#--- USER SETTINGS VALIDATION -------------------------------------------------
#------------------------------------------------------------------------------


def _checkMetaDataDirectory():
    """
    Check that the __metadata__ directory exists.
    """
    if os.path.isfile(MetaDataDir()):
        raise Exception('file already exist:' + MetaDataDir())
    if not os.path.exists(MetaDataDir()):
        lg.out(2, 'settings._checkMetaDataDirectory want to create "metadata" folder in : ' + MetaDataDir())
        bpio._dirs_make(MetaDataDir())
        return
    lg.out(4, 'settings._checkMetaDataDirectory OK , folder already exist: ' + MetaDataDir())


def _checkConfigDirectory():
    """
    Check that the __config__ directory exists.
    """
    if os.path.isfile(ConfigDir()):
        raise Exception('file already exist:' + ConfigDir())
    if not os.path.exists(ConfigDir()):
        lg.out(2, 'settings._checkConfigDirectory want to create "config" folder in : ' + ConfigDir())
        bpio._dir_make(ConfigDir())
    else:
        lg.out(4, 'settings._checkConfigDirectory OK , folder already exist: ' + ConfigDir())
    config.init(ConfigDir())


def _setUpDefaultSettings():
    """
    Configure default values for all settings.

    Every option must have a default value, howerver there are exceptions possible :-)
    """
    config.conf().setDefaultValue('interface/api/json-rpc-enabled', 'true')
    config.conf().setDefaultValue('interface/api/json-rpc-port', DefaultJsonRPCPort())

    config.conf().setDefaultValue('interface/api/rest-http-enabled', 'true')
    config.conf().setDefaultValue('interface/api/rest-http-port', DefaultRESTHTTPPort())

    config.conf().setDefaultValue('interface/ftp/enabled', 'true')
    config.conf().setDefaultValue('interface/ftp/port', DefaultFTPPort())

    config.conf().setDefaultValue('logs/debug-level', defaultDebugLevel())
    config.conf().setDefaultValue('logs/memdebug-enabled', 'false')
    config.conf().setDefaultValue('logs/memdebug-port', '9996')
    config.conf().setDefaultValue('logs/memprofile-enabled', 'false')
    config.conf().setDefaultValue('logs/stream-enabled', 'false')
    config.conf().setDefaultValue('logs/stream-port', DefaultWebLogPort())
    config.conf().setDefaultValue('logs/traffic-enabled', 'false')
    config.conf().setDefaultValue('logs/traffic-port', DefaultWebTrafficPort())

    config.conf().setDefaultValue('paths/backups', '')
    config.conf().setDefaultValue('paths/customers', '')
    config.conf().setDefaultValue('paths/messages', '')
    config.conf().setDefaultValue('paths/receipts', '')
    config.conf().setDefaultValue('paths/restore', '')

    config.conf().setDefaultValue('personal/private-key-size', DefaultPrivateKeySize())
    config.conf().setDefaultValue('personal/betatester', 'false')
    config.conf().setDefaultValue('personal/email', '')
    config.conf().setDefaultValue('personal/name', '')
    config.conf().setDefaultValue('personal/nickname', '')
    config.conf().setDefaultValue('personal/surname', '')

    config.conf().setDefaultValue('services/accountant/enabled', 'false')

    config.conf().setDefaultValue('services/backup-db/enabled', 'true')

    config.conf().setDefaultValue('services/backups/enabled', 'true')
    config.conf().setDefaultValue('services/backups/block-size', diskspace.MakeStringFromBytes(DefaultBackupBlockSize()))
    config.conf().setDefaultValue('services/backups/max-block-size', diskspace.MakeStringFromBytes(DefaultBackupMaxBlockSize()))
    config.conf().setDefaultValue('services/backups/max-copies', '2')
    config.conf().setDefaultValue('services/backups/keep-local-copies-enabled', 'false')
    config.conf().setDefaultValue('services/backups/wait-suppliers-enabled', 'false')

    config.conf().setDefaultValue('services/blockchain/enabled', 'false')
    config.conf().setDefaultValue('services/blockchain/host', '127.0.0.1')
    config.conf().setDefaultValue('services/blockchain/port', 9100)
    config.conf().setDefaultValue('services/blockchain/seeds', '')
    config.conf().setDefaultValue('services/blockchain/explorer/enabled', 'true')
    config.conf().setDefaultValue('services/blockchain/explorer/port', 9180)
    config.conf().setDefaultValue('services/blockchain/wallet/enabled', 'true')
    config.conf().setDefaultValue('services/blockchain/wallet/port', 9280)
    config.conf().setDefaultValue('services/blockchain/miner/enabled', 'false')

    config.conf().setDefaultValue('services/broadcasting/enabled', 'false')
    config.conf().setDefaultValue('services/broadcasting/routing-enabled', 'false')
    config.conf().setDefaultValue('services/broadcasting/max-broadcast-connections', '3')

    config.conf().setDefaultValue('services/contract-chain/enabled', 'false')

    config.conf().setDefaultValue('services/customer/enabled', 'true')
    config.conf().setDefaultValue('services/customer/needed-space', diskspace.MakeStringFromBytes(DefaultNeededBytes()))
    config.conf().setDefaultValue('services/customer/suppliers-number', DefaultDesiredSuppliers())

    config.conf().setDefaultValue('services/customer-contracts/enabled', 'false')

    config.conf().setDefaultValue('services/customer-family/enabled', 'true')

    config.conf().setDefaultValue('services/customer-patrol/enabled', 'true')

    config.conf().setDefaultValue('services/customer-support/enabled', 'true')

    config.conf().setDefaultValue('services/data-motion/enabled', 'true')

    config.conf().setDefaultValue('services/entangled-dht/enabled', 'true')
    config.conf().setDefaultValue('services/entangled-dht/udp-port', DefaultDHTPort())
    config.conf().setDefaultValue('services/entangled-dht/known-nodes', '')

    config.conf().setDefaultValue('services/employer/enabled', 'true')

    config.conf().setDefaultValue('services/gateway/enabled', 'true')

    config.conf().setDefaultValue('services/http-connections/enabled', 'false')
    config.conf().setDefaultValue('services/http-connections/http-port', DefaultHTTPPort())

    config.conf().setDefaultValue('services/http-transport/enabled', 'false')  # not done yet
    config.conf().setDefaultValue('services/http-transport/receiving-enabled', 'true')
    config.conf().setDefaultValue('services/http-transport/sending-enabled', 'true')
    config.conf().setDefaultValue('services/http-transport/priority', 50)

    config.conf().setDefaultValue('services/identity-server/enabled', 'false')
    config.conf().setDefaultValue('services/identity-server/host', '')
    config.conf().setDefaultValue('services/identity-server/tcp-port', IdentityServerPort())
    config.conf().setDefaultValue('services/identity-server/web-port', IdentityWebPort())

    config.conf().setDefaultValue('services/identity-propagate/enabled', 'true')
    config.conf().setDefaultValue('services/identity-propagate/known-servers', '')
    config.conf().setDefaultValue('services/identity-propagate/preferred-servers', '')
    config.conf().setDefaultValue('services/identity-propagate/min-servers', MinimumIdentitySources() + 1)
    config.conf().setDefaultValue('services/identity-propagate/max-servers', int(MaximumIdentitySources() / 2))

    config.conf().setDefaultValue('services/ip-port-responder/enabled', 'true')

    config.conf().setDefaultValue('services/keys-registry/enabled', 'true')

    config.conf().setDefaultValue('services/keys-storage/enabled', 'true')

    config.conf().setDefaultValue('services/list-files/enabled', 'true')

    config.conf().setDefaultValue('services/message-history/enabled', 'true')

    config.conf().setDefaultValue('services/miner/enabled', 'false')

    config.conf().setDefaultValue('services/my-ip-port/enabled', 'true')

    config.conf().setDefaultValue('services/network/enabled', 'true')
    config.conf().setDefaultValue('services/network/proxy/enabled', 'false')
    config.conf().setDefaultValue('services/network/proxy/host', '')
    config.conf().setDefaultValue('services/network/proxy/password', '')
    config.conf().setDefaultValue('services/network/proxy/port', '')
    config.conf().setDefaultValue('services/network/proxy/ssl', 'false')
    config.conf().setDefaultValue('services/network/proxy/username', '')
    config.conf().setDefaultValue('services/network/receive-limit', DefaultBandwidthInLimit())
    config.conf().setDefaultValue('services/network/send-limit', DefaultBandwidthOutLimit())

    config.conf().setDefaultValue('services/nodes-lookup/enabled', 'true')

    config.conf().setDefaultValue('services/p2p-hookups/enabled', 'true')

    config.conf().setDefaultValue('services/p2p-notifications/enabled', 'true')

    config.conf().setDefaultValue('services/private-messages/enabled', 'true')

    config.conf().setDefaultValue('services/proxy-server/enabled', 'true')
    config.conf().setDefaultValue('services/proxy-server/routes-limit', 10)
    config.conf().setDefaultValue('services/proxy-server/current-routes', '{}')

    config.conf().setDefaultValue('services/proxy-transport/enabled', 'true')
    config.conf().setDefaultValue('services/proxy-transport/sending-enabled', 'true')
    config.conf().setDefaultValue('services/proxy-transport/receiving-enabled', 'true')
    config.conf().setDefaultValue('services/proxy-transport/priority', 100)
    config.conf().setDefaultValue('services/proxy-transport/my-original-identity', '')
    config.conf().setDefaultValue('services/proxy-transport/current-router', '')
    config.conf().setDefaultValue('services/proxy-transport/preferred-routers', '')
    config.conf().setDefaultValue('services/proxy-transport/router-lifetime-seconds', 600)

    config.conf().setDefaultValue('services/rebuilding/enabled', 'true')

    config.conf().setDefaultValue('services/restores/enabled', 'true')

    config.conf().setDefaultValue('services/shared-data/enabled', 'true')

    config.conf().setDefaultValue('services/supplier/enabled', 'true')
    config.conf().setDefaultValue('services/supplier/donated-space', diskspace.MakeStringFromBytes(DefaultDonatedBytes()))

    config.conf().setDefaultValue('services/supplier-contracts/enabled', 'false')

    config.conf().setDefaultValue('services/supplier-relations/enabled', 'false')

    config.conf().setDefaultValue('services/tcp-connections/enabled', 'true')
    config.conf().setDefaultValue('services/tcp-connections/tcp-port', DefaultTCPPort())
    config.conf().setDefaultValue('services/tcp-connections/upnp-enabled', 'true')

    config.conf().setDefaultValue('services/tcp-transport/enabled', 'true')
    config.conf().setDefaultValue('services/tcp-transport/receiving-enabled', 'true')
    config.conf().setDefaultValue('services/tcp-transport/sending-enabled', 'true')
    config.conf().setDefaultValue('services/tcp-transport/priority', 10)

    config.conf().setDefaultValue('services/udp-datagrams/enabled', 'true')
    config.conf().setDefaultValue('services/udp-datagrams/udp-port', DefaultUDPPort())

    # TODO: UDP transport was temporary switched off
    config.conf().setDefaultValue('services/udp-transport/enabled', 'false')
    config.conf().setDefaultValue('services/udp-transport/receiving-enabled', 'true')
    config.conf().setDefaultValue('services/udp-transport/sending-enabled', 'true')
    config.conf().setDefaultValue('services/udp-transport/priority', 20)


def _checkRandomizePortNumbers():
    """
    To avoid conflicts between two nodes inside same sub-network they both need to use
    different port numbers. So this method will first check if port number already set or not.
    If it is not it will set random value in the range.
    """
    # 7000-8000 for tcp transport
    if not config.conf().getOriginalData('services/tcp-connections/tcp-port'):
        config.conf().setData('services/tcp-connections/tcp-port', str(random.randint(7001, 8000) - 1))
    # 8000-9000 for udp transport
    if not config.conf().getOriginalData('services/udp-datagrams/udp-port'):
        config.conf().setData('services/udp-datagrams/udp-port', str(random.randint(8001, 9000) - 1))
    # 9000-10000 for http transport
    if not config.conf().getOriginalData('services/http-connections/http-port'):
        config.conf().setData('services/http-connections/http-port', str(random.randint(9001, 10000) - 1))
    # 10000-11000 for entangled dht
    if not config.conf().getOriginalData('services/entangled-dht/udp-port'):
        config.conf().setData('services/entangled-dht/udp-port', str(random.randint(10001, 11000) - 1))
    # 11000-12000 for blockchain
    if not config.conf().getOriginalData('services/blockchain/port'):
        config.conf().setData('services/blockchain/port', str(random.randint(11001, 12000) - 1))


def _createNotExisingSettings():
    """
    Validate user settings and create them from default values.
    """
    for key in config.conf()._default.keys():
        if not config.conf().exist(key):
            value = config.conf().getDefaultValue(key)
            config.conf().setData(key, value)
            lg.out(2, '    created option %s with default value : [%s]' % (key, value))
            # print '    created option %s with default value : [%s]' % (key, value)


def _checkStaticDirectories():
    """
    Check existance of static data folders.
    """
    if not os.path.exists(TempDir()):
        lg.out(6, 'settings.init want to create folder: ' + TempDir())
        os.makedirs(TempDir())
    if not os.path.exists(BandwidthInDir()):
        lg.out(6, 'settings.init want to create folder: ' + BandwidthInDir())
        os.makedirs(BandwidthInDir())
    if not os.path.exists(BandwidthOutDir()):
        lg.out(6, 'settings.init want to create folder: ' + BandwidthOutDir())
        os.makedirs(BandwidthOutDir())
    if not os.path.exists(LogsDir()):
        lg.out(6, 'settings.init want to create folder: ' + LogsDir())
        os.makedirs(LogsDir())
    if not os.path.exists(IdentityCacheDir()):
        lg.out(6, 'settings.init want to create folder: ' + IdentityCacheDir())
        os.makedirs(IdentityCacheDir())
    if not os.path.exists(SuppliersDir()):
        lg.out(6, 'settings.init want to create folder: ' + SuppliersDir())
        os.makedirs(SuppliersDir())
    if not os.path.exists(RatingsDir()):
        lg.out(6, 'settings.init want to create folder: ' + RatingsDir())
        os.makedirs(RatingsDir())
    if not os.path.exists(KeyStoreDir()):
        lg.out(6, 'settings.init want to create folder: ' + KeyStoreDir())
        os.makedirs(KeyStoreDir())
    if not os.path.exists(ChatChannelsDir()):
        lg.out(6, 'settings.init want to create folder: ' + ChatChannelsDir())
        os.makedirs(ChatChannelsDir())
    if not os.path.exists(ChatHistoryDir()):
        lg.out(6, 'settings.init want to create folder: ' + ChatHistoryDir())
        os.makedirs(ChatHistoryDir())
    if not os.path.exists(BlockchainDir()):
        lg.out(6, 'settings.init want to create folder: ' + BlockchainDir())
        os.makedirs(BlockchainDir())


def _checkCustomDirectories():
    """
    Check existance of user configurable folders.
    """
    if config.conf().getString('paths/customers', '') == '':
        config.conf().setString('paths/customers', DefaultCustomersDir())
    if not os.path.exists(getCustomersFilesDir()):
        lg.out(6, 'settings.init want to create folder: ' + getCustomersFilesDir())
        os.makedirs(getCustomersFilesDir())
    if config.conf().getString('paths/backups', '') == '':
        config.conf().setString('paths/backups', DefaultBackupsDBDir())
    if not os.path.exists(getLocalBackupsDir()):
        lg.out(6, 'settings.init want to create folder: ' + getLocalBackupsDir())
        os.makedirs(getLocalBackupsDir())
    if config.conf().getString('paths/receipts', '') == '':
        config.conf().setString('paths/receipts', DefaultReceiptsDir())
    if not os.path.exists(getReceiptsDir()):
        lg.out(6, 'settings.init want to create folder: ' + getReceiptsDir())
        os.makedirs(getReceiptsDir())
    if config.conf().getString('paths/restore', '') == '':
        config.conf().setString('paths/restore', DefaultRestoreDir())

#-------------------------------------------------------------------------------

def main():
    lg.set_debug_level(24)
    init()
    try:
        inp = sys.argv[1].rstrip('/')
    except:
        print('wrong input')
        return
    if not config.conf().exist(inp):
        print('not exist')
        return
    if not config.conf().hasChilds(inp):
        print(inp, config.conf().getData(inp))
        return
    for child in config.conf().listEntries(inp):
        if config.conf().hasChilds(child):
            print(child, config.conf().listEntries(child))
        else:
            print(child, config.conf().getData(child))

#------------------------------------------------------------------------------


if __name__ == '__main__':
    main()
