from dataclasses import dataclass
from os import path
from pathlib import Path
from .getters import get_xml_root
from .data import MM_BaseElement

# Note: "object" in this context refers to an MM Object file (like `gameplay_keep`)


@dataclass
class MM_ObjectElement(MM_BaseElement):
    pass


class MM_ObjectData:
    """Everything related to MM objects"""

    def __init__(self):
        # general object list
        self.object_list: list[MM_ObjectElement] = []

        # Path to the ``ObjectList.xml`` file
        object_root = get_xml_root(Path(f"{path.dirname(path.abspath(__file__))}/xml/ObjectList.xml"))

        for obj in object_root.iterfind("Object"):
            obj_name = f"{obj.attrib['Name']} - {obj.attrib['ID'].removeprefix('OBJECT_')}"
            self.object_list.append(
                MM_ObjectElement(obj.attrib["ID"], obj.attrib["Key"], obj_name, int(obj.attrib["Index"]))
            )

        self.objects_by_id = {obj.id: obj for obj in self.object_list}
        self.objects_by_key = {obj.key: obj for obj in self.object_list}

        # list of tuples used by Blender's enum properties
        self.deleted_entry = ("None", "(Deleted from the XML)", "None")
        last_index = max(1, *(obj.index for obj in self.object_list))
        self.enum_object_key = self.get_object_id_list(last_index + 1)

    def get_object_id_list(self, max: int):
        """Generates and returns the object list in the right order"""
        objList = [self.deleted_entry] * max
        for obj in self.object_list:
            if obj.index < max:
                identifier = obj.key
                objList[obj.index] = (identifier, obj.name, obj.id)
        objList[0] = ("Custom", "Custom Object", "Custom")
        return objList
