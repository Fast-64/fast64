from dataclasses import dataclass
from os import path
from ...utility import ootGetSceneOrRoomHeader, PluginError
from .oot_getters import getXMLRoot, getEnumList
from .oot_data import OoT_BaseElement

# Note: "object" in this context refers to an OoT Object file (like ``gameplay_keep``)


@dataclass
class OoT_ObjectElement(OoT_BaseElement):
    index: int


class OoT_ObjectData:
    """Everything related to OoT objects"""

    def __init__(self):
        # general object list
        self.objectList: list[OoT_ObjectElement] = []

        # list of tuples used by Blender's enum properties
        self.ootEnumObjectKey: list[tuple] = []
        self.ootEnumObjectIDLegacy: list[tuple] = []  # for old blends

        # Path to the ``ObjectList.xml`` file
        objectXML = path.dirname(path.abspath(__file__)) + "/xml/ObjectList.xml"
        objectRoot = getXMLRoot(objectXML)

        for obj in objectRoot.iterfind("Object"):
            objName = f"{obj.attrib['Name']} - {obj.attrib['ID'].removeprefix('OBJECT_')}"
            self.objectList.append(
                OoT_ObjectElement(obj.attrib["ID"], obj.attrib["Key"], objName, int(obj.attrib["Index"]))
            )

        self.objectsByID = {obj.id: obj for obj in self.objectList}
        self.objectsByKey = {obj.key: obj for obj in self.objectList}
        self.ootEnumObjectKey = getEnumList(self.objectList, "Custom Object")[0]

        # create the legacy object list
        lastIndex = self.objectsByKey["obj_timeblock"].index
        self.ootEnumObjectIDLegacy = [None] * lastIndex
        self.ootEnumObjectIDLegacy.insert(0, ("Custom", "Custom Object", "Custom"))
        for obj in self.objectList:
            if obj.index < lastIndex + 1:
                self.ootEnumObjectIDLegacy[obj.index] = (obj.id, obj.name, obj.id)

        # validate the legacy list, if there's any None element then something's wrong
        if None in self.ootEnumObjectIDLegacy:
            raise PluginError("ERROR: Legacy Object List doesn't match!")
