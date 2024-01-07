import bpy

from .....utility import CData
from ....oot_level_classes import OOTScene
from ....cutscene.exporter import getNewCutsceneExport


def getCutsceneC(csName: str):
    csData = CData()
    declarationBase = f"CutsceneData {csName}[]"

    # .h
    csData.header = f"extern {declarationBase};\n"

    # .c
    csData.source = (
        declarationBase
        + " = {\n"
        + getNewCutsceneExport(csName, bpy.context.scene.exportMotionOnly).getExportData()
        + "};\n\n"
    )

    return csData


def getSceneCutscenes(outScene: OOTScene):
    cutscenes: list[CData] = []
    altHeaders: list[OOTScene] = [
        outScene,
        outScene.childNightHeader,
        outScene.adultDayHeader,
        outScene.adultNightHeader,
    ]
    altHeaders.extend(outScene.cutsceneHeaders)
    csObjects = []

    for curHeader in altHeaders:
        # curHeader is either None or an OOTScene. This can either be the main scene itself,
        # or one of the alternate / cutscene headers.
        if curHeader is not None and curHeader.writeCutscene:
            if curHeader.csWriteType == "Object" and curHeader.csName not in csObjects:
                cutscenes.append(getCutsceneC(curHeader.csName))
                csObjects.append(curHeader.csName)

    for csObj in outScene.extraCutscenes:
        name = csObj.name.removeprefix("Cutscene.")
        if not name in csObjects:
            cutscenes.append(getCutsceneC(name))
            csObjects.append(name)

    return cutscenes
