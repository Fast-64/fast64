from bpy.types import Object, CollectionProperty
from .data import OoT_ObjectData
from .oot_utility import getEvalParams
from .oot_constants import ootEnumMusicSeq
from .cutscene.constants import (
    ootEnumCSTextboxType,
    ootEnumCSMiscType,
    ootEnumOcarinaAction,
)


def upgradeObjectList(objList: CollectionProperty, objData: OoT_ObjectData):
    """Transition to the XML object system"""
    for obj in objList:

        # In order to check whether the data in the current blend needs to be updated,
        # we look for the ``objectID`` property, which has been removed in the current version.
        # If we find ``objectID`` it means that it's an old blend and needs be updated.
        # Finally, after the update we remove this property to tell Fast64 the object property is now up-to-date.
        if "objectID" in obj:
            # ``obj["objectID"]`` returns the index inside ``ootEnumObjectIDLegacy``
            # since Blender saves the index of the element of the EnumProperty
            objectID = objData.ootEnumObjectIDLegacy[obj["objectID"]][0]
            if objectID == "Custom":
                obj.objectKey = objectID
            else:
                obj.objectKey = objData.objectsByID[objectID].key

            del obj["objectID"]


def upgradeRoomHeaders(roomObj: Object, objData: OoT_ObjectData):
    """Main upgrade logic for room headers"""
    altHeaders = roomObj.ootAlternateRoomHeaders
    for sceneLayer in [
        roomObj.ootRoomHeader,
        altHeaders.childNightHeader,
        altHeaders.adultDayHeader,
        altHeaders.adultNightHeader,
    ]:
        if sceneLayer is not None:
            upgradeObjectList(sceneLayer.objectList, objData)
    for i in range(len(altHeaders.cutsceneHeaders)):
        upgradeObjectList(altHeaders.cutsceneHeaders[i].objectList, objData)


def upgradeCutsceneProperties(csObj: Object):
    # based on ``upgradeObjectList``

    oldNamesToNewNames = {
        # TextBox
        "messageId": "textID",
        "topOptionBranch": "topOptionTextID",
        "bottomOptionBranch": "bottomOptionTextID",

        # Lighting
        "index": "lightSettingsIndex",

        # Rumble
        "unk2": "rumbleSourceStrength",
        "unk3": "rumbleDuration",
        "unk4": "rumbleDecreaseRate",
    }

    differentPropsData = [
        # TextBox
        ("ocarinaSongAction", "ocarinaAction", ootEnumOcarinaAction)
        ("type", "textboxType", ootEnumCSTextboxType)

        # BGM
        ("value", "csSeqID", ootEnumMusicSeq),

        # Misc
        ("operation", "csMiscType", ootEnumCSMiscType),
    ]


    # conversion to the same prop type
    # simply transfer the old data to the new one
    for oldName, newName in oldNamesToNewNames.items():
        if oldName in csObj:
            csObj[newName] = csObj[oldName]

            del csObj[oldName]

    # conversion to another prop type
    for (oldName, newName, enumList) in differentPropsData:
        if oldName in csObj:
            # get the old data
            oldData = csObj[oldName]

            # if anything goes wrong there set the value to custom to avoid any data loss
            try:
                # get the value, doing an eval for strings
                value = int(getEvalParams(oldData), base=16)

                # if the value is in the list find the identifier
                if value < len(enumList):
                    setattr(csObj, newName, enumList[value][0])
                else:
                    # else raise an error to default to custom
                    raise IndexError
            except:
                setattr(csObj, newName, "Custom")
                setattr(csObj, f"{newName}Custom", oldData)

            del csObj[oldName]
