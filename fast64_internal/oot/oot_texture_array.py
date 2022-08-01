from array import array
import bpy, os, re
from bpy.utils import register_class, unregister_class
from ..utility import hexOrDecInt
from .oot_model_classes import OOTF3DContext, OOTTextureFlipbook
from ..f3d.f3d_parser import getImportData

# Special cases:
# z_en_xc: one texture is not stored in any array.
def ootReadTextureArrays(basePath: str, overlayName: str, f3dContext: OOTF3DContext):

    # read actor data
    actorFilePath = os.path.join(basePath, f"src/overlays/actors/{overlayName}/z_{overlayName[4:].lower()}.c")
    actorFileDataPath = f"{actorFilePath[:-2]}_data.c"  # some bosses store texture arrays here
    actorData = getImportData([actorFileDataPath, actorFilePath])

    # search for texture arrays
    flipbookList = {}  # {array name : OOTTextureFlipbook}
    for texArrayMatch in re.finditer(
        r"void\s*\*\s*([0-9a-zA-Z\_]*)\s*\[\s*\]\s*=\s*\{(((?!\}).)*)\}", actorData, flags=re.DOTALL
    ):
        arrayName = texArrayMatch.group(1).strip()
        textureList = [item.strip() for item in texArrayMatch.group(2).split(",")]

        # handle trailing comma
        if textureList[-1] == "":
            textureList.pop()
        flipbookList[arrayName] = OOTTextureFlipbook(arrayName, "Array", textureList)

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

        for (arrayName, flipbook) in flipbookList.items():

            # check if array is directly referenced in gSPSegment
            directArrayReference = re.search(re.escape(arrayName) + r"\s*\[", segmentParam, flags=re.DOTALL)

            # check if an array element is referenced in gSPSegment
            indexIntoArrayReference = re.search(r"[a-zA-Z0-9\_]*", segmentParam, flags=re.DOTALL) and re.search(
                r"void\s*\*\s*" + re.escape(segmentParam) + r"\s*=\s*" + re.escape(arrayName) + r"\s*\[",
                actorData,
                flags=re.DOTALL,
            )

            if directArrayReference or indexIntoArrayReference:
                f3dContext.flipbooks[flipbookKey] = flipbook

        if flipbookKey not in f3dContext.flipbooks:
            # check if single non-array texture reference (ex. z_en_ta, which uses a different texture in z_demo_ec (red nose))
            singleTextureReference = (
                re.search(r"[a-zA-Z0-9\_]*", segmentParam, flags=re.DOTALL)
                and segmentParam[0] == "g"
                and segmentParam[1].isupper()
            )
            if singleTextureReference:
                # This is not technically correct (pointer to single element array instead of pointer to texture)
                # However, its only for getting the texture visual onto model
                f3dContext.flipbooks[flipbookKey] = OOTTextureFlipbook("", "Individual", [segmentParam])
