from dataclasses import dataclass


@dataclass
class MM_BaseElement:
    id: str
    key: str
    name: str
    index: int


@dataclass
class MM_Data:
    """Contains data related to MM, like actors or objects"""

    def __init__(self):
        from .enum_data import MM_EnumData
        from .actor_data import MM_ActorData

        self.enum_data = MM_EnumData()
        self.actor_data = MM_ActorData()
