from ...utility import CData, indent

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scene import OOTScene, OOTSceneGeneral, OOTSceneHeader, OOTSceneLighting, OOTSceneCutscene, OOTSceneActors
    from .room import OOTRoom, OOTRoomHeader, OOTRoomGeneral, OOTRoomObjects, OOTRoomActors


class OOTRoomCommands:
    def getEchoSettingsCmd(self, infos: "OOTRoomGeneral"):
        return indent + f"SCENE_CMD_ECHO_SETTINGS({infos.echo})"

    def getRoomBehaviourCmd(self, infos: "OOTRoomGeneral"):
        showInvisibleActors = "true" if infos.showInvisActors else "false"
        disableWarpSongs = "true" if infos.disableWarpSongs else "false"

        return (
            (indent + "SCENE_CMD_ROOM_BEHAVIOR(")
            + ", ".join([infos.roomBehavior, infos.playerIdleType, showInvisibleActors, disableWarpSongs])
            + ")"
        )

    def getSkyboxDisablesCmd(self, infos: "OOTRoomGeneral"):
        disableSkybox = "true" if infos.disableSky else "false"
        disableSunMoon = "true" if infos.disableSunMoon else "false"

        return indent + f"SCENE_CMD_SKYBOX_DISABLES({disableSkybox}, {disableSunMoon})"

    def getTimeSettingsCmd(self, infos: "OOTRoomGeneral"):
        return indent + f"SCENE_CMD_TIME_SETTINGS({infos.hour}, {infos.minute}, {infos.timeSpeed})"

    def getWindSettingsCmd(self, infos: "OOTRoomGeneral"):
        return (
            indent + f"SCENE_CMD_WIND_SETTINGS({', '.join(f'{dir}' for dir in infos.direction)}, {infos.strength}),\n"
        )

    # def getRoomShapeCmd(self, infos: "OOTRoom"):
    #     return indent + f"SCENE_CMD_ROOM_SHAPE(&{infos.mesh.headerName()})"

    def getObjectListCmd(self, objects: "OOTRoomObjects", headerIndex: int):
        return (
            indent + "SCENE_CMD_OBJECT_LIST("
        ) + f"{objects.getObjectLengthDefineName(headerIndex)}, {objects.objectListName(headerIndex)}),\n"

    def getActorListCmd(self, actors: "OOTRoomActors", headerIndex: int):
        return (indent + "SCENE_CMD_ACTOR_LIST(") + f"{actors.getActorLengthDefineName()}, {actors.actorListName()}),\n"

    def getRoomCommandList(self, room: "OOTRoom", headerIndex: int):
        cmdListData = CData()
        curHeader = room.getRoomHeaderFromIndex(headerIndex)
        listName = f"SceneCmd {curHeader.roomName}_header{headerIndex:02}"

        getCmdFuncList = [
            self.getEchoSettingsCmd,
            self.getRoomBehaviourCmd,
            self.getSkyboxDisablesCmd,
            self.getTimeSettingsCmd,
            # self.getRoomShapeCmd,
        ]

        roomCmdData = (
            (room.getAltHeaderListCmd(room.altHeadersName) if room.hasAlternateHeaders() else "")
            + (",\n".join(getCmd(curHeader.general) for getCmd in getCmdFuncList) + ",\n")
            + (self.getWindSettingsCmd(curHeader.general) if curHeader.general.setWind else "")
            + (self.getObjectListCmd(curHeader.objects, headerIndex) if len(curHeader.objects.objectList) > 0 else "")
            + (self.getActorListCmd(curHeader.actors, headerIndex) if len(curHeader.actors.actorList) > 0 else "")
            + room.getEndCmd()
        )

        # .h
        cmdListData.header = f"extern {listName}[];\n"

        # .c
        cmdListData.source = f"{listName}[]" + " = {\n" + roomCmdData + "};\n\n"

        return cmdListData


class OOTSceneCommands:
    def getSoundSettingsCmd(self, infos: "OOTSceneGeneral"):
        return indent + f"SCENE_CMD_SOUND_SETTINGS({infos.specID}, {infos.ambienceID}, {infos.sequenceID})"

    def getRoomListCmd(self, scene: "OOTScene"):
        return indent + f"SCENE_CMD_ROOM_LIST({len(scene.roomList)}, {scene.roomListName}),\n"

    def getTransActorListCmd(self, actors: "OOTSceneActors"):
        return (
            indent + "SCENE_CMD_TRANSITION_ACTOR_LIST("
        ) + f"{len(actors.transitionActorList)}, {actors.transActorListName})"

    def getMiscSettingsCmd(self, infos: "OOTSceneGeneral"):
        return indent + f"SCENE_CMD_MISC_SETTINGS({infos.sceneCamType}, {infos.worldMapLocation})"

    # def getColHeaderCmd(self, outScene: OOTScene):
    #     return indent + f"SCENE_CMD_COL_HEADER(&{outScene.collision.headerName()})"

    def getSpawnListCmd(self, actors: "OOTSceneActors"):
        return (
            indent + "SCENE_CMD_ENTRANCE_LIST("
        ) + f"{actors.entranceListName if len(actors.entranceActorList) > 0 else 'NULL'})"

    def getSpecialFilesCmd(self, infos: "OOTSceneGeneral"):
        return indent + f"SCENE_CMD_SPECIAL_FILES({infos.naviHintType}, {infos.keepObjectID})"

    # def getPathListCmd(self, outScene: "OOTScene", headerIndex: int):
    #     return indent + f"SCENE_CMD_PATH_LIST({outScene.pathListName(headerIndex)})"

    def getSpawnActorListCmd(self, scene: "OOTScene", headerIndex: int):
        curHeader = scene.getSceneHeaderFromIndex(headerIndex)
        startPosName = curHeader.actors.startPositionsName
        return (
            (indent + "SCENE_CMD_SPAWN_LIST(")
            + f"{len(curHeader.actors.entranceActorList)}, "
            + f"{startPosName if len(curHeader.actors.entranceActorList) > 0 else 'NULL'}),\n"
        )

    def getSkyboxSettingsCmd(self, infos: "OOTSceneGeneral", lights: "OOTSceneLighting"):
        return indent + f"SCENE_CMD_SKYBOX_SETTINGS({infos.skyboxID}, {infos.skyboxConfig}, {lights.envLightMode}),\n"

    def getExitListCmd(self, scene: "OOTScene", headerIndex: int):
        curHeader = scene.getSceneHeaderFromIndex(headerIndex)
        return indent + f"SCENE_CMD_EXIT_LIST({curHeader.exits.name}),\n"

    def getLightSettingsCmd(self, lights: "OOTSceneLighting"):
        return (
            indent + "SCENE_CMD_ENV_LIGHT_SETTINGS("
        ) + f"{len(lights.settings)}, {lights.name if len(lights.settings) > 0 else 'NULL'}),\n"

    def getCutsceneDataCmd(self, cs: "OOTSceneCutscene"):
        match cs.writeType:
            case "Object":
                csDataName = cs.csObj.name
            case _:
                csDataName = cs.csWriteCustom

        return indent + f"SCENE_CMD_CUTSCENE_DATA({csDataName}),\n"

    def getSceneCommandList(self, scene: "OOTScene", curHeader: "OOTSceneHeader", headerIndex: int):
        cmdListData = CData()
        listName = f"SceneCmd {scene.headerName}"

        getCmdFunc1ArgList = [
            # self.getColHeaderCmd,
        ]

        getCmdGeneralList = [
            self.getSoundSettingsCmd,
            self.getMiscSettingsCmd,
            self.getSpecialFilesCmd,
        ]

        getCmdActorList = [
            self.getSpawnListCmd,
        ]

        if len(curHeader.actors.transitionActorList) > 0:
            getCmdActorList.append(self.getTransActorListCmd)

        # if len(outScene.pathList) > 0:
        #     getCmdFunc2ArgList.append(self.getPathListCmd)

        # if scene.writeCutscene:
        #     getCmdFunc2ArgList.append(self.getCutsceneDataCmd)

        sceneCmdData = (
            (scene.getAltHeaderListCmd(scene.altName) if scene.hasAlternateHeaders() else "")
            + self.getRoomListCmd(scene)
            + self.getSkyboxSettingsCmd(curHeader.general, curHeader.lighting)
            # + (",\n".join(getCmd(scene) for getCmd in getCmdFunc1ArgList) + ",\n")
            + (",\n".join(getCmd(curHeader.general) for getCmd in getCmdGeneralList) + ",\n")
            + (self.getExitListCmd(scene, headerIndex) if len(curHeader.exits.exitList) > 0 else "")
            + (self.getCutsceneDataCmd(curHeader.cutscene) if curHeader.cutscene.writeCutscene else "")
            + self.getSpawnActorListCmd(scene, headerIndex)
            + self.getLightSettingsCmd(curHeader.lighting)
            + (",\n".join(getCmd(curHeader.actors) for getCmd in getCmdActorList) + ",\n")
            + scene.getEndCmd()
        )

        # .h
        cmdListData.header = f"extern {listName}[]" + ";\n"

        # .c
        cmdListData.source = f"{listName}[]" + " = {\n" + sceneCmdData + "};\n\n"

        return cmdListData
