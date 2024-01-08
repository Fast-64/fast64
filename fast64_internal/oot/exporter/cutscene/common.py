import bpy

from dataclasses import dataclass
from bpy.types import Object
from typing import Optional
from ....utility import indent
from ...oot_constants import ootData
from ...cutscene.motion.utility import getBlenderPosition, getBlenderRotation, getInteger


@dataclass
class CutsceneCmdBase:
    """This class contains common Cutscene data"""

    params: list[str]

    startFrame: Optional[int] = None
    endFrame: Optional[int] = None

    def getEnumValue(self, enumKey: str, index: int, isSeqLegacy: bool = False):
        enum = ootData.enumData.enumByKey[enumKey]
        item = enum.itemById.get(self.params[index])
        if item is None:
            setting = getInteger(self.params[index])
            if isSeqLegacy:
                setting -= 1
            item = enum.itemByIndex.get(setting)
        return item.key if item is not None else self.params[index]

    def getGenericListCmd(self, cmdName: str, entryTotal: int):
        return indent * 2 + f"{cmdName}({entryTotal}),\n"

    def getCamListCmd(self, cmdName: str, startFrame: int, endFrame: int):
        return indent * 2 + f"{cmdName}({startFrame}, {endFrame}),\n"

    def getGenericSeqCmd(self, cmdName: str, type: str, startFrame: int, endFrame: int):
        return indent * 3 + f"{cmdName}({type}, {startFrame}, {endFrame}" + ", 0" * 8 + "),\n"


class CutsceneObjectFactory:
    """This class contains functions to create new Blender objects"""

    def getNewObject(self, name: str, data, selectObject: bool, parentObj: Object) -> Object:
        newObj = bpy.data.objects.new(name=name, object_data=data)
        bpy.context.view_layer.active_layer_collection.collection.objects.link(newObj)
        if selectObject:
            newObj.select_set(True)
            bpy.context.view_layer.objects.active = newObj
        newObj.parent = parentObj
        newObj.location = [0.0, 0.0, 0.0]
        newObj.rotation_euler = [0.0, 0.0, 0.0]
        newObj.scale = [1.0, 1.0, 1.0]
        return newObj

    def getNewEmptyObject(self, name: str, selectObject: bool, parentObj: Object):
        return self.getNewObject(name, None, selectObject, parentObj)

    def getNewArmatureObject(self, name: str, selectObject: bool, parentObj: Object):
        newArmatureData = bpy.data.armatures.new(name)
        newArmatureData.display_type = "STICK"
        newArmatureData.show_names = True
        newArmatureObject = self.getNewObject(name, newArmatureData, selectObject, parentObj)
        return newArmatureObject

    def getNewCutsceneObject(self, name: str, frameCount: int, parentObj: Object):
        newCSObj = self.getNewEmptyObject(name, True, parentObj)
        newCSObj.ootEmptyType = "Cutscene"
        newCSObj.ootCutsceneProperty.csEndFrame = frameCount
        return newCSObj

    def getNewActorCueListObject(self, name: str, commandType: str, parentObj: Object):
        newActorCueListObj = self.getNewEmptyObject(name, False, parentObj)
        newActorCueListObj.ootEmptyType = f"CS {'Player' if 'Player' in name else 'Actor'} Cue List"
        cmdEnum = ootData.enumData.enumByKey["csCmd"]

        if commandType == "Player":
            commandType = "player_cue"

        index = cmdEnum.itemByKey[commandType].index if commandType in cmdEnum.itemByKey else int(commandType, base=16)
        item = cmdEnum.itemByIndex.get(index)

        if item is not None:
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandType = item.key
        else:
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandType = "Custom"
            newActorCueListObj.ootCSMotionProperty.actorCueListProp.commandTypeCustom = commandType

        return newActorCueListObj

    def getNewActorCueObject(
        self,
        name: str,
        startFrame: int,
        actionID: int | str,
        location: list[int],
        rot: list[str],
        parentObj: Object,
    ):
        isDummy = "(D)" in name
        isPlayer = not isDummy and not "Actor" in name

        newActorCueObj = self.getNewEmptyObject(name, False, parentObj)
        newActorCueObj.location = getBlenderPosition(location, bpy.context.scene.ootBlenderScale)
        newActorCueObj.empty_display_type = "ARROWS"
        newActorCueObj.rotation_mode = "XZY"
        newActorCueObj.rotation_euler = getBlenderRotation(rot)
        emptyType = "Dummy" if isDummy else "Player" if isPlayer else "Actor"
        newActorCueObj.ootEmptyType = f"CS {emptyType} Cue"
        newActorCueObj.ootCSMotionProperty.actorCueProp.cueStartFrame = startFrame

        item = None
        if isPlayer:
            playerEnum = ootData.enumData.enumByKey["csPlayerCueId"]
            if isinstance(actionID, int):
                item = playerEnum.itemByIndex.get(actionID)
            else:
                item = playerEnum.itemByKey.get(actionID)

        if item is not None:
            newActorCueObj.ootCSMotionProperty.actorCueProp.playerCueID = item.key
        elif not isDummy:
            if isPlayer:
                newActorCueObj.ootCSMotionProperty.actorCueProp.playerCueID = "Custom"

            if isinstance(actionID, int):
                cueActionID = f"0x{actionID:04X}"
            else:
                cueActionID = actionID

            newActorCueObj.ootCSMotionProperty.actorCueProp.cueActionID = cueActionID

        return newActorCueObj

    def getNewCameraObject(
        self, name: str, displaySize: float, clipStart: float, clipEnd: float, alpha: float, parentObj: Object
    ):
        newCamera = bpy.data.cameras.new(name)
        newCameraObj = self.getNewObject(name, newCamera, False, parentObj)
        newCameraObj.data.display_size = displaySize
        newCameraObj.data.clip_start = clipStart
        newCameraObj.data.clip_end = clipEnd
        newCameraObj.data.passepartout_alpha = alpha
        return newCameraObj

    def getNewActorCuePreviewObject(self, name: str, selectObject, parentObj: Object):
        newPreviewObj = self.getNewEmptyObject(name, selectObject, parentObj)
        newPreviewObj.ootEmptyType = f"CS {'Actor' if 'Actor' in name else 'Player'} Cue Preview"
        return newPreviewObj
