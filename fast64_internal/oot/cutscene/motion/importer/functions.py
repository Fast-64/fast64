import bpy

from .classes import OOTCSMotionImport


def importCutsceneData(filePath: str):
    csMotionImport = OOTCSMotionImport(filePath)
    return csMotionImport.setCutsceneData(bpy.context.scene.ootCSNumber)
