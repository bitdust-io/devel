"""
StateComponent.py: Contains the StateComponent class.

"""

from __future__ import absolute_import
import hashlib
import pybc.util


class StateComponent(object):
    """
    A part of a State's DAG for transmitting over the network.

    Contains some binary data, and knows how to manipulate that data to return a
    Merkle hash, and an iterator of Merkle hashes of its dependencies.

    """

    def __init__(self, data):
        """
        Make a StateComponent with the given bytestring of data.

        """

        # Keep the bytestring data
        self.data = data

    def get_hash(self):
        """
        Return a hash of the StateComponent.

        Implementations can overide this.
        """

        return hashlib.sha512(self.data).digest()

    def get_dependencies(self):
        """
        Iterate over Merkle hashes of the dependencies of this node, that we
        should fetch to include with this node.

        Implementations can override this.

        """

        return []

    def __repr__(self):
        """
        Make a StateComponent into a string.

        """

        # Make a list of lines to merge together into one string
        lines = []

        # Start with the hash we have
        lines.append("StateComponent {}".format(pybc.util.bytes2string(
            self.get_hash())))

        for dependency in self.get_dependencies():
            # Then list all the dependencies we need.
            lines.append("\tDependency {}".format(pybc.util.bytes2string(
                dependency)))

        # Finally talk about the data
        lines.append("\t<{} bytes of data>".format(len(self.data)))

        return "\n".join(lines)
