from bpy.types import Context
from .classes import OOTCutsceneMotionExport


def exportCutsceneMotion(context: Context, filename: str, use_floats: bool, use_cscmd: bool):
    exportData = OOTCutsceneMotionExport(context, use_floats, use_cscmd)
    return exportData.exportToC(filename)
