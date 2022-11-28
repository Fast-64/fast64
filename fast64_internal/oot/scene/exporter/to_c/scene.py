from .....utility import CData, PluginError
from .....f3d.f3d_gbi import TextureExportSettings
from ....oot_level_classes import OOTScene
from .scene_header import getSceneData, getSceneModel
from .scene_collision import getSceneCollision
from .scene_cutscene import getSceneCutscenes
from .room_header import getRoomData
from .room_shape import getRoomModel, getRoomShape


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
