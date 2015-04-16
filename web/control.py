#!/usr/bin/python
# control.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: control

"""

import os
import sys

from twisted.web import wsgi
from twisted.internet import reactor
from twisted.web import server

import sqlite3

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(
        0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))
    # sys.path.insert(1, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..', 'web')))

# root_pth = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
# if not ( len(sys.path) > 0 and sys.path[0] == root_pth ):
#     sys.path.insert(0, os.path.join(root_pth))
# sys.path.insert(1, os.path.join(root_pth, 'web'))

#------------------------------------------------------------------------------ 

from django.core.wsgi import get_wsgi_application

#------------------------------------------------------------------------------ 

from logs import lg

from system import bpio

from main import settings

from contacts import contactsdb

#------------------------------------------------------------------------------

_Prefix = 'bpapp_'

# BASE_DIR1 = os.path.dirname(os.path.dirname(__file__))
# DB_FILE = os.path.join(BASE_DIR1, 'asite.sqlite3')

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
    lg.out(4, 'control.init')
    lg.out(4, '    system variable: DJANGO_SETTINGS_MODULE=web.asite.settings')
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.asite.settings")
    init_database()
    sub_path = str(os.path.abspath(os.path.join(bpio.getExecutableDir(), 'web')))
    if not sys.path.count(sub_path):
        lg.out(4, '    insert into python path: %s' % sub_path)
        # sys.path.insert(0, sub_path)
    wsgi_resource = wsgi.WSGIResource(
        reactor, reactor.getThreadPool(), get_wsgi_application())
    site = server.Site(wsgi_resource)
    web_port = 8080
    _Listener = reactor.listenTCP(web_port, site)
    lg.out(4, '    listener started on port %d' % web_port)
    contactsdb.SetSuppliersChangedCallback(update_suppliers)
    contactsdb.SetCustomersChangedCallback(update_customers)
    contactsdb.SetCorrespondentsChangedCallback(update_friends)


def shutdown():
    lg.out(4, 'control.shutdown')
    global _DBCursor
    global _DBConnection
    global _Listener
    _Listener.stopListening()
    _Listener = None
    db().close()
    _DBCursor = None
    _DBConnection = None


def show():
    lg.out(4, 'control.show')
    import webbrowser
    webbrowser.open_new('http://localhost:8080')


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
        _SQL[fullcmd] = sqlsrc % withprefix(name)
    from django.conf import settings as django_settings
    _DBConnection = sqlite3.connect(
        django_settings.DATABASES['default']['NAME'])
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
    if withprefix('friend') in tableslist:
        lg.out(4, '    "friend" table exist')
    else:
        dbcur().execute(_SQL['create friend'])
        lg.out(4, '    created table "friend"')
    db().commit()

#------------------------------------------------------------------------------

def on_suppliers_changed(current_suppliers):
    update_suppliers(current_suppliers)

def on_tray_icon_command(cmd):
    from main import shutdowner
    from p2p import network_connector
    if cmd == 'exit':
        # SendCommandToGUI('exit')
        shutdowner.A('stop', 'exit')

    elif cmd == 'restart':
        # SendCommandToGUI('exit')
        appList = bpio.find_process(['bpgui.',])
        if len(appList) > 0:
            shutdowner.A('stop', 'restartnshow') # ('restart', 'show'))
        else:
            shutdowner.A('stop', 'restart') # ('restart', ''))
        
    elif cmd == 'reconnect':
        network_connector.A('reconnect')

    elif cmd == 'show':
        show()

    elif cmd == 'hide':
        pass
        # SendCommandToGUI('exit')
        
    elif cmd == 'toolbar':
        pass
        # SendCommandToGUI('toolbar')

    else:
        lg.warn('wrong command: ' + str(cmd))    

#------------------------------------------------------------------------------ 

def update_suppliers(old_suppliers_list, suppliers_list):
    dbcur().execute(_SQL['delete supplier'])
    l = map(lambda i: (i, suppliers_list[i],), range(len(suppliers_list)))
    dbcur().executemany(_SQL['insert supplier'], l)
    db().commit()
    # TODO - need to repaint GUI here
    lg.out(4, '    updated %d suppliers' % len(suppliers_list))


def update_customers(old_customers_list, customers_list):
    dbcur().execute(_SQL['delete customer'])
    l = map(lambda i: (i, customers_list[i],), range(len(customers_list)))
    dbcur().executemany(_SQL['insert customer'], l)
    db().commit()
    # TODO - need to repaint GUI here
    lg.out(4, '    updated %d customers' % len(customers_list))


def update_friends(old_friends_list, friends_list):
    dbcur().execute(_SQL['delete friend'])
    l = map(lambda i: (i, friends_list[i][0], friends_list[i][1]), range(len(friends_list)))
    dbcur().executemany(_SQL['insert friend'], l)
    db().commit()
    # TODO - need to repaint GUI here
    lg.out(4, '    updated %d friends' % len(friends_list))


def update_contact_status(idurl):
    pass
    # TODO - need to repaint GUI here


def update_backup_fs(backup_fs_raw_list):
    # dbcur().execute(_SQL['delete backupfsitem'])
    # dbcur().executemany(_SQL['insert backupfsitem'], backup_fs_raw_list)
    # db().commit()
    # TODO - need to repaint GUI here
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