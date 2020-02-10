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

def exportLevelC(obj, transformMatrix, f3dType, isHWv1, levelName, exportDir,
    savePNG, writeScriptFile):
    
    levelDir = os.path.join(exportDir, levelName)
    if not os.path.exists(levelDir):
        os.mkdir(levelDir)
    areaDict = {}

    geoString = ''
    levelDataString = ''
    headerString = ''
    areaString = ''

    fModel = FModel(f3dType, isHWv1, levelName)
    childAreas = [child for child in obj.children if child.data is None and child.sm64_obj_type == 'Area Root']
    if len(childAreas) == 0:
        raise PluginError("The level root has no child empties with the 'Area Root' object type.")
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
	        f3dType, isHWv1, child.areaCamera, levelName + '_' + areaName, fModel, child)

        # Write geolayout
        geoFile = open(os.path.join(areaDir, 'geo.inc.c'), 'w')
        geoFile.write(geolayoutGraph.to_c())
        geoFile.close()
        geoString += '#include "levels/' + levelName + '/' + areaName + '/geo.inc.c"\n'
        headerString += geolayoutGraph.to_c_def()

        # Write collision
        collision = \
            exportCollisionCommon(obj, transformMatrix, True, True, 
                levelName + '_' + areaName, child.areaIndex)
        colFile = open(os.path.join(areaDir, 'collision.inc.c'), 'w')
        colFile.write(collision.to_c())
        colFile.close()
        levelDataString += '#include "levels/' + levelName + '/' + areaName + '/collision.inc.c"\n'
        headerString += collision.to_c_def()

        # Get area
        area = exportAreaCommon(obj, child, transformMatrix, 
            geolayoutGraph.startGeolayout, collision, levelName + '_' + areaName)
        areaString += area.to_c_script()

        # Write macros
        macroFile = open(os.path.join(areaDir, 'macro.inc.c'), 'w')
        macroFile.write(area.to_c_macros())
        macroFile.close()
        levelDataString += '#include "levels/' + levelName + '/' + areaName + '/macro.inc.c"\n'
        headerString += area.to_c_def_macros()

    # Remove old areas.
    for f in os.listdir(levelDir):
        if re.search('area\_\d+', f):
            existingArea = False
            for index, areaObj in areaDict.items():
                if f == 'area_' + str(index):
                    existingArea = True
            if not existingArea:
                shutil.rmtree(os.path.join(levelDir, f))
    
    if savePNG:
        fModel.save_c_tex_separate(True, 'levels/' + levelName, levelDir, True, 'texture_include.inc.c')
        fModel.freePalettes()
    else:
        fModel.freePalettes()
        modelPath = os.path.join(levelDir, 'model.inc.c')
        dlData = fModel.to_c(True)
        dlFile = open(modelPath, 'w')
        dlFile.write(dlData)
        dlFile.close()

    levelDataString += '#include "levels/' + levelName + '/model.inc.c"\n'
    headerString += fModel.to_c_def(True)
    #headerString += '\nextern const LevelScript level_' + levelName + '_entry[];\n'
    #headerString += '\n#endif\n'

    geoFile = open(os.path.join(levelDir, 'geo.inc.c'), 'w')
    geoFile.write(geoString)
    geoFile.close()

    levelDataFile = open(os.path.join(levelDir, 'leveldata.inc.c'), 'w')
    levelDataFile.write(levelDataString)
    levelDataFile.close()

    headerFile = open(os.path.join(levelDir, 'header.inc.h'), 'w')
    headerFile.write(headerString)
    headerFile.close()

    areaFile = open(os.path.join(levelDir, 'script.inc.c'), 'w')
    areaFile.write(areaString)
    areaFile.close()

    if writeScriptFile:
        writeIfNotFound(os.path.join(levelDir, 'geo.c'), 
            '#include "levels/' + levelName + '/geo.inc.c"\n', False)
        writeIfNotFound(os.path.join(levelDir, 'leveldata.c'), 
            '#include "levels/' + levelName + '/leveldata.inc.c"\n', False)
        writeIfNotFound(os.path.join(levelDir, 'header.h'), 
            '#include "levels/' + levelName + '/header.inc.h"\n', True)

        
        if savePNG:
            writeIfNotFound(os.path.join(levelDir, 'texture.inc.c'), 
                '#include "levels/' + levelName + '/texture_include.inc.c"\n', False)
        else:
            textureIncludePath = os.path.join(levelDir, 'texture_include.inc.c')
            if os.path.exists(textureIncludePath):
                os.remove(textureIncludePath)
            deleteIfFound(os.path.join(levelDir, 'texture.inc.c'), 
                '#include "levels/' + levelName + '/texture_include.inc.c"')


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
        
        scriptFile = open(os.path.join(levelDir, 'script.c'), 'w')
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
            prop_split(box, warpNode, 'destLevel', 'Destination Level')
            prop_split(box, warpNode, 'destArea', 'Destination Area')
            prop_split(box, warpNode, 'destNode', 'Destination Node')
            prop_split(box, warpNode, 'warpFlags', 'Warp Flags')
		
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
        prop_split(box, obj, 'music_preset', 'Music Preset')
        prop_split(box, obj, 'music_seq', 'Music Sequence')
        box.box().label(text = 'Sequence IDs defined in include/seq_ids.h.')
        prop_split(box, obj, 'terrain_type', 'Terrain Type')
        box.box().label(text = 'Terrain IDs defined in include/surface_terrains.h.')

        box.operator(AddWarpNode.bl_idname).option = len(obj.warpNodes)
        for i in range(len(obj.warpNodes)):
            drawWarpNodeProperty(box, obj.warpNodes[i], i)

warpTypeEnum = [
    ("Warp", "Warp", "Warp"),
    ("Painting", "Painting", "Painting"),
    ("Instant", "Instant", "Instant"),
]

class WarpNodeProperty(bpy.types.PropertyGroup):
    warpType : bpy.props.EnumProperty(name = 'Warp Type', items = warpTypeEnum, default = 'Warp')
    warpID : bpy.props.StringProperty(name = 'Warp ID', default = '0x0A')
    destLevel : bpy.props.StringProperty(name = 'Destination Level', default = 'LEVEL_BOB')
    destArea : bpy.props.StringProperty(name = 'Destination Area', default = '0x01')
    destNode : bpy.props.StringProperty(name = 'Destination Node', default = '0x0A')
    warpFlags : bpy.props.StringProperty(name = 'Warp Flags', default = 'WARP_NO_CHECKPOINT')
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

            return cmd + '(' + str(self.warpID) + ', ' + str(self.destLevel) + ', ' +\
                str(self.destArea) + ', ' + str(self.destNode) + ', ' + str(self.warpFlags) + ')'

class AddWarpNode(bpy.types.Operator):
	bl_idname = 'bone.add_warp_node'
	bl_label = 'Add Warp Node'
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
        name = "Music Sequence", default = 'SEQ_LEVEL_GRASS')
    bpy.types.Object.terrain_type = bpy.props.StringProperty(
        name = "Terrain Type", default = 'TERRAIN_GRASS')

    bpy.types.Object.areaCamera = bpy.props.PointerProperty(type = bpy.types.Camera)
    bpy.types.Object.warpNodes = bpy.props.CollectionProperty(
		type = WarpNodeProperty)

def level_unregister():
	
    del bpy.types.Object.areaIndex
    del bpy.types.Object.music_preset
    del bpy.types.Object.music_seq
    del bpy.types.Object.terrain_type
    del bpy.types.Object.areaCamera

    for cls in reversed(level_classes):
    	unregister_class(cls)
