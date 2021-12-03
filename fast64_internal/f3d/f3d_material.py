import bpy, math, mathutils, sys, copy, os
from bpy.app.handlers import persistent
from bpy.types import Node, NodeSocket, NodeSocketInterface, ShaderNode, ShaderNodeGroup, Panel
from bpy.types import Operator, Menu
from bl_operators.presets import AddPresetBase
from bpy.utils import register_class, unregister_class
from nodeitems_utils import NodeCategory, NodeItem
from .f3d_gbi import F3D, enumTexScroll
from .f3d_enums import *
from .f3d_material_nodes import *
from .f3d_material_settings import *
from .f3d_material_presets import *
from ..utility import *

# Properties based on nodes:
# prim color
# chroma key center
# env color

bitSizeDict = {
	'G_IM_SIZ_4b' : 4,
	'G_IM_SIZ_8b' : 8,
	'G_IM_SIZ_16b' : 16,
	'G_IM_SIZ_32b' : 32,
}

texBitSizeOf = {
	'I4' : 'G_IM_SIZ_4b',
	'IA4' : 'G_IM_SIZ_4b',
	'CI4' : 'G_IM_SIZ_4b',
	'I8' : 'G_IM_SIZ_8b',
	'IA8' : 'G_IM_SIZ_8b',
	'CI8' : 'G_IM_SIZ_8b',
	'RGBA16' : 'G_IM_SIZ_16b',
	'IA16' : 'G_IM_SIZ_16b',
	'YUV16' : 'G_IM_SIZ_16b',
	'RGBA32' : 'G_IM_SIZ_32b',
}

texFormatOf = {
	'I4' : 'G_IM_FMT_I',
	'IA4' : 'G_IM_FMT_IA',
	'CI4' : 'G_IM_FMT_CI',
	'I8' : 'G_IM_FMT_I',
	'IA8' : 'G_IM_FMT_IA',
	'CI8' : 'G_IM_FMT_CI',
	'RGBA16' : 'G_IM_FMT_RGBA',
	'IA16' : 'G_IM_FMT_IA',
	'YUV16' : 'G_IM_FMT_YUV',
	'RGBA32' : 'G_IM_FMT_RGBA',
}

sm64EnumDrawLayers = [
	('0', 'Background (0x00)', 'Background'),
	('1', 'Opaque (0x01)', 'Opaque'),
	('2', 'Opaque Decal (0x02)', 'Opaque Decal'),
	('3', 'Opaque Intersecting (0x03)', 'Opaque Intersecting'),
	('4', 'Cutout (0x04)', 'Cutout'),
	('5', 'Transparent (0x05)', 'Transparent'),
	('6', 'Transparent Decal (0x06)', 'Transparent Decal'),
	('7', 'Transparent Intersecting (0x07)', 'Transparent Intersecting'),
]

ootEnumDrawLayers = [
	('Opaque', 'Opaque', 'Opaque'),
	('Transparent', 'Transparent', 'Transparent'),
	('Overlay', 'Overlay', 'Overlay'),
]


drawLayerSM64toOOT = {
	'0' : "Opaque",
	'1' : "Opaque",
	'2' : "Opaque",
	'3' : "Opaque",
	'4' : "Opaque",
	'5' : "Transparent",
	'6' : "Transparent",
	'7' : "Transparent",
}

drawLayerOOTtoSM64 = {
	"Opaque" : '1',
	"Transparent" : '5',
	"Overlay" : '1',
}

#drawLayerOOTAlpha = {
#	"Opaque" : "OPAQUE",
#	"Transparent" : "BLEND",
#	"Overlay" : 'CLIP',
#}

drawLayerSM64Alpha = {
	'0' : "CLIP",
	'1' : "CLIP",
	'2' : "CLIP",
	'3' : "CLIP",
	'4' : "CLIP",
	'5' : "BLEND",
	'6' : "BLEND",
	'7' : "BLEND",
}

enumF3DMenu = [
	("Combiner", "Combiner", "Combiner"),
	("Sources", "Sources", "Sources"),
	("Geo", "Geo", "Geo"),
	("Upper", "Upper", "Upper"),
	("Lower", "Lower", "Lower"),
]

enumF3DSource = [
	("None", "None", "None"),
	('Texture', 'Texture', 'Texture'),
	('Tile Size', 'Tile Size', 'Tile Size'),
	('Primitive', 'Primitive', 'Primitive'),
	('Environment', 'Environment', 'Environment'),
	('Shade', 'Shade', 'Shade'),
	('Key', 'Key', 'Key'),
	('LOD Fraction', 'LOD Fraction', 'LOD Fraction'),
	('Convert', 'Convert', 'Convert'),
]

defaultMaterialPresets = {
	"Shaded Solid" : {
		"SM64" : "Shaded Solid",
		"OOT" : "oot_shaded_solid"
	},
	"Shaded Texture" : {
		"SM64" : "Shaded Texture",
		"OOT" : "oot_shaded_texture"
	}
}

def getDefaultMaterialPreset(category):
	game = bpy.context.scene.gameEditorMode
	if game in defaultMaterialPresets[category]:
		return defaultMaterialPresets[category][game]
	else:
		return "Shaded Solid"

def update_draw_layer(self, context):
	if hasattr(context, 'material_slot') and context.material_slot is not None:
		material = context.material_slot.material # Handles case of texture property groups
		if not material.is_f3d or material.f3d_update_flag:
			return

		material.f3d_update_flag = True
		if material.mat_ver > 3:
			drawLayer = material.f3d_mat.draw_layer
			if context.scene.gameEditorMode == "SM64":
				drawLayer.oot = drawLayerSM64toOOT[drawLayer.sm64]
			elif context.scene.gameEditorMode == "OOT":
				if material.f3d_mat.draw_layer.oot == "Opaque":
					if int(material.f3d_mat.draw_layer.sm64) > 4:
						material.f3d_mat.draw_layer.sm64 = '1'
				elif material.f3d_mat.draw_layer.oot == "Transparent":
					if int(material.f3d_mat.draw_layer.sm64) < 5:
						material.f3d_mat.draw_layer.sm64 = '5'
			material.f3d_mat.presetName = "Custom"
			update_blend_method(material, context)
		material.f3d_update_flag = False

def update_blend_method(material, context):
	if material.mat_ver > 3:
		drawLayer = material.f3d_mat.draw_layer
		if context.scene.gameEditorMode == "OOT":
			if drawLayer.oot == "Opaque" or drawLayer.oot == "Overlay":
				f3dMat = material.f3d_mat
				if not f3dMat.rdp_settings.rendermode_advanced_enabled and\
					"TEX_EDGE" not in f3dMat.rdp_settings.rendermode_preset_cycle_1 and\
					("TEX_EDGE" not in f3dMat.rdp_settings.rendermode_preset_cycle_2 or\
					f3dMat.rdp_settings.g_mdsft_cycletype != 'G_CYC_2CYCLE'):
					material.blend_method = "OPAQUE"
				else:
					material.blend_method = "CLIP"
			else:
				material.blend_method = "BLEND"
		elif context.scene.gameEditorMode == "SM64":
			material.blend_method = drawLayerSM64Alpha[drawLayer.sm64]

class DrawLayerProperty(bpy.types.PropertyGroup):
	sm64 : bpy.props.EnumProperty(items = sm64EnumDrawLayers, default = "1", update = update_draw_layer)
	oot : bpy.props.EnumProperty(items = ootEnumDrawLayers, default = "Opaque", update = update_draw_layer)

def getTmemWordUsage(texFormat, width, height):
	texelsPerLine = 64 / bitSizeDict[texBitSizeOf[texFormat]]
	return math.ceil(width / texelsPerLine) * height

def getTmemMax(texFormat):
	return 4096 if texFormat[:2] != 'CI' else 2048

def F3DOrganizeLights(self, context):
	# Flag to prevent infinite recursion on update callback
	if not hasattr(context, "material") or context.material.f3d_update_flag:
		return
	context.material.f3d_update_flag = True
	lightList = []
	if self.f3d_light1 is not None: lightList.append(self.f3d_light1)
	if self.f3d_light2 is not None: lightList.append(self.f3d_light2)
	if self.f3d_light3 is not None: lightList.append(self.f3d_light3)
	if self.f3d_light4 is not None: lightList.append(self.f3d_light4)
	if self.f3d_light5 is not None: lightList.append(self.f3d_light5)
	if self.f3d_light5 is not None: lightList.append(self.f3d_light6)
	if self.f3d_light6 is not None: lightList.append(self.f3d_light7)

	self.f3d_light1 = lightList[0] if len(lightList) > 0 else None
	self.f3d_light2 = lightList[1] if len(lightList) > 1 else None
	self.f3d_light3 = lightList[2] if len(lightList) > 2 else None
	self.f3d_light4 = lightList[3] if len(lightList) > 3 else None
	self.f3d_light5 = lightList[4] if len(lightList) > 4 else None
	self.f3d_light6 = lightList[5] if len(lightList) > 5 else None
	self.f3d_light7 = lightList[6] if len(lightList) > 6 else None
	context.material.f3d_update_flag = False

def combiner_uses(material, checkList, is2Cycle):
	display = False
	for value in checkList:
		if value[:5] == "TEXEL":
			value1 = value
			value2 = value.replace("0", "1") if "0" in value else value.replace("1", "0")
		else:
			value1 = value
			value2 = value

		display |= material.combiner1.A == value1
		if is2Cycle:
			display |= material.combiner2.A == value2

		display |= material.combiner1.B == value1
		if is2Cycle:
			display |= material.combiner2.B  == value2

		display |= material.combiner1.C == value1
		if is2Cycle:
			display |= material.combiner2.C  == value2

		display |= material.combiner1.D == value1
		if is2Cycle:
			display |= material.combiner2.D  == value2


		display |= material.combiner1.A_alpha == value1
		if is2Cycle:
			display |= material.combiner2.A_alpha == value2

		display |= material.combiner1.B_alpha == value1
		if is2Cycle:
			display |= material.combiner2.B_alpha  == value2

		display |= material.combiner1.C_alpha == value1
		if is2Cycle:
			display |= material.combiner2.C_alpha == value2

		display |= material.combiner1.D_alpha == value1
		if is2Cycle:
			display |= material.combiner2.D_alpha  == value2

	return display

def combiner_uses_alpha(material, checkList, is2Cycle):
	display = False
	for value in checkList:
		if value[:5] == "TEXEL":
			value1 = value
			value2 = value.replace("0", "1") if "0" in value else value.replace("1", "0")
		else:
			value1 = value
			value2 = value

		display |= material.combiner1.A_alpha == value1
		if is2Cycle:
			display |= material.combiner2.A_alpha == value2

		display |= material.combiner1.B_alpha == value1
		if is2Cycle:
			display |= material.combiner2.B_alpha  == value2

		display |= material.combiner1.C_alpha == value1
		if is2Cycle:
			display |= material.combiner2.C_alpha == value2

		display |= material.combiner1.D_alpha == value1
		if is2Cycle:
			display |= material.combiner2.D_alpha  == value2

	return display

def all_combiner_uses(material):
	useDict = {
		'Texture' : combiner_uses(material,
			['TEXEL0', 'TEXEL0_ALPHA', 'TEXEL1', 'TEXEL1_ALPHA'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),

		'Texture 0' : combiner_uses(material,
			['TEXEL0', 'TEXEL0_ALPHA'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),

		'Texture 1' : combiner_uses(material,
			['TEXEL1', 'TEXEL1_ALPHA'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),

		'Primitive' : combiner_uses(material,
			['PRIMITIVE', 'PRIMITIVE_ALPHA', 'PRIM_LOD_FRAC'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),

		'Environment' : combiner_uses(material,
			['ENVIRONMENT', 'ENV_ALPHA'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),

		'Shade' : combiner_uses(material,
			['SHADE', 'SHADE_ALPHA'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),

		'Shade Alpha' : combiner_uses_alpha(material,
			['SHADE'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),

		'Key' : combiner_uses(material, ['CENTER', 'SCALE'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),

		'LOD Fraction' : combiner_uses(material, ['LOD_FRACTION'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),

		'Convert' : combiner_uses(material, ['K4', 'K5'],
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE'),
	}
	return useDict

def ui_geo_mode(settings, dataHolder, layout, useDropdown):
	inputGroup = layout.column()
	if useDropdown:
		inputGroup.prop(dataHolder, 'menu_geo',
			text = 'Geometry Mode Settings',
			icon = 'TRIA_DOWN' if dataHolder.menu_geo else 'TRIA_RIGHT')
	if not useDropdown or dataHolder.menu_geo:
		inputGroup.prop(settings, 'g_zbuffer', text = 'Z Buffer')
		inputGroup.prop(settings, 'g_shade', text = 'Shading')
		inputGroup.prop(settings, 'g_cull_front', text = 'Cull Front')
		inputGroup.prop(settings, 'g_cull_back', text = 'Cull Back')
		inputGroup.prop(settings, 'g_fog', text = 'Fog')
		#if isinstance(dataHolder, bpy.types.Material) and \
		#	settings.g_fog:
		#	material = dataHolder
		#	fogInfoBox = inputGroup.box()
		#	fogInfoBox.label(text = 'To enable fog, make sure to do these things:')
		#	fogInfoBox.label(text = '(Ignore this if you used the preset)')
		#	fogInfoBox.label(text = 'In Other Mode Upper Settings, set Cycle Type to "2 Cycle".')
		#	fogInfoBox.label(text = 'Use a combiner that has "Shade Color".')
		#	fogInfoBox.label(text = 'In Render Settings, check "Set Render Mode".')
		#	fogInfoBox.label(text = 'Set the first field to "Fog Shade".')
		#	fogInfoBox.label(text = 'Set the second to the material\'s draw layer, usually "Opaque".')

		inputGroup.prop(settings, 'g_lighting', text = 'Lighting')
		inputGroup.prop(settings, 'g_tex_gen', text = 'Texture UV Generate')
		inputGroup.prop(settings, 'g_tex_gen_linear',
			text = 'Texture UV Generate Linear')
		inputGroup.prop(settings, 'g_shade_smooth', text = 'Smooth Shading')
		if bpy.context.scene.f3d_type == 'F3DEX_GBI_2' or \
			bpy.context.scene.f3d_type == 'F3DEX_GBI':
			inputGroup.prop(settings, 'g_clipping', text = 'Clipping')

def ui_upper_mode(settings, dataHolder, layout, useDropdown):
	inputGroup = layout.column()
	if useDropdown:
		inputGroup.prop(dataHolder, 'menu_upper',
			text = 'Other Mode Upper Settings',
			icon = 'TRIA_DOWN' if dataHolder.menu_upper else 'TRIA_RIGHT')
	if not useDropdown or dataHolder.menu_upper:
		if not bpy.context.scene.isHWv1:
			prop_split(inputGroup, settings, 'g_mdsft_alpha_dither',
				'Alpha Dither')
			prop_split(inputGroup, settings, 'g_mdsft_rgb_dither',
				'RGB Dither')
		else:
			prop_split(inputGroup, settings, 'g_mdsft_color_dither',
				'Color Dither')
		prop_split(inputGroup, settings, 'g_mdsft_combkey', 'Chroma Key')
		prop_split(inputGroup, settings, 'g_mdsft_textconv', 'Texture Convert')
		prop_split(inputGroup, settings, 'g_mdsft_text_filt', 'Texture Filter')
		#prop_split(inputGroup, settings, 'g_mdsft_textlut', 'Texture LUT')
		prop_split(inputGroup, settings, 'g_mdsft_textlod', 'Texture LOD')
		prop_split(inputGroup, settings, 'g_mdsft_textdetail', 'Texture Detail')
		prop_split(inputGroup, settings, 'g_mdsft_textpersp', 'Texture Perspective Correction')
		prop_split(inputGroup, settings, 'g_mdsft_cycletype', 'Cycle Type')

		prop_split(inputGroup, settings, 'g_mdsft_pipeline', 'Pipeline Span Buffer Coherency')

def ui_lower_mode(settings, dataHolder, layout: bpy.types.UILayout, useDropdown):
	inputGroup: bpy.types.UILayout = layout.column()
	if useDropdown:
		inputGroup.prop(dataHolder, 'menu_lower',
			text = 'Other Mode Lower Settings',
			icon = 'TRIA_DOWN' if dataHolder.menu_lower else 'TRIA_RIGHT')
	if not useDropdown or dataHolder.menu_lower:
		prop_split(inputGroup, settings, 'g_mdsft_alpha_compare', 'Alpha Compare')
		prop_split(inputGroup, settings, 'g_mdsft_zsrcsel', 'Z Source Selection')
	if settings.g_mdsft_zsrcsel == 'G_ZS_PRIM':
		prim_box = inputGroup.box()
		prop_split(prim_box, settings.prim_depth, 'z', 'Prim Depth: Z')
		prop_split(prim_box, settings.prim_depth, 'dz', 'Prim Depth: Delta Z')
		if settings.prim_depth.dz != 0 and settings.prim_depth.dz & (settings.prim_depth.dz - 1):
			prim_box.label(text='Warning: DZ should ideally be a power of 2 up to 0x4000', icon='TEXTURE_DATA')

def ui_other(settings, dataHolder, layout, useDropdown):
	inputGroup = layout.column()
	if useDropdown:
		inputGroup.prop(dataHolder, 'menu_other',
			text = 'Other Settings',
			icon = 'TRIA_DOWN' if dataHolder.menu_other else 'TRIA_RIGHT')
	if not useDropdown or dataHolder.menu_other:
		clipRatioGroup = inputGroup.column()
		prop_split(clipRatioGroup, settings, 'clip_ratio', "Clip Ratio")

		if isinstance(dataHolder, bpy.types.Material) or isinstance(dataHolder, F3DMaterialProperty):
			blend_color_group = layout.row()
			prop_input_name = blend_color_group.column()
			prop_input = blend_color_group.column()
			prop_input_name.prop(dataHolder, 'set_blend', text = "Blend Color")
			prop_input.prop(dataHolder, 'blend_color', text='')
			prop_input.enabled = dataHolder.set_blend


def tmemUsageUI(layout, textureProp):
	tex = textureProp.tex
	if tex is not None and tex.size[0] > 0 and tex.size[1] > 0:
		tmemUsage = getTmemWordUsage(textureProp.tex_format, tex.size[0], tex.size[1]) * 8
		tmemMax = getTmemMax(textureProp.tex_format)
		layout.label(text = 'TMEM Usage: ' + str(tmemUsage) + ' / ' + str(tmemMax) + ' bytes')
		if tmemUsage > tmemMax:
			tmemSizeWarning = layout.box()
			tmemSizeWarning.label(text = 'WARNING: Texture size is too large.')
			tmemSizeWarning.label(text = 'Note that width will be internally padded to 64 bit boundaries.')

# UI Assumptions:
# shading = 1
# lighting = 1
# cycle type = 1 cycle
class F3DPanel(bpy.types.Panel):
	bl_label = "F3D Material"
	bl_idname = "MATERIAL_PT_F3D_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "material"
	bl_options = {'HIDE_HEADER'}

	#def hasNecessaryNodes(self, nodes):
	#	result = True
	#	for name, nodeType in caseTemplateDict.items():
	#		result &= (name in nodes)
	#	return result

	def ui_image(self, material, layout, textureProp, name, showCheckBox):
		nodes = material.node_tree.nodes
		inputGroup = layout.box().column()

		inputGroup.prop(textureProp, 'menu', text = name + ' Properties',
			icon = 'TRIA_DOWN' if textureProp.menu else 'TRIA_RIGHT')
		if textureProp.menu:
			tex = textureProp.tex
			prop_input_name = inputGroup.column()
			prop_input = inputGroup.column()

			if showCheckBox:
				prop_input_name.prop(textureProp, 'tex_set', text = "Set Texture")
			else:
				prop_input_name.label(text = name)
			#prop_input.template_image(textureProp, 'tex',
			#	nodes[name].image_user)
			texIndex = name[-1]

			prop_input.prop(textureProp, "use_tex_reference")
			if textureProp.use_tex_reference:
				prop_split(prop_input, textureProp, "tex_reference", "Texture Reference")
				prop_split(prop_input, textureProp, "tex_reference_size", "Texture Size")
				if textureProp.tex_format[:2] == 'CI':
					prop_split(prop_input, textureProp, "pal_reference", "Palette Reference")
					prop_split(prop_input, textureProp, "pal_reference_size", "Palette Size")

			else:
				prop_input.template_ID(textureProp, 'tex', new='image.new', open='image.open',
					unlink='image.tex' + texIndex + "_unlink")
				prop_input.enabled = textureProp.tex_set

				if tex is not None:
					prop_input.label(text = "Size: " + str(tex.size[0]) + " x " + str(tex.size[1]))

			if material.mat_ver > 3 and material.f3d_mat.use_large_textures:
				prop_input.label(text = "Large texture mode enabled.")
				prop_input.label(text = "Each triangle must fit in a single tile load.")
				prop_input.label(text = "UVs must be in the [0, 1024] pixel range.")
				prop_input.prop(textureProp, "save_large_texture")
				if not textureProp.save_large_texture:
					prop_input.label(text = "Most large textures will take forever to convert.", icon = 'PREVIEW_RANGE')
			else:
				tmemUsageUI(prop_input, textureProp)

			prop_split(prop_input, textureProp, 'tex_format', name = 'Format')
			if textureProp.tex_format[:2] == 'CI':
				prop_split(prop_input, textureProp, 'ci_format', name = 'CI Format')

			if not (material.mat_ver > 3 and material.f3d_mat.use_large_textures):
				texFieldSettings = prop_input.column()
				clampSettings = texFieldSettings.row()
				clampSettings.prop(textureProp.S, "clamp", text = 'Clamp S')
				clampSettings.prop(textureProp.T, "clamp", text = 'Clamp T')

				mirrorSettings = texFieldSettings.row()
				mirrorSettings.prop(textureProp.S, "mirror", text = 'Mirror S')
				mirrorSettings.prop(textureProp.T, "mirror", text = 'Mirror T')

				prop_input.prop(textureProp, 'autoprop',
					text = 'Auto Set Other Properties')

				if not textureProp.autoprop:
					mask = prop_input.row()
					mask.prop(textureProp.S, "mask", text = 'Mask S')
					mask.prop(textureProp.T, "mask", text = 'Mask T')

					shift = prop_input.row()
					shift.prop(textureProp.S, "shift", text = 'Shift S')
					shift.prop(textureProp.T, "shift", text = 'Shift T')

					low = prop_input.row()
					low.prop(textureProp.S, "low", text = 'S Low')
					low.prop(textureProp.T, "low", text = 'T Low')

					high = prop_input.row()
					high.prop(textureProp.S, "high", text = 'S High')
					high.prop(textureProp.T, "high", text = 'T High')

				if tex is not None and tex.size[0] > 0 and tex.size[1] > 0 and \
					(math.log(tex.size[0], 2) % 1 > 0.000001 or \
					math.log(tex.size[1], 2) % 1 > 0.000001):
					warnBox = layout.box()
					warnBox.label(
						text = 'Warning: Texture dimensions are not power of 2.')
					warnBox.label(text = 'Wrapping only occurs on power of 2 bounds.')

	def ui_prop(self, material, layout, name, setName, setProp, showCheckBox):
		nodes = material.node_tree.nodes
		inputGroup = layout.row()
		prop_input_name = inputGroup.column()
		prop_input = inputGroup.column()
		if showCheckBox:
			prop_input_name.prop(material, setName, text = name)
		else:
			prop_input_name.label(text = name)
		prop_input.prop(nodes[name].outputs[0], 'default_value', text='')
		prop_input.enabled = setProp
		return inputGroup

	def ui_prop_non_node(self, material, layout, label, name, setName, setProp):
		inputGroup = layout.row()
		prop_input_name = inputGroup.column()
		prop_input = inputGroup.column()
		prop_input_name.prop(material, setName, text = name)
		prop_input.prop(material, name, text='')
		prop_input.enabled = setProp
		return inputGroup

	def ui_scale(self, material, layout):
		inputGroup = layout.row().split(factor = 0.5)
		#prop_input_name = inputGroup.column()
		prop_input = inputGroup.column()
		prop_input.prop(material, 'scale_autoprop', text='Texture Auto Scale')
		prop_input_group = inputGroup.row()
		prop_input_group.prop(material, 'tex_scale', text='')
		prop_input_group.enabled = not material.scale_autoprop
		return inputGroup

	def ui_prim(self, material, layout, setName, setProp, showCheckBox):
		if material.mat_ver > 3:
			f3dMat = material.f3d_mat
		else:
			f3dMat = material
		nodes = material.node_tree.nodes
		inputGroup = layout.row()
		prop_input_name = inputGroup.column()
		prop_input = inputGroup.column()
		if showCheckBox:
			prop_input_name.prop(f3dMat, setName, text = 'Primitive Color')
		else:
			prop_input_name.label(text = 'Primitive Color')

		if material.mat_ver == 4:
			prop_input.prop(material.f3d_mat, 'prim_color', text = '')
		elif material.mat_ver == 3:
			prop_input.prop(nodes['Primitive Color Output'].inputs[0], 'default_value', text='')
		else:
			prop_input.prop(nodes['Primitive Color'].outputs[0], 'default_value', text='')

		prop_input.prop(f3dMat, 'prim_lod_frac', text='Prim LOD Fraction')
		prop_input.prop(f3dMat, 'prim_lod_min', text='Min LOD Ratio')
		prop_input.enabled = setProp
		return inputGroup

	def ui_env(self, material, layout, showCheckBox):
		nodes = material.node_tree.nodes
		inputGroup = layout.row()
		prop_input_name = inputGroup.column()
		prop_input = inputGroup.column()

		if material.mat_ver > 3:
			if showCheckBox:
				prop_input_name.prop(material.f3d_mat, 'set_env', text = 'Environment Color')
			else:
				prop_input_name.label(text = "Environment Color")
			prop_input.prop(material.f3d_mat, 'env_color', text = '')
			setProp = material.f3d_mat.set_env
		else:
			prop_input_name.prop(material, 'set_env', text = 'Environment Color')
			prop_input.prop(nodes['Environment Color Output'].inputs[0], 'default_value', text='')
			setProp = material.set_env
		prop_input.enabled = setProp
		return inputGroup

	def ui_chroma(self, material, layout, name, setName, setProp, showCheckBox):
		nodes = material.node_tree.nodes
		inputGroup = layout.row()
		prop_input_name = inputGroup.column()
		prop_input = inputGroup.column()
		if showCheckBox:
			prop_input_name.prop(material, setName, text = 'Chroma Key')
		else:
			prop_input_name.label(text = "Chroma Key")
		if material.mat_ver == 4:
			prop_input.prop(material.f3d_mat, 'key_center', text = 'Center')
		else:
			prop_input.prop(nodes['Chroma Key Center'].outputs[0],
				'default_value', text='Center')
		prop_input.prop(material, 'key_scale', text = 'Scale')
		prop_input.prop(material, 'key_width', text = 'Width')
		if material.key_width[0] > 1 or material.key_width[1] > 1 or \
			material.key_width[2] > 1:
			layout.box().label(text = \
				"NOTE: Keying is disabled for channels with width > 1.")
		prop_input.enabled = setProp
		return inputGroup

	def ui_lights(self, material, layout, name, showCheckBox):
		inputGroup = layout.row()
		prop_input_name = inputGroup.column()
		prop_input = inputGroup.column()
		if showCheckBox:
			prop_input_name.prop(material, 'set_lights', text = name)
		else:
			prop_input_name.label(text = name)
		prop_input_name.enabled = material.rdp_settings.g_lighting and \
			material.rdp_settings.g_shade
		lightSettings = prop_input.column()
		if material.rdp_settings.g_lighting:
			if material.use_default_lighting:
				lightSettings.prop(material, 'default_light_color', text = '')
			else:
				lightSettings.prop(material, 'ambient_light_color', text = 'Ambient Color')

				lightSettings.prop_search(material, 'f3d_light1',
					bpy.data, 'lights', text = '')
				if material.f3d_light1 is not None:
					lightSettings.prop_search(material, 'f3d_light2',
						bpy.data, 'lights', text = '')
				if material.f3d_light2 is not None:
					lightSettings.prop_search(material, 'f3d_light3',
						bpy.data, 'lights', text = '')
				if material.f3d_light3 is not None:
					lightSettings.prop_search(material, 'f3d_light4',
						bpy.data, 'lights', text = '')
				if material.f3d_light4 is not None:
					lightSettings.prop_search(material, 'f3d_light5',
						bpy.data, 'lights', text = '')
				if material.f3d_light5 is not None:
					lightSettings.prop_search(material, 'f3d_light6',
						bpy.data, 'lights', text = '')
				if material.f3d_light6 is not None:
					lightSettings.prop_search(material, 'f3d_light7',
						bpy.data, 'lights', text = '')
			prop_input.prop(material, 'use_default_lighting', text = 'Use Custom Lighting', invert_checkbox = True)
			#layout.box().label(text = "Note: Lighting preview is not 100% accurate.")
			#layout.box().label(text = "For vertex colors, clear 'Lighting'.")
			prop_input.enabled = material.set_lights and \
				material.rdp_settings.g_lighting and \
				material.rdp_settings.g_shade

		return inputGroup

	def ui_convert(self, material, layout, showCheckBox):
		inputGroup = layout.row()
		prop_input_name = inputGroup.column()
		prop_input = inputGroup.column()
		if showCheckBox:
			prop_input_name.prop(material, 'set_k0_5', text = 'YUV Convert')
		else:
			prop_input_name.label(text = 'YUV Convert')

		prop_k0 = prop_input.row()
		prop_k0.prop(material, 'k0', text='K0')
		prop_k0.label(text = str(int(material.k0 * 255)))

		prop_k1 = prop_input.row()
		prop_k1.prop(material, 'k1', text='K1')
		prop_k1.label(text = str(int(material.k1 * 255)))

		prop_k2 = prop_input.row()
		prop_k2.prop(material, 'k2', text='K2')
		prop_k2.label(text = str(int(material.k2 * 255)))

		prop_k3 = prop_input.row()
		prop_k3.prop(material, 'k3', text='K3')
		prop_k3.label(text = str(int(material.k3 * 255)))

		prop_k4 = prop_input.row()
		prop_k4.prop(material, 'k4', text='K4')
		prop_k4.label(text = str(int(material.k4 * 255)))

		prop_k5 = prop_input.row()
		prop_k5.prop(material, 'k5', text='K5')
		prop_k5.label(text = str(int(material.k5 * 255)))

		prop_input.enabled = material.set_k0_5
		return inputGroup

	def ui_lower_render_mode(self, material, layout, useDropdown):
		# cycle independent
		inputGroup = layout.column()
		if useDropdown:
			inputGroup.prop(material, 'menu_lower_render',
				text = 'Render Settings',
				icon = 'TRIA_DOWN' if material.menu_lower_render else 'TRIA_RIGHT')
		if not useDropdown or material.menu_lower_render:
			inputGroup.prop(material.rdp_settings, 'set_rendermode',
				text ='Set Render Mode?')

			renderGroup = inputGroup.column()
			renderGroup.prop(material.rdp_settings, 'rendermode_advanced_enabled',
				text = 'Show Advanced Settings')
			if not material.rdp_settings.rendermode_advanced_enabled:
				prop_split(renderGroup, material.rdp_settings,
					'rendermode_preset_cycle_1', "Render Mode")
				if material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE':
					prop_split(renderGroup, material.rdp_settings,
						'rendermode_preset_cycle_2', "Render Mode Cycle 2")
			else:
				prop_split(renderGroup, material.rdp_settings, 'aa_en', 'Antialiasing')
				prop_split(renderGroup, material.rdp_settings, 'z_cmp', 'Z Testing')
				prop_split(renderGroup, material.rdp_settings, 'z_upd', 'Z Writing')
				prop_split(renderGroup, material.rdp_settings, 'im_rd', 'IM_RD (?)')
				prop_split(renderGroup, material.rdp_settings, 'clr_on_cvg',
					'Clear On Coverage')
				prop_split(renderGroup, material.rdp_settings, 'cvg_dst',
					'Coverage Destination')
				prop_split(renderGroup, material.rdp_settings, 'zmode', 'Z Mode')
				prop_split(renderGroup, material.rdp_settings, 'cvg_x_alpha',
					'Multiply Coverage And Alpha')
				prop_split(renderGroup, material.rdp_settings, 'alpha_cvg_sel',
					'Use Coverage For Alpha')
				prop_split(renderGroup, material.rdp_settings, 'force_bl', 'Force Blending')

				# cycle dependent - (P * A + M - B) / (A + B)
				combinerBox = renderGroup.box()
				combinerBox.label(text='Blender (Color = (P * A + M * B) / (A + B)')
				combinerCol = combinerBox.row()
				rowColor = combinerCol.column()
				rowAlpha = combinerCol.column()
				rowColor.prop(material.rdp_settings, 'blend_p1', text = 'P')
				rowColor.prop(material.rdp_settings, 'blend_m1', text = 'M')
				rowAlpha.prop(material.rdp_settings, 'blend_a1', text = 'A')
				rowAlpha.prop(material.rdp_settings, 'blend_b1', text = 'B')

				if material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE':
					combinerBox2 = renderGroup.box()
					combinerBox2.label(text='Blender Cycle 2')
					combinerCol2 = combinerBox2.row()
					rowColor2 = combinerCol2.column()
					rowAlpha2 = combinerCol2.column()
					rowColor2.prop(material.rdp_settings, 'blend_p2', text = 'P')
					rowColor2.prop(material.rdp_settings, 'blend_m2', text = 'M')
					rowAlpha2.prop(material.rdp_settings, 'blend_a2', text = 'A')
					rowAlpha2.prop(material.rdp_settings, 'blend_b2', text = 'B')

			renderGroup.enabled = material.rdp_settings.set_rendermode

	def ui_uvCheck(self, layout, context):
		if hasattr(context, 'object') and context.object is not None and \
			isinstance(context.object.data, bpy.types.Mesh):
			uv_layers = context.object.data.uv_layers
			if uv_layers.active is None or uv_layers.active.name != 'UVMap':
				uvErrorBox = layout.box()
				uvErrorBox.label(text = 'Warning: This mesh\'s active UV layer is not named \"UVMap\".')
				uvErrorBox.label(text = 'This will cause incorrect UVs to display.')

	def ui_draw_layer(self, material, layout, context):
		if material.mat_ver > 3:
			if context.scene.gameEditorMode == 'SM64':
				prop_split(layout, material.f3d_mat.draw_layer, "sm64", "Draw Layer")
			elif context.scene.gameEditorMode == 'OOT':
				prop_split(layout, material.f3d_mat.draw_layer, "oot", "Draw Layer")

	def ui_fog(self, f3dMat, inputCol, showCheckBox):
		if f3dMat.rdp_settings.g_fog:
			inputGroup = inputCol.column()
			if showCheckBox:
				inputGroup.prop(f3dMat, 'set_fog', text = 'Set Fog')
			if f3dMat.set_fog:
				inputGroup.prop(f3dMat, 'use_global_fog', text = 'Use Global Fog (SM64)')
				if f3dMat.use_global_fog:
					inputGroup.label(text = 'Only applies to levels (area fog settings).', icon = 'INFO')
				else:
					fogColorGroup = inputGroup.row().split(factor = 0.5)
					fogColorGroup.label(text = 'Fog Color')
					fogColorGroup.prop(f3dMat, 'fog_color', text = '')
					fogPositionGroup = inputGroup.row().split(factor = 0.5)
					fogPositionGroup.label(text = 'Fog Range')
					fogPositionGroup.prop(f3dMat, 'fog_position', text = '')


			#inputGroup = inputCol.column()
			#inputGroup.prop(f3dMat, 'set_fog', text = 'Set Fog')
			#fogInputGroup = inputGroup.column()
			#globalFogBox = fogInputGroup.box()
			#globalFogBox.prop(f3dMat, 'use_global_fog', text = 'Use Global Fog')
			#globalFogInfoBox = globalFogBox.box()
			#globalFogInfoBox.label(text = 'Only applies to levels (area fog settings).')
			#globalFogInfoBox.label(text = 'Disable this for non-level geolayout/dl exporting.')
			#fogGroup = fogInputGroup.column()
			#fogColorGroup = fogGroup.row().split(factor = 0.5)
			#fogColorGroup.label(text = 'Fog Color')
			#fogColorGroup.prop(f3dMat, 'fog_color', text = '')
			#fogPositionGroup = fogGroup.row().split(factor = 0.5)
			#fogPositionGroup.label(text = 'Fog Range')
			#fogPositionGroup.prop(f3dMat, 'fog_position', text = '')
			#fogInputGroup.enabled = f3dMat.set_fog
			#fogGroup.enabled = not f3dMat.use_global_fog
			#inputGroup.box().label(text = 'NOTE: Fog will break with draw layer overrides.')

	def drawVertexColorNotice(self, layout):
		noticeBox = layout.box().column()
		noticeBox.label(
			text = 'There must be two vertex color layers.', icon = 'LINENUMBERS_ON')
		noticeBox.label(
			text = 'They should be called "Col" and "Alpha".')

	def drawShadeAlphaNotice(self, layout):
		layout.box().column().label(text = "There must be a vertex color layer called \"Alpha\".", icon = 'IMAGE_ALPHA')

	def drawCIMultitextureNotice(self, layout):
		layout.label(text = 'CI textures will break with multitexturing.', icon = 'LIBRARY_DATA_BROKEN')

	def draw_simple(self, f3dMat, material, layout, context):
		self.ui_uvCheck(layout, context)

		inputCol = layout.column()
		useDict = all_combiner_uses(f3dMat)

		if not f3dMat.rdp_settings.g_lighting:
			self.drawVertexColorNotice(layout)
		elif useDict["Shade Alpha"]:
			self.drawShadeAlphaNotice(layout)

		useMultitexture = useDict['Texture 0'] and useDict['Texture 1'] and f3dMat.tex0.tex_set and f3dMat.tex1.tex_set

		if useMultitexture and f3dMat.tex0.tex_format[:2] == "CI" or f3dMat.tex1.tex_format[:2] == "CI":
			self.drawCIMultitextureNotice(inputCol)

		if useDict['Texture 0'] and f3dMat.tex0.tex_set:
			self.ui_image(material, inputCol, f3dMat.tex0, 'Texture 0', False)

		if useDict['Texture 1'] and f3dMat.tex1.tex_set:
			self.ui_image(material, inputCol, f3dMat.tex1, 'Texture 1', False)

		if useMultitexture:
			inputCol.prop(f3dMat, 'uv_basis', text = 'UV Basis')

		if useDict['Texture']:
			if material.mat_ver > 3:
				inputCol.prop(f3dMat, 'use_large_textures')
			self.ui_scale(f3dMat, inputCol)

		if useDict['Primitive'] and f3dMat.set_prim:
			self.ui_prim(material, inputCol, 'set_prim', f3dMat.set_prim, False)

		if useDict['Environment'] and f3dMat.set_env:
			if material.mat_ver >= 3:
				self.ui_env(material, inputCol, False)
			else:
				self.ui_prop(material, inputCol, 'Environment Color', 'set_env', material.set_env, False)

		showLightProperty = f3dMat.set_lights and \
			f3dMat.rdp_settings.g_lighting and \
			f3dMat.rdp_settings.g_shade
		if useDict['Shade'] and showLightProperty:
			self.ui_lights(f3dMat, inputCol, 'Shade Color', False)

		if useDict['Key'] and f3dMat.set_key:
			self.ui_chroma(material, inputCol, 'Chroma Key Center',
				'set_key', f3dMat.set_key, False)

		if useDict['Convert'] and f3dMat.set_k0_5:
			self.ui_convert(f3dMat, inputCol, False)

		if f3dMat.set_fog:
			self.ui_fog(f3dMat, inputCol, False)

	def draw_full(self, f3dMat, material, layout, context):

		layout.row().prop(material, "menu_tab", expand = True)
		menuTab = material.menu_tab
		useDict = all_combiner_uses(f3dMat)

		if menuTab == "Combiner":
			if material.mat_ver > 3:
				self.ui_draw_layer(material, layout, context)

			if not f3dMat.rdp_settings.g_lighting:
				self.drawVertexColorNotice(layout)
			elif useDict["Shade Alpha"]:
				self.drawShadeAlphaNotice(layout)

			combinerBox = layout.box()
			combinerBox.prop(f3dMat, 'set_combiner',
				text = 'Color Combiner (Color = (A - B) * C + D)')
			combinerCol = combinerBox.row()
			combinerCol.enabled = f3dMat.set_combiner
			rowColor = combinerCol.column()
			rowAlpha = combinerCol.column()

			rowColor.prop(f3dMat.combiner1, 'A')
			rowColor.prop(f3dMat.combiner1, 'B')
			rowColor.prop(f3dMat.combiner1, 'C')
			rowColor.prop(f3dMat.combiner1, 'D')
			rowAlpha.prop(f3dMat.combiner1, 'A_alpha')
			rowAlpha.prop(f3dMat.combiner1, 'B_alpha')
			rowAlpha.prop(f3dMat.combiner1, 'C_alpha')
			rowAlpha.prop(f3dMat.combiner1, 'D_alpha')

			if f3dMat.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE':
				combinerBox2 = layout.box()
				combinerBox2.label(text = 'Color Combiner Cycle 2')
				combinerBox2.enabled = f3dMat.set_combiner
				combinerCol2 = combinerBox2.row()
				rowColor2 = combinerCol2.column()
				rowAlpha2 = combinerCol2.column()

				rowColor2.prop(f3dMat.combiner2, 'A')
				rowColor2.prop(f3dMat.combiner2, 'B')
				rowColor2.prop(f3dMat.combiner2, 'C')
				rowColor2.prop(f3dMat.combiner2, 'D')
				rowAlpha2.prop(f3dMat.combiner2, 'A_alpha')
				rowAlpha2.prop(f3dMat.combiner2, 'B_alpha')
				rowAlpha2.prop(f3dMat.combiner2, 'C_alpha')
				rowAlpha2.prop(f3dMat.combiner2, 'D_alpha')

				layout.box().label(
					text = 'Note: In cycle 2, texture 0 and texture 1 are flipped.')

			#layout.box().label(
			#	text = 'Note: Alpha preview is not 100% accurate.')

		if menuTab == "Sources":
			self.ui_uvCheck(layout, context)

			inputCol = layout.column()

			useMultitexture = useDict['Texture 0'] and useDict['Texture 1']

			if useMultitexture and f3dMat.tex0.tex_format[:2] == "CI" or f3dMat.tex1.tex_format[:2] == "CI":
				self.drawCIMultitextureNotice(inputCol)

			if useDict['Texture 0']:
				self.ui_image(material, inputCol, f3dMat.tex0, 'Texture 0', True)

			if useDict['Texture 1']:
				self.ui_image(material, inputCol, f3dMat.tex1, 'Texture 1', True)

			if useMultitexture:
				inputCol.prop(f3dMat, 'uv_basis', text = 'UV Basis')

			if useDict['Texture']:
				if material.mat_ver > 3:
					inputCol.prop(f3dMat, 'use_large_textures')
				self.ui_scale(f3dMat, inputCol)

			if useDict['Primitive']:
				self.ui_prim(material, inputCol, 'set_prim', f3dMat.set_prim, True)

			if useDict['Environment']:
				if material.mat_ver >= 3:
					self.ui_env(material, inputCol, True)
				else:
					self.ui_prop(material, inputCol, 'Environment Color', 'set_env', material.set_env, True)

			if useDict['Shade']:
				self.ui_lights(f3dMat, inputCol, 'Shade Color', True)

			if useDict['Key']:
				self.ui_chroma(material, inputCol, 'Chroma Key Center',
					'set_key', f3dMat.set_key, True)

			if useDict['Convert']:
				self.ui_convert(f3dMat, inputCol, True)

			self.ui_fog(f3dMat, inputCol, True)

		if menuTab == "Geo":
			ui_geo_mode(f3dMat.rdp_settings, f3dMat, layout, False)
		if menuTab == "Upper":
			ui_upper_mode(f3dMat.rdp_settings, f3dMat, layout, False)
		if menuTab == "Lower":
			ui_lower_mode(f3dMat.rdp_settings, f3dMat, layout, False)
			#layout.box().label(text = \
			#	'WARNING: Render mode settings not reset after drawing.')
			self.ui_lower_render_mode(f3dMat, layout, False)
			ui_other(f3dMat.rdp_settings, f3dMat, layout, False)

	# texture convert/LUT controlled by texture settings
	# add node support for geo mode settings
	def draw(self, context):
		layout = self.layout

		layout.operator(CreateFast3DMaterial.bl_idname)
		material = context.material
		if material is None:
			return
		elif not(material.use_nodes and material.is_f3d):
			layout.label(text="This is not a Fast3D material.")
			return

		if material.mat_ver > 3:
			f3dMat = material.f3d_mat
		else:
			f3dMat = material
		#layout.box().label(text = 'Note: Do not copy paste materials.')
		layout.prop(context.scene, 'f3d_simple', text = "Show Simplified UI")
		layout = layout.box()
		titleCol = layout.column()
		titleCol.box().label(text = "F3D Material Inspector")

		if material.mat_ver > 3:
			presetCol = layout.column()
			split = presetCol.split(factor = 0.33)
			split.label(text = 'Preset')
			row = split.row(align=True)
			row.menu(MATERIAL_MT_f3d_presets.__name__, text=f3dMat.presetName)
			row.operator(AddPresetF3D.bl_idname, text="", icon='ZOOM_IN')
			row.operator(AddPresetF3D.bl_idname, text="", icon='ZOOM_OUT').remove_active = True
		else:
			prop_split(layout, material, 'f3d_preset', 'Preset Material')

		if context.scene.f3d_simple and \
			((material.mat_ver > 3 and f3dMat.presetName != "Custom") or \
			(material.mat_ver <= 3 and f3dMat.f3d_preset != "Custom")):
			self.draw_simple(f3dMat, material, layout, context)
		else:
			if material.mat_ver > 3:
				presetCol.prop(context.scene, 'f3dUserPresetsOnly')
			self.draw_full(f3dMat, material, layout, context)

#def ui_procAnimVec(self, procAnimVec, layout, name, vecType):
#	layout.prop(procAnimVec, 'menu', text = name,
#		icon = 'TRIA_DOWN' if procAnimVec.menu else 'TRIA_RIGHT')
#	if procAnimVec.menu:
#		box = layout.box()
#		self.ui_procAnimField(procAnimVec.x, box, vecType[0])
#		self.ui_procAnimField(procAnimVec.y, box, vecType[1])
#		if len(vecType) > 2:
#			self.ui_procAnimField(procAnimVec.z, box, vecType[2])

def ui_tileScroll(tex, name, layout):
	row = layout.row()
	row.label(text = name)
	row.prop(tex.tile_scroll, 's', text = 'S:')
	row.prop(tex.tile_scroll, 't', text = 'T:')
	row.prop(tex.tile_scroll, 'interval', text = 'Interval:')

def ui_procAnimVecEnum(material, procAnimVec, layout, name, vecType, useDropdown, useTex0, useTex1):
	layout = layout.box()
	box = layout.column()
	if useDropdown:
		layout.prop(procAnimVec, 'menu', text = name,
			icon = 'TRIA_DOWN' if procAnimVec.menu else 'TRIA_RIGHT')
	else:
		layout.box().label(text = name)

	if not useDropdown or procAnimVec.menu:
		box = layout.column()
		#box.box().label(text = 'Scrolling not visible in preview.')
		#box.box().label(text = 'This is decomp only.')
		combinedOption = None
		xCombined = procAnimVec.x.animType == 'Rotation'
		if xCombined:
			combinedOption = procAnimVec.x.animType
		yCombined = procAnimVec.y.animType == 'Rotation'
		if yCombined:
			combinedOption = procAnimVec.y.animType
		if not yCombined:
			ui_procAnimFieldEnum(procAnimVec.x, box, vecType[0], "UV" if xCombined else None)
		if not xCombined:
			ui_procAnimFieldEnum(procAnimVec.y, box, vecType[1], "UV" if yCombined else None)
		if len(vecType) > 2:
			ui_procAnimFieldEnum(procAnimVec.z, box, vecType[2])
		if xCombined or yCombined:
			box.row().prop(procAnimVec, 'pivot')
			box.row().prop(procAnimVec, 'angularSpeed')
			if combinedOption == "Rotation":
				pass

	if useTex0 or useTex1:
		layout.box().label(text = 'SM64 SetTileSize Texture Scroll')

		if useTex0:
			ui_tileScroll(material.tex0, 'Tex 0 Speed', layout)

		if useTex1:
			ui_tileScroll(material.tex1, 'Tex 1 Speed', layout)

def ui_procAnimFieldEnum(procAnimField, layout, name, overrideName):
	box = layout
	box.prop(procAnimField, 'animType', text = name if overrideName is None else overrideName)
	if overrideName is None:
		if procAnimField.animType == "Linear":
			split0 = box.row().split(factor = 1)
			split0.prop(procAnimField, 'speed')
		elif procAnimField.animType == "Sine":
			split1 = box.row().split(factor = 0.3333)
			split1.prop(procAnimField, 'amplitude')
			split1.prop(procAnimField, 'frequency')
			#layout.row().prop(procAnimField, 'spaceFrequency')
			#split2 = box.row().split(factor = 0.5)
			split1.prop(procAnimField, 'offset')
		elif procAnimField.animType == 'Noise':
			box.row().prop(procAnimField, 'noiseAmplitude')

def ui_procAnimField(procAnimField, layout, name):
	box = layout
	box.prop(procAnimField, 'animate', text = name)
	if procAnimField.animate:
		if name not in 'XYZ':
			split0 = box.row().split(factor = 1)
			split0.prop(procAnimField, 'speed')
		split1 = box.row().split(factor = 0.5)
		split1.prop(procAnimField, 'amplitude')
		split1.prop(procAnimField, 'frequency')
		layout.row().prop(procAnimField, 'spaceFrequency')
		split2 = box.row().split(factor = 0.5)
		split2.prop(procAnimField, 'offset')
		split2.prop(procAnimField, 'noiseAmplitude')

def ui_procAnim(material, layout, useTex0, useTex1, title, useDropdown):
	if material.mat_ver > 3:
		ui_procAnimVecEnum(material.f3d_mat, material.f3d_mat.UVanim0, layout, title, 'UV', useDropdown, useTex0, useTex1)
	else:
		ui_procAnimVecEnum(material, material.UVanim, layout, title, 'UV', useDropdown, useTex0, useTex1)
	#layout.prop(material, 'menu_procAnim',
	#	text = 'Procedural Animation',
	#	icon = 'TRIA_DOWN' if material.menu_procAnim else 'TRIA_RIGHT')
	#if material.menu_procAnim:
	#	procAnimBox = layout.box()
	#	if useTex0:
	#		ui_procAnimVec(material.UVanim_tex0, procAnimBox,
	#		"UV Texture 0", 'UV')
	#	if useTex1:
	#		ui_procAnimVec(material.UVanim_tex1, procAnimBox,
	#		"UV Texture 1", 'UV')
	#	ui_procAnimVec(material.positionAnim, procAnimBox,
	#		"Position", 'XYZ')
	#	ui_procAnimVec(material.colorAnim, procAnimBox, "Color",
	#	 	'RGB')


def update_node_values(self, context):
	if hasattr(context.scene, 'world') and \
		self == context.scene.world.rdp_defaults:
		pass
	elif hasattr(context, 'material_slot') and context.material_slot is not None:
		material = context.material_slot.material # Handles case of texture property groups
		if not material.is_f3d or material.f3d_update_flag:
			return

		material.f3d_update_flag = True
		update_node_values_of_material(material, context)
		if material.mat_ver > 3:
			material.f3d_mat.presetName = "Custom"
		else:
			material.f3d_preset = 'Custom'
		material.f3d_update_flag = False

def update_node_values_without_preset(self, context):
	if hasattr(context.scene, 'world') and \
		self == context.scene.world.rdp_defaults:
		pass
	elif hasattr(context, 'material_slot') and context.material_slot is not None:
		material = context.material_slot.material # Handles case of texture property groups
		if not material.is_f3d or material.f3d_update_flag:
			return

		material.f3d_update_flag = True
		update_node_values_of_material(material, context)
		material.f3d_update_flag = False
	elif hasattr(context, 'material') and context.material is not None:
		material = context.material
		if not material.is_f3d or material.f3d_update_flag:
			return

		material.f3d_update_flag = True
		update_node_values_of_material(material, context)
		material.f3d_update_flag = False
	else:
		#print('No material in context.')
		pass

def update_node_values_directly(material, context):
	if not material.is_f3d or material.f3d_update_flag:
		return
	material.f3d_update_flag = True
	update_node_values_of_material(material, context)
	material.f3d_preset = 'Custom'
	material.f3d_update_flag = False

def getSocketFromCombinerToNodeDictColor(nodes, f3dVer, combinerInput):
	nodeName, socketIndex = combinerToNodeDictColor[combinerInput]
	return nodes[nodeName].outputs[socketIndex] if nodeName is not None else None

def getSocketFromCombinerToNodeDictAlpha(nodes, f3dVer, combinerInput):
	nodeName, socketIndex = combinerToNodeDictAlpha[combinerInput]
	return nodes[nodeName].outputs[socketIndex] if nodeName is not None else None

def update_node_combiner(material, combinerInputs, f3dVer, cycleIndex):
	nodes = material.node_tree.nodes
	combinerNode = nodes['Color Combiner Cycle ' + str(cycleIndex) + ' F3D v3']
	for i in range(8):
		for link in combinerNode.inputs[i].links:
			material.node_tree.links.remove(link)
		if i in range(0,4):
			if combinerInputs[i] == 'COMBINED' or combinerInputs[i] == 'COMBINED_ALPHA':
				if cycleIndex == 2:
					combiner1 = nodes['Color Combiner Cycle 1 F3D v3']
					combiner2 = nodes['Color Combiner Cycle 2 F3D v3']
					material.node_tree.links.new(combiner2.inputs[i],
						combiner1.outputs[0 if combinerInputs[i] == 'COMBINED' else 1])
			else:
				if cycleIndex == 2 and combinerInputs[i][:5] == "TEXEL":
					value = combinerInputs[i]
					combinerInput = value.replace("0", "1") if "0" in value else value.replace("1", "0")
				else:
					combinerInput = combinerInputs[i]
				combinerSocket = getSocketFromCombinerToNodeDictColor(nodes, f3dVer, combinerInput)
				material.node_tree.links.new(combinerNode.inputs[i], combinerSocket)
		else:
			if combinerInputs[i] == 'COMBINED':
				if cycleIndex == 2:
					combiner1 = nodes['Color Combiner Cycle 1 F3D v3']
					combiner2 = nodes['Color Combiner Cycle 2 F3D v3']
					material.node_tree.links.new(combiner2.inputs[i], combiner1.outputs[1])
			else:
				combinerSocket = getSocketFromCombinerToNodeDictAlpha(nodes, f3dVer, combinerInputs[i])
				material.node_tree.links.new(combinerNode.inputs[i], combinerSocket)

def update_node_values_of_material(material, context):
	nodes = material.node_tree.nodes

	# Case where f3d render engine is used instead of node graph
	# Note that v4 doesn't change the node graph from v3, so we use that name
	if material.mat_ver > 3:
		update_blend_method(material, context)
		if not hasNodeGraph(material):
			return

	if material.mat_ver > 3:
		f3dMat = material.f3d_mat
	else:
		f3dMat = material

	f3dVer = F3D('F3D', False)
	if material.mat_ver == 1:
		nodes['Case A 1'].inA = material.combiner1.A
		nodes['Case B 1'].inB = material.combiner1.B
		nodes['Case C 1'].inC = material.combiner1.C
		nodes['Case D 1'].inD = material.combiner1.D
		nodes['Case A Alpha 1'].inA_alpha = material.combiner1.A_alpha
		nodes['Case B Alpha 1'].inB_alpha = material.combiner1.B_alpha
		nodes['Case C Alpha 1'].inC_alpha = material.combiner1.C_alpha
		nodes['Case D Alpha 1'].inD_alpha = material.combiner1.D_alpha
		nodes['Case A 2'].inA = material.combiner2.A
		nodes['Case B 2'].inB = material.combiner2.B
		nodes['Case C 2'].inC = material.combiner2.C
		nodes['Case D 2'].inD = material.combiner2.D
		nodes['Case A Alpha 2'].inA_alpha = material.combiner2.A_alpha
		nodes['Case B Alpha 2'].inB_alpha = material.combiner2.B_alpha
		nodes['Case C Alpha 2'].inC_alpha = material.combiner2.C_alpha
		nodes['Case D Alpha 2'].inD_alpha = material.combiner2.D_alpha
	elif material.mat_ver == 2:
		nodes['Case A 1'].outputs[0].default_value = f3dVer.CCMUXDict[material.combiner1.A]
		nodes['Case B 1'].outputs[0].default_value = f3dVer.CCMUXDict[material.combiner1.B]
		nodes['Case C 1'].outputs[0].default_value = f3dVer.CCMUXDict[material.combiner1.C]
		nodes['Case D 1'].outputs[0].default_value = f3dVer.CCMUXDict[material.combiner1.D]
		nodes['Case A Alpha 1'].outputs[0].default_value = f3dVer.ACMUXDict[material.combiner1.A_alpha]
		nodes['Case B Alpha 1'].outputs[0].default_value = f3dVer.ACMUXDict[material.combiner1.B_alpha]
		nodes['Case C Alpha 1'].outputs[0].default_value = f3dVer.ACMUXDict[material.combiner1.C_alpha]
		nodes['Case D Alpha 1'].outputs[0].default_value = f3dVer.ACMUXDict[material.combiner1.D_alpha]
		nodes['Case A 2'].outputs[0].default_value = f3dVer.CCMUXDict[material.combiner2.A]
		nodes['Case B 2'].outputs[0].default_value = f3dVer.CCMUXDict[material.combiner2.B]
		nodes['Case C 2'].outputs[0].default_value = f3dVer.CCMUXDict[material.combiner2.C]
		nodes['Case D 2'].outputs[0].default_value = f3dVer.CCMUXDict[material.combiner2.D]
		nodes['Case A Alpha 2'].outputs[0].default_value = f3dVer.ACMUXDict[material.combiner2.A_alpha]
		nodes['Case B Alpha 2'].outputs[0].default_value = f3dVer.ACMUXDict[material.combiner2.B_alpha]
		nodes['Case C Alpha 2'].outputs[0].default_value = f3dVer.ACMUXDict[material.combiner2.C_alpha]
		nodes['Case D Alpha 2'].outputs[0].default_value = f3dVer.ACMUXDict[material.combiner2.D_alpha]
	elif material.mat_ver >= 3:
		combinerInputs1 = [
			f3dMat.combiner1.A,
			f3dMat.combiner1.B,
			f3dMat.combiner1.C,
			f3dMat.combiner1.D,
			f3dMat.combiner1.A_alpha,
			f3dMat.combiner1.B_alpha,
			f3dMat.combiner1.C_alpha,
			f3dMat.combiner1.D_alpha,
		]

		combinerInputs2 = [
			f3dMat.combiner2.A,
			f3dMat.combiner2.B,
			f3dMat.combiner2.C,
			f3dMat.combiner2.D,
			f3dMat.combiner2.A_alpha,
			f3dMat.combiner2.B_alpha,
			f3dMat.combiner2.C_alpha,
			f3dMat.combiner2.D_alpha,
		]

		update_node_combiner(material, combinerInputs1, f3dVer, 1)
		update_node_combiner(material, combinerInputs2, f3dVer, 2)

	if material.mat_ver >= 3:
		nodes['F3D v3'].inputs[4].default_value = 1 if \
			f3dMat.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE' else 0
		nodes['F3D v3'].inputs[5].default_value = \
			0 if f3dMat.rdp_settings.g_cull_front else 1
		nodes['F3D v3'].inputs[6].default_value = \
			0 if f3dMat.rdp_settings.g_cull_back else 1

		nodes['Get UV 0 F3D v3'].inputs[0].default_value = 1 if \
			f3dMat.rdp_settings.g_tex_gen else 0
		nodes['Get UV 0 F3D v3'].inputs[1].default_value = 1 if \
			f3dMat.rdp_settings.g_tex_gen_linear else 0
		nodes['Get UV 1 F3D v3'].inputs[0].default_value = 1 if \
			f3dMat.rdp_settings.g_tex_gen else 0
		nodes['Get UV 1 F3D v3'].inputs[1].default_value = 1 if \
			f3dMat.rdp_settings.g_tex_gen_linear else 0

		nodes['Shade Color'].inputs[0].default_value = 0 if \
			not f3dMat.rdp_settings.g_shade else 1
		nodes['Shade Color'].inputs[1].default_value = 0 if \
			not f3dMat.rdp_settings.g_lighting else 1

		if f3dMat.use_default_lighting:
			nodes['Shade Color'].inputs[2].default_value = \
				(f3dMat.default_light_color[0],
				f3dMat.default_light_color[1],
				f3dMat.default_light_color[2],
				f3dMat.default_light_color[3])
		else:
			nodes['Shade Color'].inputs[2].default_value = \
				(f3dMat.ambient_light_color[0],
				f3dMat.ambient_light_color[1],
				f3dMat.ambient_light_color[2],
				f3dMat.ambient_light_color[3])

		if material.mat_ver > 3:
			nodes['Primitive Color Output'].inputs[0].default_value = \
				(f3dMat.prim_color[0],
				f3dMat.prim_color[1],
				f3dMat.prim_color[2],
				f3dMat.prim_color[3])

			nodes['Environment Color Output'].inputs[0].default_value = \
				(f3dMat.env_color[0],
				f3dMat.env_color[1],
				f3dMat.env_color[2],
				f3dMat.env_color[3])

			nodes['Chroma Key Center'].outputs[0].default_value = \
				(f3dMat.key_center[0],
				f3dMat.key_center[1],
				f3dMat.key_center[2],
				f3dMat.key_center[3])

	else:
		nodes['Cycle Type'].outputs[0].default_value = 1 if \
			material.rdp_settings.g_mdsft_cycletype == 'G_CYC_2CYCLE' else 0
		nodes['Cull Front'].outputs[0].default_value = \
			0 if material.rdp_settings.g_cull_front else 1
		nodes['Cull Back'].outputs[0].default_value = \
			0 if material.rdp_settings.g_cull_back else 1
		nodes['Texture Gen'].outputs[0].default_value = 1 if \
			material.rdp_settings.g_tex_gen else 0
		nodes['Texture Gen Linear'].outputs[0].default_value = 1 if \
			material.rdp_settings.g_tex_gen_linear else 0
		nodes['Shading'].outputs[0].default_value = 0 if \
			not material.rdp_settings.g_shade else 1
		nodes['Lighting'].outputs[0].default_value = 0 if \
			not material.rdp_settings.g_lighting else 1

		if material.use_default_lighting:
			nodes['Ambient Color'].outputs[0].default_value = \
				(material.default_light_color[0],
				material.default_light_color[1],
				material.default_light_color[2],
				material.default_light_color[3])
		else:
			nodes['Ambient Color'].outputs[0].default_value = \
				(material.ambient_light_color[0],
				material.ambient_light_color[1],
				material.ambient_light_color[2],
				material.ambient_light_color[3])

	material.show_transparent_back = f3dMat.rdp_settings.g_cull_front
	nodes['Chroma Key Scale'].outputs[0].default_value = \
		[value for value in f3dMat.key_scale] + [1]
	nodes['Primitive LOD Fraction'].outputs[0].default_value = \
		f3dMat.prim_lod_frac

	# nodes['YUV Convert K0'].outputs[0].default_value = material.k0
	# nodes['YUV Convert K1'].outputs[0].default_value = material.k1
	# nodes['YUV Convert K2'].outputs[0].default_value = material.k2
	# nodes['YUV Convert K3'].outputs[0].default_value = material.k3
	nodes['YUV Convert K4'].outputs[0].default_value = f3dMat.k4
	nodes['YUV Convert K5'].outputs[0].default_value = f3dMat.k5

	update_tex_values_manual(material, context)

def update_tex_values_field(self, fieldProperty, texCoordNode, pixelLength,
	isTexGen, uvBasisScale, scale, autoprop, reverseValues, texIndex, field):
	clamp = fieldProperty.clamp
	mirror = fieldProperty.mirror

	clampNode = texCoordNode['Clamp']
	mirrorNode = texCoordNode['Mirror']
	normHalfPixelNode = texCoordNode['Normalized Half Pixel']
	normLNode = texCoordNode["Normalized L"]
	normHNode = texCoordNode["Normalized H"]
	normMaskNode = texCoordNode["Normalized Mask"]
	shiftNode = texCoordNode['Shift']
	scaleNode = texCoordNode['Scale']

	clampNode.outputs[0].default_value = 1 if clamp else 0
	mirrorNode.outputs[0].default_value = 1 if mirror else 0
	normHalfPixelNode.outputs[0].default_value = \
			1 / (2 * pixelLength)

	if autoprop:
		fieldProperty.low = 0
		fieldProperty.high = pixelLength - 1
		fieldProperty.mask =  math.ceil(math.log(pixelLength, 2) - 0.001)
		#fieldProperty.mask = 0
		fieldProperty.shift = 0

	L = fieldProperty.low
	H = fieldProperty.high
	mask = fieldProperty.mask
	shift = fieldProperty.shift

	if reverseValues:
		normLNode.outputs[0].default_value = -L / pixelLength
	else:
		normLNode.outputs[0].default_value = L / pixelLength
	normHNode.outputs[0].default_value = (H + 1)/pixelLength
	normMaskNode.outputs[0].default_value = \
		(2 ** mask) / pixelLength if mask > 0 else 0

	shiftNode.outputs[0].default_value = shift
	scaleNode.outputs[0].default_value = scale * uvBasisScale

def setAutoProp(fieldProperty, pixelLength):
	fieldProperty.low = 0
	fieldProperty.high = pixelLength - 1
	fieldProperty.mask =  math.ceil(math.log(pixelLength, 2) - 0.001)
	#fieldProperty.mask = 0
	fieldProperty.shift = 0

def update_tex_values_field_v2(self, fieldProperty, pixelLength,
	uvBasisScale, scale, autoprop, texIndex, field):

	fieldIndex = 0 if field == 'S' else 1
	pixelLengthAxis = pixelLength[fieldIndex]

	nodes = self.node_tree.nodes
	clampNode = nodes['Tex ' + str(texIndex) + ' Clamp']
	mirrorNode = nodes['Tex ' + str(texIndex) + ' Mirror']
	normHalfPixelNode = nodes['Tex ' + str(texIndex) + ' Normalized Half Pixel']
	normLNode = nodes['Tex ' + str(texIndex) + " Normalized L"]
	normHNode = nodes['Tex ' + str(texIndex) + " Normalized H"]
	normMaskNode = nodes["Tex " + str(texIndex) + " Normalized Mask"]
	shiftNode = nodes['Tex ' + str(texIndex) + ' Shift']
	scaleNode = nodes['Tex ' + str(texIndex) + ' Scale']

	clampNode.inputs[fieldIndex].default_value = 1 if fieldProperty.clamp else 0
	mirrorNode.inputs[fieldIndex].default_value = 1 if fieldProperty.mirror else 0
	normHalfPixelNode.inputs[fieldIndex].default_value = 1 / (2 * pixelLengthAxis)

	if autoprop:
		setAutoProp(fieldProperty, pixelLengthAxis)

	normLNode.inputs[fieldIndex].default_value = fieldProperty.low / pixelLengthAxis * (-1 if field == 'T' else 1)
	normHNode.inputs[fieldIndex].default_value = (fieldProperty.high + 1)/pixelLengthAxis
	normMaskNode.inputs[fieldIndex].default_value = (2 ** fieldProperty.mask) / pixelLengthAxis if fieldProperty.mask > 0 else 0
	shiftNode.inputs[fieldIndex].default_value = fieldProperty.shift
	scaleNode.inputs[fieldIndex].default_value = scale[fieldIndex] * uvBasisScale[fieldIndex]

def update_tex_values_field_v3(self, texProperty, tex_size,
	uvBasisScale, scale, texIndex):
	nodes = self.node_tree.nodes
	if texProperty.autoprop:
		setAutoProp(texProperty.S, tex_size[0])
		setAutoProp(texProperty.T, tex_size[1])

	# For input index, Tex Gen = 0, Tex Gen Linear = 1

	# Image Factor
	nodes['Get UV ' + str(texIndex) + ' F3D v3'].inputs[2].default_value = (
		1024 / tex_size[0], 1024 / tex_size[1], 0)

	# Normalized L
	nodes['Get UV ' + str(texIndex) + ' F3D v3'].inputs[3].default_value = (
		texProperty.S.low / tex_size[0],
		texProperty.T.low / tex_size[1], 0)

	# Normalized H
	nodes['Get UV ' + str(texIndex) + ' F3D v3'].inputs[4].default_value = (
		(texProperty.S.high + 1) / tex_size[0],
		(texProperty.T.high + 1) / tex_size[1], 0)

	# Clamp
	isTexGen = self.f3d_mat.rdp_settings.g_tex_gen or self.f3d_mat.rdp_settings.g_tex_gen_linear
	nodes['Get UV ' + str(texIndex) + ' F3D v3'].inputs[5].default_value = (
		1 if texProperty.S.clamp and not isTexGen else 0,
		1 if texProperty.T.clamp and not isTexGen else 0, 0)

	# Normalized Mask
	nodes['Get UV ' + str(texIndex) + ' F3D v3'].inputs[6].default_value = (
		(2 ** texProperty.S.mask) / tex_size[0] if texProperty.S.mask > 0 else 0,
		(2 ** texProperty.T.mask) / tex_size[1] if texProperty.T.mask > 0 else 0, 0)

	# Mirror
	nodes['Get UV ' + str(texIndex) + ' F3D v3'].inputs[7].default_value = (
		1 if texProperty.S.mirror else 0,
		1 if texProperty.T.mirror else 0, 0)

	# Shift
	nodes['Get UV ' + str(texIndex) + ' F3D v3'].inputs[8].default_value = (
		texProperty.S.shift,
		texProperty.T.shift, 0)

	# Scale
	nodes['Get UV ' + str(texIndex) + ' F3D v3'].inputs[9].default_value = (
		scale[0] * uvBasisScale[0],
		scale[1] * uvBasisScale[1], 0)

	# Normalized Half Pixel
	nodes['Get UV ' + str(texIndex) + ' F3D v3'].inputs[10].default_value = (
		1 / (2 * tex_size[0]),
		1 / (2 * tex_size[1]), 0)

def update_tex_values_index(self, context, texProperty, texNodeName,
	uvNodeName, isTexGen, uvBasisScale, scale, texIndex):
	nodes = self.node_tree.nodes

	nodes[texNodeName].image = texProperty.tex
	if nodes[texNodeName].image is not None or texProperty.use_tex_reference:
		if nodes[texNodeName].image is not None:
			tex_size = nodes[texNodeName].image.size
		else:
			tex_size = texProperty.tex_reference_size
		if tex_size[0] > 0 and tex_size[1] > 0:
			if self.mat_ver == 1:
				tex_x = nodes[uvNodeName].node_tree.nodes[\
					'Create Tex Coord'].node_tree.nodes
				tex_y = nodes[uvNodeName].node_tree.nodes[\
					'Create Tex Coord.001'].node_tree.nodes
				imageWidthNode = nodes[uvNodeName].node_tree.nodes['Image Width Factor']
				imageHeightNode = nodes[uvNodeName].node_tree.nodes['Image Height Factor']
				# 1024 == 2^16 / 2^6 (converting 0.16 to 10.5 fixed point)
				imageWidthNode.outputs[0].default_value = 1024 / tex_size[0]
				imageHeightNode.outputs[0].default_value = 1024 / tex_size[1]

				update_tex_values_field(self, texProperty.S, tex_x, tex_size[0],
					self.rdp_settings.g_tex_gen or self.rdp_settings.g_tex_gen_linear,
					uvBasisScale[0], scale[0], texProperty.autoprop, False, texIndex, 'S')
				update_tex_values_field(self, texProperty.T, tex_y, tex_size[1],
					self.rdp_settings.g_tex_gen or self.rdp_settings.g_tex_gen_linear,
					uvBasisScale[1], scale[1], texProperty.autoprop, True, texIndex, 'T')
			elif self.mat_ver == 2:
				tex_x = nodes
				tex_y = nodes
				imageFactorNode = nodes['Tex ' + str(texIndex) + ' Image Factor']
				imageFactorNode.inputs[0].default_value = 1024 / tex_size[0]
				imageFactorNode.inputs[1].default_value = 1024 / tex_size[1]

				update_tex_values_field_v2(self, texProperty.S, tex_size,
					uvBasisScale, scale, texProperty.autoprop, texIndex, 'S')
				update_tex_values_field_v2(self, texProperty.T, tex_size,
					uvBasisScale, scale, texProperty.autoprop, texIndex, 'T')
			elif self.mat_ver >= 3:
				if self.mat_ver > 3:
					f3dMat = self.f3d_mat
				else:
					f3dMat = self
				if self.mat_ver == 3 or hasNodeGraph(self):
					update_tex_values_field_v3(self, texProperty, tex_size,
						uvBasisScale, scale, texIndex)
					#nodes[texNodeName].interpolation = "Closest"
					nodes[texNodeName].interpolation = "Closest" if \
						f3dMat.rdp_settings.g_mdsft_text_filt == 'G_TF_POINT' else "Linear"
				else:
					if texProperty.autoprop:
						setAutoProp(texProperty.S, tex_size[0])
						setAutoProp(texProperty.T, tex_size[1])
			else:
				print("Error: Unhandled material version " + str(self.mat_ver) + ' for texture properties.')

			texFormat = texProperty.tex_format
			ciFormat = texProperty.ci_format
			if self.mat_ver >= 3: # No nodes, only sockets (0 = color, 1 = alpha)
				if self.mat_ver == 3 or hasNodeGraph(self):
					getTextureColorName = 'Get Texture Color' if texIndex == 0 else "Get Texture Color.001"
					# Is Greyscale
					nodes[getTextureColorName].inputs[2].default_value =\
						1 if (texFormat[0] == 'I' or \
						(texFormat[:2] == 'CI' and ciFormat[0] == 'I')) else 0

					# Has Alpha
					nodes[getTextureColorName].inputs[3].default_value = \
	 					1 if ('A' in texFormat or \
						(texFormat[:2] == 'CI' and 'A' in ciFormat)) else 0

					# Is Intensity
					nodes[getTextureColorName].inputs[4].default_value =\
						1 if (texFormat == 'I4' or texFormat == 'I8') else 0

			else:
				nodes[texNodeName + ' Is Greyscale'].outputs[0].default_value = \
	 				1 if (texFormat[0] == 'I' or \
					(texFormat[:2] == 'CI' and ciFormat[0] == 'I')) else 0
				nodes[texNodeName + ' Has Alpha'].outputs[0].default_value = \
	 				1 if ('A' in texFormat or \
					(texFormat[:2] == 'CI' and 'A' in ciFormat))else 0

				if texNodeName + " Is Intensity" in nodes:
					nodes[texNodeName + " Is Intensity"].outputs[0].default_value =\
						1 if (texFormat == 'I4' or texFormat == 'I8') else 0
				else:
					print("Using old node graph, cannot set intensity as alpha.")

def update_tex_values_and_formats(self, context):
	if hasattr(context, 'material') and context.material is not None:
		if context.material.mat_ver > 3:
			material = context.material.f3d_mat
			useLargeTextures = material.use_large_textures
			isMultiTexture = "multitexture" in material.presetName.lower()
		else:
			material = context.material
			useLargeTextures = False
			isMultiTexture = False

		if context.material.f3d_update_flag:
			return
		context.material.f3d_update_flag = True
		if material.tex0 == self and material.tex0.tex is not None:
			if isMultiTexture:
				material.tex0.tex_format = 'RGBA16'
			else:
				material.tex0.tex_format = getOptimalFormat(material.tex0.tex, useLargeTextures)
		if material.tex1 == self and material.tex1.tex is not None:
			if isMultiTexture:
				material.tex1.tex_format = 'RGBA16'
			else:
				material.tex1.tex_format = getOptimalFormat(material.tex1.tex, useLargeTextures)
		context.material.f3d_update_flag = False

		update_tex_values(context.material, context)
	else:
		if self.tex is not None:
			self.tex_format = getOptimalFormat(self.tex, False)

def update_tex_values(self, context):
	if hasattr(context, 'material') and context.material is not None:
		material = context.material # Handles case of texture property groups
		if material.f3d_update_flag:
			return
		material.f3d_update_flag = True
		update_tex_values_manual(material, context)
		material.f3d_update_flag = False

def update_tex_values_manual(self, context):
	if self.mat_ver > 3:
		material = self.f3d_mat
	else:
		material = self
	isTexGen = material.rdp_settings.g_tex_gen or material.rdp_settings.g_tex_gen_linear

	if material.scale_autoprop:
		tex_size = None
		if material.tex0.tex is not None and material.tex1.tex is not None:
			tex_size = material.tex0.tex.size if material.uv_basis == 'TEXEL0' else \
				material.tex1.tex.size
		elif material.tex0.tex is not None:
			tex_size = material.tex0.tex.size
		elif material.tex1.tex is not None:
			tex_size = material.tex1.tex.size

		if isTexGen and tex_size is not None:
			material.tex_scale = ((tex_size[0] - 1) / 1024,
				(tex_size[1] - 1) / 1024)
		else:
			material.tex_scale = (1,1)


	useDict = all_combiner_uses(material)

	if useDict['Texture 0'] and material.tex0.tex is not None and \
		useDict['Texture 1'] and material.tex1.tex is not None and\
		material.tex0.tex.size[0] > 0 and material.tex0.tex.size[1] > 0 and\
		material.tex1.tex.size[0] > 0 and material.tex1.tex.size[1] > 0:
		if material.uv_basis == 'TEXEL0':
			uvBasisScale0 = (1,1)
			uvBasisScale1 = (material.tex0.tex.size[0] / material.tex1.tex.size[0],
				material.tex0.tex.size[1] / material.tex1.tex.size[1])
		else:
			uvBasisScale1 = (1,1)
			uvBasisScale0 = (material.tex1.tex.size[0] / material.tex0.tex.size[0],
				material.tex1.tex.size[1] / material.tex0.tex.size[1])
	else:
		uvBasisScale0 = (1,1)
		uvBasisScale1 = (1,1)

	update_tex_values_index(self, context, material.tex0, 'Texture 0',
		'Get UV', isTexGen, uvBasisScale0, material.tex_scale, 0)
	update_tex_values_index(self, context, material.tex1, 'Texture 1',
		'Get UV.001', isTexGen, uvBasisScale1, material.tex_scale, 1)

def getMaterialScrollDimensions(material):
	useDict = all_combiner_uses(material)

	if useDict['Texture 0'] and material.tex0.tex is not None and \
		useDict['Texture 1'] and material.tex1.tex is not None and\
		material.tex0.tex.size[0] > 0 and material.tex0.tex.size[1] > 0 and\
		material.tex1.tex.size[0] > 0 and material.tex1.tex.size[1] > 0:
		if material.uv_basis == 'TEXEL0':
			return material.tex0.tex.size
		else:
			return material.tex1.tex.size
	elif useDict['Texture 1'] and material.tex1.tex is not None and\
		material.tex1.tex.size[0] > 0 and material.tex1.tex.size[1] > 0:
		return material.tex1.tex.size
	elif useDict['Texture 0'] and material.tex0.tex is not None and\
		material.tex0.tex.size[0] > 0 and material.tex0.tex.size[1] > 0:
		return material.tex0.tex.size
	else:
		return [32, 32]

def update_preset(self, context):
	if hasattr(context, 'material_slot') and context.material_slot is not None:
		material = context.material_slot.material
		if material.mat_ver < 4 and material.f3d_preset != 'Custom':
			materialSettings = materialPresetDict[material.f3d_preset]
			materialSettings.applyToMaterial(material, False, update_node_values_of_material, bpy.context)

def update_preset_manual(material, context):
	if material.mat_ver < 4 and material.f3d_preset != 'Custom':
		materialSettings = materialPresetDict[material.f3d_preset]
		materialSettings.applyToMaterial(material, False, update_node_values_of_material, bpy.context)

	if material.mat_ver > 3:
		if hasNodeGraph(material):
			update_node_values_of_material(material, context)
		update_tex_values_manual(material, context)

def update_preset_manual_v4(material, preset):
	override = bpy.context.copy()
	override['material'] = material
	if preset == 'Shaded Solid':
		preset = 'sm64_shaded_solid'
	if preset == 'Shaded Texture':
		preset = "sm64_shaded_texture"
	if preset.lower() != "custom":
		material.f3d_update_flag = True
		bpy.ops.script.execute_preset(override,
			filepath=findF3DPresetPath(preset),
			menu_idname='MATERIAL_MT_f3d_presets')
		material.f3d_update_flag = False

def hasNodeGraph(material):
	return "F3D v3" in material.node_tree.nodes

def createF3DMat(obj, preset = 'Shaded Solid', index = None):
	material = bpy.data.materials.new('f3d_material')
	if obj is not None:
		if index is None:
			obj.data.materials.append(material)
			if bpy.context.object is not None:
				bpy.context.object.active_material_index = len(obj.material_slots) - 1
		else:
			obj.material_slots[index].material = material
			if bpy.context.object is not None:
				bpy.context.object.active_material_index = index

	material.is_f3d = True
	material.mat_ver = 4

	if material.mat_ver > 3 and not bpy.context.scene.generateF3DNodeGraph:
		material.use_nodes = True
		material.blend_method = 'BLEND'
		material.show_transparent_back = False

		# Remove default shader
		node_tree = material.node_tree
		nodes = material.node_tree.nodes
		links = material.node_tree.links
		bsdf = nodes.get('Principled BSDF')
		material_output = nodes.get('Material Output')

		tex0Node = node_tree.nodes.new("ShaderNodeTexImage")
		tex0Node.name = "Texture 0"
		tex0Node.label = "Texture 0"
		tex0Node.location = [-300, 300]
		tex1Node = node_tree.nodes.new("ShaderNodeTexImage")
		tex1Node.name = "Texture 1"
		tex1Node.label = "Texture 1"
		tex1Node.location = [-300, 50]

		links.new(bsdf.inputs["Base Color"], tex0Node.outputs["Color"])
		links.new(bsdf.inputs["Subsurface Color"], tex1Node.outputs["Color"])
		bsdf.inputs['Specular'].default_value = 0

		update_preset_manual_v4(material, preset)

		return material

	material.use_nodes = True
	material.blend_method = 'HASHED'
	material.show_transparent_back = False

	# Remove default shader
	node_tree = material.node_tree
	nodes = material.node_tree.nodes
	links = material.node_tree.links
	nodes.remove(nodes.get('Principled BSDF'))
	material_output = nodes.get('Material Output')

	x = 0
	y = 0

	uvDict = {}
	#texGenNode, x, y = addNodeAt(node_tree, 'ShaderNodeValue',
	#	'Texture Gen', x, y, 'Texture Gen', uvDict)
	#texGenLinearNode, x, y = addNodeAt(node_tree, 'ShaderNodeValue',
	#	'Texture Gen Linear', x, y, 'Texture Gen Linear', uvDict)

	# Create UV nodes
	uvNode0, x, y = createUVInputsAndGroup(node_tree, 0, x, y)
	uvNode1, x, y = createUVInputsAndGroup(node_tree, 1, x, y)

	x += 600
	y = 0
	x,y, primNode = addColorWithAlphaNode("Primitive Color", x, y, node_tree)
	x,y, envNode = addColorWithAlphaNode("Environment Color", x, y, node_tree)
	nodeDict, x, y = addNodeListAt(node_tree, {
		'Texture 0': 'ShaderNodeTexImage',
		'Texture 1': 'ShaderNodeTexImage',
		#'Primitive Color': 'ShaderNodeRGB',
		#'Shade Color': 'ShaderNodeBsdfDiffuse',
		#'Environment Color': 'ShaderNodeRGB',
		'Chroma Key Center': 'ShaderNodeRGB',
		'Chroma Key Scale': 'ShaderNodeRGB',
		#'Primitive Alpha': 'ShaderNodeValue',
		#'Shade Alpha': 'ShaderNodeValue',
		#'Environment Alpha' : 'ShaderNodeValue',
		'LOD Fraction' : 'ShaderNodeValue',
		'Primitive LOD Fraction' : 'ShaderNodeValue',
		'Noise' : 'ShaderNodeTexNoise',
		'YUV Convert K4' : 'ShaderNodeValue',
		'YUV Convert K5' : 'ShaderNodeValue',
		'1' : 'ShaderNodeValue',
		'0' : 'ShaderNodeValue',
		}, x, y)

	# Set noise scale
	nodeDict["Noise"].inputs[2].default_value = 10

	createGroupLink(node_tree, nodeDict['Texture 0'].inputs[0],
		uvNode0.outputs[0], 'NodeSocketVector', 'UV0Output')
	createGroupLink(node_tree, nodeDict['Texture 1'].inputs[0],
		uvNode1.outputs[0], 'NodeSocketVector', 'UV1Output')


	# Note: Because of modulo operations on UVs, aliasing occurs
	# due to mipmapping when 'Linear' filtering is used.
	# When using 'Cubic', clamping doesn't work correctly either.
	# Thus 'Closest' is used instead.
	nodes['Texture 0'].interpolation = 'Linear'
	nodes['Texture 1'].interpolation = 'Linear'

	# Create texture format nodes
	x += 300
	y = 0
	colorNode0, x, y = createTextureInputsAndGroup(node_tree, 0, x, y)
	colorNode1, x, y = createTextureInputsAndGroup(node_tree, 1, x, y)
	nodeDict["Texture 0"] = colorNode0
	nodeDict["Texture 1"] = colorNode1

	# Create cases A-D
	#x += 300
	#y = 0
	#caseNodeDict1, x, y = addNodeListAt(node_tree,
	#	caseTemplateDict2, x, y, 1)
	#
	#caseNodeDict2, x, y = addNodeListAt(node_tree,
	#	caseTemplateDict2, x, y, 2)

	# create shade node
	x += 300
	y = 0
	#lightingNode, x, y = addNodeAt(node_tree, 'ShaderNodeValue',
	#	'Lighting', x, y)
	#shadingNode, x, y = addNodeAt(node_tree, 'ShaderNodeValue',
	#	'Shading', x, y)
	#ambientNode, x, y = addNodeAt(node_tree, 'ShaderNodeRGB',
	#	'Ambient Color', x, y)
	nodeDict['Shade Color'] = createShadeNode(node_tree, [x, y])

	#x += 300
	#y = 0
	#otherDict = {}
	#cycleTypeNode, x, y = \
	#	addNodeAt(node_tree, 'ShaderNodeValue', 'Cycle Type', x, y, 'Cycle Type', otherDict)
	#cullFront, x, y = \
	#	addNodeAt(node_tree, 'ShaderNodeValue', 'Cull Front', x, y, "Cull Front", otherDict)
	#cullBack, x, y = \
	#	addNodeAt(node_tree, 'ShaderNodeValue', 'Cull Back', x, y, 'Cull Back', otherDict)

	x += 300
	y = 0
	# Create combiner nodes
	# caseNodeDict is the A-D for color and alpha
	# nodeDict is all sources
	# otherDict is other shader inputs

	combiner1 = createNodeCombiner(node_tree, 1)
	combiner1.location = [x, y]

	combiner2 = createNodeCombiner(node_tree, 2)
	combiner2.location = [x, y-400]

	x += 300
	y = 0
	finalNode, x, y = createNodeF3D(node_tree, [x, y])

	links.new(finalNode.inputs[0], combiner1.outputs[0])
	links.new(finalNode.inputs[1], combiner1.outputs[1])
	links.new(finalNode.inputs[2], combiner2.outputs[0])
	links.new(finalNode.inputs[3], combiner2.outputs[1])

	# link new node output to material_output input
	links.new(material_output.inputs[0], finalNode.outputs[0])

	x += 300
	y = 0
	material_output.location = [x, y]

	#update_node_values_directly(material, bpy.context)
	#update_tex_values(material, bpy.context)

	if material.mat_ver > 3:
		update_preset_manual_v4(material, preset)
	else:
		# This won't update because material is not in context
		if preset in [enumValue[0] for enumValue in enumMaterialPresets]:
			material.f3d_preset = preset
		else:
			raise PluginError('Enum \'' + preset + '\' not found in material preset enum list.')
		# That's why we force update
		update_preset_manual(material, bpy.context)
		#materialPresetDict['Shaded Texture'].applyToMaterial(material)

	return material

def reloadDefaultF3DPresets():
	presetNameToFilename = {}
	for game, gamePresets in material_presets.items():
		for presetName, preset in gamePresets.items():
			presetNameToFilename[bpy.path.display_name(presetName)] = presetName
	for material in bpy.data.materials:
		if material.mat_ver > 3 and material.f3d_mat.presetName in presetNameToFilename:
			update_preset_manual_v4(material, presetNameToFilename[material.f3d_mat.presetName])

class CreateFast3DMaterial(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.create_f3d_mat'
	bl_label = "Create Fast3D Material"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		obj = bpy.context.view_layer.objects.active
		if obj is None:
			self.report({'ERROR'}, 'No active object selected.')
		else:
			preset = getDefaultMaterialPreset("Shaded Solid")
			createF3DMat(obj, preset)
			self.report({'INFO'}, 'Created new Fast3D material.')
		return {'FINISHED'} # must return a set

class ReloadDefaultF3DPresets(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.reload_f3d_presets'
	bl_label = "Reload Default Fast3D Presets"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		reloadDefaultF3DPresets()
		self.report({'INFO'}, 'Success!')
		return {'FINISHED'} # must return a set

class TextureFieldProperty(bpy.types.PropertyGroup):
	clamp : bpy.props.BoolProperty(name = 'Clamp',
		update = update_tex_values)
	mirror : bpy.props.BoolProperty(name = 'Mirror',
		update = update_tex_values)
	low : bpy.props.FloatProperty(name = 'Low', min = 0, max = 1023.75,
		update = update_tex_values)
	high : bpy.props.FloatProperty(name = 'High', min = 0, max = 1023.75,
		update = update_tex_values)
	mask : bpy.props.IntProperty(min = 0, max = 15,
		update = update_tex_values, default = 5)
	shift : bpy.props.IntProperty(min = -5, max = 10,
		update = update_tex_values)

class SetTileSizeScrollProperty(bpy.types.PropertyGroup):
	s : bpy.props.IntProperty(min = -4095, max = 4095, default = 0)
	t : bpy.props.IntProperty(min = -4095, max = 4095, default = 0)
	interval : bpy.props.IntProperty(min = 1, soft_max = 1000, default = 1)

class TextureProperty(bpy.types.PropertyGroup):
	tex : bpy.props.PointerProperty(type = bpy.types.Image, name = 'Texture', update = update_tex_values_and_formats)

	tex_format : bpy.props.EnumProperty(name = 'Format', items = enumTexFormat, default = 'RGBA16', update = update_tex_values)
	ci_format : bpy.props.EnumProperty(name = 'CI Format', items = enumCIFormat, default = 'RGBA16', update = update_tex_values)
	S : bpy.props.PointerProperty(type = TextureFieldProperty)
	T : bpy.props.PointerProperty(type = TextureFieldProperty)

	use_tex_reference: bpy.props.BoolProperty(name = "Use Texture Reference", default = False, update = update_tex_values)
	tex_reference: bpy.props.StringProperty(name = "Texture Reference", default = '0x08000000')
	tex_reference_size: bpy.props.IntVectorProperty(name = "Texture Reference Size", min = 1, size = 2, default = (32,32), update = update_tex_values)
	pal_reference: bpy.props.StringProperty(name = "Palette Reference", default = '0x08000000')
	pal_reference_size : bpy.props.IntProperty(name = "Texture Reference Size", min = 1, default = 16)

	menu : bpy.props.BoolProperty()
	tex_set : bpy.props.BoolProperty(default = True, update = update_node_values)
	autoprop : bpy.props.BoolProperty(name = 'Autoprop', update = update_tex_values, default = True)
	save_large_texture : bpy.props.BoolProperty(name = "Save Large Texture As PNG", default = True)
	tile_scroll :  bpy.props.PointerProperty(type = SetTileSizeScrollProperty)
	#autoprop : bpy.props.BoolProperty(name = 'Autoprop', update = on_tex_autoprop, default = True)

def on_tex_autoprop(texProperty, context):
	if texProperty.autoprop and texProperty.tex is not None:
		tex_size = texProperty.tex.size
		if tex_size[0] > 0 and tex_size[1] > 0:
			setAutoProp(texProperty.S, tex_size[0])
			setAutoProp(texProperty.T, tex_size[1])

class CombinerProperty(bpy.types.PropertyGroup):
	A : bpy.props.EnumProperty(
		name = "A", description = "A", items = combiner_enums['Case A'],
		default = 'TEXEL0', update = update_node_values)

	B : bpy.props.EnumProperty(
		name = "B", description = "B", items = combiner_enums['Case B'],
		default = '0', update = update_node_values)

	C : bpy.props.EnumProperty(
		name = "C", description = "C", items = combiner_enums['Case C'],
		default = 'SHADE', update = update_node_values)

	D : bpy.props.EnumProperty(
		name = "D", description = "D", items = combiner_enums['Case D'],
		default = '0', update = update_node_values)

	A_alpha : bpy.props.EnumProperty(
		name = "A Alpha", description = "A Alpha",
		items = combiner_enums['Case A Alpha'],
		default = '0', update = update_node_values)

	B_alpha : bpy.props.EnumProperty(
		name = "B Alpha", description = "B Alpha",
		items = combiner_enums['Case B Alpha'],
		default = '0', update = update_node_values)

	C_alpha : bpy.props.EnumProperty(
		name = "C Alpha", description = "C Alpha",
		items = combiner_enums['Case C Alpha'],
		default = '0', update = update_node_values)

	D_alpha : bpy.props.EnumProperty(
		name = "D Alpha", description = "D Alpha",
		items = combiner_enums['Case D Alpha'],
		default = 'ENVIRONMENT', update = update_node_values)

class ProceduralAnimProperty(bpy.types.PropertyGroup):
	speed : bpy.props.FloatProperty(name = 'Speed', default = 1)
	amplitude : bpy.props.FloatProperty(name = 'Amplitude', default = 1)
	frequency : bpy.props.FloatProperty(name = 'Frequency', default = 1)
	#spaceFrequency : bpy.props.FloatVectorProperty(name = 'Space Frequency',
	#	size = 3, default = (0,0,0))
	spaceFrequency : bpy.props.FloatProperty(name = 'Space Frequency',
		default = 0)
	offset : bpy.props.FloatProperty(name = 'Offset', default = 0)
	noiseAmplitude : bpy.props.FloatProperty(name = 'Amplitude', default = 1)
	animate : bpy.props.BoolProperty()
	animType : bpy.props.EnumProperty(name = 'Type', items = enumTexScroll)

class ProcAnimVectorProperty(bpy.types.PropertyGroup):
	x : bpy.props.PointerProperty(type = ProceduralAnimProperty)
	y : bpy.props.PointerProperty(type = ProceduralAnimProperty)
	z : bpy.props.PointerProperty(type = ProceduralAnimProperty)
	pivot : bpy.props.FloatVectorProperty(size = 2, name = 'Pivot')
	angularSpeed : bpy.props.FloatProperty(default = 1, name = 'Angular Speed')
	menu : bpy.props.BoolProperty()

class PrimDepthSettings(bpy.types.PropertyGroup):
	z: bpy.props.IntProperty(
		name="Prim Depth: Z",
		default=0,
		soft_min=-1,
		soft_max=0x7fff,
		description=
			'''The value to use for z is the screen Z position of the object you are rendering. This is a value ranging from 0x0000 to 0x7fff, where 0x0000 usually corresponds to the near clipping plane and 0x7fff usually corresponds to the far clipping plane. You can use -1 to force Z to be at the far clipping plane.'''
	)
	dz: bpy.props.IntProperty(
		name="Prim Depth: Delta Z",
		default=0,
		soft_min=0,
		soft_max=0x4000,
		description=
			'''The dz value should be set to 0. This value is used for antialiasing and objects drawn in decal render mode and must always be a power of 2 (0, 1, 2, 4, 8, ... 0x4000). If you are using decal mode and part of the decaled object is not being rendered correctly, try setting this to powers of 2. Otherwise use 0.'''
	)

class RDPSettings(bpy.types.PropertyGroup):
	g_zbuffer : bpy.props.BoolProperty(name = 'Z Buffer', default = True,
		update = update_node_values)
	g_shade : bpy.props.BoolProperty(name = 'Shading', default = True,
		update = update_node_values)
	#v1/2 difference
	g_cull_front : bpy.props.BoolProperty(name = 'Cull Front',
		update = update_node_values)
	#v1/2 difference
	g_cull_back : bpy.props.BoolProperty(name = 'Cull Back', default = True,
		update = update_node_values)
	g_fog : bpy.props.BoolProperty(name = 'Fog',
		update = update_node_values)
	g_lighting : bpy.props.BoolProperty(name = 'Lighting', default = True,
		update = update_node_values)
	g_tex_gen : bpy.props.BoolProperty(name = 'Texture UV Generate',
		update = update_node_values)
	g_tex_gen_linear : bpy.props.BoolProperty(
		name = 'Texture UV Generate Linear',
		update = update_node_values)
	#v1/2 difference
	g_shade_smooth : bpy.props.BoolProperty(name = 'Smooth Shading',
		default = True,	update = update_node_values)
	# f3dlx2 only
	g_clipping : bpy.props.BoolProperty(name = 'Clipping',
		update = update_node_values)

	# upper half mode
	# v2 only
	g_mdsft_alpha_dither : bpy.props.EnumProperty(
		name = 'Alpha Dither', items = enumAlphaDither, default = 'G_AD_NOISE',	update = update_node_values)
	# v2 only
	g_mdsft_rgb_dither : bpy.props.EnumProperty(
		name = 'RGB Dither', items = enumRGBDither, default = 'G_CD_MAGICSQ', update = update_node_values)
	g_mdsft_combkey : bpy.props.EnumProperty(
		name = 'Chroma Key', items = enumCombKey, default = 'G_CK_NONE', update = update_node_values)
	g_mdsft_textconv : bpy.props.EnumProperty(
		name = 'Texture Convert', items = enumTextConv, default = 'G_TC_FILT', update = update_node_values)
	g_mdsft_text_filt : bpy.props.EnumProperty(
		name = 'Texture Filter', items = enumTextFilt, default = 'G_TF_BILERP',
		update = update_node_values_without_preset)
	g_mdsft_textlut : bpy.props.EnumProperty(
		name = 'Texture LUT', items = enumTextLUT, default = 'G_TT_NONE')
	g_mdsft_textlod : bpy.props.EnumProperty(
		name = 'Texture LOD', items = enumTextLOD, default = 'G_TL_TILE', update = update_node_values)
	g_mdsft_textdetail : bpy.props.EnumProperty(
		name = 'Texture Detail', items = enumTextDetail, default = 'G_TD_CLAMP', update = update_node_values)
	g_mdsft_textpersp : bpy.props.EnumProperty(
		name = 'Texture Perspective Correction', items = enumTextPersp,
		default = 'G_TP_PERSP', update = update_node_values)
	g_mdsft_cycletype : bpy.props.EnumProperty(
		name = 'Cycle Type', items = enumCycleType, default = 'G_CYC_1CYCLE',
		update = update_node_values)
	# v1 only
	g_mdsft_color_dither : bpy.props.EnumProperty(
		name = 'Color Dither', items = enumColorDither, default = 'G_CD_ENABLE', update = update_node_values)
	g_mdsft_pipeline : bpy.props.EnumProperty(
		name = 'Pipeline Span Buffer Coherency', items = enumPipelineMode,
		default = 'G_PM_1PRIMITIVE', update = update_node_values)

	# lower half mode
	g_mdsft_alpha_compare : bpy.props.EnumProperty(
		name = 'Alpha Compare', items = enumAlphaCompare,
		default = 'G_AC_NONE', update = update_node_values)
	g_mdsft_zsrcsel : bpy.props.EnumProperty(
		name = 'Z Source Selection', items = enumDepthSource,
		default = 'G_ZS_PIXEL', update = update_node_values)
	
	prim_depth : bpy.props.PointerProperty(type=PrimDepthSettings, name='Prim Depth Settings (gDPSetPrimDepth)', description='gDPSetPrimDepth')

	clip_ratio : bpy.props.IntProperty(default = 1,
		min = 1, max = 2**15 - 1, update = update_node_values)

	# cycle independent
	set_rendermode : bpy.props.BoolProperty(default = False, update = update_node_values)
	rendermode_advanced_enabled : bpy.props.BoolProperty(default = False, update = update_node_values)
	rendermode_preset_cycle_1 : bpy.props.EnumProperty(items = enumRenderModesCycle1,
		default = 'G_RM_AA_ZB_OPA_SURF', name = 'Render Mode Cycle 1', update = update_node_values)
	rendermode_preset_cycle_2 : bpy.props.EnumProperty(items = enumRenderModesCycle2,
		default = 'G_RM_AA_ZB_OPA_SURF2', name = 'Render Mode Cycle 2', update = update_node_values)
	aa_en : bpy.props.BoolProperty(update = update_node_values)
	z_cmp : bpy.props.BoolProperty(update = update_node_values)
	z_upd : bpy.props.BoolProperty(update = update_node_values)
	im_rd : bpy.props.BoolProperty(update = update_node_values)
	clr_on_cvg : bpy.props.BoolProperty(update = update_node_values)
	cvg_dst : bpy.props.EnumProperty(
		name = 'Coverage Destination', items = enumCoverage,
		update = update_node_values)
	zmode : bpy.props.EnumProperty(
		name = 'Z Mode', items = enumZMode, update = update_node_values)
	cvg_x_alpha : bpy.props.BoolProperty(update = update_node_values)
	alpha_cvg_sel : bpy.props.BoolProperty(update = update_node_values)
	force_bl : bpy.props.BoolProperty(update = update_node_values)

	# cycle dependent - (P * A + M - B) / (A + B)
	blend_p1 : bpy.props.EnumProperty(
		name = 'Color Source 1', items = enumBlendColor, update = update_node_values)
	blend_p2 : bpy.props.EnumProperty(
		name = 'Color Source 1', items = enumBlendColor, update = update_node_values)
	blend_m1 : bpy.props.EnumProperty(
		name = 'Color Source 2', items = enumBlendColor, update = update_node_values)
	blend_m2 : bpy.props.EnumProperty(
		name = 'Color Source 2', items = enumBlendColor, update = update_node_values)
	blend_a1 : bpy.props.EnumProperty(
		name = 'Alpha Source', items = enumBlendAlpha, update = update_node_values)
	blend_a2 : bpy.props.EnumProperty(
		name = 'Alpha Source', items = enumBlendAlpha, update = update_node_values)
	blend_b1 : bpy.props.EnumProperty(
		name = 'Alpha Mix', items = enumBlendMix, update = update_node_values)
	blend_b2 : bpy.props.EnumProperty(
		name = 'Alpha Mix', items = enumBlendMix, update = update_node_values)

class DefaultRDPSettingsPanel(bpy.types.Panel):
	bl_label = "RDP Default Settings"
	bl_idname = "WORLD_PT_RDP_Default_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "world"
	bl_options = {'HIDE_HEADER'}

	@classmethod
	def poll(cls, context):
		return context.scene.gameEditorMode == "SM64"

	def draw(self, context):
		world = context.scene.world
		layout = self.layout
		layout.box().label(text = 'RDP Default Settings')
		layout.label(text = "If a material setting is a same as a default " +\
			"setting, then it won't be set.")
		ui_geo_mode(world.rdp_defaults, world, layout, True)
		ui_upper_mode(world.rdp_defaults, world, layout, True)
		ui_lower_mode(world.rdp_defaults, world, layout, True)
		ui_other(world.rdp_defaults, world, layout, True)

### Node Categories ###
# Node categories are a python system for automatically
# extending the Add menu, toolbar panels and search operator.
# For more examples see release/scripts/startup/nodeitems_builtins.py

# all categories in a list
node_categories = [
	# identifier, label, items list
	F3DNodeCategory('CUSTOM', 'Custom', items = [
		NodeItem("GetAlphaFromColor",label="Get Alpha From Color", settings={}),
	]),
	F3DNodeCategory('FAST3D', "Fast3D", items=[
		# the node item can have additional settings,
		# which are applied to new nodes
		# NB: settings values are stored as string expressions,
		# for this reason they should be converted to strings using repr()
		NodeItem("Fast3D_A", label="A"),
		NodeItem("Fast3D_B", label="B"),
		NodeItem("Fast3D_C", label="C"),
		NodeItem("Fast3D_D", label="D"),
		NodeItem("Fast3D_A_alpha", label="A Alpha"),
		NodeItem("Fast3D_B_alpha", label="B Alpha"),
		NodeItem("Fast3D_C_alpha", label="C Alpha"),
		NodeItem("Fast3D_D_alpha", label="D Alpha"),
		'''
		NodeItem("Test_NodeType", label="Full", settings={
			"my_string_prop": repr("consectetur adipisicing elit"),
			"my_float_prop": repr(2.0),
		}),
		NodeItem("Fast3D_NodeType", label="Shaded Texture", settings={
			"inA": repr('1'), "inB": repr('8'), "inC": repr('4'),
			"inD": repr('7'), "inA_alpha": repr('7'), "inB_alpha": repr('7'),
			"inC_alpha": repr('7'), "inD_alpha": repr('5'),
		}),
		NodeItem("Fast3DSplitter_NodeType", label="Splitter", settings={
		}),
		'''
	]),
]

def getOptimalFormat(tex, useLargeTextures):
	texFormat = 'RGBA16'
	if useLargeTextures:
		return 'RGBA16'
	if bpy.context.scene.ignoreTextureRestrictions or \
		tex.size[0] * tex.size[1] > 8192: # Image too big
		return 'RGBA32'

	isGreyscale = True
	hasAlpha4bit = False
	hasAlpha1bit = False
	pixelValues = []

	# N64 is -Y, Blender is +Y
	for j in reversed(range(tex.size[1])):
		for i in range(tex.size[0]):
			color = [1,1,1,1]
			for field in range(tex.channels):
				color[field] = tex.pixels[
					(j * tex.size[0] + i) * tex.channels + field]
			if not (color[0] == color[1] and color[1] == color[2]):
				isGreyscale = False
			if color[3] < 0.9375:
				hasAlpha4bit = True
			if color[3] < 0.5:
				hasAlpha1bit = True
			pixelColor = getRGBA16Tuple(color)
			if pixelColor not in pixelValues:
				pixelValues.append(pixelColor)

	if isGreyscale:
		if tex.size[0] * tex.size[1] > 4096:
			if not hasAlpha1bit:
				texFormat = 'I4'
			else:
				texFormat = 'IA4'
		else:
			if not hasAlpha4bit:
				texFormat = 'I8'
			else:
				texFormat = 'IA8'
	else:
		if len(pixelValues) <= 16:
			texFormat = 'CI4'
		elif len(pixelValues) <= 256:
			texFormat = 'CI8'
		else:
			texFormat = 'RGBA16'

	return texFormat

def getCurrentPresetDir():
	return "f3d/" + bpy.context.scene.gameEditorMode.lower()

# modules/bpy_types.py -> Menu
class MATERIAL_MT_f3d_presets(Menu):
	bl_label = "F3D Material Presets"
	preset_operator = "script.execute_preset"

	def draw(self, _context):
		"""
		Define these on the subclass:
		- preset_operator (string)
		- preset_subdir (string)

		Optionally:
		- preset_add_operator (string)
		- preset_extensions (set of strings)
		- preset_operator_defaults (dict of keyword args)
		"""
		import bpy
		ext_valid = getattr(self, "preset_extensions", {".py", ".xml"})
		props_default = getattr(self, "preset_operator_defaults", None)
		add_operator = getattr(self, "preset_add_operator", None)
		presetDir = getCurrentPresetDir()
		paths = (bpy.utils.preset_paths(presetDir) if \
			not bpy.context.scene.f3dUserPresetsOnly else []) + \
			bpy.utils.preset_paths("f3d/user")
		self.path_menu(
			paths,
			self.preset_operator,
			props_default=props_default,
			filter_ext=lambda ext: ext.lower() in ext_valid,
			add_operator=add_operator,
		)

# https://docs.blender.org/api/current/bpy.ops.script.html
#class F3DExecutePreset(ExecutePreset):
#	"""Execute a preset"""
#	bl_idname = "script.f3d_execute_preset"
#	bl_label = "Execute an F3D Preset"
#
#	filepath: StringProperty(
#		subtype='FILE_PATH',
#		options={'SKIP_SAVE'},
#	)
#	menu_idname: StringProperty(
#		name="Menu ID Name",
#		description="ID name of the menu this was called from",
#		options={'SKIP_SAVE'},
#	)
#
#	def post_cb(self, context):
#		presetName = bpy.path.display_name(basename(filepath))
#		for material in bpy.data.materials:
#			if material.is_f3d and material.mat_ver > 3 and \
#				material.f3d_mat.preset_name == presetName:


class AddPresetF3D(AddPresetBase, Operator):
	'''Add an F3D Material Preset'''
	bl_idname = "material.f3d_preset_add"
	bl_label = "Add F3D Material Preset"
	preset_menu = "MATERIAL_MT_f3d_presets"

	# variable used for all preset values
	# do NOT set "mat" in this operator, even in a for loop! it overrides this value
	preset_defines = [
		"f3d_mat = bpy.context.material.f3d_mat"
	]

	# properties to store in the preset
	preset_values = [
		"f3d_mat",
	]

	# where to store the preset
	preset_subdir = "f3d/user"

	defaults = [
		"Custom",
		#"Shaded Texture",
	]

	ignore_props = [
		"f3d_mat.tex0.tex",
		"f3d_mat.tex0.tex_format",
		"f3d_mat.tex0.ci_format",
		"f3d_mat.tex0.use_tex_reference",
		"f3d_mat.tex0.tex_reference",
		"f3d_mat.tex0.tex_reference_size",
		"f3d_mat.tex0.pal_reference",
		"f3d_mat.tex0.pal_reference_size",
		"f3d_mat.tex0.S",
		"f3d_mat.tex0.T",
		"f3d_mat.tex0.menu",
		"f3d_mat.tex0.autoprop",
		"f3d_mat.tex0.save_large_texture",
		"f3d_mat.tex0.tile_scroll",
		"f3d_mat.tex0.tile_scroll.s",
		"f3d_mat.tex0.tile_scroll.t",
		"f3d_mat.tex0.tile_scroll.interval",
		"f3d_mat.tex1.tex",
		"f3d_mat.tex1.tex_format",
		"f3d_mat.tex1.ci_format",
		"f3d_mat.tex1.use_tex_reference",
		"f3d_mat.tex1.tex_reference",
		"f3d_mat.tex1.tex_reference_size",
		"f3d_mat.tex1.pal_reference",
		"f3d_mat.tex1.pal_reference_size",
		"f3d_mat.tex1.S",
		"f3d_mat.tex1.T",
		"f3d_mat.tex1.menu",
		"f3d_mat.tex1.autoprop",
		"f3d_mat.tex1.save_large_texture",
		"f3d_mat.tex1.tile_scroll",
		"f3d_mat.tex1.tile_scroll.s",
		"f3d_mat.tex1.tile_scroll.t",
		"f3d_mat.tex1.tile_scroll.interval",
		"f3d_mat.tex_scale",
		"f3d_mat.scale_autoprop",
		"f3d_mat.uv_basis",
		"f3d_mat.UVanim0",
		"f3d_mat.UVanim1",
		"f3d_mat.menu_procAnim",
		"f3d_mat.menu_geo",
		"f3d_mat.menu_upper",
		"f3d_mat.menu_lower",
		"f3d_mat.menu_other",
		"f3d_mat.menu_lower_render",
		"f3d_mat.f3d_update_flag",
		"f3d_mat.name",
		"f3d_mat.use_large_textures",
	]

	def execute(self, context):
		import os
		from bpy.utils import is_path_builtin

		if hasattr(self, "pre_cb"):
			self.pre_cb(context)

		preset_menu_class = getattr(bpy.types, self.preset_menu)

		is_xml = getattr(preset_menu_class, "preset_type", None) == 'XML'
		is_preset_add = not (self.remove_name or self.remove_active)

		if is_xml:
			ext = ".xml"
		else:
			ext = ".py"

		name = self.name.strip() if is_preset_add else self.name

		if is_preset_add:
			if not name:
				return {'FINISHED'}

			filename = self.as_filename(name)
			if filename in material_presets or filename == "custom":
				self.report({'WARNING'}, "Unable to delete/overwrite default presets.")
				return {'CANCELLED'}

			# Reset preset name
			wm = bpy.data.window_managers[0]
			if name == wm.preset_name:
				wm.preset_name = 'New Preset'

			filename = self.as_filename(name)
			context.material.f3d_mat.presetName = bpy.path.display_name(filename)

			target_path = os.path.join("presets", self.preset_subdir)
			target_path = bpy.utils.user_resource('SCRIPTS',
												  target_path,
												  create=True)

			if not target_path:
				self.report({'WARNING'}, "Failed to create presets path")
				return {'CANCELLED'}

			filepath = os.path.join(target_path, filename) + ext

			if hasattr(self, "add"):
				self.add(context, filepath)
			else:
				print("Writing Preset: %r" % filepath)

				if is_xml:
					import rna_xml
					rna_xml.xml_file_write(context,
										   filepath,
										   preset_menu_class.preset_xml_map)
				else:

					def rna_recursive_attr_expand(value, rna_path_step, level):
						if rna_path_step in self.ignore_props:
							#print("Ignoring: " + str(rna_path_step))
							return
						#else:
						#	print("Processing: " + str(rna_path_step))
						if isinstance(value, bpy.types.PropertyGroup):
							for sub_value_attr in value.bl_rna.properties.keys():
								if sub_value_attr == "rna_type":
									continue
								sub_value = getattr(value, sub_value_attr)
								rna_recursive_attr_expand(sub_value, "%s.%s" % (rna_path_step, sub_value_attr), level)
						elif type(value).__name__ == "bpy_prop_collection_idprop":  # could use nicer method
							file_preset.write("%s.clear()\n" % rna_path_step)
							for sub_value in value:
								file_preset.write("item_sub_%d = %s.add()\n" % (level, rna_path_step))
								rna_recursive_attr_expand(sub_value, "item_sub_%d" % level, level + 1)
						else:
							# convert thin wrapped sequences
							# to simple lists to repr()
							try:
								value = value[:]
							except:
								pass

							file_preset.write("%s = %r\n" % (rna_path_step, value))

					file_preset = open(filepath, 'w', encoding="utf-8")
					file_preset.write("import bpy\n")

					if hasattr(self, "preset_defines"):
						for rna_path in self.preset_defines:
							exec(rna_path)
							file_preset.write("%s\n" % rna_path)
						file_preset.write("\n")
					file_preset.write("bpy.context.material.f3d_update_flag = True\n")

					for rna_path in self.preset_values:
						value = eval(rna_path)
						rna_recursive_attr_expand(value, rna_path, 1)

					file_preset.write("bpy.context.material.f3d_update_flag = False\n")
					file_preset.write("f3d_mat.use_default_lighting = f3d_mat.use_default_lighting # Force nodes update\n")
					file_preset.close()

			presetName = bpy.path.display_name(filename)
			preset_menu_class.bl_label = presetName

			for otherMat in bpy.data.materials:
				if otherMat.f3d_mat.presetName == presetName and otherMat != context.material:
					update_preset_manual_v4(otherMat, filename)
			context.material.f3d_mat.presetName = bpy.path.display_name(filename)

		else:
			if self.remove_active:
				name = preset_menu_class.bl_label
				filename = self.as_filename(name)
				presetName = bpy.path.display_name(filename)

				if filename in material_presets or filename == "custom":
					self.report({'WARNING'}, "Unable to delete/overwrite default presets.")
					return {'CANCELLED'}

			# fairly sloppy but convenient.
			filepath = bpy.utils.preset_find(name,
											 self.preset_subdir,
											 ext=ext)

			if not filepath:
				filepath = bpy.utils.preset_find(name,
												 self.preset_subdir,
												 display_name=True,
												 ext=ext)

			if not filepath:
				return {'CANCELLED'}

			# Do not remove bundled presets
			if is_path_builtin(filepath):
				self.report({'WARNING'}, "Unable to remove default presets")
				return {'CANCELLED'}

			try:
				if hasattr(self, "remove"):
					self.remove(context, filepath)
				else:
					os.remove(filepath)
			except Exception as e:
				self.report({'ERROR'}, "Unable to remove preset: %r" % e)
				import traceback
				traceback.print_exc()
				return {'CANCELLED'}

			# XXX, stupid!
			preset_menu_class.bl_label = "Presets"
			for material in bpy.data.materials:
				if material.f3d_mat.presetName == presetName:
					material.f3d_mat.presetName = "Custom"
			#context.material.f3d_mat.presetName = "Custom"

		if hasattr(self, "post_cb"):
			self.post_cb(context)

		return {'FINISHED'}

def convertToNewMat(material, oldMat):
	#mat_register_old()
	material.f3d_mat.presetName = oldMat.presetName

	material.f3d_mat.scale_autoprop = oldMat.scale_autoprop
	material.f3d_mat.uv_basis = oldMat.uv_basis

	# Combiners
	copyPropertyGroup(oldMat.combiner1, material.f3d_mat.combiner1)
	copyPropertyGroup(oldMat.combiner2, material.f3d_mat.combiner2)
	#material.f3d_mat.combiner1 = oldMat.combiner1
	#material.f3d_mat.combiner2 = oldMat.combiner2

	# Texture animation
	material.f3d_mat.menu_procAnim = oldMat.menu_procAnim
	copyPropertyGroup(oldMat.UVanim, material.f3d_mat.UVanim0)
	copyPropertyGroup(oldMat.UVanim_tex1, material.f3d_mat.UVanim1)

	# material textures
	material.f3d_mat.tex_scale = oldMat.tex_scale
	copyPropertyGroup(oldMat.tex0, material.f3d_mat.tex0)
	copyPropertyGroup(oldMat.tex1, material.f3d_mat.tex1)

	# Should Set?
	material.f3d_mat.set_prim = oldMat.set_prim
	material.f3d_mat.set_lights = oldMat.set_lights
	material.f3d_mat.set_env = oldMat.set_env
	material.f3d_mat.set_blend = oldMat.set_blend
	material.f3d_mat.set_key = oldMat.set_key
	material.f3d_mat.set_k0_5 = oldMat.set_k0_5
	material.f3d_mat.set_combiner = oldMat.set_combiner
	material.f3d_mat.use_default_lighting = oldMat.use_default_lighting

	# Colors
	nodes = oldMat.node_tree.nodes
	material.f3d_mat.blend_color = oldMat.blend_color
	if oldMat.mat_ver == 3:
		prim = nodes['Primitive Color Output'].inputs[0].default_value
		env = nodes['Environment Color Output'].inputs[0].default_value
	else:
		prim = nodes['Primitive Color'].outputs[0].default_value
		env = nodes['Environment Color'].outputs[0].default_value

	material.f3d_mat.blend_color = oldMat.blend_color
	material.f3d_mat.prim_color = prim
	material.f3d_mat.env_color = env
	material.f3d_mat.key_center = nodes['Chroma Key Center'].outputs[0].default_value

	# Chroma
	material.f3d_mat.key_scale = oldMat.key_scale
	material.f3d_mat.key_width = oldMat.key_width

	# Convert
	material.f3d_mat.k0 = oldMat.k0
	material.f3d_mat.k1 = oldMat.k1
	material.f3d_mat.k2 = oldMat.k2
	material.f3d_mat.k3 = oldMat.k3
	material.f3d_mat.k4 = oldMat.k4
	material.f3d_mat.k5 = oldMat.k5

	# Prim
	material.f3d_mat.prim_lod_frac = oldMat.prim_lod_frac
	material.f3d_mat.prim_lod_min = oldMat.prim_lod_min

	# lights
	material.f3d_mat.default_light_color = oldMat.default_light_color
	material.f3d_mat.ambient_light_color = oldMat.ambient_light_color
	material.f3d_mat.f3d_light1 = oldMat.f3d_light1
	material.f3d_mat.f3d_light2 = oldMat.f3d_light2
	material.f3d_mat.f3d_light3 = oldMat.f3d_light3
	material.f3d_mat.f3d_light4 = oldMat.f3d_light4
	material.f3d_mat.f3d_light5 = oldMat.f3d_light5
	material.f3d_mat.f3d_light6 = oldMat.f3d_light6
	material.f3d_mat.f3d_light7 = oldMat.f3d_light7

	# Fog Properties
	material.f3d_mat.fog_color = oldMat.fog_color
	material.f3d_mat.fog_position = oldMat.fog_position
	material.f3d_mat.set_fog = oldMat.set_fog
	material.f3d_mat.use_global_fog = oldMat.use_global_fog

	# geometry mode
	material.f3d_mat.menu_geo = oldMat.menu_geo
	material.f3d_mat.menu_upper = oldMat.menu_upper
	material.f3d_mat.menu_lower = oldMat.menu_lower
	material.f3d_mat.menu_other = oldMat.menu_other
	material.f3d_mat.menu_lower_render = oldMat.menu_lower_render
	copyPropertyGroup(oldMat.rdp_settings, material.f3d_mat.rdp_settings)

	#mat_unregister_old()

class F3DMaterialProperty(bpy.types.PropertyGroup):
	presetName : bpy.props.StringProperty(name = "Preset Name", default = "Custom")

	scale_autoprop : bpy.props.BoolProperty(name = 'Auto Set Scale', default = True, update = update_tex_values)
	uv_basis : bpy.props.EnumProperty(name = 'UV Basis', default = 'TEXEL0', items = enumTexUV, update = update_tex_values)

	# Combiners
	combiner1 : bpy.props.PointerProperty(type = CombinerProperty)
	combiner2 : bpy.props.PointerProperty(type = CombinerProperty)

	# Texture animation
	menu_procAnim : bpy.props.BoolProperty()
	UVanim0 : bpy.props.PointerProperty(type = ProcAnimVectorProperty)
	UVanim1 : bpy.props.PointerProperty(type = ProcAnimVectorProperty)

	# material textures
	tex_scale : bpy.props.FloatVectorProperty(min = 0, max = 1, size = 2, default = (1,1), step = 1, update = update_tex_values)
	tex0 : bpy.props.PointerProperty(type = TextureProperty)
	tex1 : bpy.props.PointerProperty(type = TextureProperty)

	# Should Set?

	set_prim : bpy.props.BoolProperty(default = True, update = update_node_values)
	set_lights : bpy.props.BoolProperty(default = True, update = update_node_values)
	set_env : bpy.props.BoolProperty(default = False, update = update_node_values)
	set_blend : bpy.props.BoolProperty(default = False, update = update_node_values)
	set_key : bpy.props.BoolProperty(default = True, update = update_node_values)
	set_k0_5 : bpy.props.BoolProperty(default = True, update = update_node_values)
	set_combiner : bpy.props.BoolProperty(default = True, update = update_node_values)
	use_default_lighting : bpy.props.BoolProperty(default = True, update = update_node_values_without_preset)

	# Blend Color
	blend_color : bpy.props.FloatVectorProperty(
		name = 'Blend Color', subtype='COLOR', size = 4, min = 0, max = 1, default = (0,0,0,1))
	prim_color : bpy.props.FloatVectorProperty(
		name = 'Primitive Color', subtype='COLOR', size = 4, min = 0, max = 1, default = (1,1,1,1),
		update = update_node_values_without_preset)
	env_color : bpy.props.FloatVectorProperty(
		name = 'Environment Color', subtype='COLOR', size = 4, min = 0, max = 1, default = (1,1,1,1),
		update = update_node_values_without_preset)
	key_center : bpy.props.FloatVectorProperty(
		name = 'Key Center', subtype='COLOR', size = 4, min = 0, max = 1, default = (1,1,1,1),
		update = update_node_values_without_preset)

	# Chroma
	key_scale : bpy.props.FloatVectorProperty(name = 'Key Scale', min = 0, max = 1, step = 1, update = update_node_values)
	key_width : bpy.props.FloatVectorProperty(name = 'Key Width', min = 0, max = 16, update = update_node_values)

	# Convert
	k0 : bpy.props.FloatProperty(min = -1, max = 1, default = 175/255, step = 1, update = update_node_values)
	k1 : bpy.props.FloatProperty(min = -1, max = 1, default = -43/255, step = 1, update = update_node_values)
	k2 : bpy.props.FloatProperty(min = -1, max = 1, default = -89/255, step = 1, update = update_node_values)
	k3 : bpy.props.FloatProperty(min = -1, max = 1, default = 222/255, step = 1, update = update_node_values)
	k4 : bpy.props.FloatProperty(min = -1, max = 1, default = 114/255, step = 1, update = update_node_values)
	k5 : bpy.props.FloatProperty(min = -1, max = 1, default = 42/255, step = 1, update = update_node_values)

	# Prim
	prim_lod_frac : bpy.props.FloatProperty(name = 'Prim LOD Frac', min = 0, max = 1, step = 1, update = update_node_values)
	prim_lod_min : bpy.props.FloatProperty(name = 'Min LOD Ratio', min = 0, max = 1, step = 1, update = update_node_values)

	# lights
	default_light_color : bpy.props.FloatVectorProperty(
		name = 'Default Light Color', subtype = 'COLOR', size = 4, min = 0, max = 1, default = (1,1,1,1),
		update = update_node_values_without_preset)
	ambient_light_color : bpy.props.FloatVectorProperty(
		name = 'Ambient Light Color', subtype = 'COLOR', size = 4, min = 0, max = 1, default = (0.5,0.5,0.5,1),
		update = update_node_values_without_preset)
	f3d_light1 : bpy.props.PointerProperty(type = bpy.types.Light, update = F3DOrganizeLights)
	f3d_light2 : bpy.props.PointerProperty(type = bpy.types.Light, update = F3DOrganizeLights)
	f3d_light3 : bpy.props.PointerProperty(type = bpy.types.Light, update = F3DOrganizeLights)
	f3d_light4 : bpy.props.PointerProperty(type = bpy.types.Light, update = F3DOrganizeLights)
	f3d_light5 : bpy.props.PointerProperty(type = bpy.types.Light, update = F3DOrganizeLights)
	f3d_light6 : bpy.props.PointerProperty(type = bpy.types.Light, update = F3DOrganizeLights)
	f3d_light7 : bpy.props.PointerProperty(type = bpy.types.Light, update = F3DOrganizeLights)

	# Fog Properties
	fog_color : bpy.props.FloatVectorProperty(
		name = 'Fog Color', subtype='COLOR', size = 4, min = 0, max = 1, default = (0,0,0,1))
	fog_position : bpy.props.IntVectorProperty(
		name = 'Fog Range', size = 2, min = 0, max = 1000, default = (970,1000))
	set_fog : bpy.props.BoolProperty()
	use_global_fog : bpy.props.BoolProperty(default = False)

	# geometry mode
	menu_geo : bpy.props.BoolProperty()
	menu_upper : bpy.props.BoolProperty()
	menu_lower : bpy.props.BoolProperty()
	menu_other : bpy.props.BoolProperty()
	menu_lower_render : bpy.props.BoolProperty()
	rdp_settings : bpy.props.PointerProperty(type = RDPSettings)

	draw_layer : bpy.props.PointerProperty(type = DrawLayerProperty)
	use_large_textures : bpy.props.BoolProperty(name = "Large Texture Mode")

class UnlinkF3DImage0(bpy.types.Operator):
	bl_idname = 'image.tex0_unlink'
	bl_label = "Unlink F3D Image"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context.material.mat_ver > 3:
			context.material.f3d_mat.tex0.tex = None
		else:
			context.material.tex0.tex = None
		return {'FINISHED'} # must return a set

class UnlinkF3DImage1(bpy.types.Operator):
	bl_idname = 'image.tex1_unlink'
	bl_label = "Unlink F3D Image"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context.material.mat_ver > 3:
			context.material.f3d_mat.tex1.tex = None
		else:
			context.material.tex1.tex = None
		return {'FINISHED'} # must return a set

class UpdateF3DNodes(bpy.types.Operator):
	bl_idname = 'material.update_f3d_nodes'
	bl_label = "Update F3D Nodes"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		if context is None or not hasattr(context, "material") or context.material is None:
			self.report({"ERROR"}, "Material not found in context.")
			return {"CANCELLED"}
		if not context.material.is_f3d:
			self.report({"ERROR"}, "Material is not F3D.")
			return {"CANCELLED"}
		material = context.material

		material.f3d_update_flag = True
		update_node_values_of_material(material, context)
		if material.mat_ver > 3:
			material.f3d_mat.presetName = "Custom"
		else:
			material.f3d_preset = 'Custom'
		material.f3d_update_flag = False
		return {'FINISHED'} # must return a set

mat_classes = (
	F3DNodeA,
	F3DNodeB,
	F3DNodeC,
	F3DNodeD,
	F3DNodeA_alpha,
	F3DNodeB_alpha,
	F3DNodeC_alpha,
	F3DNodeD_alpha,
	UnlinkF3DImage0,
	UnlinkF3DImage1,
	DrawLayerProperty,
	MATERIAL_MT_f3d_presets,
	AddPresetF3D,
	F3DPanel,
	CreateFast3DMaterial,
	GetAlphaFromColor,
	TextureFieldProperty,
	SetTileSizeScrollProperty,
	TextureProperty,
	CombinerProperty,
	ProceduralAnimProperty,
	ProcAnimVectorProperty,
	PrimDepthSettings,
	RDPSettings,
	DefaultRDPSettingsPanel,
	F3DMaterialProperty,
	ReloadDefaultF3DPresets,
	UpdateF3DNodes,
)

def mat_unregister_old():
	del bpy.types.Material.f3d_preset

	del bpy.types.Material.scale_autoprop
	del bpy.types.Material.uv_basis

	# Combiners
	del bpy.types.Material.presetName

	del bpy.types.Material.combiner1
	del bpy.types.Material.combiner2

	# Texture animation
	del bpy.types.Material.menu_procAnim
	del bpy.types.Material.UVanim_tex1
	del bpy.types.Material.UVanim

	# material textures
	del bpy.types.Material.tex_scale
	del bpy.types.Material.tex0
	del bpy.types.Material.tex1

	# Should Set?
	del bpy.types.Material.set_prim
	del bpy.types.Material.set_lights
	del bpy.types.Material.set_env
	del bpy.types.Material.set_blend
	del bpy.types.Material.set_key
	del bpy.types.Material.set_k0_5
	del bpy.types.Material.set_combiner
	del bpy.types.Material.use_default_lighting

	# Blend Color
	del bpy.types.Material.blend_color

	# Chroma
	del bpy.types.Material.key_scale
	del bpy.types.Material.key_width

	# Convert
	del bpy.types.Material.k0
	del bpy.types.Material.k1
	del bpy.types.Material.k2
	del bpy.types.Material.k3
	del bpy.types.Material.k4
	del bpy.types.Material.k5

	# Prim
	del bpy.types.Material.prim_lod_frac
	del bpy.types.Material.prim_lod_min

	# lights
	del bpy.types.Material.default_light_color
	del bpy.types.Material.ambient_light_color
	del bpy.types.Material.f3d_light1
	del bpy.types.Material.f3d_light2
	del bpy.types.Material.f3d_light3
	del bpy.types.Material.f3d_light4
	del bpy.types.Material.f3d_light5
	del bpy.types.Material.f3d_light6
	del bpy.types.Material.f3d_light7

	# Fog Properties
	del bpy.types.Material.fog_color
	del bpy.types.Material.fog_position
	del bpy.types.Material.set_fog
	del bpy.types.Material.use_global_fog

	# geometry mode
	del bpy.types.Material.menu_geo
	del bpy.types.Material.menu_upper
	del bpy.types.Material.menu_lower
	del bpy.types.Material.menu_other
	del bpy.types.Material.menu_lower_render
	del bpy.types.Material.rdp_settings

def mat_register_old():
	bpy.types.Material.f3d_preset = bpy.props.EnumProperty(name = 'F3D Preset',
		items = enumMaterialPresets, default = 'Custom',
		update = update_preset)

	bpy.types.Material.scale_autoprop = bpy.props.BoolProperty(
		name = 'Auto Set Scale', default = True,
		update = update_node_values_without_preset)
	bpy.types.Material.uv_basis = bpy.props.EnumProperty(
		name = 'UV Basis', default = 'TEXEL0',
		update = update_tex_values, items = enumTexUV)

	# Combiners
	bpy.types.Material.presetName = bpy.props.StringProperty(name = "Preset Name", default = "Custom")

	bpy.types.Material.combiner1 = bpy.props.PointerProperty(type = \
		CombinerProperty)
	bpy.types.Material.combiner2 = bpy.props.PointerProperty(type = \
		CombinerProperty)

	# Texture animation
	bpy.types.Material.menu_procAnim = bpy.props.BoolProperty()
	#bpy.types.Material.positionAnim = bpy.props.PointerProperty(
	#	type = ProcAnimVectorProperty)
	#bpy.types.Material.UVanim_tex0 = bpy.props.PointerProperty(
	#	type = ProcAnimVectorProperty)
	bpy.types.Material.UVanim_tex1 = bpy.props.PointerProperty(
		type = ProcAnimVectorProperty)
	#bpy.types.Material.colorAnim = bpy.props.PointerProperty(
	#	type = ProcAnimVectorProperty)

	bpy.types.Material.UVanim = bpy.props.PointerProperty(
		type = ProcAnimVectorProperty)

	# material textures
	bpy.types.Material.tex_scale = bpy.props.FloatVectorProperty(
		min = 0, max = 1, size = 2, default = (1,1), step = 1,
		update = update_tex_values)
	bpy.types.Material.tex0 = bpy.props.PointerProperty(type = TextureProperty)
	bpy.types.Material.tex1 = bpy.props.PointerProperty(type = TextureProperty)

	# Should Set?
	bpy.types.Material.set_prim = bpy.props.BoolProperty(default = True,
		update = update_node_values)
	bpy.types.Material.set_lights = bpy.props.BoolProperty(default = True,
		update = update_node_values)
	bpy.types.Material.set_env = bpy.props.BoolProperty(default = False,
		update = update_node_values)
	bpy.types.Material.set_blend = bpy.props.BoolProperty(default = False,
		update = update_node_values)
	bpy.types.Material.set_key = bpy.props.BoolProperty(default = True,
		update = update_node_values)
	bpy.types.Material.set_k0_5 = bpy.props.BoolProperty(default = True,
		update = update_node_values)
	bpy.types.Material.set_combiner = bpy.props.BoolProperty(default = True,
		update = update_node_values)
	bpy.types.Material.use_default_lighting = bpy.props.BoolProperty(default = True,
		update = update_node_values_without_preset)

	# Blend Color
	bpy.types.Material.blend_color = bpy.props.FloatVectorProperty(
		name = 'Blend Color', subtype='COLOR', size = 4, min = 0, max = 1, default = (0,0,0,1))

	# Chroma
	bpy.types.Material.key_scale = bpy.props.FloatVectorProperty(
		name = 'Key Scale', min = 0, max = 1, step = 1,
		update = update_node_values)
	bpy.types.Material.key_width = bpy.props.FloatVectorProperty(
		name = 'Key Width', min = 0, max = 16,
		update = update_node_values)

	# Convert
	bpy.types.Material.k0 = bpy.props.FloatProperty(min = -1, max = 1,
		default = 175/255, step = 1, update = update_node_values)
	bpy.types.Material.k1 = bpy.props.FloatProperty(min = -1, max = 1,
		default = -43/255, step = 1, update = update_node_values)
	bpy.types.Material.k2 = bpy.props.FloatProperty(min = -1, max = 1,
		default = -89/255, step = 1, update = update_node_values)
	bpy.types.Material.k3 = bpy.props.FloatProperty(min = -1, max = 1,
		default = 222/255, step = 1, update = update_node_values)
	bpy.types.Material.k4 = bpy.props.FloatProperty(min = -1, max = 1,
		default = 114/255, step = 1, update = update_node_values)
	bpy.types.Material.k5 = bpy.props.FloatProperty(min = -1, max = 1,
		default = 42/255, step = 1, update = update_node_values)

	# Prim
	bpy.types.Material.prim_lod_frac = bpy.props.FloatProperty(
		name = 'Prim LOD Frac', min = 0, max = 1, step = 1,
		update = update_node_values)
	bpy.types.Material.prim_lod_min = bpy.props.FloatProperty(
		name = 'Min LOD Ratio', min = 0, max = 1, step = 1,
		update = update_node_values)

	# lights
	bpy.types.Material.default_light_color = bpy.props.FloatVectorProperty(
		name = 'Default Light Color', subtype = 'COLOR', size = 4, min = 0, max = 1, default = (1,1,1,1),
		update = update_node_values_without_preset)
	bpy.types.Material.ambient_light_color = bpy.props.FloatVectorProperty(
		name = 'Ambient Light Color', subtype = 'COLOR', size = 4, min = 0, max = 1, default = (0.5,0.5,0.5,1),
		update = update_node_values_without_preset)
	bpy.types.Material.f3d_light1 = bpy.props.PointerProperty(
		type = bpy.types.Light, update = F3DOrganizeLights)
	bpy.types.Material.f3d_light2 = bpy.props.PointerProperty(
		type = bpy.types.Light, update = F3DOrganizeLights)
	bpy.types.Material.f3d_light3 = bpy.props.PointerProperty(
		type = bpy.types.Light, update = F3DOrganizeLights)
	bpy.types.Material.f3d_light4 = bpy.props.PointerProperty(
		type = bpy.types.Light, update = F3DOrganizeLights)
	bpy.types.Material.f3d_light5 = bpy.props.PointerProperty(
		type = bpy.types.Light, update = F3DOrganizeLights)
	bpy.types.Material.f3d_light6 = bpy.props.PointerProperty(
		type = bpy.types.Light, update = F3DOrganizeLights)
	bpy.types.Material.f3d_light7 = bpy.props.PointerProperty(
		type = bpy.types.Light, update = F3DOrganizeLights)

	# Fog Properties
	bpy.types.Material.fog_color = bpy.props.FloatVectorProperty(
		name = 'Fog Color', subtype='COLOR', size = 4, min = 0, max = 1, default = (0,0,0,1))
	bpy.types.Material.fog_position = bpy.props.IntVectorProperty(
		name = 'Fog Range', size = 2, min = 0, max = 1000, default = (970,1000))
	bpy.types.Material.set_fog = bpy.props.BoolProperty()
	bpy.types.Material.use_global_fog = bpy.props.BoolProperty(default = True)

	# geometry mode
	bpy.types.Material.menu_geo = bpy.props.BoolProperty()
	bpy.types.Material.menu_upper = bpy.props.BoolProperty()
	bpy.types.Material.menu_lower = bpy.props.BoolProperty()
	bpy.types.Material.menu_other = bpy.props.BoolProperty()
	bpy.types.Material.menu_lower_render = bpy.props.BoolProperty()
	bpy.types.Material.rdp_settings = bpy.props.PointerProperty(
		type = RDPSettings)

def findF3DPresetPath(filename):
	presetPath = bpy.utils.user_resource('SCRIPTS',
		os.path.join("presets", "f3d"), create=True)
	for subdir in os.listdir(presetPath):
		subPath = os.path.join(presetPath, subdir)
		if os.path.isdir(subPath):
			for preset in os.listdir(subPath):
				if preset[:-3] == filename:
					return os.path.join(subPath, filename) + ".py"
	raise PluginError("Preset " + str(filename) + " not found.")

def getF3DPresetPath(filename, subdir):
	presetPath = bpy.utils.user_resource('SCRIPTS',
		os.path.join("presets", subdir), create=True)
	return os.path.join(presetPath, filename) + ".py"

def savePresets():
	for subdir, presets in material_presets.items():
		for filename, preset in presets.items():
			filepath = getF3DPresetPath(filename, 'f3d/' + subdir)
			file_preset = open(filepath, 'w', encoding="utf-8")
			file_preset.write(preset)
			file_preset.close()

def mat_register():
	#bpy.app.handlers.load_post.append(loadTimer)
	for cls in mat_classes:
		register_class(cls)

	#presetDict = addMaterialPresets()
	#for presetName, presetItem in presetDict.items():
	#	enumMaterialPresets.append((presetName, presetName, presetName))
	#	materialPresetDict[presetName] = presetItem

	savePresets()

	nodeitems_utils.register_node_categories('CUSTOM_NODES', node_categories)

	bpy.types.Scene.f3d_type = bpy.props.EnumProperty(
		name = 'F3D Microcode', items = enumF3D, default = 'F3D')
	bpy.types.Scene.isHWv1 = bpy.props.BoolProperty(name = 'Is Hardware v1?')

	# RDP Defaults
	bpy.types.World.rdp_defaults = bpy.props.PointerProperty(
		type = RDPSettings)
	bpy.types.World.menu_geo = bpy.props.BoolProperty()
	bpy.types.World.menu_upper = bpy.props.BoolProperty()
	bpy.types.World.menu_lower = bpy.props.BoolProperty()
	bpy.types.World.menu_other = bpy.props.BoolProperty()
	bpy.types.World.menu_layers = bpy.props.BoolProperty()

	mat_register_old()
	bpy.types.Material.is_f3d = bpy.props.BoolProperty()
	bpy.types.Material.mat_ver = bpy.props.IntProperty(default = 1)
	bpy.types.Material.f3d_update_flag = bpy.props.BoolProperty()
	bpy.types.Material.f3d_mat = bpy.props.PointerProperty(type = F3DMaterialProperty)
	bpy.types.Material.menu_tab = bpy.props.EnumProperty(items = enumF3DMenu)

	bpy.types.Scene.f3dUserPresetsOnly = bpy.props.BoolProperty(name = "User Presets Only")
	bpy.types.Scene.f3d_simple = bpy.props.BoolProperty(name = "Display Simple", default = True)

	bpy.types.Object.use_f3d_culling = bpy.props.BoolProperty(
		name = 'Enable Culling (Applies to F3DEX and up)', default = True)
	bpy.types.Object.ignore_render = bpy.props.BoolProperty(
		name = 'Ignore Render')
	bpy.types.Object.ignore_collision = bpy.props.BoolProperty(
		name = 'Ignore Collision')
	bpy.types.Object.f3d_lod_z = bpy.props.IntProperty(
		name = "F3D LOD Z", min = 1, default = 10)
	bpy.types.Object.f3d_lod_always_render_farthest = bpy.props.BoolProperty(name = "Always Render Farthest LOD")

def mat_unregister():
	del bpy.types.Material.menu_tab
	del bpy.types.Material.f3d_mat
	del bpy.types.Material.is_f3d
	del bpy.types.Material.mat_ver
	del bpy.types.Material.f3d_update_flag
	del bpy.types.Scene.f3d_simple
	del bpy.types.Object.ignore_render
	del bpy.types.Object.ignore_collision
	del bpy.types.Object.use_f3d_culling
	del bpy.types.Scene.f3dUserPresetsOnly
	del bpy.types.Object.f3d_lod_z
	del bpy.types.Object.f3d_lod_always_render_farthest
	nodeitems_utils.unregister_node_categories('CUSTOM_NODES')
	for cls in reversed(mat_classes):
		unregister_class(cls)

#from .f3d_material import *

# Presets
sm64_unlit_texture = F3DMaterialSettings()
sm64_unlit_texture.color_combiner = tuple(S_UNLIT_TEX)
sm64_unlit_texture.set_env = False

sm64_unlit_texture_cutout = F3DMaterialSettings()
sm64_unlit_texture_cutout.color_combiner = tuple(S_UNLIT_TEX_CUTOUT)
sm64_unlit_texture_cutout.set_env = False
sm64_unlit_texture_cutout.g_cull_back = False
sm64_unlit_texture_cutout.blend_method = "CLIP"

sm64_shaded_texture = F3DMaterialSettings()
sm64_shaded_texture.color_combiner = tuple(S_SHADED_TEX)
sm64_shaded_texture.set_env = False

sm64_shaded_solid = F3DMaterialSettings()
sm64_shaded_solid.color_combiner = tuple(S_SHADED_SOLID)
sm64_shaded_solid.set_env = False

sm64_shaded_texture_cutout = F3DMaterialSettings()
sm64_shaded_texture_cutout.color_combiner = tuple(S_SHADED_TEX_CUTOUT)
sm64_shaded_texture_cutout.set_env = False
sm64_shaded_texture_cutout.g_cull_back = False
sm64_shaded_texture_cutout.blend_method = "CLIP"

sm64_unlit_env_map = F3DMaterialSettings()
sm64_unlit_env_map.color_combiner = tuple(S_UNLIT_TEX)
sm64_unlit_env_map.g_tex_gen = True
sm64_unlit_env_map.set_env = False

sm64_decal = F3DMaterialSettings()
sm64_decal.color_combiner = tuple(S_UNLIT_DECAL_ON_SHADED_SOLID)
sm64_decal.set_env = False

sm64_vert_colored_tex = F3DMaterialSettings()
sm64_vert_colored_tex.color_combiner = tuple(S_VERTEX_COLORED_TEX)
sm64_vert_colored_tex.g_lighting = False
sm64_vert_colored_tex.set_env = False

sm64_vert_colored_tex_no_vert_alpha = F3DMaterialSettings()
sm64_vert_colored_tex_no_vert_alpha.color_combiner = tuple(S_VERTEX_COLORED_TEX_NO_VERT_ALPHA)
sm64_vert_colored_tex_no_vert_alpha.g_lighting = False
sm64_vert_colored_tex_no_vert_alpha.set_env = False

sm64_vert_colored_tex_transparent = F3DMaterialSettings()
sm64_vert_colored_tex_transparent.color_combiner = tuple(S_VERTEX_COLORED_TEX_TRANSPARENT)
sm64_vert_colored_tex_transparent.g_lighting = False
sm64_vert_colored_tex_transparent.set_env = False
sm64_vert_colored_tex_transparent.blend_method = "BLEND"

sm64_shaded_noise = F3DMaterialSettings()
sm64_shaded_noise.color_combiner = tuple(S_SHADED_NOISE)
sm64_shaded_noise.set_env = False

sm64_prim_transparent_shade = F3DMaterialSettings()
sm64_prim_transparent_shade.color_combiner = tuple(S_PRIM_TRANSPARENT_SHADE)
sm64_prim_transparent_shade.set_env = False
sm64_prim_transparent_shade.g_cull_back = False
sm64_prim_transparent_shade.blend_method = "BLEND"

sm64_fog_shaded_texture = F3DMaterialSettings()
sm64_fog_shaded_texture.g_fog = True
sm64_fog_shaded_texture.color_combiner = tuple(S_FOG_SHADED_TEX)
sm64_fog_shaded_texture.set_env = False
sm64_fog_shaded_texture.set_fog = True
sm64_fog_shaded_texture.g_mdsft_cycletype = 'G_CYC_2CYCLE'
sm64_fog_shaded_texture.set_rendermode = True
sm64_fog_shaded_texture.rendermode_advanced_enabled = False
sm64_fog_shaded_texture.rendermode_preset_cycle_1 = 'G_RM_FOG_SHADE_A'
sm64_fog_shaded_texture.rendermode_preset_cycle_2 = 'G_RM_AA_ZB_OPA_SURF2'

sm64_fog_shaded_texture_cutout = copy.deepcopy(sm64_fog_shaded_texture)
sm64_fog_shaded_texture_cutout.color_combiner = \
	tuple(S_FOG_SHADED_TEX_CUTOUT)
sm64_fog_shaded_texture_cutout.rendermode_preset_cycle_2 = 'G_RM_AA_ZB_TEX_EDGE2'
sm64_fog_shaded_texture_cutout.g_cull_back = False
sm64_fog_shaded_texture_cutout.blend_method = "CLIP"

sm64_fog_shaded_texture_transparent = copy.deepcopy(sm64_fog_shaded_texture)
sm64_fog_shaded_texture_transparent.color_combiner = \
	tuple(S_FOG_PRIM_TRANSPARENT_SHADE)
sm64_fog_shaded_texture_transparent.rendermode_preset_cycle_2 = 'G_RM_AA_ZB_XLU_SURF2'
sm64_fog_shaded_texture_transparent.g_cull_back = False
sm64_fog_shaded_texture_transparent.blend_method = "BLEND"

# WARNING: Adding new presets will break any custom presets added afterward.

enumMaterialPresets = [
	('Custom', 'Custom', 'Custom'),
	('Unlit Texture', 'Unlit Texture', 'Unlit Texture'),
	('Unlit Texture Cutout', 'Unlit Texture Cutout', 'Unlit Texture Cutout'),
	('Shaded Solid', 'Shaded Solid', 'Shaded Solid'),
	('Decal On Shaded Solid', 'Decal On Shaded Solid', 'Decal On Shaded Solid'),
	('Shaded Texture', 'Shaded Texture', 'Shaded Texture'),
	('Shaded Texture Cutout', 'Shaded Texture Cutout', 'Shaded Texture Cutout'),
	('Shaded Texture Transparent', 'Shaded Texture Transparent (Prim Alpha)', 'Shaded Texture Transparent (Prim Alpha)'),
	('Vertex Colored Texture', 'Vertex Colored Texture', 'Vertex Colored Texture'),
	('Environment Mapped', 'Environment Mapped', 'Environment Mapped'),
	('Fog Shaded Texture', 'Fog Shaded Texture', 'Fog Shaded Texture'),
	('Fog Shaded Texture Cutout', 'Fog Shaded Texture Cutout', 'Fog Shaded Texture Cutout'),
	('Fog Shaded Texture Transparent', 'Fog Shaded Texture Transparent (Prim Alpha)', 'Fog Shaded Texture Transparent (Prim Alpha)'),
	('Vertex Colored Texture Transparent', 'Vertex Colored Texture Transparent', 'Vertex Colored Texture Transparent'),
	('Shaded Noise', 'Shaded Noise', 'Shaded Noise'),
	('Vertex Colored Texture (No Vertex Alpha)', 'Vertex Colored Texture (No Vertex Alpha)', 'Vertex Colored Texture (No Vertex Alpha)'),
]

materialPresetDict = {
	'Unlit Texture' : sm64_unlit_texture,
	'Unlit Texture Cutout' : sm64_unlit_texture_cutout,
	'Shaded Solid' : sm64_shaded_solid,
	'Shaded Texture' : sm64_shaded_texture,
	'Shaded Texture Cutout' : sm64_shaded_texture_cutout,
	'Shaded Texture Transparent' : sm64_prim_transparent_shade,
	'Environment Mapped' : sm64_unlit_env_map,
	'Decal On Shaded Solid' : sm64_decal,
	'Vertex Colored Texture' : sm64_vert_colored_tex,
	'Fog Shaded Texture' : sm64_fog_shaded_texture,
	'Fog Shaded Texture Cutout' : sm64_fog_shaded_texture_cutout,
	'Fog Shaded Texture Transparent' : sm64_fog_shaded_texture_transparent,
	'Vertex Colored Texture Transparent' : sm64_vert_colored_tex_transparent,
	'Shaded Noise' : sm64_shaded_noise,
	'Vertex Colored Texture (No Vertex Alpha)' : sm64_vert_colored_tex_no_vert_alpha,
}
