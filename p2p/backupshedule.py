#!/usr/bin/python
#backupshedule.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: backupshedule

A set of methods to run backups at given intervals, used to provide scheduled backups. 

TODO:
need to turn on this module, it is switched off during last "big changes".
many things was changed since that moment, so need to put some work here 
"""

import os
import sys
import time
import calendar


try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in backupshedule.py')

from twisted.internet.defer import Deferred


if __name__ == '__main__':
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath('datahaven'))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..', '..')))


import lib.dhnio as dhnio
import lib.misc as misc
import lib.dhnmath as dhnmath


import dobackup
import backup_db
import backup_monitor
import p2p_service
import webcontrol


_SheduledTasks = {}
_UsingGUI = False
_GuiStatusClearPageData = None
_GuiBackupUpdate = None


#------------------------------------------------------------------------------

def init(usingGui = False):
    global _UsingGUI
    _UsingGUI = usingGui
    dhnio.Dprint(4, 'backupshedule.init ')
    loop()


def shutdown():
    dhnio.Dprint(4, 'backupshedule.shutdown ')
    global _SheduledTasks
    for dirName, task in _SheduledTasks.items():
        try:
            task.cancel()
        except:
            dhnio.Dprint(1, 'backupshedule.shutdown ERROR can not stop task for ' + str(dirName))
            dhnio.DprintException()
        dhnio.Dprint(4, 'backupshedule.shutdown canceled: ' + str(dirName))


def loop():
    dhnio.Dprint(8, 'backupshedule.loop ')
    #debugWrite("in loop about to run at "+str(time.asctime(time.localtime(time.time()))))
    run()
    #debugWrite("in loop finished run, setting callLater")
    reactor.callLater(timeout(), loop)


#will check all Shedules each 60 minutes
def timeout():
    return 60.0*60.0


def run():
    global _SheduledTasks
    try:
        dhnio.Dprint(8, 'backupshedule.run ')
        for dirName in backup_db.GetBackupDirectories():
            dhnio.Dprint(8, 'backupshedule.run %s' % dirName)
            if backup_db.IsBackupRunning(dirName):
                dhnio.Dprint(8, 'backupshedule.run %s is running at the moment, skip.' % dirName)
                continue

            next_start = next(dirName)

            if next_start is None:
                # dhnio.Dprint(8, '  backupshedule.run next_start is None')
                continue

            if next_start < 0:
                continue

            now = time.time()
            delay = next_start - now
            dhnio.Dprint(8, '  backupshedule.run delay=%s next_start=[%s]' % (str(delay), str(time.asctime(time.localtime(next_start)))))
            if delay > 0 and delay < timeout():
                if _SheduledTasks.has_key(unicode(dirName)):
                    dhnio.Dprint(8, 'backupshedule.run cancel previous task')
                    try:
                        _SheduledTasks[unicode(dirName)].cancel()
                    except:
                        pass # may have already run or already been cancelled, nothing to cancel
                    del _SheduledTasks[unicode(dirName)]
                _SheduledTasks[unicode(dirName)] = reactor.callLater(delay, start_backup, dirName)
                # dhnio.Dprint(8, '  backupshedule.run will start after %s seconds' % (str(delay)))
                # dhnio.Dprint(8, '  backupshedule.run getTime()=' + str(_SheduledTasks[unicode(dirName)].getTime()))

    except:
        dhnio.DprintException()


def start_backup(dirName):
    global _SheduledTasks
    if _SheduledTasks.has_key(unicode(dirName)): # we're running now, no longer need the schedule
        del _SheduledTasks[unicode(dirName)]
    dhnio.Dprint(6, 'backupshedule.start_backup ' + str(dirName))

    if not backup_db.CheckDirectory(dirName):
        return

    bid = misc.NewBackupID()
    # backups.AddBackupInProcess(bid)
    recursive_subfolders = backup_db.GetDirectorySubfoldersInclude(dirName)
    dir_size = dhnio.getDirectorySize(dirName, recursive_subfolders)
    result = Deferred()
    result.addCallback(backup_done)
    result.addErrback(backup_fail)
    dobackup.dobackup(bid, dirName, dir_size, recursive_subfolders, webcontrol.OnBackupDataPacketResult, result)

    global _UsingGUI
    global _GuiBackupUpdate
    if _UsingGUI:
        _GuiBackupUpdate()


def backup_done(backupID):
    dhnio.Dprint(4, 'backupshedule.backup_done ' + str(backupID))

    global _UsingGUI
    global _GuiBackupUpdate
    global _GuiStatusClearPageData

    if _UsingGUI:
        _GuiStatusClearPageData(backupID)

    aborted = False
    if backupID.endswith(' abort'):
        backupID = backupID[:-6]
        aborted = True

    backupDir = backup_db.GetDirectoryFromBackupId(backupID)
    if backupDir == "" or backupDir is None:
        dhnio.Dprint(6, 'backupshedule.backup_done  can not find %s  it in database' % backupID)
        return

    if aborted:
        backupDir = backup_db.GetDirectoryFromBackupId(backupID)
        backup_db.SetBackupStatus(backupDir, backupID, "stopped", "")
    else:
        backupDir = backup_db.GetDirectoryFromBackupId(backupID)
        backup_db.SetBackupStatus(backupDir, backupID, "done", str(time.time()))
    backup_db.Save()

    # backups.RemoveBackupInProcess(backupID)
    backup_monitor.Restart()

    if aborted:
        if _UsingGUI:
            _GuiBackupUpdate()
    else:
        if _UsingGUI:
            _GuiBackupUpdate()


def backup_fail(backupID):
    dhnio.Dprint(4, 'backupshedule.backup_fail ' + str(backupID))
    global _UsingGUI
    global _GuiBackupUpdate
    global _GuiStatusClearPageData
    if _UsingGUI:
        _GuiStatusClearPageData(backupID)

    backupDir = backup_db.GetDirectoryFromBackupId(backupID)
    if backupDir == "" or backupDir is None:
        dhnio.Dprint(6, 'backupshedule.backup_fail  can not find %s  it in database' % str(backupID))
        return

    backup_db.SetBackupStatus(backupDir, backupID, "failed", "")
    backup_db.Save()
    # backups.RemoveBackupInProcess(backupID)
    backup_monitor.Restart()

    if _UsingGUI:
        _GuiBackupUpdate()


def task(dirName=None):
    global _SheduledTasks
    if dirName is None:
        return _SheduledTasks
    return _SheduledTasks.get(unicode(dirName), None)


def next(dirName):
    global _SheduledTasks
#    lastRunId, lastRunSize, lastRunStatus, lastRunStart, lastRunFinish = backup_db.GetLastRunInfo(dirName)
#    schedule_type, schedule_time, schedule_interval, interval_details = backup_db.GetSchedule(dirName)
    schedule = backup_db.GetSchedule(dirName)
    if schedule is None:
        return None

#    dhnio.Dprint(8, 'backupshedule.next dirName=%s type=%s, time=%s, interval=%s, details=%s' % (str(dirName), schedule_type, schedule_time, schedule_interval, interval_details))
#    dhnio.Dprint(8, 'backupshedule.next %s %s' % (str(dirName), schedule))

    return schedule.next_time()
    
#    next_start = None
#    if schedule_type == 'none':
#        next_start = -1
#
#    elif schedule_type == 'hourly':
#        next_start = dhnmath.shedule_next_hourly(lastRunStart, schedule_interval)
#
#    elif schedule_type == 'daily':
#        next_start = dhnmath.shedule_next_daily(lastRunStart, schedule_interval, schedule_time)
#
#    elif schedule_type == 'weekly':
#        week_days = interval_details.split(' ')
#        week_day_numbers = []
#        week_day_names = list(calendar.day_name)
#        week_day_abbr = list(calendar.day_abbr)
#        for week_label in week_days:
#            try:
#                i = week_day_names.index(week_label)
#            except:
#                try:
#                    i = week_day_abbr.index(week_label)
#                except:
#                    continue
#            week_day_numbers.append(i)
#        next_start = dhnmath.shedule_next_weekly(lastRunStart, schedule_interval, schedule_time, week_day_numbers)
#
#    elif schedule_type == 'monthly':
#        months_labels = interval_details.split(' ')
#        months_numbers = []
#        months_names = list(calendar.month_name)
#        months_abbr = list(calendar.month_abbr)
#        for month_label in months_labels:
#            try:
#                i = months_names.index(month_label)
#            except:
#                try:
#                    i = months_abbr.index(month_label)
#                except:
#                    continue
#            months_numbers.append(i)
#        next_start = dhnmath.shedule_next_monthly(lastRunStart, schedule_interval, schedule_time, months_numbers)
#
#    return next_start


def debugWrite(debugtext): # useful when debugging this module, otherwise don't use (leave False)
    if False:
        debugFile = open("scheduledebug.txt","a")
        debugFile.write(debugtext+"\r\n")
        debugFile.close()
    else:
        dhnio.Dprint(8, debugtext)


#def types(k=None):
#    d = {'0': 'none',
#         '1': 'hourly',
#         '2': 'daily',
#         '3': 'weekly',
#         '4': 'monthly',
#         '5': 'continuously'}
#    if k is None:
#        return d
#    return d.get(k, d['0'])


#def labels():
#    return {'n': 'none',
#            'h': 'hourly',
#            'd': 'daily',
#            'w': 'weekly',
#            'm': 'monthly',
#            'c': 'continuously'}


#def default():
#    return {'type': 'none',
#            'interval': '1',
#            'time': '',
#            'details': '',}


#def format():
#    return '''
#Schedule compact format:
#[mode].[interval].[time].[details]
#
#mode:
#  n-none, h-hourly, d-daily, w-weekly, m-monthly
#  
#interval:
#  just a number - how often to restart the task, default is 1
#    
#time:
#  [hour]:[minute]
#  
#details:
#  for weeks: Mon Tue Wed Thu Fri Sat Sun
#  for months: Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec
#  
#some examples:
#  n.1..                   no schedule
#  hourly.3                each 3 hours
#  daily.4.10:15.          every 4th day at 10:15
#  w.1.3:00.MonSat         every Monday and Saturday at 3:00 in the night
#  weekly.4.18:45.MonTueWedThuFriSatSun
#                          every day in each 4th week in 18:45
#  m.5.12:34.JanJul        5th Jan and 5th July at 12:34
#'''


#def unpack(s):
#    try:
#        parts = s.split('.')
#        parts += ['']*(4-len(parts))
#        (sh_type, sh_interval, sh_time, sh_details) = parts[0:4]
#        sh_type = sh_type.lower()
#        if sh_type not in ['n', 'none', 'h', 'hourly']:
#            sh_interval = int(sh_interval)
#            time.strptime(sh_time, '%H:%M')
#    except:
#        dhnio.Dprint(2, 'backupshedule.unpack WARNING incorrect shedule '+s)
#        dhnio.DprintException()
#        return None
#    if sh_type in labels().keys():
#        sh_type = labels()[sh_type]
#    if sh_type not in labels().values():
#        dhnio.Dprint(2, 'backupshedule.unpack WARNING incorrect shedule '+s)
#        return None
#    sh_details_new = ''
#    for i in range(len(sh_details)/3):
#        label = sh_details[i*3:i*3+3]
#        if sh_type == 'weekly' and not label in calendar.day_abbr:
#            dhnio.Dprint(2, 'backupshedule.unpack WARNING incorrect shedule '+s)
#            return None
#        if sh_type == 'monthly' and not label in calendar.month_abbr:
#            dhnio.Dprint(2, 'backupshedule.unpack WARNING incorrect shedule '+s)
#            return None
#        sh_details_new += label + ' '
#    return {'type': sh_type,
#            'interval': str(sh_interval),
#            'time': str(sh_time),
#            'details': sh_details_new.strip(),}


#def split(t):
#    typ = str(t[0])
#    if typ in types().keys():
#        typ = types()[typ]
#    if typ not in types().values():
#        dhnio.Dprint(2, 'backupshedule.split WARNING incorrect shedule '+str(t))
#        return default()
#    return {
#        'type':         typ,
#        'time':         str(t[1]),
#        'interval':     str(t[2]),
#        'details':      str(t[3]), }


#-------------------------------------------------------------------------------


def main():
    nt = dhnmath.shedule_next_daily(time.time()-60*60*24*2, 4, '12:00')
    print 'daily', time.asctime(time.localtime(nt))
    nw = dhnmath.shedule_next_weekly(time.time(),1,'12:00', [0,])
    print 'weekly', time.asctime(time.localtime(nw))
    nm = dhnmath.shedule_next_monthly(time.time(),1,'12:00', [1,])
    print 'monthly', time.asctime(time.localtime(nm))
    print unpack('weekly.4.18:45.MonTueWedThuFriSatSun')
    print unpack('h.1')


if __name__ == '__main__':
    dhnio.SetDebug(12)
    main()


