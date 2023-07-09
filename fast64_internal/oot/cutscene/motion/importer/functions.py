import bpy

from .classes import OOTCSMotionImport


def importCutsceneData(filePath: str, sceneData: str):
    csMotionImport = OOTCSMotionImport(filePath, sceneData)
    return csMotionImport.setCutsceneData(bpy.context.scene.ootCSNumber)
