from .classes import OOTCutsceneMotionImport


def ImportCFile(context, filename):
    im = OOTCutsceneMotionImport(context)
    return im.ImportCFile(filename)
