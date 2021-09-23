import math
from ..oot_f3d_writer import *
from ..oot_level_writer import *
from ..oot_collision import *

def cmdName(name, header, index):
	return name + "_header" + format(header, '02') + "_cmd" + format(index, '02')

# Scene Commands
def cmdSoundSettings(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_SOUND_SETTINGS(" + str(scene.audioSessionPreset) + ", " + str(scene.nightSeq) + \
		", " + str(scene.musicSeq) + "),\n"
	return cmd

def cmdRoomList(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_ROOM_LIST(" + str(len(scene.rooms)) + ", &" + scene.roomListName() + "),\n"
	return cmd

def cmdTransiActorList(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_TRANSITION_ACTOR_LIST(" + str(len(scene.transitionActorList)) + ", &" + \
		scene.transitionActorListName(header) + "),\n"
	return cmd

def cmdMiscSettings(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_MISC_SETTINGS(" + str(scene.cameraMode) + ", " + str(scene.mapLocation) + "),\n"
	return cmd

def cmdColHeader(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_COL_HEADER(&" + scene.collision.headerName() + "),\n"
	return cmd

def cmdEntranceList(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_ENTRANCE_LIST(" + (('&' + scene.entranceListName(header)) if len(scene.entranceList) > 0 else "NULL") + "),\n"
	return cmd

def cmdSpecialFiles(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_SPECIAL_FILES(" + str(scene.naviCup) + ", " + str(scene.globalObject) + "),\n"
	return cmd

def cmdPathList(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_PATH_LIST(&" + scene.pathListName() + "),\n"
	return cmd

def cmdSpawnList(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_SPAWN_LIST(" + str(len(scene.startPositions)) + ", " + \
		(('&' + scene.startPositionsName(header)) if len(scene.startPositions) > 0 else 'NULL') + "),\n"
	return cmd

def cmdSkyboxSettings(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_SKYBOX_SETTINGS(" + str(scene.skyboxID) + ", " + str(scene.skyboxCloudiness) \
		+ ", " + str(scene.skyboxLighting) + "),\n"
	return cmd
	
def cmdExitList(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_EXIT_LIST(&" + scene.exitListName(header) + "),\n"
	return cmd

def cmdLightSettingList(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_ENV_LIGHT_SETTINGS(" + str(len(scene.lights)) + ", " + \
		(('&' + scene.lightListName(header)) if len(scene.lights) > 0 else 'NULL') + "),\n"
	return cmd

def cmdCutsceneData(scene, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_CUTSCENE_DATA(&" + scene.cutsceneDataName(header) + "),\n"
	return cmd

def cmdEndMarker(name, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_END(),\n"
	return cmd

# Room Commands
def cmdAltHeaders(name, altName, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_ALTERNATE_HEADER_LIST(&" + altName + "),\n"
	return cmd

def cmdEchoSettings(room, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_ECHO_SETTINGS(" + str(room.echo) + "),\n"
	return cmd

def cmdRoomBehaviour(room, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_ROOM_BEHAVIOR(" + str(room.roomBehaviour) + ", " + str(room.linkIdleMode) + ", " + \
		("true" if room.showInvisibleActors else "false") + ", " + \
		("true" if room.disableWarpSongs else "false") + "),\n"
	return cmd

def cmdSkyboxDisables(room, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_SKYBOX_DISABLES(" + ("true" if room.disableSkybox else "false") + ", " + \
		("true" if room.disableSunMoon else "false") + "),\n"
	return cmd

def cmdTimeSettings(room, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_TIME_SETTINGS(" + str(room.timeHours) + ", " + str(room.timeMinutes) + ", " + \
		str(room.timeSpeed) + "),\n"
	return cmd

def cmdWindSettings(room, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_WIND_SETTINGS(" + str(room.windVector[0]) + ", " + \
		str(room.windVector[1]) + ", " + \
		str(room.windVector[2]) + ", " + \
		str(room.windStrength) + "),\n"
	return cmd

def cmdMesh(room, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_MESH(&" + room.mesh.headerName() + "),\n"
	return cmd

def cmdObjectList(room, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_OBJECT_LIST(" + str(len(room.objectList)) + ", &" + str(room.objectListName(header)) + "),\n"
	return cmd

def cmdActorList(room, header, cmdCount):
	cmd = CData()
	cmd.source = "\tSCENE_CMD_ACTOR_LIST(" + str(len(room.actorList)) + ", &" + str(room.actorListName(header)) + "),\n"
	return cmd

def ootObjectListToC(room, headerIndex):
	data = CData()
	data.header = "extern s16 " + room.objectListName(headerIndex) + "[" + str(len(room.objectList)) + "];\n" 
	data.source = "s16 " + room.objectListName(headerIndex) + "[" + str(len(room.objectList)) + "] = {\n"
	for objectItem in room.objectList:
		data.source += '\t' + objectItem + ',\n'
	data.source += '};\n\n'
	return data

def ootActorToC(actor):
	return '{ ' + str(actor.actorID) + ', ' + \
		str(int(round(actor.position[0]))) + ', ' + \
		str(int(round(actor.position[1]))) + ', ' + \
		str(int(round(actor.position[2]))) + ', ' + \
		((
		actor.rotOverride[0] + ', ' +
		actor.rotOverride[1] + ', ' +
		actor.rotOverride[2] + ', '
		) if actor.rotOverride is not None else (
		str(int(round(actor.rotation[0]))) + ', ' +
		str(int(round(actor.rotation[1]))) + ', ' +
		str(int(round(actor.rotation[2]))) + ', '
		)) + \
		str(actor.actorParam) + ' },\n'

def ootActorListToC(room, headerIndex):
	data = CData()
	data.header = "extern ActorEntry " + room.actorListName(headerIndex) + "[" + str(len(room.actorList)) + "];\n"
	data.source = "ActorEntry " + room.actorListName(headerIndex) + "[" + str(len(room.actorList)) + "] = {\n"
	for actor in room.actorList:
		data.source += '\t' + ootActorToC(actor)
	data.source += "};\n\n"
	return data

def ootAlternateRoomHeadersToC(scene, room, textureExportSettings):
	altHeader = CData()
	altData = CData()

	altHeader.header = "extern SCmdBase* " + room.alternateHeadersName() + "[];\n"
	altHeader.source = "SCmdBase* " + room.alternateHeadersName() + "[] = {\n"
	
	if room.childNightHeader is not None:
		altHeader.source += "\t" + room.roomName() + "_header" + format(1, '02') + ",\n"
		altData.append(ootRoomToC(scene, room.childNightHeader, 1, textureExportSettings))
	else:
		altHeader.source += "\t0,\n"

	if room.adultDayHeader is not None:
		altHeader.source += "\t" + room.roomName() + "_header" + format(2, '02') + ",\n"
		altData.append(ootRoomToC(scene, room.adultDayHeader, 2, textureExportSettings))
	else:
		altHeader.source += "\t0,\n"

	if room.adultNightHeader is not None:
		altHeader.source += "\t" + room.roomName() + "_header" + format(3, '02') + ",\n"
		altData.append(ootRoomToC(scene, room.adultNightHeader, 3, textureExportSettings))
	else:
		altHeader.source += "\t0,\n"

	for i in range(len(room.cutsceneHeaders)):
		altHeader.source += "\t" + room.roomName() + "_header" + format(i + 4, '02') + ",\n"
		altData.append(ootRoomToC(scene, room.cutsceneHeaders[i], i + 4, textureExportSettings))

	altHeader.source += '};\n\n'

	return altHeader, altData

def ootMeshEntryToC(meshEntry, meshType):
	opaqueName = meshEntry.DLGroup.opaque.name if meshEntry.DLGroup.opaque is not None else "0"
	transparentName = meshEntry.DLGroup.transparent.name if meshEntry.DLGroup.transparent is not None else "0"
	data = "{ "
	if meshType == "1":
		raise PluginError("MeshHeader1 not supported.")
	elif meshType == "2":
		data += str(meshEntry.cullGroup.position[0]) + ", " + str(meshEntry.cullGroup.position[1]) + ", "
		data += str(meshEntry.cullGroup.position[2]) + ", " + str(meshEntry.cullGroup.cullDepth) + ", "
	data += "(u32)" + opaqueName + ", (u32)" + transparentName + ' },\n' 

	return data

def ootRoomMeshToC(room, textureExportSettings):
	mesh = room.mesh
	if len(mesh.meshEntries) == 0:
		raise PluginError("Error: Room " + str(room.index) + " has no mesh children.")

	meshHeader = CData()
	meshHeader.header = "extern MeshHeader" + str(mesh.meshType) + " " + mesh.headerName() + ';\n'
	meshHeader.source = "MeshHeader" + str(mesh.meshType) + " " + mesh.headerName() + ' = ' +\
		"{ {" + str(mesh.meshType) + "}, " + str(len(mesh.meshEntries)) + ", " +\
		"(u32)&" + mesh.entriesName() + ", (u32)&(" + mesh.entriesName() + ") + " +\
		"sizeof(" + mesh.entriesName() + ") };\n\n"

	meshEntries = CData()
	meshEntries.header = "extern MeshEntry" + str(mesh.meshType) + " " + mesh.entriesName() + "[" + str(len(mesh.meshEntries)) + "];\n"
	meshEntries.source = "MeshEntry" + str(mesh.meshType) + " " + mesh.entriesName() + "[" + str(len(mesh.meshEntries)) + "] = {\n"
	meshData = CData()
	for entry in mesh.meshEntries:
		meshEntries.source  += '\t' + ootMeshEntryToC(entry, str(mesh.meshType))
		if entry.DLGroup.opaque is not None:
			meshData.append(entry.DLGroup.opaque.to_c(mesh.model.f3d))
		if entry.DLGroup.transparent is not None:
			meshData.append(entry.DLGroup.transparent.to_c(mesh.model.f3d))
	meshEntries.source  += '};\n\n'
	exportData = mesh.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex))

	meshData.append(exportData.all())
	meshHeader.append(meshEntries)
	#meshHeader.append(meshData)

	return meshHeader, meshData

def ootRoomCommandsToC(room, headerIndex):
	commands = []
	if room.hasAlternateHeaders():
		commands.append(cmdAltHeaders(room.roomName(), room.alternateHeadersName(), headerIndex, len(commands)))
	commands.append(cmdEchoSettings(room, headerIndex, len(commands)))
	commands.append(cmdRoomBehaviour(room, headerIndex, len(commands)))
	commands.append(cmdSkyboxDisables(room, headerIndex, len(commands)))
	commands.append(cmdTimeSettings(room, headerIndex, len(commands)))
	if room.setWind:
		commands.append(cmdWindSettings(room, headerIndex, len(commands)))
	commands.append(cmdMesh(room, headerIndex, len(commands)))
	if len(room.objectList) > 0:
		commands.append(cmdObjectList(room, headerIndex, len(commands)))
	if len(room.actorList) > 0:
		commands.append(cmdActorList(room, headerIndex, len(commands)))
	commands.append(cmdEndMarker(room.roomName(), headerIndex, len(commands)))

	data = CData()
	
	# data.header = ''.join([command.header for command in commands]) +'\n'
	data.header = "extern SCmdBase " + room.roomName() + "_header" + format(headerIndex, '02') + "[];\n"

	data.source = "SCmdBase " + room.roomName() + "_header" + format(headerIndex, '02') + "[] = {\n"
	data.source += ''.join([command.source for command in commands])
	data.source += "};\n\n"

	return data

def ootRoomIncludes(scene, room):
	data = CData()
	data.source += '#include "ultra64.h"\n'
	data.source += '#include "z64.h"\n'
	data.source += '#include "macros.h"\n'
	data.source += '#include "' + scene.sceneName() + '.h"\n\n'
	
	data.source += '#include "segment_symbols.h"\n'
	data.source += '#include "command_macros_base.h"\n'
	data.source += '#include "z64cutscene_commands.h"\n'
	data.source += '#include "variables.h"\n'
	
	data.source += '\n'
	return data

def ootRoomToC(scene, room, headerIndex, textureExportSettings):
	roomC = CData() # main file
	roomMeshHeaderC = CData()
	roomMeshDataC = CData()

	if headerIndex == 0:
		roomC.append(ootRoomIncludes(scene, room))
		roomMeshHeaderC.append(ootRoomIncludes(scene, room))
		roomMeshDataC.append(ootRoomIncludes(scene, room))
	
	if room.hasAlternateHeaders():
		altHeader, altData = ootAlternateRoomHeadersToC(scene, room, textureExportSettings)
	else:
		altHeader = CData()
		altData = CData()
		
	if headerIndex == 0:
		meshHeader, meshData = ootRoomMeshToC(room, textureExportSettings)
	else:
		meshHeader = CData()
		meshData = CData()

	roomC.append(ootRoomCommandsToC(room, headerIndex))
	roomC.append(altHeader)
	if len(room.objectList) > 0:
		roomC.append(ootObjectListToC(room, headerIndex))
	if len(room.actorList) > 0:
		roomC.append(ootActorListToC(room, headerIndex))
	
	roomMeshHeaderC.append(meshHeader)
	roomC.append(altData)
	roomMeshDataC.append(meshData)
	
	return roomC, roomMeshHeaderC, roomMeshDataC

def ootAlternateSceneHeadersToC(scene):
	altHeader = CData()
	altData = CData()

	altHeader.header = "extern SCmdBase* " + scene.alternateHeadersName() + "[];\n"
	altHeader.source = "SCmdBase* " + scene.alternateHeadersName() + "[] = {\n"
	
	if scene.childNightHeader is not None:
		altHeader.source += "\t" + scene.sceneName() + "_header" + format(1, '02') + ",\n"
		altData.append(ootSceneMainToC(scene.childNightHeader, 1))
	else:
		altHeader.source += "\t0,\n"

	if scene.adultDayHeader is not None:
		altHeader.source += "\t" + scene.sceneName() + "_header" + format(2, '02') + ",\n"
		altData.append(ootSceneMainToC(scene.adultDayHeader, 2))
	else:
		altHeader.source += "\t0,\n"

	if scene.adultNightHeader is not None:
		altHeader.source += "\t" + scene.sceneName() + "_header" + format(3, '02') + ",\n"
		altData.append(ootSceneMainToC(scene.adultNightHeader, 3))
	else:
		altHeader.source += "\t0,\n"

	for i in range(len(scene.cutsceneHeaders)):
		altHeader.source += "\t" + scene.sceneName() + "_header" + format(i + 4, '02') + ",\n"
		altData.append(ootSceneMainToC(scene.cutsceneHeaders[i], i + 4))

	altHeader.source += '};\n\n'

	return altHeader, altData

def ootSceneCommandsToC(scene, headerIndex):
	commands = []
	if scene.hasAlternateHeaders():
		commands.append(cmdAltHeaders(scene.sceneName(), scene.alternateHeadersName(), headerIndex, len(commands)))
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
	commands.append(cmdEndMarker(scene.sceneName(), headerIndex, len(commands)))

	data = CData()
	
	# data.header = ''.join([command.header for command in commands]) +'\n'
	data.header = "extern SCmdBase " + scene.sceneName() + "_header" + format(headerIndex, '02') + "[];\n"
	
	data.source = "SCmdBase " + scene.sceneName() + "_header" + format(headerIndex, '02') + "[] = {\n"
	data.source += ''.join([command.source for command in commands])
	data.source += "};\n\n"

	return data

def ootStartPositionListToC(scene, headerIndex):
	data = CData()
	data.header = "extern ActorEntry " + scene.startPositionsName(headerIndex) + "[];\n"
	data.source = "ActorEntry " + scene.startPositionsName(headerIndex) + "[] = {\n"
	for i in range(len(scene.startPositions)):
		data.source += '\t' + ootActorToC(scene.startPositions[i])
	data.source += '};\n\n'
	return data

def ootTransitionActorToC(transActor):
	return '{ ' + str(transActor.frontRoom) + ', ' + \
		str(transActor.frontCam) + ', ' + \
		str(transActor.backRoom) + ', ' + \
		str(transActor.backCam) + ', ' + \
		str(transActor.actorID) + ', ' + \
		str(int(round(transActor.position[0]))) + ', ' + \
		str(int(round(transActor.position[1]))) + ', ' + \
		str(int(round(transActor.position[2]))) + ', ' + \
		str(int(round(transActor.rotationY))) + ', ' + \
		str(transActor.actorParam) + ' },\n'

def ootTransitionActorListToC(scene, headerIndex):
	data = CData()
	data.header = "extern TransitionActorEntry " + scene.transitionActorListName(headerIndex) + "[" + str(len(scene.transitionActorList)) + "];\n"
	data.source = "TransitionActorEntry " + scene.transitionActorListName(headerIndex) + "[" + str(len(scene.transitionActorList)) + "] = {\n"
	for transActor in scene.transitionActorList:
		data.source += '\t' + ootTransitionActorToC(transActor)
	data.source += '};\n\n'
	return data

def ootRoomListEntryToC(room):
	return "{ (u32)_" + room.roomName() + "SegmentRomStart, (u32)_" + room.roomName() + "SegmentRomEnd },\n"

def ootRoomListHeaderToC(scene):
	data = CData()
	data.header = "extern RomFile " + scene.roomListName() + "[];\n"
	data.source = "RomFile " + scene.roomListName() + "[] = {\n"
	for i in range(len(scene.rooms)):
		data.source += '\t' + ootRoomListEntryToC(scene.rooms[i])
	data.source += '};\n\n'
	return data

def ootEntranceToC(entrance):
	return "{ " + str(entrance.startPositionIndex) + ', ' + str(entrance.roomIndex) + ' },\n'

def ootEntranceListToC(scene, headerIndex):
	data = CData()
	data.header = "extern EntranceEntry " + scene.entranceListName(headerIndex) + "[];\n"
	data.source = "EntranceEntry " + scene.entranceListName(headerIndex) + "[] = {\n"
	for entrance in scene.entranceList:
		data.source += '\t' + ootEntranceToC(entrance)
	data.source += '};\n\n'
	return data

def ootExitListToC(scene, headerIndex):
	data = CData()
	data.header = "extern u16 " + scene.exitListName(headerIndex) + "[" + str(len(scene.exitList)) + "];\n"
	data.source = "u16 " + scene.exitListName(headerIndex) + "[" + str(len(scene.exitList)) + "] = {\n"
	for exitEntry in scene.exitList:
		data.source += '\t' + str(exitEntry.index) + ',\n'
	data.source += '};\n\n'
	return data

def ootVectorToC(vector):
	return "0x{:02X}, 0x{:02X}, 0x{:02X}".format(vector[0], vector[1], vector[2])

def ootRGBColorToC(color):
	return str(color[0]) + ', ' + str(color[1]) + ', ' + str(color[2])

def ootLightToC(light):
	return "\t{ " + \
		ootRGBColorToC(light.ambient) + ', ' +\
		ootVectorToC(light.diffuseDir0) + ', ' +\
		ootRGBColorToC(light.diffuse0) + ', ' +\
		ootVectorToC(light.diffuseDir1) + ', ' +\
		ootRGBColorToC(light.diffuse1) + ', ' +\
		ootRGBColorToC(light.fogColor) + ', ' +\
		light.getBlendFogShort() + ', ' +\
		"0x{:04X}".format(light.fogFar) + ' },\n'

def ootLightSettingsToC(scene, useIndoorLighting, headerIndex):
	data = CData()
	lightArraySize = len(scene.lights)
	data.header = "extern EnvLightSettings " + scene.lightListName(headerIndex) + "[" + str(lightArraySize) + "];\n"
	data.source = "EnvLightSettings " + scene.lightListName(headerIndex) + "[" + str(lightArraySize) + "] = {\n"
	for light in scene.lights:
		data.source += ootLightToC(light)
	data.source += '};\n\n'
	return data

def ootPathToC(path):
	data = CData()
	data.header = "extern Vec3s " + path.pathName() + '[];\n'
	data.source = "Vec3s " + path.pathName() + '[] = {\n'
	for point in path.points:
		data.source += '\t' + "{ " +\
			str(int(round(point[0]))) + ', ' +\
			str(int(round(point[1]))) + ', ' +\
			str(int(round(point[2]))) + ' },\n'
	data.source += '};\n\n'

	return data
	
def ootPathListToC(scene):
	data = CData()
	data.header = "extern Path " + scene.pathListName() + "[" + str(len(scene.pathList)) + "];\n"
	data.source = "Path " + scene.pathListName() + "[" + str(len(scene.pathList)) + "] = {\n"
	pathData = CData()
	for i in range(len(scene.pathList)):
		path = scene.pathList[i]
		data.source += '\t' + "{ " + str(len(path.points)) + ', (u32)' + path.pathName() + " },\n"
		pathData.append(ootPathToC(path))
	data.source += '};\n\n'
	pathData.append(data)
	return pathData

def ootCutsceneToC(scene, headerIndex):
	data = CData()
	data.header = "extern s32 " + scene.cutsceneDataName(headerIndex) + "[];\n"
	data.source = "s32 " + scene.cutsceneDataName(headerIndex) + "[] = {\n"
	nentries = len(scene.csLists) + (1 if scene.csWriteTerminator else 0)
	data.source += "\tCS_BEGIN_CUTSCENE(" + str(nentries) + ", " + str(scene.csEndFrame) + "),\n"
	if scene.csWriteTerminator:
		data.source += "\tCS_TERMINATOR(" + str(scene.csTermIdx) + ", " + str(scene.csTermStart) + ", " + str(scene.csTermEnd) + "),\n"
	for list in scene.csLists:
		data.source += "\t" + ootEnumCSListTypeListC[list.listType] + "("
		if list.listType == "Unk":
			data.source += list.unkType + ", "
		if list.listType == "FX":
			data.source += list.fxType + ", " + str(list.fxStartFrame) + ", " + str(list.fxEndFrame)
		else:
			data.source += str(len(list.entries))
		data.source += "),\n"
		for e in list.entries:
			data.source += "\t\t"
			if list.listType == "Textbox":
				data.source += ootEnumCSTextboxTypeEntryC[e.textboxType]
			else:
				data.source += ootEnumCSListTypeEntryC[list.listType]
			data.source += "("
			if list.listType == "Textbox":
				if e.textboxType == "Text":
					data.source += e.messageId + ", " + str(e.startFrame) + ", " \
						+ str(e.endFrame) + ", " + e.type + ", " + e.topOptionBranch \
						+ ", " + e.bottomOptionBranch
				elif e.textboxType == "None":
					data.source += str(e.startFrame) + ", " + str(e.endFrame)
				elif e.textboxType == "LearnSong":
					data.source += e.ocarinaSongAction + ", " + str(e.startFrame) \
						+ ", " + str(e.endFrame) + ", " + e.ocarinaMessageId
			elif list.listType == "Lighting":
				data.source += str(e.index) + ", " + str(e.startFrame) + ", " \
					+ str(e.startFrame + 1) + ", 0, 0, 0, 0, 0, 0, 0, 0"
			elif list.listType == "Time":
				data.source += "0, " + str(e.startFrame) + ", " + str(e.startFrame + 1) \
					+ ", " + str(e.hour) + ", " + str(e.minute) + ", 0"
			elif list.listType in ["PlayBGM", "StopBGM", "FadeBGM"]:
				data.source += e.value
				if list.listType != "FadeBGM":
					data.source += " + 1" # Game subtracts 1 to get actual seq
				data.source += ", " + str(e.startFrame) + ", " + str(e.endFrame) \
					+ ", 0, 0, 0, 0, 0, 0, 0, 0"
			elif list.listType == "Misc":
				data.source += str(e.operation) + ", " + str(e.startFrame) + ", " \
					+ str(e.endFrame) + ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0"
			elif list.listType == "0x09":
				data.source += "0, " + str(e.startFrame) + ", " + str(e.startFrame + 1) + ", " \
					+ e.unk2 + ", " + e.unk3 + ", " + e.unk4 + ", 0, 0"
			elif list.listType == "Unk":
				data.source += e.unk1 + ", " + e.unk2 + ", " + e.unk3 + ", " \
					+ e.unk4 + ", " + e.unk5 + ", " + e.unk6 + ", " \
					+ e.unk7 + ", " + e.unk8 + ", " + e.unk9 + ", " \
					+ e.unk10 + ", " + e.unk11 + ", " + e.unk12
			else:
				raise PluginError("Invalid cutscene list type")
			data.source += "),\n"
	data.source += "\tCS_END(),\n"
	data.source += "};\n"
	return data

def ootSceneMeshToC(scene, textureExportSettings):
	exportData = scene.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex))
	return exportData.all()

def ootSceneIncludes(scene):
	data = CData()
	data.source += '#include "ultra64.h"\n'
	data.source += '#include "z64.h"\n'
	data.source += '#include "macros.h"\n'
	data.source += '#include "' + scene.sceneName() + '.h"\n\n'
	data.source += '#include "segment_symbols.h"\n'
	data.source += '#include "command_macros_base.h"\n'
	data.source += '#include "z64cutscene_commands.h"\n'
	data.source += '#include "variables.h"\n'
	data.source += '\n'
	return data

def ootSceneMainToC(scene, headerIndex):
	sceneMainC = CData()

	if headerIndex == 0:
		sceneMainC.append(ootSceneIncludes(scene))
		roomHeaderData = ootRoomListHeaderToC(scene)

		if len(scene.pathList) > 0:
			pathData = ootPathListToC(scene)
		else:
			pathData = CData()
	else:
		roomHeaderData = CData()
		pathData = CData()

	if scene.hasAlternateHeaders():
		altHeader, altData = ootAlternateSceneHeadersToC(scene)
	else:
		altHeader = CData()
		altData = CData()

	# Write the scene header
	sceneMainC.append(ootSceneCommandsToC(scene, headerIndex))
	sceneMainC.append(altHeader)
	
	if len(scene.startPositions) > 0:
		sceneMainC.append(ootStartPositionListToC(scene, headerIndex))
	
	if len(scene.transitionActorList) > 0:
		sceneMainC.append(ootTransitionActorListToC(scene, headerIndex))
	
	sceneMainC.append(roomHeaderData)
	
	if len(scene.entranceList) > 0:
		sceneMainC.append(ootEntranceListToC(scene, headerIndex))
	
	if len(scene.exitList) > 0:
		sceneMainC.append(ootExitListToC(scene, headerIndex))
	
	if len(scene.lights) > 0:
		sceneMainC.append(ootLightSettingsToC(scene, scene.skyboxLighting == '0x01', headerIndex))
	
	sceneMainC.append(pathData)

	# Write alternate headers
	sceneMainC.append(altData)

	return sceneMainC

def ootSceneCollisionToC(scene):
	sceneCollisionC = CData()

	# Writes collision data
	sceneCollisionC.append(ootSceneIncludes(scene))
	sceneCollisionC.append(ootCollisionToC(scene.collision))

	return sceneCollisionC

def ootSceneTexturesToC(scene, textureExportSettings):
	sceneTexturesC = CData()

	# Writes any "meshes", though for scenes these will always be material displaylists and textures
	sceneTexturesC.append(ootSceneIncludes(scene))
	sceneTexturesC.append(ootSceneMeshToC(scene, textureExportSettings))

	return sceneTexturesC

def ootLevelToC(scene, textureExportSettings):
	levelC = OOTLevelC()

	# Write each scene file
	levelC.sceneMain = ootSceneMainToC(scene, 0)
	levelC.sceneCollision = ootSceneCollisionToC(scene)
	levelC.sceneTextures = ootSceneTexturesToC(scene, textureExportSettings)

	# Append the header data from all of the scene files into a single header
	levelC.sceneHeader.append(levelC.sceneMain)
	levelC.sceneHeader.append(levelC.sceneCollision)
	levelC.sceneHeader.append(levelC.sceneTextures)
	
	# TODO: Split room files the same way as scene files!
	for i in range(len(scene.rooms)):
		curRoomName = scene.rooms[i].roomName()
		
		# Write each room file for this room
		levelC.rooms[curRoomName], levelC.roomMeshHeaders[curRoomName], levelC.roomMeshData =\
			ootRoomToC(scene, scene.rooms[i], 0, textureExportSettings)
		
		# Append the header data for this room
		levelC.sceneHeader.append(levelC.rooms[curRoomName])
		levelC.sceneHeader.append(levelC.roomMeshHeaders[curRoomName])
		levelC.sceneHeader.append(levelC.roomMeshData[curRoomName])
	
	return levelC

class OOTLevelC:
	def __init__(self):
		# Header file for the entire scene
		# TODO: Do this a better way such that all of the c files and header files that make up the scene do not need to be appended together.
		self.sceneHeader = CData()
		
		# Each file that is contained in the scene segment
		self.sceneMain = CData()
		self.sceneCollision = CData()
		self.sceneTextures = CData()

		# Each file that is contained in the room segment
		self.rooms = {} # main file
		self.roomMeshHeaders = {}
		self.roomMeshData = {}
