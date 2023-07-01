from bpy.types import Context
from .classes import OOTCutsceneMotionImport


def importCutsceneMotion(context: Context, filename: str):
    importData = OOTCutsceneMotionImport(context)
    return importData.importFromC(filename)
