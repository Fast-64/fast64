import bpy
import os

from .....utility import CData, PluginError
from .....f3d.f3d_gbi import TextureExportSettings
from ....oot_constants import ootData
from ....oot_model_classes import OOTModel
from ....oot_object import addMissingObjectsToAllRoomHeaders
from ....oot_f3d_writer import writeTextureArraysNew, writeTextureArraysExisting1D
from ....oot_utility import ootGetPath, getSceneDirFromLevelName
from ..classes import OOTScene
from ..functions import ootConvertScene
from .scene_header import getSceneData, getSceneModel
from .scene_collision import getSceneCollision
from .scene_cutscene import getSceneCutscenes
from .room_header import getRoomData
from .room_shape import getRoomModel, getRoomShape
from .scene_bootup import setBootupScene
from .scene_table_c import modifySceneTable
from .scene_folder import modifySceneFiles
from .spec import editSpecFile

from .....utility import (
    PluginError,
    CData,
    checkObjectReference,
    writeCDataSourceOnly,
    writeCDataHeaderOnly,
    readFile,
    writeFile,
)


class OOTSceneC:
    def sceneTexturesIsUsed(self):
        return len(self.sceneTexturesC.source) > 0

    def sceneCutscenesIsUsed(self):
        return len(self.sceneCutscenesC) > 0

    def __init__(self):
        # Main header file for both the scene and room(s)
        self.header = CData()

        # Files for the scene segment
        self.sceneMainC = CData()
        self.sceneTexturesC = CData()
        self.sceneCollisionC = CData()
        self.sceneCutscenesC = []

        # Files for room segments
        self.roomMainC = {}
        self.roomShapeInfoC = {}
        self.roomModelC = {}


def getSceneC(outScene: OOTScene, textureExportSettings: TextureExportSettings):
    """Generates C code for each scene element and returns the data"""
    sceneC = OOTSceneC()

    sceneC.sceneMainC = getSceneData(outScene)
    sceneC.sceneTexturesC = getSceneModel(outScene, textureExportSettings)
    sceneC.sceneCollisionC = getSceneCollision(outScene)
    sceneC.sceneCutscenesC = getSceneCutscenes(outScene)

    for outRoom in outScene.rooms.values():
        outRoomName = outRoom.roomName()

        if len(outRoom.mesh.meshEntries) > 0:
            roomShapeInfo = getRoomShape(outRoom)
            roomModel = getRoomModel(outRoom, textureExportSettings)
        else:
            raise PluginError(f"Error: Room {outRoom.index} has no mesh children.")

        sceneC.roomMainC[outRoomName] = getRoomData(outRoom)
        sceneC.roomShapeInfoC[outRoomName] = roomShapeInfo
        sceneC.roomModelC[outRoomName] = roomModel

    return sceneC


def getIncludes(outScene: OOTScene):
    """Returns the files to include"""
    # @TODO: avoid including files where it's not needed
    includeData = CData()

    fileNames = [
        "ultra64",
        "z64",
        "macros",
        outScene.sceneName(),
        "segment_symbols",
        "command_macros_base",
        "z64cutscene_commands",
        "variables",
    ]

    includeData.source = "\n".join(f'#include "{fileName}.h"' for fileName in fileNames) + "\n\n"

    return includeData


def ootPreprendSceneIncludes(scene, file):
    exportFile = getIncludes(scene)
    exportFile.append(file)
    return exportFile


def ootCreateSceneHeader(levelC):
    sceneHeader = CData()

    sceneHeader.append(levelC.sceneMainC)
    if levelC.sceneTexturesIsUsed():
        sceneHeader.append(levelC.sceneTexturesC)
    sceneHeader.append(levelC.sceneCollisionC)
    if levelC.sceneCutscenesIsUsed():
        for i in range(len(levelC.sceneCutscenesC)):
            sceneHeader.append(levelC.sceneCutscenesC[i])
    for roomName, roomMainC in levelC.roomMainC.items():
        sceneHeader.append(roomMainC)
    for roomName, roomShapeInfoC in levelC.roomShapeInfoC.items():
        sceneHeader.append(roomShapeInfoC)
    for roomName, roomModelC in levelC.roomModelC.items():
        sceneHeader.append(roomModelC)

    return sceneHeader


def ootCombineSceneFiles(levelC):
    sceneC = CData()

    sceneC.append(levelC.sceneMainC)
    if levelC.sceneTexturesIsUsed():
        sceneC.append(levelC.sceneTexturesC)
    sceneC.append(levelC.sceneCollisionC)
    if levelC.sceneCutscenesIsUsed():
        for i in range(len(levelC.sceneCutscenesC)):
            sceneC.append(levelC.sceneCutscenesC[i])
    return sceneC


def writeOtherSceneProperties(scene, exportInfo, levelC):
    modifySceneTable(scene, exportInfo)
    editSpecFile(scene, exportInfo, levelC)
    modifySceneFiles(scene, exportInfo)


def writeTextureArraysExistingScene(fModel: OOTModel, exportPath: str, sceneInclude: str):
    drawConfigPath = os.path.join(exportPath, "src/code/z_scene_table.c")
    drawConfigData = readFile(drawConfigPath)
    newData = drawConfigData

    if f'#include "{sceneInclude}"' not in newData:
        additionalIncludes = f'#include "{sceneInclude}"\n'
    else:
        additionalIncludes = ""

    for flipbook in fModel.flipbooks:
        if flipbook.exportMode == "Array":
            newData = writeTextureArraysExisting1D(newData, flipbook, additionalIncludes)
        else:
            raise PluginError("Scenes can only use array flipbooks.")

    if newData != drawConfigData:
        writeFile(drawConfigPath, newData)


def ootExportSceneToC(
    originalSceneObj, transformMatrix, f3dType, isHWv1, sceneName, DLFormat, savePNG, exportInfo, bootToSceneOptions
):
    checkObjectReference(originalSceneObj, "Scene object")
    isCustomExport = exportInfo.isCustomExportPath
    exportPath = exportInfo.exportPath

    scene = ootConvertScene(originalSceneObj, transformMatrix, f3dType, isHWv1, sceneName, DLFormat, not savePNG)

    exportSubdir = ""
    if exportInfo.customSubPath is not None:
        exportSubdir = exportInfo.customSubPath
    if not isCustomExport and exportInfo.customSubPath is None:
        exportSubdir = os.path.dirname(getSceneDirFromLevelName(sceneName))

    roomObjList = [
        obj for obj in originalSceneObj.children_recursive if obj.data is None and obj.ootEmptyType == "Room"
    ]
    for roomObj in roomObjList:
        room = scene.rooms[roomObj.ootRoomHeader.roomIndex]
        addMissingObjectsToAllRoomHeaders(roomObj, room, ootData)

    sceneInclude = exportSubdir + "/" + sceneName + "/"
    levelPath = ootGetPath(exportPath, isCustomExport, exportSubdir, sceneName, True, True)
    levelC = getSceneC(scene, TextureExportSettings(False, savePNG, sceneInclude, levelPath))

    if not isCustomExport:
        writeTextureArraysExistingScene(scene.model, exportPath, sceneInclude + sceneName + "_scene.h")
    else:
        textureArrayData = writeTextureArraysNew(scene.model, None)
        levelC.sceneTexturesC.append(textureArrayData)

    if bpy.context.scene.ootSceneExportSettings.singleFile:
        writeCDataSourceOnly(
            ootPreprendSceneIncludes(scene, ootCombineSceneFiles(levelC)),
            os.path.join(levelPath, scene.sceneName() + ".c"),
        )
        for i in range(len(scene.rooms)):
            roomC = CData()
            roomC.append(levelC.roomMainC[scene.rooms[i].roomName()])
            roomC.append(levelC.roomShapeInfoC[scene.rooms[i].roomName()])
            roomC.append(levelC.roomModelC[scene.rooms[i].roomName()])
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, roomC), os.path.join(levelPath, scene.rooms[i].roomName() + ".c")
            )
    else:
        # Export the scene segment .c files
        writeCDataSourceOnly(
            ootPreprendSceneIncludes(scene, levelC.sceneMainC), os.path.join(levelPath, scene.sceneName() + "_main.c")
        )
        if levelC.sceneTexturesIsUsed():
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, levelC.sceneTexturesC),
                os.path.join(levelPath, scene.sceneName() + "_tex.c"),
            )
        writeCDataSourceOnly(
            ootPreprendSceneIncludes(scene, levelC.sceneCollisionC),
            os.path.join(levelPath, scene.sceneName() + "_col.c"),
        )
        if levelC.sceneCutscenesIsUsed():
            for i in range(len(levelC.sceneCutscenesC)):
                writeCDataSourceOnly(
                    ootPreprendSceneIncludes(scene, levelC.sceneCutscenesC[i]),
                    os.path.join(levelPath, scene.sceneName() + "_cs_" + str(i) + ".c"),
                )

        # Export the room segment .c files
        for roomName, roomMainC in levelC.roomMainC.items():
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, roomMainC), os.path.join(levelPath, roomName + "_main.c")
            )
        for roomName, roomShapeInfoC in levelC.roomShapeInfoC.items():
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, roomShapeInfoC), os.path.join(levelPath, roomName + "_model_info.c")
            )
        for roomName, roomModelC in levelC.roomModelC.items():
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, roomModelC), os.path.join(levelPath, roomName + "_model.c")
            )

    # Export the scene .h file
    writeCDataHeaderOnly(ootCreateSceneHeader(levelC), os.path.join(levelPath, scene.sceneName() + ".h"))

    # Copy bg images
    scene.copyBgImages(levelPath)

    if not isCustomExport:
        writeOtherSceneProperties(scene, exportInfo, levelC)

    if bootToSceneOptions is not None and bootToSceneOptions.bootToScene:
        setBootupScene(
            os.path.join(exportPath, "include/config/config_debug.h")
            if not isCustomExport
            else os.path.join(levelPath, "config_bootup.h"),
            "ENTR_" + sceneName.upper() + "_" + str(bootToSceneOptions.spawnIndex),
            bootToSceneOptions,
        )
