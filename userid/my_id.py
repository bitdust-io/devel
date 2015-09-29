#!/usr/bin/python
#my_id.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: my_id

"""

import os
import sys
import string
import time

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

from lib import misc
from lib import nameurl

from crypt import key 

import identity

#------------------------------------------------------------------------------ 

_LocalIdentity = None
_LocalIDURL = None
_LocalName = None
_ValidTransports = ['tcp', 'udp', 'proxy',]

#------------------------------------------------------------------------------ 

def init():
    """
    Will be called in main thread at start up.
    Can put here some minor things if needed.
    """
    lg.out(4, 'my_id.init')
    loadLocalIdentity()

def shutdown():
    lg.out(4, 'my_id.shutdown')
    forgetLocalIdentity()

#-------------------------------------------------------------------------------

def isLocalIdentityReady():
    """
    Return True if local identity object already initialized and stored in memory. 
    """
    global _LocalIdentity
    return _LocalIdentity is not None

def setLocalIdentity(ident):
    """
    Set local identity object in the memory.  
    """
    global _LocalIdentity
    global _LocalIDURL
    global _LocalName
    if not ident:
        return
    _LocalIdentity = ident
    _LocalIDURL = _LocalIdentity.getIDURL()
    _LocalName = _LocalIdentity.getIDName()

def setLocalIdentityXML(idxml):
    """
    Construct identity object from XML string and save it to the memory.
    """
    setLocalIdentity(identity.identity(xmlsrc=idxml))

def getLocalIdentity():
    """
    Return my identity object.
    """
    global _LocalIdentity
    if not isLocalIdentityReady():
        loadLocalIdentity()
    return _LocalIdentity

def getLocalID():
    """
    Return my IDURL.
    """ 
    global _LocalIDURL
    if _LocalIDURL is None:
        localIdent = getLocalIdentity()
        if localIdent:
            _LocalIDURL = localIdent.getIDURL()
    return _LocalIDURL

def getIDName():
    """
    Return my account name, this is a filename part of IDURL without '.xml'.
    """
    global _LocalName
    if _LocalName is None:
        localIdent = getLocalIdentity()
        if localIdent:
            _LocalName = localIdent.getIDName()
    return _LocalName

#------------------------------------------------------------------------------ 

def loadLocalIdentity():
    """
    The core method.
    The file [BitDust data dir]/metadata/localidentity keeps the user identity in XML format.
    Do read the local file and set into object in memory.  
    """
    global _LocalIdentity
    global _LocalIDURL
    global _LocalName
    xmlid = ''
    filename = bpio.portablePath(settings.LocalIdentityFilename())
    if os.path.exists(filename):
        xmlid = bpio.ReadTextFile(filename)
        lg.out(6, 'my_id.loadLocalIdentity %d bytes read from\n        %s' % (len(xmlid), filename))
    if xmlid == '':
        lg.out(2, "my_id.loadLocalIdentity ERROR reading local identity from " + filename)
        return
    lid = identity.identity(xmlsrc=xmlid)
    if not lid.Valid():
        lg.out(2, "my_id.loadLocalIdentity ERROR loaded identity is not Valid")
        return
    _LocalIdentity = lid
    _LocalIDURL = lid.getIDURL()
    _LocalName = lid.getIDName()
    setTransportOrder(getOrderFromContacts(_LocalIdentity))
    lg.out(6, "my_id.loadLocalIdentity my name is [%s]" % lid.getIDName())

def saveLocalIdentity():
    """
    Save identity object from memory into local file.
    Do sign the identity than serialize to write to the file.
    """
    global _LocalIdentity
    if not isLocalIdentityReady():
        lg.out(2, "my_id.saveLocalIdentity ERROR localidentity not exist!")
        return
    _LocalIdentity.sign()
    xmlid = _LocalIdentity.serialize()
    filename = bpio.portablePath(settings.LocalIdentityFilename())
    bpio.WriteFile(filename, xmlid)
    lg.out(6, "my_id.saveLocalIdentity %d bytes wrote to %s" % (len(xmlid), filename))

def forgetLocalIdentity():
    """
    """
    global _LocalIdentity
    if not isLocalIdentityReady():
        lg.out(2, "my_id.forgetLocalIdentity ERROR localidentity not exist!")
        return
    lg.out(6, "my_id.saveLocalIdentity")
    _LocalIdentity = None

#------------------------------------------------------------------------------ 

def getValidTransports():
    """
    """
    global _ValidTransports
    return _ValidTransports

def isValidTransport(transport):
    """
    Check string to be a valid transport.
    See ``lib.transport_control' for more details.
    """
    global _ValidTransports
    if transport in _ValidTransports:
        return True
    else:
        return False

def validateTransports(orderL):
    """
    Validate a list of strings - all must be a valid transports.
    """
    global _ValidTransports
    transports = []
    for transport in orderL:
        if isValidTransport(transport):
            transports.append(transport)
        else:
            lg.warn('invalid entry int transport list: %s , ignored' % str(transport))
    if len(transports) == 0:
        lg.out(1, 'my_id.validateTransports ERROR no valid transports, using default transports ' + str(_ValidTransports))
        transports = _ValidTransports
#    if len(transports) != len(orderL):
#        lg.out(1, 'my_id.validateTransports ERROR Transports contained an invalid entry, need to figure out where it came from.')
    return transports

def setTransportOrder(orderL):
    """
    Validate transports and save the list in the [BitDust data dir]\metadata\torder.
    It is useful to remember the priority of used transports. 
    """
    orderl = orderL
    orderL = validateTransports(orderL)
    orderTxt = string.join(orderl, ' ')
    lg.out(8, 'my_id.setTransportOrder: ' + str(orderTxt))
    bpio.WriteFile(settings.DefaultTransportOrderFilename(), orderTxt)

def getTransportOrder():
    """
    Read and validate tranports from [BitDust data dir]\metadata\torder file.
    """
    global _ValidTransports
    lg.out(8, 'my_id.getTransportOrder')
    order = bpio.ReadTextFile(settings.DefaultTransportOrderFilename()).strip()
    if order == '':
        orderL = _ValidTransports
    else:
        orderL = order.split(' ')
        orderL = validateTransports(orderL)
    setTransportOrder(orderL)
    return orderL

def getOrderFromContacts(ident):
    """
    A wrapper for ``identity.getProtoOrder`` method.
    """
    return ident.getProtoOrder()

#------------------------------------------------------------------------------ 

def buildProtoContacts(lid):
    """
    Create a full list of needed transport methods
    to be able to accept incoming traffic from other nodes.
    Make calls to transport services to build a list of my contacts.
    """
    from services import driver
    # prepare contacts
    current_contats = lid.getContactsByProto()
    current_order = lid.getProtoOrder()
    lg.out(4, 'my_id.buildProtoContacts')
    lg.out(4, '    current contacts: %s' % str(current_contats))
    lg.out(4, '    current order: %s' % str(current_order))
    new_contacts = {}
    new_order = []
    # prepare list of active transports 
    active_transports = []
    for proto in getValidTransports():
        if not settings.transportIsEnabled(proto):
            continue
        if not driver.is_started('service_%s_transport' % proto):
            continue
        if not settings.transportReceivingIsEnabled(proto):
            continue
        active_transports.append(proto)
    # sort active transports by priority
    active_transports.sort(key=settings.getTransportPriority)
    lg.out(4, '    active transports: %s' % str(active_transports))
    if not driver.is_started('service_gateway'):
        new_contacts = current_contats
        new_order = current_order
    else:
        from transport import gateway
        # build contacts data according transports priorities
        for proto in active_transports:
            clist = gateway.transport(proto).interface.build_contacts()
            cdict = {}
            if len(clist) > 1:
                clist.reverse()
                for contact in clist: 
                    cproto, cdata = contact.split('://')
                    cdict[cproto] = cdata
                    if cproto in new_order:
                        new_order.remove(cproto)
                    new_order.insert(0, proto)
            else:
                for contact in clist: 
                    cproto, cdata = contact.split('://')
                    cdict[cproto] = cdata
                    if cproto in new_order:
                        new_order.remove(cproto)
                    if cproto in current_order and current_order.index(cproto) == 0:
                        new_order.insert(0, proto)
                    else:
                        new_order.append(proto)
            new_contacts.update(cdict)
    lg.out(4, '    new contacts: %s' % str(new_contacts))
    lg.out(4, '    new order: %s' % str(new_order))
    return new_contacts, new_order


def buildDefaultIdentity(name='', ip='', idurls=[]):
    """
    Use some local settings and config files to create some new identity.
    Nice to provide a user name or it will have a form like: [ip address]_[date].     
    """
    if ip == '':
        ip = bpio.ReadTextFile(settings.ExternalIPFilename())
    if name == '':
        name = ip.replace('.', '-') + '_' + time.strftime('%M%S')
    lg.out(4, 'my_id.buildDefaultIdentity: %s %s' % (name, ip))
    # create a new identity object
    # it is stored in memory and another copy on disk drive 
    ident = identity.identity(xmlsrc=identity.default_identity_src)
    # this is my IDURL address
    # you can have many IDURL locations for same identity
    # just need to keep all them synchronized
    # this is identity propagate procedure, see p2p/propagate.py
    if len(idurls) == 0:
        idurls.append('http://localhost/'+name.lower()+'.xml')
    for idurl in idurls: 
        ident.sources.append(idurl.encode("ascii").strip())
    # create a full list of needed transport methods
    # to be able to accept incoming traffic from other nodes
    new_contacts, new_order = buildProtoContacts(ident)
    if len(new_contacts) == 0:
        if settings.enableTCP() and settings.enableTCPreceiving():
            new_contacts['tcp'] = 'tcp://'+ip+':'+str(settings.getTCPPort())
            new_order.append('tcp')
        if settings.enableUDP() and settings.enableUDPreceiving():
            x, servername, x, x = nameurl.UrlParse(ident.sources[0])
            new_contacts['udp'] = 'udp://%s@%s' % (name.lower(), servername)
            new_order.append('udp')
    # erase current contacts from my identity
    ident.clearContacts()
    # add contacts data to the local identity
    for proto in new_order:
        contact = new_contacts.get(proto, None)
        if contact is None:
            lg.warn('proto %s was not found in contacts' % proto)
            continue
        ident.setProtoContact(proto, contact)
    # set other info
    ident.certificates = []
    ident.date = time.strftime('%b %d, %Y')
    ident.postage = "1"
    ident.revision = "0"
    # update software version number
    version_number = bpio.ReadTextFile(settings.VersionNumberFile()).strip()
    repo, location = misc.ReadRepoLocation()
    ident.version = (version_number.strip() + ' ' + repo.strip() + ' ' + bpio.osinfo().strip()).strip()
    # build a version info
    vernum = bpio.ReadTextFile(settings.VersionNumberFile())
    repo, location = misc.ReadRepoLocation()
    ident.version = (vernum.strip() + ' ' + repo.strip() + ' ' + bpio.osinfo().strip()).strip()
    # put my public key in my identity
    ident.publickey = key.MyPublicKey()
    # generate signature
    ident.sign()
    # validate new identity
    if not ident.Valid():
        lg.warn('generated identity is not valid !!!') 
    return ident

    
def rebuildLocalIdentity(self):
    """
    If some transports was enabled or disabled we want to update identity contacts.
    Just empty all of the contacts and create it again in the same order.
    Also increase revision number by one - others may keep track of my modifications.
    """
    # remember the current identity - full XML source code   
    current_identity_xmlsrc = getLocalIdentity().serialize()
    lg.out(4, 'my_id.rebuildLocalIdentity current identity is %d bytes long' % len(current_identity_xmlsrc))
    # getting current copy of local identity
    lid = getLocalIdentity()
    # create a full list of needed transport methods
    # to be able to accept incoming traffic from other nodes
    new_contacts, new_order = buildProtoContacts(lid)
    # erase current contacts from my identity
    lid.clearContacts()
    # add contacts data to the local identity
    for proto in new_order:
        contact = new_contacts.get(proto, None)
        if contact is None:
            lg.warn('proto %s was not found in contacts' % proto)
            continue
        lid.setProtoContact(proto, contact)
    # update software version number
    repo, location = misc.ReadRepoLocation()
    lid.version = (self.version_number.strip() + ' ' + repo.strip() + ' ' + bpio.osinfo().strip()).strip()
    # generate signature with changed content
    lid.sign()
    changed = False
    if lid.serialize() == current_identity_xmlsrc:
        # no modifications in my identity - cool !!!
        lg.out(4, '    same revision: %s' % lid.revision)
    else:
        lid.revision = str(int(lid.revision)+1)   
        # generate signature again because revision were changed !!!
        lid.sign()
        lg.out(4, '    revision add: %s' % lid.revision)
        changed = True
        # remember the new identity
        setLocalIdentity(lid)
    lg.out(4, '    version: %s' % str(lid.version))
    lg.out(4, '    contacts: %s' % str(lid.contacts))
    lg.out(4, '    %s identity contacts has %been changed' % (('' if changed else 'NOT ')))

    if changed:
        # finally saving modified local identity
        saveLocalIdentity()
    return changed


