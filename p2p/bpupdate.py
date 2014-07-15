#!/usr/bin/python
#bpupdate.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: bpupdate

A code for Windows platforms to check for updates and download latest binaries.   
"""

import os
import sys
import time
import calendar


try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in bpupdate.py')

from twisted.internet.defer import Deferred


if __name__ == '__main__':
    sys.path.append(os.path.abspath('..'))


import lib.io as io
import lib.misc as misc
import lib.net_misc as net_misc
import lib.settings as settings
import lib.maths as maths
import lib.tmpfile as tmpfile
import lib.schedule as schedule


import backup_control
import init_shutdown


#-------------------------------------------------------------------------------

_CloseFunc = None
#_CloseFlag = 0
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
_CurrentUpdateLocationURL = ''

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
    io.log(4, 'bpupdate.init')
    update_shedule_file(settings.getUpdatesSheduleData())
    if not io.isFrozen() or not io.Windows():
        io.log(6, 'bpupdate.init finishing')
        return
    if not os.path.isfile(settings.VersionFile()):
        io.WriteFile(settings.VersionFile(), '')
    SetLocalDir(io.getExecutableDir())
    if settings.getUpdatesMode() != settings.getUpdatesModeValues()[2]:
        io.log(6, 'bpupdate.init starting the loop')
        reactor.callLater(0, loop, True)
    else:
        io.log(6, 'bpupdate.init skip, update mode is: %s' % settings.getUpdatesMode())
        

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
    out_file = file(settings.UpdateLogFilename(), 'a')
    print >>out_file, txt
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
    io.log(1, 'bpupdate.fail ' + str(txt))
    write2window('there are some errors during updating: ' + str(txt))
    _UpdatingInProgress = False

#------------------------------------------------------------------------------

def download_version():
    repo, locationURL = misc.ReadRepoLocation()
    url = locationURL + settings.CurrentVersionDigestsFilename()
    io.log(6, 'bpupdate.download_version ' + str(url))
    return net_misc.getPageTwisted(url)

def download_info():
    
    def _done(src, result):
        io.log(6, 'bpupdate.download_info.done ')
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
        io.log(1, 'bpupdate.download_info FAILED')
        result.errback(Exception('error downloading info'))
        return x
    
    repo, locationURL = misc.ReadRepoLocation()
    url = locationURL + settings.FilesDigestsFilename()

    io.log(6, 'bpupdate.download_info ' + str(url))
    result = Deferred()
    d = net_misc.getPageTwisted(url)
    d.addCallback(_done, result)
    d.addErrback(_fail, result)
    return result

def download_and_replace_starter(output_func = None):
    repo, locationURL = misc.ReadRepoLocation()
    url = settings.WindowsStarterFileURL(repo)
    io.log(6, 'bpupdate.download_and_replace_starter  ' + str(url))
    result = Deferred()
    
    def _done(x, filename):
        try:
            fin = open(filename, 'rb')
            src = fin.read()
            fin.close()
        except:
            if output_func:
                output_func('error opening downloaded starter file')
            result.errback(Exception('error opening downloaded starter file'))
            return

        local_filename = os.path.join(GetLocalDir(), settings.WindowsStarterFileName())

        io.backup_and_remove(local_filename)

        try:
            os.rename(filename, local_filename)
            io.log(4, 'bpupdate.download_and_replace_starter  file %s was updated' % local_filename)
        except:
            io.log(1, 'bpupdate.download_and_replace_starter ERROR can not rename %s to %s ' % (filename, local_filename))
            io.exception()
            result.errback(Exception('can not rename the file ' + filename))
            return
        
        python27dll_path = os.path.join(GetLocalDir(), 'python27.dll')
        if not os.path.exists(python27dll_path):
            url = settings.UpdateLocationURL('test') + 'windows/' + 'python27.dll' 
            d = net_misc.downloadHTTP(url, python27dll_path)
            d.addCallback(_done_python27_dll, filename)
            d.addErrback(_fail, filename)
            return
        
        result.callback(1)

    def _done_python27_dll(x, filename):
        io.log(4, 'bpupdate.download_and_replace_starter file %s was updated' % filename)
        result.callback(1)

    def _fail(x, filename):
        io.log(1, 'bpupdate.download_and_replace_starter FAILED')
        if output_func:
            try:
                output_func(x.getErrorMessage())
            except:
                output_func('error downloading starter')
        try:
            os.remove(filename)
        except:
            io.log(1, 'bpupdate.download_and_replace_starter ERROR can not remove ' + filename)
        result.errback(Exception('error downloading starter'))

    fileno, filename = tmpfile.make('other', '.starter')
    os.close(fileno)
    d = net_misc.downloadHTTP(url, filename)
    d.addCallback(_done, filename)
    d.addErrback(_fail, filename)
    return result

#-------------------------------------------------------------------------------

def step0():
    io.log(4, 'bpupdate.step0')
    global _UpdatingInProgress
    if _UpdatingInProgress:
        io.log(6, 'bpupdate.step0  _UpdatingInProgress is True, skip.')
        return

    repo, locationURL = misc.ReadRepoLocation()
    src = io.ReadTextFile(settings.RepoFile())
    if src == '':
        io.WriteFile(settings.RepoFile(), '%s\n%s' % (repo, locationURL))
             
    _UpdatingInProgress = True
    d = download_version()
    d.addCallback(step1)
    d.addErrback(fail)

def step1(version_digest):
    io.log(4, 'bpupdate.step1')
    global _UpdatingInProgress
    global _CurrentVersionDigest
    global _NewVersionNotifyFunc
    global _UpdatingByUser

    _CurrentVersionDigest = str(version_digest).strip()
    local_version = io.ReadBinaryFile(settings.VersionFile()).strip()
    if local_version == _CurrentVersionDigest:
        io.log(6, 'bpupdate.step1 no need to update')
        _UpdatingInProgress = False
        if _NewVersionNotifyFunc is not None:
            _NewVersionNotifyFunc(_CurrentVersionDigest)
        return

    appList = io.find_process(['bpgui.', ])
    if len(appList) > 0:
        if not _UpdatingByUser:
            io.log(6, 'bpupdate.step1 bpgui is running, ask user to update.')
            _UpdatingInProgress = False
            if _NewVersionNotifyFunc is not None:
                _NewVersionNotifyFunc(_CurrentVersionDigest)
            return

    d = download_info()
    d.addCallback(step2, _CurrentVersionDigest)
    d.addErrback(fail)

def step2(info, version_digest):
    io.log(4, 'bpupdate.step2')
    if not isinstance(info, dict):
        fail('wrong data')
        return

    bpstarter_server_digest = info.get(settings.WindowsStarterFileName(), None)
    if bpstarter_server_digest is None:
        io.log(2, 'bpupdate.step2 WARNING windows starter executable is not found in the info file')
        reactor.callLater(0.5, step4, version_digest)
        #fail('windows starter executable is not found in the info file')
        return

    bpstarter_local_digest = misc.file_hash(os.path.join(GetLocalDir(), settings.WindowsStarterFileName()))

    if bpstarter_local_digest != bpstarter_server_digest:
        reactor.callLater(0.5, step3, version_digest)
    else:
        reactor.callLater(0.5, step4, version_digest)


def step3(version_digest):
    io.log(4, 'bpupdate.step3')
    d = download_and_replace_starter(write2window)
    d.addCallback(lambda x: step4(version_digest))
    d.addErrback(fail)


def step4(version_digest):
    io.log(4, 'bpupdate.step4')
    global _UpdatingInProgress
    global _CurrentVersionDigest
    global _NewVersionNotifyFunc
    global _UpdatingByUser

    _CurrentVersionDigest = str(version_digest)
    local_version = io.ReadBinaryFile(settings.VersionFile())
    if local_version == _CurrentVersionDigest:
        io.log(6, 'bpupdate.step4 no need to update')
        _UpdatingInProgress = False
        return

    io.log(6, 'bpupdate.step4 local=%s current=%s ' % (local_version, _CurrentVersionDigest))

    if settings.getUpdatesMode() == settings.getUpdatesModeValues()[2] and not _UpdatingByUser:
        io.log(6, 'bpupdate.step4 run scheduled, but mode is %s, skip now' % settings.getUpdatesMode())
        return

    if _UpdatingByUser or settings.getUpdatesMode() == settings.getUpdatesModeValues()[0]:
#        info_file_path = os.path.join(io.getExecutableDir(), settings.FilesDigestsFilename())
        info_file_path = settings.InfoFile()
        if os.path.isfile(info_file_path):
            try:
                os.remove(info_file_path)
            except:
                io.log(1, 'bpupdate.step4 ERROR can no remove ' + info_file_path )
                io.exception()

        param = ''
        if _UpdatingByUser:
            param = 'show'
        import shutdowner
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
    io.log(8, 'bpupdate.read_shedule_dict')
    d = io._read_dict(settings.UpdateSheduleFilename())
    if d is None or not check_shedule_dict_correct(d):
        d = make_blank_shedule()
    return d


def write_shedule_dict(d):
    io.log(8, 'bpupdate.write_shedule_dict')
    if d is None or not check_shedule_dict_correct(d):
        return
    io._write_dict(settings.UpdateSheduleFilename(), d)


def blank_shedule(type):
    d = { 'type': type }
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


def make_blank_shedule(type='daily'):
    io.log(8, 'bpupdate.make_blank_shedule')
    d = blank_shedule(type)
    io._write_dict(settings.UpdateSheduleFilename(), d)
    return d


def check_shedule_dict_correct(d):
    if not (d.has_key('type') and
            d.has_key('interval') and
            d.has_key('daytime') and
            d.has_key('details') and
            d.has_key('lasttime')):
        io.log(2, 'bpupdate.check_shedule_dict_correct WARNING incorrect data: ' + str(d))
        return False
    try:
        float(d['interval'])
    except:
        io.log(2, 'bpupdate.check_shedule_dict_correct WARNING incorrect data: ' + str(d))
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
    if d['type'] not in _SheduleTypesDict.values():
        d['type'] = 'daily'
    d['daytime'] = l[1].strip()
    d['interval'] = l[2].strip()
    # small protection
    if d['type'] == 'continuously':
        d['type'] = 'hourly'
    d['details'] = (l[3].strip() if len(l) >= 4 else '')
    d['lasttime'] = (l[4].strip() if len(l) >= 5 else '')
    return d

def update_shedule_file(raw_data):
    d = string_to_shedule(raw_data)
    write_shedule_dict(d)

#------------------------------------------------------------------------------

def run():
    global _UpdatingInProgress
    global _UpdatingByUser
    io.log(6, 'bpupdate.run')
    if _UpdatingInProgress:
        io.log(6, '  update is in progress, finish.')
        return
    _UpdatingByUser = True
    reactor.callLater(0, step0)


def run_sheduled_update():
    global _UpdatingByUser
    global _UpdatingInProgress
    io.log(6, 'bpupdate.run_sheduled_update')
    if _UpdatingInProgress:
        io.log(6, '  update is in progress, finish.')
        return
    if settings.getUpdatesMode() == settings.getUpdatesModeValues()[2]:
        io.log(6, '  update mode is %s, finish.' % settings.getUpdatesMode())
        return
    if backup_control.HasRunningBackup():
        io.log(6, '  some backups are running at the moment, finish.')
        return

    _UpdatingByUser = False
    reactor.callLater(0, step0)

    #check or start the update
    d = read_shedule_dict()
    d['lasttime'] = str(time.time())
    write_shedule_dict(d)
    loop()


def next(d):
    lasttime = d.get('lasttime', '').strip()
    if lasttime == '':
        # let it be one year ago (we can shedule 1 month maximum)
        lasttime = str(time.time()-365*24*60*60)

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
        io.log(1, 'bpupdate.loop ERROR wrong shedule type')
        return None    

def loop(first_start=False):
    global _ShedulerTask
    io.log(4, 'bpupdate.loop mode=' + str(settings.getUpdatesMode()))

    if settings.getUpdatesMode() == settings.getUpdatesModeValues()[2]:
        io.log(4, 'bpupdate.loop is finishing. updates is turned off')
        return

    shed = schedule.Schedule(from_dict=read_shedule_dict())
    nexttime = shed.next_time()
#    nexttime = next(d)
    if first_start:
        nexttime = time.time() + 5
    
    if nexttime is None:
        io.log(1, 'bpupdate.loop ERROR calculating shedule interval')
        return
    
    if nexttime < 0:
        io.log(1, 'bpupdate.loop nexttime=%s' % str(nexttime))
        return

    # DEBUG
    # nexttime = time.time() + 60.0

    delay = nexttime - time.time()
    if delay < 0:
        io.log(2, 'bpupdate.loop WARNING delay=%s %s' % (str(delay), shed))
        delay = 10

    io.log(6, 'bpupdate.loop run_sheduled_update will start after %s seconds (%s hours)' % (str(delay), str(delay/3600.0)))
    _ShedulerTask = reactor.callLater(delay, run_sheduled_update)


def update_sheduler():
    global _ShedulerTask
    io.log(4, 'bpupdate.update_sheduler')
##    if not io.isFrozen() or not io.Windows():
##        return
    if _ShedulerTask is not None:
        if _ShedulerTask.active():
            _ShedulerTask.cancel()
        del _ShedulerTask
        _ShedulerTask = None
    loop()


def check():
    io.log(4, 'bpupdate.check')

    def _success(x):
        global _CurrentVersionDigest
        global _NewVersionNotifyFunc
        _CurrentVersionDigest = str(x)
        local_version = io.ReadBinaryFile(settings.VersionFile())
        io.log(6, 'bpupdate.check._success local=%s current=%s' % (local_version, _CurrentVersionDigest))
        if _NewVersionNotifyFunc is not None:
            _NewVersionNotifyFunc(_CurrentVersionDigest)
        return x

    def _fail(x):
        global _NewVersionNotifyFunc
        io.log(10, 'bpupdate.check._fail NETERROR ' + x.getErrorMessage())
        if _NewVersionNotifyFunc is not None:
            _NewVersionNotifyFunc('failed')
        return x

    d = download_version()
    d.addCallback(_success)
    d.addErrback(_fail)
    return d


#------------------------------------------------------------------------------

def test1():
    io.SetDebug(20)
    io.init()
    settings.init()
    update_sheduler()
    #SetLocalDir('c:\\Program Files\\\xc4 \xd8 \xcd')
    #download_and_replace_starter()
    reactor.run()

if __name__ == '__main__':
    io.init()
    settings.init()
    test1()










