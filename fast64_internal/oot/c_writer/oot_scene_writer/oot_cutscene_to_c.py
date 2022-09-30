from ....utility import CData
from ...oot_level_classes import OOTScene
from ...oot_cutscene import ootCutsceneDataToC


def ootSceneCutscenesToC(scene: OOTScene):
    """Returns the cutscene data"""
    csData: list[CData] = []
    sceneLayers = [scene, scene.childNightHeader, scene.adultDayHeader, scene.adultNightHeader]
    sceneLayers.extend(scene.cutsceneHeaders)

    for i, layer in enumerate(sceneLayers):
        if layer is not None and layer.writeCutscene:
            data = CData()
            if layer.csWriteType == "Embedded":
                data = ootCutsceneDataToC(scene, scene.cutsceneDataName(i))
            elif layer.csWriteType == "Object":
                data = ootCutsceneDataToC(scene.csWriteObject, scene.csWriteObject.name)
            csData.append(data)

    for extraCs in scene.extraCutscenes:
        csData.append(ootCutsceneDataToC(extraCs, extraCs.name))

    return csData
