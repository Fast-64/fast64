from ...utility import CData
from ...f3d.f3d_gbi import ScrollMethod, TextureExportSettings

from ..oot_model_classes import OOTGfxFormatter
from ..oot_level_classes import OOTScene, OOTRoom
from ..oot_collision import ootCollisionToC

from .oot_scene_room_cmds.oot_scene_cmds import ootSceneCommandsToC
from .oot_scene_room_cmds.oot_room_cmds import ootRoomCommandsToC

from .oot_room_writer.oot_object_to_c import ootObjectListToC
from .oot_room_writer.oot_actor_to_c import ootActorListToC
from .oot_room_writer.oot_room_list_to_c import ootRoomListHeaderToC
from .oot_room_writer.oot_room_shape_to_c import ootGetRoomShapeHeaderData, ootRoomModelToC

from .oot_scene_writer.oot_path_to_c import ootPathListToC
from .oot_scene_writer.oot_light_to_c import ootLightSettingsToC
from .oot_scene_writer.oot_trans_actor_to_c import ootTransitionActorListToC
from .oot_scene_writer.oot_entrance_exit_to_c import ootEntranceListToC, ootExitListToC
from .oot_scene_writer.oot_cutscene_to_c import ootSceneCutscenesToC


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


def ootLevelToC(scene: OOTScene, textureExportSettings: TextureExportSettings):
    levelC = OOTLevelC()
    textureData = scene.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex)).all()

    levelC.sceneMainC = ootSceneMainToC(scene, 0)
    levelC.sceneTexturesC = textureData
    levelC.sceneCollisionC = ootCollisionToC(scene.collision)
    levelC.sceneCutscenesC = ootSceneCutscenesToC(scene)

    for room in scene.rooms.values():
        name = room.roomName()
        levelC.roomMainC[name] = ootRoomMainToC(scene, room, 0)
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


def ootAlternateRoomMainToC(scene: OOTScene, room: OOTRoom):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SCmdBase* " + room.alternateHeadersName() + "[];\n"
    altHeader.source = "SCmdBase* " + room.alternateHeadersName() + "[] = {\n"

    if room.childNightHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(1, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.childNightHeader, 1))
    else:
        altHeader.source += "\t0,\n"

    if room.adultDayHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(2, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.adultDayHeader, 2))
    else:
        altHeader.source += "\t0,\n"

    if room.adultNightHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(3, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.adultNightHeader, 3))
    else:
        altHeader.source += "\t0,\n"

    for i in range(len(room.cutsceneHeaders)):
        altHeader.source += "\t" + room.roomName() + "_header" + format(i + 4, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.cutsceneHeaders[i], i + 4))

    altHeader.source += "};\n\n"

    return altHeader, altData


def ootRoomMainToC(scene: OOTScene, room: OOTRoom, headerIndex: int):
    roomMainC = CData()

    if room.hasAlternateHeaders():
        altHeader, altData = ootAlternateRoomMainToC(scene, room)
    else:
        altHeader = CData()
        altData = CData()

    roomMainC.append(ootRoomCommandsToC(room, headerIndex))
    roomMainC.append(altHeader)

    if len(room.objectIDList) > 0:
        roomMainC.append(ootObjectListToC(room, headerIndex))

    if len(room.actorList) > 0:
        roomMainC.append(ootActorListToC(None, room, headerIndex))

    roomMainC.append(altData)

    return roomMainC


def ootAlternateSceneMainToC(scene: OOTScene):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SCmdBase* " + scene.alternateHeadersName() + "[];\n"
    altHeader.source = "SCmdBase* " + scene.alternateHeadersName() + "[] = {\n"

    if scene.childNightHeader is not None:
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(1, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.childNightHeader, 1))
    else:
        altHeader.source += "\t0,\n"

    if scene.adultDayHeader is not None:
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(2, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.adultDayHeader, 2))
    else:
        altHeader.source += "\t0,\n"

    if scene.adultNightHeader is not None:
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(3, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.adultNightHeader, 3))
    else:
        altHeader.source += "\t0,\n"

    for i in range(len(scene.cutsceneHeaders)):
        altHeader.source += "\t" + scene.sceneName() + "_header" + format(i + 4, "02") + ",\n"
        altData.append(ootSceneMainToC(scene.cutsceneHeaders[i], i + 4))

    altHeader.source += "};\n\n"

    return altHeader, altData


def ootSceneMainToC(scene: OOTScene, headerIndex: int):
    sceneMainC = CData()

    if headerIndex == 0:
        # Check if this is the first time the function is being called, we do not want to write this data multiple times
        roomHeaderData = ootRoomListHeaderToC(scene)
        if len(scene.pathList) > 0:
            pathData = ootPathListToC(scene)
        else:
            pathData = CData()
    else:
        # The function has already been called (and is being called for another scene header), so we can make this data be a blank string
        roomHeaderData = CData()
        pathData = CData()

    if scene.hasAlternateHeaders():
        # Gets the alternate data for the scene's main c file
        altHeader, altData = ootAlternateSceneMainToC(scene)
    else:
        # Since the scene does not use alternate headers, this data can just be a blank string
        altHeader = CData()
        altData = CData()

    # Write the scene header
    sceneMainC.append(ootSceneCommandsToC(scene, headerIndex))

    # Write alternate scene headers
    sceneMainC.append(altHeader)

    # Write the spawn position list data
    if len(scene.startPositions) > 0:
        sceneMainC.append(ootActorListToC(scene, None, headerIndex))

    # Write the transition actor list data
    if len(scene.transitionActorList) > 0:
        sceneMainC.append(ootTransitionActorListToC(scene, headerIndex))

    # Write the room segment list
    sceneMainC.append(roomHeaderData)

    # Write the entrance list
    if len(scene.entranceList) > 0:
        sceneMainC.append(ootEntranceListToC(scene, headerIndex))

    # Write the exit list
    if len(scene.exitList) > 0:
        sceneMainC.append(ootExitListToC(scene, headerIndex))

    # Write the light data
    if len(scene.lights) > 0:
        sceneMainC.append(ootLightSettingsToC(scene, headerIndex))

    # Write the path data, if used
    sceneMainC.append(pathData)

    # Write the data from alternate headers
    sceneMainC.append(altData)

    return sceneMainC
