import bpy

from dataclasses import dataclass
from mathutils import Matrix
from bpy.types import Object
from typing import Optional
from ....utility import PluginError, CData, indent
from ....f3d.f3d_gbi import TextureExportSettings, ScrollMethod
from ...scene.properties import OOTSceneHeaderProperty
from ...model_classes import OOTModel, OOTGfxFormatter
from ..file import SceneFile
from ..utility import Utility, altHeaderList
from ..collision import CollisionHeader
from .header import SceneAlternateHeader, SceneHeader
from .rooms import RoomEntries


@dataclass
class Scene:
    """This class defines a scene"""

    name: str
    model: OOTModel
    mainHeader: Optional[SceneHeader]
    altHeader: Optional[SceneAlternateHeader]
    rooms: Optional[RoomEntries]
    colHeader: Optional[CollisionHeader]
    hasAlternateHeaders: bool

    @staticmethod
    def new(
        name: str,
        original_scene_obj: Object,
        sceneObj: Object,
        transform: Matrix,
        useMacros: bool,
        saveTexturesAsPNG: bool,
        model: OOTModel,
    ):
        i = 0
        rooms = RoomEntries.new(
            f"{name}_roomList",
            name.removesuffix("_scene"),
            model,
            original_scene_obj,
            sceneObj,
            transform,
            saveTexturesAsPNG,
        )

        colHeader = CollisionHeader.new(
            f"{name}_collisionHeader",
            name,
            sceneObj,
            transform,
            useMacros,
            True,
        )

        try:
            mainHeader = SceneHeader.new(
                f"{name}_header{i:02}", sceneObj.ootSceneHeader, sceneObj, transform, i, useMacros
            )
        except Exception as exc:
            raise PluginError(f"In main scene header: {exc}") from exc
        hasAlternateHeaders = False
        altHeader = SceneAlternateHeader(f"{name}_alternateHeaders")
        altProp = sceneObj.ootAlternateSceneHeaders

        for i, header in enumerate(altHeaderList, 1):
            altP: OOTSceneHeaderProperty = getattr(altProp, f"{header}Header")
            if altP.usePreviousHeader:
                continue
            try:
                setattr(
                    altHeader, header, SceneHeader.new(f"{name}_header{i:02}", altP, sceneObj, transform, i, useMacros)
                )
                hasAlternateHeaders = True
            except Exception as exc:
                raise PluginError(f"In alternate scene header {header}: {exc}") from exc

        altHeader.cutscenes = []
        for i, csHeader in enumerate(altProp.cutsceneHeaders, 4):
            try:
                altHeader.cutscenes.append(
                    SceneHeader.new(f"{name}_header{i:02}", csHeader, sceneObj, transform, i, useMacros)
                )
            except Exception as exc:
                raise PluginError(f"In alternate, cutscene header {i}: {exc}") from exc

        hasAlternateHeaders = True if len(altHeader.cutscenes) > 0 else hasAlternateHeaders
        altHeader = altHeader if hasAlternateHeaders else None
        return Scene(name, model, mainHeader, altHeader, rooms, colHeader, hasAlternateHeaders)

    def validateRoomIndices(self):
        """Checks if there are multiple rooms with the same room index"""

        for i, room in enumerate(self.rooms.entries):
            if i != room.roomIndex:
                return False
        return True

    def validateScene(self):
        """Performs safety checks related to the scene data"""

        if not len(self.rooms.entries) > 0:
            raise PluginError("ERROR: This scene does not have any rooms!")

        if not self.validateRoomIndices():
            raise PluginError("ERROR: Room indices do not have a consecutive list of indices.")

    def getSceneHeaderFromIndex(self, headerIndex: int) -> SceneHeader | None:
        """Returns the scene header based on the header index"""

        if headerIndex == 0:
            return self.mainHeader

        for i, header in enumerate(altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.altHeader, header)

        for i, csHeader in enumerate(self.altHeader.cutscenes, 4):
            if headerIndex == i:
                return csHeader

        return None

    def getCmdList(self, curHeader: SceneHeader, hasAltHeaders: bool):
        """Returns the scene's commands list"""

        cmdListData = CData()
        listName = f"SceneCmd {curHeader.name}"

        # .h
        cmdListData.header = f"extern {listName}[]" + ";\n"

        # .c
        cmdListData.source = (
            (f"{listName}[]" + " = {\n")
            + (Utility.getAltHeaderListCmd(self.altHeader.name) if hasAltHeaders else "")
            + self.colHeader.getCmd()
            + self.rooms.getCmd()
            + curHeader.infos.getCmds(curHeader.lighting)
            + curHeader.lighting.getCmd()
            + curHeader.path.getCmd()
            + (curHeader.transitionActors.getCmd() if len(curHeader.transitionActors.entries) > 0 else "")
            + curHeader.spawns.getCmd()
            + curHeader.entranceActors.getCmd()
            + (curHeader.exits.getCmd() if len(curHeader.exits.exitList) > 0 else "")
            + (curHeader.cutscene.getCmd() if len(curHeader.cutscene.entries) > 0 else "")
            + Utility.getEndCmd()
            + "};\n\n"
        )

        return cmdListData

    def getSceneMainC(self):
        """Returns the main informations of the scene as ``CData``"""

        sceneC = CData()
        headers: list[tuple[SceneHeader, str]] = []
        altHeaderPtrs = None

        if self.hasAlternateHeaders:
            headers = [
                (self.altHeader.childNight, "Child Night"),
                (self.altHeader.adultDay, "Adult Day"),
                (self.altHeader.adultNight, "Adult Night"),
            ]

            for i, csHeader in enumerate(self.altHeader.cutscenes):
                headers.append((csHeader, f"Cutscene No. {i + 1}"))

            altHeaderPtrs = "\n".join(
                indent + curHeader.name + "," if curHeader is not None else indent + "NULL," if i < 4 else ""
                for i, (curHeader, _) in enumerate(headers, 1)
            )

        headers.insert(0, (self.mainHeader, "Child Day (Default)"))
        for i, (curHeader, headerDesc) in enumerate(headers):
            if curHeader is not None:
                sceneC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
                sceneC.append(self.getCmdList(curHeader, i == 0 and self.hasAlternateHeaders))

                if i == 0:
                    if self.hasAlternateHeaders and altHeaderPtrs is not None:
                        altHeaderListName = f"SceneCmd* {self.altHeader.name}[]"
                        sceneC.header += f"extern {altHeaderListName};\n"
                        sceneC.source += altHeaderListName + " = {\n" + altHeaderPtrs + "\n};\n\n"

                    # Write the room segment list
                    sceneC.append(self.rooms.getC(self.mainHeader.infos.useDummyRoomList))

                sceneC.append(curHeader.getC())

        return sceneC

    def getSceneCutscenesC(self):
        """Returns the cutscene informations of the scene as ``CData``"""

        csDataList: list[CData] = []
        headers: list[SceneHeader] = [
            self.mainHeader,
        ]

        if self.altHeader is not None:
            headers.extend(
                [
                    self.altHeader.childNight,
                    self.altHeader.adultDay,
                    self.altHeader.adultNight,
                ]
            )
            headers.extend(self.altHeader.cutscenes)

        for curHeader in headers:
            if curHeader is not None:
                for csEntry in curHeader.cutscene.entries:
                    csDataList.append(csEntry.getC())

        return csDataList

    def getSceneTexturesC(self, textureExportSettings: TextureExportSettings):
        """
        Writes the textures and material setup displaylists that are shared between multiple rooms
        (is written to the scene)
        """

        return self.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex)).all()

    def getNewSceneFile(self, path: str, isSingleFile: bool, textureExportSettings: TextureExportSettings):
        """Returns a new scene file containing the C data"""

        sceneMainData = self.getSceneMainC()
        sceneCollisionData = self.colHeader.getC()
        sceneCutsceneData = self.getSceneCutscenesC()
        sceneTexturesData = self.getSceneTexturesC(textureExportSettings)

        if bpy.context.scene.fast64.oot.is_globalh_present():
            includes = [
                '#include "ultra64.h"',
                '#include "macros.h"',
                '#include "z64.h"',
            ]
        elif bpy.context.scene.fast64.oot.is_z64sceneh_present():
            includes = [
                '#include "ultra64.h"',
                '#include "romfile.h"',
                '#include "array_count.h"',
                '#include "sequence.h"',
                '#include "z64actor_profile.h"',
                '#include "z64bgcheck.h"',
                '#include "z64camera.h"',
                '#include "z64cutscene.h"',
                '#include "z64cutscene_commands.h"',
                '#include "z64environment.h"',
                '#include "z64math.h"',
                '#include "z64object.h"',
                '#include "z64ocarina.h"',
                '#include "z64path.h"',
                '#include "z64player.h"',
                '#include "z64room.h"',
                '#include "z64scene.h"',
            ]
        else:
            includes = [
                '#include "ultra64.h"',
                '#include "romfile.h"',
                '#include "array_count.h"',
                '#include "sequence.h"',
                '#include "actor_profile.h"',
                '#include "bgcheck.h"',
                '#include "camera.h"',
                '#include "cutscene.h"',
                '#include "cutscene_commands.h"',
                '#include "environment.h"',
                '#include "z_math.h"',
                '#include "object.h"',
                '#include "ocarina.h"',
                '#include "path.h"',
                '#include "player.h"',
                '#include "room.h"',
                '#include "scene.h"',
            ]

        backwards_compatibility = [
            "// For older decomp versions",
            "#ifndef SCENE_CMD_PLAYER_ENTRY_LIST",
            "#define SCENE_CMD_PLAYER_ENTRY_LIST(length, playerEntryList) \\",
            indent + "{ SCENE_CMD_ID_SPAWN_LIST, length, CMD_PTR(playerEntryList) }",
            "#undef SCENE_CMD_SPAWN_LIST",
            "#define SCENE_CMD_SPAWN_LIST(spawnList) \\",
            indent + "{ SCENE_CMD_ID_ENTRANCE_LIST, 0, CMD_PTR(spawnList) }",
            "#endif\n\n",
        ]

        return SceneFile(
            self.name,
            sceneMainData.source,
            sceneCollisionData.source,
            [cs.source for cs in sceneCutsceneData],
            sceneTexturesData.source,
            {
                room.roomIndex: room.getNewRoomFile(path, isSingleFile, textureExportSettings)
                for room in self.rooms.entries
            },
            isSingleFile,
            path,
            (
                f"#ifndef {self.name.upper()}_H\n"
                + f"#define {self.name.upper()}_H\n\n"
                + ("\n".join(includes) + "\n\n")
                + "\n".join(backwards_compatibility)
                + sceneMainData.header
                + "".join(cs.header for cs in sceneCutsceneData)
                + sceneCollisionData.header
                + sceneTexturesData.header
            ),
        )
