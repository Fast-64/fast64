from bpy.types import Context
from .classes import OOTCutsceneMotionImport


def importCutsceneMotion(context: Context, filename: str):
    im = OOTCutsceneMotionImport(context)
    return im.importCutsceneMotion(filename)
