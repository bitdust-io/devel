#!/usr/bin/python
#money.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: money

A methods to process accounting operations.
"""

import os
import sys
import string
import StringIO
import time

import lib.dhnio as dhnio
import lib.misc as misc
import lib.settings as settings
import lib.nameurl as nameurl

#------------------------------------------------------------------------------ 

_receiptId = 0
_InboxReceiptCallback = None

#------------------------------------------------------------------------------

def SetInboxReceiptCallback(cb):
    global _InboxReceiptCallback
    _InboxReceiptCallback = cb

def Receipt(tup):
    SaveReceipt(tup)

def SaveReceipt(data):
    try:
        rfilename = settings.getReceiptsDir() + os.sep + data[0] + '.receipt'
    except:
        return
    src = ''
    for i in data:
        if isinstance(i, float):
            src += '%f\n' % i
        else:
            src += str(i).strip() + '\n'
    dhnio.Dprint(8, 'money.SaveReceipt %s to %s' % (data[0], rfilename))
    if not dhnio._write_data(rfilename, src.strip()):
        dhnio.Dprint(1, 'money.SaveReceipt ERROR during writing to file ' + rfilename)

    SaveBalance(data[6], data[8], data[0])
    currentBal, currentNTBal, maxReceiptId = LoadBalance()
#    if (int(data[0]) == maxReceiptId): # don't set burn rate unless this packet is most recent receipt, not just filling in a missing receipt
#        try:
#            summary.SetBalanceAndBurnRate(float(data[6])+float(data[8]), float(data[5])+float(data[7]))
#        except:
#            dhnio.Dprint(1, 'money.SaveReceipt ERROR setting burn rate or balance for ' + str(data))

def UnpackReceipt(body): # TODO, appears not to be called
    sin = StringIO.StringIO(str(body))
    ReceiptID = sin.readline().strip()
    DateTime = sin.readline().strip()
    Command = sin.readline().strip()
    FromID = sin.readline().strip()
    ToID = sin.readline().strip()
    Amount = sin.readline().strip()
    Balance = sin.readline().strip()
    Report = sin.read().strip()
    return (ReceiptID, DateTime, Command, FromID, ToID, Amount, Balance, Report)

def UnpackReceipt2(body):
    sin = StringIO.StringIO(str(body))
    ReceiptID = misc.receiptIDstr(sin.readline().strip())
    DateTime = sin.readline().strip()
    Command = sin.readline().strip()
    FromID = sin.readline().strip()
    ToID = sin.readline().strip()
    try:
        Amount = float(sin.readline().strip())
        Balance = float(sin.readline().strip())
        AmountNT = float(sin.readline().strip())
        BalanceNT = float(sin.readline().strip())
    except:
        Amount = 0.0
        Balance = 0.0
        AmountNT = 0.0
        BalanceNT = 0.0
    PayRate = sin.readline().strip()
    Report = sin.read().strip()
    return (ReceiptID, DateTime, Command, FromID, ToID, Amount, Balance, AmountNT, BalanceNT, PayRate, Report)

def UnpackReport(report):
    d = {    'suppliers':   {'space': 0.0, 'costs':  0.0, },
             'customers':   {'space': 0.0, 'income': 0.0, },
             'total':       '',
             'text':        '', }
    try:
        for line in report.split('\n'):
            words = line.strip().split(' ')
            if words[0] == 'supplier':
                d['suppliers'][words[1]] = words[2]
            elif words[0] == 'suppliers':
                d['suppliers']['space'] = words[1]
                d['suppliers']['costs'] = words[2]
            elif words[0] == 'customer':
                d['customers'][words[1]] = words[2]
            elif words[0] == 'customers':
                d['customers']['space'] = words[1]
                d['customers']['income'] = words[2]
            elif words[0] == 'total':
                d['total'] += words[1] + '\n'
            else:
                if not line.strip().startswith('end') and not line.strip().endswith('end'):
                    d['text'] += line.strip() + '\n'
    except:
        dhnio.DprintException()
    return d

def LoadReceipt(path):
    fin = open(path, 'r')
    body = fin.read()
    fin.close()
    return UnpackReceipt2(body)

def ReadReceipt( number ):
    path = settings.getReceiptsDir() + os.sep + number + '.receipt'
    if not os.path.exists(path):
        dhnio.Dprint(1, 'money.ReadReceipt ERROR file not exist ' + path)
        return None
    return LoadReceipt(path)

def ReadAllReceipts():
    l = []
    burnRate = 0.0
    balanceTrans = 0.0
    balanceNonTrans = 0.0

    try:
        current_balance = ''
        filenames = os.listdir(settings.getReceiptsDir())
        filenames.sort()
        for filename in filenames:
            if not filename.endswith('.receipt'):
                continue

            receipt_id = filename[:-11]
            if len(receipt_id) != 8:
                continue
            try:
                receipt_id = int(receipt_id)
            except:
                continue
            if receipt_id < 0:
                continue
            if receipt_id > 99999999:
                continue

            path = settings.getReceiptsDir() + os.sep + filename
            if not os.path.exists(path):
                continue

            receipt = LoadReceipt(path)
            if receipt is None:
                continue
            if receipt[2] == '' or receipt[3] == '' or receipt[4] == '': # if we don't have a to, from, or command leave out?
                continue

            tupple = (
                receipt[0],
                receipt[2],
                GetTrueAmount(receipt),
                nameurl.GetName(receipt[3]),
                nameurl.GetName(receipt[4]),
                receipt[1])
            l.append(tupple)

            balanceTrans = float(receipt[6])
            balanceNonTrans = float(receipt[8])
            if receipt[2] == 'space':
                burnRate = float(receipt[5]) + float(receipt[7])

    except:
        dhnio.Dprint(1, 'money.ReadAllReceipts unexpected ERROR')
        dhnio.DprintException()

    #def key_func(t):
    #    try:
    #        return int(t[0])
    #    except:
    #        return 0
    #l.sort(key=key_func)

#    if summary.SetBalanceAndBurnRate is not None:
#        summary.SetBalanceAndBurnRate(balanceTrans+balanceNonTrans, burnRate)

    return l


def LoadBalance():
    src = dhnio._read_data(settings.BalanceFile())
    if src is None:
        src = '0.0 0.0 0'
        dhnio._write_data(settings.BalanceFile(), src)
    words = src.split(' ')
    try:
        b = float(words[0])
        b2 = float(words[1])
    except:
        b = 0.0
        b2 = 0.0
    try:
        r = int(words[2])
    except:
        r = 0

    return b, b2, r


def SaveBalance(balance, balancent, receipt_id):
    src = dhnio._read_data(settings.BalanceFile())
    if src is None:
        src = '0.0 0.0 0'

    words = src.split(' ')
    try:
        b = words[0]
        b2 = words[1]
        r = words[2]
    except:
        b = '0.0'
        b2 = '0.0'
        r = '0'
    try:
        b = float(b)
        b2 = float(b2)
        r = int(r)
    except:
        b = 0.0
        b2 = 0.0
        r = 0
    try:
        balanceV = float(balance)
        balancentV = float(balancent)
        receipt_idV = int(receipt_id)
    except:
        balanceV = 0.0
        balancentV = 0.0
        receipt_idV = 0

    if receipt_idV >= r:
        src = '%f %f %d' % (balanceV, balancentV, receipt_idV)

    return dhnio._write_data(settings.BalanceFile(), src)


def SearchMissingReceipts(last_receipt_id=-1):
    dhnio.Dprint(8, 'money.SearchMissingReceipts ' + str(last_receipt_id))

    def try2remove(filepath):
        try:
            os.remove(filepath)
        except:
            dhnio.Dprint(4, 'money.SearchMissingReceipts.try2remove WARNING can not remove ' + filepath)
        dhnio.Dprint(6, 'money.SearchMissingReceipts.try2remove %s removed' % filepath)

    existing_receipts = set()
    max_index = -1
    for filename in os.listdir(settings.getReceiptsDir()):
        filepath = os.path.join(settings.getReceiptsDir(), filename)
        if not filename.endswith('.receipt'):
            try2remove(filepath)
            continue
        receipt_id = filename[:-11]
        if len(receipt_id) != 8:
            try2remove(filepath)
            continue
        try:
            receipt_id = int(receipt_id)
        except:
            try2remove(filepath)
            continue
        if receipt_id < 0:
            try2remove(filepath)
            continue
        if receipt_id > 99999999:
            try2remove(filepath)
            continue
        if receipt_id > max_index:
            max_index = receipt_id
        existing_receipts.add(receipt_id)

    if last_receipt_id > max_index:
        max_index = last_receipt_id

    r = []
    dhnio.Dprint(8, 'money.SearchMissingReceipts existing_receipts=%s  max_index=%s' % (str(len(existing_receipts)), str(max_index)))

    for i in range(max_index + 1):
        if i not in existing_receipts:
            r.append(misc.receiptIDstr(i))
        if len(r) >= 100:
            break

    if max_index not in existing_receipts:
        r.insert(0, misc.receiptIDstr(max_index))

    existing_receipts.clear()
    return r


def GetTrueAmount(receipt):  # return a float, receipt from UnpackReceipt2 has the trans and nt as floats already
    try:
        return receipt[7] + receipt[5]
    except:
        dhnio.Dprint(1, 'money.GetTrueAmount ERROR with receipt: ' + str(receipt))
        return 0.0

def InboxReceipt(newpacket):
    global _InboxReceiptCallback
    dhnio.Dprint(6, 'money.InboxReceipt ')
    sio = StringIO.StringIO(newpacket.Payload)
    receipt_body = ''
    for line in sio:
        receipt_body += line
        if line.startswith('end'):
            t = UnpackReceipt2(receipt_body.strip())
            receipt_body = ''
            SaveReceipt(t)
    if _InboxReceiptCallback:
        _InboxReceiptCallback(newpacket)
            
    
def main():
    print SearchMissingReceipts()

if __name__ == '__main__':
    main()






