from .classes import OOTCutsceneMotionImport


def importCutsceneMotion(context, filename):
    im = OOTCutsceneMotionImport(context)
    return im.importCutsceneMotion(filename)
