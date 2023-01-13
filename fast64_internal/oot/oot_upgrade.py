from bpy.types import Object, CollectionProperty
from .data import OoT_ObjectData
from .oot_utility import getEvalParams
from .oot_constants import ootEnumMusicSeq
from .cutscene.constants import (
    ootEnumTextType,
    ootEnumCSMiscType,
    ootEnumOcarinaAction,
    ootEnumCSTransitionType,
    ootEnumCSDestinationType,
)


#####################################
# Room Header
#####################################
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


#####################################
# Cutscene
#####################################
def transferOldDataToNew(data, oldDataToNewData: dict):
    # conversion to the same prop type
    # simply transfer the old data to the new one
    # special case for rumble subprops where it's a string to int conversion
    for oldName, newName in oldDataToNewData.items():
        if oldName in data:
            if newName is not None:
                value = data[oldName]

                if newName in ["rumbleSourceStrength", "rumbleDuration", "rumbleDecreaseRate"]:
                    value = int(getEvalParams(data[oldName]), base=16)

                data[newName] = value

            del data[oldName]


def convertOldDataToEnumData(data, oldDataToEnumData: list[tuple[str, str, list[tuple[str, str, str]]]]):
    # conversion to another prop type
    for (oldName, newName, enumList) in oldDataToEnumData:
        if oldName in data:
            # get the old data
            oldData = data[oldName]

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

                    if newName == "csSeqID":
                        # the old fade out value is wrong, it assumes it's a seq id
                        # but it's not, it's a seq player id,
                        # hence why we raise an error so it defaults to "custom" to avoid any data loss
                        # @TODO: find a way to check properly which seq command it is
                        raise NotImplementedError
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
                    setattr(data, newName, enumList[value][0])
                else:
                    # else raise an error to default to custom
                    raise IndexError
            except:
                setattr(data, newName, "Custom")
                setattr(data, f"{newName}Custom", str(oldData))

                # @TODO: find a way to check properly which seq command it is
                if newName == "csSeqID":
                    setattr(data, "csSeqPlayer", "Custom")
                    setattr(data, "csSeqPlayerCustom", str(oldData))

            del data[oldName]


def upgradeCutsceneSubProps(csListSubProp):
    # ``csListSubProp`` types: OOTCSTextProperty | OOTCSSeqProperty | OOTCSMiscProperty | OOTCSRumbleProperty
    # based on ``upgradeObjectList``

    subPropsOldToNew = {
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
        # Unk (Deprecated)
        "unk": None,
        "unkType": None,
        "unk1": None,
        "unk2": None,
        "unk3": None,
        "unk4": None,
        "unk5": None,
        "unk6": None,
        "unk7": None,
        "unk8": None,
        "unk9": None,
        "unk10": None,
        "unk11": None,
        "unk12": None,
    }

    subPropsToEnum = [
        # TextBox
        ("ocarinaSongAction", "ocarinaAction", ootEnumOcarinaAction),
        ("type", "csTextType", ootEnumTextType),
        # Seq
        ("value", "csSeqID", ootEnumMusicSeq),
        # Misc
        ("operation", "csMiscType", ootEnumCSMiscType),
    ]

    transferOldDataToNew(csListSubProp, subPropsOldToNew)
    convertOldDataToEnumData(csListSubProp, subPropsToEnum)


def upgradeCSListProps(csListProp):
    # ``csListProp`` type: ``OOTCSListProperty``

    csListPropOldToNew = {
        "textbox": "textList",
        "lighting": "lightSettingsList",
        "time": "timeList",
        "bgm": "seqList",
        "misc": "miscList",
        "nine": "rumbleList",
        "fxStartFrame": "transitionStartFrame",
        "fxEndFrame": "transitionEndFrame",
    }

    transferOldDataToNew(csListProp, csListPropOldToNew)

    # both are enums but the item list is different (the old one doesn't have a "custom" entry)
    convertOldDataToEnumData(csListProp, [("fxType", "transitionType", ootEnumCSTransitionType)])


def upgradeCutsceneProperty(csProp):
    # ``csProp`` type: ``OOTCutsceneProperty``

    csPropOldToNew = {
        "csWriteTerminator": "csUseDestination",
        "csTermStart": "csDestinationStartFrame",
        "csTermEnd": None,
    }

    transferOldDataToNew(csProp, csPropOldToNew)
    convertOldDataToEnumData(csProp, [("csTermIdx", "csDestination", ootEnumCSDestinationType)])
