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
 
TODO: 
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

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------ 

from logs import lg 

from userid import identity

from system import bpio

from main import settings

import net_misc
import packetid

#------------------------------------------------------------------------------ 

_RemoveAfterSent = True

# Functions outside should use getLocalIdentity()

# if we come up with more valid transports,
# we'll need to add them here
# in the case we don't have any valid transports,
# we use this array as the default
# order is important!
# this is default order to be used for new users
# more stable transports must be higher
_AttenuationFactor = 2.0

#-------------------------------------------------------------------------------

def init():
    """
    Will be called in main thread at start up.
    Can put here some minor things if needed.
    """
    lg.out(4, 'misc.init')

#------------------------------------------------------------------------------ 

def readLocalIP():
    """
    Read local IP stored in the file [BitDust data dir]/metadata/localip.
    """
    return bpio.ReadBinaryFile(settings.LocalIPFilename())

def readExternalIP():
    """
    Read external IP stored in the file [BitDust data dir]/metadata/externalip.
    """
    return bpio.ReadBinaryFile(settings.ExternalIPFilename())

def readSupplierData(idurl, filename):
    """
    Read a file from [BitDust data dir]/suppliers/[IDURL] folder.
    The file names right now is ['connected', 'disconnected', 'listfiles']. 
    """
    path = settings.SupplierPath(idurl, filename)
    if not os.path.isfile(path):
        return ''
    return bpio.ReadTextFile(path)

def writeSupplierData(idurl, filename, data):
    """
    Writes to a config file for given supplier.
    """
    dirPath = settings.SupplierPath(idurl)
    if not os.path.isdir(dirPath):
        os.makedirs(dirPath)
    path = settings.SupplierPath(idurl, filename)
    return bpio.WriteFile(path, data)

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
        lg.warn('time.strftime("%p") returns empty string')
        ampm = 'AM' if time.time() % 86400 < 43200 else 'PM'
    result = "F" + time.strftime("%Y%m%d%I%M%S", time_st) + ampm
    return result

def TimeStructFromVersion(backupID):
    """
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
        return st_time
    except:
        lg.exc()
        return None

def TimeFromBackupID(backupID):
    """
    Reverse method - return a date and time from given BackupID with ``time.mktime()``.
    """
    try:
        return time.mktime(TimeStructFromVersion(backupID))
    except:
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
        lg.exc()
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
    fp = bpio.portablePath(filepath)
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
#                        lg.exc()
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
    return True

def ValidNickName(username):
    """
    A method to validate account name entered by user.
    """
    if len(username) < settings.MinimumUsernameLength():
        return False
    if len(username) > settings.MaximumUsernameLength():
        return False
    # for c in username:
    #     if c not in settings.LegalNickNameChars():
    #         return False
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
        fil = open(filename, 'a')         
        fil.write(' ' * increase)
        fil.close()

def RoundupString(data, stepsize):
    """
    """
    size = len(data)
    mod = size % stepsize
    increase = 0
    addon = ''
    if mod > 0:
        increase = stepsize - mod
        addon = ' ' * increase
    return data + addon

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

def ObjectToString_old(obj):
    """
    """
    return cPickle.dumps(obj, protocol=cPickle.HIGHEST_PROTOCOL)

def StringToObject_old(inp):
    """
    """
    return cPickle.loads(inp)

def ObjectToString(obj):
    """
    """
    import serialization
    return serialization.ObjectToString(obj)
    
    
def StringToObject(inp):
    """
    """
    import serialization
    return serialization.StringToObject(inp)


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
            lg.exc()
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
        lg.exc()
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

def username2idurl(username, host='id.bitdust.io'):
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
        lg.exc()
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
    s = float2str(round(percent, precis),
                  mask=("%%3.%df" % (precis+2)))
    # if s[-2:] == '.0':
    #     s = s[:-2]
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

def isEnglishString(s):
    try:
        s.decode('ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True

#------------------------------------------------------------------------------

def getClipboardText():
    """
    A portable way to get a clipboard data - some sort of Ctrl-V.  
    """
    if bpio.Windows():
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
            d = win32clipboard.GetClipboardData(win32con.CF_TEXT)
            win32clipboard.CloseClipboard()
            return d.replace('\r\n','\n')
        except:
            lg.exc()
            return ''
    elif bpio.Linux():
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
    if bpio.Windows():
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_TEXT, txt)
            win32clipboard.CloseClipboard()
        except:
            lg.exc()
    elif bpio.Linux():
        try:
            import wx
            clipdata = wx.TextDataObject()
            clipdata.SetText(txt)
            if wx.TheClipboard:
                wx.TheClipboard.Open()
                wx.TheClipboard.SetData(clipdata)
                wx.TheClipboard.Close()
        except:
            lg.exc()
    elif bpio.Mac():
#         import tempfile
#         fd, fname = tempfile.mkstemp()
#         fd.write(txt)
#         fd.close()
#         subprocess.Popen('')
#         os.system('cat %s | pbcopy')
        #TODO
        return

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
    src = bpio.ReadBinaryFile(path)
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
    if bpio.Linux() or bpio.Mac():
        repo_file = os.path.join(bpio.getExecutableDir(), 'repo')
        if os.path.isfile(repo_file):
            src = bpio.ReadTextFile(repo_file)
            if src:
                try:
                    return src.split('\n')[0].strip(), src.split('\n')[1].strip() 
                except:
                    lg.exc()
        return 'sources', 'http://bitdust.io/download/'
    src = bpio.ReadTextFile(settings.RepoFile()).strip()
    if src == '':
        return settings.DefaultRepo(), settings.DefaultRepoURL(settings.DefaultRepo())
    l = src.split('\n')
    if len(l) < 2:
        return settings.DefaultRepo(), settings.DefaultRepoURL(settings.DefaultRepo())
    return l[0], l[1]   

#-------------------------------------------------------------------------------

def SetAutorunWindows():
    """
    Creates a shortcut in Start->Applications->Startup under Windows, so program can be started during system startup.
    """
    if os.path.abspath(bpio.getExecutableDir()) != os.path.abspath(settings.WindowsBinDir()):
        return
    createWindowsShortcut(
        'BitDust.lnk',
        '%s' % settings.getIconLaunchFilename(),
        bpio.getExecutableDir(),
        os.path.join(bpio.getExecutableDir(), 'icons', settings.IconFilename()),
        '',
        'Startup', )

def ClearAutorunWindows():
    """
    Remove a shortcut from Windows startup menu.
    """
    removeWindowsShortcut('BitDust.lnk', folder='Startup')

#def SetAutorunWindowsOld(CUorLM='CU', location=settings.getAutorunFilename(), name=settings.ApplicationName()):
#    cmdexec = r'reg add HK%s\software\microsoft\windows\currentversion\run /v "%s" /t REG_SZ /d "%s" /f' % (CUorLM, name, location)
#    lg.out(6, 'misc.SetAutorunWindows executing: ' + cmdexec)
#    return nonblocking.ExecuteString(cmdexec)

#def ClearAutorunWindowsOld(CUorLM='CU', name = settings.ApplicationName()):
#    cmdexec = r'reg delete HK%s\software\microsoft\windows\currentversion\run /v "%s" /f' % (CUorLM, name)
#    lg.out(6, 'misc.ClearAutorunWindows executing: ' + cmdexec)
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
        lg.exc()
        return ''

def createWindowsShortcut(filename, target='', wDir='', icon='', args='', folder='Desktop'):
    """
    Creates a shortcut for BitDust on the desktop. 
    """
    if bpio.Windows():
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
            lg.exc()

def removeWindowsShortcut(filename, folder='Desktop'):
    """
    Removes a BitDust shortcut from the desktop.
    """
    if bpio.Windows():
        path = pathToWindowsShortcut(filename, folder)
        if os.path.isfile(path) and os.access(path, os.W_OK):
            try:
                os.remove(path)
            except:
                lg.exc()

#-------------------------------------------------------------------------------

def pathToStartMenuShortcut(filename):
    """
    Path to the Windows start menu folder.
    """
    try:
        from win32com.shell import shell, shellcon #@UnresolvedImport
        from win32com.client import Dispatch
        shell_ = Dispatch('WScript.Shell') 
        csidl = getattr(shellcon, 'CSIDL_PROGRAMS')
        startmenu = shell.SHGetSpecialFolderPath(0, csidl, False)
        return os.path.join(startmenu, filename)
    except:
        lg.exc()
        return ''

def createStartMenuShortcut(filename, target='', wDir='', icon='', args=''):
    """
    Create a BitDust shortcut in the Windows start menu.
    """
    if bpio.Windows():
        try:
            from win32com.shell import shell, shellcon #@UnresolvedImport
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
            lg.exc()

def removeStartMenuShortcut(filename):
    """
    Remove a shortcut from Windows start menu.
    """
    if bpio.Windows():
        path = pathToStartMenuShortcut(filename)
        if os.path.isfile(path) and os.access(path, os.W_OK):
            try:
                os.remove(path)
            except:
                lg.exc()
    return

#------------------------------------------------------------------------------ 

def DoRestart(param='', detach=False):
    """
    A smart and portable way to restart a whole program.
    """
    if bpio.Windows():
        if bpio.isFrozen():
            # lg.out(2, "misc.DoRestart under Windows (Frozen), param=%s" % param)
            # lg.out(2, "misc.DoRestart sys.executable=" + sys.executable)
            # lg.out(2, "misc.DoRestart sys.argv=" + str(sys.argv))
            starter_filepath = os.path.join(bpio.getExecutableDir(), settings.WindowsStarterFileName())
            if not os.path.isfile(starter_filepath):
                # lg.out(2, "misc.DoRestart ERROR %s not found" % starter_filepath)
                main_filepath = os.path.join(bpio.getExecutableDir(), settings.WindowsMainScritpFileName())
                cmdargs = [os.path.basename(main_filepath),]
                if param != '':
                    cmdargs.append(param)
                # lg.out(2, "misc.DoRestart cmdargs="+str(cmdargs))
                return os.spawnve(os.P_DETACH, main_filepath, cmdargs, os.environ)
            cmdargs = [os.path.basename(starter_filepath),]
            if param != '':
                cmdargs.append(param)
            # lg.out(2, "misc.DoRestart cmdargs="+str(cmdargs))
            return os.spawnve(os.P_DETACH, starter_filepath, cmdargs, os.environ)

        else:
            lg.out(2, "misc.DoRestart under Windows param=%s" % param)
            lg.out(2, "misc.DoRestart sys.executable=" + sys.executable)
            lg.out(2, "misc.DoRestart sys.argv=" + str(sys.argv))
            pypath = sys.executable
            cmdargs = [sys.executable]
            cmdargs.append(sys.argv[0])
            cmdargs += sys.argv[1:]
            if param != '' and not sys.argv.count(param):
                cmdargs.append(param)
            if cmdargs.count('restart'):
                cmdargs.remove('restart')
            if cmdargs.count('detach'):
                cmdargs.remove('detach')
            if detach:
                from system import child_process
                lg.out(0, 'run "%s"' % str(' '.join(cmdargs)))
                return child_process.detach(cmdargs)
            lg.out(2, "misc.DoRestart cmdargs="+str(cmdargs))
            return os.execvpe(pypath, cmdargs, os.environ)

    else:
        lg.out(2, "misc.DoRestart under Linux param=%s" % param)
        lg.out(2, "misc.DoRestart sys.executable=" + sys.executable)
        lg.out(2, "misc.DoRestart sys.argv=" + str(sys.argv))
        pypyth = sys.executable
        cmdargs = [sys.executable]
        if sys.argv[0] == '/usr/share/bitdust/bitdust.py':
            cmdargs.append('/usr/bin/bitdust')
        else:
            cmdargs.append(sys.argv[0])
        if param:
            cmdargs.append(param)
        if cmdargs.count('restart'):
            cmdargs.remove('restart')
        if cmdargs.count('detach'):
            cmdargs.remove('detach')
        pid = os.fork()
        if pid != 0:
            lg.out(2, "misc.DoRestart os.fork returned: "+str(pid))
            return None
        if detach:
        #     from lib import child_process
        #     return child_process.detach(cmdargs)
            # return os.spawnv(os.P_DETACH, pypath, cmdargs)
            cmdargs[1] = os.path.abspath(cmdargs[1])
            # cmdargs.insert(0, '/usr/bin/nohup')
            cmdargs.append('1>/dev/null')
            cmdargs.append('2>/dev/null')
            # return os.spawnve(os.P_NOWAIT, '/usr/bin/nohup', cmdargs, os.environ)
            cmd = 'nohup ' + (' '.join(cmdargs)) + ' &'
            # lg.out(0, 'run "%s"' % cmd)
            return os.system(cmd)
        lg.out(2, "misc.DoRestart cmdargs="+str(cmdargs))
        return os.execvpe(pypyth, cmdargs, os.environ)
            
def RunBatFile(filename, output_filename=None):
    """
    Can execute a bat file under Windows.
    """
    if not bpio.Windows():
        return
    lg.out(0, 'misc.RunBatFile going to execute ' + str(filename))

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
    lg.out(8, 'misc.RunShellCommand ' + cmdstr)
    try:
        if bpio.Windows():
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
        lg.exc()
        return None
    if wait:
        try:
            result = p.wait()
        except:
            lg.exc()
            return None
    else:
        return p.pid
    return result


def ExplorePathInOS(filepath):
    """
    Very nice and portable way to show location or file on local disk. 
    """
    try:
        if bpio.Windows():
            # os.startfile(filepath)
            if os.path.isfile(filepath):
                subprocess.Popen(['explorer', '/select,', '%s' % (filepath.replace('/','\\'))])
            else:
                subprocess.Popen(['explorer', '%s' % (filepath.replace('/','\\'))])

        elif bpio.Linux():
            subprocess.Popen(['`which xdg-open`', filepath])
            
        elif bpio.Mac():
            subprocess.Popen(["open", "-R", filepath])

    except:
        try:
            import webbrowser
            webbrowser.open(filepath)
        except:
            lg.exc()
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
        if bpio.Linux():
            cmdargs = ['cp', '-r', current, new]
            lg.out(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdargs))
            subprocess.call(cmdargs)
            if remove_old:
                cmdargs = ['rm', '-r', current]
                lg.out(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdargs))
                subprocess.call(cmdargs)
            return 'ok'
    
        if bpio.Windows():
            cmdstr0 = 'mkdir %s' % new
            cmdstr1 = 'xcopy %s %s /E /K /R /H /Y' % (cmdLineQuote(os.path.join(current_dir, '*.*')), new)
            cmdstr2 = 'rmdir /S /Q %s' % current
            if not os.path.isdir(new):
                lg.out(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdstr0))
                if RunShellCommand(cmdstr0) is None:
                    return 'error'
                lg.out(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdstr1))
            if RunShellCommand(cmdstr1) is None:
                return 'error'
            if remove_old:
                lg.out(4, 'misc.MoveFolderWithFiles wish to call: ' + str(cmdstr2))
                if RunShellCommand(cmdstr2) is None:
                    return 'error'
            return 'ok'
        
        if bpio.Mac():
            # TODO
            return 'error'
        
    except:
        lg.exc()
        return 'failed'
    
    return 'ok'

#------------------------------------------------------------------------------

#def UpdateDesktopShortcut():
#    """
#    Called at startup to update BitDust shortcut on the desktop.
#    I was playing with that, tried to keep the shortcut on the desktop always (even if user removes it).
#    This is switched off now, it was very anoying for one my friend who install the software.
#    """
#    lg.out(6, 'misc.UpdateDesktopShortcut')
#    if bpio.Windows() and bpio.isFrozen():
#        if settings.getGeneralDesktopShortcut():
#            if not os.path.exists(pathToWindowsShortcut(settings.getIconLinkFilename())):
#                createWindowsShortcut(
#                    settings.getIconLinkFilename(),
#                    '%s' % settings.getIconLaunchFilename(),
#                    bpio.getExecutableDir(),
#                    os.path.join(bpio.getExecutableDir(), 'icons', settings.IconFilename()),
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
#    lg.out(6, 'misc.UpdateStartMenuShortcut')
#    if bpio.Windows() and bpio.isFrozen():
#        if settings.getGeneralStartMenuShortcut():
#            if not os.path.exists(pathToStartMenuShortcut(settings.getIconLinkFilename())):
#                createStartMenuShortcut(
#                    settings.getIconLinkFilename(),
#                    '%s' % settings.getIconLaunchFilename(),
#                    bpio.getExecutableDir(),
#                    os.path.join(bpio.getExecutableDir(), 'icons', settings.IconFilename()),
#                    'show' )
#        else:
#            if os.path.exists(pathToStartMenuShortcut(settings.getIconLinkFilename())):
#                removeStartMenuShortcut('Data Haven .NET.lnk')


def UpdateSettings():
    """
    This method is called at startup, during "local initialization" part.
    I used that place sometimes to 'patch' users settings on clients.
    """
    lg.out(6, 'misc.UpdateSettings')

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
            filesList.append(os.path.join(bpio.getExecutableDir(), 'bpmain.exe.log'))
            filesList.append(os.path.join(bpio.getExecutableDir(), 'bpmain.log'))
            for filename in os.listdir(settings.LogsDir()):
                filepath = os.path.join(settings.LogsDir(), filename)
                filesList.append(filepath)
        if len(filesList) > 0:
            import zipfile
            import time
            username = bpio.ReadTextFile(settings.UserNameFilename())
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
        lg.exc()
        

def SendDevReport(subject, body, includelogs, progress=None):
    """
    Send a developer report to our public cgi script at:
        http://bitdust.io/cgi-bin/feedback.py
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
            filesList.append(os.path.join(bpio.getExecutableDir(), 'bpmain.exe.log'))
            filesList.append(os.path.join(bpio.getExecutableDir(), 'bpmain.log'))
            lst = os.listdir(settings.LogsDir())
            lst.sort(key=lambda fn: os.path.getatime(os.path.join(settings.LogsDir(),fn)), 
                     reverse=True)
            totalsz = 0
            for filename in lst:
                filepath = os.path.join(settings.LogsDir(), filename)
                sz = os.path.getsize(filepath)
                if totalsz + sz > 1024*1024*10:
                    continue
                totalsz += sz
                filesList.append(filepath)
        if len(filesList) > 0:
            import zipfile
            import time
            username = bpio.ReadTextFile(settings.UserNameFilename())
            zipfd, zipfilename = tempfile.mkstemp('.zip', username+'-'+time.strftime('%Y%m%d%I%M%S')+'-' )
            zfile = zipfile.ZipFile(zipfilename, "w", compression=zipfile.ZIP_DEFLATED)
            for filename in filesList:
                if os.path.isfile(filename):
                    try:
                        if os.path.getsize(filename) < 1024*1024*10:
                            zfile.write(filename, os.path.basename(filename))
                    except:
                        pass
            zfile.close()
        files = {}
        if zipfilename:
            files['upload'] = zipfilename
        data = {'subject': subject, 'body': body}
        return net_misc.uploadHTTP('http://bitdust.io/cgi-bin/feedback.py', files, data, progress)
        # r.addErrback(lambda err: lg.out(2, 'misc.SendDevReport ERROR : %s' % str(err)))
        # r.addCallback(lambda src: lg.out(2, 'misc.SendDevReport : %s' % str(src)))            
        # return r 
    except:
        lg.exc()
    return None

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
    if bpio.Windows():
        
        username = os.path.basename(os.path.expanduser('~'))
        if bpio.windows_version() == 5: # Windows XP
            # %ALLUSERSPROFILE%\Application Data\Microsoft\User Account Pictures
            allusers = os.environ.get('ALLUSERSPROFILE', os.path.join(os.path.dirname(os.path.expanduser('~')), 'All Users'))
            return os.path.join(allusers, 'Application Data', 'Microsoft', 'User Account Pictures', username+'.bmp')
        elif bpio.windows_version() == 6: # Windows 7
            # C:\Users\<username>\AppData\Local\Temp\<domain>+<username>.bmp 
            default_path = os.path.join(os.path.expanduser('~'), 'Application Data')
            return os.path.join(os.environ.get('APPDATA', default_path), 'Local', 'Temp', username+'.bmp')
        else:
            return ''
    elif bpio.Linux():
        return os.path.join(os.path.expanduser('~'), '.face')
    elif bpio.Mac():
        # TODO
        return ''
    return ''

def UpdateRegistryUninstall(uninstall=False):
    """
    This is not used right now.
    Now BitDust is installed via .msi file and we do all that stuff inside it.
    """
    try:
        import _winreg
    except:
        return False
    unistallpath = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall" 
    regpath = unistallpath + "\\BitDust"
    values = {
        'DisplayIcon':      '%s,0' % str(bpio.getExecutableFilename()),
        'DisplayName':      'BitDust',
        'DisplayVersion':   bpio.ReadTextFile(settings.VersionNumberFile()).strip(),
        'InstallLocation:': settings.BaseDir(),
        'NoModify':         1,
        'NoRepair':         1,
        'UninstallString':  '%s uninstall' % bpio.getExecutableFilename(),
        'URLInfoAbout':     'http://bitdust.io', }    
    # open
    try:
        reg = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, regpath, 0, _winreg.KEY_ALL_ACCESS)
    except:
        try:
            reg = _winreg.CreateKey(_winreg.HKEY_LOCAL_MACHINE, regpath)
        except:
            lg.exc()
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
                    lg.exc()
        else:
            if name == 'DisplayName' and value == 'BitDust':
                _winreg.CloseKey(reg)
                return True
    # delete
    if uninstall:
        _winreg.CloseKey(reg)
        try:
            reg = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, unistallpath, 0, _winreg.KEY_ALL_ACCESS)
        except:
            lg.exc()
            return False
        try:
            _winreg.DeleteKey(reg, 'BitDust')
        except:
            lg.exc()
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


def MakeBatFileToUninstall(wait_appname='bpmain.exe', local_dir=bpio.getExecutableDir(), dirs2delete=[settings.BaseDir(),]):
    """
    Not used.
    """
    lg.out(0, 'misc.MakeBatFileToUninstall')
    batfileno, batfilename = tempfile.mkstemp('.bat', 'BitDust-uninstall-')
    batsrc = ''
    batsrc += 'cd "%s"\n' % local_dir
    batsrc += 'del search.log /Q\n'
    batsrc += ':again\n'
    batsrc += 'sleep 1\n'
    batsrc += 'tasklist /FI "IMAGENAME eq %s" /FO CSV > search.log\n' % wait_appname
    batsrc += 'FOR /F %%A IN (search.log) DO IF %%-zA EQU 0 GOTO again\n'
#    batsrc += 'start /B /D"%s" %s\n' % (local_dir, start_cmd)
#    batsrc += 'start /B /D"%s" %s\n' % (bpio.shortPath(local_dir), start_cmd)
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
    if current_delay < max:
        current_delay *= _AttenuationFactor
        if current_delay > max:
            current_delay = max
    return current_delay

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    lg.set_debug_level(10)
    bpio.init()
    init()

    if True:
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred        
        def _progress(x, y):
            print '%d/%d' % (x,y)      
        def _done(x):
            print 'DONE', x
            reactor.stop()
            return x  
        def _fail(x):
            print 'FAIL', x
            reactor.stop()
            return x  
        d = SendDevReport('subject ', 'some body112', True, _progress)
        if d:
            d.addCallback(_done)
            d.addErrback(_fail)
        reactor.run()
        
