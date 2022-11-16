from .....utility import CData
from .....f3d.f3d_gbi import TextureExportSettings
from .scene_header import ootSceneMainToC, ootSceneTexturesToC
from .scene_collision import ootSceneCollisionToC
from .scene_cutscene import ootSceneCutscenesToC
from .room_header import ootRoomMainToC
from .room_shape import ootRoomMeshToC


def ootSceneIncludes(scene):
    data = CData()
    data.source += '#include "ultra64.h"\n'
    data.source += '#include "z64.h"\n'
    data.source += '#include "macros.h"\n'
    data.source += '#include "' + scene.sceneName() + '.h"\n'

    # Not used if all header declarations are in scene.h
    # for i in range(len(scene.rooms)):
    #    data.source += f'#include "{scene.rooms[i].roomName()}.h"\n'

    data.source += '#include "segment_symbols.h"\n'
    data.source += '#include "command_macros_base.h"\n'
    data.source += '#include "z64cutscene_commands.h"\n'
    data.source += '#include "variables.h"\n'
    data.source += "\n"
    return data


def ootLevelToC(scene, textureExportSettings: TextureExportSettings):
    levelC = OOTLevelC()

    levelC.sceneMainC = ootSceneMainToC(scene, 0)
    levelC.sceneTexturesC = ootSceneTexturesToC(scene, textureExportSettings)
    levelC.sceneCollisionC = ootSceneCollisionToC(scene)
    levelC.sceneCutscenesC = ootSceneCutscenesToC(scene)

    for i in range(len(scene.rooms)):
        levelC.roomMainC[scene.rooms[i].roomName()] = ootRoomMainToC(scene, scene.rooms[i], 0)
        meshHeader, meshData = ootRoomMeshToC(scene.rooms[i], textureExportSettings)
        levelC.roomMeshInfoC[scene.rooms[i].roomName()] = meshHeader
        levelC.roomMeshC[scene.rooms[i].roomName()] = meshData
    return levelC


class OOTLevelC:
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
        self.roomMeshInfoC = {}
        self.roomMeshC = {}
