#!/usr/bin/python
# os_windows_update.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (os_windows_update.py) is part of BitDust Software.
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
#

"""
.. module:: os_windows_update.

A code for Windows platforms to check for updates and download latest
binaries.
"""

from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import time
import calendar
from io import open

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in os_windows_update.py')

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from lib import strng

from logs import lg

from system import bpio
from system import tmpfile

from lib import misc
from lib import net_misc
from lib import maths
from lib import schedule

from main import settings

#-------------------------------------------------------------------------------

_CloseFunc = None
_LocalDir = ''
_UpdateList = []
_ShedulerTask = None
_UpdatingByUser = True
_UpdatingInProgress = False
_UpdateWindowObject = None
_GuiMessageFunc = None
_NewVersionNotifyFunc = None
_CurrentVersionDigest = ''
_CurrentRepo = ''
_CurrentDefaultRepoURL = ''

_SheduleTypesDict = {
    '0': 'none',
    '1': 'hourly',
    '2': 'daily',
    '3': 'weekly',
    '4': 'monthly',
    '5': 'continuously',
}

#------------------------------------------------------------------------------


def init():
    lg.out(4, 'os_windows_update.init')
    # update_shedule_file(settings.getUpdatesSheduleData())
    if not bpio.isFrozen() or not bpio.Windows():
        lg.out(6, 'os_windows_update.init finishing')
        return
    # if not os.path.isfile(settings.VersionFile()):
    #     bpio.WriteFile(settings.VersionFile(), '')
    SetLocalDir(bpio.getExecutableDir())
    if settings.getUpdatesMode() != settings.getUpdatesModeValues()[2]:
        lg.out(6, 'os_windows_update.init starting the loop')
        reactor.callLater(0, loop, True)
    else:
        lg.out(6, 'os_windows_update.init skip, update mode is: %s' % settings.getUpdatesMode())

#------------------------------------------------------------------------------


def SetUpdateWindowObject(obj):
    global _UpdateWindowObject
    _UpdateWindowObject = obj


def SetLocalDir(local_dir):
    global _LocalDir
    _LocalDir = local_dir


def GetLocalDir():
    global _LocalDir
    return _LocalDir


def SetCloseFunc(func):
    global _CloseFunc
    _CloseFunc = func


def SetGuiMessageFunc(func):
    global _GuiMessageFunc
    _GuiMessageFunc = func


def SetNewVersionNotifyFunc(func):
    global _NewVersionNotifyFunc
    _NewVersionNotifyFunc = func


def CurrentVersionDigest():
    global _CurrentVersionDigest
    return _CurrentVersionDigest


def UpdatingInProgress():
    global _UpdatingInProgress
    return _UpdatingInProgress

#-------------------------------------------------------------------------------


def write2log(txt):
    out_file = open(settings.UpdateLogFilename(), 'a')
    print(txt, file=out_file)
    out_file.close()


def write2window(txt, state=True):
    global _GuiMessageFunc
    global _UpdatingByUser
    write2log('[%s] %s' % (time.asctime(), txt))
    if _GuiMessageFunc is not None:
        _GuiMessageFunc(txt, proto='U', state=state)


def write2window_sameline(txt, state=True):
    global _GuiMessageFunc
    global _UpdatingByUser
    if _GuiMessageFunc is not None:
        _GuiMessageFunc(txt, proto='U', state=state)


def set_bat_filename(filename):
    global _UpdateWindowObject
    global _UpdatingByUser
    if not _UpdateWindowObject:
        return
    if not _UpdatingByUser:
        return
    _UpdateWindowObject.set_bat_filename(filename)

#-------------------------------------------------------------------------------


def fail(txt):
    global _NewVersionNotifyFunc
    global _UpdatingInProgress
    lg.out(1, 'os_windows_update.fail ' + str(txt))
    write2window('there are some errors during updating: ' + str(txt))
    _UpdatingInProgress = False

#------------------------------------------------------------------------------


def download_version():
    repo, locationURL = misc.ReadRepoLocation()
    url = locationURL + settings.CurrentVersionDigestsFilename()
    lg.out(6, 'os_windows_update.download_version ' + str(url))
    return net_misc.getPageTwisted(url)


def download_info():
    def _done(src, result):
        lg.out(6, 'os_windows_update.download_info.done ')
        lines = src.split('\n')
        files_dict = {}
        for line in lines:
            words = line.split(' ')
            if len(words) < 2:
                continue
            files_dict[words[1].strip()] = words[0].strip()
        result.callback(files_dict)
        return src

    def _fail(x, result):
        lg.out(1, 'os_windows_update.download_info FAILED')
        result.errback(Exception('error downloading info'))
        return x
    repo, locationURL = misc.ReadRepoLocation()
    url = locationURL + settings.FilesDigestsFilename()
    lg.out(6, 'os_windows_update.download_info ' + str(url))
    result = Deferred()
    d = net_misc.getPageTwisted(url)
    d.addCallback(_done, result)
    d.addErrback(_fail, result)
    return result


def download_and_replace_starter(output_func=None):
    repo, locationURL = misc.ReadRepoLocation()
    url = locationURL + settings.WindowsStarterFileName()
    lg.out(6, 'os_windows_update.download_and_replace_starter ' + str(url))
    result = Deferred()

    def _done(x, filename):
        try:
            fin = open(filename, 'rb')
            src = strng.to_text(fin.read())
            fin.close()
        except:
            if output_func:
                output_func('error opening downloaded starter file')
            result.errback(Exception('error opening downloaded starter file'))
            return
        local_filename = os.path.join(GetLocalDir(), settings.WindowsStarterFileName())
        bpio.backup_and_remove(local_filename)
        try:
            os.rename(filename, local_filename)
            lg.out(4, 'os_windows_update.download_and_replace_starter  file %s was updated' % local_filename)
        except:
            lg.out(1, 'os_windows_update.download_and_replace_starter ERROR can not rename %s to %s ' % (filename, local_filename))
            lg.exc()
            result.errback(Exception('can not rename the file ' + filename))
            return
        python27dll_path = os.path.join(GetLocalDir(), 'python27.dll')
        if not os.path.exists(python27dll_path):
            lg.out(4, 'os_windows_update.download_and_replace_starter file "python27.dll" not found download from "%s" repo' % repo)
            url = settings.DefaultRepoURL(repo) + 'python27.dll'
            d = net_misc.downloadHTTP(url, python27dll_path)
            d.addCallback(_done_python27_dll, filename)
            d.addErrback(_fail, filename)
            return
        result.callback(1)

    def _done_python27_dll(x, filename):
        lg.out(4, 'os_windows_update.download_and_replace_starter file %s was updated' % filename)
        result.callback(1)

    def _fail(x, filename):
        lg.out(1, 'os_windows_update.download_and_replace_starter FAILED')
        if output_func:
            try:
                output_func(x.getErrorMessage())
            except:
                output_func('error downloading starter')
        try:
            os.remove(filename)
        except:
            lg.out(1, 'os_windows_update.download_and_replace_starter ERROR can not remove ' + filename)
        result.errback(Exception('error downloading starter'))

    fileno, filename = tmpfile.make('all', extension='.starter')
    os.close(fileno)
    d = net_misc.downloadHTTP(url, filename)
    d.addCallback(_done, filename)
    d.addErrback(_fail, filename)
    return result

#-------------------------------------------------------------------------------


def step0():
    lg.out(4, 'os_windows_update.step0')
    global _UpdatingInProgress
    if _UpdatingInProgress:
        lg.out(6, 'os_windows_update.step0  _UpdatingInProgress is True, skip.')
        return

    repo, locationURL = misc.ReadRepoLocation()
    src = bpio.ReadTextFile(settings.RepoFile())
    if src == '':
        bpio.WriteTextFile(settings.RepoFile(), u'%s\n%s' % (repo, locationURL))

    _UpdatingInProgress = True
    d = download_version()
    d.addCallback(step1)
    d.addErrback(fail)


def step1(version_digest):
    lg.out(4, 'os_windows_update.step1')
    global _UpdatingInProgress
    global _CurrentVersionDigest
    global _NewVersionNotifyFunc
    global _UpdatingByUser

    _CurrentVersionDigest = str(version_digest).strip()
    local_checksum = bpio.ReadBinaryFile(settings.CheckSumFile()).strip()
    if local_checksum == _CurrentVersionDigest:
        lg.out(6, 'os_windows_update.step1 no need to update, checksums are equal')
        _UpdatingInProgress = False
        if _NewVersionNotifyFunc is not None:
            _NewVersionNotifyFunc(_CurrentVersionDigest)
        return

    appList = bpio.find_process(['bpgui.', ])
    if len(appList) > 0:
        if not _UpdatingByUser:
            lg.out(6, 'os_windows_update.step1 bpgui is running, ask user to update.')
            _UpdatingInProgress = False
            if _NewVersionNotifyFunc is not None:
                _NewVersionNotifyFunc(_CurrentVersionDigest)
            return

    d = download_info()
    d.addCallback(step2, _CurrentVersionDigest)
    d.addErrback(fail)


def step2(info, version_digest):
    lg.out(4, 'os_windows_update.step2')
    if not isinstance(info, dict):
        fail('wrong data')
        return

    bitstarter_server_digest = info.get(settings.WindowsStarterFileName(), None)
    if bitstarter_server_digest is None:
        lg.warn('windows starter executable is not found in the info file')
        reactor.callLater(0.5, step4, version_digest)
        #fail('windows starter executable is not found in the info file')
        return

    bitstarter_local_digest = misc.file_hash(os.path.join(GetLocalDir(), settings.WindowsStarterFileName()))

    if bitstarter_local_digest != bitstarter_server_digest:
        reactor.callLater(0.5, step3, version_digest)
    else:
        reactor.callLater(0.5, step4, version_digest)


def step3(version_digest):
    lg.out(4, 'os_windows_update.step3')
    d = download_and_replace_starter(write2window)
    d.addCallback(lambda x: step4(version_digest))
    d.addErrback(fail)


def step4(version_digest):
    lg.out(4, 'os_windows_update.step4')
    global _UpdatingInProgress
    global _CurrentVersionDigest
    global _NewVersionNotifyFunc
    global _UpdatingByUser

    _CurrentVersionDigest = str(version_digest)
    local_version = bpio.ReadBinaryFile(settings.CheckSumFile())
    if local_version == _CurrentVersionDigest:
        lg.out(6, 'os_windows_update.step4 no need to update')
        _UpdatingInProgress = False
        return

    lg.out(6, 'os_windows_update.step4 local=%s current=%s ' % (local_version, _CurrentVersionDigest))

    if settings.getUpdatesMode() == settings.getUpdatesModeValues()[2] and not _UpdatingByUser:
        lg.out(6, 'os_windows_update.step4 run scheduled, but mode is %s, skip now' % settings.getUpdatesMode())
        return

    if _UpdatingByUser or settings.getUpdatesMode() == settings.getUpdatesModeValues()[0]:
        #        info_file_path = os.path.join(bpio.getExecutableDir(), settings.FilesDigestsFilename())
        info_file_path = settings.InfoFile()
        if os.path.isfile(info_file_path):
            try:
                os.remove(info_file_path)
            except:
                lg.out(1, 'os_windows_update.step4 ERROR can no remove ' + info_file_path)
                lg.exc()

        param = ''
        if _UpdatingByUser:
            param = 'show'
        from main import shutdowner
        if param == 'show':
            shutdowner.A('stop', 'restartnshow')
        else:
            shutdowner.A('stop', 'restart')

    else:
        if _NewVersionNotifyFunc is not None:
            _NewVersionNotifyFunc(_CurrentVersionDigest)

#------------------------------------------------------------------------------


def is_running():
    global _UpdatingInProgress
    return _UpdatingInProgress


def read_shedule_dict():
    lg.out(8, 'os_windows_update.read_shedule_dict')
    # d = bpio._read_dict(settings.UpdateSheduleFilename())
    # if d is None or not check_shedule_dict_correct(d):
    #     d = make_blank_shedule()
    d = string_to_shedule(settings.getUpdatesSheduleData())
    d['mode'] = settings.getUpdatesMode()
    return d


def write_shedule_dict(d):
    lg.out(8, 'os_windows_update.write_shedule_dict')
    if d is None or not check_shedule_dict_correct(d):
        return
    old = string_to_shedule(settings.getUpdatesSheduleData())
    d['lasttime'] = old.get('lasttime', '')
    settings.setUpdatesSheduleData(shedule_to_string(d))
    if 'mode' in d:
        settings.setUpdatesMode(d['mode'])
    # bpio._write_dict(settings.UpdateSheduleFilename(), d)


def blank_shedule(type):
    d = {'type': type}
    if type == 'none':
        d['interval'] = ''
        d['daytime'] = ''
        d['details'] = ''
        d['lasttime'] = ''
    elif type == 'continuously':
        d['interval'] = '3600'
        d['daytime'] = ''
        d['details'] = ''
        d['lasttime'] = ''
    elif type == 'hourly':
        d['interval'] = '1'
        d['daytime'] = ''
        d['details'] = ''
        d['lasttime'] = ''
    elif type == 'daily':
        d['interval'] = '1'
        d['daytime'] = '12:00:00'
        d['details'] = ''
        d['lasttime'] = ''
    elif type == 'weekly':
        d['interval'] = '1'
        d['daytime'] = '12:00:00'
        d['details'] = 'Monday'
        d['lasttime'] = ''
    elif type == 'monthly':
        d['interval'] = '1'
        d['daytime'] = '12:00:00'
        d['details'] = 'January'
        d['lasttime'] = ''
    else:
        d['type'] = 'hourly'
        d['interval'] = '1'
        d['daytime'] = ''
        d['details'] = ''
        d['lasttime'] = ''
    return d


# def make_blank_shedule(type='daily'):
#    lg.out(8, 'os_windows_update.make_blank_shedule')
#    d = blank_shedule(type)
#    # bpio._write_dict(settings.UpdateSheduleFilename(), d)
#    return d


def check_shedule_dict_correct(d):
    if not ('type' in d and
            'interval' in d and
            'daytime' in d and
            'details' in d and
            'lasttime' in d):
        lg.warn('incorrect data: ' + str(d))
        return False
    try:
        float(d['interval'])
    except:
        lg.warn('incorrect data: ' + str(d))
        return False
    return True


def shedule_to_string(d):
    global _SheduleTypesDict
    src = ''
    for num, type in _SheduleTypesDict.items():
        if type == d['type']:
            src += num + '\n'
            break
    src += d['daytime'] + '\n'
    src += d['interval'] + '\n'
    src += d['details'] + '\n'
    src += d['lasttime']
    return src


def string_to_shedule(raw_data):
    global _SheduleTypesDict
    l = raw_data.split('\n')
    if len(l) < 3:
        return blank_shedule('hourly')
    d = {}
    d['type'] = l[0].strip()
    if d['type'] in ['0', '1', '2', '3', '4', '5']:
        d['type'] = _SheduleTypesDict.get(d['type'], 'none')
    if d['type'] not in list(_SheduleTypesDict.values()):
        d['type'] = 'daily'
    d['daytime'] = l[1].strip()
    d['interval'] = l[2].strip()
    # small protection
    if d['type'] == 'continuously':
        d['type'] = 'hourly'
    d['details'] = (l[3].strip() if len(l) >= 4 else '')
    d['lasttime'] = (l[4].strip() if len(l) >= 5 else '')
    return d


# def update_shedule_file(raw_data):
#     d = string_to_shedule(raw_data)
#     write_shedule_dict(d)

#------------------------------------------------------------------------------

def run():
    global _UpdatingInProgress
    global _UpdatingByUser
    lg.out(6, 'os_windows_update.run')
    if _UpdatingInProgress:
        lg.out(6, '  update is in progress, finish.')
        return
    _UpdatingByUser = True
    reactor.callLater(0, step0)


def run_sheduled_update():
    global _UpdatingByUser
    global _UpdatingInProgress
    lg.out(6, 'os_windows_update.run_sheduled_update')
    if _UpdatingInProgress:
        lg.out(6, '  update is in progress, finish.')
        return
    if settings.getUpdatesMode() == settings.getUpdatesModeValues()[2]:
        lg.out(6, '  update mode is %s, finish.' % settings.getUpdatesMode())
        return
    from storage import backup_control
    if backup_control.HasRunningBackup():
        lg.out(6, '  some backups are running at the moment, finish.')
        return

    _UpdatingByUser = False
    reactor.callLater(0, step0)

    # check or start the update
    d = read_shedule_dict()
    d['lasttime'] = str(time.time())
    write_shedule_dict(d)
    loop()


def next(d):
    lasttime = d.get('lasttime', '').strip()
    if lasttime == '':
        # let it be one year ago (we can shedule 1 month maximum)
        lasttime = str(time.time() - 365 * 24 * 60 * 60)

    if d['type'] in ['none', 'disabled']:
        return -1

    elif d['type'] == 'continuously':
        return maths.shedule_continuously(lasttime, d['interval'],)

    elif d['type'] == 'hourly':
        return maths.shedule_next_hourly(lasttime, d['interval'])

    elif d['type'] == 'daily':
        return maths.shedule_next_daily(lasttime, d['interval'], d['daytime'])

    elif d['type'] == 'weekly':
        week_days = d['details'].split(' ')
        week_day_numbers = []
        week_day_names = list(calendar.day_name)
        for week_label in week_days:
            try:
                i = week_day_names.index(week_label)
            except:
                continue
            week_day_numbers.append(i)
        return maths.shedule_next_weekly(lasttime, d['interval'], d['daytime'], week_day_numbers)

    elif d['type'] == 'monthly':
        month_dates = d['details'].split(' ')
        return maths.shedule_next_monthly(lasttime, d['interval'], d['daytime'], month_dates)
#        months_labels = d['details'].split(' ')
#        months_numbers = []
#        months_names = list(calendar.month_name)
#        for month_label in months_labels:
#            try:
#                i = months_names.index(month_label)
#            except:
#                continue
#            months_numbers.append(i)
#        return maths.shedule_next_monthly(lasttime, d['interval'], d['daytime'], months_numbers)

    else:
        lg.out(1, 'os_windows_update.loop ERROR wrong shedule type')
        return None


def loop(first_start=False):
    global _ShedulerTask
    lg.out(4, 'os_windows_update.loop mode=' + str(settings.getUpdatesMode()))

    if settings.getUpdatesMode() == settings.getUpdatesModeValues()[2]:
        lg.out(4, 'os_windows_update.loop is finishing. updates is turned off')
        return

    shed = schedule.Schedule(from_dict=read_shedule_dict())
    nexttime = shed.next_time()
#    nexttime = next(d)
    if first_start:
        nexttime = time.time()

    if nexttime is None:
        lg.out(1, 'os_windows_update.loop ERROR calculating shedule interval')
        return

    if nexttime < 0:
        lg.out(1, 'os_windows_update.loop nexttime=%s' % str(nexttime))
        return

    # DEBUG
    # nexttime = time.time() + 60.0

    delay = nexttime - time.time()
    if delay < 0:
        lg.warn('delay=%s %s' % (str(delay), shed))
        delay = 0

    lg.out(6, 'os_windows_update.loop run_sheduled_update will start after %s seconds (%s hours)' % (str(delay), str(delay / 3600.0)))
    _ShedulerTask = reactor.callLater(delay, run_sheduled_update)


def update_sheduler():
    global _ShedulerTask
    lg.out(4, 'os_windows_update.update_sheduler')
# if not bpio.isFrozen() or not bpio.Windows():
# return
    if _ShedulerTask is not None:
        if _ShedulerTask.active():
            _ShedulerTask.cancel()
        _ShedulerTask = None
    loop()


def check():
    lg.out(4, 'os_windows_update.check')

    def _success(x):
        global _CurrentVersionDigest
        global _NewVersionNotifyFunc
        _CurrentVersionDigest = str(x)
        local_version = bpio.ReadBinaryFile(settings.CheckSumFile())
        lg.out(6, 'os_windows_update.check._success local=%s current=%s' % (local_version, _CurrentVersionDigest))
        if _NewVersionNotifyFunc is not None:
            _NewVersionNotifyFunc(_CurrentVersionDigest)
        return x

    def _fail(x):
        global _NewVersionNotifyFunc
        lg.out(10, 'os_windows_update.check._fail NETERROR ' + x.getErrorMessage())
        if _NewVersionNotifyFunc is not None:
            _NewVersionNotifyFunc('failed')
        return x

    d = download_version()
    d.addCallback(_success)
    d.addErrback(_fail)
    return d


#------------------------------------------------------------------------------

def test1():
    lg.set_debug_level(20)
    bpio.init()
    settings.init()
    update_sheduler()
    #SetLocalDir('c:\\Program Files\\\xc4 \xd8 \xcd')
    # download_and_replace_starter()
    reactor.run()

if __name__ == '__main__':
    bpio.init()
    settings.init()
    test1()
