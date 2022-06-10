import bpy, bmesh, os, math, re, shutil, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..utility import *
from .oot_utility import *
from .oot_constants import *

ootEnumConveyer = [
	("None", "None", "None"),
	("Land", "Land", "Land"),
	("Water", "Water", "Water"),
]

ootEnumFloorSetting = [
	("Custom", "Custom", "Custom"),
	("0x00", "Default", "Default"),
	("0x05", "Void (Small)", "Void (Small)"),
	("0x06", "Grab Wall", "Grab Wall"),
	("0x08", "Stop Air Momentum", "Stop Air Momentum"),
	("0x09", "Fall Instead Of Jumping", "Fall Instead Of Jumping"),
	("0x0B", "Dive", "Dive"),
	("0x0C", "Void (Large)", "Void (Large)"),
]

ootEnumWallSetting = [
	("Custom", "Custom", "Custom"),
	("0x00", "None", "None"),
	("0x01", "No Ledge Grab", "No Ledge Grab"),
	("0x02", "Ladder", "Ladder"),
	("0x03", "Ladder Top", "Ladder Top"),
	("0x04", "Vines", "Vines"),
	("0x05", "Crawl Space", "Crawl Space"),
	("0x06", "Crawl Space 2", "Crawl Space 2"),
	("0x07", "Push Block", "Push Block"),
]

ootEnumFloorProperty = [
	("Custom", "Custom", "Custom"),
	("0x00", "None", "None"),
	("0x01", "Haunted Wasteland Camera", "Haunted Wasteland Camera"),
	("0x02", "Hurt Floor (Spikes)", "Hurt Floor (Spikes)"),
	("0x03", "Hurt Floor (Lava)", "Hurt Floor (Lava)"),
	("0x04", "Shallow Sand", "Shallow Sand"),
	("0x05", "Slippery", "Slippery"),
	("0x06", "No Fall Damage", "No Fall Damage"),
	("0x07", "Quicksand Crossing (Epona Uncrossable)", "Quicksand Crossing (Epona Uncrossable)"),
	("0x08", "Jabu Jabu's Belly", "Jabu Jabu's Belly"),
	("0x09", "Void", "Void"),
	("0x0A", "Link Looks Up", "Link Looks Up"),
	("0x0B", "Quicksand Crossing (Epona Crossable)", "Quicksand Crossing (Epona Crossable)")
]

ootEnumCollisionTerrain = [
	("Custom", "Custom", "Custom"),
	("0x00", "Walkable", "Walkable"),
	("0x01", "Steep", "Steep"),
	("0x02", "Walkable (Preserves Exit Flags)", "Walkable (Preserves Exit Flags)"),
	("0x03", "Walkable (?)", "Walkable (?)"),
]

ootEnumCollisionSound = [
	("Custom", "Custom", "Custom"),
	("0x00", "Earth", "Earth"),
	("0x01", "Sand", "Sand"),
	("0x02", "Stone", "Stone"),
	("0x03", "Wet Stone", "Wet Stone"),
	("0x04", "Shallow Water", "Shallow Water"),
	("0x05", "Water", "Water"),
	("0x06", "Grass", "Grass"),
	("0x07", "Lava/Goo", "Lava/Goo"),
	("0x08", "Earth", "Earth"),
	("0x09", "Wooden Plank", "Wooden Plank"),
	("0x0A", "Packed Earth/Wood", "Packed Earth/Wood"),
	("0x0B", "Earth", "Earth"),
	("0x0C", "Ceramic/Ice", "Ceramic/Ice"),
	("0x0D", "Loose Earth", "Loose Earth"),
]

ootEnumConveyorSpeed = [
	("Custom", "Custom", "Custom"),
	("0x00", "None", "None"),
	("0x01", "Slow", "Slow"),
	("0x02", "Medium", "Medium"),
	("0x03", "Fast", "Fast"),
]

ootEnumCameraSType = [
	("Custom", "Custom", "Custom"),
	("CAM_SET_NONE", "None", "None"),
    ("CAM_SET_NORMAL0", "Normal0", "Normal0"),
    ("CAM_SET_NORMAL1", "Normal1", "Normal1"),
    ("CAM_SET_DUNGEON0", "Dungeon0", "Dungeon0"),
    ("CAM_SET_DUNGEON1", "Dungeon1", "Dungeon1"),
    ("CAM_SET_NORMAL3", "Normal3", "Normal3"),
    ("CAM_SET_HORSE", "Horse", "Horse"),
    ("CAM_SET_BOSS_GOHMA", "Boss_gohma", "Boss_gohma"),
    ("CAM_SET_BOSS_DODONGO", "Boss_dodongo", "Boss_dodongo"),
    ("CAM_SET_BOSS_BARINADE", "Boss_barinade", "Boss_barinade"),
    ("CAM_SET_BOSS_PHANTOM_GANON", "Boss_phantom_ganon", "Boss_phantom_ganon"),
    ("CAM_SET_BOSS_VOLVAGIA", "Boss_volvagia", "Boss_volvagia"),
    ("CAM_SET_BOSS_BONGO", "Boss_bongo", "Boss_bongo"),
    ("CAM_SET_BOSS_MORPHA", "Boss_morpha", "Boss_morpha"),
    ("CAM_SET_TWINROVA_PLATFORM", "Twinrova_platform", "Twinrova_platform"),
    ("CAM_SET_TWINROVA_FLOOR", "Twinrova_floor", "Twinrova_floor"),
    ("CAM_SET_BOSS_GANONDORF", "Boss_ganondorf", "Boss_ganondorf"),
    ("CAM_SET_BOSS_GANON", "Boss_ganon", "Boss_ganon"),
    ("CAM_SET_TOWER_CLIMB", "Tower_climb", "Tower_climb"),
    ("CAM_SET_TOWER_UNUSED", "Tower_unused", "Tower_unused"),
    ("CAM_SET_MARKET_BALCONY", "Market_balcony", "Market_balcony"),
    ("CAM_SET_CHU_BOWLING", "Chu_bowling", "Chu_bowling"),
    ("CAM_SET_PIVOT_CRAWLSPACE", "Pivot_crawlspace", "Pivot_crawlspace"),
    ("CAM_SET_PIVOT_SHOP_BROWSING", "Pivot_shop_browsing", "Pivot_shop_browsing"),
    ("CAM_SET_PIVOT_IN_FRONT", "Pivot_in_front", "Pivot_in_front"),
    ("CAM_SET_PREREND_FIXED", "Prerend_fixed", "Prerend_fixed"),
    ("CAM_SET_PREREND_PIVOT", "Prerend_pivot", "Prerend_pivot"),
    ("CAM_SET_PREREND_SIDE_SCROLL", "Prerend_side_scroll", "Prerend_side_scroll"),
    ("CAM_SET_DOOR0", "Door0", "Door0"),
    ("CAM_SET_DOORC", "Doorc", "Doorc"),
    ("CAM_SET_CRAWLSPACE", "Crawlspace", "Crawlspace"),
    ("CAM_SET_START0", "Start0", "Start0"),
    ("CAM_SET_START1", "Start1", "Start1"),
    ("CAM_SET_FREE0", "Free0", "Free0"),
    ("CAM_SET_FREE2", "Free2", "Free2"),
    ("CAM_SET_PIVOT_CORNER", "Pivot_corner", "Pivot_corner"),
    ("CAM_SET_PIVOT_WATER_SURFACE", "Pivot_water_surface", "Pivot_water_surface"),
    ("CAM_SET_CS_0", "Cs_0", "Cs_0"),
    ("CAM_SET_CS_TWISTED_HALLWAY", "Twisted_Hallway", "Twisted_Hallway"),
    ("CAM_SET_FOREST_BIRDS_EYE", "Forest_birds_eye", "Forest_birds_eye"),
    ("CAM_SET_SLOW_CHEST_CS", "Slow_chest_cs", "Slow_chest_cs"),
    ("CAM_SET_ITEM_UNUSED", "Item_unused", "Item_unused"),
    ("CAM_SET_CS_3", "Cs_3", "Cs_3"),
    ("CAM_SET_CS_ATTENTION", "Cs_attention", "Cs_attention"),
    ("CAM_SET_BEAN_GENERIC", "Bean_generic", "Bean_generic"),
    ("CAM_SET_BEAN_LOST_WOODS", "Bean_lost_woods", "Bean_lost_woods"),
    ("CAM_SET_SCENE_UNUSED", "Scene_unused", "Scene_unused"),
    ("CAM_SET_SCENE_TRANSITION", "Scene_transition", "Scene_transition"),
    ("CAM_SET_FIRE_PLATFORM", "Fire_platform", "Fire_platform"),
    ("CAM_SET_FIRE_STAIRCASE", "Fire_staircase", "Fire_staircase"),
    ("CAM_SET_FOREST_UNUSED", "Forest_unused", "Forest_unused"),
    ("CAM_SET_FOREST_DEFEAT_POE", "Defeat_poe", "Defeat_poe"),
    ("CAM_SET_BIG_OCTO", "Big_octo", "Big_octo"),
    ("CAM_SET_MEADOW_BIRDS_EYE", "Meadow_birds_eye", "Meadow_birds_eye"),
    ("CAM_SET_MEADOW_UNUSED", "Meadow_unused", "Meadow_unused"),
    ("CAM_SET_FIRE_BIRDS_EYE", "Fire_birds_eye", "Fire_birds_eye"),
    ("CAM_SET_TURN_AROUND", "Turn_around", "Turn_around"),
    ("CAM_SET_PIVOT_VERTICAL", "Pivot_vertical", "Pivot_vertical"),
    ("CAM_SET_NORMAL2", "Normal2", "Normal2"),
    ("CAM_SET_FISHING", "Fishing", "Fishing"),
    ("CAM_SET_CS_C", "Cs_c", "Cs_c"),
    ("CAM_SET_JABU_TENTACLE", "Jabu_tentacle", "Jabu_tentacle"),
    ("CAM_SET_DUNGEON2", "Dungeon2", "Dungeon2"),
    ("CAM_SET_DIRECTED_YAW", "Directed_yaw", "Directed_yaw"),
    ("CAM_SET_PIVOT_FROM_SIDE", "Pivot_from_side", "Pivot_from_side"),
    ("CAM_SET_NORMAL4", "Normal4", "Normal4"),
]

class OOTCollisionVertex:
	def __init__(self, position):
		self.position = position

class OOTCollisionPolygon:
	def __init__(self, indices, normal, distance):
		self.indices = indices
		self.normal = normal
		self.distance = distance

	def convertShort02(self, ignoreCamera, ignoreActor, ignoreProjectile):
		vertPart = self.indices[0] & 0x1FFF
		colPart = (1 if ignoreCamera else 0) +\
			(2 if ignoreActor else 0) +\
			(4 if ignoreProjectile else 0)

		return vertPart | (colPart << 13)

	def convertShort04(self, enableConveyor):
		vertPart = self.indices[1] & 0x1FFF
		conveyorPart = 1 if enableConveyor else 0

		return vertPart | (conveyorPart << 13)

	def convertShort06(self):
		return self.indices[2] & 0x1FFF

class OOTPolygonType:
	def __eq__(self, other):
		return \
			self.eponaBlock == other.eponaBlock and\
			self.decreaseHeight == other.decreaseHeight and\
			self.floorSetting == other.floorSetting and\
			self.wallSetting == other.wallSetting and\
			self.floorProperty == other.floorProperty and\
			self.exitID == other.exitID and\
			self.cameraID == other.cameraID and\
			self.isWallDamage == other.isWallDamage and\
			self.enableConveyor == other.enableConveyor and\
			self.conveyorRotation == other.conveyorRotation and\
			self.conveyorSpeed == other.conveyorSpeed and\
			self.hookshotable == other.hookshotable and\
			self.echo == other.echo and\
			self.lightingSetting == other.lightingSetting and\
			self.terrain == other.terrain and\
			self.sound == other.sound and\
			self.ignoreCameraCollision == other.ignoreCameraCollision and\
			self.ignoreActorCollision == other.ignoreActorCollision and\
			self.ignoreProjectileCollision == other.ignoreProjectileCollision
	
	def __ne__(self, other):
		return \
			self.eponaBlock != other.eponaBlock or\
			self.decreaseHeight != other.decreaseHeight or\
			self.floorSetting != other.floorSetting or\
			self.wallSetting != other.wallSetting or\
			self.floorProperty != other.floorProperty or\
			self.exitID != other.exitID or\
			self.cameraID != other.cameraID or\
			self.isWallDamage != other.isWallDamage or\
			self.enableConveyor != other.enableConveyor or\
			self.conveyorRotation != other.conveyorRotation or\
			self.conveyorSpeed != other.conveyorSpeed or\
			self.hookshotable != other.hookshotable or\
			self.echo != other.echo or\
			self.lightingSetting != other.lightingSetting or\
			self.terrain != other.terrain or\
			self.sound != other.sound or\
			self.ignoreCameraCollision != other.ignoreCameraCollision or\
			self.ignoreActorCollision != other.ignoreActorCollision or\
			self.ignoreProjectileCollision != other.ignoreProjectileCollision

	def __hash__(self):
		return hash((self.eponaBlock, 
			self.decreaseHeight, 
			self.floorSetting, 
			self.wallSetting, 
			self.floorProperty, 
			self.exitID, 
			self.cameraID, 
			self.isWallDamage, 
			self.enableConveyor, 
			self.conveyorRotation, 
			self.conveyorSpeed, 
			self.hookshotable, 
			self.echo, 
			self.lightingSetting, 
			self.terrain, 
			self.sound, 
			self.ignoreCameraCollision, 
			self.ignoreActorCollision, 
			self.ignoreProjectileCollision))

	def __init__(self):
		self.eponaBlock = None #eponaBlock
		self.decreaseHeight = None #decreaseHeight
		self.floorSetting = None #floorSetting
		self.wallSetting = None #wallSetting
		self.floorProperty = None #floorProperty
		self.exitID = None #exitID
		self.cameraID = None #cameraID
		self.isWallDamage = None #isWallDamage
		self.enableConveyor = None
		self.conveyorRotation = None #conveyorDirection
		self.conveyorSpeed = None #conveyorSpeed
		self.hookshotable = None #hookshotable
		self.echo = None #echo
		self.lightingSetting = None #lightingSetting
		self.terrain = None #terrain
		self.sound = None #sound
		self.ignoreCameraCollision = None
		self.ignoreActorCollision = None
		self.ignoreProjectileCollision = None

	def convertHigh(self):
		value = ((1 if self.eponaBlock else 0) << 31) |\
			((1 if self.decreaseHeight else 0) << 30) |\
			(int(self.floorSetting, 16) << 26) |\
			(int(self.wallSetting, 16) << 21) |\
			(int(self.floorProperty, 16) << 13) |\
			(self.exitID << 8) |\
			(self.cameraID << 0)

		return convertIntTo2sComplement(value, 4, False)

	def convertLow(self):
		value = ((1 if self.isWallDamage else 0) << 27) |\
			(self.conveyorRotation << 21) |\
			(self.conveyorSpeed << 18) |\
			((1 if self.hookshotable else 0) << 17) |\
			(int(self.echo, 16) << 11) |\
			(self.lightingSetting << 6) |\
			(int(self.terrain, 16) << 4) |\
			(int(self.sound, 16) << 0)

		return convertIntTo2sComplement(value, 4, False)

class OOTCollision:
	def __init__(self, ownerName):
		self.ownerName = ownerName
		self.bounds = []
		self.vertices = []
		# dict of polygon type : polygon list
		self.polygonGroups = {}
		self.cameraData = None
		self.waterBoxes = []

	def polygonCount(self):
		count = 0
		for polygonType, polygons in self.polygonGroups.items():
			count += len(polygons)
		return count

	def headerName(self):
		return self.ownerName + "_collisionHeader"

	def verticesName(self):
		return self.ownerName + "_vertices"

	def polygonsName(self):
		return self.ownerName + "_polygons"

	def polygonTypesName(self):
		return self.ownerName + "_polygonTypes"
	
	def camDataName(self):
		return self.ownerName + "_camData"

	def waterBoxesName(self):
		return self.ownerName + "_waterBoxes"

def getPolygonType(collisionProp):
	polygonType = OOTPolygonType()
	polygonType.ignoreCameraCollision = collisionProp.ignoreCameraCollision
	polygonType.ignoreActorCollision = collisionProp.ignoreActorCollision
	polygonType.ignoreProjectileCollision = collisionProp.ignoreProjectileCollision
	polygonType.eponaBlock = collisionProp.eponaBlock
	polygonType.decreaseHeight = collisionProp.decreaseHeight
	polygonType.floorSetting = getCustomProperty(collisionProp, 'floorSetting')
	polygonType.wallSetting = getCustomProperty(collisionProp, 'wallSetting')
	polygonType.floorProperty = getCustomProperty(collisionProp, 'floorProperty')
	polygonType.exitID = collisionProp.exitID
	polygonType.cameraID = collisionProp.cameraID
	polygonType.isWallDamage = collisionProp.isWallDamage
	polygonType.enableConveyor = collisionProp.conveyorOption == "Land"
	if collisionProp.conveyorOption != "None":
		polygonType.conveyorRotation = int(collisionProp.conveyorRotation / (2 * math.pi) * 0x3F)
		polygonType.conveyorSpeed = int(getCustomProperty(collisionProp, 'conveyorSpeed'), 16) + \
			(4 if collisionProp.conveyorKeepMomentum else 0)
	else:
		polygonType.conveyorRotation = 0
		polygonType.conveyorSpeed = 0

	polygonType.hookshotable = collisionProp.hookshotable
	polygonType.echo = collisionProp.echo
	polygonType.lightingSetting = collisionProp.lightingSetting
	polygonType.terrain = getCustomProperty(collisionProp, "terrain")
	polygonType.sound = getCustomProperty(collisionProp, "sound")
	return polygonType

class OOTWaterBox(BoxEmpty):
	def __init__(self, roomIndex, lightingSetting, cameraSetting, position, scale, emptyScale):
		self.roomIndex = roomIndex
		self.lightingSetting = lightingSetting
		self.cameraSetting = cameraSetting
		BoxEmpty.__init__(self, position, scale, emptyScale)

	def propertyData(self):
		value = (int(self.roomIndex) << 13) |\
			(self.lightingSetting << 8) |\
			(self.cameraSetting << 0)
		return convertIntTo2sComplement(value, 4, False)

class OOTCameraData:
	def __init__(self, ownerName):
		self.ownerName = ownerName
		self.camPosDict = {}

	def camDataName(self):
		return self.ownerName + "_camData"

	def camPositionsName(self):
		return self.ownerName + "_camPosData"

	def validateCamPositions(self):
		count = 0
		while count < len(self.camPosDict):
			if count not in self.camPosDict:
				raise PluginError("Error: Camera positions do not have a consecutive list of indices.\n" +\
					"Missing index: " + str(count))
			count = count + 1

class OOTCameraPosData:
	def __init__(self, camSType, hasPositionData, position, rotation, fov, jfifID):
		self.camSType = camSType
		self.position = position
		self.rotation = rotation
		self.fov = fov
		self.jfifID = jfifID
		self.unknown = -1
		self.hasPositionData = hasPositionData
