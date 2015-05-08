#!/usr/bin/python
#dbwrite.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: dbwrite

"""

#------------------------------------------------------------------------------ 

from logs import lg

#------------------------------------------------------------------------------ 

def update_identities(ids, cache, single_item):
    if single_item:
        update_single_identity(single_item[0], single_item[1], single_item[2])
        return
    lg.out(6, 'dbwrite.update_identities %d items' % len(cache))
    from web.identityapp.models import Identity
    current_identities = Identity.objects.all()
    lg.out(6, '        currently %d items will be removed' % len(current_identities))
    new_identities = []
    for idurl, idobj in cache.items():
        new_identities.append(Identity(
            id=ids[idurl], 
            idurl=idurl, 
            src=idobj.serialize()))
    current_identities.delete()
    Identity.objects.bulk_create(new_identities)
    lg.out(6, '        wrote %d items' % len(new_identities))


def update_single_identity(index, idurl, idobj):
    lg.out(6, 'dbwrite.update_single_identity') 
    from web.identityapp.models import Identity
    if idurl is None:
        try:
            Identity.objects.get(id=index).delete()
            lg.out(6, '        deleted an item at index %d' % index)
        except:
            lg.exc()
    else:
        try:
            ident = Identity.objects.get(id=index)
            lg.out(6, '        updated an item at index %d' % index)
        except:
            ident = Identity(id=index)
            lg.out(6, '        created a new item with index %d' % index)
        ident.idurl = idurl
        ident.src = idobj.serialize()
        ident.save()
        
#------------------------------------------------------------------------------ 

def update_friends(old_friends_list, friends_list):
    lg.out(6, 'dbwrite.update_friends old:%d new:%d' % (len(old_friends_list), len(friends_list)))
    from web.friendapp.models import Friend
    current_friends = Friend.objects.all()
    lg.out(6, '        currently %d items will be removed' % len(current_friends))
    new_friends = []
    for idurl in friends_list:
        new_friends.append(Friend(idurl=idurl))
    current_friends.delete()
    Friend.objects.bulk_create(new_friends)
    lg.out(6, '        wrote %d items' % len(new_friends))
    
    
    
