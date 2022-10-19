from .....utility import CData
from ....oot_level_classes import OOTScene
from ....oot_cutscene import ootCutsceneDataToC


def getCutsceneIncludes(fileName: str):
    includeData = CData()

    includeFiles = [
        "ultra64.h",
        "z64.h",
        "macros.h",
        "command_macros_base.h",
        "z64cutscene_commands.h",
        f"{fileName}",
    ]

    includeData.source = "\n".join([f'#include "{include}"' for include in includeFiles]) + "\n\n"
    return includeData


def convertCutsceneToC(outScene: OOTScene):
    """Returns the cutscene data"""
    csData: list[CData] = []
    sceneLayers: list[OOTScene] = [
        outScene,
        outScene.childNightHeader,
        outScene.adultDayHeader,
        outScene.adultNightHeader,
    ]
    sceneLayers.extend(outScene.cutsceneHeaders)

    for i, layer in enumerate(sceneLayers):
        if layer is not None and layer.writeCutscene:
            data = CData()
            if layer.csWriteType == "Embedded":
                data = ootCutsceneDataToC(layer, layer.getCutsceneDataName(i))
            elif layer.csWriteType == "Object":
                data = ootCutsceneDataToC(layer.csWriteObject, layer.csWriteObject.name)
            csData.append(data)

    for extraCs in outScene.extraCutscenes:
        csData.append(ootCutsceneDataToC(extraCs, extraCs.name))

    return csData
