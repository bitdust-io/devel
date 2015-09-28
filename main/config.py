#!/usr/bin/python
#config.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: config
"""

import os
import sys
import types
import re

if __name__ == "__main__":
    import os.path as _p
    sys.path.append(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..'))

from logs import lg

#------------------------------------------------------------------------------ 

_Config = None

#------------------------------------------------------------------------------ 

def init(configDir):
    """
    """
    global _Config
    if _Config is None: 
        _Config = DetailedConfig(configDir)
        lg.out(2, 'config.init     at %s' % configDir)
    else:
        lg.warn('already called, was set up in %s' % _Config.getConfigDir())
    

def shutdown():
    """
    """
    lg.out(2, 'config.shutdown')
    global _Config
    if _Config:
        del _Config
        _Config = None


def conf():
    global _Config
    return _Config

#------------------------------------------------------------------------------ 

class BaseConfig( object ) :
    def __init__( self, configDir ) :
        self.configDir = configDir

    def getConfigDir( self ) :
        return self.configDir
    
    def exist(self, entryPath):
        return self._get( entryPath ) is not None
    
    def remove( self, entryPath ) :
        elemList = self._parseEntryPath( entryPath )
        fpath = os.path.join( self.configDir, *elemList )
        return self._rmrf( fpath )

    def listEntries( self, entryPath ) :
        entries = self._get( entryPath )
        t = type(entries)
        if t is types.StringType :
            # lg.warn( 'argument to listEntries is a file: %s' % entryPath )
            return []
        if entries is None :
            return []
        assert t is types.ListType
        return entries
    
    def hasChilds(self, entryPath):
        elemList = self._parseEntryPath( entryPath )
        fpath = os.path.join( self.configDir, *elemList )
        if os.path.isdir(fpath) :
            return True
        return False
    
    def listAllEntries(self):
        try:
            from system import bpio
            l = []
            abspth = bpio.portablePath(os.path.abspath(self.getConfigDir()))
            for subpath in bpio.list_dir_recursive(abspth):
                path = bpio.portablePath(subpath)
                l.append(path.replace(abspth, '').strip('/'))
            return l
        except:
            lg.exc()
            return []

    def getData( self, entryPath, default=None ) :
        data = self._get( entryPath )
        if data is None : 
            return default
        if type(data) is types.ListType :
            lg.warn( 'argument to getData is a directory: %s' % entryPath )
            return default
        return data

    def setData( self, entryPath, value ) :
        return self._set( entryPath, value )

    def getInt( self, entryPath, default=None ) :
        data = self.getData( entryPath )
        if data is None : 
            return default
        try :
            return int(data.strip())
        except ValueError :
            return default

    def setInt( self, entryPath, value ) :
        return self._set( entryPath, str(value) )

    def getBool( self, entryPath, default=None ) :
        data = self.getData( entryPath )
        if data is None : 
            return default
        return True if data.strip() == 'true' else False

    def setBool(self, entryPath, value):
        return self._set(entryPath, 'true' if value else 'false')

    def getString( self, entryPath, default=None ) :
        data = self.getData( entryPath )
        if data is None: 
            return default
        data = data.strip()
        if len(data) < 2: 
            return default
        if not (data[0] == data[-1] == '"'): 
            return default
        data = data[1:-1]
        try :
            out = []
            i = 0
            while i < len(data) :
                c = data[i]
                if c == '\\' :
                    out.append( data[i+1] )
                    i += 2
                else :
                    out.append( c )
                    i += 1
            return ''.join( out )
        except IndexError :
            return default

    def setString( self, entryPath, value ) :
        out = ['"']
        for x in value :
            if x in '\\"' :
                out.append( '\\' )
            out.append( x )
        out.append( '"' )
        return self._set( entryPath, ''.join(out) )
    
    def _mkdir( self, dpath ) :
        if os.path.isfile(dpath) :
            self._unlink( dpath )
        if not os.path.isdir(dpath) :
            try :
                if sys.platform == 'win32' :
                    os.makedirs( dpath )
                else :
                    os.makedirs( dpath, 0700 )
                return True
            except OSError :
                lg.exc( 'error creating directory: %s' % dpath )
                return False
        return True

    def _listdir( self, dpath ) :
        try :
            return os.listdir( dpath )
        except OSError :
            lg.exc( 'error listing dir: %s' % dpath )
            return []

    def _unlink( self, fpath ) :
        try :
            if os.path.isdir(fpath) :
                os.rmdir( fpath )
            else :
                os.unlink( fpath )
            return True
        except OSError :
            lg.exc( 'error unlinking: %s' % fpath )
            return False

    def _rmrf( self, fpath ) :
        if os.path.isdir(fpath) :
            files = self._listdir( fpath )
            for f in files :
                childPath = os.path.join( fpath, f )
                self._rmrf( childPath )
            return self._unlink( fpath )
        elif os.path.isfile(fpath) :
            return self._unlink( fpath )
        return False

    def _validateElemList( self, elemList ) :
        for x in elemList :
            assert x.strip() == x
            assert '\\' not in x
            assert '/' not in x
            assert x not in ('.','..')

    def _parseEntryPath( self, entryPath ) :
        elemList = entryPath.split( '/' )
        if elemList and (not elemList[0]) :
            del elemList[0]
        if elemList :
            assert elemList[-1]
        self._validateElemList( elemList )
        return elemList

    def _get( self, entryPath ) :
        elemList = self._parseEntryPath( entryPath )
        fpath = os.path.join( self.configDir, *elemList )
        if os.path.isdir(fpath) :
            out = []
            for x in self._listdir(fpath) :
                childPath = '/'.join( elemList + [x] )
                out.append( childPath )
            return out
        elif os.path.isfile(fpath) :
            data = None
            try :
                f = file( fpath, 'rb' )
                data = f.read()
                f.close()
            except (OSError,IOError) :
                lg.exc( 'error reading from file: %s' % fpath )
            return data
        return None

    def _set( self, entryPath, data ) :
        elemList = self._parseEntryPath( entryPath )
        assert elemList
        dpath = self.configDir
        for d in elemList[:-1] :
            dpath = os.path.join( dpath, d )
            self._mkdir( dpath )
        fpath = os.path.join( dpath, elemList[-1] )
        try :
            f = file( fpath, 'wb' )
            f.write( data )
            f.close()
            return True
        except (OSError,IOError) :
            lg.exc( 'error writing to file: %s' % fpath )
        return False

#------------------------------------------------------------------------------ 
    
class DefaultsConfig(BaseConfig):
    _default = {}
    
    def setDefaultValue(self, entryPath, value):
        self._default[entryPath] = str(value)
        
    def getDefaultValue(self, entryPath):
        return self._default.get(entryPath, None)
    
    def getData(self, entryPath, default=None):
        if default is not None:
            return BaseConfig.getData(self, entryPath, default)
        result = BaseConfig.getData(self, entryPath)
        if result is not None:
            return result
        return self.getDefaultValue(entryPath)
        
#------------------------------------------------------------------------------ 

class NotifiableConfig(DefaultsConfig):
    def __init__(self, configDir):
        BaseConfig.__init__(self, configDir)
        self.callbacks = {}
    
    def addCallback(self, mask, cb):
        """
        You can add a callback to catch a moment when some particular option were modified.
        Mask is a string which is used to compared in this way:
            
            entryPath.startswith(mask)
            
        The callback will be fired with such arguments:
        
            cb(entryPath, newValue, oldValue, result)
            
        """
        self.callbacks[mask] = cb
        
    def removeCallback(self, mask):
        """
        Remove existing callback.
        """
        self.callbacks.pop(mask, None)
        
    def _set( self, entryPath, newValue ) :
        oldValue = self._get(entryPath)
        result = BaseConfig._set(self, entryPath, newValue)
        for mask, cb in self.callbacks.items():
            if entryPath.startswith(mask):
                cb(entryPath, newValue, oldValue, result)
        return result

#------------------------------------------------------------------------------ 

TYPE_UNDEFINED = 0
TYPE_BOOLEAN = 1
TYPE_STRING = 2
TYPE_TEXT = 3
TYPE_INTEGER = 4
TYPE_POSITIVE_INTEGER = 5
TYPE_NON_ZERO_POSITIVE_INTEGER = 6
TYPE_FOLDER_PATH = 7
TYPE_FILE_PATH = 8
TYPE_COMBO_BOX = 9
TYPE_PASSWORD = 10
TYPE_DISK_SPACE = 11

TYPES_LABELS = {
    TYPE_UNDEFINED :                'undefined',
    TYPE_BOOLEAN :                  'boolean',
    TYPE_STRING :                   'string',
    TYPE_TEXT :                     'text',
    TYPE_INTEGER :                  'integer',
    TYPE_POSITIVE_INTEGER :         'positive integer',
    TYPE_NON_ZERO_POSITIVE_INTEGER: 'non zero positive integer',
    TYPE_FOLDER_PATH :              'folder path',
    TYPE_FILE_PATH :                'file path',
    TYPE_COMBO_BOX :                'combo box',
    TYPE_PASSWORD :                 'password',
    TYPE_DISK_SPACE :               'disk space',
   }

class FixedTypesConfig(NotifiableConfig):
    _types = {
        'emergency/email':                              TYPE_STRING,
        'emergency/fax':                                TYPE_STRING,
        'emergency/first':                              TYPE_COMBO_BOX,
        'emergency/phone':                              TYPE_STRING,
        'emergency/second':                             TYPE_COMBO_BOX,
        'emergency/text':                               TYPE_STRING,
        'logs/debug-level':                             TYPE_POSITIVE_INTEGER,
        'logs/memdebug-enabled':                        TYPE_BOOLEAN,
        'logs/memdebug-port':                           TYPE_POSITIVE_INTEGER,
        'logs/memprofile-enabled':                      TYPE_BOOLEAN,
        'logs/stream-enabled':                          TYPE_BOOLEAN,
        'logs/stream-port':                             TYPE_POSITIVE_INTEGER,
        'logs/traffic-enabled':                         TYPE_BOOLEAN,
        'logs/traffic-port':                            TYPE_POSITIVE_INTEGER,
        'other/upnp-at-startup':                        TYPE_BOOLEAN,
        'paths/backups':                                TYPE_FOLDER_PATH,
        'paths/customers':                              TYPE_FOLDER_PATH,
        'paths/messages':                               TYPE_FOLDER_PATH,
        'paths/receipts':                               TYPE_FOLDER_PATH,
        'paths/restore':                                TYPE_FOLDER_PATH,
        'personal/betatester':                          TYPE_BOOLEAN,
        'personal/name':                                TYPE_STRING,
        'personal/nickname':                            TYPE_STRING,
        'personal/private-key-size':                    TYPE_STRING,
        'personal/surname':                             TYPE_STRING,
        'services/backup-db/enabled':                   TYPE_BOOLEAN,
        'services/backups/block-size':                  TYPE_DISK_SPACE,
        'services/backups/enabled':                     TYPE_BOOLEAN,
        'services/backups/keep-local-copies-enabled':   TYPE_BOOLEAN,
        'services/backups/max-block-size':              TYPE_DISK_SPACE,
        'services/backups/max-copies':                  TYPE_POSITIVE_INTEGER,
        'services/backups/wait-suppliers-enabled':      TYPE_BOOLEAN,
        'services/customer/enabled':                    TYPE_BOOLEAN,
        'services/customer/needed-space':               TYPE_DISK_SPACE,
        'services/customer/suppliers-number':           TYPE_COMBO_BOX,
        'services/customer-patrol/enabled':             TYPE_BOOLEAN,
        'services/data-motion/enabled':                 TYPE_BOOLEAN,
        'services/entangled-dht/enabled':               TYPE_BOOLEAN,
        'services/entangled-dht/udp-port':              TYPE_POSITIVE_INTEGER,
        'services/employer/enabled':                    TYPE_BOOLEAN,
        'services/gateway/enabled':                     TYPE_BOOLEAN,
        'services/id-server/enabled':                   TYPE_BOOLEAN,
        'services/id-server/host':                      TYPE_STRING,
        'services/id-server/tcp-port':                  TYPE_POSITIVE_INTEGER,
        'services/id-server/web-port':                  TYPE_POSITIVE_INTEGER,
        'services/identity-propagate/enabled':          TYPE_BOOLEAN,
        'services/id-server/enabled':                   TYPE_BOOLEAN,
        'services/list-files/enabled':                  TYPE_BOOLEAN,
        'services/network/enabled':                     TYPE_BOOLEAN,
        'services/network/proxy/enabled':               TYPE_BOOLEAN,
        'services/network/proxy/host':                  TYPE_STRING,
        'services/network/proxy/password':              TYPE_PASSWORD,
        'services/network/proxy/port':                  TYPE_POSITIVE_INTEGER,
        'services/network/proxy/ssl':                   TYPE_BOOLEAN,
        'services/network/proxy/username':              TYPE_STRING,
        'services/network/receive-limit':               TYPE_POSITIVE_INTEGER,
        'services/network/send-limit':                  TYPE_POSITIVE_INTEGER,
        'services/p2p-hookups/enabled':                 TYPE_BOOLEAN,
        'services/private-messages/enabled':            TYPE_BOOLEAN,
        'services/rebuilding/enabled':                  TYPE_BOOLEAN,
        'services/restores/enabled':                    TYPE_BOOLEAN,
        'services/my-ip-port/enabled':                  TYPE_BOOLEAN,
        'services/ip-port-responder/enabled':           TYPE_BOOLEAN,
        'services/supplier/donated-space':              TYPE_DISK_SPACE,
        'services/supplier/enabled':                    TYPE_BOOLEAN,
        'services/tcp-connections/enabled':             TYPE_BOOLEAN,
        'services/tcp-connections/tcp-port':            TYPE_POSITIVE_INTEGER,
        'services/tcp-connections/upnp-enabled':        TYPE_BOOLEAN,
        'services/tcp-transport/enabled':               TYPE_BOOLEAN,
        'services/tcp-transport/receiving-enabled':     TYPE_BOOLEAN,
        'services/tcp-transport/sending-enabled':       TYPE_BOOLEAN,
        'services/tcp-transport/priority':              TYPE_POSITIVE_INTEGER,
        'services/udp-datagrams/enabled':               TYPE_BOOLEAN,
        'services/udp-datagrams/udp-port':              TYPE_POSITIVE_INTEGER,
        'services/udp-transport/enabled':               TYPE_BOOLEAN,
        'services/udp-transport/receiving-enabled':     TYPE_BOOLEAN,
        'services/udp-transport/sending-enabled':       TYPE_BOOLEAN,
        'services/udp-transport/priority':              TYPE_POSITIVE_INTEGER,
        'services/proxy-server/enabled':                TYPE_BOOLEAN,
        'services/proxy-transport/enabled':             TYPE_BOOLEAN,
        'services/proxy-transport/sending-enabled':     TYPE_BOOLEAN,
        'services/proxy-transport/receiving-enabled':   TYPE_BOOLEAN,
        'services/proxy-transport/priority':            TYPE_POSITIVE_INTEGER,
        'updates/mode':                                 TYPE_COMBO_BOX,
        'updates/shedule':                              TYPE_TEXT,
    }

    def listKnownTypes(self):
        return self._types.keys()
    
    def setType(self, key, typ):
        self._types[key] = typ
    
    def getType(self, entry):
        return self._types.get(entry, TYPE_UNDEFINED)
    
    def getTypeLabel(self, entry):
        return TYPES_LABELS.get(self.getType(entry))
    
#------------------------------------------------------------------------------ 

class CachedConfig(FixedTypesConfig):
    _cache = {}
    
    def _set(self, entryPath, data):
        if self._cache.has_key(entryPath):
            if self._cache[entryPath] == data:
                return True
        self._cache[entryPath] = data
        result = FixedTypesConfig._set(self, entryPath, data)
        return result
    
    def _get(self, entryPath):
        if self._cache.has_key(entryPath):
            return self._cache[entryPath]
        result = FixedTypesConfig._get(self, entryPath)
        self._cache[entryPath] = result
        return result
    
    def cache(self):
        return self._cache
    
    def reloadCache(self):
        """
        Reload whole cache from local files.
        """
        #TODO
        
    def storeCache(self):
        """
        Write all cached entries into local files.
        """
        #TODO

#------------------------------------------------------------------------------ 

class DetailedConfig(CachedConfig):
    _labels = {}
    _infos = {}
    
    def __init__(self, configDir):
        CachedConfig.__init__(self, configDir)
        try:
            import config_details
            self._load_details(config_details.raw())
        except:
            pass
    
    def _loadDetails(self, src):
        """
        """
        current_option = ''
        for line in src.splitlines():
            if not line.strip():
                continue
            r = re.match('^{(.+?)}(.+?)$', line)
            if r:
                current_option = r.group(1).strip()
                self._labels[current_option] = r.group(2).strip()
            else:
                if current_option:
                    if not self._infos.has_key(current_option):
                        self._infos[current_option] = ''
                    self._infos[current_option] += line.strip() + '\n'
                    
    def getLabel(self, entryPath):
        return self._labels.get(entryPath, '')
    
    def getInfo(self, entryPath):
        return self._infos.get(entryPath, '')
    
#------------------------------------------------------------------------------ 


def main():
    """
    Read settings from 'userconfig' file and print in HTML form.
    """
    from main import settings
    settings.init()
    init(settings.ConfigDir())
#    last = ''
#    for entry in sorted(conf()._types.keys()):
#        parent, key = entry.rsplit('/', 1)
#        while parent.count('/'):
#            p, parent = parent.rsplit('/', 1)
#            if p != 'services':
#                print p
#            parent = '  ' + parent 
#        if parent != last:
#            print parent
#            last = parent
#        print ' ' * (last.count(' ') + 1) * 2, key, '\t\t\t\t', conf().get_type_label(entry).upper()
    # print '\n'.join(map(lambda x: "    '%s':\t\t\tNode," % x, sorted(conf().listAllEntries())))
    s = conf().getData('details')
    conf().loadDetails(s)
    


if __name__ == "__main__":
    main()


