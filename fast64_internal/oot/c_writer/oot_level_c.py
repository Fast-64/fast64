import math
from ..oot_f3d_writer import *
from ..oot_level_writer import *
from ..oot_collision import *

def cmdName(name, header, index):
	return name + "_header" + format(header, '02') + "_cmd" + format(index, '02')

# Scene Commands
def cmdCameraList(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdCsCameraList " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdCsCameraList " + cmdName(scene.sceneName(), header, cmdCount) + " = { " + \
		"0x02, " + str(len(scene.cameraList)) + ', (u32)&' + scene.cameraListName() + ' };\n\n'
	return cmd

def cmdSoundSettings(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdSoundSettings " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdSoundSettings " + cmdName(scene.sceneName(), header, cmdCount) + " = { " + \
		"0x15, " + str(scene.audioSessionPreset) + ", " + "0x00, 0x00, 0x00, 0x00, " + \
		str(scene.nightSeq) + ', ' + str(scene.musicSeq) + " };\n\n"
	return cmd

def cmdRoomList(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdRoomList " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdRoomList " + cmdName(scene.sceneName(), header, cmdCount) + " = { " + \
		"0x04, " + str(len(scene.rooms)) + ", " + "(u32)&" + scene.roomListName() + " };\n\n" 
	return cmd

def cmdTransiActorList(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdTransiActorList " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdTransiActorList " + cmdName(scene.sceneName(), header, cmdCount) + " = { " + \
		"0x0E, " + str(len(scene.transitionActorList)) + ", (u32)" + scene.transitionActorListName(header) + " };\n\n"
	return cmd

def cmdMiscSettings(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdMiscSettings " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdMiscSettings " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x19, " + str(scene.cameraMode) + ", " + str(scene.mapLocation) + " };\n\n"
	return cmd

def cmdColHeader(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdColHeader " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdColHeader " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x03, 0x00, (u32)&" + scene.collision.headerName() + " };\n\n"
	return cmd

def cmdEntranceList(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdEntranceList " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdEntranceList " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x06, 0x00, (u32)" + (('&' + scene.entranceListName(header)) if len(scene.entranceList) > 0 else "0") + " };\n\n"
	return cmd

def cmdSpecialFiles(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdSpecialFiles " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdSpecialFiles " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x07, " + str(scene.naviCup) + ', ' + str(scene.globalObject) + " };\n\n"
	return cmd

def cmdPathList(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdPathList " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdPathList " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x0D, 0x00, (u32)&" + scene.pathListName() + " };\n\n"
	return cmd

def cmdSpawnList(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdSpawnList " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdSpawnList " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x00, " + str(len(scene.startPositions)) + ', (u32)' + \
		(('&' + scene.startPositionsName(header)) if len(scene.startPositions) > 0 else '0') + " };\n\n"
	return cmd

def cmdSkyboxSettings(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdSkyboxSettings " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdSkyboxSettings " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x11, 0x00, 0x00, 0x00, " + str(scene.skyboxID) + ', ' + str(scene.skyboxCloudiness) + ', ' + \
		str(scene.skyboxLighting) + " };\n\n" 
	return cmd
	
def cmdExitList(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdExitList " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdExitList " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x13, 0x00, (u32)&" + scene.exitListName(header) + " };\n\n"
	return cmd

def cmdLightSettingList(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdLightSettingList " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdLightSettingList " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x0F, " + str(len(scene.lights)) + ", (u32)" + \
		(('&' + scene.lightListName(header)) if len(scene.lights) > 0 else '0') + " };\n\n"
	return cmd

def cmdCutsceneData(scene, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdCutsceneData " + cmdName(scene.sceneName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdCutsceneData " + cmdName(scene.sceneName(), header, cmdCount) + " = { " +\
		"0x17, 0x00, (u32)&" + scene.cutsceneDataName(header) + ' };\n\n'
	return cmd

def cmdEndMarker(name, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdEndMarker " + cmdName(name, header, cmdCount) + ";\n"
	cmd.source = "SCmdEndMarker " + cmdName(name, header, cmdCount) + " = { 0x14, 0x00, 0x00 };\n\n"
	return cmd

# Room Commands
def cmdAltHeaders(name, altName, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdAltHeaders " + cmdName(name, header, cmdCount) + ';\n'
	cmd.source = "SCmdAltHeaders " + cmdName(name, header, cmdCount) + " = { " +\
		"0x18, 0x00, (u32)&" + altName + " };\n\n"
	return cmd

def cmdEchoSettings(room, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdEchoSettings " + cmdName(room.roomName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdEchoSettings " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x16, 0x00, {0x00}, " + str(room.echo) + " };\n\n"
	return cmd

def cmdRoomBehaviour(room, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdRoomBehavior " + cmdName(room.roomName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdRoomBehavior " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x08, " + str(room.roomBehaviour) + ', 0x0000' + \
		("1" if room.disableWarpSongs else "0") + \
		("1" if room.showInvisibleActors else "0") + \
		format(int(room.linkIdleMode, 16), '02X')  + " };\n\n"
	return cmd
		

def cmdSkyboxDisables(room, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdSkyboxDisables " + cmdName(room.roomName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdSkyboxDisables " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x12, 0x00, 0x00, 0x00, " + \
		("0x01" if room.disableSkybox else "0x00") + ", " +\
		("0x01" if room.disableSunMoon else "0x00") + " };\n\n"
	return cmd

def cmdTimeSettings(room, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdTimeSettings " + cmdName(room.roomName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdTimeSettings " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x10, 0x00, 0x00, 0x00, " + str(room.timeHours) + ', ' +\
		str(room.timeMinutes) + ', ' + str(room.timeSpeed) + " };\n\n" 
	return cmd

def cmdWindSettings(room, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdWindSettings " + cmdName(room.roomName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdWindSettings " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x05, 0x00, 0x00, 0x00, " + \
		str(room.windVector[0]) + ', ' +\
		str(room.windVector[1]) + ', ' +\
		str(room.windVector[2]) + ', ' +\
		str(room.windStrength) + ' };\n\n'
	return cmd

def cmdMesh(room, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdMesh " + cmdName(room.roomName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdMesh " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x0A, 0x00, (u32)&" + room.mesh.headerName() + " };\n\n"
	return cmd

def cmdObjectList(room, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdObjectList " + cmdName(room.roomName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdObjectList " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x0B, " + str(len(room.objectList)) + ", (u32)" + str(room.objectListName(header)) + " };\n\n"
	return cmd

def cmdActorList(room, header, cmdCount):
	cmd = CData()
	cmd.header = "extern " + "SCmdActorList " + cmdName(room.roomName(), header, cmdCount) + ';\n'
	cmd.source = "SCmdActorList " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x01, " + str(len(room.actorList)) + ", (u32)" + str(room.actorListName(header)) + " };\n\n" 
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

	altHeader.header = "extern u32 " + room.alternateHeadersName() + "[];\n"
	altHeader.source = "u32 " + room.alternateHeadersName() + "[] = {\n"
	
	if room.childNightHeader is not None:
		altHeader.source += "\t(u32)&" + cmdName(room.roomName(), 1, 0) + ', \n'
		altData.append(ootRoomToC(scene, room.childNightHeader, 1, textureExportSettings))
	else:
		altHeader.source += "\t0,\n"

	if room.adultDayHeader is not None:
		altHeader.source += "\t(u32)&" + cmdName(room.roomName(), 2, 0) + ', \n'
		altData.append(ootRoomToC(scene, room.adultDayHeader, 2, textureExportSettings))
	else:
		altHeader.source += "\t0,\n"

	if room.adultNightHeader is not None:
		altHeader.source += "\t(u32)&" + cmdName(room.roomName(), 3, 0) + ', \n'
		altData.append(ootRoomToC(scene, room.adultNightHeader, 3, textureExportSettings))
	else:
		altHeader.source += "\t0,\n"

	for i in range(len(room.cutsceneHeaders)):
		altHeader.source += "\t(u32)&" + cmdName(room.roomName(), i + 4, 0) + ', \n'
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
	data.header = ''.join([command.header for command in commands]) +'\n'
	data.source = ''.join([command.source for command in commands]) +'\n'

	return data

def ootRoomIncludes(scene, room):
	data = CData()
	data.source += '#include "ultra64.h"\n'
	data.source += '#include "z64.h"\n'
	data.source += '#include "macros.h"\n'
	data.source += '#include "' + room.roomName() + '.h"\n\n'
	data.source += '#include "segment_symbols.h"\n'
	data.source += '#include "command_macros_base.h"\n'
	data.source += '#include "z64cutscene_commands.h"\n'
	data.source += '#include "variables.h"\n'
	data.source += '#include "' + scene.sceneName() + '.h"\n'
	data.source += '\n'
	return data

def ootRoomToC(scene, room, headerIndex, textureExportSettings):
	roomC = CData()
	if headerIndex == 0:
		roomC.append(ootRoomIncludes(scene, room))
	
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
	roomC.append(meshHeader)
	roomC.append(altData)
	roomC.append(meshData)
	
	return roomC

def ootAlternateSceneHeadersToC(scene, textureExportSettings):
	altHeader = CData()
	altData = CData()

	altHeader.header = "extern u32 " + scene.alternateHeadersName() + "[];\n"
	altHeader.source = "u32 " + scene.alternateHeadersName() + "[] = {\n"
	
	if scene.childNightHeader is not None:
		altHeader.source += "\t(u32)&" + cmdName(scene.sceneName(), 1, 0) + ', \n'
		altData.append(ootSceneToC(scene.childNightHeader, 1, textureExportSettings))
	else:
		altHeader.source += "\t0,\n"

	if scene.adultDayHeader is not None:
		altHeader.source += "\t(u32)&" + cmdName(scene.sceneName(), 2, 0) + ', \n'
		altData.append(ootSceneToC(scene.adultDayHeader, 2, textureExportSettings))
	else:
		altHeader.source += "\t0,\n"

	if scene.adultNightHeader is not None:
		altHeader.source += "\t(u32)&" + cmdName(scene.sceneName(), 3, 0) + ', \n'
		altData.append(ootSceneToC(scene.adultNightHeader, 3, textureExportSettings))
	else:
		altHeader.source += "\t0,\n"

	for i in range(len(scene.cutsceneHeaders)):
		altHeader.source += "\t(u32)&" + cmdName(scene.sceneName(), i + 4, 0) + ', \n'
		altData.append(ootSceneToC(scene.cutsceneHeaders[i], i + 4, textureExportSettings))

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
	data.header = ''.join([command.header for command in commands]) +'\n'
	data.source = ''.join([command.source for command in commands]) +'\n'

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
	data.header = "extern EntranceEntry " + scene.entranceListName(headerIndex) + "[" + str(len(scene.entranceList)) + "];\n"
	data.source = "EntranceEntry " + scene.entranceListName(headerIndex) + "[" + str(len(scene.entranceList)) + "] = {\n"
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
	return str(vector[0]) + ', ' + str(vector[1]) + ', ' + str(vector[2])

def ootLightToC(light):
	return "\t{ " + \
		ootVectorToC(light.ambient) + ', ' +\
		ootVectorToC(light.diffuseDir0) + ', ' +\
		ootVectorToC(light.diffuse0) + ', ' +\
		ootVectorToC(light.diffuseDir1) + ', ' +\
		ootVectorToC(light.diffuse1) + ', ' +\
		ootVectorToC(light.fogColor) + ', ' +\
		light.getBlendFogShort() + ', ' +\
		str(light.drawDistance) + ' },\n'

def ootLightSettingsToC(scene, useIndoorLighting, headerIndex):
	data = CData()
	lightArraySize = len(scene.lights)
	data.header = "extern LightSettings " + scene.lightListName(headerIndex) + "[" + str(lightArraySize) + "];\n"
	data.source = "LightSettings " + scene.lightListName(headerIndex) + "[" + str(lightArraySize) + "] = {\n"
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
	data.source += "\tCS_BEGIN_CUTSCENE(" + str(1 if scene.csWriteTerminator else 0) + ", " + str(scene.csEndFrame) + "),\n"
	if scene.csWriteTerminator:
		data.source += "\tCS_TERMINATOR(" + str(scene.csTermIdx) + ", " + str(scene.csTermStart) + ", " + str(scene.csTermEnd) + "),\n"
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

def ootSceneToC(scene, headerIndex, textureExportSettings):
	sceneC = CData()

	if headerIndex == 0:
		sceneC.append(ootSceneIncludes(scene))
		meshData = ootSceneMeshToC(scene, textureExportSettings)
		colData = ootCollisionToC(scene.collision)
		roomHeaderData = ootRoomListHeaderToC(scene)
		if len(scene.pathList) > 0:
			pathData = ootPathListToC(scene)
		else:
			pathData = CData()
	else:
		meshData = CData()
		colData = CData()
		roomHeaderData = CData()
		pathData = CData()

	if scene.hasAlternateHeaders():
		altHeader, altData = ootAlternateSceneHeadersToC(scene, textureExportSettings)
	else:
		altHeader = CData()
		altData = CData()

	sceneC.append(ootSceneCommandsToC(scene, headerIndex))
	sceneC.append(altHeader)
	if len(scene.startPositions) > 0:
		sceneC.append(ootStartPositionListToC(scene, headerIndex))
	if len(scene.transitionActorList) > 0:
		sceneC.append(ootTransitionActorListToC(scene, headerIndex))
	sceneC.append(roomHeaderData)
	if len(scene.entranceList) > 0:
		sceneC.append(ootEntranceListToC(scene, headerIndex))
	if len(scene.exitList) > 0:
		sceneC.append(ootExitListToC(scene, headerIndex))
	if len(scene.lights) > 0:
		sceneC.append(ootLightSettingsToC(scene, scene.skyboxLighting == '0x01', headerIndex))
	sceneC.append(pathData)
	sceneC.append(colData)
	if scene.writeCutscene is not None:
		sceneC.append(ootCutsceneToC(scene, headerIndex))
	sceneC.append(altData)
	sceneC.append(meshData)

	return sceneC

def ootLevelToC(scene, textureExportSettings):
	levelC = OOTLevelC()
	levelC.scene = ootSceneToC(scene, 0, textureExportSettings)
	for i in range(len(scene.rooms)):
		levelC.rooms[scene.rooms[i].roomName()] = ootRoomToC(scene, scene.rooms[i], 0, textureExportSettings)
	return levelC

class OOTLevelC:
	def __init__(self):
		self.scene = CData()
		self.rooms = {}
