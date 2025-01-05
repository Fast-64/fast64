from os import path
from dataclasses import dataclass
from pathlib import Path
from .getters import get_xml_root
from .data import MM_BaseElement


@dataclass
class MM_ActorElement(MM_BaseElement):
    category: str
    tied_objects: list[str]


class MM_ActorData:
    """Everything related to MM Actors"""

    def __init__(self):
        # Path to the ``ActorList.xml`` file
        actor_root = get_xml_root(Path(f"{path.dirname(path.abspath(__file__))}/xml/ActorList.xml").resolve())

        # general actor list
        self.actor_list: list[MM_ActorElement] = []

        for actor in actor_root.iterfind("Actor"):
            tied_objects = []
            obj_key = actor.get("ObjectKey")
            actorName = f"{actor.attrib['Name']} - {actor.attrib['ID'].removeprefix('ACTOR_')}"

            if obj_key is not None:  # actors don't always use an object
                tied_objects = obj_key.split(",")

            self.actor_list.append(
                MM_ActorElement(
                    actor.attrib["ID"],
                    actor.attrib["Key"],
                    actorName,
                    int(actor.attrib["Index"]),
                    actor.attrib["Category"],
                    tied_objects,
                )
            )

        self.actors_by_key = {actor.key: actor for actor in self.actor_list}
        self.actors_by_id = {actor.id: actor for actor in self.actor_list}

        # list of tuples used by Blender's enum properties
        last_index = max(1, *(actor.index for actor in self.actor_list))
        self.enum_actor_id = [("None", f"{i} (Deleted from the XML)", "None") for i in range(last_index)]
        self.enum_actor_id.insert(0, ("Custom", "Custom Actor", "Custom"))
        for actor in self.actor_list:
            self.enum_actor_id[actor.index] = (actor.id, actor.name, actor.id)
