from .classes import OOTCutsceneMotionExport


def ExportCFile(context, filename, use_floats, use_tabs, use_cscmd):
    ex = OOTCutsceneMotionExport(context, use_floats, use_tabs, use_cscmd)
    return ex.ExportCFile(filename)
