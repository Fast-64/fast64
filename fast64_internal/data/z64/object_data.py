from dataclasses import dataclass
from pathlib import Path

from ...utility import PluginError
from .common import Z64_BaseElement, get_xml_root

# Note: "object" in this context refers to an OoT Object file (like ``gameplay_keep``)


@dataclass
class Z64_ObjectElement(Z64_BaseElement):
    pass


class Z64_ObjectData:
    """Everything related to OoT objects"""

    def __init__(self, game: str):
        # general object list
        self.objectList: list[Z64_ObjectElement] = []

        # Path to the ``ObjectList.xml`` file
        xml_path = Path(__file__).resolve().parent / "xml" / f"{game.lower()}_object_list.xml"
        object_root = get_xml_root(xml_path.resolve())

        for obj in object_root.iterfind("Object"):
            objName = f"{obj.attrib['Name']} - {obj.attrib['ID'].removeprefix('OBJECT_')}"
            self.objectList.append(
                Z64_ObjectElement(obj.attrib["ID"], obj.attrib["Key"], objName, int(obj.attrib["Index"]))
            )

        self.objects_by_id = {obj.id: obj for obj in self.objectList}
        self.objects_by_key = {obj.key: obj for obj in self.objectList}

        # list of tuples used by Blender's enum properties
        self.deletedEntry = ("None", "(Deleted from the XML)", "None")
        lastIndex = max(1, *(obj.index for obj in self.objectList))
        self.ootEnumObjectKey = self.getObjectIDList(lastIndex + 1, False, game)

        # create the legacy object list for old blends
        if game == "OOT":
            self.ootEnumObjectIDLegacy = self.getObjectIDList(
                self.objects_by_key["obj_timeblock"].index + 1, True, game
            )

            # validate the legacy list, if there's any None element then something's wrong
            if self.deletedEntry in self.ootEnumObjectIDLegacy:
                raise PluginError("ERROR: Legacy Object List doesn't match!")
        else:
            self.ootEnumObjectIDLegacy = []

    def getObjectIDList(self, max: int, isLegacy: bool, game: str):
        """Generates and returns the object list in the right order"""
        objList = [self.deletedEntry] * max
        for obj in self.objectList:
            if obj.index < max:
                identifier = obj.id if isLegacy else obj.key
                objList[obj.index] = (identifier, obj.name, obj.id)
        if game == "OOT":
            objList[0] = ("Custom", "Custom Object", "Custom")
        else:
            objList.insert(0, ("Custom", "Custom Object", "Custom"))
        return objList
