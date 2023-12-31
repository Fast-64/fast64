import bpy

from bpy.types import Object
from ....utility import PluginError
from .classes import CutsceneExport


def getCutsceneObjects(csName: str):
    """Returns the object list containing every object from the cutscene to export"""

    csObjects: dict[str, list[Object]] = {
        "Cutscene": [],
        "CS Actor Cue List": [],
        "CS Player Cue List": [],
        "camShot": [],
    }

    if csName is None:
        raise PluginError("ERROR: The cutscene name is None!")

    for obj in bpy.data.objects:
        isEmptyObj = obj.type == "EMPTY"

        # look for the cutscene object based on the cutscene name
        parentCheck = obj.parent is not None and obj.parent.name == f"Cutscene.{csName}"
        csObjCheck = isEmptyObj and obj.ootEmptyType == "Cutscene" and obj.name == f"Cutscene.{csName}"
        if parentCheck or csObjCheck:
            # add the relevant objects based on the empty type or if it's an armature
            if isEmptyObj and obj.ootEmptyType in csObjects.keys():
                csObjects[obj.ootEmptyType].append(obj)

            if obj.type == "ARMATURE" and obj.parent.ootEmptyType == "Cutscene":
                csObjects["camShot"].append(obj)

    if len(csObjects["Cutscene"]) != 1:
        raise PluginError(f"ERROR: Expected 1 Cutscene Object, found {len(csObjects['Cutscene'])} ({csName}).")

    return csObjects


def getNewCutsceneExport(csName: str, motionOnly: bool):
    """Returns the initialised cutscene exporter"""

    # this allows us to change the exporter's variables to get what we need
    return CutsceneExport(
        getCutsceneObjects(csName),
        bpy.context.scene.fast64.oot.hackerFeaturesEnabled or bpy.context.scene.useDecompFeatures,
        motionOnly,
    )
