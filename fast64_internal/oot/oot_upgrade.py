import bpy

from dataclasses import dataclass
from typing import TYPE_CHECKING
import bpy
from bpy.types import Object, CollectionProperty
from .data import OoT_ObjectData
from .oot_utility import getEvalParams
from .oot_constants import ootData
from .cutscene.constants import ootEnumCSMotionCamMode

if TYPE_CHECKING:
    from .cutscene.properties import OOTCutsceneProperty


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
@dataclass
class Cutscene_UpgradeData:
    oldPropName: str
    newPropName: str
    enumData: list[tuple[str, str, str]]  # this is the list used for enum properties


def transferOldDataToNew(data, oldDataToNewData: dict[str, str]):
    # conversion to the same prop type
    # simply transfer the old data to the new one
    for oldName, newName in oldDataToNewData.items():
        if oldName in data:
            if newName is not None:
                value = data[oldName]

                # special case for rumble subprops where it's a string to int conversion
                # another special case for light setting index where the value need to be minus one
                if newName in ["rumbleSourceStrength", "rumbleDuration", "rumbleDecreaseRate"]:
                    value = int(getEvalParams(data[oldName]), base=16)
                elif newName == "lightSettingsIndex":
                    value -= 1

                data[newName] = value

            del data[oldName]


def convertOldDataToEnumData(data, oldDataToEnumData: list[Cutscene_UpgradeData]):
    # conversion to another prop type
    for csUpgradeData in oldDataToEnumData:
        if csUpgradeData.oldPropName in data:
            # get the old data
            oldData = data[csUpgradeData.oldPropName]

            # if anything goes wrong there set the value to custom to avoid any data loss
            try:
                if isinstance(oldData, str):
                    # get the value, doing an eval for strings
                    # account for custom elements in the enums by adding 1
                    value = int(getEvalParams(oldData), base=16) + 1

                    # special cases for ocarina action enum
                    # since we don't have everything the value need to be shifted
                    if csUpgradeData.newPropName == "ocarinaAction":
                        if value in [0x00, 0x01, 0x0E] or value > 0x1A:
                            raise IndexError

                        if value > 0x0E:
                            value -= 1

                        value -= 2

                    if csUpgradeData.newPropName == "csSeqID":
                        # the old fade out value is wrong, it assumes it's a seq id
                        # but it's not, it's a seq player id,
                        # hence why we raise an error so it defaults to "custom" to avoid any data loss
                        # @TODO: find a way to check properly which seq command it is
                        raise NotImplementedError
                elif isinstance(oldData, int):
                    # account for custom elements in the enums by adding 1
                    value = oldData + 1

                    # another special case, this time for the misc enum
                    if csUpgradeData.newPropName == "csMiscType":
                        if value in [0x00, 0x04, 0x05]:
                            raise IndexError

                        if value > 0x05:
                            value -= 2

                        value -= 1
                else:
                    raise NotImplementedError

                # if the value is in the list find the identifier
                if value < len(csUpgradeData.enumData):
                    setattr(data, csUpgradeData.newPropName, csUpgradeData.enumData[value][0])
                else:
                    # else raise an error to default to custom
                    raise IndexError
            except:
                setattr(data, csUpgradeData.newPropName, "Custom")
                setattr(data, f"{csUpgradeData.newPropName}Custom", str(oldData))

                # @TODO: find a way to check properly which seq command it is
                if csUpgradeData.newPropName == "csSeqID":
                    setattr(data, "csSeqPlayer", "Custom")
                    setattr(data, "csSeqPlayerCustom", str(oldData))

            del data[csUpgradeData.oldPropName]


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
        Cutscene_UpgradeData("ocarinaSongAction", "ocarinaAction", ootData.enumData.ootEnumOcarinaSongActionId),
        Cutscene_UpgradeData("type", "csTextType", ootData.enumData.ootEnumCsTextType),
        # Seq
        Cutscene_UpgradeData("value", "csSeqID", ootData.enumData.ootEnumSeqId),
        # Misc
        Cutscene_UpgradeData("operation", "csMiscType", ootData.enumData.ootEnumCsMiscType),
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
    convertOldDataToEnumData(
        csListProp, [Cutscene_UpgradeData("fxType", "transitionType", ootData.enumData.ootEnumCsTransitionType)]
    )


def upgradeCutsceneProperty(csProp: "OOTCutsceneProperty"):
    csPropOldToNew = {
        "csWriteTerminator": "csUseDestination",
        "csTermStart": "csDestinationStartFrame",
        "csTermEnd": None,
    }

    transferOldDataToNew(csProp, csPropOldToNew)
    convertOldDataToEnumData(
        csProp, [Cutscene_UpgradeData("csTermIdx", "csDestination", ootData.enumData.ootEnumCsDestination)]
    )


def upgradeCutsceneMotion(csMotionObj: Object):
    """Main upgrade logic for Cutscene Motion data from zcamedit"""
    objName = csMotionObj.name

    if csMotionObj.type == "EMPTY":
        csMotionProp = csMotionObj.ootCSMotionProperty

        if "zc_alist" in csMotionObj and ("Preview." in objName or "ActionList." in objName):
            legacyData = csMotionObj["zc_alist"]
            emptyTypeSuffix = "List" if "ActionList." in objName else "Preview"
            csMotionObj.ootEmptyType = f"CS {'Player' if 'Link' in objName else 'Actor'} Cue {emptyTypeSuffix}"

            if "actor_id" in legacyData:
                index = legacyData["actor_id"]
                if index >= 0:
                    cmdEnum = ootData.enumData.enumByKey["csCmd"]
                    cmdType = cmdEnum.itemByIndex.get(index)
                    if cmdType is not None:
                        csMotionProp.actorCueListProp.commandType = cmdType.key
                    else:
                        csMotionProp.actorCueListProp.commandType = "Custom"
                        csMotionProp.actorCueListProp.commandTypeCustom = f"0x{index:04X}"
                del legacyData["actor_id"]

            del csMotionObj["zc_alist"]

        if "zc_apoint" in csMotionObj and "Point." in objName:
            isPlayer = "Link" in csMotionObj.parent.name
            legacyData = csMotionObj["zc_apoint"]
            csMotionObj.ootEmptyType = f"CS {'Player' if isPlayer else 'Actor'} Cue"

            if "start_frame" in legacyData:
                csMotionProp.actorCueProp.cueStartFrame = legacyData["start_frame"]
                del legacyData["start_frame"]

            if "action_id" in legacyData:
                playerEnum = ootData.enumData.enumByKey["csPlayerCueId"]
                item = None
                if isPlayer:
                    item = playerEnum.itemByIndex.get(int(legacyData["action_id"], base=16))

                if isPlayer and item is not None:
                    csMotionProp.actorCueProp.playerCueID = item.key
                else:
                    csMotionProp.actorCueProp.cueActionID = legacyData["action_id"]
                del legacyData["action_id"]

            del csMotionObj["zc_apoint"]

    if csMotionObj.type == "ARMATURE":
        camShotProp = csMotionObj.data.ootCamShotProp

        if "start_frame" in csMotionObj.data:
            camShotProp.shotStartFrame = csMotionObj.data["start_frame"]
            del csMotionObj.data["start_frame"]

        if "cam_mode" in csMotionObj.data:
            camShotProp.shotCamMode = ootEnumCSMotionCamMode[csMotionObj.data["cam_mode"]][0]
            del csMotionObj.data["cam_mode"]

        for bone in csMotionObj.data.bones:
            camShotPointProp = bone.ootCamShotPointProp

            if "frames" in bone:
                camShotPointProp.shotPointFrame = bone["frames"]
                del bone["frames"]

            if "fov" in bone:
                camShotPointProp.shotPointViewAngle = bone["fov"]
                del bone["fov"]

            if "camroll" in bone:
                camShotPointProp.shotPointRoll = bone["camroll"]
                del bone["camroll"]


#####################################
# Actors
#####################################
def upgradeActors(actorObj: Object):
    # parameters
    actorProp = None
    if actorObj.ootEmptyType == "Actor":
        actorProp = actorObj.ootActorProperty
    elif actorObj.ootEmptyType == "Transition Actor":
        actorProp = actorObj.ootTransitionActorProperty.actor
    elif actorObj.ootEmptyType == "Entrance":
        actorProp = actorObj.ootEntranceProperty.actor

    if actorProp is not None:
        isCustom = False
        if actorObj.ootEmptyType == "Entrance":
            isCustom = actorObj.ootEntranceProperty.customActor
        else:
            isCustom = actorProp.actorID == "Custom"

        if not isCustom:
            actorProp.params = actorProp.actorParam
            actorProp.actorParam = "0x0000"

            if actorObj.ootEmptyType == "Actor" and actorProp.rotOverride:
                actorProp.rotX = actorProp.rotOverrideX
                actorProp.rotY = actorProp.rotOverrideY
                actorProp.rotZ = actorProp.rotOverrideZ
                actorProp.rotOverrideX = "0x0000"
                actorProp.rotOverrideY = "0x0000"
                actorProp.rotOverrideZ = "0x0000"

    # room stuff
    if actorObj.ootEmptyType == "Entrance":
        entranceProp = actorObj.ootEntranceProperty

        for obj in bpy.data.objects:
            if obj.type == "EMPTY" and obj.ootEmptyType == "Room":
                if actorObj in obj.children_recursive:
                    entranceProp.tiedRoom = obj
                    break
    elif actorObj.ootEmptyType == "Transition Actor":
        # get room parent
        roomParent = None
        for obj in bpy.data.objects:
            if obj.type == "EMPTY" and obj.ootEmptyType == "Room" and actorObj in obj.children_recursive:
                roomParent = obj
                break

        # if it's ``None`` then this door actor is not parented to a room
        if roomParent is None:
            print("WARNING: Ignoring Door Actor not parented to a room")
            return

        transActorProp = actorObj.ootTransitionActorProperty
        if "dontTransition" in transActorProp or "roomIndex" in transActorProp:
            # look for old data since we don't want to overwrite newer existing data
            transActorProp.fromRoom = roomParent

        # upgrade old props if present
        if "dontTransition" in transActorProp:
            transActorProp.isRoomTransition = transActorProp["dontTransition"] == False
            del transActorProp["dontTransition"]

        if "roomIndex" in transActorProp:
            for obj in bpy.data.objects:
                if (
                    obj != transActorProp.fromRoom
                    and obj.type == "EMPTY"
                    and obj.ootEmptyType == "Room"
                    and obj.ootRoomHeader.roomIndex == transActorProp["roomIndex"]
                ):
                    transActorProp.toRoom = obj
                    del transActorProp["roomIndex"]
                    break
