from ...utility import CData
from ...f3d.f3d_gbi import ScrollMethod, TextureExportSettings
from ..oot_model_classes import OOTGfxFormatter
from ..oot_level_classes import OOTScene

from ..oot_collision import ootCollisionToC
from .oot_room_writer.oot_room_shape_to_c import ootGetRoomShapeHeaderData, ootRoomModelToC
from .oot_room_writer.oot_room_layer_to_c import ootRoomLayersToC
from .oot_scene_writer.oot_cutscene_to_c import ootSceneCutscenesToC
from .oot_scene_writer.oot_scene_layer_to_c import ootSceneLayersToC


class OOTLevelC:
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

    def sceneTexturesIsUsed(self):
        return len(self.sceneTexturesC.source) > 0

    def sceneCutscenesIsUsed(self):
        return len(self.sceneCutscenesC) > 0


def ootLevelToC(scene: OOTScene, textureExportSettings: TextureExportSettings):
    levelC = OOTLevelC()
    textureData = scene.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex)).all()

    levelC.sceneMainC = ootSceneLayersToC(scene)
    levelC.sceneTexturesC = textureData
    levelC.sceneCollisionC = ootCollisionToC(scene.collision)
    levelC.sceneCutscenesC = ootSceneCutscenesToC(scene)

    for room in scene.rooms.values():
        name = room.roomName()
        levelC.roomMainC[name] = ootRoomLayersToC(room)
        levelC.roomMeshInfoC[name] = ootGetRoomShapeHeaderData(room.mesh)
        levelC.roomMeshC[name] = ootRoomModelToC(room, textureExportSettings)

    return levelC


def ootSceneIncludes(scene: OOTScene):
    sceneIncludeData = CData()
    includeFiles = [
        "ultra64.h",
        "z64.h",
        "macros.h",
        f"{scene.sceneName()}.h",
        "segment_symbols.h",
        "command_macros_base.h",
        "variables.h",
    ]

    if scene.writeCutscene:
        includeFiles.append("z64cutscene_commands.h")

    sceneIncludeData.source = "\n".join([f'#include "{fileName}"' for fileName in includeFiles]) + "\n\n"
    return sceneIncludeData
