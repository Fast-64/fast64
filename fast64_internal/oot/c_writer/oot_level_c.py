import math
from ..oot_f3d_writer import *
from ..oot_level_writer import *
from .oot_collision_c import *

def cmdName(name, header, index):
	return name + "_header" + str(header) + "_cmd" + str(index)

# Scene Commands
def cmdCameraList(scene, header, cmdCount):
	return "SCmdCsCameraList " + cmdName(scene.name, header, cmdCount) + " = { " + \
		"0x02, " + str(len(scene.cameraList)) + ', ' + scene.cameraListName() + ' };\n'

def cmdSoundSettings(scene, header, cmdCount):
	cmd = "SCmdSoundSettings " + cmdName(scene.name, header, cmdCount) + " = { " + \
		" 0x15, " + str(scene.audioSessionPreset) + ", " + "0x00, 0x00, 0x00, 0x00, " + \
		str(scene.nightSeq) + ', ' + str(scene.musicSeq) + " };\n"
	return cmd

def cmdRoomList(scene, header, cmdCount):
	return "SCmdRoomList " + cmdName(scene.name, header, cmdCount) + " = { " + \
		"0x04, " + str(len(scene.rooms)) + ", " + "(u32)&" + scene.roomListName() + " };\n" 

def cmdTransiActorList(scene, header, cmdCount):
	return "SCmdTransiActorList " + cmdName(scene.name, header, cmdCount) + " = { " + \
		"0x0E, " + str(len(scene.transitionActorList)) + ", (u32)&" + scene.transitionActorListName() + " };\n"

def cmdMiscSettings(scene, header, cmdCount):
	return "SCmdMiscSettings " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x19, " + str(scene.cameraMode) + ", " + str(scene.mapLocation) + " };\n"

def cmdColHeader(scene, header, cmdCount):
	return "SCmdColHeader " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x03, 0x00, (u32)&" + scene.collision.headerName() + " };\n"

def cmdEntranceList(scene, header, cmdCount):
	return "SCmdEntranceList " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x06, 0x00, (u32)&" + scene.entranceListName() + " };\n"

def cmdSpecialFiles(scene, header, cmdCount):
	return "SCmdSpecialFiles " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x07, " + str(scene.naviCup) + ', ' + str(scene.globalObject) + " };\n"

def cmdPathList(scene, header, cmdCount):
	return "SCmdPathList " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x0D, 0x00, " + scene.pathListName() + " };\n"

def cmdSpawnList(scene, header, cmdCount):
	return "SCmdSpawnList " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x00, " + str(len(scene.startPositions)) + ', (u32)&' + scene.startPositionsName() + " };\n"

def cmdSkyboxSettings(scene, header, cmdCount):
	return "SCmdSkyboxSettings " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x11, 0x00, 0x00, 0x00, " + str(scene.skyboxID) + ', ' + str(scene.skyboxCloudiness) + ', ' + \
		str(scene.skyboxLighting) + " };\n" 

def cmdExitList(scene, header, cmdCount):
	return "SCmdExitList " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x13, 0x00, (u32)&" + scene.exitListName() + " };\n"

def cmdLightSettingList(scene, header, cmdCount):
	return "SCmdLightSettingList " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x0F, " + str(len(scene.lights)) + ", (u32)&" + scene.lightListName() + " };\n"

def cmdCustsceneData(scene, header, cmdCount):
	return "SCmdCutsceneData " + cmdName(scene.name, header, cmdCount) + " = { " +\
		"0x17, 0x00, " + scene.cutsceneDataName() + ' };\n'

def cmdEndMarker(name, header, cmdCount):
	return "SCmdEndMarker " + cmdName(name, header, cmdCount) + " = { 0x14, 0x00, 0x00 };\n"

# Room Commands
def cmdAltHeaders(room, header, cmdCount):
	return "SCmdAltHeaders " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x18, 0x00, " + room.alternateHeadersName() + " };\n"

def cmdEchoSettings(room, header, cmdCount):
	return "SCmdEchoSettings " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x16, 0x00, {0x00}, " + str(room.echo) + " };\n"

def cmdRoomBehaviour(room, header, cmdCount):
	return "SCmdRoomBehavior " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x08, " + str(room.roomBehaviour) + ', 0x0000' + \
		("1" if room.disableWarpSongs else "0") + \
		("1" if room.showInvisibleActors else "0") + \
		format(int(room.linkIdleMode, 16), '02X')  + "};\n"

def cmdSkyboxDisables(room, header, cmdCount):
	return "SCmdSkyboxDisables " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x12, 0x00, 0x00, 0x00, " + \
		("0x01" if room.disableSkybox else "0x00") + ", " +\
		("0x01" if room.disableSunMoon else "0x00") + " };\n"

def cmdTimeSettings(room, header, cmdCount):
	return "SCmdTimeSettings " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x10, 0x00, 0x00, 0x00, " + str(room.timeHours) + ', ' +\
		str(room.timeMinutes) + ', ' + str(room.timeSpeed) + " };\n" 

def cmdWindSettings(room, header, cmdCount):
	return "SCmdWindSettings " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x05, 0x00, 0x00, 0x00, " + \
		str(room.windVector[0]) + ', ' +\
		str(room.windVector[1]) + ', ' +\
		str(room.windVector[2]) + ', ' +\
		str(room.windStrength) + ' };\n'

def cmdMesh(room, header, cmdCount):
	return "SCmdMesh " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x0A, 0x00, (u32)&" + room.mesh.headerName() + " };\n"

def cmdObjectList(room, header, cmdCount):
	return "SCmdObjectList " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x0B, " + str(len(room.objectList)) + ", " + str(room.objectListName()) + " };\n"

def cmdActorList(room, header, cmdCount):
	return "SCmdActorList " + cmdName(room.roomName(), header, cmdCount) + " = { " +\
		"0x01, " + str(len(room.actorList)) + ", " + str(room.actorListName()) + " };\n" 

def ootObjectListToC(room):
	data = 's16 ' + room.objectListName() + "[] = \n{\n"
	for objectItem in room.objectList:
		data += '\t' + objectItem + ',\n'
	data += '};\n\n'
	return data

def ootActorToC(actor):
	return '{ ' + str(actor.actorID) + ', ' + \
		str(int(round(actor.position[0]))) + ', ' + \
		str(int(round(actor.position[1]))) + ', ' + \
		str(int(round(actor.position[2]))) + ', ' + \
		str(int(round(math.degrees(actor.rotation[0])))) + ', ' + \
		str(int(round(math.degrees(actor.rotation[1])))) + ', ' + \
		str(int(round(math.degrees(actor.rotation[2])))) + ', ' + \
		str(actor.actorParam) + ' },\n'

def ootActorListToC(room):
	data = "ActorEntry " + room.actorListName() + "[" + str(len(room.actorList)) + "] = \n{\n"
	for actor in room.actorList:
		data += '\t' + ootActorToC(actor)
	data += "};\n\n"
	return data

def ootAlternateRoomHeadersToC(room):
	data = ''
	header = "u32 " + room.alternateHeadersName() + "[] = \n{\n"
	if room.childNightHeader is not None:
		header += "(u32)&" + cmdName(room.roomName(), 1, 0) + ', \n'
		data += ootRoomToC(room.childNightHeader, 1)
	else:
		header += "0,\n"

	if room.adultDayHeader is not None:
		header += "(u32)&" + cmdName(room.roomName(), 2, 0) + ', \n'
		data += ootRoomToC(room.adultDayHeader, 2)
	else:
		header += "0,\n"

	if room.adultNightHeader is not None:
		header += "(u32)&" + cmdName(room.roomName(), 3, 0) + ', \n'
		data += ootRoomToC(room.adultNightHeader, 3)
	else:
		header += "0,\n"

	for i in range(len(room.cutsceneHeaders)):
		header += "(u32)&" + cmdName(room.roomName(), i + 4, 0) + ', \n'
		data += ootRoomToC(room.cutsceneHeaders[i], i + 4)

	header += '};\n\n'

	return header, data

def ootMeshEntryToC(meshEntry, meshType):
	opaqueName = meshEntry.opaque.name if meshEntry.opaque is not None else "0"
	transparentName = meshEntry.transparent.name if meshEntry.transparent is not None else "0"
	data = "{ "
	if meshType == "2":
		if meshEntry.cullVolume is None:
			data += "0x7FFF, 0x7FFF, 0x8000, 0x8000, "
		else:
			data += "(s16)" + str(meshEntry.cullVolume.high[0]) + ", (s16)" + str(meshEntry.cullVolume.high[1]) + ", "
			data += "(s16)" + str(meshEntry.cullVolume.low[0]) + ", (s16)" + str(meshEntry.cullVolume.low[1]) + ", "
	data += "(u32)" + opaqueName + ", (u32)" + transparentName + ' },\n' 

	return data

def ootMeshToC(mesh):
	meshHeader = "MeshHeader" + str(mesh.meshType) + " " + mesh.headerName() + ' = ' +\
		"{ {" + str(mesh.meshType) + "}, " + str(len(mesh.meshEntries)) + ", " +\
		"(u32)&" + mesh.entriesName() + ", (u32)&(" + mesh.entriesName() + ") + " +\
		"sizeof(" + mesh.entriesName() + ") };\n\n"

	meshEntries = "MeshEntry" + str(mesh.meshType) + " " + mesh.entriesName() + "[" + str(len(mesh.meshEntries)) + "] = \n{\n"
	meshData = ''
	for entry in mesh.meshEntries:
		meshEntries += '\t' + ootMeshEntryToC(entry, str(mesh.meshType))
		if entry.opaque is not None:
			meshData += entry.opaque.to_c(mesh.model.f3d) + '\n\n'
		if entry.transparent is not None:
			meshData += entry.transparent.to_c(mesh.model.f3d) + '\n\n'
	meshEntries += '};\n\n'
	staticData, dynamicData, texC = mesh.model.to_c(False, False, "", OOTGfxFormatter(ScrollMethod.Vertex))
	meshData += staticData + dynamicData
	#headerStatic + headerDynamic

	return meshHeader + meshEntries, meshData

def ootRoomCommandsToC(room, headerIndex):
	commands = []
	if room.hasAlternateHeaders():
		commands.append(cmdAltHeaders(room, headerIndex, len(commands)))
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
	data = ''.join(commands) +'\n'

	return data

def ootRoomToC(room, headerIndex):
	roomC = CData()
	if room.hasAlternateHeaders():
		altHeader, altData = ootAlternateRoomHeadersToC(room)
	else:
		altHeader = ''
		altData = ''

	if headerIndex == 0:
		meshHeader, meshData = ootMeshToC(room.mesh)

	roomC.source = ''
	roomC.source += ootRoomCommandsToC(room, headerIndex)
	roomC.source += altHeader
	if len(room.objectList) > 0:
		roomC.source += ootObjectListToC(room)
	if len(room.actorList) > 0:
		roomC.source += ootActorListToC(room)
	roomC.source += meshHeader
	roomC.source += altData
	roomC.source += meshData
	
	return roomC

def ootSceneCommandsToC(scene, headerIndex):
	commands = []
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
	if scene.custcene is not None:
		commands.append(cmdCustsceneData(scene, headerIndex, len(commands)))
	commands.append(cmdEndMarker(scene.name, headerIndex, len(commands)))
	data = ''.join(commands) + '\n'
	return data

def ootStartPositionListToC(scene):
	data = "ActorEntry " + scene.startPositionsName() + "[] = \n{\n"
	for i in range(len(scene.startPositions)):
		data += '\t' + ootActorToC(scene.startPositions[i])
	data += '};\n\n'
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
		str(int(round(math.degrees(transActor.rotationY)))) + ', ' + \
		str(transActor.actorParam) + ' },\n'

def ootTransitionActorListToC(scene):
	data = "TransitionActorEntry " + scene.transitionActorListName() + "[] = \n{\n"
	for transActor in scene.transitionActorList:
		data += '\t' + ootTransitionActorToC(transActor)
	data += '};\n\n'
	return data

def ootRoomListEntryToC(room):
	return "{ (u32)" + room.roomName() + "SegmentRomStart, (u32)" + room.roomName() + "SegmentRomEnd },\n"

def ootRoomListHeaderToC(scene):
	data = "Romfile " + scene.roomListName() + "[] = \n{\n"
	for i in range(len(scene.rooms)):
		data += '\t' + ootRoomListEntryToC(scene.rooms[i])
	data += '};\n\n'
	return data

def ootEntranceToC(entrance):
	return "{ " + str(entrance.startPositionIndex) + ', ' + str(entrance.roomIndex) + ' },\n'

def ootEntranceListToC(scene):
	data = "EntranceEntry " + scene.entranceListName() + "[] = \n{\n"
	for entrance in scene.entranceList:
		data += '\t' + ootEntranceToC(entrance)
	data += '};\n\n'
	return data

def ootExitListToC(scene):
	data = "ExitList " + scene.exitListName() + "[] = \n{\n"
	for exitEntry in scene.exitList:
		data += '\t' + str(exitEntry.index) + ',\n'
	data += '};\n\n'
	return data

def ootVectorToC(vector):
	return str(vector[0]) + ', ' + str(vector[1]) + ', ' + str(vector[2])

def ootLightToC(light):
	return "{ " + \
		ootVectorToC(light.ambient) + ', ' +\
		ootVectorToC(light.diffuse0) + ', ' +\
		ootVectorToC(light.diffuseDir0) + ', ' +\
		ootVectorToC(light.diffuse1) + ', ' +\
		ootVectorToC(light.diffuseDir1) + ', ' +\
		ootVectorToC(light.fogColor) + ', ' +\
		light.getBlendFogShort() + ', ' +\
		str(light.fogFar) + ' },\n'

def ootLightSettingsToC(scene):
	data = "LightSettings " + scene.lightListName() + "[] = \n{\n"
	for light in scene.lights:
		data += '\t' + ootLightToC(light)
	data += '};\n\n'
	return data

def ootPathToC(path):
	data = "Vec3s " + path.pathName() + '[] = \n{\n'
	for point in path.points:
		data += '\t' + "{ " +\
			str(int(round(point[0]))) + ', ' +\
			str(int(round(point[1]))) + ', ' +\
			str(int(round(point[2]))) + ' },\n'
	data += '};\n\n'

	return data
	
def ootPathListToC(scene):
	header = "Path " + scene.pathListName() + "[] = \n{\n"
	data = ''
	for path in scene.pathList:
		header += '\t' + "{ " + str(len(path.points)) + ', (u32)' + path.pathName() + " },\n"
		data += ootPathToC(path)
	header += '};\n\n'
	return data + header

def ootCutsceneToC(scene):
	raise PluginError("Cutscenes not implemented.")

def ootSceneToC(scene):
	levelC = OOTLevelC()
	levelC.scene.source += ootSceneCommandsToC(scene, 0)
	for i in range(len(scene.rooms)):
		levelC.rooms.append(ootRoomToC(scene.rooms[i], 0))

	levelC.scene.source += ootStartPositionListToC(scene)
	if len(scene.transitionActorList) > 0:
		levelC.scene.source += ootTransitionActorListToC(scene)
	levelC.scene.source += ootRoomListHeaderToC(scene)
	levelC.scene.source += ootEntranceListToC(scene)
	if len(scene.exitList) > 0:
		levelC.scene.source += ootExitListToC(scene)
	levelC.scene.source += ootLightSettingsToC(scene)
	if len(scene.pathList) > 0:
		levelC.scene.source += ootPathListToC(scene)
	levelC.scene.source += ootCollisionToC(scene.collision)
	if scene.custcene is not None:
		levelC.scene.source += ootCutsceneToC(scene)

	return levelC

class OOTLevelC:
	def __init__(self):
		self.scene = CData()
		self.rooms = []