
from genghis.game.action import Action
from genghis.game.observation import Observation


class Bot:
    """
    Base class for all bots.
    """
    def __init__(self, id: str = "NPC"):
        self.id = id

    def act(self, observation: Observation) -> Action:
        """
        This method should be implemented by the child class.
        It should receive an observation and return an action.
        """
        raise NotImplementedError

    def reset(self):
        """
        This method allows the agent to reset its state.
        If not needed, just pass.
        """
        raise NotImplementedError

    def __str__(self):
        return self.id