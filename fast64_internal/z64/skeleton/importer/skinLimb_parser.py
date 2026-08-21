import re
from mathutils import Vector
from ....utility import hexOrDecInt, PluginError, get_include_data
from ...model_classes import SkinAnimatedLimbData, OOTVert, VertexTransform, VertexWeight
from ...animation.importer.functions import ootGetAnimationData, ootGetAnimRawTranslation, ootGetAnimRawRotation


def getSkinLimbRestPose(
    filepath: str, importData: str, isCustomImport: bool, actorScale: float
) -> list[tuple[float, float, float]]:
    animName = re.search(r"AnimationHeader (.*?IdleAnim)", importData).group(1)
    frameData, jointIndices, staticIndexMax, _ = ootGetAnimationData(filepath, importData, animName, isCustomImport)

    restPoseData: list[tuple[float, float, float]] = [
        tuple(ootGetAnimRawTranslation(0, staticIndexMax, frameData, jointIndices[0], actorScale))
    ]
    for jointIndex in jointIndices[1:]:
        restPoseData.append(tuple(ootGetAnimRawRotation(0, staticIndexMax, frameData, jointIndex, actorScale)))

    return restPoseData


def parseSkinVertex(includeData: str, skinVertexName: str, vertexData: list[OOTVert]):
    pattern = r"SkinVertex\s+?" + re.escape(skinVertexName) + r"\[\]\s+=\s+?{\s*?(.*?)};"
    skinVertexData = re.search(pattern, includeData, re.DOTALL)

    if skinVertexData is None:
        raise PluginError("Cannot find SkinVertex named: " + skinVertexName)
    data = skinVertexData.group(1).replace("\n", "").replace(" ", "")
    if "#include" in data:
        data = get_include_data(skinVertexData.group(1), strip=True)

    verts: list[OOTVert] = []
    for skinVert in re.finditer(r"{(.*?)}", data, re.DOTALL):
        values = skinVert.group(1).split(",")
        index = hexOrDecInt(values[0])
        vert = vertexData[index]
        uv = Vector((hexOrDecInt(values[1]), hexOrDecInt(values[2])))
        normal = Vector((hexOrDecInt(values[3]), hexOrDecInt(values[4]), hexOrDecInt(values[5])))
        alpha = hexOrDecInt(values[6])
        vert.uv = uv
        # store normal in rgb to match how Vtx are imported
        vert.rgb = normal
        vert.alpha = alpha
        vert.skinVert = True
        verts.append(vert)

    return verts


def parseSkinTransformation(
    includeData: str, skinTransformName: str
) -> tuple[list[VertexTransform], list[VertexWeight[int]]]:
    pattern = r"SkinTransformation\s+?" + re.escape(skinTransformName) + r"\[\]\s+=\s+?{\s*?(.*?)};"
    skinTransformData = re.search(pattern, includeData, re.DOTALL)

    if skinTransformData is None:
        raise PluginError("Cannot find SkinTransformation named: " + skinTransformName)

    data = skinTransformData.group(1).replace("\n", "").replace(" ", "")
    if "#include" in data:
        data = get_include_data(skinTransformData.group(1), strip=True)
    transforms: list[VertexTransform] = []
    weights: list[VertexWeight[int]] = []

    for transform in re.finditer("{(.*?)}", data):
        values = transform.group(1).split(",")
        limbIndex = hexOrDecInt(values[0])
        pos = Vector((hexOrDecInt(values[1]), hexOrDecInt(values[2]), hexOrDecInt(values[3])))
        scale = hexOrDecInt(values[4]) * 0.01

        transforms.append(VertexTransform(limbIndex, pos, scale))
        weights.append(VertexWeight(limbIndex, scale))

    return transforms, weights


def parseSkinLimbModifs(includeData: str, modifName: str, vertexData: list[OOTVert]) -> None:
    pattern = r"SkinLimbModif\s+?" + re.escape(modifName) + r"\[\]\s+=\s+?{\s*?(.*?)};"
    verts: list[OOTVert] = []
    modifData = re.search(pattern, includeData, re.DOTALL)

    if modifData is None:
        raise PluginError("Cannot find SkinLimbModif named: " + modifName)

    data = modifData.group(1).replace("\n", "").replace(" ", "")
    if "#include" in data:
        data = get_include_data(modifData.group(1), strip=True)

    for modif in re.finditer(r"{(.*?)}", data, re.DOTALL):
        values = modif.group(1).split(",")
        limbTransformations, groups = parseSkinTransformation(includeData, values[4])
        verts = parseSkinVertex(includeData, values[3], vertexData)

        for vert in verts:
            vert.transforms = limbTransformations


def parseSkinAnimatedLimbData(includeData: str, dataName: str) -> SkinAnimatedLimbData:
    pattern = r"SkinAnimatedLimbData\s*?" + re.escape(dataName[1:]) + r"\s*?=\s*?{\s*?(.*?)};"

    animatedLimbText = re.search(pattern, includeData, re.DOTALL)

    if animatedLimbText is None:
        raise PluginError(f"Cannot find SkinAnimatedLimbData named: {dataName}")

    if "#include" in animatedLimbText.group(0):
        data = get_include_data(animatedLimbText.group(1), strip=True)
    else:
        data = animatedLimbText.group(1)

    data = data.replace("\n", "").replace(" ", "").split(",")

    totalVtxCount = int(data[0])
    vertexData = [
        OOTVert(Vector([0, 0, 0]), Vector([0, 0]), Vector([0, 0, 0]), Vector([0, 0, 0]), 0)
        for _ in range(totalVtxCount)
    ]

    parseSkinLimbModifs(includeData, data[2], vertexData)

    skinAnimatedLimbData = SkinAnimatedLimbData(data[3], vertexData)

    return skinAnimatedLimbData
