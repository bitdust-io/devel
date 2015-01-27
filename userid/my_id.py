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

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

import identity

#------------------------------------------------------------------------------ 

_LocalIdentity = None
_LocalIDURL = None
_LocalName = None
_ValidTransports = ['tcp', 'udp', ]

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
        lg.out(2, "my_id.loadLocalIdentity ERROR local identity is not Valid")
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
    lg.out(6, "my_id.saveLocalIdentity")
    _LocalIdentity.sign()
    xmlid = _LocalIdentity.serialize()
    filename = bpio.portablePath(settings.LocalIdentityFilename())
    bpio.WriteFile(filename, xmlid)

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




