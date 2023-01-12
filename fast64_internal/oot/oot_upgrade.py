from bpy.types import Object, CollectionProperty
from .data import OoT_ObjectData
from .oot_utility import getEvalParams
from .oot_constants import ootEnumMusicSeq
from .cutscene.constants import (
    ootEnumTextType,
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


def upgradeCutsceneProperties(csListProp):
    # ``csListProp`` types: OOTCSTextboxProperty | OOTCSBGMProperty | OOTCSMiscProperty | OOTCSRumbleProperty
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
        ("ocarinaSongAction", "ocarinaAction", ootEnumOcarinaAction),
        ("type", "csTextType", ootEnumTextType),

        # BGM
        ("value", "csSeqID", ootEnumMusicSeq),

        # Misc
        ("operation", "csMiscType", ootEnumCSMiscType),
    ]


    # conversion to the same prop type
    # simply transfer the old data to the new one
    # special case for rumble props where it's a string to int conversion
    for oldName, newName in oldNamesToNewNames.items():
        if oldName in csListProp:
            value = csListProp[oldName]

            if newName in ["rumbleSourceStrength", "rumbleDuration", "rumbleDecreaseRate"]:
                value = int(getEvalParams(csListProp[oldName]), base=16)

            csListProp[newName] = value

            del csListProp[oldName]

    # conversion to another prop type
    for (oldName, newName, enumList) in differentPropsData:
        if oldName in csListProp:
            # get the old data
            oldData = csListProp[oldName]

            # if anything goes wrong there set the value to custom to avoid any data loss
            try:
                if isinstance(oldData, str):
                    # get the value, doing an eval for strings
                    # account for custom elements in the enums by adding 1
                    value = int(getEvalParams(oldData), base=16) + 1

                    # special cases for ocarina action enum
                    # since we don't have everything the value need to be shifted
                    if newName == "ocarinaAction":
                        if value in [0x00, 0x01, 0x0E] or value > 0x1A:
                            raise IndexError

                        if value > 0x0E:
                            value -= 1

                        value -= 2
                elif isinstance(oldData, int):
                    # account for custom elements in the enums by adding 1
                    value = oldData + 1

                    # another special case, this time for the misc enum
                    if newName == "csMiscType":
                        if value in [0x00, 0x04, 0x05]:
                            raise IndexError

                        if value > 0x05:
                            value -= 2

                        value -= 1
                else:
                    raise NotImplementedError

                # if the value is in the list find the identifier
                if value < len(enumList):
                    setattr(csListProp, newName, enumList[value][0])
                else:
                    # else raise an error to default to custom
                    raise IndexError
            except:
                setattr(csListProp, newName, "Custom")
                setattr(csListProp, f"{newName}Custom", str(oldData))

            del csListProp[oldName]
