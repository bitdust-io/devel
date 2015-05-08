#!/usr/bin/python
#sqlio.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: sqlio

"""

import os
import sys

import sqlite3

#------------------------------------------------------------------------------ 

from logs import lg

from lib import nameurl

#------------------------------------------------------------------------------ 

_DBConnection = None
_DBCursor = None

#------------------------------------------------------------------------------ 

_Prefix = {'identity': 'identityapp_',
           'supplier': 'supplierapp_',
           'customer': 'customerapp_',
           'friend': 'firendapp_',
           'backupfsitem': 'myfilesapp_',
           'localfsitem': 'myfilesapp_',
           'remotematrixitem': 'myfilesapp_',
           'localmatrixitem': 'myfilesapp_',
           'option': 'settingsapp_',
           'automat': 'debugapp_',
           'ratingmonth': 'ratingapp_',
           'ratingtotal': 'ratingapp_',
           }

_SQL = \
    """[create identity]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY,
idurl text,
src text);

[delete identity]
DELETE FROM %s;

[insert identity]
INSERT INTO %s VALUES (?,?,?);

[update identity]
UPDATE %s SET idurl=?, src=? WHERE id=?;

[create supplier]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY, 
idurl text);

[delete supplier]
DELETE FROM %s;

[insert supplier]
INSERT INTO %s VALUES (?,?);

[update supplier]
UPDATE %s SET idurl=? WHERE id=?;

[create customer]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY, 
idurl text);

[delete customer]
DELETE FROM %s;

[insert customer]
INSERT INTO %s VALUES (?,?);

[update customer]
UPDATE %s SET idurl=? WHERE id=?;

[create backupfsitem]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY, 
backupid text, 
size integer,
path text);

[delete backupfsitem]
DELETE FROM %s;

[insert backupfsitem]
INSERT INTO %s VALUES (?,?,?,?);

[update backupfsitem]
UPDATE %s SET size=? path=? WHERE backupid=?;

[create friend]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY, 
idurl text,
name text);

[delete friend]
DELETE FROM %s;

[insert friend]
INSERT INTO %s VALUES (?,?,?);

[update friend]
UPDATE %s SET idurl=? name=? WHERE id=?;

[create localfsitem]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY, 
mask text,
path text);

[create remotematrixitem]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY,
backupid text,
blocknum integer,
dataparity integer, 
suppliernum integer,
value integer);

[create localmatrixitem]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY,
backupid text,
blocknum integer,
dataparity integer, 
suppliernum integer,
value integer);

[create option]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY,
path text,
value text,
type integer,
label text, 
info text);

[create automat]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY,
automatid integer,
index integer,
name text,
state text);

[create ratingmonth]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY,
idurl text,
all integer,
alive integer);

[create ratingtotal]
CREATE TABLE %s (
id integer NOT NULL PRIMARY KEY,
idurl text,
all integer,
alive integer);"""

#------------------------------------------------------------------------------ 

def withprefix(table_name):
    global _Prefix
    return _Prefix[table_name] + table_name


def db():
    global _DBConnection
    return _DBConnection


def dbcur():
    global _DBConnection
    global _DBCursor
    if _DBCursor is None:
        lg.out(4, 'sqlio.dbcur created a new DB cursor')
        _DBCursor = _DBConnection.cursor()
    return _DBCursor


def dbcommit():
    lg.out(8, 'sqlio.dbcommit')
    db().commit()
    lg.out(8, '        OK')

#------------------------------------------------------------------------------ 

def init(database_info):
    global _DBConnection
    global _SQL
    lg.out(4, 'sqlio.init')
    parts = _SQL.split('\n\n')
    _SQL = {}
    for part in parts:
        lines = part.splitlines()
        fullcmd = lines[0].strip('[]')
        sqlsrc = ''.join(lines[1:])
        cmd, name = fullcmd.split(' ')
        _SQL[fullcmd] = sqlsrc % withprefix(name)
    _DBConnection = sqlite3.connect(database_info)
    dbcur().execute('SELECT SQLITE_VERSION();')
    lg.out(4, "    SQLite version is %s" % dbcur().fetchone())
    dbcur().execute("SELECT name FROM sqlite_master WHERE type='table';")
    tableslist = map(lambda x: str(x[0]), dbcur().fetchall())
    lg.out(4, "    %d tables found" % len(tableslist))
    if withprefix('identity') in tableslist:
        lg.out(4, '    "identity" table exist')
    else:
        dbcur().execute(_SQL['create identity'])
        lg.out(4, '    created table "identity"')
    if withprefix('supplier') in tableslist:
        lg.out(4, '    "supplier" table exist')
    else:
        dbcur().execute(_SQL['create supplier'])
        lg.out(4, '    created table "supplier"')
    if withprefix('customer') in tableslist:
        lg.out(4, '    "customer" table exist')
    else:
        dbcur().execute(_SQL['create customer'])
        lg.out(4, '    created table "customer"')
    if withprefix('friend') in tableslist:
        lg.out(4, '    "friend" table exist')
    else:
        dbcur().execute(_SQL['create friend'])
        lg.out(4, '    created table "friend"')
    dbcommit()
    

def shutdown():    
    global _DBCursor
    global _DBConnection
    lg.out(4, 'sqlio.shutdown')
    if _DBConnection:
        lg.out(4, '    close connection %s' % _DBConnection)
        _DBConnection.close()
    _DBCursor = None
    _DBConnection = None
        
#------------------------------------------------------------------------------

def update_identities(ids, cache, updated_idurl):
    lg.out(6, 'sqlio.update_identities %d items' % len(cache))
    l = map(lambda itm: (ids[itm[0]], itm[0], itm[1].serialize(),), cache.items())
    try:
        dbcur().execute(_SQL['delete identity'])
        dbcur().executemany(_SQL['insert identity'], l)
    except:
        lg.exc()
    dbcommit()
    # TODO - need to repaint GUI here


def update_suppliers(old_suppliers_list, suppliers_list):
    lg.out(6, 'sqlio.update_suppliers %d items' % len(suppliers_list))
    l = map(lambda i: (i, suppliers_list[i],), range(len(suppliers_list)))
    try:
        dbcur().execute(_SQL['delete supplier'])
        dbcur().executemany(_SQL['insert supplier'], l)
    except:
        lg.exc()
    dbcommit()
    # TODO - need to repaint GUI here


def update_customers(old_customers_list, customers_list):
    lg.out(6, 'sqlio.update_customers %d items' % len(customers_list))
    l = map(lambda i: (i, customers_list[i],), range(len(customers_list)))
    try:
        dbcur().execute(_SQL['delete customer'])
        dbcur().executemany(_SQL['insert customer'], l)
    except:
        lg.exc()
    dbcommit()
    # TODO - need to repaint GUI here


def update_friends(old_friends_list, friends_list):
    lg.out(6, 'sqlio.update_friends %d items' % len(friends_list))
    l = map(lambda i: (i, friends_list[i][0], friends_list[i][1]), range(len(friends_list)))
    try:
        dbcur().execute(_SQL['delete friend'])
        dbcur().executemany(_SQL['insert friend'], l)
    except:
        lg.exc()
    dbcommit()
    # TODO - need to repaint GUI here


def update_contact_status(idurl):
    pass
    # TODO - need to repaint GUI here


def update_backup_fs(backup_fs_raw_list):
    lg.out(6, 'sqlio.update_backup_fs %d items' % len(backup_fs_raw_list))
    # dbcur().execute(_SQL['delete backupfsitem'])
    # dbcur().executemany(_SQL['insert backupfsitem'], backup_fs_raw_list)
    # db().commit()
    # TODO - need to repaint GUI here
    
