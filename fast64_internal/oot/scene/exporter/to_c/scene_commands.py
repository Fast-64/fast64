from .....utility import CData, indent


def cmdSoundSettings(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_SOUND_SETTINGS("
        + ", ".join(
            (
                str(scene.audioSessionPreset),
                str(scene.nightSeq),
                str(scene.musicSeq),
            )
        )
        + "),\n"
    )
    return cmd


def cmdRoomList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = indent + "SCENE_CMD_ROOM_LIST(" + str(len(scene.rooms)) + ", " + scene.roomListName() + "),\n"
    return cmd


def cmdTransiActorList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_TRANSITION_ACTOR_LIST("
        + str(len(scene.transitionActorList))
        + ", "
        + scene.transitionActorListName(header)
        + "),\n"
    )
    return cmd


def cmdMiscSettings(scene, header, cmdCount):
    cmd = CData()
    cmd.source = indent + "SCENE_CMD_MISC_SETTINGS(" + str(scene.cameraMode) + ", " + str(scene.mapLocation) + "),\n"
    return cmd


def cmdColHeader(scene, header, cmdCount):
    cmd = CData()
    cmd.source = indent + "SCENE_CMD_COL_HEADER(&" + scene.collision.headerName() + "),\n"
    return cmd


def cmdEntranceList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_ENTRANCE_LIST("
        + (scene.entranceListName(header) if len(scene.entranceList) > 0 else "NULL")
        + "),\n"
    )
    return cmd


def cmdSpecialFiles(scene, header, cmdCount):
    cmd = CData()
    cmd.source = indent + "SCENE_CMD_SPECIAL_FILES(" + str(scene.naviCup) + ", " + str(scene.globalObject) + "),\n"
    return cmd


def cmdPathList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = indent + "SCENE_CMD_PATH_LIST(" + scene.pathListName(header) + "),\n"
    return cmd


def cmdSpawnList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_SPAWN_LIST("
        + str(len(scene.startPositions))
        + ", "
        + (scene.startPositionsName(header) if len(scene.startPositions) > 0 else "NULL")
        + "),\n"
    )
    return cmd


def cmdSkyboxSettings(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_SKYBOX_SETTINGS("
        + ", ".join(
            (
                str(scene.skyboxID),
                str(scene.skyboxCloudiness),
                str(scene.skyboxLighting),
            )
        )
        + "),\n"
    )
    return cmd


def cmdExitList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = indent + "SCENE_CMD_EXIT_LIST(" + scene.exitListName(header) + "),\n"
    return cmd


def cmdLightSettingList(scene, header, cmdCount):
    cmd = CData()
    cmd.source = (
        indent
        + "SCENE_CMD_ENV_LIGHT_SETTINGS("
        + str(len(scene.lights))
        + ", "
        + (scene.lightListName(header) if len(scene.lights) > 0 else "NULL")
        + "),\n"
    )
    return cmd


def cmdCutsceneData(scene, header, cmdCount):
    cmd = CData()
    if scene.csWriteType == "Embedded":
        csname = scene.cutsceneDataName(header)
    elif scene.csWriteType == "Object":
        csname = scene.csWriteObject.name
    elif scene.csWriteType == "Custom":
        csname = scene.csWriteCustom
    cmd.source = indent + "SCENE_CMD_CUTSCENE_DATA(" + csname + "),\n"
    return cmd


def ootSceneCommandsToC(scene, headerIndex):
    commands = []
    if scene.hasAlternateHeaders():
        commands.append(
            scene.cmdAltHeaders(scene.sceneName(), scene.alternateHeadersName(), headerIndex, len(commands))
        )
    commands.append(cmdSoundSettings(scene, headerIndex, len(commands)))
    commands.append(cmdRoomList(scene, headerIndex, len(commands)))
    if len(scene.transitionActorList) > 0:
        commands.append(cmdTransiActorList(scene, headerIndex, len(commands)))
    commands.append(cmdMiscSettings(scene, headerIndex, len(commands)))
    commands.append(cmdColHeader(scene, headerIndex, len(commands)))
    commands.append(cmdEntranceList(scene, headerIndex, len(commands)))
    commands.append(cmdSpecialFiles(scene, headerIndex, len(commands)))
    if len(scene.pathList) > 0:
        commands.append(cmdPathList(scene, headerIndex, len(commands)))
    commands.append(cmdSpawnList(scene, headerIndex, len(commands)))
    commands.append(cmdSkyboxSettings(scene, headerIndex, len(commands)))
    if len(scene.exitList) > 0:
        commands.append(cmdExitList(scene, headerIndex, len(commands)))
    commands.append(cmdLightSettingList(scene, headerIndex, len(commands)))
    if scene.writeCutscene:
        commands.append(cmdCutsceneData(scene, headerIndex, len(commands)))
    commands.append(scene.cmdEndMarker(scene.sceneName(), headerIndex, len(commands)))

    data = CData()

    # data.header = ''.join([command.header for command in commands]) +'\n'
    data.header = "extern SceneCmd " + scene.sceneName() + "_header" + format(headerIndex, "02") + "[];\n"

    data.source = "SceneCmd " + scene.sceneName() + "_header" + format(headerIndex, "02") + "[] = {\n"
    data.source += "".join([command.source for command in commands])
    data.source += "};\n\n"

    return data
