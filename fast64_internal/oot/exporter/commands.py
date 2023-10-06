from ...utility import CData, indent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .collision import CollisionHeader
    from .room import Room, RoomInfos, RoomObjects, RoomActors
    from .scene import (
        Scene,
        SceneInfos,
        SceneHeader,
        SceneLighting,
        SceneCutscene,
        SceneActors,
        ScenePathways,
    )


class RoomCommands:
    """This class defines the command list for rooms"""

    def getEchoSettingsCmd(self, infos: "RoomInfos"):
        return indent + f"SCENE_CMD_ECHO_SETTINGS({infos.echo})"

    def getRoomBehaviourCmd(self, infos: "RoomInfos"):
        showInvisibleActors = "true" if infos.showInvisActors else "false"
        disableWarpSongs = "true" if infos.disableWarpSongs else "false"

        return (
            (indent + "SCENE_CMD_ROOM_BEHAVIOR(")
            + ", ".join([infos.roomBehavior, infos.playerIdleType, showInvisibleActors, disableWarpSongs])
            + ")"
        )

    def getSkyboxDisablesCmd(self, infos: "RoomInfos"):
        disableSkybox = "true" if infos.disableSky else "false"
        disableSunMoon = "true" if infos.disableSunMoon else "false"

        return indent + f"SCENE_CMD_SKYBOX_DISABLES({disableSkybox}, {disableSunMoon})"

    def getTimeSettingsCmd(self, infos: "RoomInfos"):
        return indent + f"SCENE_CMD_TIME_SETTINGS({infos.hour}, {infos.minute}, {infos.timeSpeed})"

    def getWindSettingsCmd(self, infos: "RoomInfos"):
        return (
            indent + f"SCENE_CMD_WIND_SETTINGS({', '.join(f'{dir}' for dir in infos.direction)}, {infos.strength}),\n"
        )

    def getRoomShapeCmd(self, room: "Room"):
        return indent + f"SCENE_CMD_ROOM_SHAPE(&{room.roomShape.getName()}),\n"

    def getObjectListCmd(self, objects: "RoomObjects"):
        return (indent + "SCENE_CMD_OBJECT_LIST(") + f"{objects.getDefineName()}, {objects.name}),\n"

    def getActorListCmd(self, actors: "RoomActors"):
        return (indent + "SCENE_CMD_ACTOR_LIST(") + f"{actors.getDefineName()}, {actors.name}),\n"

    def getRoomCommandList(self, room: "Room", headerIndex: int):
        cmdListData = CData()
        curHeader = room.getRoomHeaderFromIndex(headerIndex)
        listName = f"SceneCmd {curHeader.name}"

        getCmdFuncInfosList = [
            self.getEchoSettingsCmd,
            self.getRoomBehaviourCmd,
            self.getSkyboxDisablesCmd,
            self.getTimeSettingsCmd,
        ]

        if curHeader.infos.setWind:
            getCmdFuncInfosList.append(self.getWindSettingsCmd)

        hasAltHeaders = headerIndex == 0 and room.hasAlternateHeaders
        roomCmdData = (
            (room.getAltHeaderListCmd(room.altHeader.name) if hasAltHeaders else "")
            + self.getRoomShapeCmd(room)
            + (self.getObjectListCmd(curHeader.objects) if len(curHeader.objects.objectList) > 0 else "")
            + (self.getActorListCmd(curHeader.actors) if len(curHeader.actors.actorList) > 0 else "")
            + (",\n".join(getCmd(curHeader.infos) for getCmd in getCmdFuncInfosList) + ",\n")
            + room.getEndCmd()
        )

        # .h
        cmdListData.header = f"extern {listName}[];\n"

        # .c
        cmdListData.source = f"{listName}[]" + " = {\n" + roomCmdData + "};\n\n"

        return cmdListData


class SceneCommands:
    """This class defines the command list for scenes"""

    def getSoundSettingsCmd(self, infos: "SceneInfos"):
        return indent + f"SCENE_CMD_SOUND_SETTINGS({infos.specID}, {infos.ambienceID}, {infos.sequenceID})"

    def getRoomListCmd(self, scene: "Scene"):
        return indent + f"SCENE_CMD_ROOM_LIST({len(scene.roomList)}, {scene.roomListName}),\n"

    def getTransActorListCmd(self, actors: "SceneActors"):
        return (
            indent + "SCENE_CMD_TRANSITION_ACTOR_LIST("
        ) + f"{len(actors.transitionActorList)}, {actors.transActorListName})"

    def getMiscSettingsCmd(self, infos: "SceneInfos"):
        return indent + f"SCENE_CMD_MISC_SETTINGS({infos.sceneCamType}, {infos.worldMapLocation})"

    def getColHeaderCmd(self, colHeader: "CollisionHeader"):
        return indent + f"SCENE_CMD_COL_HEADER(&{colHeader.name}),\n"

    def getSpawnListCmd(self, actors: "SceneActors"):
        return (
            indent + "SCENE_CMD_ENTRANCE_LIST("
        ) + f"{actors.entranceListName if len(actors.entranceActorList) > 0 else 'NULL'})"

    def getSpecialFilesCmd(self, infos: "SceneInfos"):
        return indent + f"SCENE_CMD_SPECIAL_FILES({infos.naviHintType}, {infos.keepObjectID})"

    def getPathListCmd(self, path: "ScenePathways"):
        return indent + f"SCENE_CMD_PATH_LIST({path.name}),\n" if len(path.pathList) > 0 else ""

    def getSpawnActorListCmd(self, scene: "Scene", headerIndex: int):
        curHeader = scene.getSceneHeaderFromIndex(headerIndex)
        startPosName = curHeader.actors.startPositionsName
        return (
            (indent + "SCENE_CMD_SPAWN_LIST(")
            + f"{len(curHeader.actors.entranceActorList)}, "
            + f"{startPosName if len(curHeader.actors.entranceActorList) > 0 else 'NULL'})"
        )

    def getSkyboxSettingsCmd(self, infos: "SceneInfos", lights: "SceneLighting"):
        return indent + f"SCENE_CMD_SKYBOX_SETTINGS({infos.skyboxID}, {infos.skyboxConfig}, {lights.envLightMode}),\n"

    def getExitListCmd(self, scene: "Scene", headerIndex: int):
        curHeader = scene.getSceneHeaderFromIndex(headerIndex)
        return indent + f"SCENE_CMD_EXIT_LIST({curHeader.exits.name})"

    def getLightSettingsCmd(self, lights: "SceneLighting"):
        return (
            indent + "SCENE_CMD_ENV_LIGHT_SETTINGS("
        ) + f"{len(lights.settings)}, {lights.name if len(lights.settings) > 0 else 'NULL'}),\n"

    def getCutsceneDataCmd(self, cs: "SceneCutscene"):
        match cs.writeType:
            case "Object":
                csDataName = cs.csObj.name
            case _:
                csDataName = cs.csWriteCustom

        return indent + f"SCENE_CMD_CUTSCENE_DATA({csDataName}),\n"

    def getSceneCommandList(self, scene: "Scene", curHeader: "SceneHeader", headerIndex: int):
        cmdListData = CData()
        listName = f"SceneCmd {curHeader.name}"

        getCmdFunc1List = [
            self.getSpawnActorListCmd,
        ]

        getCmdGeneralList = [
            self.getSoundSettingsCmd,
            self.getMiscSettingsCmd,
            self.getSpecialFilesCmd,
        ]

        getCmdActorList = [
            self.getSpawnListCmd,
        ]

        if len(curHeader.exits.exitList) > 0:
            getCmdFunc1List.append(self.getExitListCmd)

        if len(curHeader.actors.transitionActorList) > 0:
            getCmdActorList.insert(0, self.getTransActorListCmd)

        # if scene.writeCutscene:
        #     getCmdFunc2ArgList.append(self.getCutsceneDataCmd)

        hasAltHeaders = headerIndex == 0 and scene.hasAlternateHeaders()
        sceneCmdData = (
            (scene.getAltHeaderListCmd(scene.altHeader.name) if hasAltHeaders else "")
            + self.getColHeaderCmd(scene.colHeader)
            + self.getRoomListCmd(scene)
            + self.getSkyboxSettingsCmd(curHeader.infos, curHeader.lighting)
            + self.getLightSettingsCmd(curHeader.lighting)
            + self.getPathListCmd(curHeader.path)
            # + (self.getCutsceneDataCmd(curHeader.cutscene) if curHeader.cutscene.writeCutscene else "")
            + (",\n".join(getCmd(curHeader.infos) for getCmd in getCmdGeneralList) + ",\n")
            + (",\n".join(getCmd(curHeader.actors) for getCmd in getCmdActorList) + ",\n")
            + (",\n".join(getCmd(scene, headerIndex) for getCmd in getCmdFunc1List) + ",\n")
            + scene.getEndCmd()
        )

        # .h
        cmdListData.header = f"extern {listName}[]" + ";\n"

        # .c
        cmdListData.source = f"{listName}[]" + " = {\n" + sceneCmdData + "};\n\n"

        return cmdListData
