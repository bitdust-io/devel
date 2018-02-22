"""
State.py: contains the base State class.

"""

from StateComponent import StateComponent
from StateMachine import StateMachine


class State(object):
    """
    Represents some state data that gets kept up to date with the tip of the
    blockchain as new blocks come in. In Bitcoin, this might be used to hold the
    currently unspent outputs.

    Can return a copy of itself, and update with a block forwards, or a block
    backwards. Because we can run history both forwards and backwards, we can
    easily calculate the state at any block by walking a path from the tip of
    the longest branch.

    A State can be packed up for transmission over the network into a series of
    components. Components can depend on each other in a DAG. When the state
    changes, only log(n) components need to be updated, so it's possible to
    download components from a node that has a state that's constantly changing
    and still make meaningful progress. Every State exposes a means to get
    components.

    Responsible for persisting itself to and from a file. It should load from
    the file on construction, and save to the file on commit().

    Also responsible for producing StateMachine instances that can be used to
    update it.

    Ought to be replaced by implementations that actually keep state and make
    copies.

    """

    def step_forwards(self, block):
        """
        If this was the state before the given block, update to what the state
        would be after the block.

        """

        # No change is possible
        pass

    def step_backwards(self, block):
        """
        If this was the state after the given block, update to what the state
        must have been before the block.

        """

        # No change is possible
        pass

    def copy(self):
        """
        Return a shallow copy of this State. The State must have no un-commited
        operations. The copy may be stepped forwards and backwards without
        affecting the original state, and it may be safely discarded.

        """

        # Since there can be no change, no need to actually copy.
        return State()

    def commit(self):
        """
        Mark this State as the parent of all States that will be used from now
        on. No other States not descended form this one may be comitted in the
        future. Allows the State to clean up internal data structures related to
        efficiently allowing independent copies. Saves the state to disk to be
        re-loaded later.

        """

        # Nothing to do here.
        pass

    def clear(self):
        """
        Reset the State to zero or empty, as would be the case before the
        genesis block. When this method is called, all other existing copies of
        the State become invalid and may never be used again.

        """

        pass

    def get_component(self, component_hash):
        """
        Return the StateComponent with the given hash from this State, or None
        if no StateComponent with that hash exists in the State.

        All StateComponents are descendants of a StateComponent with the same
        hash as the State itself.

        """

        return None

    def update_from_components(self, components, root_hash):
        """
        Given a dict of just the StateComponents this State does not already
        have, by hash, and the hash of the new root StateComponent that we want
        this State to adopt, replace internal parts of the State with the
        StateComponents from the dict so that the State will have the given root
        hash.

        Subclasses must override this.

        """
        pass

    def get_hash(self):
        """
        Return a 64-byte hash of the State that is unique and matches the hashes
        of other identical states.

        """

        # Nothing to hash.
        return "\0" * 64

    def audit(self):
        """
        Make sure the State is internally consistent.

        """

        pass

    def make_state_machine(self):
        """
        Create a StateMachine that uses this State as a local store, and which
        uses the appropriate StateComponent implementation to deserialize
        incoming StateComponents.

        If you change the StateComponent class that your State uses, override
        this.

        """

        return StateMachine(StateComponent, self)
