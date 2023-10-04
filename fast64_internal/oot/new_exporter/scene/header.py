from dataclasses import dataclass, field
from bpy.types import Object
from ....utility import PluginError, CData, indent
from .classes import TransitionActor, EntranceActor, EnvLightSettings, Path


@dataclass
class OOTSceneHeaderInfos:
    """This class stores various scene header informations"""

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
class OOTSceneHeaderLighting:
    """This class hosts lighting data"""

    name: str
    envLightMode: str = None
    settings: list[EnvLightSettings] = field(default_factory=list)

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
class OOTSceneHeaderCutscene:
    """This class hosts cutscene data (unfinished)"""

    headerIndex: int
    writeType: str
    writeCutscene: bool
    csObj: Object
    csWriteCustom: str
    extraCutscenes: list[Object]
    name: str = None

    def __post_init__(self):
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
class OOTSceneHeaderExits:
    """This class hosts exit data"""

    name: str = None
    exitList: list[tuple[int, str]] = field(default_factory=list)

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
class OOTSceneHeaderActors:
    """This class handles scene actors (transition actors and entrance actors)"""

    entranceListName: str
    startPositionsName: str
    transActorListName: str

    transitionActorList: list[TransitionActor] = field(default_factory=list)
    entranceActorList: list[EntranceActor] = field(default_factory=list)

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
class OOTSceneHeaderPath:
    """This class hosts pathways array data"""

    name: str
    pathList: list[Path]

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
class OOTSceneAlternateHeader:
    """This class stores alternate header data for the scene"""

    name: str
    childNight: "OOTSceneHeader" = None
    adultDay: "OOTSceneHeader" = None
    adultNight: "OOTSceneHeader" = None
    cutscenes: list["OOTSceneHeader"] = field(default_factory=list)


@dataclass
class OOTSceneHeader:
    """This class defines a scene header"""

    name: str
    infos: OOTSceneHeaderInfos
    lighting: OOTSceneHeaderLighting
    cutscene: OOTSceneHeaderCutscene
    exits: OOTSceneHeaderExits
    actors: OOTSceneHeaderActors
    path: OOTSceneHeaderPath

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
