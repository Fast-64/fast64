import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
#from .oot_function_map import func_map
#from .oot_spline import *

from ..utility import *

class OOTActor:
	def __init__(self, actorID, position, rotation, actorParam, headerIndices):
		self.actorID = actorID
		self.actorParam = actorParam
		self.position = position
		self.rotation = rotation
		self.headerIndices = headerIndices

	
	def toC(self):
		return '{' + str(self.actorID) + ', ' + \
			str(int(round(self.position[0]))) + ', ' + \
			str(int(round(self.position[1]))) + ', ' + \
			str(int(round(self.position[2]))) + ', ' + \
			str(int(round(math.degrees(self.rotation[0])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[2])))) + ', ' + \
			str(self.actorParam) + '},'

class OOTTransitionActor:
	def __init__(self, actorID, frontRoom, backRoom, frontCam, backCam, position, rotation, actorParam):
		self.actorID = actorID
		self.actorParam = actorParam
		self.frontRoom = frontRoom
		self.backRoom = backRoom
		self.frontCam = frontCam
		self.backCam = backCam
		self.position = position
		self.rotation = rotation
	
	# TODO: Fix y rotation?
	def toC(self):
		return '{' + str(self.frontRoom) + ', ' + \
			str(self.frontCam) + ', ' + \
			str(self.backRoom) + ', ' + \
			str(self.backCam) + ', ' + \
			str(self.actorID) + ', ' + \
			str(int(round(self.position[0]))) + ', ' + \
			str(int(round(self.position[1]))) + ', ' + \
			str(int(round(self.position[2]))) + ', ' + \
			str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
			str(self.actorParam) + '},'

class OOTExit:
	def __init__(self, index):
		self.index = index

class OOTEntrance:
	def __init__(self, roomIndex, startPositionIndex):
		self.roomIndex = roomIndex
		self.startPositionIndex = startPositionIndex

class OOTStartPosition:
	def __init__(self, position, rotation, params):
		self.position = position
		self.rotation = rotation
		self.params = params
	
	def toCStartPositions(self):
		return 'ENTRANCE(' +\
			str(int(round(self.position[0]))) + ', ' + \
			str(int(round(self.position[1]))) + ', ' + \
			str(int(round(self.position[2]))) + ', ' + \
			str(int(round(math.degrees(self.rotation[0])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[2])))) + ')'

	def toCEntranceList(self):
		pass

class OOTLight:
	def __init__(self):
		self.ambient = (0,0,0)
		self.diffuse0 = (0,0,0)
		self.diffuseDir0 = (0,0,0)
		self.diffuse1 = (0,0,0)
		self.diffuseDir1 = (0,0,0)
		self.fogColor = (0,0,0)
		self.fogDistance = 0
		self.transitionSpeed = 0
		self.drawDistance = 0

class OOTCollision:
	def __init__(self):
		self.waterBoxes = []

class OOTScene:
	def __init__(self, name, model):
		self.name = toAlnum(name)
		self.rooms = {}
		self.transitionActors = []
		self.entrances = []
		self.startPositions = {}
		self.actors = []
		self.lights = []
		self.model = model
		self.collision = OOTCollision()

		# Skybox
		self.skyboxID = None
		self.skyboxCloudiness = None
		self.skyboxLighting = None

		# Camera
		self.mapLocation = None
		self.cameraMode = None

		self.childNightHeader = None
		self.adultDayHeader = None
		self.adultNightHeader = None
		self.cutsceneHeaders = []

		self.exitList = []

	def validateStartPositions(self):
		count = 0
		while count < len(self.startPositions):
			if count not in self.startPositions:
				raise PluginError("Error: Start positions do not have a consecutive list of indices.\n" +\
					"Missing index: " + str(count))
			count = count + 1
		

	def addRoom(self, roomIndex, roomName, meshType):
		roomModel = self.model.addSubModel(roomName + '_dl')
		room = OOTRoom(roomIndex, roomName, roomModel, meshType)
		if roomIndex in self.rooms:
			raise PluginError("Repeat room index " + str(roomIndex) + " for " + str(roomName))
		self.rooms[roomIndex] = room
		return room

class OOTRoomMesh:
	def __init__(self, roomName, meshType, model):
		self.roomName = roomName
		self.meshType = meshType
		self.meshEntries = []
		self.model = model

	def terminateDLs(self):
		for entry in self.meshEntries:
			entry.terminateDLs()

	def headerName(self):
		return str(self.roomName) + "_meshHeader"
	
	def entriesName(self):
		return str(self.roomName) + "_meshDListEntry"

	def headerToC(self):
		return "MeshHeader" + str(self.meshType) + " " + self.headerName() + ' = ' +\
			"{ {" + str(self.meshType) + "}, " + str(len(self.meshEntries)) + ", " +\
			"(u32)&" + self.entriesName() + ", (u32)&(" + self.entriesName() + ") + " +\
			"sizeof(" + self.entriesName() + ") };\n"
	
	def entriesToC(self):
		data = "MeshEntry" + str(self.meshType) + self.entriesName() + "[" + str(len(self.meshEntries)) + "] = \n{\n"
		for entry in self.meshEntries:
			data += '\t' + entry.entryToC(str(self.meshType)) + '\n'
		data += '};\n'
	
	def addMeshGroup(self, cullVolume):
		meshGroup = OOTRoomMeshGroup(cullVolume, self.model.DLFormat, self.roomName, len(self.meshEntries))
		self.meshEntries.append(meshGroup)
		return meshGroup
	
	def currentMeshGroup(self):
		return self.meshEntries[-1]

class OOTRoomMeshGroup:
	def __init__(self, cullVolume, DLFormat, roomName, entryIndex):
		self.opaque = None
		self.transparent = None
		self.cullVolume = cullVolume
		self.DLFormat = DLFormat
		self.roomName = roomName
		self.entryIndex = entryIndex

	def entryName(self):
		return self.roomName + "_entry_" + str(self.entryIndex)
	
	def addDLCall(self, displayList, drawLayer):
		if drawLayer == 'Opaque':
			if self.opaque is None:
				self.opaque = GfxList(self.entryName() + '_opaque', GfxListTag.Draw, self.DLFormat)
			self.opaque.commands.append(SPDisplayList(displayList))
		elif drawLayer == "Transparent":
			if self.transparent is None:
				self.transparent = GfxList(self.entryName() + '_transparent', GfxListTag.Draw, self.DLFormat)
			self.transparent.commands.append(SPDisplayList(displayList))
		else:
			raise PluginError("Unhandled draw layer: " + str(drawLayer))

	def terminateDLs(self):
		if self.opaque is not None:
			self.opaque.commands.append(SPEndDisplayList())
		
		if self.transparent is not None:
			self.transparent.commands.append(SPEndDisplayList())
	
	def entryToC(self, meshType):
		opaqueName = self.opaque.name if self.opaque is not None else "0"
		transparentName = self.transparent.name if self.transparent is not None else "0"
		data = "{ "
		if meshType == "2":
			if self.cullVolume is None:
				data += "0x7FFF, 0x7FFF, 0x8000, 0x8000, "
			else:
				data += "(s16)" + str(self.cullVolume.high[0]) + ", (s16)" + str(self.cullVolume.high[1]) + ", "
				data += "(s16)" + str(self.cullVolume.low[0]) + ", (s16)" + str(self.cullVolume.low[1]) + ", "
		data += "(u32)" + opaqueName + ", (u32)" + transparentName + '},' 
	
	def DLtoC(self):
		data = ''
		if self.opaque is not None:
			data += self.opaque.to_c() + '\n'
		if self.transparent is not None:
			data += self.transparent.to_c() + '\n'
		return data

class OOTRoom:
	def __init__(self, index, name, model, meshType):
		self.name = toAlnum(name)
		self.collision = None
		self.index = index
		self.actors = []
		self.transitionActors = []
		self.water_boxes = []
		self.mesh = OOTRoomMesh(self.name, meshType, model)

		self.entrances = []
		self.exits = []
		self.pathways = []

		# Room behaviour
		self.disableSunSongEffect = False
		self.disableActionJumping = False
		self.disableWarpSongs = False
		self.showInvisibleActors = False
		self.linkIdleMode = None

		self.customBehaviourX = None
		self.customBehaviourY = None

		# Wind 
		self.setWind = False
		self.windVector = [0,0,0]
		self.windStrength = 0

		# Time
		self.timeValue = 0xFFFF
		self.timeSpeed = 0xA

		# Skybox
		self.disableSkybox = False
		self.disableSunMoon = False

		# Echo
		self.echo = 0x00

		self.objectList = []

		self.childNightHeader = None
		self.adultDayHeader = None
		self.adultNightHeader = None
		self.cutsceneHeaders = []

	def toCWindCommand(self):

		return "SET_WIND(" + '0x' + format(self.windVector[0], 'X') + ', ' +\
			'0x' + format(self.windVector[1], 'X') + ', ' +\
			'0x' + format(self.windVector[2], 'X') + ', ' +\
			'0x' + format(self.windStrength, 'X') + ')'

	def toCScript(self, includeRooms):
		data = ''
		data += '\tAREA(' + str(self.index) + ', ' + self.geolayout.name + '),\n'
		for warpNode in self.warpNodes:
			data += '\t\t' + warpNode + ',\n'
		for obj in self.objects:
			data += '\t\t' + obj.to_c() + ',\n'
		data += '\t\tTERRAIN(' + self.collision.name + '),\n'
		if includeRooms:
			data += '\t\tROOMS(' + self.collision.rooms_name() + '),\n'
		data += '\t\tMACRO_OBJECTS(' + self.macros_name() + '),\n'
		if self.music_seq is None:
			data += '\t\tSTOP_MUSIC(0),\n'
		else:
			data += '\t\tSET_BACKGROUND_MUSIC(' + self.music_preset + ', ' + self.music_seq + '),\n'
		if self.startDialog is not None:
			data += '\t\tSHOW_DIALOG(0x00, ' + self.startDialog + '),\n'
		data += '\t\tTERRAIN_TYPE(' + self.terrain_type + '),\n'
		data += '\tEND_AREA(),\n\n'
		return data
	
	def toCPathways(self):
		data = ''
		for spline in self.pathways:
			data += spline.to_c() + '\n'
		return data
	
	def toCDefSplines(self):
		data = ''
		for spline in self.splines:
			data += spline.to_c_def()
		return data

class OOTWaterBox(BoxEmpty):
	def __init__(self, lightingSetting, cameraSetting, position, scale, emptyScale):
		self.lightingSetting = lightingSetting
		self.cameraSetting = cameraSetting
		BoxEmpty.__init__(self, position, scale, emptyScale)
	
	def to_c(self):
		data = 'WATER_BOX(' + \
			str(self.waterBoxType) + ', ' + \
			str(int(round(self.low[0]))) + ', ' + \
			str(int(round(self.low[1]))) + ', ' + \
			str(int(round(self.high[0]))) + ', ' + \
			str(int(round(self.high[1]))) + ', ' + \
			str(int(round(self.height))) + '),\n'
		return data
