#!/usr/bin/python
# xmlrpc_server.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (xmlrpc_server.py) is part of BitDust Software.
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

"""
..

module:: xmlrpc_server
"""

from twisted.internet import reactor
from twisted.web import server
from twisted.web import xmlrpc

#------------------------------------------------------------------------------

from logs import lg

import api

#------------------------------------------------------------------------------


def init():
    lg.out(4, 'xmlrpc_server.init')
    from main import settings
    from system import bpio
    port = settings.DefaultXMLRPCPort()
    bpio.AtomicWriteFile(settings.LocalXMLRPCPortFilename(), str(port))
    reactor.listenTCP(port, server.Site(XMLRPCServer()))
    lg.out(4, '    started on port %d' % port)

#------------------------------------------------------------------------------


class XMLRPCServer(xmlrpc.XMLRPC):

    def __init__(self):
        xmlrpc.XMLRPC.__init__(self, allowNone=True)
        self.methods = {
            'stop': api.stop,
            'restart': api.restart,
            # 'show':                     api.show,
            'backups_list': api.backups_list,
            'backups_id_list': api.backups_id_list,
            'backup_start_id': api.backup_start_id,
            'backup_start_path': api.backup_start_path,
            'backup_dir_add': api.backup_dir_add,
            'backup_file_add': api.backup_file_add,
            'backup_tree_add': api.backup_tree_add,
            #            'backup_delete_local':      api.backup_delete_local,
            #            'backup_delete_id':         api.backup_delete_id,
            #            'backup_delete_path':       api.backup_delete_path,
            #            'backups_update':           api.backups_update,
            #            'restore_single':           api.restore_single,
            # 'list_messages':            api.list_messages,
            'send_message': api.send_message,
            'find_peer_by_nickname': api.find_peer_by_nickname,
            # 'list_correspondents':      api.list_correspondents,
        }

    def lookupProcedure(self, procedurePath):
        try:
            return self.methods[procedurePath]
        except KeyError as e:
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                                        "procedure %s not found" % procedurePath)

    def listProcedures(self):
        return self.methods.keys()
