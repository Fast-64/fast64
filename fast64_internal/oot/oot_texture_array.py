import os, re
from typing import Callable
from ..utility import hexOrDecInt

from .oot_model_classes import (
    OOTF3DContext,
    TextureFlipbook,
    ootGetActorData,
    ootGetActorDataPaths,
    ootGetIncludedAssetData,
    ootGetLinkData,
)

# Special cases:
# z_en_xc: one texture is not stored in any array.
# skeletonName only used for en_ossan (shopkeepers) and demo_ec (end credits party), which have multiple skeletons
def ootReadTextureArrays(
    basePath: str,
    overlayName: str,
    skeletonName: str,
    f3dContext: OOTF3DContext,
    isLink: bool,
    flipbookArrayIndex2D: int,
):
    if not isLink:
        actorData = ootGetActorData(basePath, overlayName)
        currentPaths = ootGetActorDataPaths(basePath, overlayName)
    else:
        actorData = ootGetLinkData(basePath)
        currentPaths = [os.path.join(basePath, f"src/code/z_player_lib.c")]
    actorData = ootGetIncludedAssetData(basePath, currentPaths, actorData) + actorData

    # search for texture arrays
    # this is done first so that its easier to tell which gSPSegment calls refer to texture data.
    flipbookList = getTextureArrays(actorData, flipbookArrayIndex2D)

    if not isLink and overlayName == "ovl_En_Ossan":
        # remove function declarations
        actorData = re.sub(r"void\s*EnOssan\_(((?!\{).)*)?\)\s*;", "", actorData)
        ootReadTextureArraysFromMultiple(
            flipbookList, skeletonName, actorData, f3dContext, "EnOssan", getSPSegmentCalls, flipbookArrayIndex2D
        )
    elif not isLink and overlayName == "ovl_Demo_Ec":
        ootReadTextureArraysFromMultiple(
            flipbookList, skeletonName, actorData, f3dContext, "DemoEc", getSPSegmentCallsDemoEc, flipbookArrayIndex2D
        )
    else:
        ootReadTextureArraysGeneric(flipbookList, actorData, getSPSegmentCalls, f3dContext)


# we return when no matches found to handle cases where actor does not have dynamic textures.
def ootReadTextureArraysFromMultiple(
    flipbookList: dict[str, TextureFlipbook],
    skeletonName: str,
    actorData: str,
    f3dContext: OOTF3DContext,
    functionPrefix: str,
    getSegmentCallsFunc: Callable[[str], None],
    flipbookArrayIndex2D: int,
):
    # regex should ignore DemoEc_Init()
    # relies on formatting convention (tabs indicating bracket scope)
    initMatch = re.search(
        r"void\s*"
        + re.escape(functionPrefix)
        + r"\_Init(?!SkelAnime)(((?![\s\(]).)*?)\((((?!\n\}).)*?)"
        + re.escape(skeletonName),
        actorData,
        flags=re.DOTALL,
    )
    if not initMatch:
        return

    # relies on formatting convention (tabs indicating scope of bracket)
    name = initMatch.group(1)
    drawMatch = re.search(
        r"void\s*" + re.escape(functionPrefix) + r"\_Draw" + re.escape(name) + r"\s*\((.*?)\n\}",
        actorData,
        flags=re.DOTALL,
    )
    if not drawMatch:
        return

    drawData = drawMatch.group(1)
    flipbookList = getTextureArrays(drawData, flipbookArrayIndex2D)
    ootReadTextureArraysGeneric(flipbookList, drawData, getSegmentCallsFunc, f3dContext)


def ootReadTextureArraysGeneric(
    flipbookList: dict[str, TextureFlipbook],
    actorData: str,
    getSegmentCallsFunc: Callable[[str], None],
    f3dContext: OOTF3DContext,
):
    # find gSPSegment() calls that reference texture arrays
    for (flipbookKey, segmentParam, spSegmentMatch) in getSegmentCallsFunc(actorData):

        # check for texture array reference
        for (arrayName, flipbook) in flipbookList.items():
            directArrayReference = findDirectArrayReference(arrayName, segmentParam)
            indexIntoArrayReference = findIndexIntoArrayReference(arrayName, segmentParam, actorData)

            if directArrayReference or indexIntoArrayReference:
                f3dContext.flipbooks[flipbookKey] = flipbook

        # check if single non-array texture reference (ex. z_en_ta, which uses a different texture in z_demo_ec (red nose))
        # This is will not get correct texture name, but otherwise works fine.
        if flipbookKey not in f3dContext.flipbooks and findSingleTextureReference(segmentParam):
            f3dContext.flipbooks[flipbookKey] = TextureFlipbook("", "Individual", [segmentParam])


# check if array is directly referenced in gSPSegment
# SEGMENTED_TO_VIRTUAL(arrayName[...])
def findDirectArrayReference(arrayName: str, segmentParam: str) -> re.Match:
    return re.search(re.escape(arrayName) + r"\s*\[", segmentParam, flags=re.DOTALL)


# check if an array element is referenced in gSPSegment
# void* segmentParam = arrayName[...];
# SEGMENTED_TO_VIRTUAL(segmentParam)
def findIndexIntoArrayReference(arrayName: str, segmentParam: str, actorData: str) -> re.Match:
    return re.search(r"[a-zA-Z0-9\_]*", segmentParam, flags=re.DOTALL) and re.search(
        r"void\s*\*\s*" + re.escape(segmentParam) + r"\s*=\s*" + re.escape(arrayName) + r"\s*\[",
        actorData,
        flags=re.DOTALL,
    )


# check for single non-array reference
# convention: camel case starting with 'g'
# gSomeTexture
def findSingleTextureReference(segmentParam: str) -> re.Match:
    return (
        re.search(r"[a-zA-Z0-9\_]*", segmentParam, flags=re.DOTALL)
        and segmentParam[0] == "g"
        and segmentParam[1].isupper()
    )


# check for texture arrays in data.
# void* ???[] = {a, b, c,}
def getTextureArrays(actorData: str, flipbookArrayIndex2D: int) -> dict[str, TextureFlipbook]:
    flipbookList = {}  # {array name : TextureFlipbook}

    if flipbookArrayIndex2D is not None:
        for texArray2DMatch in re.finditer(
            r"void\s*\*\s*([0-9a-zA-Z\_]*)\s*\[\s*\]\s*\[[0-9a-fA-Fx]*\]\s*=\s*\{(.*?)\}\s*;",
            actorData,
            flags=re.DOTALL,
        ):
            arrayMatchData = [
                arrayMatch.group(1)
                for arrayMatch in re.finditer(r"\{(((?!\}).)*)\}", texArray2DMatch.group(2), flags=re.DOTALL)
            ]

            if flipbookArrayIndex2D >= len(arrayMatchData):
                continue

            arrayName = texArray2DMatch.group(1).strip()
            textureList = stripComments([item for item in arrayMatchData[flipbookArrayIndex2D].split(",")])

            # handle trailing comma
            if textureList[-1] == "":
                textureList.pop()
            flipbookList[arrayName] = TextureFlipbook(arrayName, "Array", textureList)
    else:
        for texArrayMatch in re.finditer(
            r"void\s*\*\s*([0-9a-zA-Z\_]*)\s*\[\s*\]\s*=\s*\{(((?!\}).)*)\}", actorData, flags=re.DOTALL
        ):
            arrayName = texArrayMatch.group(1).strip()
            textureList = stripComments([item for item in texArrayMatch.group(2).split(",")])

            # handle trailing comma
            if textureList[-1] == "":
                textureList.pop()
            flipbookList[arrayName] = TextureFlipbook(arrayName, "Array", textureList)

    return flipbookList


def stripComments(textureNameList: list[str]) -> list[str]:
    for i in range(len(textureNameList)):
        try:
            commentIndex = textureNameList[i].index("//")
        except ValueError:
            textureNameList[i] = textureNameList[i].strip()
        else:
            textureNameList[i] = re.sub(r"//.*?\n", "", textureNameList[i]).strip()
    return textureNameList


def getSPSegmentCalls(actorData: str) -> list[tuple[tuple[int, str], str, re.Match]]:
    segmentCalls = []

    # find gSPSegment() calls that reference texture arrays
    for spSegmentMatch in re.finditer(
        r"gSPSegment\s*\(\s*POLY\_(OPA)?(XLU)?\_DISP\s*\+\+\s*,\s*([0-9a-fA-Fx]*)\s*,\s*SEGMENTED\_TO\_VIRTUAL\s*\(\s*(((?!;).)*)\)\s*\)\s*;",
        actorData,
        flags=re.DOTALL,
    ):
        # see ootEnumDrawLayers
        drawLayer = "Transparent" if spSegmentMatch.group(2) else "Opaque"
        segment = hexOrDecInt(spSegmentMatch.group(3))
        flipbookKey = (segment, drawLayer)
        segmentParam = spSegmentMatch.group(4).strip()

        segmentCalls.append((flipbookKey, segmentParam, spSegmentMatch))

    return segmentCalls


# assumes DemoEc_DrawSkeleton()/DemoEc_DrawSkeletonCustomColor() is unmodified
def getSPSegmentCallsDemoEc(actorData: str) -> list[tuple[tuple[int, str], str, re.Match]]:
    segmentCalls = getSPSegmentCalls(actorData)
    functionMatch = re.search(r"DemoEc_DrawSkeleton(CustomColor)?\s*\(.*?,.*?,(.*?),(.*?),", actorData, flags=re.DOTALL)
    if functionMatch:
        isCustomColor = functionMatch.group(1) is not None
        param1 = functionMatch.group(2).strip()
        param2 = functionMatch.group(3).strip()

        if param1 == "NULL" or param1 == "0":
            param1 = None
        if param2 == "NULL" or param2 == "0":
            param2 = None

        if isCustomColor:
            if param1:
                segmentCalls.append(((0x0A, "Opaque"), param1, functionMatch))
            if param2:
                segmentCalls.append(((0x0B, "Opaque"), param2, functionMatch))
        else:
            if param1:
                segmentCalls.append(((0x08, "Opaque"), param1, functionMatch))
                if not param2:
                    segmentCalls.append(((0x09, "Opaque"), param1, functionMatch))
            if param2:
                segmentCalls.append(((0x09, "Opaque"), param2, functionMatch))

    return segmentCalls
