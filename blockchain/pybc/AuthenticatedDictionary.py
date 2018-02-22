"""
AuthenticatedDictionary.py: Contains an authenticated dictionary data structure.
Supports O(log n) insert, find, and delete, and maintains a hash authenticating
the contents.

The data structure is set-unique; if the same data is in it, it always produces
the same hash, no matter what order it was inserted in.

The data structure is backed by a SQliteShelf database, and exposes a commit()
method that must be called when you want to commit your changes to disk.

"""

import hashlib
import collections
import struct
import logging

from collections import MutableMapping
from sqliteshelf import SQLiteShelf
from StateComponent import StateComponent
import util

# How many children should each MerkleTrieNode be able to have? As many as
# there are hex digits.
ORDER = 16


class MerkleTrieNode(object):
    """
    An object that we use to represent a Merkle trie node. Gets pickled and
    unpickled, and carries a list of child pointers, a key field, a value field,
    and a hash field.

    Keys, values, and hashes must all be byte strings.

    Can't really do anything by itself, since it can't directly access its
    children, just their pointer values.

    """

    def __init__(self, children=None, key=None, value=None, hash=None):
        """
        Make a new blank MerkleTrieNode with the given number of child pointer
        storage locations.

        Once stored, MerkleTrieNodes should never be changed.

        """

        # Don't store any children pointer locations until we need to. If we
        # need children, this turns into a list of child pointers or Nones.
        self.children = children

        # What is our key, if any?
        self.key = key

        # What is our value, if any?
        self.value = value

        # And our Merkle hash
        self.hash = hash

    def copy(self):
        """
        Return a deep copy of this MerkleTrieNode. Not in the sense that we
        create new MerkleTrieNodes for its children, but in the sense that if we
        update the resultant Python object in place it won't affect the
        original.

        """

        # Load the children
        children = self.children

        if children is not None:
            # It's a list of children and we need to make a copy of it rather
            # than just referencing it
            children = list(children)

        # Make a new MerkleTrieNode exactly like us.
        return MerkleTrieNode(children, self.key, self.value, self.hash)

    def __repr__(self):
        """
        Stringify this node for debugging.

        """

        # Hold all the parts to merge.
        parts = ["MerkleTrieNode("]

        if self.key is not None:
            parts.append(self.key)
            parts.append(" -> ")
        if self.value is not None:
            parts.append(self.value)
        if self.children is not None:
            for i, child in enumerate(self.children):
                if child is not None:
                    parts.append("<Child {}:\"{}\">".format(i, child))
        if self.hash is not None:
            if len(parts) > 1:
                parts.append(", Hash:")
            parts.append(util.bytes2string(self.hash))
        parts.append(")")

        return "".join(parts)


class AuthenticatedDictionaryStateComponent(StateComponent):
    """
    A StateComponent for an AuthenticatedDictionary. Each StateComponent
    contains a MerkleTrieNode turned into portable pointer-independent bytes
    with node_to_bytes, so the StateComponents have the same hashes as the
    MerkleTrieNodes they represent.

    Knows how its dependencies are encoded in the bytestring.

    """

    def get_dependencies(self):
        """
        Yield the Merkle hash of each dependency of this StateComponent.

        """

        # Children are encoded as follows:
        # First byte gives child count
        # Then we have that many 65-byte records of child number and child hash.

        if len(self.data) == 0:
            raise Exception("No data")

        child_count = struct.unpack(">B", self.data[0])[0]

        if child_count > 16:
            # Don't have absurd numbers of children
            raise Exception("Too many children: {}".format(child_count))

        for i in xrange(child_count):
            # Unpack the next 65-byte record
            child_index, child_hash = struct.unpack_from(">B64s", self.data,
                                                         offset=1 + 65 * i)

            # Say the hash is a dependency.
            yield child_hash

    def get_child_list(self):
        """
        Return a list of child Merkle hashes, with None everywhere that there is
        no child.

        """

        # We can have up to 16 children
        children = [None] * 16

        # Children are encoded as follows:
        # First byte gives child count
        # Then we have that many 65-byte records of child number and child hash.

        if len(self.data) == 0:
            raise Exception("No data")

        child_count = struct.unpack(">B", self.data[0])[0]

        if child_count > 16:
            # Don't have absurd numbers of children
            raise Exception("Too many children: {}".format(child_count))

        for i in xrange(child_count):
            # Unpack the next 65-byte record
            child_index, child_hash = struct.unpack_from(">B64s", self.data,
                                                         offset=1 + 65 * i)

            # Record it in the list of child hashes at the appropriate index.
            children[child_index] = child_hash

        return children

    def get_key(self):
        """
        Return the key for thhis AuthenticatedDictionaryStateComponent, or None
        if it doesn't carry one.

        """

        if len(self.data) == 0:
            raise Exception("No data")

        # After the children, we have key length (8 bytes), key, and value.

        # How many child records are there?
        child_count = struct.unpack(">B", self.data[0])[0]

        # Skip to after the child data
        offset = 1 + 65 * child_count

        if len(self.data) > offset:
            # We actually do have a key

            # Unpack the key length
            key_length = struct.unpack_from(">Q", self.data, offset=offset)[0]

            # Account for the 8 byte key length
            offset += 8

            # And the key itself
            key = self.data[offset: offset + key_length]

            return key

        # No key length was given after the children
        return None

    def get_value(self):
        """
        Return the value for thhis AuthenticatedDictionaryStateComponent, or None
        if it doesn't carry one.

        """

        if len(self.data) == 0:
            raise Exception("No data")

        # After the children, we have key length (8 bytes), key, and value.

        # How many child records are there?
        child_count = struct.unpack(">B", self.data[0])[0]

        # Skip to after the child data
        offset = 1 + 65 * child_count

        if len(self.data) > offset:
            # We actually do have a key

            # Unpack the key length
            key_length = struct.unpack_from(">Q", self.data, offset=offset)[0]

            # Advance to the start of thre data
            offset += 8 + key_length

            # Get the data
            data = self.data[offset:]

            return data

        # No key length was given after the children
        return None


class AuthenticatedDictionary(object):
    """
    An authenticated dictionary, based on a Merkle Trie, and stored on disk.

    Nodes are identified by pointers (really strings).

    The whole thing is backed by an SQLite database, but has additional
    transaction support. You can make a shallow copy of an
    AuthenticatedDictionary, and insert, find, and delete on it without
    affecting the original or other shallow copies. Copying a shallow copy with
    n changes made is O(N). When you want to save your changes to disk, run
    commit(). After one shallow copy (or the updated original) has been
    comitted, no accesses are allowed to anything that isn't it or a descendant
    of it created after the commit.

    Each chain of an AuthenticatedDictionary and its shallow copy descendants
    must have a unique database filename not shared with any other
    AuthenticatedDictonary chain. It's fine to share it with other things, as
    long as they never sync the database without calling commit on an
    AuthenticatedDictionary first.

    This is how you use it:
    >>> a = AuthenticatedDictionary(":memory:")
    >>> for x in map(str, xrange(100)):
    ...     a.insert(x, x)
    ...     a.commit()
    >>> a.clear()
    >>> a.insert("stuff", "wombats")
    >>> components, root = a.dump_state_components()
    >>> a.get_hash() == root
    True
    >>> a.commit()
    >>> a.clear()
    >>> b = a.copy()
    >>> b.import_from_state_components(components, root)
    >>> b.get_hash() == root
    True
    >>> b.find("stuff")
    'wombats'
    >>> c = a.copy()
    >>> c.update_from_state_components(components, root)
    >>> c.get_hash() == b.get_hash()
    True
    >>> c.find("stuff")
    'wombats'
    >>> a.insert("thing", "other thing")
    >>> a.commit()
    >>> for x in map(str, xrange(100)):
    ...     a.insert(x, x)
    ...     a.commit()
    >>> a.commit()
    >>> util.bytes2hex(a.get_hash())
    '3cf8a21949088a41f405e3f37c90af54e3cc33dce1c7b8226bd4e2450ddf2aff2d8dd089f3\
d78cd8a6dc5aea757a941868fd369daca22efd87b00d882b6e667d'
    >>> a.find("thing")
    'other thing'
    >>> print a.find("some third thing")
    None
    >>> len(set(a.iterkeys()))
    101
    >>> a.insert("some third thing", "foo")
    >>> a.remove("thing")
    >>> a.remove("some third thing")
    >>> a.insert("thing", "other thing")
    >>> util.bytes2hex(a.get_hash())
    '3cf8a21949088a41f405e3f37c90af54e3cc33dce1c7b8226bd4e2450ddf2aff2d8dd089f3\
d78cd8a6dc5aea757a941868fd369daca22efd87b00d882b6e667d'
    >>> a.get_node_by_hash(a.get_hash())
    'root'
    >>> a.commit()
    >>> a.get_node_by_hash(a.get_hash())
    'root'
    >>> a.insert("thing", "a different thing")
    >>> util.bytes2hex(a.get_hash())
    'af8e3873a0eb172a1aefe78661630f908266e4edbcaae9752ca0fc6a441bad654485\
43240d17f7ced11d5dad2f72a12ffab1afd7ad600ee4cfb89cdb4a5c64c8'

    This next test depends explicitly on internal pointer values.
    >>> a.node_to_state_component("100") # doctest: +NORMALIZE_WHITESPACE
    StateComponent gDoDgLKgh+RqaXBf6kdnQ67qkSy4wXwcQ/jdNFApA/rGZFssb87C+4ygOid5\
l3yNr1m9i9inTKl+pWhOQC0rRg==
        \t<13 bytes of data>


    We also get cool order independence
    >>> import random
    >>> observed_hashes = set()
    >>> for i in xrange(10):
    ...     items = [str(n) for n in xrange(10)]
    ...     random.shuffle(items)
    ...     d = AuthenticatedDictionary(":memory:", table="test{}".format(i))
    ...     for item in items:
    ...         d.insert(item, item)
    ...         d.commit()
    ...     random.shuffle(items)
    ...     for item in items:
    ...         d.remove(item)
    ...         d.commit()
    ...     random.shuffle(items)
    ...     for item in items:
    ...         d.insert(item, item)
    ...         d.commit()
    ...     random.shuffle(items)
    ...     for item in items:
    ...         d.insert(item, "{} updated".format(item))
    ...         d.commit()
    ...     observed_hashes.add(d.get_hash())
    >>> len(observed_hashes)
    1

    A demo of the shallow copy semantics:
    >>> c0 = AuthenticatedDictionary(":memory:", table="copies")
    >>> c0.insert("thing", "other thing")
    >>> digest = c0.get_hash()
    >>> c0.get_hash() == digest
    True

    Note that we can copy without committing. This is O(number of updates made
    since last commit)
    >>> c1 = c0.copy()
    >>> c0.get_hash() == digest
    True
    >>> c1.find("thing")
    'other thing'
    >>> c1.insert("thing", "not a thing")
    >>> c0.get_hash() == digest
    True
    >>> c1.find("thing")
    'not a thing'
    >>> c0.find("thing")
    'other thing'
    >>> c0.get_hash() == digest
    True
    >>> c1.get_hash() == digest
    False
    >>> print c1.get_node_by_hash(digest)
    None
    >>> c0.remove("thing")
    >>> print c0.find("thing")
    None
    >>> c1.find("thing")
    'not a thing'
    >>> c1.commit()



    """

    def __init__(self, filename=":memory:", table="AuthenticatedDictionary",
                 parent=None):
        """"
        Make a new AuthenticatedDictionary. Store it in the specified file. If a
        table is given, use that table name.

        If a parent is given, this AuthenticatedDictionary will be a transaction
        based off the parent. If this one is committed, the parent and any other
        copies must never be used again. If the parent or some other copy of it
        is committed, this copy must never be used again.

        Either a file name and a table, or a parent, should be specified, and
        not both or neither.

        """

        if parent is None:
            # We're setting up ourselves. We need to open the database and
            # potentially create a root.

            # Get the SQLiteDict we use to store our data. Make sure to use
            # transactions.
            self.store = SQLiteShelf(filename, table=table, lazy=True)

            # We use another SQLiteDict in the same database to maintain a
            # mapping from Merkle hashes to node pointers.
            self.hashmap = SQLiteShelf(filename, table="{}hashes".format(
                table), lazy=True)

            # Keep track of what to use as the next pointer for the next
            # allocated node. If it's None, it will get loaded from the database
            # when needed, and it gets saved back to the database on commit.
            self.next_pointer = None

            # Keep track of stored or overwritten nodes not yet comitted, by
            # pointer
            self.updates = {}

            # Keep track of deleted node pointers
            self.deletes = set()

            # And the same for the hashmap (these are by Merkle hash)
            self.hashmap_updates = {}
            self.hashmap_deletes = set()

            # Make sure we have a root node
            try:
                # Make sure we can load the root node (and thus that it exists)
                self.load_node("root")
            except BaseException:                # We couldn't load the root node, probably since it doesn't
                # exist. Fix that.
                self.store_node("root", MerkleTrieNode())
                self.update_node_hash("root")

        else:
            # We're becoming a transactional copy of a given parent.

            # Steal their database
            self.store = parent.store
            self.hashmap = parent.hashmap

            # Steal their next available pointer value
            self.next_pointer = parent.next_pointer

            # Steal a copy of their uncommitted updates. We can just store
            # references to the objects, though, because every time we update a
            # MerkleTrieNode we make a copy of it.
            self.updates = dict(parent.updates)

            # Copy their uncommitted deletes as well. These can't be updated in
            # place, so everything is OK.
            self.deletes = set(parent.deletes)

            # The parent took care of making a root node (even if it's
            # uncommitted), so we should have it.

            # Copy their uncommitted updates and deletes on the Merkle hash ->
            # node pointer database.
            self.hashmap_updates = dict(parent.hashmap_updates)
            self.hashmap_deletes = set(parent.hashmap_deletes)

    def copy(self):
        """
        Return a transactional copy of this AuthenticatedDictionary. Changes may
        be made to it and read back from it. If it is ever committed, the
        parent, all other copies of the parent, and all copies made from the
        copy before the commit must never be used again. If some other copy of
        the parent, the parent itself, or a copy of the copy is commited, the
        original copy must never be used again.

        """

        # Just use our awesome copy constructor mode.
        return AuthenticatedDictionary(parent=self)

    def get_hash(self):
        """
        Return the 64-byte digest of the current state of the dictionary, as a
        bytestring.

        """

        return self.load_node("root").hash

    def iterkeys(self):
        """
        Yield each key in the AuthenticatedDictionary. Not key hashes, the
        actual key strings.

        The caller may not add to or remove from the AuthenticatedDictionary
        while iterating over it. Modifying values shouild be OK.

        """

        # What do we need to look at?
        stack = []
        stack.append("root")

        while len(stack) > 0:
            # Pop a node to look at
            node = stack.pop()

            # Load the node's key
            key = self.get_node_key(node)

            if key is not None:
                # It's a data node
                yield key
            else:
                # It's not a data node. Look at its children.
                for child in self.get_node_children(node):
                    if child is not None:
                        # It actually has this child, so look at it.
                        stack.append(child)

    def iteritems(self):
        """
        Yield each key, value pair in the AuthenticatedDictionary. Not key hashes, the
        actual key strings.

        The caller may not add to or remove from the AuthenticatedDictionary
        while iterating over it. Modifying values shouild be OK.

        """

        # What do we need to look at?
        stack = []
        stack.append("root")

        while len(stack) > 0:
            # Pop a node to look at
            node = stack.pop()

            # Load the node
            node_obj = self.load_node(node)
            key = node_obj.key
            value = node_obj.value

            if key is not None:
                # It's a data node
                yield (key, value)
            else:
                # It's not a data node. Look at its children.
                for child in self.get_node_children(node):
                    if child is not None:
                        # It actually has this child, so look at it.
                        stack.append(child)

    def insert(self, key, value):
        """
        Insert the given value into the trie under the given key. The key and
        the value must both be strings.

        """

        # Hash the key
        key_hash = util.bytes2hex(hashlib.sha512(key).digest())

        self.recursive_insert("root", key_hash, key, 0, value)

    def recursive_insert(self, node, key_hash, key, level, value):
        """
        Insert the given value under the given key with the given hash (in hex)
        into the subtree rooted by the given node. level indicates the character
        in key_hash that corresponds to this node.

        """

        # It goes under the child slot corresponding to the level-th
        # character of the key hash.

        if level >= len(key_hash):
            raise Exception("Tree deeper ({}) than length of keys.".format(
                level))

        # Which child slot do we use?
        child_index = int(key_hash[level], base=16)

        # Get the child pointer value, or None if there is no child there.
        child = self.get_node_children(node)[child_index]
        logging.debug('INSERT to [{}:{}] with "{}" {} bytes'.format(
            self.store.table, node, key_hash[:8], len(value)))

        if child is None:
            # If that slot is empty, put the value there in a new node.
            child = self.create_node()
            self.set_node_key(child, key)
            self.set_node_value(child, value)
            self.update_node_hash(child)

            # Attach the node in the right place
            self.set_node_child(node, child_index, child)
        else:
            # Get the child's key
            child_key = self.get_node_key(child)

            if child_key == key:
                # If the slot has a node with the same key, overwrite
                # it.
                self.set_node_value(child, value)
                self.update_node_hash(child)

                if self.get_node_by_hash(self.get_node_hash(child)) != child:
                    raise Exception("Inconsistent insert")

                if self.load_node(child).children is not None:
                    raise Exception("Updated value on node with children")

            elif child_key is not None:
                # If the slot has a node with a different key hash,
                # recursively insert both that old value and this new ones
                # as children of the node that's there.

                # Hash the child key
                child_key_hash = util.bytes2hex(hashlib.sha512(
                    child_key).digest())

                # Get the value the child was storing.
                child_value = self.get_node_value(child)

                # Blank it out
                self.set_node_key(child, None)
                self.set_node_value(child, None)

                # Store the value that was there as a child of the child
                # node.
                self.recursive_insert(child, child_key_hash, child_key,
                                      level + 1, child_value)

                # Store our value as a (hopefully different) child of the
                # child node.
                self.recursive_insert(child, key_hash, key, level + 1, value)

                if self.get_node_by_hash(self.get_node_hash(child)) != child:
                    raise Exception("Inconsistent insert")

                if (self.get_node_key(child) is not None or
                        self.get_node_value(child) is not None):

                    raise Exception("Node with children added still has value")

            else:
                # If the slot has a node with no key hash (i.e. it has
                # children), insert the new value as a child of that node.

                self.recursive_insert(child, key_hash, key, level + 1, value)

                if self.get_node_by_hash(self.get_node_hash(child)) != child:
                    raise Exception("Inconsistent insert")

                if (self.get_node_key(child) is not None or
                        self.get_node_value(child) is not None):

                    raise Exception("Node with children added still has value")

        # Update our Merkle hash
        self.update_node_hash(node)

        if self.get_node_by_hash(self.get_node_hash(node)) != node:
            raise Exception("Inconsistent insert")

    def remove(self, key):
        """
        Remove the value under the given key from the trie. The key must be in
        the trie, and a string.

        """

        # Hash the key
        key_hash = util.bytes2hex(hashlib.sha512(key).digest())

        # Run the removal
        self.recursive_remove("root", key_hash, key, 0)

    def recursive_remove(self, node, key_hash, key, level):
        """
        Remove the value with the given key (which has the given hash) from the
        subtree rooted at the given node. The key hash is in hex, and level is
        the character in that hash being used at this level to decide on a child
        storage location.

        The algorithm works by the invariant that every leaf node (i.e. one with
        a value) has a sibling.

        If the key to remove is our direct descendant, drop it. This will never
        leave us with no children, since every leaf node has a sibling. It may
        leave us with one child with a value that now has no siblings.

        If the key to remove is our indirect descendant, we know it has a
        sibling. Remove the key we are removing, recursively. If this leaves a
        leaf node without any siblings, that value will be promoted to the child
        we recursed into. This may leave us with one child with a value that now
        has no siblings.

        If we now have only one child, which has a value, promote that value to
        this node and drop the child.

        """

        # The key can be found under the child slot corresponding to the level-
        # th character of the key hash.

        if level >= len(key_hash):
            raise Exception("Tree deeper ({}) than length of keys.".format(
                level))

        # Which child slot do we use?
        child_index = int(key_hash[level], base=16)

        # Get the pointer value, or None if there is no child there.
        child = self.get_node_children(node)[child_index]

        logging.debug('REMOVE from [{}:{}] key {}'.format(self.store.table, node, key_hash[:8]))

        if child is None:
            # If that slot is empty, the key can't possibly be in the trie.
            raise Exception("Tried to remove key hash {} that wasn't in the "
                            "trie".format(key_hash))

        child_key = self.get_node_key(child)

        if child_key == key:
            # If the slot has a node with the same key, we've found its leaf
            # node. Remove the leaf node.
            self.delete_node(child)

            # Set the child pointer in this node to None
            self.set_node_child(node, child_index, None)

        elif child_key is not None:
            # If the slot has a node with a different key, we're trying to
            # remove something not in the trie.
            raise Exception("Tried to remove key hash {} that wasn't in "
                            "the trie".format(key_hash))
        else:
            # If the slot has a node with no key (i.e. it has children), recurse
            # down on that node

            self.recursive_remove(child, key_hash, key, level + 1)

            if self.get_node_by_hash(self.get_node_hash(child)) != child:
                raise Exception("Inconsistent remove")

        # If we now have only one child, and that child has a value, promote the
        # value and remove the child.

        # Get a list of all the child pointers, some of which may be None. This
        # reflects all the changes made to remove the key we just removed.
        child_list = self.get_node_children(node)

        # Get a list of the indices that are filled with children
        child_indices = [i for i, child in enumerate(child_list) if child is not
                         None]

        if len(child_indices) == 1 and level != 0:
            # We have an only child, and we aren't the root, so we may need to
            # promote its value to us.

            # This holds the pointer for the child
            child = child_list[child_indices[0]]

            # Get its key
            child_key = self.get_node_key(child)

            if child_key is not None:
                # The only child is a leaf node. We need to promote it.

                # Steal the child's key and value
                self.set_node_key(node, child_key)
                self.set_node_value(node, self.get_node_value(child))

                # Kill the child
                self.delete_node(child)
                self.set_node_child(node, child_indices[0], None)

                if self.load_node(node).children is not None:
                    raise Exception("Node left with children when value "
                                    "promoted")

        # Update our Merkle hash
        self.update_node_hash(node)

        if self.get_node_by_hash(self.get_node_hash(node)) != node:
            raise Exception("Inconsistent remove")

    def find(self, key):
        """
        Return the value string corresponding to the given key string.

        """

        # Hash the key
        key_hash = util.bytes2hex(hashlib.sha512(key).digest())

        # Run the removal
        return self.recursive_find("root", key_hash, key, 0)

    def recursive_find(self, node, key_hash, key, level):
        """
        Find the value with the given key, which has the given hash, in the
        subtree rooted at the given node. The key hash is in hex, and level is
        the character in that hash being used at this level to decide on a child
        storage location.

        Returns the value found (a string), or None if no value is found.

        """

        # The key can be found under the child slot corresponding to the level-
        # th character of the key hash.

        if level >= len(key_hash):
            raise Exception("Tree deeper ({}) than length of keys.".format(
                level))

        # Which child slot do we use?
        child_index = int(key_hash[level], base=16)

        # Get the pointer value, or None if there is no child there.
        child = self.get_node_children(node)[child_index]

        if child is None:
            # If that slot is empty, the key can't possibly be in the trie.
            return None

        child_key = self.get_node_key(child)

        if child_key == key:
            # If the slot has a node with the same key, we've found its leaf
            # node. Return the value.
            return self.get_node_value(child)

        elif child_key is not None:
            # If the slot has a node with a different key, we're trying to find
            # something not in the trie.
            return None
        else:
            # If the slot has a node with no key (i.e. it has children), recurse
            # down on that node

            return self.recursive_find(child, key_hash, key, level + 1)

    def audit(self):
        """
        Make sure the AuthenticatedDictionary is in a consistent state.

        """

        # Put some statistics
        logging.debug("TRIE AUDIT: {} nodes on disk, {} updates, {} "
                      "deletes".format(len(self.store), len(self.updates),
                                       len(self.deletes)))

        # What do we need to look at?
        stack = []
        stack.append("root")

        root_hash = self.get_hash()

        while len(stack) > 0:
            # Pop a node to look at
            node = stack.pop()

            if node in self.updates and node in self.deletes:
                logging.error("Node {} both updated and deleted".format(node))

            # Load the node's struct
            node_struct = self.load_node(node)

            # Compute what its hash should be
            expected_hash = hashlib.sha512(self.node_to_bytes(node)).digest()

            if expected_hash != node_struct.hash:
                logging.error("Hash mismatch on node {}".format(node))

            if node_struct.children is not None:
                if node_struct.key is not None or node_struct.value is not None:
                    logging.error("Both value and children on node "
                                  "{}".format(node))
                for child in node_struct.children:
                    if child is not None:
                        # It actually has this child, so look at it.
                        stack.append(child)
            else:
                if node_struct.key is None or node_struct.value is None:
                    logging.error("Neither value nor key on node {}".format(
                        node))

                if self.find(node_struct.key) != node_struct.value:
                    logging.info("Node {} could not be found by search.".format(
                        node))

    def get_node_children(self, node):
        """
        Given the pointer of a node, return a sequence of either child
        pointers, or Nones if a node does not have a child at that index.

        """

        # Nodes are stored internally as pickled MerkleTrieNodes

        # Load the children list, which may itself be None
        children = self.load_node(node).children

        if children is None:
            # We don't store a whole empty child list, but our callers expect to
            # get one, so we fake it.
            return [None] * ORDER
        else:
            return children

    def set_node_child(self, node, index, child):
        """
        Set the index'th child of the node at the given pointer to the given
        child pointer value, which may be None.

        """

        # Load the node
        node_struct = self.load_node(node).copy()

        if node_struct.children is None:
            # We need to allocate spme spaces for child pointers
            node_struct.children = [None] * ORDER

        # Update the node
        node_struct.children[index] = child

        if child is None:
            # We may have removed the last real child.
            # Count up all the not-None children
            actual_children = sum(1 for c in node_struct.children
                                  if c is not None)

            if actual_children == 0:
                # No real children remain. Get rid of the list of Nones
                node_struct.children = None

        # Save the node again
        self.store_node(node, node_struct)

    def get_node_key(self, node):
        """
        Returns the key stored in the node with the given pointer, or None if it
        has no key.

        """

        return self.load_node(node).key

    def set_node_key(self, node, key):
        """
        Set the key stored at the node with the given pointer. May be set to
        None.

        """

        # Load the node
        node_struct = self.load_node(node).copy()

        # Update the node
        node_struct.key = key

        # Save the node again
        self.store_node(node, node_struct)

    def get_node_value(self, node):
        """
        Return the value stored at the node with the given pointer, or None if it
        has no value.

        """

        return self.load_node(node).value

    def set_node_value(self, node, value):
        """
        Set the value stored at the node with the given pointer. May be set to
        None.

        """

        # Load the node
        node_struct = self.load_node(node).copy()

        # Update the node
        node_struct.value = value

        # Save the node again
        self.store_node(node, node_struct)

    def get_node_hash(self, node):
        """
        Return the Merkle hash of the node with the given pointer.

        """

        return self.load_node(node).hash

    def get_node_by_hash(self, node_hash):
        """
        Given a node Merkle hash, return the node pointer that the hash belongs
        to, or None if no node exists with the given Merkle hash.

        """

        if node_hash in self.hashmap_deletes:
            # This node has been deleted
            return None
        elif node_hash in self.hashmap_updates:
            # This node has been updated (almost certainly created) since the
            # last commit.
            return self.hashmap_updates[node_hash]
        elif node_hash in self.hashmap:
            # This node exists in the actual database
            return self.hashmap[node_hash]
        else:
            # The node isn't in the database and hasn't been added.
            return None

    def node_to_bytes(self, node):
        """
        Given a node pointer, return a bytestring containing the node's unique
        state and the Merkle hashes of its children. The hash of this is the
        node's Merkle hash.

        This is the same regardless of what pointer a node or its children have.

        """

        # Load the node struct
        node_struct = self.load_node(node)

        # Structure: we have child count (1 byte), then that many child number
        # (byte) and Merkle hash (64 byte) records, followed optionally by a key
        # length (8 bytes), a key, and a value (which is the remainder). If key
        # length is not provided, no key is used.

        # This holds the bytestring parts to join together
        parts = []

        if node_struct.children is not None:
            # How many non-empty children do we have?
            child_count = sum(1 for child in node_struct.children if
                              child is not None)

            # Put the child couint
            parts.append(struct.pack(">B", child_count))

            for i, child_pointer in enumerate(node_struct.children):
                if child_pointer is not None:
                    # Say we have a child with this number
                    parts.append(struct.pack(">B", i))
                    # Go get the Merkle hash for this child
                    parts.append(self.get_node_hash(child_pointer))
        else:
            # No child list at all. Put 0 children.
            parts.append(struct.pack(">B", 0))

        if node_struct.key is not None:
            # We have a key and a value. Put the key length.
            parts.append(struct.pack(">Q", len(node_struct.key)))
            # Then the key string
            parts.append(node_struct.key)
            # Then the value string
            parts.append(node_struct.value)

        return "".join(parts)

    def update_node_hash(self, node):
        """
        Recalculate the Merkle hash for the given node. All of its childrens'
        Merkle hashes must be up to date.

        This is just the hash of the node, when the node is converted to bytes.

        """

        # Load the node
        node_struct = self.load_node(node).copy()

        if node_struct.hash is not None:
            # Either this node or a new node is listed under the node's current
            # hash. If it's this node, we need to remove the listing.

            if node_struct.hash in self.hashmap_updates:
                if self.hashmap_updates[node_struct.hash] == node:

                    # We're in as an update. Remove the update.
                    del self.hashmap_updates[node_struct.hash]
                else:
                    # Someone has overwritten us. Do nothing
                    pass
            elif (node_struct.hash in self.hashmap and
                  self.hashmap[node_struct.hash] == node):
                # Nobody has replaced us, and we're still under the old hash in
                # the backing database. Delete the old Merkle hash -> node
                # pointer mapping that points to us.
                self.hashmap_deletes.add(node_struct.hash)

            # If we don't delete anything, it probably means our key and value
            # got taken from us and put in some new leaf node that's exactly
            # like we used to be and hence has the same hash, and it got its
            # hash updated before we could (perhaps it is now our child)

        # Get the new hash. It's OK to hash the thing we copied from since we
        # have't changed it yet.
        node_struct.hash = hashlib.sha512(self.node_to_bytes(node)).digest()

        # Save the node
        self.store_node(node, node_struct)

        # Add the new Merkle hash -> node pointer mapping
        self.hashmap_deletes.discard(node_struct.hash)
        self.hashmap_updates[node_struct.hash] = node

    def create_node(self):
        """
        Return the pointer for a new node. Caller must make sure to update its
        hash.

        """

        if self.next_pointer is None:
            if "next_pointer" in self.store:
                # We need to load it from the database, since we haven't yet.
                self.next_pointer = self.store["next_pointer"]
            else:
                # It's a fresh database; start at 0
                self.next_pointer = 0
        # Make a string to actually use as the node pointer
        pointer = str(self.next_pointer)

        # Store a new node under that pointer
        self.store_node(pointer, MerkleTrieNode())

        # Increment the next pointer counter
        self.next_pointer += 1

        # Return the pointer to the new node
        return pointer

    def load_node(self, node):
        """
        Return a MerkleTrieNode object for the given node pointer. If you update
        it in place, you must store is back with store_node. (It's not that
        updating it in place won't take if you don't, it's that it might take
        and so we need to know it has happened.)

        Internally, lools at the list of changes since the last commit first. If
        the node hasn't been updated or deleted there, looks at the shelf
        database.

        """

        if node in self.updates:
            # The node at this pointer has been set since the last commit, so
            # use our in-memory version.
            return self.updates[node]
        elif node in self.deletes:
            # The node at this pointer has been deleted since the last commit,
            # so complain that someone is trying to use it.
            raise Exception("Attempted read of deleted node {}".format(node))

        # If it hasn't been updated or deleted, read it from the database.
        return self.store[node]

    def store_node(self, node, node_struct):
        """
        Store the given node struct (a MerkleTrieNode) under the given node
        pointer.

        Changes are not written to disk until commit is called, but can be seen
        by load_node.

        """

        # If it was deleted, it isn't anymore.
        self.deletes.discard(node)

        # Save the modified node as an update
        self.updates[node] = node_struct

    def delete_node(self, node):
        """
        Delete the node with the given pointer. It must not be the child of any
        node.

        Changes are not written to disk until commit is called, but can be seen
        by load_node. In particular, it is an error to try to load a node you
        have deleted.

        """

        # Grab the node hash before we delete it
        node_hash = self.get_node_hash(node)

        if node in self.updates:
            # If we wrote to it, now we need to delete it
            del self.updates[node]
        elif node in self.store:
            # Mark this key for deletion from the database, since it's there.
            self.deletes.add(node)
        else:
            # Complain about deleting a node that doesn't exist.
            raise Exception("Attempt to delete non-existent node {}".format(
                node))

        # Delete the Merkle hash to node pointer mapping
        if node_hash in self.hashmap:
            # It's in the real database, so mark it for deletion
            self.hashmap_deletes.add(node_hash)
        if node_hash in self.hashmap_updates:
            # It's not yet recorded in the database (potentially also). Don't
            # record it.
            del self.hashmap_updates[node_hash]

    def clear(self):
        """
        Remove all keys and values from the AuthenticatedDictionary. Does it
        quickly by emptying the underlying database table, but consequently
        invalidates all other copies of the AuthenticatedDictionary.

        """

        # Throw out our delta from the database
        self.deletes = set()
        self.updates = {}

        self.hashmap_deletes = set()
        self.hashmap_updates = {}

        # Clear the hashmap. This doesn't commit to the database, but empties
        # the shared SQLiteShelf.
        self.hashmap.clear()

        # Clear the node store
        self.store.clear()

        # We don't *need* to do this, but our test cases are happier if we start
        # the node pointers over again.
        self.next_pointer = None

        # We've deleted our root node. Make a new one.
        self.store_node("root", MerkleTrieNode())
        self.update_node_hash("root")

    def commit(self):
        """
        Commit changes to disk. Call this when you are done with a transaction.
        """

        # Audit the adds and deletes
        for key in self.updates.iterkeys():
            if key in self.deletes:
                raise Exception("Deleting and updating the same key: {}".format(
                    util.bytes2string(key)))

        for key in self.deletes:
            if key in self.updates:
                raise Exception("Deleting and updating the same key: {}".format(
                    key))

        for key in self.hashmap_updates.iterkeys():
            if key in self.hashmap_deletes:
                raise Exception("Deleting and updating the same key: {}".format(
                    util.bytes2string(key)))

        for key in self.hashmap_deletes:
            if key in self.hashmap_updates:
                raise Exception("Deleting and updating the same key: {}".format(
                    util.bytes2string(key)))

        # First, check up on all our updated nodes
        updated_nodes = self.updates.keys()
        for node in updated_nodes:
            if self.get_node_by_hash(self.get_node_hash(node)) != node:

                print self.updates
                print self.deletes
                print {util.bytes2string(key): value for key, value in self.hashmap_updates.iteritems()}
                print set(util.bytes2string(item) for item in self.hashmap_deletes)

                raise Exception("Node {} with hash {}, key {} not retrievable".format(
                    node, util.bytes2string(self.get_node_hash(node)),
                    self.get_node_key(node)))

        if self.next_pointer is not None:
            # Save the next unused node pointer to the store, if we ever
            # initialized it.
            self.store["next_pointer"] = self.next_pointer

        for node, node_struct in self.updates.iteritems():
            # Update all the updated nodes, pickling them in the process.
            self.store[node] = node_struct

        for node in self.deletes:
            if node in self.store:
                # Delete each deleted node that was actually in the database and
                # not, for example, added and deleted since the last commit.
                del self.store[node]

        for node_hash, node_pointer in self.hashmap_updates.iteritems():
            # Record all updated Merkle hash to pointer mappings. These are
            # almost certainly all additions.
            self.hashmap[node_hash] = node_pointer

        for node_hash in self.hashmap_deletes:
            # Record all the deleted Merkle hash to node pointer mappings
            del self.hashmap[node_hash]

        # Reset our records of what changes we need to make
        self.updates = {}
        self.deletes = set()
        self.hashmap_updates = {}
        self.hashmap_deletes = set()

        # Sync the store to disk, ending the transaction and implicitly starting
        # a new one.
        self.store.sync()
        # This uses the same underlying connection, but it never hurts to be
        # thorough. Hopefully.
        self.hashmap.sync()

        for node in updated_nodes:
            # Make sure the hashmap is still consistent now.
            if self.get_node_by_hash(self.get_node_hash(node)) != node:
                raise Exception("Node {} with hash {} not retrievable".format(
                    node, util.bytes2string(self.get_node_hash(node))))

    def discard(self):
        """
        Discard any changes made since the last commit.

        You don't need to call this if you're just getting rid of an
        AuthenticatedDictionary. You can just let the garbage collector collect
        it.

        """

        # Don't mess with the database, since we now only ever touch the
        # database on commit. Instead, just take the database as being correct.

        self.updates = {}

        self.deletes = set()

    def node_to_state_component(self, node):
        """
        Given a node pointer, return an AuthenticatedDictionaryStateComponent
        representing the node.

        """

        return AuthenticatedDictionaryStateComponent(self.node_to_bytes(node))

    def update_from_state_components(self, state_components, root_hash):
        """
        Given a dict from hash to StateComponent, and a root hash, make this
        AuthenticatedDictionary have the given hash. Requires that all
        dependency StateComponents be in the dict or in this
        AuthenticatedDictionary.

        The passed dict must contain the new root StateComponent, and root_hash
        must differ from the current root hash of the State.

        Assumes the StateComponents have all been validated.

        """

        # Conceptually, we're replacing the root and core of a tree, while
        # keeping some of the branches

        # Keep a set of re-used subtree root hashes.
        reused_roots = set()

        # We start at the root hash of the new tree, and traverse it. For each
        # Merkle hash, if we have a node for that hash, put it in the list of
        # re-used subtree roots and don't traverse down it. (The nodes for this
        # traversal can all come from the input dict.)

        # This holds the StateComponents we're traversing down through
        stack = [state_components[root_hash]]

        while len(stack) > 0:
            # Grab the top of the stack.
            current_component = stack.pop()

            for child_hash in current_component.get_dependencies():
                if self.get_node_by_hash(child_hash) is not None:
                    # This child is the root of a re-used subtree. Remember not
                    # to delete it, and don't traverse it.
                    reused_roots.add(child_hash)
                else:
                    # This child is a new node that came in in the dict. Recurse
                    # into it.
                    stack.append(state_components[child_hash])

        # We traverse our tree. If we find a re-used subtree root, don't
        # traverse down that branch. Otherwise, do. Remove the root of each
        # subtree we do traverse.

        # Now this holds a list of node pointers that we have to traverse.
        stack = ["root"]

        while len(stack) > 0:
            # Pop off the node to process
            current_pointer = stack.pop()

            if self.get_node_hash(current_pointer) not in reused_roots:
                # This is node and its children that aren't themselves reused
                # subtree roots need to be removed.

                for child_pointer in self.get_node_children(current_pointer):
                    if child_pointer is None:
                        # Skip empty children
                        continue

                    # Put the real children on the stack
                    stack.append(child_pointer)

                # Get rid of this replaced node (which may be "root")
                self.delete_node(current_pointer)

        # Now we only have the forrest of re-used subtrees.

        # Traverse the tree of StateComponents again, adding in pointers to re-
        # used subtrees or new nodes, as appropriate.

        # Now this holds the StateComponents we're traversing and turning into
        # nodes.
        stack = [state_components[root_hash]]

        while len(stack) > 0:
            # Grab the top of the stack.
            current_component = stack[-1]

            # How many of its children do we still need to make nodes for?
            missing_children = 0
            for child_hash in current_component.get_dependencies():
                if self.get_node_by_hash(child_hash) is None:
                    # Make sure we make a node for this child before truing to
                    # do its parent.
                    stack.append(state_components[child_hash])
                    missing_children += 1

            if missing_children > 0:
                # We've put all the children we still need on top of the current
                # node on the stack. Do them, and then come back to this node
                # when they're done.
                continue

            # When we get here, we know the subtrees for all our children have
            # been built. Build a subtree for us.

            if len(stack) == 1:
                # We're adding in the new root. Don't create a node, re-use the
                # "root" pointer.
                node_pointer = "root"

                # The old "root" node was deleted already above, beacuse it
                # wasn't the root of a reused subtree.

                # Store a fresh node as "root"
                self.store_node(node_pointer, MerkleTrieNode())
            else:
                # Make a new node with a new pointer to realize this non-root
                # StateComponent.
                node_pointer = self.create_node()

            for i, child_hash in enumerate(current_component.get_child_list()):
                if child_hash is not None:
                    # Grab the node pointer used for the subtree with this hash
                    child_node = self.get_node_by_hash(child_hash)

                    # We definitely should have this node at this point.
                    assert child_node is not None

                    # Make it a child of the new node.
                    self.set_node_child(node_pointer, i, child_node)

            if current_component.get_key() is not None:
                # We need to add a key and a value
                self.set_node_key(node_pointer, current_component.get_key())
                self.set_node_value(node_pointer,
                                    current_component.get_value())

            # Now we have populated this node, and we can calculate its Merkle
            # hash.
            self.update_node_hash(node_pointer)

            # It really needs to match the hash of the thing we're supposed to
            # be adding.
            assert (self.get_node_hash(node_pointer) ==
                    current_component.get_hash())

            # Now we're done putting in the node on top of the stack. Go up and
            # do the next one.
            stack.pop()

        # Now the AuthenticatedDictionary should be up to date. Since everything
        # went through load_node and store_node at some level, we have not even
        # invalidated other copies.

        # Make sure we did it right.
        assert root_hash == self.get_hash()

    def import_from_state_components(self, state_components, root_hash):
        """
        Given a dict from hash to StateComponent, and a root hash, make this
        AuthenticatedDictionary have the given hash. Requires that all
        dependency StateComponents be in the dict, and that this
        AuthenticatedDictionary start out empty.

        Assumes the StateComponents have all been validated.

        """

        # What component are we currently putting in?
        current_component = None

        # What components are stil to add? Use a stack because depth-first is
        # limited in depth.
        to_add = [root_hash]

        while len(to_add) > 0:
            # Now we just insert all the key/value pairs in the properly rooted
            # tree. TODO: This may be a bit slow.

            # Look at the top StateComponent
            current_component = state_components[to_add.pop()]

            # What are its children?
            child_hashes = list(current_component.get_dependencies())
            for child_hash in child_hashes:
                # Put its children on top of the stack to process next
                to_add.append(child_hash)

            if current_component.get_key() is not None:
                # Put in a node holding the key-value mapping
                self.insert(current_component.get_key(),
                            current_component.get_value())

    def dump_state_components(self):
        """
        Return a dict from Merkle hash to StateComponent, and the Merkel hash of
        the root StateCmponent, for a complete set of StateComponents describing
        this AuthenticatedDictionary.

        """

        # Make the dict from Merkle hash to state component
        state_components = {}

        # This holds a list of node pointers that we have to traverse.
        stack = ["root"]

        while len(stack) > 0:
            # Pop off the node to process
            pointer = stack.pop()

            for child_pointer in self.get_node_children(pointer):
                if child_pointer is None:
                    # Skip empty children
                    continue

                # Put the real children on the stack
                stack.append(child_pointer)

            # Make a StateComponent for the node
            component = self.node_to_state_component(pointer)

            # Keep it under its hash
            state_components[component.get_hash()] = component

        return state_components, self.get_hash()


if __name__ == "__main__":

    # Run doctests. See <http://docs.python.org/2/library/doctest.html>
    import doctest
    doctest.testmod()
