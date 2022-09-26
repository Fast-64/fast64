from dataclasses import dataclass
from .oot_object_data import OoT_ObjectData
from .oot_actor_data import OoT_ActorData
from .oot_getters import OoT_Getters


class OoT_Common:
    """Common Data used by other functions or classes"""

    getters = OoT_Getters()


@dataclass
class OoT_Data:
    """Contains data related to OoT, like actors or objects"""

    def __init__(self):
        self.commonData = OoT_Common()
        self.objectData = OoT_ObjectData()
        self.actorData = OoT_ActorData()
