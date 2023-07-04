import bpy

from bpy.types import Object
from .classes import OOTCSMotionExport


def getCSMotionObjects():
    csMotionObjects: dict[str, list[Object]] = {
        "Cutscene": [],
        "CS Actor Cue List": [],
        "CS Player Cue List": [],
        "CS Actor Cue": [],
        "CS Player Cue": [],
        "camShot": [],
    }

    for obj in bpy.data.objects:
        if obj.type == "EMPTY" and obj.ootEmptyType in csMotionObjects.keys():
            csMotionObjects[obj.ootEmptyType].append(obj)

        if obj.type == "ARMATURE" and obj.parent.ootEmptyType == "Cutscene":
            csMotionObjects["camShot"].append(obj)

    return csMotionObjects


def getCutsceneMotionData():
    csMotionExport = OOTCSMotionExport(
        getCSMotionObjects(), bpy.context.scene.fast64.oot.hackerFeaturesEnabled or bpy.context.scene.useDecompFeatures
    )

    return csMotionExport.getExportData()
