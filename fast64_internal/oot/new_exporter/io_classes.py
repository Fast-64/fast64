import os

from dataclasses import dataclass, field
from math import radians
from mathutils import Quaternion, Matrix
from bpy.types import Object
from ...utility import PluginError, CData, exportColor, ootGetBaseOrCustomLight, toAlnum, writeFile, indent
from ..oot_utility import ootConvertTranslation, ootConvertRotation
from ..scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ..room.properties import OOTRoomHeaderProperty
from ..actor.properties import OOTActorProperty
from ..oot_constants import ootData
from .commands import OOTRoomCommands, OOTSceneCommands

    
@dataclass
class Common:
    sceneObj: Object
    roomObj: Object
    transform: Matrix
    roomIndex: int
    sceneName: str

    def isCurrentHeaderValid(self, actorProp: OOTActorProperty, headerIndex: int):
        preset = actorProp.headerSettings.sceneSetupPreset

        if preset == "All Scene Setups" or (preset == "All Non-Cutscene Scene Setups" and headerIndex < 4):
            return True

        if preset == "Custom":
            if actorProp.headerSettings.childDayHeader and headerIndex == 0:
                return True
            if actorProp.headerSettings.childNightHeader and  headerIndex == 1:
                return True
            if actorProp.headerSettings.adultDayHeader and headerIndex == 2:
                return True
            if actorProp.headerSettings.adultNightHeader and  headerIndex == 3:
                return True
        
        return False

    def getPropValue(self, data, propName: str):
        """Returns ``data.propName`` or ``data.propNameCustom``"""

        value = getattr(data, propName)
        return value if value != "Custom" else getattr(data, f"{propName}Custom")
    
    def getConvertedTransformWithOrientation(self, transformMatrix, sceneObj, obj, orientation):
        relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
        blenderTranslation, blenderRotation, scale = relativeTransform.decompose()
        rotation = blenderRotation @ orientation
        convertedTranslation = ootConvertTranslation(blenderTranslation)
        convertedRotation = ootConvertRotation(rotation)

        return convertedTranslation, convertedRotation, scale, rotation

    def getConvertedTransform(self, transformMatrix, sceneObj, obj, handleOrientation):
        # Hacky solution to handle Z-up to Y-up conversion
        # We cannot apply rotation to empty, as that modifies scale
        if handleOrientation:
            orientation = Quaternion((1, 0, 0), radians(90.0))
        else:
            orientation = Matrix.Identity(4)
        return self.getConvertedTransformWithOrientation(transformMatrix, sceneObj, obj, orientation)
    
    def getAltHeaderListCmd(self, altName):
        return indent + f"SCENE_CMD_ALTERNATE_HEADER_LIST({altName}),\n"

    def getEndCmd(self):
        return indent + "SCENE_CMD_END(),\n"


@dataclass
class Actor:
    name: str = None
    id: str = None
    pos: list[int] = field(default_factory=list)
    rot: str = None
    params: str = None

    def getActorEntry(self):
        """Returns a single actor entry"""
        posData = "{ " + ", ".join(f"{round(p)}" for p in self.pos) + " }"
        rotData = "{ " + self.rot + " }"

        actorInfos = [self.id, posData, rotData, self.params]
        infoDescs = ["Actor ID", "Position", "Rotation", "Parameters"]

        return (
            indent
            + (f"// {self.name}\n" + indent if self.name != "" else "")
            + "{\n"
            + ",\n".join((indent * 2) + f"/* {desc:10} */ {info}" for desc, info in zip(infoDescs, actorInfos))
            + ("\n" + indent + "},\n")
        )


@dataclass
class TransitionActor(Actor):
    dontTransition: bool = None
    roomFrom: int = None
    roomTo: int = None
    cameraFront: str = None
    cameraBack: str = None

    def getTransitionActorEntry(self):
        """Returns a single transition actor entry"""
        sides = [(self.roomFrom, self.cameraFront), (self.roomTo, self.cameraBack)]
        roomData = "{ " + ", ".join(f"{room}, {cam}" for room, cam in sides) + " }"
        posData = "{ " + ", ".join(f"{round(pos)}" for pos in self.pos) + " }"

        actorInfos = [roomData, self.id, posData, self.rot, self.params]
        infoDescs = ["Room & Cam Index (Front, Back)", "Actor ID", "Position", "Rotation Y", "Parameters"]

        return (
            (indent + f"// {self.name}\n" + indent if self.name != "" else "")
            + "{\n"
            + ",\n".join((indent * 2) + f"/* {desc:30} */ {info}" for desc, info in zip(infoDescs, actorInfos))
            + ("\n" + indent + "},\n")
        )


@dataclass
class EntranceActor(Actor):
    roomIndex: int = None
    spawnIndex: int = None

    def getSpawnEntry(self):
        """Returns a single spawn entry"""
        return indent + "{ " + f"{self.spawnIndex}, {self.roomIndex}" + " },\n"


### EXPORT UTILITY ###

@dataclass
class OOTRoomData:
    name: str
    roomMain: str = None
    roomModel: str = None
    roomModelInfo: str = None


@dataclass
class OOTSceneData:
    sceneMain: str = None
    sceneCollision: str = None


@dataclass
class OOTExporter:
    scene: "OOTScene"
    path: str

    header: str = ""
    sceneData: OOTSceneData = None
    roomList: dict[int, OOTRoomData] = field(default_factory=dict)
    csList: dict[int, str] = field(default_factory=dict)

    def setRoomListData(self):
        for room in self.scene.roomList:
            roomData = OOTRoomData(room.getRoomName())
            roomMainData = room.getRoomData()

            roomData.roomMain = roomMainData.source
            self.header += roomMainData.header

            self.roomList[room.roomIndex] = roomData
    
    def setSceneData(self):
        sceneData = OOTSceneData()
        sceneMainData = self.scene.getSceneData()

        sceneData.sceneMain = sceneMainData.source
        self.header += sceneMainData.header
        self.sceneData = sceneData

    def writeScene(self):
        scenePath = os.path.join(self.path, self.scene.getSceneName() + ".c")
        writeFile(scenePath, self.sceneData.sceneMain)

        for room in self.roomList.values():
            roomPath = os.path.join(self.path, room.name + ".c")
            writeFile(roomPath, room.roomMain)


### ROOM ###

@dataclass
class RoomCommon:
    roomName: str

@dataclass
class OOTRoomGeneral:
    ### General ###

    index: int
    roomShape: str

    ### Behavior ###

    roomBehavior: str
    playerIdleType: str
    disableWarpSongs: bool
    showInvisActors: bool

    ### Skybox And Time ###

    disableSky: bool
    disableSunMoon: bool
    hour: int
    minute: int
    timeSpeed: float
    echo: str

    ### Wind ###

    setWind: bool
    direction: tuple[int, int, int]
    strength: int


@dataclass
class OOTRoomObjects(RoomCommon):
    objectList: list[str]

    def objectListName(self, headerIndex: int):
        return f"{self.roomName}_header{headerIndex:02}_objectList"

    def getObjectLengthDefineName(self, headerIndex: int):
        return f"LENGTH_{self.objectListName(headerIndex).upper()}"
    
    def getObjectList(self, headerIndex: int):
        objectList = CData()

        listName = f"s16 {self.objectListName(headerIndex)}"

        # .h
        objectList.header = f"extern {listName}[];\n"

        # .c
        objectList.source = (
            (f"{listName}[{self.getObjectLengthDefineName(headerIndex)}]" + " = {\n")
            + ",\n".join(indent + objectID for objectID in self.objectList)
            + ",\n};\n\n"
        )

        return objectList


@dataclass
class OOTRoomActors(RoomCommon):
    actorList: list[Actor]

    def actorListName(self, headerIndex: int):
        return f"{self.roomName}_header{headerIndex:02}_actorList"

    def getActorLengthDefineName(self, headerIndex: int):
        return f"LENGTH_{self.actorListName(headerIndex).upper()}"
    
    def getActorListData(self, headerIndex: int):
        """Returns the actor list for the current header"""
        actorList = CData()
        listName = f"ActorEntry {self.actorListName(headerIndex)}"

        # .h
        actorList.header = f"extern {listName}[];\n"

        # .c
        actorList.source = (
            (f"{listName}[{self.getActorLengthDefineName(headerIndex)}]" + " = {\n")
            + "\n".join(actor.getActorEntry() for actor in self.actorList)
            + "};\n\n"
        )

        return actorList


@dataclass
class OOTRoomAlternate:
    childNight: "OOTRoomHeader" = None
    adultDay: "OOTRoomHeader" = None
    adultNight: "OOTRoomHeader" = None
    cutscene: list["OOTRoomHeader"] = field(default_factory=list)


@dataclass
class OOTRoomHeader(RoomCommon):
    general: OOTRoomGeneral
    objects: OOTRoomObjects
    actors: OOTRoomActors

    def getHeaderDefines(self, headerIndex: int):
        """Returns a string containing defines for actor and object lists lengths"""
        headerDefines = ""

        if len(self.objects.objectList) > 0:
            name = self.objects.getObjectLengthDefineName(headerIndex)
            headerDefines += f"#define {name} {len(self.objects.objectList)}\n"

        if len(self.actors.actorList) > 0:
            name = self.actors.getActorLengthDefineName(headerIndex)
            headerDefines += f"#define {name} {len(self.actors.actorList)}\n"

        return headerDefines


@dataclass
class OOTRoom(Common):
    header: OOTRoomHeader = None
    alternate: OOTRoomAlternate = None

    def hasAlternateHeaders(self):
        return (
            self.alternate is not None and 
            self.alternate.childNight is not None and
            self.alternate.adultDay is not None and
            self.alternate.adultNight is not None and
            len(self.alternate.cutscene) > 0
        )
    
    def getRoomHeader(self, headerIndex: int) -> OOTRoomHeader | None:
        if headerIndex == 0:
            return self.header
        
        for i, header in enumerate(self.altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.alternate, header)
        
        for i, csHeader in enumerate(self.alternate.cutscene, 4):
            if headerIndex == i:
                return csHeader

        return None

    def getActorList(self, headerIndex: int):
        actorList: list[Actor] = []
        actorObjList: list[Object] = [
            obj for obj in self.roomObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Actor"
        ]
        for obj in actorObjList:
            actorProp = obj.ootActorProperty
            if not self.isCurrentHeaderValid(actorProp, headerIndex):
                continue

            # The Actor list is filled with ``("None", f"{i} (Deleted from the XML)", "None")`` for
            # the total number of actors defined in the XML. If the user deletes one, this will prevent
            # any data loss as Blender saves the index of the element in the Actor list used for the EnumProperty
            # and not the identifier as defined by the first element of the tuple. Therefore, we need to check if
            # the current Actor has the ID `None` to avoid export issues.
            if actorProp.actorID != "None":
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                actor = Actor()

                if actorProp.actorID == "Custom":
                    actor.id = actorProp.actorIDCustom
                else:
                    actor.id = actorProp.actorID

                if actorProp.rotOverride:
                    actor.rot = ", ".join([actorProp.rotOverrideX, actorProp.rotOverrideY, actorProp.rotOverrideZ])
                else:
                    actor.rot = ", ".join(f"DEG_TO_BINANG({(r * (180 / 0x8000)):.3f})" for r in rot)

                actor.name = (
                    ootData.actorData.actorsByID[actorProp.actorID].name.replace(
                        f" - {actorProp.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if actorProp.actorID != "Custom"
                    else "Custom Actor"
                )

                actor.pos = pos
                actor.params = actorProp.actorParam
                actorList.append(actor)
        return actorList

    def getSingleRoomHeader(self, headerProp: OOTRoomHeaderProperty, headerIndex: int=0):
        """Returns a single room header with the informations from the scene empty object"""

        objIDList = []
        for objProp in headerProp.objectList:
            if objProp.objectKey == "Custom":
                objIDList.append(objProp.objectIDCustom)
            else:
                objIDList.append(ootData.objectData.objectsByKey[objProp.objectKey].id)

        return OOTRoomHeader(
            self.getRoomName(),
            OOTRoomGeneral(
                headerProp.roomIndex,
                headerProp.roomShape,
                self.getPropValue(headerProp, "roomBehaviour"),
                self.getPropValue(headerProp, "linkIdleMode"),
                headerProp.disableWarpSongs,
                headerProp.showInvisibleActors,
                headerProp.disableSkybox,
                headerProp.disableSunMoon,
                0xFF if headerProp.leaveTimeUnchanged else headerProp.timeHours,
                0xFF if headerProp.leaveTimeUnchanged else headerProp.timeMinutes,
                max(-128, min(127, round(headerProp.timeSpeed * 0xA))),
                headerProp.echo,
                headerProp.setWind,
                [d for d in headerProp.windVector] if headerProp.setWind else None,
                headerProp.windStrength if headerProp.setWind else None
            ),
            OOTRoomObjects(self.getRoomName(), objIDList),
            OOTRoomActors(
                self.getRoomName(),
                self.getActorList(headerIndex),
            )
        )
    
    # Export

    def getRoomName(self):
        return f"{toAlnum(self.sceneName)}_room_{self.roomIndex}"
    
    def alternateHeadersName(self):
        return f"{self.getRoomName()}_alternateHeaders"

    def getRoomData(self):
        cmdExport = OOTRoomCommands()
        roomC = CData()

        roomHeaders: list[tuple[OOTRoomHeader, str]] = [
            (self.alternate.childNight, "Child Night"),
            (self.alternate.adultDay, "Adult Day"),
            (self.alternate.adultNight, "Adult Night"),
        ]

        for i, csHeader in enumerate(self.alternate.cutscene):
            roomHeaders.append((csHeader, f"Cutscene No. {i + 1}"))

        altHeaderPtrListName = f"SceneCmd* {self.alternateHeadersName()}"

        # .h
        roomC.header = f"extern {altHeaderPtrListName}[];\n"

        # .c
        altHeaderPtrList = (
            f"{altHeaderPtrListName}[]"
            + " = {\n"
            + "\n".join(
                indent + f"{curHeader.roomName()}_header{i:02}," if curHeader is not None else indent + "NULL,"
                for i, (curHeader, headerDesc) in enumerate(roomHeaders, 1)
            )
            + "\n};\n\n"
        )

        roomHeaders.insert(0, (self.header, "Child Day (Default)"))
        for i, (curHeader, headerDesc) in enumerate(roomHeaders):
            if curHeader is not None:
                roomC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
                roomC.source += curHeader.getHeaderDefines(i)
                roomC.append(cmdExport.getRoomCommandList(self, i))

                if i == 0 and self.hasAlternateHeaders():
                    roomC.source += altHeaderPtrList

                if len(curHeader.objects.objectList) > 0:
                    roomC.append(curHeader.objects.getObjectList(i))

                if len(curHeader.actors.actorList) > 0:
                    roomC.append(curHeader.actors.getActorListData(i))

        return roomC


### SCENE ###

@dataclass
class SceneCommon:
    sceneName: str


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
            + "".join(indent * 2 + f"{'{ ' + vecToC(vector) + ' },':26} // {desc}\n" for (vector, desc, vecToC) in vectors)
            + "".join(indent * 2 + f"{fogValue + ',':26} // {fogDesc}\n" for fogValue, fogDesc in fogData)
            + (indent + "},\n")
        )

        return lightData


@dataclass
class OOTSceneGeneral:
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
class OOTSceneLighting:
    envLightMode: str
    settings: list[EnvLightSettings]

    def lightListName(self, headerName: str):
        return f"{headerName}_lightSettings"

    def getLightSettings(self, headerName: str):
        lightSettingsData = CData()
        lightName = f"EnvLightSettings {self.lightListName(headerName)}[{len(self.settings)}]"

        # .h
        lightSettingsData.header = f"extern {lightName};\n"

        # .c
        lightSettingsData.source = (
            (lightName + " = {\n")
            + "".join(
                light.getLightSettingsEntry(i)
                for i, light in enumerate(self.settings)
            )
            + "};\n\n"
        )

        return lightSettingsData


@dataclass
class OOTSceneCutscene:
    writeType: str
    writeCutscene: bool
    csObj: Object
    csWriteCustom: str
    extraCutscenes: list[Object]


@dataclass
class OOTSceneExits:
    exitList: list[tuple[int, str]]

    def exitListName(self, headerName: str):
        return f"{headerName}_exitList"

    def getExitListData(self, headerName: str):
        exitList = CData()
        listName = f"u16 {self.exitListName(headerName)}[{len(self.exitList)}]"

        # .h
        exitList.header = f"extern {listName};\n"

        # .c
        exitList.source = (
            (listName + " = {\n")
            # @TODO: use the enum name instead of the raw index
            + "\n".join(indent + f"{value}," for (_, value) in self.exitList)
            + "\n};\n\n"
        )

        return exitList


@dataclass
class OOTSceneActors:
    transitionActorList: list[TransitionActor]
    entranceActorList: list[EntranceActor]

    def entranceListName(self, headerName: str):
        return f"{headerName}_entranceList"
    
    def startPositionsName(self, headerName: str):
        return f"{headerName}_playerEntryList"
    
    def transitionActorListName(self, headerName: str):
        return f"{headerName}_transitionActors"
    
    def getSpawnActorList(self, headerName: str):
        """Returns the spawn actor list for the current header"""
        spawnActorList = CData()
        listName = f"ActorEntry {self.startPositionsName(headerName)}"

        # .h
        spawnActorList.header = f"extern {listName}[];\n"

        # .c
        spawnActorList.source = (
            (f"{listName}[]" + " = {\n")
            + "".join(entrance.getActorEntry() for entrance in self.entranceActorList)
            + "};\n\n"
        )

        return spawnActorList

    def getSpawnList(self, headerName: str):
        """Returns the spawn list for the current header"""
        spawnList = CData()
        listName = f"Spawn {self.entranceListName(headerName)}"

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
    
    def getTransitionActorListData(self, headerName: str):
        """Returns the transition actor list for the current header"""
        transActorList = CData()
        listName = f"TransitionActorEntry {self.transitionActorListName(headerName)}"

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
class OOTSceneAlternate:
    childNight: "OOTSceneHeader" = None
    adultDay: "OOTSceneHeader" = None
    adultNight: "OOTSceneHeader" = None
    cutscene: list["OOTSceneHeader"] = field(default_factory=list)


@dataclass
class OOTSceneHeader:
    general: OOTSceneGeneral
    lighting: OOTSceneLighting
    cutscene: OOTSceneCutscene
    exits: OOTSceneExits
    actors: OOTSceneActors

    def getHeaderData(self, headerName: str):
        headerData = CData()

        # Write the spawn position list data and the entrance list
        if len(self.actors.entranceActorList) > 0:
            headerData.append(self.actors.getSpawnActorList(headerName))
            headerData.append(self.actors.getSpawnList(headerName))

        # Write the transition actor list data
        if len(self.actors.transitionActorList) > 0:
            headerData.append(self.actors.getTransitionActorListData(headerName))

        # Write the exit list
        if len(self.exits.exitList) > 0:
            headerData.append(self.exits.getExitListData(headerName))

        # Write the light data
        if len(self.lighting.settings) > 0:
            headerData.append(self.lighting.getLightSettings(headerName))

        # Write the path data, if used
        # if len(self.pathList) > 0:
        #     headerData.append(getPathData(header, headerIndex))

        return headerData


@dataclass
class OOTScene(Common):
    header: OOTSceneHeader = None
    alternate: OOTSceneAlternate = None
    roomList: list[OOTRoom] = field(default_factory=list)

    altHeaderList: list[str] = field(default_factory=lambda: ["childNight", "adultDay", "adultNight"])

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
            self.alternate is not None and 
            self.alternate.childNight is not None and
            self.alternate.adultDay is not None and
            self.alternate.adultNight is not None and
            len(self.alternate.cutscene) > 0
        )
    
    def getSceneHeader(self, headerIndex: int) -> OOTSceneHeader | None:
        if headerIndex == 0:
            return self.header
        
        for i, header in enumerate(self.altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.alternate, header)
        
        for i, csHeader in enumerate(self.alternate.cutscene, 4):
            if headerIndex == i:
                return csHeader

        return None
    
    def getExitList(self, headerProp: OOTSceneHeaderProperty):
        """Returns the exit list and performs safety checks"""

        exitList: list[tuple[int, str]] = []

        for i, exitProp in enumerate(headerProp.exitList):
            if exitProp.exitIndex != "Custom":
                raise PluginError("ERROR: Exits are unfinished, please use 'Custom'.")

            exitList.append((i, exitProp.exitIndexCustom))
        
        return exitList

    def getRoomObject(self, object: Object) -> Object | None:
        # Note: temporary solution until PRs #243 & #255 are merged
        for obj in self.sceneObj.children_recursive:
            if obj.type == "EMPTY" and obj.ootEmptyType == "Room":
                for o in obj.children_recursive:
                    if o == object:
                        return obj
        return None

    def getTransitionActorList(self, headerIndex: int):
        actorList: list[TransitionActor] = []
        actorObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "EMPTY" and obj.ootEmptyType == "Transition Actor"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObject(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")
            self.roomIndex = roomObj.ootRoomHeader.roomIndex

            transActorProp = obj.ootTransitionActorProperty

            if not self.isCurrentHeaderValid(transActorProp.actor, headerIndex):
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

    def getEntranceActorList(self, headerIndex: int):
        actorList: list[EntranceActor] = []
        actorObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "EMPTY" and obj.ootEmptyType == "Entrance"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObject(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")

            entranceProp = obj.ootEntranceProperty
            if not self.isCurrentHeaderValid(entranceProp.actor, headerIndex):
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

    def getSingleSceneHeader(self, headerProp: OOTSceneHeaderProperty, headerIndex: int=0):
        """Returns a single scene header with the informations from the scene empty object"""

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
                    lightProp.transitionSpeed
                )
            )

        return OOTSceneHeader(
            OOTSceneGeneral(
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
                self.getPropValue(headerProp, "cameraMode")
            ),
            OOTSceneLighting(
                lightMode,
                lightSettings,
            ),
            OOTSceneCutscene(
                headerProp.csWriteType,
                headerProp.writeCutscene,
                headerProp.csWriteObject,
                headerProp.csWriteCustom if headerProp.csWriteType == "Custom" else None,
                [csObj for csObj in headerProp.extraCutscenes]
            ),
            OOTSceneExits(self.getExitList(headerProp)),
            OOTSceneActors(
                self.getTransitionActorList(headerIndex),
                self.getEntranceActorList(headerIndex)
            )
        )
    
    # Export

    def getSceneName(self):
        return f"{toAlnum(self.sceneName)}_scene"

    def getHeaderName(self, headerIndex: int):
        return f"{self.getSceneName()}_header{headerIndex:02}"
    
    def alternateHeadersName(self):
        return f"{self.getSceneName()}_alternateHeaders"

    def roomListName(self):
        return f"{self.getSceneName()}_roomList"

    def getRoomList(self):
        roomList = CData()
        listName = f"RomFile {self.roomListName()}[]"

        # generating segment rom names for every room
        segNames = []
        for i in range(len(self.roomList)):
            roomName = self.roomList[i].getRoomName()
            segNames.append((f"_{roomName}SegmentRomStart", f"_{roomName}SegmentRomEnd"))

        # .h
        roomList.header += f"extern {listName};\n"

        if not self.header.general.useDummyRoomList:
            # Write externs for rom segments
            roomList.header += "".join(
                f"extern u8 {startName}[];\n" + f"extern u8 {stopName}[];\n" for startName, stopName in segNames
            )

        # .c
        roomList.source = listName + " = {\n"

        if self.header.general.useDummyRoomList:
            roomList.source = (
                "// Dummy room list\n" + roomList.source + ((indent + "{ NULL, NULL },\n") * len(self.roomList))
            )
        else:
            roomList.source += (
                " },\n".join(
                    indent + "{ " + f"(uintptr_t){startName}, (uintptr_t){stopName}" 
                    for startName, stopName in segNames
                )
                + " },\n"
            )

        roomList.source += "};\n\n"
        return roomList

    def getSceneData(self):
        cmdExport = OOTSceneCommands()
        sceneC = CData()

        headers: list[tuple[OOTSceneHeader, str]] = [
            (self.alternate.childNight, "Child Night"),
            (self.alternate.adultDay, "Adult Day"),
            (self.alternate.adultNight, "Adult Night"),
        ]

        for i, csHeader in enumerate(self.alternate.cutscene):
            headers.append((csHeader, f"Cutscene No. {i + 1}"))

        altHeaderPtrs = "\n".join(
            indent + self.getHeaderName(i) + ","
            if curHeader is not None
            else indent + "NULL,"
            if i < 4
            else ""
            for i, (curHeader, _) in enumerate(headers, 1)
        )

        headers.insert(0, (self.header, "Child Day (Default)"))
        for i, (curHeader, headerDesc) in enumerate(headers):
            if curHeader is not None:
                sceneC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
                sceneC.append(cmdExport.getSceneCommandList(self, curHeader, i))

                if i == 0:
                    if self.hasAlternateHeaders():
                        altHeaderListName = f"SceneCmd* {self.alternateHeadersName()}[]"
                        sceneC.header += f"extern {altHeaderListName};\n"
                        sceneC.source += altHeaderListName + " = {\n" + altHeaderPtrs + "\n};\n\n"

                    # Write the room segment list
                    sceneC.append(self.getRoomList())

                sceneC.append(curHeader.getHeaderData(self.getHeaderName(i)))

        return sceneC
