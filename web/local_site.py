#!/usr/bin/python
#local_site.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: local_site

"""

import os
import sys

from twisted.web import wsgi
from twisted.internet import reactor
# from twisted.application import service, strports
from twisted.web import server 
# from twisted.web import http

import sqlite3
# import webbrowser

root_pth = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
if not ( len(sys.path) > 0 and sys.path[0] == root_pth ):
    sys.path.insert(0, os.path.join(root_pth))
sys.path.insert(1, os.path.join(root_pth, 'web'))

from django.core.handlers.wsgi import WSGIHandler

from logs import lg
from system import bpio
from main import settings

#------------------------------------------------------------------------------ 

_Prefix = 'bpapp_'

_SQL = \
"""[create supplier]
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

_Listener = None
_DBConnection = None
_DBCursor = None

#------------------------------------------------------------------------------ 

def db():
    global _DBConnection
    return _DBConnection


def dbcur():
    global _DBConnection
    global _DBCursor
    if _DBCursor is None:
        _DBCursor = _DBConnection.cursor()
    return _DBCursor


def withprefix(table_name):
    global _Prefix
    return _Prefix + table_name

    
def init():
    global _Listener
    if _Listener:
        return
    lg.out(4, 'local_site.init')
    init_database()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.asite.settings") 
    wsgi_resource = wsgi.WSGIResource(reactor, reactor.getThreadPool(), WSGIHandler())
    site = server.Site(wsgi_resource)
    _Listener = reactor.listenTCP(8080, site)
    # webbrowser.open_new('http://localhost:8080')
    

def shutdown():
    lg.out(4, 'local_site.shutdown')
    global _DBCursor
    global _DBConnection
    global _Listener
    _Listener.stopListening()
    _Listener = None
    db().close()
    _DBCursor = None
    _DBConnection = None         

#------------------------------------------------------------------------------ 

def init_database():
    global _DBConnection
    global _SQL
    parts = _SQL.split('\n\n')
    _SQL = {}
    for part in parts:
        lines = part.splitlines()
        fullcmd = lines[0].strip('[]')
        sqlsrc = ''.join(lines[1:])
        cmd, name = fullcmd.split(' ')
        _SQL[fullcmd] = sqlsrc % name
    _DBConnection = sqlite3.connect(os.path.join(root_pth, 'web', 'asite.db'))
    dbcur().execute('SELECT SQLITE_VERSION();')
    lg.out(4, "    SQLite version is %s" % dbcur().fetchone())
    dbcur().execute("SELECT name FROM sqlite_master WHERE type='table';")
    tableslist = map(lambda x: str(x[0]), dbcur().fetchall())
    lg.out(4, "    %d tables found" % len(tableslist))
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
    db().commit()
        

def update_suppliers(suppliers_list):
    dbcur().execute(_SQL['delete supplier'])
    l = map(lambda i: (i, suppliers_list[i],), range(len(suppliers_list)))
    dbcur().executemany(_SQL['insert supplier'], l)
    db().commit()
    lg.out(4, '    updated %d suppliers' % len(suppliers_list))


def update_customers(customers_list):
    dbcur().execute(_SQL['delete customer'])
    l = map(lambda i: (i, customers_list[i],), range(len(customers_list)))
    dbcur().executemany(_SQL['insert customer'], l)
    db().commit()
    lg.out(4, '    updated %d customers' % len(customers_list))


def update_backup_fs(backup_fs_raw_list):
    dbcur().execute(_SQL['delete backupfsitem'])
    dbcur().executemany(_SQL['insert backupfsitem'], backup_fs_raw_list)
    db().commit()
    lg.out(4, '    updated %d backup_fs items' % len(backup_fs_raw_list))

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)
    reactor.callWhenRunning(init)
    reactor.run()
    lg.out(2, 'reactor stopped, EXIT')

