from dataclasses import dataclass
from ....utility import PluginError, CData, indent
from ....f3d.f3d_gbi import TextureExportSettings, ScrollMethod
from ...oot_model_classes import OOTGfxFormatter
from ...scene.properties import OOTSceneHeaderProperty
from ..classes import SceneFile
from .base import SceneBase

from ..collision import (
    Vertices,
    CollisionPolygons,
    SurfaceTypes,
    BgCamInformations,
    WaterBoxes,
    CollisionHeader,
)

from .header import (
    SceneInfos,
    SceneLighting,
    SceneCutscene,
    SceneExits,
    SceneActors,
    ScenePathways,
    SceneHeader,
)


@dataclass
class Scene(SceneBase):
    """This class defines a scene"""

    roomListName: str = None
    colHeader: CollisionHeader = None

    def __post_init__(self):
        self.roomListName = f"{self.name}_roomList"

    def getNewCollisionHeader(self):
        """Returns and creates collision data"""

        colBounds, vertexList, polyList, surfaceTypeList = self.getColSurfaceVtxDataFromMeshObj()
        bgCamInfoList = self.getBgCamInfoDataFromObjects()

        return CollisionHeader(
            f"{self.name}_collisionHeader",
            colBounds[0],
            colBounds[1],
            Vertices(f"{self.name}_vertices", vertexList),
            CollisionPolygons(f"{self.name}_polygons", polyList),
            SurfaceTypes(f"{self.name}_polygonTypes", surfaceTypeList),
            BgCamInformations(
                f"{self.name}_bgCamInfo",
                f"{self.name}_camPosData",
                bgCamInfoList,
                self.getCrawlspaceDataFromObjects(),
            ),
            WaterBoxes(f"{self.name}_waterBoxes", self.getWaterBoxDataFromObjects()),
        )

    def getNewSceneHeader(self, headerProp: OOTSceneHeaderProperty, headerIndex: int = 0):
        """Returns the scene header"""

        self.headerIndex = headerIndex
        headerName = f"{self.name}_header{self.headerIndex:02}"
        lightMode = self.getPropValue(headerProp, "skyboxLighting")

        if headerProp.writeCutscene and headerProp.csWriteType == "Embedded":
            raise PluginError("ERROR: 'Embedded' CS Write Type is not supported!")

        return SceneHeader(
            headerName,
            SceneInfos(
                self.getPropValue(headerProp, "globalObject"),
                self.getPropValue(headerProp, "naviCup"),
                self.getPropValue(headerProp.sceneTableEntry, "drawConfig"),
                headerProp.appendNullEntrance,
                self.sceneObj.fast64.oot.scene.write_dummy_room_list,
                self.getPropValue(headerProp, "skyboxID"),
                self.getPropValue(headerProp, "skyboxCloudiness"),
                self.getPropValue(headerProp, "musicSeq"),
                self.getPropValue(headerProp, "nightSeq"),
                self.getPropValue(headerProp, "audioSessionPreset"),
                self.getPropValue(headerProp, "mapLocation"),
                self.getPropValue(headerProp, "cameraMode"),
            ),
            SceneLighting(
                f"{headerName}_lightSettings",
                lightMode,
                self.getEnvLightSettingsListFromProps(headerProp, lightMode),
            ),
            SceneCutscene(
                headerIndex,
                headerProp.csWriteType,
                headerProp.writeCutscene,
                headerProp.csWriteObject,
                headerProp.csWriteCustom if headerProp.csWriteType == "Custom" else None,
                [csObj for csObj in headerProp.extraCutscenes],
            )
            if headerProp.writeCutscene
            else None,
            SceneExits(f"{headerName}_exitList", self.getExitListFromProps(headerProp)),
            SceneActors(
                f"{headerName}_entranceList",
                f"{headerName}_playerEntryList",
                f"{headerName}_transitionActors",
                self.getTransActorListFromProps(),
                self.getEntranceActorListFromProps(),
            ),
            ScenePathways(f"{headerName}_pathway", self.getPathListFromProps(f"{headerName}_pathwayList")),
        )

    def getRoomListC(self):
        """Returns the ``CData`` containing the room list array"""

        roomList = CData()
        listName = f"RomFile {self.roomListName}[]"

        # generating segment rom names for every room
        segNames = []
        for i in range(len(self.roomList)):
            roomName = self.roomList[i].name
            segNames.append((f"_{roomName}SegmentRomStart", f"_{roomName}SegmentRomEnd"))

        # .h
        roomList.header += f"extern {listName};\n"

        if not self.mainHeader.infos.useDummyRoomList:
            # Write externs for rom segments
            roomList.header += "".join(
                f"extern u8 {startName}[];\n" + f"extern u8 {stopName}[];\n" for startName, stopName in segNames
            )

        # .c
        roomList.source = listName + " = {\n"

        if self.mainHeader.infos.useDummyRoomList:
            roomList.source = (
                "// Dummy room list\n" + roomList.source + ((indent + "{ NULL, NULL },\n") * len(self.roomList))
            )
        else:
            roomList.source += (
                " },\n".join(
                    indent + "{ " + f"(uintptr_t){startName}, (uintptr_t){stopName}" for startName, stopName in segNames
                )
                + " },\n"
            )

        roomList.source += "};\n\n"
        return roomList

    def getSceneMainC(self):
        """Returns the main informations of the scene as ``CData``"""

        sceneC = CData()
        headers: list[tuple[SceneHeader, str]] = []
        altHeaderPtrs = None

        if self.hasAlternateHeaders():
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
                sceneC.append(self.getSceneCommandList(self, curHeader, i))

                if i == 0:
                    if self.hasAlternateHeaders() and altHeaderPtrs is not None:
                        altHeaderListName = f"SceneCmd* {self.altHeader.name}[]"
                        sceneC.header += f"extern {altHeaderListName};\n"
                        sceneC.source += altHeaderListName + " = {\n" + altHeaderPtrs + "\n};\n\n"

                    # Write the room segment list
                    sceneC.append(self.getRoomListC())

                sceneC.append(curHeader.getHeaderC())

        return sceneC

    def getSceneCutscenesC(self):
        """Returns the cutscene informations of the scene as ``CData`` (unfinished)"""

        # will be implemented when PR #208 is merged
        csDataList: list[CData] = []
        return csDataList

    def getSceneTexturesC(self, textureExportSettings: TextureExportSettings):
        """
        Writes the textures and material setup displaylists that are shared between multiple rooms
        (is written to the scene)
        """

        return self.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex)).all()

    def getNewSceneFile(self, path: str, isSingleFile: bool, textureExportSettings: TextureExportSettings):
        """Gets and sets C data for every scene elements"""

        sceneMainData = self.getSceneMainC()
        sceneCollisionData = self.colHeader.getSceneCollisionC()
        sceneCutsceneData = self.getSceneCutscenesC()
        sceneTexturesData = self.getSceneTexturesC(textureExportSettings)

        return SceneFile(
            self.name,
            sceneMainData.source,
            sceneCollisionData.source,
            [cs.source for cs in sceneCutsceneData],
            sceneTexturesData.source,
            {room.roomIndex: room.getNewRoomFile(path, isSingleFile, textureExportSettings) for room in self.roomList},
            isSingleFile,
            path,
            (
                f"#ifndef {self.name.upper()}_H\n"
                + f"#define {self.name.upper()}_H\n\n"
                + sceneMainData.header
                + "".join(cs.header for cs in sceneCutsceneData)
                + sceneCollisionData.header
                + sceneTexturesData.header
            ),
        )
