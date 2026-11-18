import bpy

from bpy.types import Object

from ...utility import get_new_object
from ...game_data import game_data
from .motion.utility import getBlenderPosition, getBlenderRotation


class CutsceneObjectFactory:
    """This class contains functions to create new Blender objects"""

    def getNewEmptyObject(self, name: str, selectObject: bool, parentObj: Object):
        return get_new_object(name, None, selectObject, parent=parentObj)

    def getNewArmatureObject(self, name: str, selectObject: bool, parentObj: Object):
        newArmatureData = bpy.data.armatures.new(name)
        newArmatureData.display_type = "STICK"
        newArmatureData.show_names = True
        newArmatureObject = get_new_object(name, newArmatureData, selectObject, parent=parentObj)
        return newArmatureObject

    def getNewCutsceneObject(self, name: str, frameCount: int, parentObj: Object):
        newCSObj = self.getNewEmptyObject(name, True, parentObj)
        newCSObj.ootEmptyType = "Cutscene"
        newCSObj.ootCutsceneProperty.csEndFrame = frameCount
        return newCSObj

    def getNewActorCueListObject(self, name: str, commandType: str, parentObj: Object):
        newActorCueListObj = self.getNewEmptyObject(name, False, parentObj)
        newActorCueListObj.ootEmptyType = f"CS {'Player' if 'Player' in name else 'Actor'} Cue List"
        cmdEnum = game_data.z64.enums.enumByKey["cs_cmd"]

        if commandType == "Player":
            commandType = "player_cue"

        index = (
            cmdEnum.item_by_key[commandType].index if commandType in cmdEnum.item_by_key else int(commandType, base=16)
        )
        item = cmdEnum.item_by_index.get(index)

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
            playerEnum = game_data.z64.enums.enumByKey["cs_player_cue_id"]
            if isinstance(actionID, int):
                item = playerEnum.item_by_index.get(actionID)
            else:
                item = playerEnum.item_by_key.get(actionID)

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
        newCameraObj = get_new_object(name, newCamera, False, parent=parentObj)
        newCameraObj.data.display_size = displaySize
        newCameraObj.data.clip_start = clipStart
        newCameraObj.data.clip_end = clipEnd
        newCameraObj.data.passepartout_alpha = alpha
        return newCameraObj

    def getNewActorCuePreviewObject(self, name: str, selectObject, parentObj: Object):
        newPreviewObj = self.getNewEmptyObject(name, selectObject, parentObj)
        newPreviewObj.ootEmptyType = f"CS {'Actor' if 'Actor' in name else 'Player'} Cue Preview"
        return newPreviewObj
