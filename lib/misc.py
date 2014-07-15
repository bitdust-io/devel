#!/usr/bin/python
#misc.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: misc

A set of different methods across the code.
 
TODO 
    Really need to do some refactoring here - too many things in one place.
"""

import os
import sys
import random
import time
import math
import hmac
import hashlib
import base64
import string
import subprocess
import re
import tempfile
import urllib
import locale
import textwrap
import cPickle


from twisted.python.win32 import cmdLineQuote

import io
import settings
import net_misc
import packetid

import userid.identity

#------------------------------------------------------------------------------ 

_RemoveAfterSent = True

# Functions outside should use getLocalIdentity()
_LocalIdentity = None
_LocalIDURL = None
_LocalName = None

# if we come up with more valid transports,
# we'll need to add them here
# in the case we don't have any valid transports,
# we use this array as the default
# order is important!
# this is default order to be used for new users
# more stable transports must be higher
validTransports = [ 'http', 'cspace', 'q2q', 'tcp', 'ssh', 'email', 'skype', 'udp', 'dhtudp']

_AttenuationFactor = 1.1

#-------------------------------------------------------------------------------

def init():
    """
    Will be called in main thread at start up.
    Can put here some minor things if needed.
    """
    io.log(4, 'misc.init')
    loadLocalIdentity()

#-------------------------------------------------------------------------------

def isLocalIdentityReady():
    """
    Return True if local identity object already initialized and stored in memory. 
    """
    global _LocalIdentity
    return _LocalIdentity is not None

def setLocalIdentity(ident):
    """
    Set local identity object in the memory.  
    """
    global _LocalIdentity
    global _LocalIDURL
    global _LocalName
    if not ident:
        return
    _LocalIdentity = ident
    _LocalIDURL = _LocalIdentity.getIDURL()
    _LocalName = _LocalIdentity.getIDName()

def setLocalIdentityXML(idxml):
    """
    Construct identity object from XML string and save it to the memory.
    """
    global _LocalIdentity
    _LocalIdentity = userid.identity.identity(xmlsrc=idxml)

def getLocalIdentity():
    """
    Return my identity object.
    """
    global _LocalIdentity
    if not isLocalIdentityReady():
        loadLocalIdentity()
    return _LocalIdentity

def getLocalID():
    """
    Return my IDURL.
    """ 
    global _LocalIDURL
    if _LocalIDURL is None:
        localIdent = getLocalIdentity()
        if localIdent:
            _LocalIDURL = localIdent.getIDURL()
    return _LocalIDURL

def getIDName():
    """
    Return my account name, this is a filename part of IDURL without '.xml'.
    """
    global _LocalName
    if _LocalName is None:
        localIdent = getLocalIdentity()
        if localIdent:
            _LocalName = localIdent.getIDName()
    return _LocalName

def loadLocalIdentity():
    """
    The core method.
    The file [BitPie.NET data dir]/metadata/localidentity keeps the user identity in XML format.
    Do read the local file and set into object in memory.  
    """
    global _LocalIdentity
    global _LocalIDURL
    global _LocalName
    xmlid = ''
    filename = settings.LocalIdentityFilename()
    if os.path.exists(filename):
        xmlid = io.ReadTextFile(filename)
        io.log(6, 'misc.loadLocalIdentity %d bytes read from\n        %s' % (len(xmlid), filename))
    if xmlid == '':
        io.log(2, "misc.loadLocalIdentity ERROR reading local identity from " + filename)
        return
    lid = userid.identity.identity(xmlsrc=xmlid)
    if not lid.Valid():
        io.log(2, "misc.loadLocalIdentity ERROR local identity is not Valid")
        return
    _LocalIdentity = lid
    _LocalIDURL = lid.getIDURL()
    _LocalName = lid.getIDName()
    setTransportOrder(getOrderFromContacts(_LocalIdentity))
    io.log(6, "misc.loadLocalIdentity my name is [%s]" % lid.getIDName())

def saveLocalIdentity():
    """
    Save identity object from memory into local file.
    Do sign the identity than serialize to write to the file.
    """
    global _LocalIdentity
    if not isLocalIdentityReady():
        io.log(2, "misc.saveLocalIdentity ERROR localidentity not exist!")
        return
    io.log(6, "misc.saveLocalIdentity")
    _LocalIdentity.sign()
    xmlid = _LocalIdentity.serialize()
    filename = settings.LocalIdentityFilename()
    io.WriteFile(filename, xmlid)

#------------------------------------------------------------------------------ 

def readLocalIP():
    """
    Read local IP stored in the file [BitPie.NET data dir]/metadata/localip.
    """
    return io.ReadBinaryFile(settings.LocalIPFilename())

def readExternalIP():
    """
    Read external IP stored in the file [BitPie.NET data dir]/metadata/externalip.
    """
    return io.ReadBinaryFile(settings.ExternalIPFilename())

def readSupplierData(idurl, filename):
    """
    Read a file from [BitPie.NET data dir]/suppliers/[IDURL] folder.
    The file names right now is ['connected', 'disconnected', 'listfiles']. 
    """
    path = settings.SupplierPath(idurl, filename)
    if not os.path.isfile(path):
        return ''
    return io.ReadTextFile(path)

def writeSupplierData(idurl, filename, data):
    """
    Writes to a config file for given supplier.
    """
    dirPath = settings.SupplierPath(idurl)
    if not os.path.isdir(dirPath):
        os.makedirs(dirPath)
    path = settings.SupplierPath(idurl, filename)
    return io.WriteFile(path, data)

#-------------------------------------------------------------------------------

def NewBackupID(time_st=None):
    """
    BackupID is just a string representing time and date.
    Symbol "F" is placed at the start to identify that this is a FULL backup.
    We have a plans to provide INCREMENTAL backups also. 
    """
    if time_st is None:
        time_st = time.localtime()
    ampm = time.strftime("%p", time_st)
    if ampm == '':
        io.log(2, 'misc.NewBackupID WARNING time.strftime("%p") returns empty string')
        ampm = 'AM' if time.time() % 86400 < 43200 else 'PM'
    result = "F" + time.strftime("%Y%m%d%I%M%S", time_st) + ampm
    return result

def TimeFromBackupID(backupID):
    """
    Reverse method - return a date and time from given BackupID.
    """
    try:
        if backupID.endswith('AM') or backupID.endswith('PM'):
            ampm = backupID[-2:]
            st_time = list(time.strptime(backupID[1:-2], '%Y%m%d%I%M%S'))
        else:
            i = backupID.rfind('M')
            ampm = backupID[i-1:i+1]
            st_time = list(time.strptime(backupID[1:i-1], '%Y%m%d%I%M%S'))
        if ampm == 'PM':
            st_time[3] += 12
        return time.mktime(st_time)
    except:
        io.exception()
        return None

def modified_version(a):
    """
    Next functions are to come up with a sorted list of backup ids (dealing with AM/PM).
    This method make a number for given BackupID - used to compare two BackupID's.
    """
    try:
        if a.endswith('AM') or a.endswith('PM'):
            int_a = int(a[1:-2])
            int_b = 0
        else:
            i = a.rfind('M')
            int_a = int(a[1:i-1])
            int_b = int(a[i+1:])
    except:
        io.exception()
        return -1  
    hour = a[-8:-6]
    if a.endswith('PM') and hour != '12':
        int_a += 120000
    elif a.endswith('AM') and hour == '12':
        int_a -= 120000
    return int_a + int_b

def version_compare(version1, version2):
    """
    Compare two BackupID's, I start using another term for BackupID not so long ago: ``version``.
    I decided to create a complex ID to identify the data on remote machine.:
        <path>/<version>/<packetName>
    This way same data can have different versions.
    See ``lib.packetid`` module for more info.
    """
    return cmp(modified_version(version1), modified_version(version2))

def backup_id_compare(backupID1, backupID2):
    """
    Compare two 'complex' backupID's: at first compare paths, than version.
    """
    if isinstance(backupID1, tuple):
        backupID1 = backupID1[0]
        backupID2 = backupID2[0]
    pathID1, version1 = packetid.SplitBackupID(backupID1)
    pathID2, version2 = packetid.SplitBackupID(backupID2)
    if pathID1 is None or pathID2 is None:
        return 0
    if pathID1 != pathID2:
        return cmp(pathID1, pathID2)
    return version_compare(version1, version2)

def sorted_backup_ids(backupIds, reverse=False):
    """
    Sort a list of backupID's.
    """
    sorted_ids = sorted(backupIds, backup_id_compare, reverse=reverse)
    return sorted_ids

def sorted_versions(versions, reverse=False):
    """
    Sort a list of versions.
    """
    sorted_versions_list = sorted(versions, version_compare, reverse=reverse)
    return sorted_versions_list

#------------------------------------------------------------------------------ 

BASE_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!()+-#$^&_=@[]{}`~' 
BASE_LIST = BASE_ALPHABET
BASE_DICT = dict((c, i) for i, c in enumerate(BASE_LIST))

def base_decode(string, reverse_base=BASE_DICT):
    """
    Not used right now, I was playing with file paths on remote peers.
    """
    return base64.decodestring(string)
#    length = len(reverse_base)
#    ret = 0
#    for i, c in enumerate(string[::-1]):
#        ret += (length ** i) * reverse_base[c]
#    return ret

def base_encode(string, base=BASE_LIST):
    """
    Not used at the moment.
    """
    return base64.encodestring(string)
#    length = len(base)
#    ret = ''
#    while integer != 0:
#        ret = base[integer % length] + ret
#        integer /= length
#    return ret

def FilePathToBackupID(filepath):
    """
    The idea was to hide the original file and folders names on suppliers machines but keep the directory structure.
    Finally I came to index file wich is encrypted and all data is stored in the same directory tree, 
    but files and folders names are replaced with numbers.
    Not used at the moment.
    """
    # be sure the string is in unicode
    fp = io.portablePath(filepath)
    # now convert to string with char codes as numbers
    result = ''
    for part in fp.split('/'):
        if part == '':
            result += '/'
            continue
        if len(result) > 0:
            # skip first separator
            # if this is Linux absolute path  
            result += '/'
        # switch from unicode if it was
        part = str(part) # unicode(part).encode()
        # word = base64.b64encode(part).replace('+', '-').replace('/', '_')
        # word = base64.b64encode(hashlib.sha1(part+os.urandom(8)).digest()).replace('+', '-').replace('/', '_').replace('=', '')
        # word = hashlib.sha1(part+os.urandom(8)).hexdigest()
        print base64.b64encode(os.urandom(6))
        word = hashlib.md5(part+os.urandom(4)).hexdigest()
        print len(word)
#        # compress the string
#        if compress:
#            # import zlib
#            # word = base_encode(zlib.compress(upart, 9))
#            word = base_encode(upart)
#        else:
#            word = u''
#            for c in upart:
#                word += '%04d' % ord(c)
#        word = word.strip()
        # print '[%s]' % word
        result += word 
    return result

def BackupIDToFilePath(backupID, decompress=False):
    """
    Not used.
    """
    result = ''
    part = ''
    ch = ''
    for c in backupID:
        if c == '/':
            if part != '':
                # base64.b64encode(part).replace('+', '-').replace('/', '_')
                result += base64.b64decode(part.replace('-', '+').replace('_', '/'))
#                if decompress:
#                    import zlib
#                    # result += zlib.decompress(base_decode(part))
#                    result += base_decode(part)
#                else:
#                    result += part
            result += c
            part = ''
        else:
            part += c
#            if decompress:
#                part += c
#            else:
#                ch += c
#                if len(ch) == 4:
#                    try:
#                        v = int(ch)
#                    except:
#                        io.exception()
#                    part += unichr(v)
#                    ch = ''
    if part:
        result += base64.b64decode(part.replace('-', '+').replace('_', '/'))
        # result += part
#        if decompress:
#            import zlib
#            result += zlib.decompress(base_decode(part))
#        else:
#            result += part
    # we return string in unicode
    return unicode(result)

#------------------------------------------------------------------------------ 

def DigitsOnly(input, includes=''):
    """
    Very basic method to convert string to number.
    This returns same string but with digits only.
    """
    return ''.join([c for c in input if c in '0123456789' + includes])

def IsDigitsOnly(input):
    """
    Return True if ``input`` string contains only digits. 
    """
    for c in input:
        if c not in '0123456789':
            return False
    return True

def ToInt(input, default=0):
    """
    Convert a string to number using built-in int() method.
    """
    try:
        return int(input)
    except:
        return default
    
def ToFloat(input, default=0.0):
    """
    Convert a string to number using built-in float() method.
    """
    try:
        return float(input)
    except:
        return default

#------------------------------------------------------------------------------ 

def ValidUserName(username):
    """
    A method to validate account name entered by user.
    """
    if len(username) < settings.MinimumUsernameLength():
        return False
    if len(username) > settings.MaximumUsernameLength():
        return False
    for c in username:
        if c not in settings.LegalUsernameChars():
            return False
    if username[0] not in set('abcdefghijklmnopqrstuvwxyz'):
        return False
    if username.startswith('dhn'):
        return False
    return True

def ValidEmail(email, full_check=True):
    """
    A method to validate typed email address.
    """
    regexp = '^[\w\-\.\@]*$'
    if re.match(regexp,email) == None:
        return False
    if email.startswith('.'):
        return False
    if email.endswith('.'):
        return False
    if email.startswith('-'):
        return False
    if email.endswith('-'):
        return False
    if email.startswith('@'):
        return False
    if email.endswith('@'):
        return False
    if len(email) < 3:
        return False
    if full_check:
        regexp2 = '^[\w\-\.]*\@[\w\-\.]*$'
        if re.match(regexp2,email) == None:
            return False
    return True

def ValidPhone(value):
    """
    A method to validate typed phone number.
    """
    regexp = '^[ \d\-\+]*$'
    if re.match(regexp,value) == None:
        return False
    if len(value) < 5:
        return False
    return True

def ValidName(value):
    """
    A method to validate user name.
    """
    regexp = '^[\w\-]*$'
    if re.match(regexp, value) == None:
        return False
    if len(value) > 100:
        return False
    return True

def MakeValidHTMLComment(text):
    """
    Keeps only ascii symbols of the string.
    """
    ret = ''
    for c in text:
        if c in set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-+*/=_()[]{}:;,.?!@#$%|~ "):
            ret += c
    return ret

def ValidateBitCoinAddress(strAddr):
    """ 
    Does simple validation of a bitcoin address. 
        :param strAddr: an ASCII or unicode string, of a bitcoin public address.
        :return boolean: indicating that the address has a correct format.
    http://www.rugatu.com/questions/3255/anybody-has-python-code-to-verifyvalidate-bitcoin-address
    """
    # The first character indicates the "version" of the address.
    CHARS_OK_FIRST = "123"
    # alphanumeric characters without : l I O 0
    CHARS_OK = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    # We do not check the high length limit of the adress. 
    if len(strAddr) < 27:
        return False
    if len(strAddr) > 35:
        return False
    if strAddr[0] not in CHARS_OK_FIRST:
        return False
    # We use the function "all" by passing it an enumerator as parameter. 
    # It does a little optimisation : 
    # if one of the character is not valid, the next ones are not tested.
    return all( ( char in CHARS_OK for char in strAddr[1:] ) )

#------------------------------------------------------------------------------ 

def RoundupFile(filename, stepsize):
    """
    For some things we need to have files which are round sizes, 
    for example some encryption needs files that are multiples of 8 bytes.
    This function rounds file up to the next multiple of step size.
    """
    try:
        size = os.path.getsize(filename)
    except:
        return
    mod = size % stepsize
    increase = 0
    if mod > 0:
        increase = stepsize - mod
        file = open(filename, 'a')         
        file.write(' ' * increase)
        file.close()

def AddNL(s):
    """
    Just return a same string but with '\n' symbol at the end. 
    """
    return s + "\n"

def Data():
    """
    An alias for Data packets.
    """
    return "Data"

def Parity():
    """
    An alias for Parity packets.
    """
    return "Parity"

def BinaryToAscii(input):
    """
    Not used right now.
    Have had some troubles with jelly/banana.
    Plan to move to my own serialization of objects but leaving this here for now.
    """
    return base64.encodestring(input)

def AsciiToBinary(input):
    """
    Uses built-in method ``base64.decodestring``.
    """
    return base64.decodestring(input)

def ObjectToString(obj):
    """
    """
    return cPickle.dumps(obj, protocol=cPickle.HIGHEST_PROTOCOL)

def StringToObject(inp):
    """
    """
    return cPickle.loads(inp)

def ObjectToAscii(input):
    """
    Not used.
    """
    return BinaryToAscii(ObjectToString(input))

def AsciiToObject(input):
    """
    Not used.
    """
    return StringToObject(AsciiToBinary(input))              # works for 384 bit RSA keys

#------------------------------------------------------------------------------ 

def pack_url_param(s):
    """
    A wrapper for built-in ``urllib.quote`` method.
    """
    try:
        return urllib.quote(s)
    except:
        try:
            return str(urllib.quote(str(s)))
        except:
            io.exception()
    return s

def unpack_url_param(s, default=None):
    """
    A wrapper for built-in ``urllib.unquote`` method.
    """
    if s is None or s == '':
        if default is not None:
            return default
        return s
    try:
        return urllib.unquote(str(s))
    except:
        io.exception()
        return default

def rndstr(length):
    """
    This generates a random string of given ``length`` - with only digits and letters.
    """
    return ''.join([random.choice(string.letters+string.digits) for i in range(0,length)])

def stringToLong(s):
    """
    Not used.
    """
    return long('\0'+s, 256)

def longToString(n):
    """
    Not used.
    """
    s = n.tostring()
    if s[0] == '\0' and s != '\0':
        s = s[1:]
    return s

def receiptIDstr(receipt_id):
    """
    This method is used to make good string for receipt ID.  
    """
    try:
        return '%08d' % int(receipt_id)
    except:
        return str(receipt_id)

def username2idurl(username, host='id.bitpie.net'):
    """
    Creates an IDURL from given username, default identity server is used.
    """
    return 'http://' + host + '/' + username + '.xml'

def calculate_best_dimension(sz, maxsize=8):
    """
    This method is used to visually organize users on screen.
    Say 4 items is pretty good looking in one line.
    But 13 items seems fine in three lines.
        :param sz: number of items to be organized
        :param maxsize: the maximum width of the matrix. 
    """
    cached = {2: (2,1), 
              4: (4,1),
              7: (4,2),
              13:(5,3),
              18:(6,3),
              26:(7,4),
              64:(8,8)}.get(sz, None)
    if cached:
        return cached
    try:
        w = math.sqrt(sz)
        h = sz / w
    except:
        io.exception()
    w = w * 1.4
    h = h / 1.4
    if int(w) * int(h) < sz and int(h) > 0:
        w += 1.0
    if w > maxsize:
        w = float(maxsize)
        h = sz / w
    w = int(w)
    h = int(h)
    w = 1 if w==0 else w
    h = 1 if h==0 else h
    if w * h < sz:
        h += 1
    if w * h - sz > h:
        w -= 1 
    return w, h

def calculate_padding(w, h):
    """
    Calculates space between icons to show in the GUI. 
    Need to put less spaces when show a lot of items. 
    """
    imgW = 64
    imgH = 64
    if w >= 4:
        imgW = 4 * imgW / w
        imgH = 4 * imgH / w
    padding = 64/w - 8
    return imgW, imgH, padding

def getDeltaTime(tm):
    """
    Return a string shows how much time passed since ``tm`` moment.
    """
    try:
#        tm = time.mktime(time.strptime(self.backupID, "F%Y%m%d%I%M%S%p"))
        dt = round(time.time() - tm)
        if dt > 2*60*60:
            return round(dt/(60.0*60.0)), 'hours'
        if dt > 60:
            return round(dt/60.0), 'minutes'
        return dt, 'seconds'
    except:
        return None, None

def getRealHost(host, port=None):
    """
    Some tricks to get a 'host' from contact method (see ``lib.identity``).
    """
    if isinstance(host, str):
        if host.startswith('http://'):
            host = host[7:]
        elif host.startswith('cspace://'):
            host = host[9:]
        if port is not None:
            host += ':' + str(port)
    elif isinstance(host, tuple) and len(host) == 2:
        host = host[0] + ':' + str(host[1])
    elif host is None:
        host = 'None'
    else:
        if getattr(host, 'host', None) is not None:
            if getattr(host, 'port', None) is not None:
                host = str(getattr(host, 'host')) + ':' + str(getattr(host, 'port'))
            else:
                host = str(getattr(host, 'host'))
        elif getattr(host, 'underlying', None) is not None:
            host = str(getattr(host, 'underlying'))
        else:
            host = str(host)
            if port is not None:
                host += ':' + str(port)
    return host


def split_geom_string(geomstr):
    """
    Split strings created with format "%dx%d+%d+%d" into 4 integers.
    """
    try:
        r = re.split('\D+', geomstr, 4)
        return int(r[0]), int(r[1]), int(r[2]), int(r[3])
    except:
        return None, None, None, None


def percent2string(percent, precis=3):
    """
    A tool to make a string (with % at the end) from given float, ``precis`` is precision to round the number. 
    """
    s = str(round(percent, precis))
    if s[-2:] == '.0':
        s = s[:-2]
    return s + '%'

def float2str(float_value, mask='%6.8f', no_trailing_zeros=True):
    """
    Some smart method to do simple operation - convert float value into string.
    """
    try:
        f = float(float_value)
    except:
        return float_value 
    s = mask % f
    if no_trailing_zeros:
        s = s.rstrip('0').rstrip('.')
    return s

def seconds_to_time_left_string(seconds):
    """
    Using this method you can print briefly some period of time.
    This is my post on StackOverflow to share that:
        http://stackoverflow.com/questions/538666/python-format-timedelta-to-string/19074707#19074707
    """
    s = int(seconds)
    years = s // 31104000
    if years > 1:
        return '%d years' % years
    s = s - (years * 31104000)
    months = s // 2592000
    if years == 1:
        r = 'one year'
        if months > 0:
            r += ' and %d months' % months
        return r
    if months > 1:
        return '%d months' % months
    s = s - (months * 2592000)
    days = s // 86400
    if months == 1:
        r = 'one month'
        if days > 0:
            r += ' and %d days' % days
        return r
    if days > 1:
        return '%d days' % days
    s = s - (days * 86400)
    hours = s // 3600
    if days == 1:
        r = 'one day'
        if hours > 0:
            r += ' and %d hours' % hours
        return r 
    s = s - (hours * 3600)
    minutes = s // 60
    seconds = s - (minutes * 60)
    if hours >= 6:
        return '%d hours' % hours
    if hours >= 1:
        r = '%d hours' % hours
        if hours == 1:
            r = 'one hour'
        if minutes > 0:
            r += ' and %d minutes' % minutes
        return r
    if minutes == 1:
        r = 'one minute'
        if seconds > 0:
            r += ' and %d seconds' % seconds
        return r
    if minutes == 0:
        return '%d seconds' % seconds
    if seconds == 0:
        return '%d minutes' % minutes
    return '%d minutes and %d seconds' % (minutes, seconds)

def unicode_to_str_safe(unicode_string, encodings=None):
    """
    I tried to make an 'ultimate' method to convert unicode to string here. 
    """
    try:
        return str(unicode_string) # .decode('utf-8')
    except:
        try:
            return unicode(unicode_string).encode(locale.getpreferredencoding(), errors='ignore')
        except:
            pass
    if encodings is None:
        encodings = [locale.getpreferredencoding(),] #  'utf-8' 
    output = ''
    for i in xrange(len(unicode_string)):
        unicode_char = unicode_string[i]
        char = '?'
        try:
            char = unicode_char.encode(encodings[0])
            # print char, encodings[0]
        except:
            for encoding in encodings:
                try:
                    char = unicode_char.encode(encoding, errors='ignore')
                    # print char, encoding
                    break
                except:
                    pass
        output += char
    return output

def wrap_long_string(longstring, width=40, wraptext='\n'):
    w = len(longstring)
    if w < width:
        return longstring
    return wraptext.join(textwrap.wrap(longstring, width))

def cut_long_string(longstring, length=40, suffix=''):
    l = len(longstring)
    if l < length:
        return longstring
    return longstring[:length] + suffix

#------------------------------------------------------------------------------

def getClipboardText():
    """
    A portable way to get a clipboard data - some sort of Ctrl-V.  
    """
    if io.Windows():
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
            d = win32clipboard.GetClipboardData(win32con.CF_TEXT)
            win32clipboard.CloseClipboard()
            return d.replace('\r\n','\n')
        except:
            io.exception()
            return ''
    elif io.Linux():
        try:
            import wx
            # may crash, otherwise
            # this needs app.MainLoop() to be started 
            if not wx.TheClipboard.IsOpened():  
                do = wx.TextDataObject()
                wx.TheClipboard.Open()
                success = wx.TheClipboard.GetData(do)
                wx.TheClipboard.Close()
                if success:
                    return do.GetText()
                else:
                    return ''
            else:
                return ''
        except:
            return ''
    else:
        return ''

def setClipboardText(txt):
    """
    A portable way to set a clipboard data - just like when you select something and press Ctrl-C.  
    """
    if io.Windows():
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_TEXT, txt)
            win32clipboard.CloseClipboard()
        except:
            io.exception()
    elif io.Linux():
        try:
            import wx
            clipdata = wx.TextDataObject()
            clipdata.SetText(txt)
            if wx.TheClipboard:
                wx.TheClipboard.Open()
                wx.TheClipboard.SetData(clipdata)
                wx.TheClipboard.Close()
        except:
            io.exception()
    else:
        #TODO
        return
              
#------------------------------------------------------------------------------ 

def isValidTransport(transport):
    """
    Check string to be a valid transport.
    See ``lib.transport_control' for more details.
    """
    global validTransports
    if transport in validTransports:
        return True
    else:
        return False

def validateTransports(orderL):
    """
    Validate a list of strings - all must be a valid transports.
    """
    global validTransports
    transports = []
    for transport in orderL:
        if isValidTransport(transport):
            transports.append(transport)
        else:
            io.log(6, 'misc.validateTransports WARNING invalid entry int transport list: %s , ignored' % str(transport))
    if len(transports) == 0:
        io.log(1, 'misc.validateTransports ERROR no valid transports, using default transports ' + str(validTransports))
        transports = validTransports
#    if len(transports) != len(orderL):
#        io.log(1, 'misc.validateTransports ERROR Transports contained an invalid entry, need to figure out where it came from.')
    return transports

def setTransportOrder(orderL):
    """
    Validate transports and save the list in the [BitPie.NET data dir]\metadata\torder.
    It is useful to remember the priority of used transports. 
    """
    orderl = orderL
    orderL = validateTransports(orderL)
    orderTxt = string.join(orderl, ' ')
    io.log(8, 'misc.setTransportOrder: ' + str(orderTxt))
    io.WriteFile(settings.DefaultTransportOrderFilename(), orderTxt)

def getTransportOrder():
    """
    Read and validate tranports from [BitPie.NET data dir]\metadata\torder file.
    """
    global validTransports
    io.log(8, 'misc.getTransportOrder')
    order = io.ReadTextFile(settings.DefaultTransportOrderFilename()).strip()
    if order == '':
        orderL = validTransports
    else:
        orderL = order.split(' ')
        orderL = validateTransports(orderL)
    setTransportOrder(orderL)
    return orderL

def getOrderFromContacts(ident):
    """
    A wrapper for ``identity.getProtoOrder`` method.
    """
    return ident.getProtoOrder()

#-------------------------------------------------------------------------------

def StartWebStream():
    """
    This calls ``lib.weblog.init`` to start a web server to show the program logs.
    The port number is set in the settings.    
    """
    io.log(6,"misc.StartWebStream")
    import weblog
    weblog.init(settings.getWebStreamPort())
    io.SetWebStream(weblog.log)

def StopWebStream():
    """
    Call ``lib.weblog.shutdown`` to stop a web server. 
    """
    io.log(6,"misc.StopWebStream")
    io.SetWebStream(None)
    import weblog
    weblog.shutdown()

def StartWebTraffic(root=None, path='traffic'):
    """
    Calls ``lib.webtraffic.init`` to run a web server to monitor packets traffic.
    """
    io.log(6,"misc.StartWebStream")
    import lib.webtraffic as webtraffic
    webtraffic.init(root, path, settings.getWebTrafficPort())
    import transport.callback as callback
    callback.add_inbox_callback(webtraffic.inbox)
    callback.add_finish_file_sending_callback(webtraffic.outbox)

def StopWebTraffic():
    """
    Stops web server for traffic montitoring.
    """
    io.log(6,"misc.StopWebTraffic")
    import lib.webtraffic as webtraffic
    webtraffic.shutdown()
    import transport.callback as callback
    callback.remove_inbox_callback(webtraffic.inbox)
    callback.remove_finish_file_sending_callback(webtraffic.outbox)

#------------------------------------------------------------------------------

def hmac_hash(string):
    """
    Not used.
    """
    h = hmac.HMAC(settings.HMAC_key_word(), string)
    return h.hexdigest().upper()

def encode64(s):
    """
    A wrapper for built-in ``base64.b64encode``.
    """
    return base64.b64encode(s)

def decode64(s):
    """
    A wrapper for built-in ``base64.b64decode``.
    """
    return base64.b64decode(s)

def get_hash(src):
    """
    Get a good looking MD5 hash of ``src`` string.
    """
    return hashlib.md5(src).hexdigest()

def file_hash(path):
    """
    Read file and get get its hash.
    """
    src = io.ReadBinaryFile(path)
    if not src:
        return None
    return get_hash(src)

#-------------------------------------------------------------------------------

def time2daystring(tm=None):
    """
    Use built-in method ``time.strftime`` to conver ``tm`` to string in '%Y%m%d' format.
    """
    tm_ = tm
    if tm_ is None:
        tm_ = time.time()
    return time.strftime('%Y%m%d', time.localtime(tm_))

def daystring2time(daystring):
    """
    Reverse method for ``time2daystring``.
    """
    try:
        t = time.strptime(daystring, '%Y%m%d')
    except:
        return None
    return time.mktime(t)

def time2str(format):
    """
    A wrapper for ``time.strftime``.
    """
    return time.strftime(format)

def gmtime2str(format, seconds=None):
    """
    Almost the same to ``time2str``, but uses ``time.gmtime`` to get the current moment.
    """
    if not seconds:
        return time.strftime(format, time.gmtime())
    return time.strftime(format, time.gmtime(seconds))

def str2gmtime(time_string, format):
    """
    A reverse method for ``gmtime2str``.
    """
    return time.mktime(time.strptime(time_string, format))

#------------------------------------------------------------------------------ 

def ReadRepoLocation():
    """
    This method reutrn a tuple of two strings: "name of the current repo" and "repository location".
    """
    if io.Linux():
        repo_file = os.path.join(io.getExecutableDir(), 'repo.txt')
        if os.path.isfile(repo_file):
            src = io.ReadTextFile(repo_file)
            if src:
                try:
                    return src.split('\n')[0].strip(), src.split('\n')[1].strip() 
                except:
                    io.exception()
        return 'sources', 'http://bitpie.net/download.html'
            
    src = io.ReadTextFile(settings.RepoFile()).strip()
    if src == '':
        return settings.DefaultRepo(), settings.UpdateLocationURL(settings.DefaultRepo())
    l = src.split('\n')
    if len(l) < 2:
        return settings.DefaultRepo(), settings.UpdateLocationURL(settings.DefaultRepo())
    return l[0], l[1]   

#-------------------------------------------------------------------------------

def SetAutorunWindows():
    """
    Creates a shortcut in Start->Applications->Startup under Windows, so program can be started during system startup.
    """
    if os.path.abspath(io.getExecutableDir()) != os.path.abspath(settings.WindowsBinDir()):
        return
    createWindowsShortcut(
        'BitPie.NET.lnk',
        '%s' % settings.getIconLaunchFilename(),
        io.getExecutableDir(),
        os.path.join(io.getExecutableDir(), 'icons', settings.IconFilename()),
        '',
        'Startup', )

def ClearAutorunWindows():
    """
    Remove a shortcut from Windows startup menu.
    """
    removeWindowsShortcut('BitPie.NET.lnk', folder='Startup')

#def SetAutorunWindowsOld(CUorLM='CU', location=settings.getAutorunFilename(), name=settings.ApplicationName()):
#    cmdexec = r'reg add HK%s\software\microsoft\windows\currentversion\run /v "%s" /t REG_SZ /d "%s" /f' % (CUorLM, name, location)
#    io.log(6, 'misc.SetAutorunWindows executing: ' + cmdexec)
#    return nonblocking.ExecuteString(cmdexec)

#def ClearAutorunWindowsOld(CUorLM='CU', name = settings.ApplicationName()):
#    cmdexec = r'reg delete HK%s\software\microsoft\windows\currentversion\run /v "%s" /f' % (CUorLM, name)
#    io.log(6, 'misc.ClearAutorunWindows executing: ' + cmdexec)
#    return nonblocking.ExecuteString(cmdexec)

#-------------------------------------------------------------------------------

def transport_control_remove_after():
    """
    Not used.
    """
    global _RemoveAfterSent
    return _RemoveAfterSent

def set_transport_control_remove_after(flag):
    """
    Not used.
    """
    global _RemoveAfterSent
    _RemoveAfterSent = flag

#-------------------------------------------------------------------------------

def pathToWindowsShortcut(filename, folder='Desktop'):
    """
    This should return a path to the "Desktop" folder, creating a files in that folder will show an icons on the desktop.
    """
    try:
        from win32com.client import Dispatch
        shell = Dispatch('WScript.Shell')
        desktop = shell.SpecialFolders(folder)
        return os.path.join(desktop, filename)
    except:
        io.exception()
        return ''

def createWindowsShortcut(filename, target='', wDir='', icon='', args='', folder='Desktop'):
    """
    Creates a shortcut for BitPie.NET on the desktop. 
    """
    if io.Windows():
        try:
            from win32com.client import Dispatch
            shell = Dispatch('WScript.Shell')
            desktop = shell.SpecialFolders(folder)
            path = os.path.join(desktop, filename)
            shortcut = shell.CreateShortCut(path)
            shortcut.Targetpath = target
            shortcut.WorkingDirectory = wDir
            shortcut.Arguments = args
            if icon != '':
                shortcut.IconLocation = icon
            shortcut.save()
        except:
            io.exception()

def removeWindowsShortcut(filename, folder='Desktop'):
    """
    Removes a BitPie.NET shortcut from the desktop.
    """
    if io.Windows():
        path = pathToWindowsShortcut(filename, folder)
        if os.path.isfile(path) and os.access(path, os.W_OK):
            try:
                os.remove(path)
            except:
                io.exception()

#-------------------------------------------------------------------------------

def pathToStartMenuShortcut(filename):
    """
    Path to the Windows start menu folder.
    """
    try:
        from win32com.shell import shell, shellcon
        from win32com.client import Dispatch
        shell_ = Dispatch('WScript.Shell')
        csidl = getattr(shellcon, 'CSIDL_PROGRAMS')
        startmenu = shell.SHGetSpecialFolderPath(0, csidl, False)
        return os.path.join(startmenu, filename)
    except:
        io.exception()
        return ''

def createStartMenuShortcut(filename, target='', wDir='', icon='', args=''):
    """
    Create a BitPie.NET shortcut in the Windows start menu.
    """
    if io.Windows():
        try:
            from win32com.shell import shell, shellcon
            from win32com.client import Dispatch
            shell_ = Dispatch('WScript.Shell')
            csidl = getattr(shellcon, 'CSIDL_PROGRAMS')
            startmenu = shell.SHGetSpecialFolderPath(0, csidl, False)
            path = os.path.join(startmenu, filename)
            shortcut = shell_.CreateShortCut(path)
            shortcut.Targetpath = target
            shortcut.WorkingDirectory = wDir
            shortcut.Arguments = args
            if icon != '':
                shortcut.IconLocation = icon
            shortcut.save()
        except:
            io.exception()

def removeStartMenuShortcut(filename):
    """
    Remove a shortcut from Windows start menu.
    """
    if io.Windows():
        path = pathToStartMenuShortcut(filename)
        if os.path.isfile(path) and os.access(path, os.W_OK):
            try:
                os.remove(path)
            except:
                io.exception()
    return

#------------------------------------------------------------------------------ 

def DoRestart(param=''):
    """
    A smart and portable way to restart a whole program.
    """
    if io.Windows():
        if io.isFrozen():
            io.log(2, "misc.DoRestart under Windows (Frozen), param=%s" % param)
            io.log(2, "misc.DoRestart sys.executable=" + sys.executable)
            io.log(2, "misc.DoRestart sys.argv=" + str(sys.argv))
            starter_filepath = os.path.join(io.getExecutableDir(), settings.WindowsStarterFileName())
            if not os.path.isfile(starter_filepath):
                io.log(2, "misc.DoRestart ERROR %s not found" % starter_filepath)
                return
            cmdargs = [os.path.basename(starter_filepath),]
            if param != '':
                cmdargs.append(param)
            io.log(2, "misc.DoRestart cmdargs="+str(cmdargs))
            os.spawnve(os.P_DETACH, starter_filepath, cmdargs, os.environ)

        else:
            io.log(2, "misc.DoRestart under Windows param=%s" % param)
            io.log(2, "misc.DoRestart sys.executable=" + sys.executable)
            io.log(2, "misc.DoRestart sys.argv=" + str(sys.argv))

            pypath = sys.executable
            cmdargs = [sys.executable]
            cmdargs.append(sys.argv[0])
            cmdargs += sys.argv[1:]
            if param != '' and not sys.argv.count(param):
                cmdargs.append(param)
            if cmdargs.count('restart'):
                cmdargs.remove('restart')

            io.log(2, "misc.DoRestart cmdargs="+str(cmdargs))
            # os.spawnve(os.P_DETACH, pypath, cmdargs, os.environ)
            os.execvpe(pypath, cmdargs, os.environ)

    else:
        io.log(2, "misc.DoRestart under Linux param=%s" % param)
        io.log(2, "misc.DoRestart sys.executable=" + sys.executable)
        io.log(2, "misc.DoRestart sys.argv=" + str(sys.argv))
        
        pypyth = sys.executable
        cmdargs = [sys.executable]
        if sys.argv[0] == '/usr/share/bitpie/bitpie.py':
            cmdargs.append('/usr/bin/bitpie')
        else:
            cmdargs.append(sys.argv[0])
        if param:
            cmdargs.append(param)

        pid = os.fork()
        if pid == 0:
            io.log(2, "misc.DoRestart cmdargs="+str(cmdargs))
            os.execvpe(pypyth, cmdargs, os.environ)
        else:
            io.log(2, "misc.DoRestart os.fork returned "+str(pid))
            
            
def RunBatFile(filename, output_filename=None):
    """
    Can execute a bat file under Windows.
    """
    if not io.Windows():
        return
    io.log(0, 'misc.RunBatFile going to execute ' + str(filename))

    cmd = os.path.abspath(filename).replace('\\', '/')
    if output_filename is not None:
        cmd += ' >"%s"' % os.path.abspath(output_filename).replace('\\', '/')

    return RunShellCommand(cmd, False)


def RunShellCommand(cmdstr, wait=True):
    """
    This uses ``subprocess.Popen`` to execute a process. 
        :param cmdstr: a full command line ( with arguments ) to execute.
        :param wait: if True - the main process will be blocked until child is finished.
    """
    io.log(8, 'misc.RunShellCommand ' + cmdstr)
    try:
        if io.Windows():
            import win32process
            p = subprocess.Popen(
                cmdstr,
                shell=True,
                creationflags = win32process.CREATE_NO_WINDOW,)
        else:
            p = subprocess.Popen(
                cmdstr,
                shell=True,)
    except:
        io.exception()
        return None
    if wait:
        try:
            result = p.wait()
        except:
            io.exception()
            return None
    else:
        return p.pid
    return result


def ExplorePathInOS(filepath):
    """
    Very nice and portable way to show location or file on local disk. 
    """
    try:
        if io.Windows():
            # os.startfile(filepath)
            if os.path.isfile(filepath):
                subprocess.Popen(['explorer', '/select,', '%s' % (filepath.replace('/','\\'))])
            else:
                subprocess.Popen(['explorer', '%s' % (filepath.replace('/','\\'))])

        elif io.Linux():
            subprocess.Popen(['xdg-open', filepath])

        elif io.Mac():
            subprocess.Popen(['open', filepath])

    except:
        try:
            import webbrowser
            webbrowser.open(filepath)
        except:
            io.exception()
    return


def MoveFolderWithFiles(current_dir, new_dir, remove_old=False):
    """
    The idea was to be able to move the files inside the donated area to another location.
    Say, user want to switch our software to donate space from another HDD. 
    At the moment this feature is off.
    """
    if os.path.abspath(current_dir) == os.path.abspath(new_dir):
        return None
    
    current = cmdLineQuote(current_dir)
    new = cmdLineQuote(new_dir)
    
    try:
        if io.Linux():
            cmdargs = ['cp', '-r', current, new]
            io.log(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdargs))
            subprocess.call(cmdargs)
            if remove_old:
                cmdargs = ['rm', '-r', current]
                io.log(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdargs))
                subprocess.call(cmdargs)
            return 'ok'
    
        if io.Windows():
            cmdstr0 = 'mkdir %s' % new
            cmdstr1 = 'xcopy %s %s /E /K /R /H /Y' % (cmdLineQuote(os.path.join(current_dir, '*.*')), new)
            cmdstr2 = 'rmdir /S /Q %s' % current
            if not os.path.isdir(new):
                io.log(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdstr0))
                if RunShellCommand(cmdstr0) is None:
                    return 'error'
                io.log(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdstr1))
            if RunShellCommand(cmdstr1) is None:
                return 'error'
            if remove_old:
                io.log(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdstr2))
                if RunShellCommand(cmdstr2) is None:
                    return 'error'
            return 'ok'
        
    except:
        io.exception()
        return 'failed'
    
    return 'ok'

#------------------------------------------------------------------------------

#def UpdateDesktopShortcut():
#    """
#    Called at startup to update BitPie.NET shortcut on the desktop.
#    I was playing with that, tried to keep the shortcut on the desktop always (even if user removes it).
#    This is switched off now, it was very anoying for one my friend who install the software.
#    """
#    io.log(6, 'misc.UpdateDesktopShortcut')
#    if io.Windows() and io.isFrozen():
#        if settings.getGeneralDesktopShortcut():
#            if not os.path.exists(pathToWindowsShortcut(settings.getIconLinkFilename())):
#                createWindowsShortcut(
#                    settings.getIconLinkFilename(),
#                    '%s' % settings.getIconLaunchFilename(),
#                    io.getExecutableDir(),
#                    os.path.join(io.getExecutableDir(), 'icons', settings.IconFilename()),
#                    'show' )
#        else:
#            if os.path.exists(pathToWindowsShortcut(settings.getIconLinkFilename())):
#                removeWindowsShortcut(settings.getIconLinkFilename())
#
#
#def UpdateStartMenuShortcut():
#    """
#    Update icons in the start menu, switched off right now.
#    """
#    io.log(6, 'misc.UpdateStartMenuShortcut')
#    if io.Windows() and io.isFrozen():
#        if settings.getGeneralStartMenuShortcut():
#            if not os.path.exists(pathToStartMenuShortcut(settings.getIconLinkFilename())):
#                createStartMenuShortcut(
#                    settings.getIconLinkFilename(),
#                    '%s' % settings.getIconLaunchFilename(),
#                    io.getExecutableDir(),
#                    os.path.join(io.getExecutableDir(), 'icons', settings.IconFilename()),
#                    'show' )
#        else:
#            if os.path.exists(pathToStartMenuShortcut(settings.getIconLinkFilename())):
#                removeStartMenuShortcut('Data Haven .NET.lnk')


def UpdateSettings():
    """
    This method is called at startup, during "local initialization" part, 
    see ``p2p.init_shutdown.init_local()`` method.
    I used that place sometimes to 'patch' users settings.
    """
    io.log(6, 'misc.UpdateSettings')

#-------------------------------------------------------------------------------

def SendDevReportOld(subject, body, includelogs):
    """
    The old stuff to send dev. reports.
    """
    try:
        filesList = []
        if includelogs:
            filesList.append(settings.LocalIdentityFilename())
            filesList.append(settings.UserConfigFilename())
            filesList.append(os.path.join(io.getExecutableDir(), 'bpmain.exe.log'))
            filesList.append(os.path.join(io.getExecutableDir(), 'bpmain.log'))
            for filename in os.listdir(settings.LogsDir()):
                filepath = os.path.join(settings.LogsDir(), filename)
                filesList.append(filepath)
        if len(filesList) > 0:
            import zipfile
            import time
            username = io.ReadTextFile(settings.UserNameFilename())
            zipfd, zipfilename = tempfile.mkstemp('.zip', username+'-'+time.strftime('%Y%m%d%I%M%S')+'-' )
            zfile = zipfile.ZipFile(zipfilename, "w", compression=zipfile.ZIP_DEFLATED)
            for filename in filesList:
                if os.path.isfile(filename):
                    try:
                        if os.path.getsize(filename) < 1024*512:
                            zfile.write(filename, os.path.basename(filename))
                    except:
                        pass
            zfile.close()
            filesList = [zipfilename]    
        net_misc.SendEmail(
            'to@mail',
            'from@mail',
            'smtp.gmail.com',
            587,
            'user',
            'password',
            subject,
            body,
            filesList,)
    except:
        io.exception()
        

def SendDevReport(subject, body, includelogs, progress=None, receiverDeferred=None):
    """
    Send a developer report to our public cgi script at:
        http://bitpie.net/cgi-bin/feedback.py
    It should record it and so I can get your message and ( optional ) your logs.
        TODO:
            This seems to be not working correct yet.
            The process may not finish for big data, and progress is not shown correctly.
    """
    try:
        zipfilename = ''
        filesList = []
        if includelogs:
            filesList.append(settings.LocalIdentityFilename())
            filesList.append(settings.UserConfigFilename())
            filesList.append(os.path.join(io.getExecutableDir(), 'bpmain.exe.log'))
            filesList.append(os.path.join(io.getExecutableDir(), 'bpmain.log'))
            for filename in os.listdir(settings.LogsDir()):
                filepath = os.path.join(settings.LogsDir(), filename)
                filesList.append(filepath)
        if len(filesList) > 0:
            import zipfile
            import time
            username = io.ReadTextFile(settings.UserNameFilename())
            zipfd, zipfilename = tempfile.mkstemp('.zip', username+'-'+time.strftime('%Y%m%d%I%M%S')+'-' )
            zfile = zipfile.ZipFile(zipfilename, "w", compression=zipfile.ZIP_DEFLATED)
            for filename in filesList:
                if os.path.isfile(filename):
                    try:
                        # if os.path.getsize(filename) < 1024*1024*10:
                        zfile.write(filename, os.path.basename(filename))
                    except:
                        pass
            zfile.close()
        files = {}
        if zipfilename:
            files['upload'] = zipfilename
        data = {'subject': subject, 'body': body}
        net_misc.uploadHTTP('http://bitpie.net/cgi-bin/feedback.py', files, data, progress, receiverDeferred)            
        return True 
    except:
        io.exception()
    return False

#------------------------------------------------------------------------------ 

def GetUserProfilePicturePath():
    """
    Not used right now.
    I wish to show some personal images instead of green or gray boys.
    Users can provide own avatars, but more smart way is to take that avatar from user private space.
    This should be used only during first install of the program. 
    May be we can use facebook or google personal page to get the picture.
    The idea was taken from: 
        http://social.msdn.microsoft.com/Forums/en/vcgeneral/thread/8c72b948-d32c-4785-930e-0d6fdf032ecc
    For linux we just check the file ~/.face.
    Than user can upload his avatar to some place (we can store avatars for free) 
    and set that url into his identity - so others can get his avatar very easy.
    """
    if io.Windows():
        
        username = os.path.basename(os.path.expanduser('~'))
        if io.windows_version() == 5: # Windows XP
            # %ALLUSERSPROFILE%\Application Data\Microsoft\User Account Pictures
            allusers = os.environ.get('ALLUSERSPROFILE', os.path.join(os.path.dirname(os.path.expanduser('~')), 'All Users'))
            return os.path.join(allusers, 'Application Data', 'Microsoft', 'User Account Pictures', username+'.bmp')
        elif io.windows_version() == 6: # Windows 7
            # C:\Users\<username>\AppData\Local\Temp\<domain>+<username>.bmp 
            default_path = os.path.join(os.path.expanduser('~'), 'Application Data')
            return os.path.join(os.environ.get('APPDATA', default_path), 'Local', 'Temp', username+'.bmp')
        else:
            return ''
    elif io.Linux():
        return os.path.join(os.path.expanduser('~'), '.face')
    return ''

def UpdateRegistryUninstall(uninstall=False):
    """
    This is not used right now.
    Now BitPie.NET is installed via .msi file and we do all that stuff inside it.
    """
    try:
        import _winreg
    except:
        return False
    unistallpath = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall" 
    regpath = unistallpath + "\\BitPie.NET"
    values = {
        'DisplayIcon':      '%s,0' % str(io.getExecutableFilename()),
        'DisplayName':      'BitPie.NET',
        'DisplayVersion':   'rev'+io.ReadTextFile(settings.RevisionNumberFile()).strip(),
        'InstallLocation:': settings.BaseDir(),
        'NoModify':         1,
        'NoRepair':         1,
        'UninstallString':  '%s uninstall' % io.getExecutableFilename(),
        'URLInfoAbout':     'http://bitpie.net', }    
    # open
    try:
        reg = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, regpath, 0, _winreg.KEY_ALL_ACCESS)
    except:
        try:
            reg = _winreg.CreateKey(_winreg.HKEY_LOCAL_MACHINE, regpath)
        except:
            io.exception()
            return False
    # check
    i = 0
    while True:
        try:
            name, value, typ = _winreg.EnumValue(reg, i)
        except:
            break
        i += 1
        if uninstall:
            try:
                _winreg.DeleteKey(reg, name)
            except:
                try:
                    _winreg.DeleteValue(reg, name)
                except:
                    io.exception()
        else:
            if name == 'DisplayName' and value == 'BitPie.NET':
                _winreg.CloseKey(reg)
                return True
    # delete
    if uninstall:
        _winreg.CloseKey(reg)
        try:
            reg = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, unistallpath, 0, _winreg.KEY_ALL_ACCESS)
        except:
            io.exception()
            return False
        try:
            _winreg.DeleteKey(reg, 'BitPie.NET')
        except:
            io.exception()
            _winreg.CloseKey(reg)
            return False
        _winreg.CloseKey(reg)
        return True
    # write
    for key, value in values.items():
        typ = _winreg.REG_SZ
        if isinstance(value, int):
            typ = _winreg.REG_DWORD
        _winreg.SetValueEx(reg, key, 0, typ, value)
    _winreg.CloseKey(reg)
    return True


def MakeBatFileToUninstall(wait_appname='bpmain.exe', local_dir=io.getExecutableDir(), dirs2delete=[settings.BaseDir(),]):
    """
    Not used.
    """
    io.log(0, 'misc.MakeBatFileToUninstall')
    batfileno, batfilename = tempfile.mkstemp('.bat', 'BitPie.NET-uninstall-')
    batsrc = ''
    batsrc += 'cd "%s"\n' % local_dir
    batsrc += 'del search.log /Q\n'
    batsrc += ':again\n'
    batsrc += 'sleep 1\n'
    batsrc += 'tasklist /FI "IMAGENAME eq %s" /FO CSV > search.log\n' % wait_appname
    batsrc += 'FOR /F %%A IN (search.log) DO IF %%-zA EQU 0 GOTO again\n'
#    batsrc += 'start /B /D"%s" %s\n' % (local_dir, start_cmd)
#    batsrc += 'start /B /D"%s" %s\n' % (io.shortPath(local_dir), start_cmd)
    for dirpath in dirs2delete:
        batsrc += 'rmdir /S /Q "%s"\n' % os.path.abspath(dirpath)
    batsrc += 'del /F /S /Q "%s"\n' % os.path.abspath(batfilename)
    print batsrc
    os.write(batfileno, batsrc)
    os.close(batfileno)
    return os.path.abspath(batfilename)

#------------------------------------------------------------------------------

def LoopAttenuation(current_delay, faster, min, max):
    """
    Pretty common method.
    Twisted reactor is very nice, you can call ``reactor.callLater(3, method_a, 'param1')`` 
    and method_a('param1') will be called exactly when 3 seconds passed.
    But we do not want fixed periods sometimes. 
    You must be hury when you have a lot of work, in the next moment - need rest.
    For example - need to read some queue as fast as possible when you have some items inside.
    This method is used to calculate the delay to the next call of some 'idle' method.
        :param current_delay: current period of time in seconds between calls 
        :param faster:  if this is True - method should return ``min`` period - call next time as soon as possible
                        if this is False - method will multiply ``current_delay`` by ``_AttenuationFactor`` and so decrease the speed 
        :param min: the minimum delay between calls
        :param max: the maximum delay between calls
    """
    global _AttenuationFactor
    if faster:
        return min
    else:
        if current_delay < max:
            return current_delay * _AttenuationFactor   
    return current_delay

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    io.SetDebug(10)
    io.init()
    init()

    if True:
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred        
        def _progress(x, y):
            print '%d/%d' % (x,y)      
        def _done(x):
            print 'DONE', x
            reactor.stop()  
        d = Deferred()
        d.addBoth(_done)
        SendDevReport('subject ', 'some body112', True, _progress, d)
        reactor.run()
        
