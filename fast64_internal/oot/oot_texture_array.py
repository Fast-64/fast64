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

    # read any /asset includes
    # includes = []
    # for includesMatch in re.finditer(r"\#include\s*\"(assets\/objects\/(((?!\").)*))\"", actorData, flags=re.DOTALL):
    #     includes.append(os.path.join(basePath, includesMatch.group(1)))

    # assetData = getImportData(includes)

    # search for texture arrays
    for texArrayMatch in re.finditer(
        r"void\s*\*\s*([0-9a-zA-Z\_]*)\s*\[\s*\]\s*=\s*\{(((?!\}).)*)\}", actorData, flags=re.DOTALL
    ):
        arrayName = texArrayMatch.group(1)
        textureList = [item.strip() for item in texArrayMatch.group(2).split(",")]

        # handle trailing comma
        if textureList[-1] == "":
            textureList.pop()

        # find gSPSegment() calls that reference texture arrays
        for spSegmentMatch in re.finditer(
            r"gSPSegment\s*\(\s*POLY\_(OPA)?(XLU)?\_DISP\s*\+\+\s*,\s*([0-9a-fA-Fx]*)\s*,\s*SEGMENTED\_TO\_VIRTUAL\s*\(\s*(((?!;).)*)\)\s*\)\s*;",
            actorData,
            flags=re.DOTALL,
        ):
            if arrayName in spSegmentMatch.group(4):  # very basic detection, need to improve

                # see ootEnumDrawLayers
                drawLayer = "Transparent" if spSegmentMatch.group(2) else "Opaque"
                segment = hexOrDecInt(spSegmentMatch.group(3))
                flipbookKey = (segment, drawLayer)
                f3dContext.flipbooks[flipbookKey] = OOTTextureFlipbook(arrayName, textureList)
