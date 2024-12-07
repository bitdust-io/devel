#!/usr/bin/python
# my_id.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (my_id.py) is part of BitDust Software.
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

module:: my_id
"""

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import sys
import time
import tempfile

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.system import bpio
from bitdust.system import local_fs

from bitdust.main import settings
from bitdust.main import events

from bitdust.lib import misc
from bitdust.lib import nameurl
from bitdust.lib import strng

from bitdust.crypt import key

from bitdust.userid import identity
from bitdust.userid import id_url

#------------------------------------------------------------------------------

_LocalIdentity = None
_LocalIDURL = None
_LocalID = None
_LocalName = None
_ValidTransports = [
    'tcp',
    'udp',
    'http',
    'proxy',
]

#------------------------------------------------------------------------------


def init():
    """
    Will be called in main thread at start up.

    Can put here some minor things if needed.
    """
    if _Debug:
        lg.out(_DebugLevel, 'my_id.init')
    loadLocalIdentity()


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'my_id.shutdown')
    forgetLocalIdentity()


#-------------------------------------------------------------------------------


def isLocalIdentityExists():
    """
    Return True if local file `~/.bitdust/[network name]/metadata/localidentity` exists.
    """
    return os.path.isfile(settings.LocalIdentityFilename())


def isLocalIdentityReady():
    """
    Return True if local identity object already initialized and stored in
    memory.
    """
    global _LocalIdentity
    return _LocalIdentity is not None


def setLocalIdentity(ident):
    """
    Set local identity object in the memory.
    """
    global _LocalIdentity
    global _LocalIDURL
    global _LocalID
    global _LocalName
    if not ident:
        return
    modified = False
    old_json = {}
    new_json = {}
    if _LocalIdentity:
        current_src = _LocalIdentity.serialize()
        if current_src != ident.serialize():
            modified = True
            li_json = _LocalIdentity.serialize_json()
            old_json['revision'] = li_json['revision']
            old_json['contacts'] = li_json['contacts']
    _LocalIdentity = ident
    _LocalIDURL = _LocalIdentity.getIDURL()
    _LocalIDURL.refresh(replace_original=True)
    _LocalID = _LocalIDURL.to_id()
    _LocalName = _LocalIdentity.getIDName()
    li_json = _LocalIdentity.serialize_json()
    new_json['revision'] = li_json['revision']
    new_json['contacts'] = li_json['contacts']
    if modified:
        events.send('local-identity-modified', data=dict(old=old_json, new=new_json))
    else:
        events.send('local-identity-set', data=new_json)
    try:
        id_url.identity_cached(_LocalIdentity)
    except:
        lg.exc()


def setLocalIdentityXML(idxml):
    """
    Construct identity object from XML string and save it to the memory.
    """
    setLocalIdentity(identity.identity(xmlsrc=idxml))


def getLocalIdentity():
    """
    Returns my identity object.
    """
    global _LocalIdentity
    if not isLocalIdentityReady():
        loadLocalIdentity()
    return _LocalIdentity


def getIDName():
    """
    Returns my account name, this is a filename part of IDURL without '.xml'.
    """
    global _LocalName
    if _LocalName is None:
        localIdent = getLocalIdentity()
        if localIdent:
            _LocalName = localIdent.getIDName()
    return _LocalName


def getGlobalID(key_alias=None):
    """
    Returns my global user id - according to my current IDURL.
    """
    global _LocalID
    if not key_alias and _LocalID is not None:
        return _LocalID
    if key_alias == 'master' and _LocalID is not None:
        return strng.to_text('{}${}'.format(key_alias, _LocalID))
    from bitdust.userid import global_id
    glob_id = global_id.UrlToGlobalID(getIDURL())
    if not glob_id:
        return glob_id
    if key_alias:
        glob_id = strng.to_text('{}${}'.format(key_alias, glob_id))
    return glob_id


def getIDURL():
    """
    Returns my IDURL as a field.
    """
    global _LocalIDURL
    if _LocalIDURL is None:
        localIdent = getLocalIdentity()
        if localIdent:
            _LocalIDURL = localIdent.getIDURL()
    return _LocalIDURL


def getID():
    """
    Returns my global ID as a string.
    """
    return getGlobalID()


#------------------------------------------------------------------------------


def loadLocalIdentity():
    """
    The file `~/.bitdust/[network name]/metadata/localidentity` keeps the user
    identity in XML format.
    The method reads the local file and set into object in memory.
    """
    global _LocalIdentity
    xmlid = ''
    lid_filename = bpio.portablePath(settings.LocalIdentityFilename())
    key_filename = settings.KeyFileName()
    if not os.path.isfile(key_filename):
        keyfilenamelocation = settings.KeyFileNameLocation()
        if not os.path.isfile(keyfilenamelocation):
            lg.warn('not possible to load local identity because master key file does not exist at specified location')
            return False
        key_filename = bpio.ReadTextFile(keyfilenamelocation).strip()
        if not os.path.isfile(key_filename):
            lg.warn('not possible to load local identity because master key file does not exist at default location')
            return False
    if os.path.exists(lid_filename):
        xmlid = bpio.ReadTextFile(lid_filename)
        if _Debug:
            lg.out(_DebugLevel, 'my_id.loadLocalIdentity %d bytes read from %s' % (len(xmlid), lid_filename))
    if not xmlid:
        if _Debug:
            lg.out(_DebugLevel, 'my_id.loadLocalIdentity SKIPPED, local identity in %s is EMPTY !!!' % lid_filename)
        return False
    lid = identity.identity(xmlsrc=xmlid)
    if not lid.isCorrect():
        if _Debug:
            lg.out(_DebugLevel, 'my_id.loadLocalIdentity ERROR loaded identity is not Correct')
        return False
    if not lid.Valid():
        if _Debug:
            lg.out(_DebugLevel, 'my_id.loadLocalIdentity ERROR loaded identity is not Valid')
        return False
    setLocalIdentity(lid)
    setTransportOrder(getOrderFromContacts(_LocalIdentity))
    if _Debug:
        lg.out(_DebugLevel, 'my_id.loadLocalIdentity my global id is %s' % getGlobalID())
    return True


def saveLocalIdentity():
    """
    Save identity object from memory into local file.

    Do sign the identity than serialize to write to the file.
    """
    global _LocalIdentity
    if not isLocalIdentityReady():
        lg.warn('ERROR local identity not exist!')
        return False
    if not _LocalIdentity.isCorrect():
        lg.warn('local identity is not correct')
        return False
    _LocalIdentity.sign()
    if not _LocalIdentity.Valid():
        lg.err('local identity is not valid')
        return False
    xmlid = _LocalIdentity.serialize(as_text=True)
    filename = bpio.portablePath(settings.LocalIdentityFilename())
    bpio.WriteTextFile(filename, xmlid)
    setTransportOrder(getOrderFromContacts(_LocalIdentity))
    events.send('local-identity-written', data=dict(idurl=_LocalIdentity.getIDURL(), filename=filename))
    if _Debug:
        lg.out(_DebugLevel, 'my_id.saveLocalIdentity %d bytes wrote to %s' % (len(xmlid), filename))
    return True


def forgetLocalIdentity():
    global _LocalIdentity
    global _LocalIDURL
    global _LocalID
    global _LocalName
    if not isLocalIdentityReady():
        if _Debug:
            lg.out(_DebugLevel, 'my_id.forgetLocalIdentity ERROR local identity not exist!')
        return False
    if _Debug:
        lg.out(_DebugLevel, 'my_id.saveLocalIdentity')
    _LocalIdentity = None
    _LocalIDURL = None
    _LocalID = None
    _LocalName = None
    events.send('local-identity-cleaned', data=dict())
    return True


def eraseLocalIdentity(do_backup=True):
    if do_backup:
        if os.path.isfile(settings.LocalIdentityFilename()):
            current_identity_xmlsrc = local_fs.ReadBinaryFile(settings.LocalIdentityFilename())
            if current_identity_xmlsrc:
                fd, fname = tempfile.mkstemp(prefix='localidentity_', dir=settings.MetaDataDir())
                os.write(fd, current_identity_xmlsrc)
                os.close(fd)
                lg.info('created backup copy of my local identity in the file : %r' % fname)
    filename = bpio.portablePath(settings.LocalIdentityFilename())
    if not os.path.exists(filename):
        if _Debug:
            lg.out(_DebugLevel, 'my_id.eraseLocalIdentity SKIP file %s not exist' % filename)
        return True
    if not os.path.isfile(filename):
        if _Debug:
            lg.out(_DebugLevel, 'my_id.eraseLocalIdentity ERROR path %s is not a file' % filename)
        return False
    try:
        os.remove(filename)
    except:
        lg.exc()
        return False
    events.send('local-identity-erased', data=dict())
    if _Debug:
        lg.out(_DebugLevel, 'my_id.eraseLocalIdentity file %s was deleted' % filename)
    return True


#------------------------------------------------------------------------------


def getValidTransports():
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
            lg.warn('invalid entry in transport list: %s , ignored' % str(transport))
    if len(transports) == 0:
        if _Debug:
            lg.out(_DebugLevel, 'my_id.validateTransports ERROR no valid transports, using default transports ' + str(_ValidTransports))
        transports = _ValidTransports


#    if len(transports) != len(orderL):
#        lg.out(1, 'my_id.validateTransports ERROR Transports contained an invalid entry, need to figure out where it came from.')
    return transports


def setTransportOrder(orderL):
    """
    Validate transports and save the list in the `~/.bitdust/[network name]/metadata/torder`.
    It is useful to remember the priority of used transports.
    """
    orderl = orderL
    orderL = validateTransports(orderL)
    orderTxt = ' '.join(orderl)
    if _Debug:
        lg.out(_DebugLevel, 'my_id.setTransportOrder: ' + str(orderTxt))
    bpio.WriteTextFile(settings.DefaultTransportOrderFilename(), orderTxt)


def getTransportOrder():
    """
    Read and validate tranports from `~/.bitdust/[network name]/metadata/torder` file.
    """
    global _ValidTransports
    if _Debug:
        lg.out(_DebugLevel, 'my_id.getTransportOrder')
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


def buildProtoContacts(id_obj, skip_transports=[]):
    """
    Create a full list of needed transport methods to be able to accept
    incoming traffic from other nodes.

    Make calls to transport services to build a list of my contacts.
    """
    from bitdust.services import driver
    # prepare contacts
    current_contats = id_obj.getContactsByProto()
    current_order = id_obj.getProtoOrder()
    if _Debug:
        lg.out(_DebugLevel, 'my_id.buildProtoContacts')
        lg.out(_DebugLevel, '    current contacts: %s' % str(current_contats))
        lg.out(_DebugLevel, '    current order: %s' % str(current_order))
    new_contacts = {}
    new_order_correct = []
    # prepare list of active transports
    active_transports = []
    for proto in getValidTransports():
        if proto in skip_transports:
            continue
        if not settings.transportIsEnabled(proto):
            continue
        if not settings.transportReceivingIsEnabled(proto):
            continue
        if not driver.is_on('service_%s_transport' % proto):
            lg.warn('transport "%s" is enabled, but service_%s_transport() is not ready yet' % (proto, proto))
            continue
        active_transports.append(proto)
    # sort active transports by priority
    if _Debug:
        lg.out(_DebugLevel, '    active transports: %s' % str(active_transports))
    active_transports.sort(key=settings.getTransportPriority)
    if _Debug:
        lg.out(_DebugLevel, '    sorted transports: %s' % str(active_transports))
    if not driver.is_on('service_gateway'):
        new_contacts = current_contats
        new_order_correct = current_order
        lg.warn('service_gateway() is not started, use my current contacts as a source')
    else:
        from bitdust.transport import gateway
        # build contacts data according transports priorities
        new_order = current_order
        for proto in active_transports:
            clist = gateway.transport(proto).interface.build_contacts(id_obj)
            cdict = {}
            corder = []
            for contact in clist:
                cproto, _ = contact.split(b'://')
                cdict[cproto] = contact
                corder.append(cproto)
            new_contacts.update(cdict)
            for cproto in corder:
                if cproto not in new_order:
                    new_order.append(cproto)
        new_order_correct = list(new_order)
        for nproto in new_order:
            if nproto not in list(new_contacts.keys()):
                new_order_correct.remove(nproto)
    if _Debug:
        lg.out(_DebugLevel, '    new contacts: %s' % str(new_contacts))
        lg.out(_DebugLevel, '    new order: %s' % str(new_order_correct))
    return new_contacts, new_order_correct


def buildDefaultIdentity(name='', ip='', idurls=[], revision=0):
    """
    Use some local settings and config files to create some new identity.

    Nice to provide a user name or it will have a form like: [ip_address]_[date].
    """
    if not ip:
        ip = misc.readExternalIP()
    if not name:
        name = ip.replace('.', '-') + '_' + time.strftime('%M%S')
    if _Debug:
        lg.args(_DebugLevel, name=name, ip=ip, idurls=idurls)
    # this is my IDURL address
    # you can have many IDURL locations for same identity
    # just need to keep all them synchronized
    # this is identity propagate procedure, see p2p/propagate.py
    if len(idurls) == 0:
        idurls.append(b'http://127.0.0.1/%s.xml' % strng.to_bin(name.lower()))
    # create a new identity object
    # it is stored in memory and another copy will be located on disk drive
    ident = identity.identity(xmlsrc=identity.default_identity_src)
    ident.setSources(idurls)
    # create a full list of needed transport methods
    # to be able to accept incoming traffic from other nodes
    new_contacts, new_order = buildProtoContacts(ident)
    if len(new_contacts) == 0:
        if settings.enableTCP() and settings.enableTCPreceiving():
            new_contacts['tcp'] = b'tcp://' + strng.to_bin(ip) + b':' + strng.to_bin(str(settings.getTCPPort()))
            new_order.append('tcp')
        if settings.enableUDP() and settings.enableUDPreceiving():
            _, servername, _, _ = nameurl.UrlParse(ident.getSources(as_originals=True)[0])
            new_contacts['udp'] = b'udp://' + strng.to_bin(name.lower()) + b'@' + strng.to_bin(servername)
            new_order.append('udp')
        if settings.enableHTTP() and settings.enableHTTPreceiving():
            new_contacts['http'] = b'http://' + strng.to_bin(ip) + b':' + strng.to_bin(str(settings.getHTTPPort()))
            new_order.append('http')
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
    # ident.certificates = []
    ident.setDate(time.strftime('%b %d, %Y'))
    ident.setPostage(1)
    ident.setRevision(revision)
    ident.setVersion('')  # TODO: put latest git commit hash here
    # update software version number
    # version_number = bpio.ReadTextFile(settings.VersionNumberFile()).strip()
    # repo, location = misc.ReadRepoLocation()
    # ident.version = (version_number.strip() + ' ' + repo.strip() + ' ' + bpio.osinfo().strip()).strip()
    # build a version info
    # vernum = bpio.ReadTextFile(settings.VersionNumberFile())
    # repo, location = misc.ReadRepoLocation()
    # ident.version = (vernum.strip() + ' ' + repo.strip() + ' ' + bpio.osinfo().strip()).strip()
    # put my public key in my identity
    ident.setPublicKey(key.MyPublicKey())
    # generate signature
    ident.sign()
    # validate new identity
    if not ident.Valid():
        lg.warn('generated identity is not valid !!!')
    return ident


def rebuildLocalIdentity(identity_object=None, skip_transports=[], new_sources=None, revision_up=False, new_revision=None, save_identity=True):
    """
    If some transports was enabled or disabled we want to update identity
    contacts. Just empty all of the contacts and create it again in the same
    order.

    Also increase revision number by one - others may keep track of my modifications.
    """
    # remember the current identity - full XML source code
    current_identity_xmlsrc = getLocalIdentity().serialize()
    if _Debug:
        lg.out(_DebugLevel, 'my_id.rebuildLocalIdentity current identity is %d bytes long new_revision=%r' % (len(current_identity_xmlsrc), new_revision))
    # getting a copy of local identity to be modified or another object to be used
    lid = identity_object or identity.identity(xmlsrc=current_identity_xmlsrc)
    # create a full list of needed transport methods
    # to be able to accept incoming traffic from other nodes
    new_contacts, new_order = buildProtoContacts(lid, skip_transports=skip_transports)
    # erase current contacts from my identity
    lid.clearContacts()
    # add contacts data to the local identity
    lid.setContactsFromDict(new_contacts, new_order)
    # if I need to rotate my sources do it now
    if new_sources:
        lid.setSources(new_sources)
    # update software version number
    # TODO: need to read GIT commit hash here instead of version
    vernum = strng.to_bin(bpio.ReadTextFile(settings.VersionNumberFile())).strip()
    # repo, _ = misc.ReadRepoLocation()
    repo = 'sources'
    # lid.setVersion((vernum + b' ' + strng.to_bin(repo.strip()) + b' ' + strng.to_bin(bpio.osinfo().strip()).strip()))
    # TODO: add latest commit hash from the GIT repo to the version
    lid.setVersion(vernum + b' ' + strng.to_bin(repo.strip()))
    # generate signature with changed content
    lid.sign()
    new_xmlsrc = lid.serialize()
    changed = False
    if new_xmlsrc != current_identity_xmlsrc or revision_up or new_revision:
        if not new_revision:
            new_revision = lid.getRevisionValue() + 1
        try:
            lid.setRevision(new_revision)
        except:
            lg.exc()
            return False
        # generate signature again because revision were changed !!!
        lid.sign()
        lg.info('incremented my identity revision: %d' % lid.getRevisionValue())
        changed = True
    else:
        # no modifications in my identity - cool !!!
        if _Debug:
            lg.out(_DebugLevel, '    same revision: %d' % lid.getRevisionValue())
    if _Debug:
        lg.out(_DebugLevel, '    version: %r' % lid.version)
        lg.out(_DebugLevel, '    contacts: %r' % lid.contacts)
        lg.out(_DebugLevel, '    sources: %r' % lid.getSources(as_originals=True))
    if changed:
        if save_identity:
            # finally saving modified local identity
            if _Debug:
                lg.out(_DebugLevel, '    SAVING new identity #%s' % lid.revision)
            # remember the new identity
            setLocalIdentity(lid)
            saveLocalIdentity()
            # NOW TEST IT!
            # forgetLocalIdentity()
            # loadLocalIdentity()
            if _Debug:
                lg.out(_DebugLevel, '    LOCAL IDENTITY CORRECT: %r' % getLocalIdentity().isCorrect())
                lg.out(_DebugLevel, '    LOCAL IDENTITY VALID: %r' % getLocalIdentity().Valid())
    lg.info('my identity HAS %sBEEN changed' % (('' if changed else 'NOT ')))
    if _Debug:
        lg.out(_DebugLevel, '\n' + strng.to_text(lid.serialize()) + '\n')
    return changed
