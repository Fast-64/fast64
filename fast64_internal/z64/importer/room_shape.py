import os
import re
import bpy
import mathutils

from ...utility import parentObject, hexOrDecInt, yUpToZUp
from ...f3d.f3d_parser import importMeshC
from ..model_classes import OOTF3DContext
from ..room.properties import OOTRoomHeaderProperty
from ..constants import ootEnumRoomShapeType
from .classes import SharedSceneData
from .utility import getDataMatch, stripName


def parseMeshHeader(
    roomObj: bpy.types.Object,
    sceneData: str,
    meshHeaderName: str,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
):
    roomHeader = roomObj.ootRoomHeader
    meshData = getDataMatch(sceneData, meshHeaderName, "", "mesh header", False, strip=True)
    meshData = meshData.replace("{", "").replace("}", "")

    meshParams = [value.strip() for value in meshData.split(",") if value.strip() != ""]
    roomShape = meshParams[0]
    if "ROOM_SHAPE_TYPE_" in roomShape:
        roomShapeIndex = [value[0] for value in ootEnumRoomShapeType].index(roomShape)
    else:
        roomShapeIndex = int(roomShape)

    roomHeader.roomShape = ootEnumRoomShapeType[roomShapeIndex][0]
    isType1 = roomShapeIndex == 1
    isMulti = meshParams[1] == "2" or meshParams[1] == "ROOM_SHAPE_IMAGE_AMOUNT_MULTI"

    meshListName = stripName(meshParams[2])
    parseMeshList(roomObj, sceneData, meshListName, roomShapeIndex, f3dContext, sharedSceneData)

    if isType1:
        if not isMulti:
            parseBGImage(roomHeader, meshParams, sharedSceneData)
        else:
            bgListName = stripName(f"{meshParams[4]}")
            parseBGImageList(roomHeader, sceneData, bgListName, sharedSceneData)


def parseBGImage(roomHeader: OOTRoomHeaderProperty, params: list[str], sharedSceneData: SharedSceneData):
    bgImage = roomHeader.bgImageList.add()
    bgImage.otherModeFlags = params[10]
    bgName = f"{params[3]}.jpg"
    image = bpy.data.images.load(os.path.join(bpy.path.abspath(sharedSceneData.scenePath), f"{bgName}"))
    bgImage.image = image


def parseBGImageList(
    roomHeader: OOTRoomHeaderProperty, sceneData: str, bgListName: str, sharedSceneData: SharedSceneData
):
    bgData = getDataMatch(sceneData, bgListName, "", "bg list")
    bgList = [value.replace("{", "").strip() for value in bgData.split("},") if value.strip() != ""]
    for bgDataItem in bgList:
        params = [value.strip() for value in bgDataItem.split(",") if value.strip() != ""]
        bgImage = roomHeader.bgImageList.add()
        # Assuming camera index increments appropriately
        # bgImage.camera = hexOrDecInt(params[1])
        bgImage.otherModeFlags = params[9]

        bgName = params[2]
        image = bpy.data.images.load(os.path.join(bpy.path.abspath(sharedSceneData.scenePath), f"{bgName}.jpg"))
        bgImage.image = image


def parseMeshList(
    roomObj: bpy.types.Object,
    sceneData: str,
    meshListName: str,
    roomShape: int,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
):
    roomHeader = roomObj.ootRoomHeader
    meshEntryData = getDataMatch(sceneData, meshListName, "", "mesh list", roomShape != 1, strip=True)

    if roomShape == 2:
        matchPattern = r"\{\s*\{(.*?),(.*?),(.*?)\}\s*,(.*?),(.*?),(.*?),?\}\s*,?"
        searchItems = re.finditer(matchPattern, meshEntryData, flags=re.DOTALL)
    elif roomShape == 1:
        searchItems = [meshEntryData]
    else:
        matchPattern = r"\{(.*?),(.*?),?\}\s*,?"
        searchItems = re.finditer(matchPattern, meshEntryData, flags=re.DOTALL)

    for entryMatch in searchItems:
        if roomShape == 2:
            opaqueDL = entryMatch.group(5).strip()
            transparentDL = entryMatch.group(6).strip()
            position = yUpToZUp @ mathutils.Vector(
                [
                    hexOrDecInt(entryMatch.group(value).strip().removesuffix(",")) / bpy.context.scene.ootBlenderScale
                    for value in range(1, 4)
                ]
            )
            if sharedSceneData.includeCullGroups:
                cullObj = bpy.data.objects.new("Cull Group", None)
                bpy.context.scene.collection.objects.link(cullObj)
                cullObj.location = position
                cullObj.ootEmptyType = "Cull Group"
                cullObj.name = "Cull Group"
                cullProp = cullObj.ootCullGroupProperty
                cullProp.sizeControlsCull = False
                cullProp.manualRadius = hexOrDecInt(entryMatch.group(4).strip())
                cullObj.show_name = True
                # cullObj.empty_display_size = hexOrDecInt(entryMatch.group(4).strip()) / bpy.context.scene.ootBlenderScale
                parentObject(roomObj, cullObj)
                parentObj = cullObj
            else:
                parentObj = roomObj
        elif roomShape == 1:
            dls = [value.strip() for value in entryMatch.split(",")]
            opaqueDL = dls[0]
            transparentDL = dls[1]
            parentObj = roomObj
        else:
            opaqueDL = entryMatch.group(1).strip()
            transparentDL = entryMatch.group(2).strip()
            parentObj = roomObj

        # Technically the base path argument will not be used for the f3d context,
        # since all our data should be included already. So it should be okay for custom imports.
        for displayList, drawLayer in [(opaqueDL, "Opaque"), (transparentDL, "Transparent")]:
            if displayList != "0" and displayList != "NULL":
                meshObj = importMeshC(
                    sceneData, displayList, bpy.context.scene.ootBlenderScale, True, True, drawLayer, f3dContext, False
                )
                meshObj.location = [0, 0, 0]
                meshObj.ignore_collision = True
                parentObject(parentObj, meshObj)
