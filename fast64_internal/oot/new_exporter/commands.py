from ...utility import CData, indent

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .room import OOTRoom, OOTRoomHeaderInfos, OOTRoomHeaderObjects, OOTRoomHeaderActors
    from .scene import (
        OOTScene,
        OOTSceneHeaderInfos,
        OOTSceneHeader,
        OOTSceneHeaderLighting,
        OOTSceneHeaderCutscene,
        OOTSceneHeaderActors,
        OOTSceneHeaderPath,
    )


class OOTRoomCommands:
    def getEchoSettingsCmd(self, infos: "OOTRoomHeaderInfos"):
        return indent + f"SCENE_CMD_ECHO_SETTINGS({infos.echo})"

    def getRoomBehaviourCmd(self, infos: "OOTRoomHeaderInfos"):
        showInvisibleActors = "true" if infos.showInvisActors else "false"
        disableWarpSongs = "true" if infos.disableWarpSongs else "false"

        return (
            (indent + "SCENE_CMD_ROOM_BEHAVIOR(")
            + ", ".join([infos.roomBehavior, infos.playerIdleType, showInvisibleActors, disableWarpSongs])
            + ")"
        )

    def getSkyboxDisablesCmd(self, infos: "OOTRoomHeaderInfos"):
        disableSkybox = "true" if infos.disableSky else "false"
        disableSunMoon = "true" if infos.disableSunMoon else "false"

        return indent + f"SCENE_CMD_SKYBOX_DISABLES({disableSkybox}, {disableSunMoon})"

    def getTimeSettingsCmd(self, infos: "OOTRoomHeaderInfos"):
        return indent + f"SCENE_CMD_TIME_SETTINGS({infos.hour}, {infos.minute}, {infos.timeSpeed})"

    def getWindSettingsCmd(self, infos: "OOTRoomHeaderInfos"):
        return (
            indent + f"SCENE_CMD_WIND_SETTINGS({', '.join(f'{dir}' for dir in infos.direction)}, {infos.strength}),\n"
        )

    # def getRoomShapeCmd(self, infos: "OOTRoom"):
    #     return indent + f"SCENE_CMD_ROOM_SHAPE(&{infos.mesh.headerName()})"

    def getObjectListCmd(self, objects: "OOTRoomHeaderObjects"):
        return (indent + "SCENE_CMD_OBJECT_LIST(") + f"{objects.getObjectLengthDefineName()}, {objects.name}),\n"

    def getActorListCmd(self, actors: "OOTRoomHeaderActors"):
        return (indent + "SCENE_CMD_ACTOR_LIST(") + f"{actors.getActorLengthDefineName()}, {actors.name}),\n"

    def getRoomCommandList(self, room: "OOTRoom", headerIndex: int):
        cmdListData = CData()
        curHeader = room.getRoomHeaderFromIndex(headerIndex)
        listName = f"SceneCmd {curHeader.name}"

        getCmdFuncInfosList = [
            self.getEchoSettingsCmd,
            self.getRoomBehaviourCmd,
            self.getSkyboxDisablesCmd,
            self.getTimeSettingsCmd,
            # self.getRoomShapeCmd,
        ]

        if curHeader.infos.setWind:
            getCmdFuncInfosList.append(self.getWindSettingsCmd)

        hasAltHeaders = headerIndex == 0 and room.hasAlternateHeaders()
        roomCmdData = (
            (room.getAltHeaderListCmd(room.altHeader.name) if hasAltHeaders else "")
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


class OOTSceneCommands:
    def getSoundSettingsCmd(self, infos: "OOTSceneHeaderInfos"):
        return indent + f"SCENE_CMD_SOUND_SETTINGS({infos.specID}, {infos.ambienceID}, {infos.sequenceID})"

    def getRoomListCmd(self, scene: "OOTScene"):
        return indent + f"SCENE_CMD_ROOM_LIST({len(scene.roomList)}, {scene.roomListName}),\n"

    def getTransActorListCmd(self, actors: "OOTSceneHeaderActors"):
        return (
            indent + "SCENE_CMD_TRANSITION_ACTOR_LIST("
        ) + f"{len(actors.transitionActorList)}, {actors.transActorListName})"

    def getMiscSettingsCmd(self, infos: "OOTSceneHeaderInfos"):
        return indent + f"SCENE_CMD_MISC_SETTINGS({infos.sceneCamType}, {infos.worldMapLocation})"

    # def getColHeaderCmd(self, outScene: OOTScene):
    #     return indent + f"SCENE_CMD_COL_HEADER(&{outScene.collision.headerName()})"

    def getSpawnListCmd(self, actors: "OOTSceneHeaderActors"):
        return (
            indent + "SCENE_CMD_ENTRANCE_LIST("
        ) + f"{actors.entranceListName if len(actors.entranceActorList) > 0 else 'NULL'})"

    def getSpecialFilesCmd(self, infos: "OOTSceneHeaderInfos"):
        return indent + f"SCENE_CMD_SPECIAL_FILES({infos.naviHintType}, {infos.keepObjectID})"

    def getPathListCmd(self, path: "OOTSceneHeaderPath"):
        return indent + f"SCENE_CMD_PATH_LIST({path.name}),\n" if len(path.pathList) > 0 else ""

    def getSpawnActorListCmd(self, scene: "OOTScene", headerIndex: int):
        curHeader = scene.getSceneHeaderFromIndex(headerIndex)
        startPosName = curHeader.actors.startPositionsName
        return (
            (indent + "SCENE_CMD_SPAWN_LIST(")
            + f"{len(curHeader.actors.entranceActorList)}, "
            + f"{startPosName if len(curHeader.actors.entranceActorList) > 0 else 'NULL'})"
        )

    def getSkyboxSettingsCmd(self, infos: "OOTSceneHeaderInfos", lights: "OOTSceneHeaderLighting"):
        return indent + f"SCENE_CMD_SKYBOX_SETTINGS({infos.skyboxID}, {infos.skyboxConfig}, {lights.envLightMode}),\n"

    def getExitListCmd(self, scene: "OOTScene", headerIndex: int):
        curHeader = scene.getSceneHeaderFromIndex(headerIndex)
        return indent + f"SCENE_CMD_EXIT_LIST({curHeader.exits.name})"

    def getLightSettingsCmd(self, lights: "OOTSceneHeaderLighting"):
        return (
            indent + "SCENE_CMD_ENV_LIGHT_SETTINGS("
        ) + f"{len(lights.settings)}, {lights.name if len(lights.settings) > 0 else 'NULL'}),\n"

    def getCutsceneDataCmd(self, cs: "OOTSceneHeaderCutscene"):
        match cs.writeType:
            case "Object":
                csDataName = cs.csObj.name
            case _:
                csDataName = cs.csWriteCustom

        return indent + f"SCENE_CMD_CUTSCENE_DATA({csDataName}),\n"

    def getSceneCommandList(self, scene: "OOTScene", curHeader: "OOTSceneHeader", headerIndex: int):
        cmdListData = CData()
        listName = f"SceneCmd {curHeader.name}"

        getCmdFunc1List = [
            self.getExitListCmd,
            self.getSpawnActorListCmd,
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

        # if scene.writeCutscene:
        #     getCmdFunc2ArgList.append(self.getCutsceneDataCmd)

        hasAltHeaders = headerIndex == 0 and scene.hasAlternateHeaders()
        sceneCmdData = (
            (scene.getAltHeaderListCmd(scene.altHeader.name) if hasAltHeaders else "")
            + self.getRoomListCmd(scene)
            + self.getSkyboxSettingsCmd(curHeader.infos, curHeader.lighting)
            + self.getLightSettingsCmd(curHeader.lighting)
            + self.getPathListCmd(curHeader.path)
            # + (self.getCutsceneDataCmd(curHeader.cutscene) if curHeader.cutscene.writeCutscene else "")
            + (",\n".join(getCmd(curHeader.infos) for getCmd in getCmdGeneralList) + ",\n")
            + (",\n".join(getCmd(scene, headerIndex) for getCmd in getCmdFunc1List) + ",\n")
            + (",\n".join(getCmd(curHeader.actors) for getCmd in getCmdActorList) + ",\n")
            + scene.getEndCmd()
        )

        # .h
        cmdListData.header = f"extern {listName}[]" + ";\n"

        # .c
        cmdListData.source = f"{listName}[]" + " = {\n" + sceneCmdData + "};\n\n"

        return cmdListData
