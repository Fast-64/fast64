from dataclasses import dataclass
from .oot_object_data import OoT_ObjectData
from .oot_actor_data import OoT_ActorData
from .oot_getters import OoT_Getters


class OoT_Common:
    """Common Data used by other functions or classes"""

    @dataclass
    class OoT_Object:
        id: str
        key: str
        name: str

    @dataclass
    class OoT_Actor:
        id: str
        key: str
        name: str
        category: str
        tiedObjects: str

    getters = OoT_Getters()


@dataclass
class OoT_Data:
    """Contains data related to OoT, like actors or objects"""

    def __init__(self):
        self.common = OoT_Common()
        self.object = OoT_ObjectData()
        self.actor = OoT_ActorData()
