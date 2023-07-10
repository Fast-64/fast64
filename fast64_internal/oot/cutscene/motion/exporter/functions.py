import bpy

from bpy.types import Object
from .....utility import PluginError
from .classes import OOTCSMotionExport


def getCSMotionObjects(csName: str):
    csMotionObjects: dict[str, list[Object]] = {
        "Cutscene": [],
        "CS Actor Cue List": [],
        "CS Player Cue List": [],
        "camShot": [],
    }

    if csName is None:
        raise PluginError("ERROR: The cutscene name is None!")

    for obj in bpy.data.objects:
        isEmptyObj = obj.type == "EMPTY"
        parentCheck = obj.parent is not None and csName in obj.parent.name
        csObjCheck = isEmptyObj and obj.ootEmptyType == "Cutscene" and csName in obj.name
        if parentCheck or csObjCheck:
            if isEmptyObj and obj.ootEmptyType in csMotionObjects.keys():
                csMotionObjects[obj.ootEmptyType].append(obj)

            if obj.type == "ARMATURE" and obj.parent.ootEmptyType == "Cutscene":
                csMotionObjects["camShot"].append(obj)

    return csMotionObjects


def getCutsceneMotionData(csName: str, addBeginEndCmds: bool):
    return OOTCSMotionExport(
        getCSMotionObjects(csName),
        bpy.context.scene.fast64.oot.hackerFeaturesEnabled or bpy.context.scene.useDecompFeatures,
        addBeginEndCmds,
    )
