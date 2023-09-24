from dataclasses import dataclass, field
from bpy.types import Object
from ...utility import PluginError, CData, exportColor, ootGetBaseOrCustomLight, indent
from ..scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ..oot_constants import ootData
from .commands import OOTSceneCommands
from .common import Common, TransitionActor, EntranceActor, altHeaderList
from .room import OOTRoom

from .scene_header import (
    OOTSceneHeader,
    OOTSceneAlternateHeader,
    Path,
    EnvLightSettings,
    OOTSceneHeaderInfos,
    OOTSceneHeaderLighting,
    OOTSceneHeaderCutscene,
    OOTSceneHeaderExits,
    OOTSceneHeaderActors,
    OOTSceneHeaderPath,
    OOTSceneHeaderCrawlspace,
)


@dataclass
class OOTScene(Common, OOTSceneCommands):
    name: str = None
    headerIndex: int = None
    mainHeader: OOTSceneHeader = None
    altHeader: OOTSceneAlternateHeader = None
    roomList: list[OOTRoom] = field(default_factory=list)
    roomListName: str = None

    def __post_init__(self):
        self.roomListName = f"{self.name}_roomList"

    def validateCurveData(self, curveObj: Object):
        curveData = curveObj.data
        if curveObj.type != "CURVE" or curveData.splines[0].type != "NURBS":
            # Curve was likely not intended to be exported
            return False

        if len(curveData.splines) != 1:
            # Curve was intended to be exported but has multiple disconnected segments
            raise PluginError(f"Exported curves should have only one single segment, found {len(curveData.splines)}")

        return True

    def validateRoomIndices(self):
        for i, room in enumerate(self.roomList):
            if i != room.roomIndex:
                return False

        return True

    def validateScene(self):
        if not len(self.roomList) > 0:
            raise PluginError("ERROR: This scene does not have any rooms!")

        if not self.validateRoomIndices():
            raise PluginError("ERROR: Room indices do not have a consecutive list of indices.")

    def hasAlternateHeaders(self):
        return self.altHeader is not None

    def getSceneHeaderFromIndex(self, headerIndex: int) -> OOTSceneHeader | None:
        if headerIndex == 0:
            return self.mainHeader

        for i, header in enumerate(altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.altHeader, header)

        for i, csHeader in enumerate(self.altHeader.cutscenes, 4):
            if headerIndex == i:
                return csHeader

        return None

    def getExitListFromProps(self, headerProp: OOTSceneHeaderProperty):
        """Returns the exit list and performs safety checks"""

        exitList: list[tuple[int, str]] = []

        for i, exitProp in enumerate(headerProp.exitList):
            if exitProp.exitIndex != "Custom":
                raise PluginError("ERROR: Exits are unfinished, please use 'Custom'.")

            exitList.append((i, exitProp.exitIndexCustom))

        return exitList

    def getRoomObjectFromChild(self, childObj: Object) -> Object | None:
        # Note: temporary solution until PRs #243 & #255 are merged
        for obj in self.sceneObj.children_recursive:
            if obj.type == "EMPTY" and obj.ootEmptyType == "Room":
                for o in obj.children_recursive:
                    if o == childObj:
                        return obj
        return None

    def getTransActorListFromProps(self):
        actorList: list[TransitionActor] = []
        actorObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "EMPTY" and obj.ootEmptyType == "Transition Actor"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObjectFromChild(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")
            self.roomIndex = roomObj.ootRoomHeader.roomIndex

            transActorProp = obj.ootTransitionActorProperty

            if not self.isCurrentHeaderValid(transActorProp.actor.headerSettings, self.headerIndex):
                continue

            if transActorProp.actor.actorID != "None":
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                transActor = TransitionActor()

                if transActorProp.dontTransition:
                    front = (255, self.getPropValue(transActorProp, "cameraTransitionBack"))
                    back = (self.roomIndex, self.getPropValue(transActorProp, "cameraTransitionFront"))
                else:
                    front = (self.roomIndex, self.getPropValue(transActorProp, "cameraTransitionFront"))
                    back = (transActorProp.roomIndex, self.getPropValue(transActorProp, "cameraTransitionBack"))

                if transActorProp.actor.actorID == "Custom":
                    transActor.id = transActorProp.actor.actorIDCustom
                else:
                    transActor.id = transActorProp.actor.actorID

                transActor.name = (
                    ootData.actorData.actorsByID[transActorProp.actor.actorID].name.replace(
                        f" - {transActorProp.actor.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if transActorProp.actor.actorID != "Custom"
                    else "Custom Actor"
                )

                transActor.pos = pos
                transActor.rot = f"DEG_TO_BINANG({(rot[1] * (180 / 0x8000)):.3f})"  # TODO: Correct axis?
                transActor.params = transActorProp.actor.actorParam
                transActor.roomFrom, transActor.cameraFront = front
                transActor.roomTo, transActor.cameraBack = back
                actorList.append(transActor)
        return actorList

    def getEntranceActorListFromProps(self):
        actorList: list[EntranceActor] = []
        actorObjList: list[Object] = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Entrance"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObjectFromChild(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")

            entranceProp = obj.ootEntranceProperty
            if not self.isCurrentHeaderValid(entranceProp.actor.headerSettings, self.headerIndex):
                continue

            if entranceProp.actor.actorID != "None":
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                entranceActor = EntranceActor()

                entranceActor.name = (
                    ootData.actorData.actorsByID[entranceProp.actor.actorID].name.replace(
                        f" - {entranceProp.actor.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if entranceProp.actor.actorID != "Custom"
                    else "Custom Actor"
                )

                entranceActor.id = "ACTOR_PLAYER" if not entranceProp.customActor else entranceProp.actor.actorIDCustom
                entranceActor.pos = pos
                entranceActor.rot = ", ".join(f"DEG_TO_BINANG({(r * (180 / 0x8000)):.3f})" for r in rot)
                entranceActor.params = entranceProp.actor.actorParam
                entranceActor.roomIndex = roomObj.ootRoomHeader.roomIndex
                entranceActor.spawnIndex = entranceProp.spawnIndex
                actorList.append(entranceActor)
        return actorList

    def getPathListFromProps(self, listNameBase: str):
        pathList: list[Path] = []
        pathObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Path"
        ]

        for i, obj in enumerate(pathObjList):
            isHeaderValid = self.isCurrentHeaderValid(obj.ootSplineProperty.headerSettings, self.headerIndex)
            if isHeaderValid and self.validateCurveData(obj):
                pathList.append(
                    Path(
                        f"{listNameBase}{i:02}", [self.transform @ point.co.xyz for point in obj.data.splines[0].points]
                    )
                )

        return pathList

    def getEnvLightSettingsListFromProps(self, headerProp: OOTSceneHeaderProperty, lightMode: str):
        lightList: list[OOTLightProperty] = []
        lightSettings: list[EnvLightSettings] = []

        if lightMode == "LIGHT_MODE_TIME":
            todLights = headerProp.timeOfDayLights
            lightList = [todLights.dawn, todLights.day, todLights.dusk, todLights.night]
        else:
            lightList = headerProp.lightList

        for lightProp in lightList:
            light1 = ootGetBaseOrCustomLight(lightProp, 0, True, True)
            light2 = ootGetBaseOrCustomLight(lightProp, 1, True, True)
            lightSettings.append(
                EnvLightSettings(
                    lightMode,
                    exportColor(lightProp.ambient),
                    light1[0],
                    light1[1],
                    light2[0],
                    light2[1],
                    exportColor(lightProp.fogColor),
                    lightProp.fogNear,
                    lightProp.fogFar,
                    lightProp.transitionSpeed,
                )
            )

        return lightSettings

    def getNewSceneHeader(self, headerProp: OOTSceneHeaderProperty, headerIndex: int = 0):
        """Returns a single scene header with the informations from the scene empty object"""

        self.headerIndex = headerIndex
        headerName = f"{self.name}_header{self.headerIndex:02}"
        lightMode = self.getPropValue(headerProp, "skyboxLighting")

        if headerProp.writeCutscene and headerProp.csWriteType == "Embedded":
            raise PluginError("ERROR: 'Embedded' CS Write Type is not supported!")

        return OOTSceneHeader(
            headerName,
            OOTSceneHeaderInfos(
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
            OOTSceneHeaderLighting(
                f"{headerName}_lightSettings",
                lightMode,
                self.getEnvLightSettingsListFromProps(headerProp, lightMode),
            ),
            OOTSceneHeaderCutscene(
                headerProp.csWriteObject.name.removeprefix("Cutscene."),
                headerProp.csWriteType,
                headerProp.writeCutscene,
                headerProp.csWriteObject,
                headerProp.csWriteCustom if headerProp.csWriteType == "Custom" else None,
                [csObj for csObj in headerProp.extraCutscenes],
            ),
            OOTSceneHeaderExits(f"{headerName}_exitList", self.getExitListFromProps(headerProp)),
            OOTSceneHeaderActors(
                f"{headerName}_entranceList",
                f"{headerName}_playerEntryList",
                f"{headerName}_transitionActors",
                self.getTransActorListFromProps(),
                self.getEntranceActorListFromProps(),
            ),
            OOTSceneHeaderPath(f"{headerName}_pathway", self.getPathListFromProps(f"{headerName}_pathwayList")),
            OOTSceneHeaderCrawlspace(None), # not implemented yet
        )

    def getRoomListC(self):
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
        sceneC = CData()
        headers: list[tuple[OOTSceneHeader, str]] = []
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
        # will be implemented when PR #208 is merged
        csDataList: list[CData] = []
        return csDataList
