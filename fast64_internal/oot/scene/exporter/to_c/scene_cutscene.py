from .....utility import CData
from ....oot_cutscene import ootCutsceneDataToC
from ....oot_level_classes import OOTScene


def getSceneCutscenes(outScene: OOTScene):
    cutscenes: list[CData] = []
    altHeaders = [outScene, outScene.childNightHeader, outScene.adultDayHeader, outScene.adultNightHeader]
    altHeaders.extend(outScene.cutsceneHeaders)

    for i, curHeader in enumerate(altHeaders):
        # curHeader is either None or an OOTScene. This can either be the main scene itself,
        # or one of the alternate / cutscene headers.
        if curHeader is not None and curHeader.writeCutscene:
            if curHeader.csWriteType == "Embedded":
                cutscenes.append(ootCutsceneDataToC(curHeader, curHeader.cutsceneDataName(i)))
            elif curHeader.csWriteType == "Object":
                cutscenes.append(ootCutsceneDataToC(curHeader.csWriteObject, curHeader.csWriteObject.name))

    for extraCs in outScene.extraCutscenes:
        cutscenes.append(ootCutsceneDataToC(extraCs, extraCs.name))

    return cutscenes
