"""
StateMachine.py: contains the StateMachine class.

"""

import logging


import util
import science


class StateMachine(object):
    """
    Represents a StateMachine, which downloads StateComponents until it has a
    whole tree of them. The StateMachine keeps track of whrre we are in the
    download process, because all block downloads themselves are asynchronous
    and cause event loop events, and because at any point we may get a new block
    and need to start from the top again and download pieces that have changed.

    If a Peer discovers that its Blockchain has no valid State, it can send us a
    download message with the hash of the root StateComponent to download. We
    will then go into a state where we can produce StateComponent hashes that
    we want to download.

    """

    def __init__(self, state_component_class, local_store=None):
        """
        Make a new StateMachine for downloading StateComponents. Uses the given
        state_component_class to deserialize StateComponents from bytestrings.

        If local_store is specified, it is a local source of StateComponents. It
        must always have the same StateComponents in it as long as we are in the
        downloading state, bust always have complete subtrees, and must expose
        them via a get_component(hash) method that returns a StateComponent
        object or None. (In practice, this can probably be the old State we are
        replacing.)

        """

        # Remember the StateComponentClass
        self.state_component_class = state_component_class

        # Remember the local store
        self.local_store = None

        # This holds a dict of downloaded StateComponents, by hash
        self.downloaded_components = {}

        # This holds a dict of all the StateComponents that we have along with
        # all their children, by hash
        self.downloaded_subtrees = {}

        # This holds a set of StateComponent hashes we need to download, which
        # are all children of the StateComponent on top of the stack.
        self.queued_set = set()

        # This holds the stack of StateComponents we're downloading subtrees
        # for. The top thing on it is always a StateComponent that we have, but
        # which we don't have all the children for. When it's empty, and we have
        # the subtree for the root, our download is done.
        self.stack = []

        # This holds the hash of the root StateComponent that we want to have
        # all the children of.
        self.root_hash = None

    def have_component(self, hash):
        """
        Return True if we've downloaded the component with the given hash, and
        False otherwise.

        """

        if hash in self.downloaded_components:
            # We downloaded it
            return True

        if (self.local_store is not None and
                self.local_store.get_component(hash) is not None):
            # We had it to start with
            return True

        return False

    def get_component(self, hash):
        """
        Return a StateComponent that we have, by hash.

        """

        if hash in self.downloaded_components:
            # We downloaded it
            return self.downloaded_components[hash]

        # We know we have it, so it must be in the local store.
        return self.local_store.get_component(hash)

    def have_subtree(self, hash):
        """
        Return True if we have the subtree rooted by the component with the
        given hash, and False otheriwse.

        """

        if hash in self.downloaded_subtrees:
            # We downloaded it
            return True

        if (self.local_store is not None and
                self.local_store.get_component(hash) is not None):
            # We had it to start with
            return True

    def process_stack(self):
        """
        Put all the children that we next should download into queued_set.
        Advances and retracts the stack according to an in-order traversal.

        Returns False if there are children in queued_set that we still need to
        download before the stack can move, or True if there is more stack
        processing to be done and it should be called again.

        If it returns True, but the stack is empty, we have downloaded
        everything on the stack.

        """

        # Get the StateComponent on top of the stack.

        top = self.stack[-1]

        # Do we have all of its children downloaded? If not, the stack stays
        # here.
        needed_children = 0

        for child_hash in top.get_dependencies():
            if not self.have_component(child_hash):
                # Go get this child
                needed_children += 1
                self.queued_set.add(child_hash)

        if needed_children > 0:
            # We already queued up all the missing children of this node. Stop
            # processing the stack and go get them.
            return False

        # If we get here, we have all the children of the top node.

        # Do we have all of its child subtrees downloaded? If not, advance into
        # the first one.
        for child_hash in top.get_dependencies():
            if not self.have_subtree(child_hash):
                # This is the first, go into this one.
                self.stack.append(self.downloaded_components[child_hash])

                # Start again from the top, and either download the children of
                # this child, or advance into its first incomplete subtree, or
                # mark it as complete.
                return True

        # If we get here, the StateComponent on top of the stack has all its
        # child subtrees. So we know we have the subtree rooted at it
        self.downloaded_subtrees[top.get_hash()] = top

        # Pop it off the stack, and go back and check on its parent, which may
        # either be a complete subtree now, or have other children to get, or
        # have other subtrees to download.
        self.stack.pop()
        return True

    def add_component(self, component_bytestring):
        """
        We got a new StateComponent.

        """

        # Deserialize it
        component = self.state_component_class(component_bytestring)

        # Get its hash
        component_hash = component.get_hash()

        if component_hash in self.queued_set:
            # We asked for this one, and now we have it
            self.queued_set.remove(component_hash)

            # Save it
            self.downloaded_components[component_hash] = component

            logging.debug("Accepted StateComponent {}".format(util.bytes2string(
                component_hash)))
        elif component_hash in self.downloaded_components:
            # We don't need that one because we have it already.
            logging.debug("StateComponent {} was already downloaded.".format(
                util.bytes2string(component_hash)))
        else:
            # We got someting we didn't ask for.
            logging.warning("StateComponent {} was unsolicited!".format(
                util.bytes2string(component_hash)))

    def tick(self):
        """
        Advance the stack until either we have some components to download or
        the stack empties and we have the root subtree and we're done with our
        download.

        """

        if len(self.stack) == 0 and not self.have_subtree(self.root_hash):
            # We still need the root subtree
            if self.have_component(self.root_hash):
                # We got the root component, though. Put it on the stack so we
                # can go get its children.
                self.stack.append(self.get_component(self.root_hash))
            else:
                # We need to download the root component first.
                self.queued_set.add(self.root_hash)

                logging.debug("Need to download root hash: {}".format(
                    util.bytes2string(self.root_hash)))

        while len(self.stack) > 0 and self.process_stack():
            # Keep going through this loop
            pass

        # When we get here, we either have a set of StateComponent hashes to
        # download, or we're done.

    def is_done(self):
        """
        Return True if we're done with our download, False otherwise.

        """

        # Are we done yet? We're done if we have the root hash's subtree.
        done = self.have_subtree(self.root_hash)

        if done:
            # Stop our state download timer, if it's running. We assume we only
            # ever have on SateMachine going at a time, but we do actually only
            # ever have one StateMachine going at a time (for a Blockchain).
            science.stop_timer("state_download")

        return done

    def get_components(self):
        """
        Return a dict from hash to StateComponent object for all the newly
        downloaded StateComponents that are subtree roots.

        """

        return self.downloaded_subtrees

    def get_requests(self):
        """
        Returns a set of StateComponent hashes that we would like to download.

        """

        return self.queued_set

    def download(self, root_hash):
        """
        Download the StateComponent tree for the given root hash. Re-sets any
        in-progress download and clears the set of requests. Keeps the
        downloaded StateCompinents and subtrees since they will probably be re-
        used at least partially. Call tick after this so that get_requests will
        have something in it.

        """

        # Throw out the old requested component set
        self.queued_set = set()

        # Set the root hash
        self.root_hash = root_hash

        # Clear off the stack, since we need to come down from the new root and
        # download different branches. In the ideal case we'll have lots of
        # subtrees already from our local store or the parts we've been
        # downloading.
        self.stack = []

        logging.info("Now downloading state {}".format(util.bytes2string(
            self.root_hash)))

        # Start a timer so we know when the state download is done. Don't
        # replace a running timer because we may switch to downloading a
        # different state in the middle.
        science.start_timer("state_download", replace=False)
