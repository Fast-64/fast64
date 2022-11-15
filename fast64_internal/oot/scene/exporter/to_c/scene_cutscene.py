from ....oot_cutscene import ootCutsceneDataToC


# scene is either None or an OOTScene. This can either be the main scene itself,
# or one of the alternate / cutscene headers.
def ootGetCutsceneC(scene, headerIndex):
    if scene is not None and scene.writeCutscene:
        if scene.csWriteType == "Embedded":
            return [ootCutsceneDataToC(scene, scene.cutsceneDataName(headerIndex))]
        elif scene.csWriteType == "Object":
            return [ootCutsceneDataToC(scene.csWriteObject, scene.csWriteObject.name)]
    return []


def ootSceneCutscenesToC(scene):
    sceneCutscenes = ootGetCutsceneC(scene, 0)
    sceneCutscenes.extend(ootGetCutsceneC(scene.childNightHeader, 1))
    sceneCutscenes.extend(ootGetCutsceneC(scene.adultDayHeader, 2))
    sceneCutscenes.extend(ootGetCutsceneC(scene.adultNightHeader, 3))

    for i in range(len(scene.cutsceneHeaders)):
        sceneCutscenes.extend(ootGetCutsceneC(scene.cutsceneHeaders[i], i + 4))
    for ec in scene.extraCutscenes:
        sceneCutscenes.append(ootCutsceneDataToC(ec, ec.name))

    return sceneCutscenes
