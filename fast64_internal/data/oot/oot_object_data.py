from dataclasses import dataclass
from os import path
from ...utility import PluginError
from .oot_getters import getXMLRoot
from .oot_data import OoT_BaseElement

# Note: "object" in this context refers to an OoT Object file (like ``gameplay_keep``)


@dataclass
class OoT_ObjectElement(OoT_BaseElement):
    pass


class OoT_ObjectData:
    """Everything related to OoT objects"""

    def __init__(self):
        # general object list
        self.objectList: list[OoT_ObjectElement] = []

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

        # list of tuples used by Blender's enum properties
        self.deletedEntry = ("None", "(Deleted from the XML)", "None")
        lastIndex = max(1, *(obj.index for obj in self.objectList))
        self.ootEnumObjectKey = self.getObjectIDList(lastIndex + 1, False)

        # create the legacy object list for old blends
        self.ootEnumObjectIDLegacy = self.getObjectIDList(self.objectsByKey["obj_timeblock"].index + 1, True)

        # validate the legacy list, if there's any None element then something's wrong
        if self.deletedEntry in self.ootEnumObjectIDLegacy:
            raise PluginError("ERROR: Legacy Object List doesn't match!")

    def getObjectIDList(self, max: int, isLegacy: bool):
        """Generates and returns the object list in the right order"""
        objList = [self.deletedEntry] * max
        for obj in self.objectList:
            if obj.index < max:
                identifier = obj.id if isLegacy else obj.key
                objList[obj.index] = (identifier, obj.name, obj.id)
        objList[0] = ("Custom", "Custom Object", "Custom")
        return objList
