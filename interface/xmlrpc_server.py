

from twisted.internet import reactor
from twisted.web import server
from twisted.web import xmlrpc

from logs import lg

from lib import bpio
from lib import diskspace
from lib import contacts

from p2p import backup_fs

#------------------------------------------------------------------------------ 

def init():
    lg.out(4, 'xmlrpc_server.init')
    Listener = reactor.listenTCP(5001, server.Site(XMLRPCServer()))

#------------------------------------------------------------------------------ 

class XMLRPCServer(xmlrpc.XMLRPC):
    def __init__(self):
        xmlrpc.XMLRPC.__init__(self, allowNone=True)
        self.methods = {
            'ls': self._ls,
        }

    def lookupProcedure(self, procedurePath):
        try:
            return self.methods[procedurePath]
        except KeyError, e:
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                        "procedure %s not found" % procedurePath)

    def listProcedures(self):
        return self.methods.keys()    

    def _ls(self, path=None):
        result = []
        for pathID, localPath, item in backup_fs.IterateIDs():
            result.append((pathID, localPath, item))
#            sz = diskspace.MakeStringFromBytes(item.size) if item.exist() else ''
#            result.append((pathID, localPath, sz))
#            for version, vinfo in item.get_versions().items():
#                if vinfo[1] >= 0:
#                    szver = diskspace.MakeStringFromBytes(vinfo[1]/contacts.numSuppliers())+' / '+diskspace.MakeStringFromBytes(vinfo[1]) 
#                else:
#                    szver = '?'
#                result.append((pathID+'/'+version, szver))
        return result
        
