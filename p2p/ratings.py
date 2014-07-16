#!/usr/bin/python
#ratings.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

import os
import sys
import time
import math


try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in ratings.py')

from twisted.internet import task


import lib.bpio as bpio
import lib.maths as maths
import lib.misc as misc
import lib.nameurl as nameurl
import lib.settings as settings
import lib.contacts as contacts


import contact_status


#-------------------------------------------------------------------------------

_LoopCountRatingsTask = None
_IndexMonth = {}
_IndexTotal = {}
_InitDone = False

#-------------------------------------------------------------------------------


def init():
    global _InitDone
    if _InitDone:
        return
    bpio.log(4, 'ratings.init')
    read_index()
    run()
    _InitDone = True


def shutdown():
    bpio.log(4, 'ratings.shutdown')
    stop()


def run():
    global _LoopCountRatingsTask
    stop()
    interval = maths.interval_to_next_hour()
    # debug
    #interval = 5
    reactor.callLater(interval, start)
    bpio.log(6, 'ratings.run will start after %s minutes' % str(interval/60.0))
    
    
def start():
    global _LoopCountRatingsTask
    _LoopCountRatingsTask = task.LoopingCall(rate_all_users)
    _LoopCountRatingsTask.start(settings.DefaultAlivePacketTimeOut())
    bpio.log(6, 'ratings.start will count ratings every %s minutes' % str(settings.DefaultAlivePacketTimeOut()/60.0))


def stop():
    global _LoopCountRatingsTask
    if _LoopCountRatingsTask:
        if _LoopCountRatingsTask.running:
            _LoopCountRatingsTask.stop()
        del _LoopCountRatingsTask
        _LoopCountRatingsTask = None
        bpio.log(6, 'ratings.stop task finished')
        
            
def rating_dir(idurl):
    return os.path.join(settings.RatingsDir(), nameurl.UrlFilename(idurl))


def rating_month_file(idurl, monthstr=None):
    if monthstr is None:
        monthstr = time.strftime('%m%y')
    return os.path.join(rating_dir(idurl), monthstr)


def rating_total_file(idurl):
    return os.path.join(rating_dir(idurl), 'total')


def exist_rating_dir(idurl):
    return bpio._dir_exist(rating_dir(idurl))


def make_rating_dir(idurl):
    bpio._dir_make(rating_dir(idurl))


def read_month_rating_dict(idurl, monthstr=None):
    if monthstr is None:
        monthstr = time.strftime('%m%y')
    return bpio._read_dict(rating_month_file(idurl, monthstr))


def write_month_rating_dict(idurl, rating_dict, monthstr=None):
    if monthstr is None:
        monthstr = time.strftime('%m%y')
    return bpio._write_dict(rating_month_file(idurl, monthstr), rating_dict)


def read_total_rating_dict(idurl):
    return bpio._read_dict(rating_total_file(idurl))


def write_total_rating_dict(idurl, rating_dict):
    return bpio._write_dict(rating_total_file(idurl), rating_dict)


def make_blank_rating_dict():
    return {'all':'0', 'alive':'0'}


def increase_rating(idurl, alive_state):
    if not exist_rating_dir(idurl):
        make_rating_dir(idurl)

    month_rating = read_month_rating_dict(idurl)
    if month_rating is None:
        month_rating = make_blank_rating_dict()
    try:
        mallI = int(month_rating['all'])
        maliveI = int(month_rating['alive'])
    except:
        mallI = 0
        maliveI = 0
    mallI += 1
    if alive_state:
        maliveI += 1
    month_rating['all'] = str(mallI)
    month_rating['alive'] = str(maliveI)
    write_month_rating_dict(idurl, month_rating)

    total_rating = read_total_rating_dict(idurl)
    if total_rating is None:
        total_rating = make_blank_rating_dict()
    try:
        tallI = int(total_rating['all'])
        taliveI = int(total_rating['alive'])
    except:
        tallI = 0
        taliveI = 0
    tallI += 1
    if alive_state:
        taliveI += 1
    total_rating['all'] = str(tallI)
    total_rating['alive'] = str(taliveI)
    write_total_rating_dict(idurl, total_rating)
    return mallI, maliveI, tallI, taliveI


def rate_all_users():
    bpio.log(4, 'ratings.rate_all_users')
    monthStr = time.strftime('%B')
    for idurl in contacts.getContactsAndCorrespondents():
        isalive = contact_status.isOnline(idurl)
        mall, malive, tall, talive = increase_rating(idurl, isalive)
        month_percent = 100.0*float(malive)/float(mall)
        total_percent = 100.0*float(talive)/float(tall)
        bpio.log(4, '[%6.2f%%: %s/%s] in %s and [%6.2f%%: %s/%s] total - %s' % (
            month_percent,
            malive,
            mall,
            monthStr,
            total_percent,
            talive,
            tall,
            nameurl.GetName(idurl),))
    read_index()


def remember_connected_time(idurl):
    if not exist_rating_dir(idurl):
        make_rating_dir(idurl)
    bpio._write_data(os.path.join(rating_dir(idurl), 'connected'), time.strftime('%d%m%y %H:%M:%S'))
                         

def connected_time(idurl):
    s = bpio._read_data(os.path.join(rating_dir(idurl), 'connected'))
    if s == '':
        return 0
    try:
        return time.mktime(time.strptime(s, '%d%m%y %H:%M:%S'))
    except:
        return 0


def read_all_monthly_ratings(idurl):
    if not exist_rating_dir(idurl):
        return None
    d = {}
    for monthstr in os.listdir(rating_dir(idurl)):
        if monthstr == 'total':
            continue
        if monthstr == 'last':
            continue
        month_rating = read_month_rating_dict(idurl, monthstr)
        if month_rating is None:
            continue
        d[monthstr] = month_rating
    return d


def read_index(monthstr=None):
    global _IndexMonth
    global _IndexTotal
    #bpio.log(4, 'ratings.read_index')
    if monthstr is None:
        monthstr = time.strftime('%m%y')
    _IndexMonth.clear()
    _IndexTotal.clear()
    for idurl_filename in os.listdir(settings.RatingsDir()):
        idurl = nameurl.FilenameUrl(idurl_filename)
        if idurl is None:
            continue
        month = read_month_rating_dict(idurl, monthstr)
        total = read_total_rating_dict(idurl)
        _IndexMonth[idurl] = {'all': '0', 'alive': '0'} if month is None else month
        _IndexTotal[idurl] = {'all': '0', 'alive': '0'} if total is None else total
        #bpio.log(4, '    [%s]: %s, %s' % (nameurl.GetName(idurl), _IndexMonth[idurl], _IndexTotal[idurl]))


def month(idurl):
    global _IndexMonth
    return _IndexMonth.get(idurl, {'all': '0', 'alive': '0'})


def total(idurl):
    global _IndexTotal
    return _IndexTotal.get(idurl, {'all': '0', 'alive': '0'})


def month_percent(idurl):
    try:
        r = month(idurl)
        return round(100.0 * float(r['alive']) / float(r['all']), 2)
    except:
        return 0.0
    

def total_percent(idurl):
    try:
        r = total(idurl)
        return round(100.0 * float(r['alive']) / float(r['all']), 2)
    except:
        return 0.0


#-------------------------------------------------------------------------------


def main():
    pass

if __name__ == '__main__':
    main()
