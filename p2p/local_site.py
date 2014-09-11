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
from twisted.application import service, strports
from twisted.web import server 
from twisted.web import http

import sqlite3
import webbrowser

root_pth = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
if not ( len(sys.path) > 0 and sys.path[0] == root_pth ):
    sys.path.insert(0, os.path.join(root_pth))
sys.path.insert(1, os.path.join(root_pth, 'web'))

from django.core.handlers.wsgi import WSGIHandler

from logs import lg
from lib import bpio
from lib import settings

#------------------------------------------------------------------------------ 

_SQL = \
"""[create supplier]
CREATE TABLE bpapp_supplier (
id integer NOT NULL PRIMARY KEY, 
idurl varchar(200) NOT NULL);

[delete supplier]
DELETE FROM bpapp_supplier;

[insert supplier]
INSERT INTO bpapp_supplier VALUES (?,?);

[update supplier]
UPDATE bpapp_supplier SET idurl=? WHERE id=?;

[create customer]
CREATE TABLE bpapp_customer (
id integer NOT NULL PRIMARY KEY, 
idurl varchar(200) NOT NULL);

[delete customer]
DELETE FROM bpapp_customer;

[insert customer]
INSERT INTO bpapp_customer VALUES (?,?);

[update customer]
UPDATE bpapp_customer SET idurl=? WHERE id=?;

[create backupfsitem]
CREATE TABLE bpapp_backupfsitem (
id integer NOT NULL PRIMARY KEY, 
backupid text NOT NULL, 
size integer,
path text);

[delete backupfsitem]
DELETE FROM bpapp_backupfsitem;

[insert backupfsitem]
INSERT INTO bpapp_backupfsitem VALUES (?,?,?,?);

[update backupfsitem]
UPDATE bpapp_backupfsitem SET size=? path=? WHERE backupid=?;

[create localfsitem]

[create backupmatrixitem]

[create_table_option]

[create_table_automat]

[create_table_rating]"""

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
    sqllist = _SQL.split('\n\n')
    _SQL = {}
    for sql in sqllist:
        lines = sql.splitlines()
        _SQL[lines[0].strip('[]')] = ''.join(lines[1:])
    _DBConnection = sqlite3.connect(os.path.join(root_pth, 'web', 'asite.db'))
    dbcur().execute('SELECT SQLITE_VERSION();')
    lg.out(4, "    SQLite version is %s" % dbcur().fetchone())
    dbcur().execute("SELECT name FROM sqlite_master WHERE type='table';")
    tableslist = map(lambda x: str(x[0]), dbcur().fetchall())
    lg.out(4, "    %d tables found" % len(tableslist))
    if 'bpapp_supplier' in tableslist:
        lg.out(4, '    "bpapp_supplier" table exist')
    else:
        dbcur().execute(_SQL['create supplier'])
        lg.out(4, '    created table "bpapp_supplier"') 
    if 'bpapp_customer' in tableslist:
        lg.out(4, '    "bpapp_customer" table exist')
    else:
        dbcur().execute(_SQL['create customer'])
        lg.out(4, '    created table "bpapp_customer"')
    if 'bpapp_backupfsitem' in tableslist:
        lg.out(4, '    "bpapp_backupfsitem" table exist')
    else:
        dbcur().execute(_SQL['create backupfsitem'])
        lg.out(4, '    created table "bpapp_backupfsitem"')
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

