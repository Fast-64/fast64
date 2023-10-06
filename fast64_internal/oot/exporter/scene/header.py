from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from ....utility import PluginError, CData, exportColor, ootGetBaseOrCustomLight, indent
from ...oot_constants import ootData
from ...scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ..base import Base
from .classes import TransitionActor, EntranceActor, EnvLightSettings, Path


@dataclass
class HeaderBase(Base):
    props: OOTSceneHeaderProperty


@dataclass
class SceneInfos(HeaderBase):
    """This class stores various scene header informations"""

    sceneObj: Object

    ### General ###

    keepObjectID: str = None
    naviHintType: str = None
    drawConfig: str = None
    appendNullEntrance: bool = None
    useDummyRoomList: bool = None

    ### Skybox And Sound ###

    # Skybox
    skyboxID: str = None
    skyboxConfig: str = None

    # Sound
    sequenceID: str = None
    ambienceID: str = None
    specID: str = None

    ### Camera And World Map ###

    # World Map
    worldMapLocation: str = None

    # Camera
    sceneCamType: str = None

    def __post_init__(self):
        self.keepObjectID = self.getPropValue(self.props, "globalObject")
        self.naviHintType = self.getPropValue(self.props, "naviCup")
        self.drawConfig = self.getPropValue(self.props.sceneTableEntry, "drawConfig")
        self.appendNullEntrance = self.props.appendNullEntrance
        self.useDummyRoomList = self.sceneObj.fast64.oot.scene.write_dummy_room_list
        self.skyboxID = self.getPropValue(self.props, "skyboxID")
        self.skyboxConfig = self.getPropValue(self.props, "skyboxCloudiness")
        self.sequenceID = self.getPropValue(self.props, "musicSeq")
        self.ambienceID = self.getPropValue(self.props, "nightSeq")
        self.specID = self.getPropValue(self.props, "audioSessionPreset")
        self.worldMapLocation = self.getPropValue(self.props, "mapLocation")
        self.sceneCamType = self.getPropValue(self.props, "cameraMode")


@dataclass
class SceneLighting(HeaderBase):
    """This class hosts lighting data"""

    name: str

    envLightMode: str = None
    settings: list[EnvLightSettings] = field(default_factory=list)

    def __post_init__(self):
        self.envLightMode = self.getPropValue(self.props, "skyboxLighting")
        lightList: list[OOTLightProperty] = []

        if self.envLightMode == "LIGHT_MODE_TIME":
            todLights = self.props.timeOfDayLights
            lightList = [todLights.dawn, todLights.day, todLights.dusk, todLights.night]
        else:
            lightList = self.props.lightList

        for lightProp in lightList:
            light1 = ootGetBaseOrCustomLight(lightProp, 0, True, True)
            light2 = ootGetBaseOrCustomLight(lightProp, 1, True, True)
            self.settings.append(
                EnvLightSettings(
                    self.envLightMode,
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

    def getEnvLightSettingsC(self):
        """Returns a ``CData`` containing the C data of env. light settings"""

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
class SceneCutscene(HeaderBase):
    """This class hosts cutscene data (unfinished)"""

    headerIndex: int

    writeType: str = None
    writeCutscene: bool = None
    csObj: Object = None
    csWriteCustom: str = None
    extraCutscenes: list[Object] = field(default_factory=list)
    name: str = None

    def __post_init__(self):
        self.writeType = self.props.csWriteType
        self.writeCutscene = self.props.writeCutscene
        self.csObj = self.props.csWriteObject
        self.csWriteCustom = self.props.csWriteCustom if self.props.csWriteType == "Custom" else None
        self.extraCutscenes = [csObj for csObj in self.props.extraCutscenes]

        if self.writeCutscene and self.writeType == "Embedded":
            raise PluginError("ERROR: 'Embedded' CS Write Type is not supported!")

        if self.headerIndex > 0 and len(self.extraCutscenes) > 0:
            raise PluginError("ERROR: Extra cutscenes can only belong to the main header!")

        if self.csObj is not None:
            self.name = self.csObj.name.removeprefix("Cutscene.")

            if self.csObj.ootEmptyType != "Cutscene":
                raise PluginError("ERROR: Object selected as cutscene is wrong type, must be empty with Cutscene type")
            elif self.csObj.parent is not None:
                raise PluginError("ERROR: Cutscene empty object should not be parented to anything")
        else:
            raise PluginError("ERROR: No object selected for cutscene reference")

    def getCutsceneC(self):
        # will be implemented when PR #208 is merged
        cutsceneData = CData()
        return cutsceneData


@dataclass
class SceneExits(HeaderBase):
    """This class hosts exit data"""

    name: str
    exitList: list[tuple[int, str]] = field(default_factory=list)

    def __post_init__(self):
        for i, exitProp in enumerate(self.props.exitList):
            if exitProp.exitIndex != "Custom":
                raise PluginError("ERROR: Exits are unfinished, please use 'Custom'.")
            self.exitList.append((i, exitProp.exitIndexCustom))

    def getExitListC(self):
        """Returns a ``CData`` containing the C data of the exit array"""

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
class SceneActors(HeaderBase):
    """This class handles scene actors (transition actors and entrance actors)"""

    sceneObj: Object
    transform: Matrix
    headerIndex: int
    entranceListName: str
    startPositionsName: str
    transActorListName: str

    transitionActorList: list[TransitionActor] = field(default_factory=list)
    entranceActorList: list[EntranceActor] = field(default_factory=list)

    def initTransActorList(self):
        """Returns the transition actor list based on empty objects with the type 'Transition Actor'"""

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

            if (
                self.isCurrentHeaderValid(transActorProp.actor.headerSettings, self.headerIndex)
                and transActorProp.actor.actorID != "None"
            ):
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
                self.transitionActorList.append(transActor)

    def initEntranceActorList(self):
        """Returns the entrance actor list based on empty objects with the type 'Entrance'"""

        entranceActorFromIndex: dict[int, EntranceActor] = {}
        actorObjList: list[Object] = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Entrance"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObjectFromChild(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")

            entranceProp = obj.ootEntranceProperty
            if (
                self.isCurrentHeaderValid(entranceProp.actor.headerSettings, self.headerIndex)
                and entranceProp.actor.actorID != "None"
            ):
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

                if not entranceProp.spawnIndex in entranceActorFromIndex:
                    entranceActorFromIndex[entranceProp.spawnIndex] = entranceActor
                else:
                    raise PluginError(f"ERROR: Repeated Spawn Index: {entranceProp.spawnIndex}")

        entranceActorFromIndex = dict(sorted(entranceActorFromIndex.items()))
        if list(entranceActorFromIndex.keys()) != list(range(len(entranceActorFromIndex))):
            raise PluginError("ERROR: The spawn indices are not consecutive!")

        self.entranceActorList = list(entranceActorFromIndex.values())

    def __post_init__(self):
        self.initTransActorList()
        self.initEntranceActorList()

    def getSpawnActorListC(self):
        """Returns the spawn actor array"""

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
        """Returns the spawn array"""

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
        """Returns the transition actor array"""

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
class ScenePathways(HeaderBase):
    """This class hosts pathways array data"""

    name: str
    sceneObj: Object
    transform: Matrix
    headerIndex: int

    pathList: list[Path] = field(default_factory=list)

    def __post_init__(self):
        pathObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Path"
        ]

        for i, obj in enumerate(pathObjList):
            isHeaderValid = self.isCurrentHeaderValid(obj.ootSplineProperty.headerSettings, self.headerIndex)
            if isHeaderValid and self.validateCurveData(obj):
                self.pathList.append(
                    Path(
                        f"{self.name}List{i:02}",
                        [self.transform @ point.co.xyz for point in obj.data.splines[0].points],
                    )
                )

    def getPathC(self):
        """Returns a ``CData`` containing the C data of the pathway array"""

        pathData = CData()
        pathListData = CData()
        listName = f"Path {self.name}[{len(self.pathList)}]"

        # .h
        pathListData.header = f"extern {listName};\n"

        # .c
        pathListData.source = listName + " = {\n"

        for path in self.pathList:
            pathListData.source += indent + "{ " + f"ARRAY_COUNTU({path.name}), {path.name}" + " },\n"
            pathData.append(path.getPathPointListC())

        pathListData.source += "};\n\n"
        pathData.append(pathListData)

        return pathData


@dataclass
class SceneHeader(HeaderBase):
    """This class defines a scene header"""

    name: str
    sceneObj: Object
    transform: Matrix
    headerIndex: int

    infos: SceneInfos = None
    lighting: SceneLighting = None
    cutscene: SceneCutscene = None
    exits: SceneExits = None
    actors: SceneActors = None
    path: ScenePathways = None

    def __post_init__(self):
        self.infos = SceneInfos(self.props, self.sceneObj)
        self.lighting = SceneLighting(self.props, f"{self.name}_lightSettings")
        if self.props.writeCutscene:
            self.cutscene = SceneCutscene(self.props, self.headerIndex)
        self.exits = SceneExits(self.props, f"{self.name}_exitList")
        self.actors = SceneActors(
            self.props,
            self.sceneObj,
            self.transform,
            self.headerIndex,
            f"{self.name}_entranceList",
            f"{self.name}_playerEntryList",
            f"{self.name}_transitionActors",
        )
        self.path = ScenePathways(self.props, f"{self.name}_pathway", self.sceneObj, self.transform, self.headerIndex)

    def getHeaderC(self):
        """Returns the ``CData`` containing the header's data"""

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
        if len(self.path.pathList) > 0:
            headerData.append(self.path.getPathC())

        return headerData


@dataclass
class SceneAlternateHeader:
    """This class stores alternate header data for the scene"""

    name: str
    childNight: SceneHeader = None
    adultDay: SceneHeader = None
    adultNight: SceneHeader = None
    cutscenes: list[SceneHeader] = field(default_factory=list)
