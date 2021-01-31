from .oot_constants import *
from .oot_utility import *

from ..utility import *

from bpy.utils import register_class, unregister_class
from io import BytesIO
import bpy, bmesh, os, math, re, shutil, mathutils
from .oot_scene_room import *

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
    ("CAM_SET_HORSE0", "Horse0", "Horse0"),
    ("CAM_SET_BOSS_GOMA", "Boss_goma", "Boss_goma"),
    ("CAM_SET_BOSS_DODO", "Boss_dodo", "Boss_dodo"),
    ("CAM_SET_BOSS_BARI", "Boss_bari", "Boss_bari"),
    ("CAM_SET_BOSS_FGANON", "Boss_fganon", "Boss_fganon"),
    ("CAM_SET_BOSS_BAL", "Boss_bal", "Boss_bal"),
    ("CAM_SET_BOSS_SHADES", "Boss_shades", "Boss_shades"),
    ("CAM_SET_BOSS_MOFA", "Boss_mofa", "Boss_mofa"),
    ("CAM_SET_TWIN0", "Twin0", "Twin0"),
    ("CAM_SET_TWIN1", "Twin1", "Twin1"),
    ("CAM_SET_BOSS_GANON1", "Boss_ganon1", "Boss_ganon1"),
    ("CAM_SET_BOSS_GANON2", "Boss_ganon2", "Boss_ganon2"),
    ("CAM_SET_TOWER0", "Tower0", "Tower0"),
    ("CAM_SET_TOWER1", "Tower1", "Tower1"),
    ("CAM_SET_FIXED0", "Fixed0", "Fixed0"),
    ("CAM_SET_FIXED1", "Fixed1", "Fixed1"),
    ("CAM_SET_CIRCLE0", "Circle0", "Circle0"),
    ("CAM_SET_CIRCLE2", "Circle2", "Circle2"),
    ("CAM_SET_CIRCLE3", "Circle3", "Circle3"),
    ("CAM_SET_PREREND0", "Prerend0", "Prerend0"),
    ("CAM_SET_PREREND1", "Prerend1", "Prerend1"),
    ("CAM_SET_PREREND3", "Prerend3", "Prerend3"),
    ("CAM_SET_DOOR0", "Door0", "Door0"),
    ("CAM_SET_DOORC", "Doorc", "Doorc"),
    ("CAM_SET_RAIL3", "Rail3", "Rail3"),
    ("CAM_SET_START0", "Start0", "Start0"),
    ("CAM_SET_START1", "Start1", "Start1"),
    ("CAM_SET_FREE0", "Free0", "Free0"),
    ("CAM_SET_FREE2", "Free2", "Free2"),
    ("CAM_SET_CIRCLE4", "Circle4", "Circle4"),
    ("CAM_SET_CIRCLE5", "Circle5", "Circle5"),
    ("CAM_SET_DEMO0", "Demo0", "Demo0"),
    ("CAM_SET_DEMO1", "Demo1", "Demo1"),
    ("CAM_SET_MORI1", "Mori1", "Mori1"),
    ("CAM_SET_ITEM0", "Item0", "Item0"),
    ("CAM_SET_ITEM1", "Item1", "Item1"),
    ("CAM_SET_DEMO3", "Demo3", "Demo3"),
    ("CAM_SET_DEMO4", "Demo4", "Demo4"),
    ("CAM_SET_UFOBEAN", "Ufobean", "Ufobean"),
    ("CAM_SET_LIFTBEAN", "Liftbean", "Liftbean"),
    ("CAM_SET_SCENE0", "Scene0", "Scene0"),
    ("CAM_SET_SCENE1", "Scene1", "Scene1"),
    ("CAM_SET_HIDAN1", "Hidan1", "Hidan1"),
    ("CAM_SET_HIDAN2", "Hidan2", "Hidan2"),
    ("CAM_SET_MORI2", "Mori2", "Mori2"),
    ("CAM_SET_MORI3", "Mori3", "Mori3"),
    ("CAM_SET_TAKO", "Tako", "Tako"),
    ("CAM_SET_SPOT05A", "Spot05a", "Spot05a"),
    ("CAM_SET_SPOT05B", "Spot05b", "Spot05b"),
    ("CAM_SET_HIDAN3", "Hidan3", "Hidan3"),
    ("CAM_SET_ITEM2", "Item2", "Item2"),
    ("CAM_SET_CIRCLE6", "Circle6", "Circle6"),
    ("CAM_SET_NORMAL2", "Normal2", "Normal2"),
    ("CAM_SET_FISHING", "Fishing", "Fishing"),
    ("CAM_SET_DEMOC", "Democ", "Democ"),
    ("CAM_SET_UO_FIBER", "Uo_fiber", "Uo_fiber"),
    ("CAM_SET_DUNGEON2", "Dungeon2", "Dungeon2"),
    ("CAM_SET_TEPPEN", "Teppen", "Teppen"),
    ("CAM_SET_CIRCLE7", "Circle7", "Circle7"),
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

		return convertIntTo2sComplement(value, 4)

	def convertLow(self):
		value = ((1 if self.isWallDamage else 0) << 27) |\
			(self.conveyorRotation << 21) |\
			(self.conveyorSpeed << 18) |\
			((1 if self.hookshotable else 0) << 17) |\
			(int(self.echo, 16) << 11) |\
			(self.lightingSetting << 6) |\
			(int(self.terrain, 16) << 4) |\
			(int(self.sound, 16) << 0)

		return convertIntTo2sComplement(value, 4)

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
	polygonType.enableConveyor = collisionProp.enableConveyor
	polygonType.conveyorRotation = int(collisionProp.conveyorRotation / (2 * math.pi) * 0x3F)
	polygonType.conveyorSpeed = int(getCustomProperty(collisionProp, 'conveyorSpeed'), 16) + \
		(4 if collisionProp.conveyorKeepMomentum else 0)
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
		return convertIntTo2sComplement(value, 4)

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

class OOTCameraPositionProperty(bpy.types.PropertyGroup):
	index : bpy.props.IntProperty(min = 0)
	jfifID : bpy.props.StringProperty(default = "-1")
	camSType : bpy.props.EnumProperty(items = ootEnumCameraSType, default = 'CAM_SET_NONE')
	camSTypeCustom : bpy.props.StringProperty(default = "CAM_SET_NONE")
	hasPositionData : bpy.props.BoolProperty(default = True, name = "Has Position Data")

class OOTCameraPositionPropertyRef(bpy.types.PropertyGroup):
	camera : bpy.props.PointerProperty(type = bpy.types.Camera)

class OOTMaterialCollisionProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty()

	ignoreCameraCollision : bpy.props.BoolProperty()
	ignoreActorCollision : bpy.props.BoolProperty()
	ignoreProjectileCollision : bpy.props.BoolProperty()

	eponaBlock : bpy.props.BoolProperty()
	decreaseHeight : bpy.props.BoolProperty()
	floorSettingCustom : bpy.props.StringProperty(default = '0x00')
	floorSetting : bpy.props.EnumProperty(items = ootEnumFloorSetting, default = "0x00")
	wallSettingCustom : bpy.props.StringProperty(default = '0x00')
	wallSetting : bpy.props.EnumProperty(items = ootEnumWallSetting, default = "0x00")
	floorPropertyCustom : bpy.props.StringProperty(default = '0x00')
	floorProperty : bpy.props.EnumProperty(items = ootEnumFloorProperty, default = "0x00")
	exitID : bpy.props.IntProperty(default = 0, min = 0)
	cameraID : bpy.props.IntProperty(default = 0, min = 0)
	isWallDamage : bpy.props.BoolProperty()
	enableConveyor : bpy.props.BoolProperty()
	conveyorRotation : bpy.props.FloatProperty(min = 0, max = 2 * math.pi, subtype = "ANGLE")
	conveyorSpeed : bpy.props.EnumProperty(items = ootEnumConveyorSpeed, default = "0x00")
	conveyorSpeedCustom : bpy.props.StringProperty(default = "0x00")
	conveyorKeepMomentum : bpy.props.BoolProperty()
	hookshotable : bpy.props.BoolProperty()
	echo : bpy.props.StringProperty(default = "0x00")
	lightingSetting : bpy.props.IntProperty(default = 0, min = 0)
	terrainCustom : bpy.props.StringProperty(default = '0x00')
	terrain : bpy.props.EnumProperty(items = ootEnumCollisionTerrain, default = "0x00")
	soundCustom : bpy.props.StringProperty(default = '0x00')
	sound : bpy.props.EnumProperty(items = ootEnumCollisionSound, default = "0x00")

class OOTWaterBoxProperty(bpy.types.PropertyGroup):
	lighting : bpy.props.IntProperty(name = 'Lighting', min = 0)
	camera: bpy.props.IntProperty(name = "Camera", min = 0)

def drawWaterBoxProperty(layout, waterBoxProp):
	box = layout.column()
	#box.box().label(text = "Properties")
	prop_split(box, waterBoxProp, 'lighting', "Lighting")
	prop_split(box, waterBoxProp, 'camera', "Camera")
	box.label(text = "Defined by top face of box empty.")
	box.label(text = "No rotation allowed.")

def drawCameraPosProperty(layout, cameraRefProp, index, headerIndex, objName):
	camBox = layout.box()
	prop_split(camBox, cameraRefProp, "camera", "Camera " + str(index))
	drawCollectionOps(camBox, index, "Camera Position", headerIndex, objName)

class OOT_CameraPosPanel(bpy.types.Panel):
	bl_label = "Camera Position Inspector"
	bl_idname = "OBJECT_PT_OOT_Camera_Position_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "object"
	bl_options = {'HIDE_HEADER'} 

	@classmethod
	def poll(cls, context):
		return (context.scene.gameEditorMode == "OOT" and isinstance(context.object.data, bpy.types.Camera))
	
	def draw(self, context):
		box = self.layout.box()
		obj = context.object

		box.box().label(text = "Camera Data")
		drawEnumWithCustom(box, obj.ootCameraPositionProperty, "camSType", "Camera S Type", "")
		prop_split(box, obj.ootCameraPositionProperty, "index", "Camera Index")
		if obj.ootCameraPositionProperty.hasPositionData:
			prop_split(box, obj.data, "angle", "Field Of View")
			prop_split(box, obj.ootCameraPositionProperty, "jfifID", "JFIF ID")
		box.prop(obj.ootCameraPositionProperty, 'hasPositionData')

		#drawParentSceneRoom(box, context.object)
	

class OOT_CollisionPanel(bpy.types.Panel):
	bl_label = "Collision Inspector"
	bl_idname = "MATERIAL_PT_OOT_Collision_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "material"
	bl_options = {'HIDE_HEADER'} 

	@classmethod
	def poll(cls, context):
		return (context.scene.gameEditorMode == "OOT" and context.material is not None)
	
	def draw(self, context):
		box = self.layout.box().column()
		collisionProp = context.material.ootCollisionProperty

		box.prop(collisionProp, 'expandTab', text = "OOT Collision Properties", 
			icon = 'TRIA_DOWN' if collisionProp.expandTab else \
			'TRIA_RIGHT')
		if collisionProp.expandTab:
			prop_split(box, collisionProp, "exitID", "Exit ID")
			prop_split(box, collisionProp, "cameraID", "Camera ID")
			prop_split(box, collisionProp, "echo", "Echo")
			prop_split(box, collisionProp, "lightingSetting", "Lighting")
			drawEnumWithCustom(box, collisionProp, "terrain", "Terrain", "")
			drawEnumWithCustom(box, collisionProp, "sound", "Sound", "")

			box.prop(collisionProp, "eponaBlock", text = "Blocks Epona")
			box.prop(collisionProp, "decreaseHeight", text = "Decrease Height 1 Unit")
			box.prop(collisionProp, "isWallDamage", text = "Is Wall Damage")
			box.prop(collisionProp, "hookshotable", text = "Hookshotable")

			drawEnumWithCustom(box, collisionProp, "floorSetting", "Floor Setting", "")
			drawEnumWithCustom(box, collisionProp, "wallSetting", "Wall Setting", "")
			drawEnumWithCustom(box, collisionProp, "floorProperty", "Floor Property", "")

			box.prop(collisionProp, "ignoreCameraCollision", text = "Ignore Camera Collision")
			box.prop(collisionProp, "ignoreActorCollision", text = "Ignore Actor Collision")
			box.prop(collisionProp, "ignoreProjectileCollision", text = "Ignore Projectile Collision")
			box.prop(collisionProp, "enableConveyor", text = "Enable Conveyor")
			if collisionProp.enableConveyor:
				prop_split(box, collisionProp, "conveyorRotation", "Conveyor Rotation")
				drawEnumWithCustom(box, collisionProp, 'conveyorSpeed', "Conveyor Speed", "")
				if collisionProp.conveyorSpeed != "Custom":
					box.prop(collisionProp, "conveyorKeepMomentum", text = "Keep Momentum")

# water boxes handled by level writer					
def exportCollisionCommon(collision, sceneObj, allObjs, transformMatrix, includeChildren, name):
	bpy.ops.object.select_all(action = 'DESELECT')
	sceneObj.select_set(True)

	# dict of collisionType : faces
	collisionDict = {}

	addCollisionTriangles(sceneObj, collisionDict, includeChildren, transformMatrix, collision.bounds)
	for material, faces in collisionDict.items():
		polygonType = getPolygonType(material.ootCollisionProperty)
		collision.polygonGroups[polygonType] = []
		for (faceVerts, normal, distance) in faces:
			indices = []
			for roundedPosition in faceVerts:
				index = collisionVertIndex(roundedPosition, collision.vertices)
				if index is None:
					collision.vertices.append(OOTCollisionVertex(roundedPosition))
					indices.append(len(collision.vertices) - 1)
				else:
					indices.append(index)
			collision.polygonGroups[polygonType].append(OOTCollisionPolygon(indices, normal, distance))

def updateBounds(position, bounds):
	if len(bounds) == 0:
		bounds.append([position[0], position[1], position[2]])
		bounds.append([position[0], position[1], position[2]])
		return

	minBounds = bounds[0]
	maxBounds = bounds[1]
	for i in range(3):
		if position[i] < minBounds[i]:
			minBounds[i] = position[i]
		if position[i] > maxBounds[i]:
			maxBounds[i] = position[i]

def addCollisionTriangles(obj, collisionDict, includeChildren, transformMatrix, bounds):
	if isinstance(obj.data, bpy.types.Mesh) and not obj.ignore_collision:
		if len(obj.data.materials) == 0:
			raise PluginError(obj.name + " must have a material associated with it.")
		obj.data.calc_loop_triangles()
		for face in obj.data.loop_triangles:
			material = obj.data.materials[face.material_index]
			#polygonType = getPolygonType(material.ootCollisionProperty)

			planePoint = transformMatrix @ obj.data.vertices[face.vertices[0]].co
			(x1, y1, z1) = roundPosition(planePoint)
			(x2, y2, z2) = roundPosition(transformMatrix @ obj.data.vertices[face.vertices[1]].co)
			(x3, y3, z3) = roundPosition(transformMatrix @ obj.data.vertices[face.vertices[2]].co)

			updateBounds((x1, y1, z1), bounds)
			updateBounds((x2, y2, z2), bounds)
			updateBounds((x3, y3, z3), bounds)

			faceNormal = (transformMatrix.inverted().transposed() @ face.normal).normalized()
			normal = convertNormalizedVectorToShort(faceNormal)
			distance = int(round(-1 * (
				faceNormal[0] * planePoint[0] + \
				faceNormal[1] * planePoint[1] + \
				faceNormal[2] * planePoint[2])))
			distance = convertIntTo2sComplement(distance, 2)

			nx = (y2 - y1) * (z3 - z2) - (z2 - z1) * (y3 - y2)
			ny = (z2 - z1) * (x3 - x2) - (x2 - x1) * (z3 - z2)
			nz = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
			magSqr = nx * nx + ny * ny + nz * nz

			if magSqr <= 0:
				print("Ignore denormalized triangle.")
				continue

			if material not in collisionDict:
				collisionDict[material] = []
			collisionDict[material].append(((
				(x1, y1, z1),
				(x2, y2, z2),
				(x3, y3, z3)), normal, distance))
	
	if includeChildren:
		for child in obj.children:
			addCollisionTriangles(child, collisionDict, includeChildren, transformMatrix @ child.matrix_local, bounds)

def roundPosition(position):
	#return [int.from_bytes(int(round(value)).to_bytes(2, 'big', signed = True), 'big') for value in position]
	return (int(round(position[0])),
		int(round(position[1])),
		int(round(position[2])))

def collisionVertIndex(vert, vertArray):
	for i in range(len(vertArray)):
		colVert = vertArray[i]
		if colVert.position == vert:
			return i
	return None

class OOT_ExportCollision(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.oot_export_collision'
	bl_label = "Export Collision"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	def execute(self, context):
		romfileOutput = None
		tempROM = None
		try:
			obj = None
			if context.mode != 'OBJECT':
				raise PluginError("Operator can only be used in object mode.")
			if len(context.selected_objects) == 0:
				raise PluginError("Object not selected.")
			obj = context.active_object
			#if type(obj.data) is not bpy.types.Mesh:
			#	raise PluginError("Mesh not selected.")
		
			#T, R, S = obj.matrix_world.decompose()
			#objTransform = R.to_matrix().to_4x4() @ \
			#	mathutils.Matrix.Diagonal(S).to_4x4()
			#finalTransform = (blenderToSM64Rotation * \
			#	(bpy.context.scene.blenderToSM64Scale)).to_4x4()
			#finalTransform = mathutils.Matrix.Identity(4)

			scaleValue = bpy.context.scene.blenderToSM64Scale
			finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((
				scaleValue, scaleValue, scaleValue))).to_4x4()
		except Exception as e:
			raisePluginError(self, e)
			return {"CANCELLED"}
		
		try:
			applyRotation([obj], math.radians(90), 'X')
			if context.scene.colExportType == 'C':
				exportPath, levelName = getPathAndLevel(context.scene.colCustomExport, 
					context.scene.colExportPath, context.scene.colLevelName, 
					context.scene.colLevelOption)
				if not context.scene.colCustomExport:
					applyBasicTweaks(exportPath)
				exportCollisionC(obj, finalTransform,
					exportPath, False,
					context.scene.colIncludeChildren, 
					bpy.context.scene.colName, context.scene.colCustomExport, context.scene.colExportRooms,
					context.scene.colExportHeaderType, context.scene.colGroupName, levelName)
				self.report({'INFO'}, 'Success!')
			elif context.scene.colExportType == 'Insertable Binary':
				exportCollisionInsertableBinary(obj, finalTransform, 
					bpy.path.abspath(context.scene.colInsertableBinaryPath), 
					False, context.scene.colIncludeChildren)
				self.report({'INFO'}, 'Success! Collision at ' + \
					context.scene.colInsertableBinaryPath)
			else:
				tempROM = tempName(context.scene.outputRom)
				checkExpanded(bpy.path.abspath(context.scene.exportRom))
				romfileExport = \
					open(bpy.path.abspath(context.scene.exportRom), 'rb')	
				shutil.copy(bpy.path.abspath(context.scene.exportRom), 
					bpy.path.abspath(tempROM))
				romfileExport.close()
				romfileOutput = open(bpy.path.abspath(tempROM), 'rb+')

				levelParsed = parseLevelAtPointer(romfileOutput, 
					level_pointers[context.scene.colExportLevel])
				segmentData = levelParsed.segmentData

				if context.scene.extendBank4:
					ExtendBank0x04(romfileOutput, segmentData, 
						defaultExtendSegment4)

				addrRange = \
					exportCollisionBinary(obj, finalTransform, romfileOutput, 
						int(context.scene.colStartAddr, 16), 
						int(context.scene.colEndAddr, 16),
						False, context.scene.colIncludeChildren)

				segAddress = encodeSegmentedAddr(addrRange[0], segmentData)
				if context.scene.set_addr_0x2A:
					romfileOutput.seek(int(context.scene.addr_0x2A, 16) + 4)
					romfileOutput.write(segAddress)
				segPointer = bytesToHex(segAddress)

				romfileOutput.close()

				if os.path.exists(bpy.path.abspath(context.scene.outputRom)):
					os.remove(bpy.path.abspath(context.scene.outputRom))
				os.rename(bpy.path.abspath(tempROM), 
					bpy.path.abspath(context.scene.outputRom))

				self.report({'INFO'}, 'Success! Collision at (' + \
					hex(addrRange[0]) + ', ' + hex(addrRange[1]) + \
					') (Seg. ' + segPointer + ').')

			applyRotation([obj], math.radians(-90), 'X')
			return {'FINISHED'} # must return a set

		except Exception as e:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')

			applyRotation([obj], math.radians(-90), 'X')

			if context.scene.colExportType == 'Binary':
				if romfileOutput is not None:
					romfileOutput.close()
				if tempROM is not None and os.path.exists(bpy.path.abspath(tempROM)):
					os.remove(bpy.path.abspath(tempROM))
			obj.select_set(True)
			context.view_layer.objects.active = obj
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

class OOT_ExportCollisionPanel(bpy.types.Panel):
	bl_idname = "OOT_PT_export_collision"
	bl_label = "OOT Collision Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'OOT'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		propsColE = col.operator(OOT_ExportCollision.bl_idname)

		col.prop(context.scene, 'colIncludeChildren')
		col.prop(context.scene, 'colCustomExport')
		if context.scene.colCustomExport:
			col.prop(context.scene, 'colExportPath')
			prop_split(col, context.scene, 'colName', 'Name')
			customExportWarning(col)
		else:
			prop_split(col, context.scene, 'colExportLevel', 'Level')
			if context.scene.colExportLevel == 'Custom':
				prop_split(col, context.scene, 'colLevelName', 'Level Name')


oot_col_classes = (
	OOT_ExportCollision,
	OOTWaterBoxProperty,
	OOTCameraPositionPropertyRef,
	OOTCameraPositionProperty,
	OOTMaterialCollisionProperty,
)

oot_col_panel_classes = (
	OOT_CollisionPanel,
	OOT_CameraPosPanel,
	#OOT_ExportCollisionPanel,
)

def oot_col_panel_register():
	for cls in oot_col_panel_classes:
		register_class(cls)

def oot_col_panel_unregister():
	for cls in oot_col_panel_classes:
		unregister_class(cls)

def oot_col_register():
	for cls in oot_col_classes:
		register_class(cls)

	# Collision
	bpy.types.Scene.ootColExportPath = bpy.props.StringProperty(
		name = 'Directory', subtype = 'FILE_PATH')
	bpy.types.Scene.ootColExportLevel = bpy.props.EnumProperty(items = ootEnumSceneID, 
		name = 'Level Used By Collision', default = 'SCENE_YDAN')
	bpy.types.Scene.ootColIncludeChildren = bpy.props.BoolProperty(
		name = 'Include child objects', default = True)
	bpy.types.Scene.ootColName = bpy.props.StringProperty(
		name = 'Name', default = 'link')
	bpy.types.Scene.ootColLevelName = bpy.props.StringProperty(
		name = 'Name', default = 'SCENE_YDAN')
	bpy.types.Scene.ootColCustomExport = bpy.props.BoolProperty(
		name = 'Custom Export Path')
	
	bpy.types.Object.ootCameraPositionProperty = bpy.props.PointerProperty(type = OOTCameraPositionProperty)
	bpy.types.Material.ootCollisionProperty = bpy.props.PointerProperty(type = OOTMaterialCollisionProperty)

def oot_col_unregister():
	# Collision
	del bpy.types.Scene.ootColExportPath
	del bpy.types.Scene.ootColExportLevel
	del bpy.types.Scene.ootColName
	del bpy.types.Scene.ootColLevelName
	del bpy.types.Scene.ootColIncludeChildren
	del bpy.types.Scene.ootColCustomExport

	for cls in reversed(oot_col_classes):
		unregister_class(cls)
