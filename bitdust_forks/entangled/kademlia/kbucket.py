#!/usr/bin/env python
# kbucket.py
#
# Copyright (C) 2007-2008 Francois Aucamp, Meraka Institute, CSIR
# See AUTHORS for all authors and contact information.
#
# License: GNU Lesser General Public License, version 3 or later; see COPYING
#          included in this archive for details.
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#
# The docstrings in this module contain epytext markup; API documentation
# may be created by processing this file with epydoc: http://epydoc.sf.net

from __future__ import absolute_import
import six

from . import constants  # @UnresolvedImport

_Debug = False


class BucketFull(Exception):
    """
    Raised when the bucket is full.
    """


class KBucket(object):
    """ Description - later
    """
    def __init__(self, rangeMin, rangeMax):
        """
        @param rangeMin: The lower boundary for the range in the 160-bit ID
                         space covered by this k-bucket
        @param rangeMax: The upper boundary for the range in the ID space
                         covered by this k-bucket
        """
        self.lastAccessed = 0
        self.rangeMin = rangeMin
        self.rangeMax = rangeMax
        self._contacts = list()

    def __repr__(self, *args, **kwargs):
        return str(self)

    def __str__(self):
        return '<KBucket %d %r to %r>' % (len(self._contacts), self.rangeMin, self.rangeMax)

    def addContact(self, contact):
        """
        Add contact to _contact list in the right order. This will move the
        contact to the end of the k-bucket if it is already present.

        @raise kademlia.kbucket.BucketFull: Raised when the bucket is full and
                                            the contact isn't in the bucket
                                            already

        @param contact: The contact to add
        @type contact: kademlia.contact.Contact
        """
        if contact in self._contacts:
            # Move the existing contact to the end of the list
            # - using the new contact to allow add-on data (e.g. optimization-specific stuff) to pe updated as well
            self._contacts.remove(contact)
            self._contacts.append(contact)
            if _Debug:
                print('[DHT KBUCKET]    moved contact to the end of the bucket %r' % contact)
        elif len(self._contacts) < constants.k:
            self._contacts.append(contact)
            if _Debug:
                print('[DHT KBUCKET]    added new contact %r' % contact)
        else:
            raise BucketFull('No space in bucket to insert contact')

    def getContact(self, contactID):
        """
        Get the contact specified node ID.
        """
        index = self._contacts.index(contactID)
        return self._contacts[index]

    def getContacts(self, count=-1, excludeContact=None):
        """
        Returns a list containing up to the first count number of contacts.

        @param count: The amount of contacts to return (if 0 or less, return
                      all contacts)
        @type count: int
        @param excludeContact: A contact to exclude; if this contact is in
                               the list of returned values, it will be
                               discarded before returning. If a C{str} is
                               passed as this argument, it must be the
                               contact's ID.
        @type excludeContact: kademlia.contact.Contact or str


        @raise IndexError: If the number of requested contacts is too large

        @return: Return up to the first count number of contacts in a list
                If no contacts are present an empty is returned
        @rtype: list
        """
        # Return all contacts in bucket
        if count <= 0:
            count = len(self._contacts)

        # Get current contact number
        currentLen = len(self._contacts)

        # If count greater than k - return only k contacts
        if count > constants.k:
            count = constants.k

        # Check if count value in range and,
        # if count number of contacts are available
        if not currentLen:
            contactList = list()

        # length of list less than requested amount
        elif currentLen < count:
            contactList = self._contacts[0:currentLen]
        # enough contacts in list
        else:
            contactList = self._contacts[0:count]

        if excludeContact in contactList:
            contactList.remove(excludeContact)

        return contactList

    def removeContact(self, contact):
        """
        Remove given contact from list.

        @param contact: The contact to remove, or a string containing the
                        contact's node ID
        @type contact: kademlia.contact.Contact or str

        @raise ValueError: The specified contact is not in this bucket
        """
        self._contacts.remove(contact)
        if _Debug:
            print('[DHT KBUCKET]    removed contact %r' % contact)

    def keyInRange(self, key):
        """
        Tests whether the specified key (i.e. node ID) is in the range of the
        160-bit ID space covered by this k-bucket (in otherwords, it returns
        whether or not the specified key should be placed in this k-bucket)

        @param key: The key to test
        @type key: str or int

        @return: C{True} if the key is in this k-bucket's range, or C{False}
                 if not.
        @rtype: bool
        """
        _k = key
        if isinstance(key, six.integer_types):
            return self.rangeMin <= key < self.rangeMax
        key = int(key, 16)
        return self.rangeMin <= key < self.rangeMax

    def __len__(self):
        return len(self._contacts)
