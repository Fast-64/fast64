from dataclasses import dataclass, field
from bpy.types import Object
from ...utility import PluginError, CData, indent
from .common import TransitionActor, EntranceActor


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
class Path:
    name: str
    points: list[tuple[int, int, int]] = field(default_factory=list)

    def getPathPointListC(self):
        pathData = CData()
        pathName = f"Vec3s {self.name}"

        # .h
        pathData.header = f"extern {pathName}[];\n"

        # .c
        pathData.source = (
            f"{pathName}[]"
            + " = {\n"
            + "\n".join(
                indent + "{ " + ", ".join(f"{round(curPoint):5}" for curPoint in point) + " }," for point in self.points
            )
            + "\n};\n\n"
        )

        return pathData


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
class OOTSceneHeaderLighting:
    name: str
    envLightMode: str = None
    settings: list[EnvLightSettings] = field(default_factory=list)

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
    name: str = None
    exitList: list[tuple[int, str]] = field(default_factory=list)

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
class OOTSceneHeaderActors:
    entranceListName: str
    startPositionsName: str
    transActorListName: str

    transitionActorList: list[TransitionActor] = field(default_factory=list)
    entranceActorList: list[EntranceActor] = field(default_factory=list)

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
class OOTSceneHeaderPath:
    name: str
    pathList: list[Path]

    def getPathC(self):
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
    name: str
    childNight: "OOTSceneHeader" = None
    adultDay: "OOTSceneHeader" = None
    adultNight: "OOTSceneHeader" = None
    cutscenes: list["OOTSceneHeader"] = field(default_factory=list)


@dataclass
class OOTSceneHeader:
    name: str
    infos: OOTSceneHeaderInfos
    lighting: OOTSceneHeaderLighting
    cutscene: OOTSceneHeaderCutscene
    exits: OOTSceneHeaderExits
    actors: OOTSceneHeaderActors
    path: OOTSceneHeaderPath

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
        if len(self.path.pathList) > 0:
            headerData.append(self.path.getPathC())

        return headerData
