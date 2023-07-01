from bpy.types import Context
from .classes import OOTCutsceneMotionExport


def ExportCFile(context: Context, filename: str, use_floats: bool, use_tabs: bool, use_cscmd: bool):
    ex = OOTCutsceneMotionExport(context, use_floats, use_tabs, use_cscmd)
    return ex.ExportCFile(filename)
