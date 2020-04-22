from .utility import *
from .sm64_constants import *
from .sm64_objects import *
from .sm64_collision import *
from .sm64_geolayout_writer import *
from bpy.utils import register_class, unregister_class
import bpy, bmesh
import os
from io import BytesIO
import math
import re
import shutil

enumTerrain = [
	('Custom', 'Custom', 'Custom'),
	('TERRAIN_GRASS', 'Grass', 'Grass'),
	('TERRAIN_STONE', 'Stone', 'Stone'),
	('TERRAIN_SNOW', 'Snow', 'Snow'),
	('TERRAIN_SAND', 'Sand', 'Sand'),
	('TERRAIN_SPOOKY', 'Spooky', 'Spooky'),
	('TERRAIN_WATER', 'Water', 'Water'),
	('TERRAIN_SLIDE', 'Slide', 'Slide'),
]

enumMusicSeq = [
	('Custom', 'Custom', 'Custom'),
	('SEQ_LEVEL_BOSS_KOOPA', 'Boss Koopa', 'Boss Koopa'),
    ('SEQ_LEVEL_BOSS_KOOPA_FINAL', 'Boss Koopa Final', 'Boss Koopa Final'),
    ('SEQ_LEVEL_GRASS', 'Grass Level', 'Grass Level'),
    ('SEQ_LEVEL_HOT', 'Hot Level', 'Hot Level'),
    ('SEQ_LEVEL_INSIDE_CASTLE', 'Inside Castle', 'Inside Castle'),
    ('SEQ_LEVEL_KOOPA_ROAD', 'Koopa Road', 'Koopa Road'),
    ('SEQ_LEVEL_SLIDE', 'Slide Level', 'Slide Level'),
    ('SEQ_LEVEL_SNOW', 'Snow Level', 'Snow Level'),
    ('SEQ_LEVEL_SPOOKY', 'Spooky Level', 'Spooky Level'),
    ('SEQ_LEVEL_UNDERGROUND', 'Underground Level', 'Underground Level'),
    ('SEQ_LEVEL_WATER', 'Water Level', 'Water Level'),
    ('SEQ_MENU_FILE_SELECT', 'File Select', 'File Select'),
    ('SEQ_MENU_STAR_SELECT', 'Star Select Menu', 'Star Select Menu'),
    ('SEQ_MENU_TITLE_SCREEN', 'Title Screen', 'Title Screen'),
    ('SEQ_EVENT_BOSS', 'Boss', 'Boss'),
    ('SEQ_EVENT_CUTSCENE_COLLECT_KEY', 'Collect Key', 'Collect Key'),
    ('SEQ_EVENT_CUTSCENE_COLLECT_STAR', 'Collect Star', 'Collect Star'),
    ('SEQ_EVENT_CUTSCENE_CREDITS', 'Credits', 'Credits'),
    ('SEQ_EVENT_CUTSCENE_ENDING', 'Ending Cutscene', 'Ending Cutscene'),
    ('SEQ_EVENT_CUTSCENE_INTRO', 'Intro Cutscene', 'Intro Cutscene'),
    ('SEQ_EVENT_CUTSCENE_LAKITU', 'Lakitu Cutscene', 'Lakitu Cutscene'),
    ('SEQ_EVENT_CUTSCENE_STAR_SPAWN', 'Star Spawn', 'Star Spawn'),
    ('SEQ_EVENT_CUTSCENE_VICTORY', 'Victory Cutscene', 'Victory Cutscene'),
    ('SEQ_EVENT_ENDLESS_STAIRS', 'Endless Stairs', 'Endless Stairs'),
    ('SEQ_EVENT_HIGH_SCORE', 'High Score', 'High Score'),
    ('SEQ_EVENT_KOOPA_MESSAGE', 'Koopa Message', 'Koopa Message'),
    ('SEQ_EVENT_MERRY_GO_ROUND', 'Merry Go Round', 'Merry Go Round'),
    ('SEQ_EVENT_METAL_CAP', 'Metal Cap', 'Metal Cap'),
    ('SEQ_EVENT_PEACH_MESSAGE', 'Peach Message', 'Peach Message'),
    ('SEQ_EVENT_PIRANHA_PLANT', 'Piranha Lullaby', 'Piranha Lullaby'),
    ('SEQ_EVENT_POWERUP', 'Powerup', 'Powerup'),
    ('SEQ_EVENT_RACE', 'Race', 'Race'),
    ('SEQ_EVENT_SOLVE_PUZZLE', 'Solve Puzzle', 'Solve Puzzle'),
	('SEQ_SOUND_PLAYER', 'Sound Player', 'Sound Player'),
    ('SEQ_EVENT_TOAD_MESSAGE', 'Toad Message', 'Toad Message'),
]

def exportLevelC(obj, transformMatrix, f3dType, isHWv1, levelName, exportDir,
	savePNG, customExport, exportRooms, levelCameraVolumeName, DLFormat):
	
	if customExport:
		levelDir = os.path.join(exportDir, levelName)
	else:
		levelDir = os.path.join(exportDir, 'levels/' + levelName)

	if not os.path.exists(levelDir):
		os.mkdir(levelDir)
	areaDict = {}

	geoString = ''
	levelDataString = ''
	headerString = ''
	areaString = ''
	cameraVolumeString = "struct CameraTrigger " + levelCameraVolumeName + "[] = {\n"

	fModel = FModel(f3dType, isHWv1, levelName, DLFormat)
	childAreas = [child for child in obj.children if child.data is None and child.sm64_obj_type == 'Area Root']
	if len(childAreas) == 0:
		raise PluginError("The level root has no child empties with the 'Area Root' object type.")

	mario_start = None
	for child in childAreas:
		if len(child.children) == 0:
			raise PluginError("Area for " + child.name + " has no children.")
		if child.areaIndex in areaDict:
			raise PluginError(child.name + " shares the same area index as " + areaDict[child.areaIndex].name)
		#if child.areaCamera is None:
		#    raise PluginError(child.name + ' does not have an area camera set.')
		#setOrigin(obj, child)
		areaDict[child.areaIndex] = child
		
		areaIndex = child.areaIndex
		areaName = 'area_' + str(areaIndex)
		areaDir = os.path.join(levelDir, areaName)
		if not os.path.exists(areaDir):
			os.mkdir(areaDir)

		geolayoutGraph, fModel = \
			convertObjectToGeolayout(obj, transformMatrix, 
			f3dType, isHWv1, child.areaCamera, levelName + '_' + areaName, fModel, child, DLFormat)

		# Write geolayout
		geoFile = open(os.path.join(areaDir, 'geo.inc.c'), 'w', newline = '\n')
		geoFile.write(geolayoutGraph.to_c())
		geoFile.close()
		geoString += '#include "levels/' + levelName + '/' + areaName + '/geo.inc.c"\n'
		headerString += geolayoutGraph.to_c_def()

		# Write collision
		collision = \
			exportCollisionCommon(obj, transformMatrix, True, True, 
				levelName + '_' + areaName, child.areaIndex)
		colFile = open(os.path.join(areaDir, 'collision.inc.c'), 'w', newline = '\n')
		colFile.write(collision.to_c())
		colFile.close()
		levelDataString += '#include "levels/' + levelName + '/' + areaName + '/collision.inc.c"\n'
		headerString += collision.to_c_def()

		# Write rooms
		if exportRooms:
			roomFile = open(os.path.join(areaDir, 'room.inc.c'), 'w', newline = '\n')
			roomFile.write(collision.to_c_rooms())
			roomFile.close()
			levelDataString += '#include "levels/' + levelName + '/' + areaName + '/room.inc.c"\n'
			headerString += collision.to_c_rooms_def()

		# Get area
		area = exportAreaCommon(obj, child, transformMatrix, 
			geolayoutGraph.startGeolayout, collision, levelName + '_' + areaName)
		if area.mario_start is not None:
			mario_start = area.mario_start
		areaString += area.to_c_script(exportRooms)
		cameraVolumeString += area.to_c_camera_volumes()

		# Write macros
		macroFile = open(os.path.join(areaDir, 'macro.inc.c'), 'w', newline = '\n')
		macroFile.write(area.to_c_macros())
		macroFile.close()
		levelDataString += '#include "levels/' + levelName + '/' + areaName + '/macro.inc.c"\n'
		headerString += area.to_c_def_macros()

	cameraVolumeString += '\tNULL_TRIGGER\n};'

	# Remove old areas.
	for f in os.listdir(levelDir):
		if re.search('area\_\d+', f):
			existingArea = False
			for index, areaObj in areaDict.items():
				if f == 'area_' + str(index):
					existingArea = True
			if not existingArea:
				shutil.rmtree(os.path.join(levelDir, f))
	
	static_data, dynamic_data, texC, scroll_data = fModel.to_c(savePNG, savePNG, 'levels/' + levelName, levelName)
	headerStatic, headerDynamic, headerScroll = fModel.to_c_def(levelName)
	if savePNG:
		fModel.save_textures(levelDir)

		texPath = os.path.join(levelDir, 'texture_include.inc.c')
		texFile = open(texPath, 'w', newline='\n')
		texFile.write(texC)
		texFile.close()

	writeTexScrollFiles(exportDir, levelDir, headerScroll, scroll_data)

	# Write materials
	if DLFormat == "Static":
		static_data += dynamic_data
		headerStatic += headerDynamic
	else:
		geoString = writeMaterialFiles(exportDir, levelDir, 
			'#include "levels/' + levelName + '/header.h"', 
			'#include "levels/' + levelName + '/material.inc.h"',
			headerDynamic, dynamic_data, geoString, customExport)

	modelPath = os.path.join(levelDir, 'model.inc.c')
	modelFile = open(modelPath, 'w', newline='\n')
	modelFile.write(static_data)
	modelFile.close()

	fModel.freePalettes()

	levelDataString += '#include "levels/' + levelName + '/model.inc.c"\n'
	headerString += headerStatic
	#headerString += '\nextern const LevelScript level_' + levelName + '_entry[];\n'
	#headerString += '\n#endif\n'

	# Write geolayout
	geoFile = open(os.path.join(levelDir, 'geo.inc.c'), 'w', newline='\n')
	geoFile.write(geoString)
	geoFile.close()

	levelDataFile = open(os.path.join(levelDir, 'leveldata.inc.c'), 'w', newline='\n')
	levelDataFile.write(levelDataString)
	levelDataFile.close()

	headerFile = open(os.path.join(levelDir, 'header.inc.h'), 'w', newline='\n')
	headerFile.write(headerString)
	headerFile.close()

	areaFile = open(os.path.join(levelDir, 'script.inc.c'), 'w', newline='\n')
	areaFile.write(areaString)
	areaFile.close()

	if customExport:
		cameraVolumeString = '// Replace the level specific camera volume struct in src/game/camera.c with this.\n' +\
			'// Make sure to also add the struct name to the LEVEL_DEFINE in levels/level_defines.h.\n' +\
			cameraVolumeString
		cameraFile = open(os.path.join(levelDir, 'camera_trigger.inc.c'), 'w', newline='\n')
		cameraFile.write(cameraVolumeString)
		cameraFile.close()

	if not customExport:
		if DLFormat != 'Static':
			# Write material headers
			writeMaterialHeaders(exportDir,  
				'#include "levels/' + levelName + '/material.inc.c"',
				'#include "levels/' + levelName + '/material.inc.h"')

		# Export camera triggers
		cameraPath = os.path.join(exportDir, 'src/game/camera.c')
		overwriteData('struct\s*CameraTrigger\s*', levelCameraVolumeName, cameraVolumeString, cameraPath,
			'struct CameraTrigger *sCameraTriggers', False)

		levelDefinesPath = os.path.join(exportDir, 'levels/level_defines.h')
		levelDefines = readLevelDefines(levelDefinesPath, levelName)
		levelDefines['camera table'] = levelCameraVolumeName
		writeLevelDefines(levelDefinesPath, levelName, levelDefines)

		# Write level data
		writeIfNotFound(os.path.join(levelDir, 'geo.c'), 
			'#include "levels/' + levelName + '/geo.inc.c"\n', '')
		writeIfNotFound(os.path.join(levelDir, 'leveldata.c'), 
			'#include "levels/' + levelName + '/leveldata.inc.c"\n', '')
		writeIfNotFound(os.path.join(levelDir, 'header.h'), 
			'#include "levels/' + levelName + '/header.inc.h"\n', '#endif')
		
		if savePNG:
			writeIfNotFound(os.path.join(levelDir, 'texture.inc.c'), 
				'#include "levels/' + levelName + '/texture_include.inc.c"\n', '')
		else:
			textureIncludePath = os.path.join(levelDir, 'texture_include.inc.c')
			if os.path.exists(textureIncludePath):
				os.remove(textureIncludePath)
			deleteIfFound(os.path.join(levelDir, 'texture.inc.c'), 
				'#include "levels/' + levelName + '/texture_include.inc.c"')
		
		texscrollIncludeC = '#include "levels/' + levelName + '/texscroll.inc.c"'
		texscrollIncludeH = '#include "levels/' + levelName + '/texscroll.inc.h"'
		texscrollGroup = levelName
		texscrollGroupInclude = '#include "levels/' + levelName + '/header.h"'

		writeTexScrollHeadersGroup(exportDir, texscrollIncludeC, texscrollIncludeH, 
			texscrollGroup, headerScroll, texscrollGroupInclude)


		# modifies script.c
		scriptFile = open(os.path.join(levelDir, 'script.c'), 'r')
		scriptData = scriptFile.read()
		scriptFile.close()

		# removes old AREA() commands
		#prog = re.compile('\sAREA\(.*END\_AREA\(\)\,', re.MULTILINE)
		#prog.sub('', scriptData)
		#scriptData = re.sub('\sAREA\(.*END\_AREA\(\)\,', '', scriptData)
		#scriptData = re.sub('\sAREA\(', '/*AREA(', scriptData)
		#scriptData = re.sub('END\_AREA\(\)\,', 'END_AREA(),*/', scriptData)

		# comment out old AREA() commands
		i = 0
		isArea = False
		while i < len(scriptData):
			if isArea and scriptData[i] == '\n' and scriptData[i+1:i+3] != '//':
				scriptData = scriptData[:i + 1] + '//' + scriptData[i+1:]
				i += 2
			if scriptData[i:i+5] == 'AREA(' and scriptData[max(i-1, 0)] != '_' and \
				scriptData[max(i-2, 0):i] != '//':
				scriptData = scriptData[:i] + '//' + scriptData[i:]
				i += 2
				isArea = True
			if scriptData[i:i+9] == 'END_AREA(':
				isArea = False
			i += 1

		# Adds new script include 
		scriptInclude =  '#include "levels/' + levelName + '/script.inc.c"'
		if scriptInclude not in scriptData:
			areaPos = scriptData.find('FREE_LEVEL_POOL(),')
			if areaPos == -1:
				raise PluginError("Could not find FREE_LEVEL_POOL() call in level script.c.")
			scriptData = scriptData[:areaPos] + scriptInclude + "\n\n\t" + scriptData[areaPos:]
		
		# Changes skybox mio0 segment
		#if not re.match('LOAD\_MIO0\(\s*.*0x0A\,\s*\_' + bgSegment + '\_skybox\_mio0SegmentRomStart\,\s*\_' + \
		#    bgSegment + '\_skybox\_mio0SegmentRomEnd\)\s*\,', scriptData):
		bgSegment = backgroundSegments[obj.background]
		segmentString = 'LOAD_MIO0(0x0A, _' + bgSegment + '_skybox_mio0SegmentRomStart, _' +\
			bgSegment + '_skybox_mio0SegmentRomEnd),'
		scriptData = re.sub(
			'LOAD\_MIO0\(\s*.*0x0A\,\s*\_.*\_skybox\_mio0SegmentRomStart\,\s*\_.*\_skybox\_mio0SegmentRomEnd\)\s*\,', segmentString, scriptData)

		# Writes mario pos if in script.c.
		if mario_start is not None:
			marioPosString = mario_start.to_c() + ","
			scriptData = re.sub(
				'MARIO\_POS\(.*\)\,', marioPosString, scriptData)
		
		scriptFile = open(os.path.join(levelDir, 'script.c'), 'w', newline = '\n')
		scriptFile.write(scriptData)
		scriptFile.close()


def addGeoC(levelName):
	header = \
		'#include <ultra64.h>\n' \
		'#include "sm64.h"\n' \
		'#include "geo_commands.h"\n' \
		'\n' \
		'#include "game/level_geo.h"\n' \
		'#include "game/geo_misc.h"\n' \
		'#include "game/camera.h"\n' \
		'#include "game/moving_texture.h"\n' \
		'#include "game/screen_transition.h"\n' \
		'#include "game/paintings.h"\n\n'
	
	header += '#include "levels/' + levelName + '/header.h"\n'
	return header

def addLevelDataC(levelName):
	header = \
		'#include <ultra64.h>\n' \
		'#include "sm64.h"\n' \
		'#include "surface_terrains.h"\n' \
		'#include "moving_texture_macros.h"\n' \
		'#include "level_misc_macros.h"\n' \
		'#include "macro_preset_names.h"\n' \
		'#include "special_preset_names.h"\n' \
		'#include "textures.h"\n' \
		'#include "dialog_ids.h"\n' \
		'\n' \
		'#include "make_const_nonconst.h"\n'
	
	return header

def addHeaderC(levelName):
	header = \
		'#ifndef ' + levelName.upper() + '_HEADER_H\n' +\
		'#define ' + levelName.upper() + '_HEADER_H\n' +\
		'\n' \
		'#include "types.h"\n' \
		'#include "game/moving_texture.h"\n\n'
	
	return header

def drawWarpNodeProperty(layout, warpNode, index):
	box = layout.box()
	#box.box().label(text = 'Switch Option ' + str(index + 1))
	box.prop(warpNode, 'expand', text = 'Warp Node ' + \
		str(warpNode.warpID), icon = 'TRIA_DOWN' if warpNode.expand else \
		'TRIA_RIGHT')
	if warpNode.expand:
		prop_split(box, warpNode, 'warpType', 'Warp Type')
		if warpNode.warpType == 'Instant':
			prop_split(box, warpNode, 'warpID', 'Warp ID')
			prop_split(box, warpNode, 'destArea', 'Destination Area')
			prop_split(box, warpNode, 'instantOffset', 'Offset')
		else:
			prop_split(box, warpNode, 'warpID', 'Warp ID')
			prop_split(box, warpNode, 'destLevelEnum', 'Destination Level')
			if warpNode.destLevelEnum == 'custom':
				prop_split(box, warpNode, 'destLevel', 'Destination Level Value')
			prop_split(box, warpNode, 'destArea', 'Destination Area')
			prop_split(box, warpNode, 'destNode', 'Destination Node')
			prop_split(box, warpNode, 'warpFlagEnum', 'Warp Flags')
			if warpNode.warpFlagEnum == 'Custom':
				prop_split(box, warpNode, 'warpFlags', 'Warp Flags Value')
		
		buttons = box.row(align = True)
		buttons.operator(RemoveWarpNode.bl_idname,
			text = 'Remove Option').option = index
		buttons.operator(AddWarpNode.bl_idname, 
			text = 'Add Option').option = index + 1

class SM64AreaPanel(bpy.types.Panel):
	bl_label = "Area Inspector"
	bl_idname = "SM64_Area_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "object"
	bl_options = {'HIDE_HEADER'} 

	@classmethod
	def poll(cls, context):
		if context.object is not None:
			obj = context.object
			return obj.data is None and obj.sm64_obj_type == 'Area Root'
		#if context.object is not None and isinstance(context.object.data, bpy.types.Mesh):
		#    obj = context.object
		#    if obj.parent is not None:
		#        parent = obj.parent
		#        return parent.data is None and parent.sm64_obj_type == 'Level Root'
		return False

	def draw(self, context):
		obj = context.object
		box = self.layout.box()
		box.box().label(text = 'SM64 Area Inspector')
		prop_split(box, obj, 'areaIndex', 'Area Index')
		#prop_split(box, obj, 'areaCamera', 'Area Camera')
		prop_split(box, obj, 'noMusic', 'Disable Music')
		if not obj.noMusic:
			prop_split(box, obj, 'musicSeqEnum', 'Music Sequence')
			if obj.musicSeqEnum == 'Custom':
				prop_split(box, obj, 'music_seq', 'Music Sequence Value')
			prop_split(box, obj, 'music_preset', 'Music Preset')
			box.box().label(text = 'Sequence IDs defined in include/seq_ids.h.')
		prop_split(box, obj, 'terrainEnum', 'Terrain')
		if obj.terrainEnum == 'Custom':
			prop_split(box, obj, 'terrain_type', 'Terrain Type')
		box.box().label(text = 'Terrain IDs defined in include/surface_terrains.h.')

		box.operator(AddWarpNode.bl_idname).option = len(obj.warpNodes)
		for i in range(len(obj.warpNodes)):
			drawWarpNodeProperty(box, obj.warpNodes[i], i)

enumWarpType = [
	("Warp", "Warp", "Warp"),
	("Painting", "Painting", "Painting"),
	("Instant", "Instant", "Instant"),
]

enumWarpFlag = [
	("Custom", "Custom", "Custom"),
	("WARP_NO_CHECKPOINT", 'No Checkpoint', 'No Checkpoint'),
	("WARP_CHECKPOINT", 'Checkpoint', 'Checkpoint'),
]

class WarpNodeProperty(bpy.types.PropertyGroup):
	warpType : bpy.props.EnumProperty(name = 'Warp Type', items = enumWarpType, default = 'Warp')
	warpID : bpy.props.StringProperty(name = 'Warp ID', default = '0x0A')
	destLevelEnum : bpy.props.EnumProperty(name = 'Destination Level', default = 'custom', items = enumLevelNames)
	destLevel : bpy.props.StringProperty(name = 'Destination Level Value', default = 'LEVEL_BOB')
	destArea : bpy.props.StringProperty(name = 'Destination Area', default = '0x01')
	destNode : bpy.props.StringProperty(name = 'Destination Node', default = '0x0A')
	warpFlags : bpy.props.StringProperty(name = 'Warp Flags', default = 'WARP_NO_CHECKPOINT')
	warpFlagEnum : bpy.props.EnumProperty(name = 'Warp Flags Value', default = 'WARP_NO_CHECKPOINT', items = enumWarpFlag)
	instantOffset : bpy.props.IntVectorProperty(name = 'Offset',
		size = 3, default = (0,0,0))

	expand : bpy.props.BoolProperty()

	def to_c(self):
		if self.warpType == 'Instant':
			return 'INSTANT_WARP(' + str(self.warpID) + ', ' + str(self.destArea) +\
				', ' + str(self.instantOffset[0]) + ', ' + str(self.instantOffset[1]) + \
				', ' + str(self.instantOffset[2]) + ')'
		else:
			if self.warpType == 'Warp':
				cmd = 'WARP_NODE'
			elif self.warpType == 'Painting':
				cmd = 'PAINTING_WARP_NODE'

			if self.destLevelEnum == 'custom':
				destLevel = self.destLevel
			else:
				destLevel = levelIDNames[self.destLevelEnum]

			if self.warpFlagEnum == 'Custom':
				warpFlags = self.warpFlags
			else:
				warpFlags = self.warpFlagEnum
			return cmd + '(' + str(self.warpID) + ', ' + str(destLevel) + ', ' +\
				str(self.destArea) + ', ' + str(self.destNode) + ', ' + str(warpFlags) + ')'

class AddWarpNode(bpy.types.Operator):
	bl_idname = 'bone.add_warp_node'
	bl_label = 'Add Warp Node'
	bl_options = {'REGISTER', 'UNDO'} 
	option : bpy.props.IntProperty()
	def execute(self, context):
		obj = context.object
		obj.warpNodes.add()
		obj.warpNodes.move(len(obj.warpNodes)-1, self.option)
		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 

class RemoveWarpNode(bpy.types.Operator):
	bl_idname = 'bone.remove_warp_node'
	bl_label = 'Remove Warp Node'
	bl_options = {'REGISTER', 'UNDO'} 
	option : bpy.props.IntProperty()
	def execute(self, context):
		context.object.warpNodes.remove(self.option)
		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} 

level_classes = (
	SM64AreaPanel,
	WarpNodeProperty,
	AddWarpNode,
	RemoveWarpNode,
)

def level_register():
	for cls in level_classes:
		register_class(cls)
		
	bpy.types.Object.areaIndex = bpy.props.IntProperty(name = 'Index',
		min = 1, default = 1)

	bpy.types.Object.music_preset = bpy.props.StringProperty(
		name = "Music Preset", default = '0x00')
	bpy.types.Object.music_seq = bpy.props.StringProperty(
		name = "Music Sequence Value", default = 'SEQ_LEVEL_GRASS')
	bpy.types.Object.noMusic = bpy.props.BoolProperty(
		name = 'No Music', default = False)
	bpy.types.Object.terrain_type = bpy.props.StringProperty(
		name = "Terrain Type", default = 'TERRAIN_GRASS')
	bpy.types.Object.terrainEnum = bpy.props.EnumProperty(
		name = 'Terrain', items = enumTerrain, default = "Custom")
	bpy.types.Object.musicSeqEnum = bpy.props.EnumProperty(
		name = 'Music Sequence', items = enumMusicSeq, default = "Custom")

	bpy.types.Object.areaCamera = bpy.props.PointerProperty(type = bpy.types.Camera)
	bpy.types.Object.warpNodes = bpy.props.CollectionProperty(
		type = WarpNodeProperty)

def level_unregister():
	
	del bpy.types.Object.areaIndex
	del bpy.types.Object.music_preset
	del bpy.types.Object.music_seq
	del bpy.types.Object.terrain_type
	del bpy.types.Object.areaCamera
	del bpy.types.Object.noMusic

	for cls in reversed(level_classes):
		unregister_class(cls)
