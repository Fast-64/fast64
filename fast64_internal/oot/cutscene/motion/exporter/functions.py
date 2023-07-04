from bpy.types import Context
from .classes import OOTCutsceneMotionExport
from .to_c import getCutsceneMotionData


def exportCutsceneMotion(context: Context, filename: str, use_floats: bool, use_cscmd: bool):
    exportData = OOTCutsceneMotionExport(context, use_floats, use_cscmd)
    return exportData.exportToC(filename)
