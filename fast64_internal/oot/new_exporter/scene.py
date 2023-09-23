from dataclasses import dataclass, field
from bpy.types import Object
from ...utility import PluginError, CData, exportColor, ootGetBaseOrCustomLight, indent
from ..scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ..oot_constants import ootData
from .commands import OOTSceneCommands
from .common import Common, TransitionActor, EntranceActor, altHeaderList
from .room import OOTRoom


@dataclass
class SceneCommon:
    headerName: str


@dataclass
class EnvLightSettings:
    envLightMode: str
    ambientColor: tuple[int, int, int]
    light1Color: tuple[int, int, int]
    light1Dir: tuple[int, int, int]
    light2Color: tuple[int, int, int]
    light2Dir: tuple[int, int, int]
    fogColor: tuple[int, int, int]
    fogNear: int
    zFar: int
    blendRate: int

    def getBlendFogNear(self):
        return f"(({self.blendRate} << 10) | {self.fogNear})"

    def getColorValues(self, vector: tuple[int, int, int]):
        return ", ".join(f"{v:5}" for v in vector)

    def getDirectionValues(self, vector: tuple[int, int, int]):
        return ", ".join(f"{v - 0x100 if v > 0x7F else v:5}" for v in vector)

    def getLightSettingsEntry(self, index: int):
        isLightingCustom = self.envLightMode == "Custom"

        vectors = [
            (self.ambientColor, "Ambient Color", self.getColorValues),
            (self.light1Dir, "Diffuse0 Direction", self.getDirectionValues),
            (self.light1Color, "Diffuse0 Color", self.getColorValues),
            (self.light2Dir, "Diffuse1 Direction", self.getDirectionValues),
            (self.light2Color, "Diffuse1 Color", self.getColorValues),
            (self.fogColor, "Fog Color", self.getColorValues),
        ]

        fogData = [
            (self.getBlendFogNear(), "Blend Rate & Fog Near"),
            (f"{self.zFar}", "Fog Far"),
        ]

        lightDescs = ["Dawn", "Day", "Dusk", "Night"]

        if not isLightingCustom and self.envLightMode == "LIGHT_MODE_TIME":
            # @TODO: Improve the lighting system.
            # Currently Fast64 assumes there's only 4 possible settings for "Time of Day" lighting.
            # This is not accurate and more complicated,
            # for now we are doing ``index % 4`` to avoid having an OoB read in the list
            # but this will need to be changed the day the lighting system is updated.
            lightDesc = f"// {lightDescs[index % 4]} Lighting\n"
        else:
            isIndoor = not isLightingCustom and self.envLightMode == "LIGHT_MODE_SETTINGS"
            lightDesc = f"// {'Indoor' if isIndoor else 'Custom'} No. {index + 1} Lighting\n"

        lightData = (
            (indent + lightDesc)
            + (indent + "{\n")
            + "".join(
                indent * 2 + f"{'{ ' + vecToC(vector) + ' },':26} // {desc}\n" for (vector, desc, vecToC) in vectors
            )
            + "".join(indent * 2 + f"{fogValue + ',':26} // {fogDesc}\n" for fogValue, fogDesc in fogData)
            + (indent + "},\n")
        )

        return lightData


@dataclass
class OOTSceneHeaderInfos:
    ### General ###

    keepObjectID: str
    naviHintType: str
    drawConfig: str
    appendNullEntrance: bool
    useDummyRoomList: bool

    ### Skybox And Sound ###

    # Skybox
    skyboxID: str
    skyboxConfig: str

    # Sound
    sequenceID: str
    ambienceID: str
    specID: str

    ### Camera And World Map ###

    # World Map
    worldMapLocation: str

    # Camera
    sceneCamType: str


@dataclass
class OOTSceneHeaderLighting(SceneCommon):
    envLightMode: str = None
    settings: list[EnvLightSettings] = field(default_factory=list)
    name: str = None

    def __post_init__(self):
        self.name = f"{self.headerName}_lightSettings"

    def getEnvLightSettingsC(self):
        lightSettingsC = CData()
        lightName = f"EnvLightSettings {self.name}[{len(self.settings)}]"

        # .h
        lightSettingsC.header = f"extern {lightName};\n"

        # .c
        lightSettingsC.source = (
            (lightName + " = {\n")
            + "".join(light.getLightSettingsEntry(i) for i, light in enumerate(self.settings))
            + "};\n\n"
        )

        return lightSettingsC


@dataclass
class OOTSceneHeaderCutscene:
    writeType: str
    writeCutscene: bool
    csObj: Object
    csWriteCustom: str
    extraCutscenes: list[Object]
    name: str = None


@dataclass
class OOTSceneHeaderExits(SceneCommon):
    exitList: list[tuple[int, str]] = field(default_factory=list)
    name: str = None

    def __post_init__(self):
        self.name = f"{self.headerName}_exitList"

    def getExitListC(self):
        exitListC = CData()
        listName = f"u16 {self.name}[{len(self.exitList)}]"

        # .h
        exitListC.header = f"extern {listName};\n"

        # .c
        exitListC.source = (
            (listName + " = {\n")
            # @TODO: use the enum name instead of the raw index
            + "\n".join(indent + f"{value}," for (_, value) in self.exitList)
            + "\n};\n\n"
        )

        return exitListC


@dataclass
class OOTSceneHeaderActors(SceneCommon):
    transitionActorList: list[TransitionActor] = field(default_factory=list)
    entranceActorList: list[EntranceActor] = field(default_factory=list)

    entranceListName: str = None
    startPositionsName: str = None
    transActorListName: str = None

    def __post_init__(self):
        self.entranceListName = f"{self.headerName}_entranceList"
        self.startPositionsName = f"{self.headerName}_playerEntryList"
        self.transActorListName = f"{self.headerName}_transitionActors"

    def getSpawnActorListC(self):
        """Returns the spawn actor list for the current header"""
        spawnActorList = CData()
        listName = f"ActorEntry {self.startPositionsName}"

        # .h
        spawnActorList.header = f"extern {listName}[];\n"

        # .c
        spawnActorList.source = (
            (f"{listName}[]" + " = {\n")
            + "".join(entrance.getActorEntry() for entrance in self.entranceActorList)
            + "};\n\n"
        )

        return spawnActorList

    def getSpawnListC(self):
        """Returns the spawn list for the current header"""
        spawnList = CData()
        listName = f"Spawn {self.entranceListName}"

        # .h
        spawnList.header = f"extern {listName}[];\n"

        # .c
        spawnList.source = (
            (f"{listName}[]" + " = {\n")
            + (indent + "// { Spawn Actor List Index, Room Index }\n")
            + "".join(entrance.getSpawnEntry() for entrance in self.entranceActorList)
            + "};\n\n"
        )

        return spawnList

    def getTransActorListC(self):
        """Returns the transition actor list for the current header"""
        transActorList = CData()
        listName = f"TransitionActorEntry {self.transActorListName}"

        # .h
        transActorList.header = f"extern {listName}[];\n"

        # .c
        transActorList.source = (
            (f"{listName}[]" + " = {\n")
            + "\n".join(transActor.getTransitionActorEntry() for transActor in self.transitionActorList)
            + "};\n\n"
        )

        return transActorList


@dataclass
class OOTSceneAlternateHeader:
    name: str
    childNight: "OOTSceneHeader" = None
    adultDay: "OOTSceneHeader" = None
    adultNight: "OOTSceneHeader" = None
    cutscenes: list["OOTSceneHeader"] = field(default_factory=list)


@dataclass
class OOTSceneHeader:
    infos: OOTSceneHeaderInfos
    lighting: OOTSceneHeaderLighting
    cutscene: OOTSceneHeaderCutscene
    exits: OOTSceneHeaderExits
    actors: OOTSceneHeaderActors

    def getHeaderC(self):
        headerData = CData()

        # Write the spawn position list data and the entrance list
        if len(self.actors.entranceActorList) > 0:
            headerData.append(self.actors.getSpawnActorListC())
            headerData.append(self.actors.getSpawnListC())

        # Write the transition actor list data
        if len(self.actors.transitionActorList) > 0:
            headerData.append(self.actors.getTransActorListC())

        # Write the exit list
        if len(self.exits.exitList) > 0:
            headerData.append(self.exits.getExitListC())

        # Write the light data
        if len(self.lighting.settings) > 0:
            headerData.append(self.lighting.getEnvLightSettingsC())

        # Write the path data, if used
        # if len(self.pathList) > 0:
        #     headerData.append(getPathData(header, headerIndex))

        return headerData


@dataclass
class OOTScene(Common, OOTSceneCommands):
    name: str = None
    headerIndex: int = None
    headerName: str = None
    mainHeader: OOTSceneHeader = None
    altHeader: OOTSceneAlternateHeader = None
    roomList: list[OOTRoom] = field(default_factory=list)
    roomListName: str = None

    def __post_init__(self):
        self.roomListName = f"{self.name}_roomList"

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
        return (
            self.altHeader is not None
            and self.altHeader.childNight is not None
            and self.altHeader.adultDay is not None
            and self.altHeader.adultNight is not None
            and len(self.altHeader.cutscenes) > 0
        )

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

            if not self.isCurrentHeaderValid(transActorProp.actor, self.headerIndex):
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
            if not self.isCurrentHeaderValid(entranceProp.actor, self.headerIndex):
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

    def getNewSceneHeader(self, headerProp: OOTSceneHeaderProperty, headerIndex: int = 0):
        """Returns a single scene header with the informations from the scene empty object"""

        self.headerIndex = headerIndex
        self.headerName = f"{self.name}_header{self.headerIndex:02}"

        if headerProp.csWriteType == "Embedded":
            raise PluginError("ERROR: 'Embedded' CS Write Type is not supported!")

        lightMode = self.getPropValue(headerProp, "skyboxLighting")
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

        return OOTSceneHeader(
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
                self.headerName,
                lightMode,
                lightSettings,
            ),
            OOTSceneHeaderCutscene(
                headerProp.csWriteType,
                headerProp.writeCutscene,
                headerProp.csWriteObject,
                headerProp.csWriteCustom if headerProp.csWriteType == "Custom" else None,
                [csObj for csObj in headerProp.extraCutscenes],
            ),
            OOTSceneHeaderExits(self.headerName, self.getExitListFromProps(headerProp)),
            OOTSceneHeaderActors(
                self.headerName,
                self.getTransActorListFromProps(),
                self.getEntranceActorListFromProps(),
            ),
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

        headers: list[tuple[OOTSceneHeader, str]] = [
            (self.altHeader.childNight, "Child Night"),
            (self.altHeader.adultDay, "Adult Day"),
            (self.altHeader.adultNight, "Adult Night"),
        ]

        for i, csHeader in enumerate(self.altHeader.cutscenes):
            headers.append((csHeader, f"Cutscene No. {i + 1}"))

        altHeaderPtrs = "\n".join(
            indent + self.headerName + "," if curHeader is not None else indent + "NULL," if i < 4 else ""
            for i, (curHeader, _) in enumerate(headers, 1)
        )

        headers.insert(0, (self.mainHeader, "Child Day (Default)"))
        for i, (curHeader, headerDesc) in enumerate(headers):
            if curHeader is not None:
                sceneC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
                sceneC.append(self.getSceneCommandList(self, curHeader, i))

                if i == 0:
                    if self.hasAlternateHeaders():
                        altHeaderListName = f"SceneCmd* {self.altHeader.name}[]"
                        sceneC.header += f"extern {altHeaderListName};\n"
                        sceneC.source += altHeaderListName + " = {\n" + altHeaderPtrs + "\n};\n\n"

                    # Write the room segment list
                    sceneC.append(self.getRoomListC())

                sceneC.append(curHeader.getHeaderC())

        return sceneC
