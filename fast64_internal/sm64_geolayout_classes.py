from .sm64_geolayout_constants import *
from .sm64_geolayout_utility import *
from .utility import *
from .sm64_constants import *
import struct

class Geolayout:
	def __init__(self, name):
		self.nodes = []
		self.name = toAlnum(name)
		# dict of Object : geolayout
		self.secondaryGeolayouts = {}

	def to_binary(self, segmentData):
		data = bytearray(0)
		for node in self.nodes:
			data += node.to_binary(segmentData)
		data += bytearray([GEO_END, 0x00, 0x00, 0x00])
		return data

	def to_c(self):
		data = 'const GeoLayout ' + self.name + '[] = {\n'
		for node in self.nodes:
			data += node.to_c(1)
		data += '\t' + 'GEO_END(),\n'
		data += '};\n'
		return data
	
	def to_c_def(self):
		return 'extern const GeoLayout ' + self.name + '[];\n'

	def toTextDump(self, segmentData):
		data = ''
		for node in self.nodes:
			data += node.toTextDump(1, segmentData)
		data += '01 00 00 00'
		return data
		
class TransformNode:
	def __init__(self, node):
		self.node = node
		self.children = []
		self.parent = None
	
	# Function commands usually effect the following command, so it is similar
	# to a parent child relationship.
	def to_binary(self, segmentData):
		if self.node is not None:
			data = self.node.to_binary(segmentData)
		else:
			data = bytearray(0)
		if len(self.children) > 0:
			if type(self.node) is DisplayListNode:
				raise ValueError("A DisplayListNode cannot have children.")
			elif type(self.node) is FunctionNode:
				raise ValueError("An FunctionNode cannot have children.")

			if data[0] in nodeGroupCmds:
				data.extend(bytearray([GEO_NODE_OPEN, 0x00, 0x00, 0x00]))
			for child in self.children:
				data.extend(child.to_binary(segmentData))
			if data[0] in nodeGroupCmds:
				data.extend(bytearray([GEO_NODE_CLOSE, 0x00, 0x00, 0x00]))
		elif type(self.node) is SwitchNode:
			raise ValueError("A switch bone must have at least one child bone.")
		return data

	def to_c(self, depth):
		if self.node is not None:
			data = depth * '\t' + self.node.to_c() + '\n'
		else:
			data = ''
		if len(self.children) > 0:
			if type(self.node) in nodeGroupClasses:
				data += depth * '\t' + 'GEO_OPEN_NODE(),\n'
			for child in self.children:
				data += child.to_c(depth + 1)
			if type(self.node) in nodeGroupClasses:
				data += depth * '\t' + 'GEO_CLOSE_NODE(),\n'
		elif type(self.node) is SwitchNode:
			raise ValueError("A switch bone must have at least one child bone.")
		return data
	
	def toTextDump(self, nodeLevel, segmentData):
		data = ''
		if self.node is not None:
			command = self.node.to_binary(segmentData)
		else:
			command = bytearray(0)

		data += '\t' * nodeLevel
		for byteVal in command:
			data += (format(byteVal, '02X') + ' ')
		data += '\n'

		if len(self.children) > 0:
			if len(command) == 0 or command[0] in nodeGroupCmds:
				data += '\t' * nodeLevel + '04 00 00 00\n'
			for child in self.children:
				data += child.toTextDump(nodeLevel + 1, segmentData)
			if len(command) == 0 or command[0] in nodeGroupCmds:
				data += '\t' * nodeLevel + '05 00 00 00\n'
		elif type(self.node) is SwitchNode:
			raise ValueError("A switch bone must have at least one child bone.")
		return data


class SwitchOverrideNode:
	def __init__(self, material, specificMat, drawLayer, overrideType):
		self.material = material
		self.specificMat = specificMat
		self.drawLayer = drawLayer
		self.overrideType = overrideType

# We add Function commands to nonDeformTransformData because any skinned
# 0x15 commands should go before them, as they are usually preceding
# an empty transform command (of which they modify?)
class FunctionNode:
	def __init__(self, geo_func, func_param):
		self.geo_func = geo_func
		self.func_param = func_param
		self.hasDL = False
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_CALL_ASM, 0x00])
		command.extend(self.func_param.to_bytes(2, 'big', signed = True))
		command.extend(bytes.fromhex(self.geo_func))
		return command

	def to_c(self):
		return "GEO_ASM(" + str(self.func_param) + ', ' + \
			toAlnum(self.geo_func) + '),'

class HeldObjectNode:
	def __init__(self, geo_func, translate):
		self.geo_func = geo_func
		self.translate = translate
		self.hasDL = False
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_HELD_OBJECT, 0x00])
		command.extend(bytearray([0x00] * 6))
		writeVectorToShorts(command, 2, self.translate)
		command.extend(bytes.fromhex(self.geo_func))
		return command
	
	def to_c(self):
		return "GEO_HELD_OBJECT(0, " + \
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) + ', ' +\
			toAlnum(self.geo_func) + '),'

class StartNode:
	def __init__(self):
		self.hasDL = False
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_START, 0x00, 0x00, 0x00])
		return command

	def to_c(self):
		return "GEO_NODE_START(),"

class EndNode:
	def __init__(self):
		self.hasDL = False
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_END, 0x00, 0x00, 0x00])
		return command

	def to_c(self):
		return 'GEO_END(),'

# Geolayout node hierarchy is first generated without material/draw layer
# override options, but with material override DL's being generated.
# Afterward, for each switch node the node hierarchy is duplicated and
# the correct diplsay lists are added.
class SwitchNode:
	def __init__(self, geo_func, func_param):
		self.switchFunc = geo_func
		self.defaultCase = func_param
		self.hasDL = False
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_SWITCH, 0x00])
		command.extend(self.defaultCase.to_bytes(2, 'big', signed = True))
		command.extend(bytes.fromhex(self.switchFunc))
		return command

	def to_c(self):
		return "GEO_SWITCH_CASE(" + \
			str(self.defaultCase) + ', ' +\
			toAlnum(self.switchFunc) + '),'

class TranslateRotateNode:
	def __init__(self, drawLayer, fieldLayout, hasDL, translate, rotate):

		self.drawLayer = drawLayer
		self.fieldLayout = fieldLayout
		self.hasDL = hasDL

		self.translate = translate
		self.rotate = rotate

		self.fMesh = None
		self.DLmicrocode = None
		
	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) & \
			(self.fieldLayout << 4) | self.drawLayer

		command = bytearray([GEO_TRANSLATE_ROTATE, params])
		if self.fieldLayout == 0:
			command.extend(bytearray([0x00] * 14))
			writeVectorToShorts(command, 4, self.translate)
			writeEulerVectorToShorts(command, 10, 
				self.rotate.to_euler(geoNodeRotateOrder))
		elif self.fieldLayout == 1:
			command.extend(bytearray([0x00] * 6))
			writeVectorToShorts(command, 2, self.translate)
		elif self.fieldLayout == 2:
			command.extend(bytearray([0x00] * 6))
			writeEulerVectorToShorts(command, 2, 
				self.rotate.to_euler(geoNodeRotateOrder))
		elif self.fieldLayout == 3:
			command.extend(bytearray([0x00] * 2))
			writeFloatToShort(command, 2, 
			self.rotate.to_euler(geoNodeRotateOrder).y)
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		if self.fieldLayout == 0:
			return ("GEO_TRANSLATE_ROTATE_WITH_DL" if self.hasDL else \
				"GEO_TRANSLATE_ROTATE") + "(" + \
				str(self.drawLayer) + ', ' +\
				str(convertFloatToShort(self.translate[0])) + ', ' +\
				str(convertFloatToShort(self.translate[1])) + ', ' +\
				str(convertFloatToShort(self.translate[2])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[0])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[1])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[2])) + \
				((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')
		elif self.fieldLayout == 1:
			return ("GEO_TRANSLATE_WITH_DL" if self.hasDL else \
				"GEO_TRANSLATE") + "(" + \
				str(self.drawLayer) + ', ' +\
				str(convertFloatToShort(self.translate[0])) + ', ' +\
				str(convertFloatToShort(self.translate[1])) + ', ' +\
				str(convertFloatToShort(self.translate[2])) +\
				((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')
		elif self.fieldLayout == 2:
			return ("GEO_ROTATE_WITH_DL" if self.hasDL else \
				"GEO_ROTATE") + "(" + \
				str(self.drawLayer) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[0])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[1])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[2])) + \
				((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')
		elif self.fieldLayout == 3:
			return ("GEO_ROTATE_Y_WITH_DL" if self.hasDL else \
				"GEO_ROTATE_Y") + "(" + \
				str(self.drawLayer) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[1])) +\
				((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')

class TranslateNode:
	def __init__(self, drawLayer, useDeform, translate):
		self.drawLayer = drawLayer
		self.hasDL = useDeform
		self.translate = translate
		self.fMesh = None
		self.DLmicrocode = None
		
	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) | self.drawLayer
		command = bytearray([GEO_TRANSLATE, params])
		command.extend(bytearray([0x00] * 6))
		writeVectorToShorts(command, 2, self.translate)
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command
	
	def to_c(self):
		return ("GEO_TRANSLATE_NODE_WITH_DL" if self.hasDL else \
			"GEO_TRANSLATE_NODE") + "(" + \
			str(self.drawLayer) + ', ' +\
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) +\
			((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')

class RotateNode:
	def __init__(self, drawLayer, hasDL, rotate):
		# In the case for automatically inserting rotate nodes between
		# 0x13 bones.

		self.drawLayer = drawLayer
		self.hasDL = hasDL
		self.rotate = rotate
		self.fMesh = None
		self.DLmicrocode = None
		
	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) | self.drawLayer
		command = bytearray([GEO_ROTATE, params])
		command.extend(bytearray([0x00] * 6))
		writeEulerVectorToShorts(command, 2, 
			self.rotate.to_euler(geoNodeRotateOrder))
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		return ("GEO_ROTATION_NODE_WITH_DL" if self.hasDL else \
			"GEO_ROTATION_NODE") + "(" + \
			str(self.drawLayer) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[0])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[1])) + ', ' +\
				str(convertEulerFloatToShort(self.rotate.to_euler(
					geoNodeRotateOrder)[2])) + \
			((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')
	
class BillboardNode:
	def __init__(self, drawLayer, hasDL, translate):
		self.drawLayer = drawLayer
		self.hasDL = hasDL
		self.translate = translate
		self.fMesh = None
		self.DLmicrocode = None

	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) | self.drawLayer
		command = bytearray([GEO_BILLBOARD, params])
		command.extend(bytearray([0x00] * 6))
		writeVectorToShorts(command, 2, self.translate)
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		return ("GEO_BILLBOARD_WITH_PARAMS_AND_DL" if self.hasDL else \
			"GEO_BILLBOARD_WITH_PARAMS") + "(" + \
			str(self.drawLayer) + ', ' +\
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) +\
			((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')

class DisplayListNode:
	def __init__(self, drawLayer):
		self.drawLayer = drawLayer
		self.hasDL = True
		self.fMesh = None
		self.DLmicrocode = None

	def to_binary(self, segmentData):
		if self.DLmicrocode is None:
			raise ValueError("No mesh data associated with this 0x15 command. Make sure you have assigned vertices to this node.")
		command = bytearray([GEO_LOAD_DL, self.drawLayer, 0x00, 0x00])
		if segmentData is not None:
			command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
		else:
			command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		return "GEO_DISPLAY_LIST(" + \
			str(self.drawLayer) + ', ' +\
			self.DLmicrocode.name + '),'

class ShadowNode:
	def __init__(self, shadow_type, shadow_solidity, shadow_scale):
		self.shadowType = int(shadow_type)
		self.shadowSolidity = int(round(shadow_solidity * 0xFF))
		self.shadowScale = shadow_scale
		self.hasDL = False

	def to_binary(self, segmentData):
		command = bytearray([GEO_START_W_SHADOW, 0x00])
		command.extend(self.shadowType.to_bytes(2, 'big'))
		command.extend(self.shadowSolidity.to_bytes(2, 'big'))
		command.extend(self.shadowScale.to_bytes(2, 'big'))
		return command
	
	def to_c(self):
		return "GEO_SHADOW(" + \
			str(self.shadowType) + ', ' +\
			str(self.shadowSolidity) + ', ' +\
			str(self.shadowScale) + '),'

class ScaleNode:
	def __init__(self, drawLayer, geo_scale, use_deform):
		self.drawLayer = drawLayer
		self.scaleValue = geo_scale
		self.hasDL = use_deform
		self.fMesh = None
		self.DLmicrocode = None
	
	def to_binary(self, segmentData):
		params = ((1 if self.hasDL else 0) << 7) | self.drawLayer
		command = bytearray([GEO_SCALE, params, 0x00, 0x00])
		command.extend(int(self.scaleValue * 0x10000).to_bytes(4, 'big'))
		if self.hasDL:
			if segmentData is not None:
				command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
			else:
				command.extend(bytearray([0x00] * 4))
		return command
	
	def to_c(self):
		return ("GEO_SCALE_WITH_DL" if self.hasDL else "GEO_SCALE") + "(" + \
			str(self.drawLayer) + ', ' +\
			str(int(round(self.scaleValue * 0x10000))) +\
			((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')

class StartRenderAreaNode:
	def __init__(self, cullingRadius):
		self.cullingRadius = cullingRadius
		self.hasDL = False

	def to_binary(self, segmentData):
		command = bytearray([GEO_START_W_RENDERAREA, 0x00])
		command.extend(self.cullingRadius.to_bytes(2, 'big'))
		return command
	
	def to_c(self):
		return 'GEO_CULLING_RADIUS(' + str(self.cullingRadius) + '),'

class DisplayListWithOffsetNode:
	def __init__(self, drawLayer, use_deform, translate):
		self.drawLayer = drawLayer
		self.hasDL = use_deform
		self.translate = translate
		self.fMesh = None
		self.DLmicrocode = None

	def to_binary(self, segmentData):
		command = bytearray([GEO_LOAD_DL_W_OFFSET, self.drawLayer])
		command.extend(bytearray([0x00] * 6))
		writeVectorToShorts(command, 2, self.translate)
		if self.hasDL and self.DLmicrocode is not None and segmentData is not None:
			command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
		else:
			command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		return "GEO_ANIMATED_PART(" + \
			str(self.drawLayer) + ', ' +\
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) + ', ' +\
			(self.DLmicrocode.name if self.hasDL else 'NULL') + '),'

class ScreenAreaNode:
	def __init__(self, useDefaults, entryMinus2Count, position, size):
		self.useDefaults = useDefaults
		self.entryMinus2Count = entryMinus2Count
		self.position = position
		self.size = size
		
	def to_binary(self, segmentData):
		position = [160, 120] if self.useDefaults else self.position
		size = [160, 120] if self.useDefaults else self.size
		entryMinus2Count = 0xA if self.useDefaults else self.entryMinus2Count
		command = bytearray([GEO_SET_RENDER_AREA, 0x00])
		command.extend(entryMinus2Count.to_bytes(2, 'big', signed = False))
		command.extend(position[0].to_bytes(2, 'big', signed = True))
		command.extend(position[1].to_bytes(2, 'big', signed = True))
		command.extend(size[0].to_bytes(2, 'big', signed = True))
		command.extend(size[1].to_bytes(2, 'big', signed = True))
		return command

	def to_c(self):
		if self.useDefaults:
			return 'GEO_NODE_SCREEN_AREA(10, ' +\
				'SCREEN_WIDTH/2, SCREEN_HEIGHT/2, ' +\
				'SCREEN_WIDTH/2, SCREEN_HEIGHT/2),'
		else:
			return 'GEO_NODE_SCREEN_AREA(' + str(self.entryMinus2Count) +\
				', ' + str(self.position[0]) + ', ' + str(self.position[1]) +\
				', ' + str(self.size[0]) + ', ' + str(self.size[1]) + '),'

class OrthoNode:
	def __init__(self, scale):
		self.scale = scale
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_SET_ORTHO, 0x00])
		# FIX: This should be f32.
		command.extend(bytearray(struct.pack(">f", self.scale)))
		return command

	def to_c(self):
		return 'GEO_NODE_ORTHO(' + format(self.scale, '.4f') + '),'

class FrustumNode:
	def __init__(self, fov, near, far):
		self.fov = fov
		self.near = int(round(100 * near))
		self.far = int(round(100 * far))
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_SET_CAMERA_FRUSTRUM, 0x00])
		command.extend(bytearray(struct.pack(">f", self.fov)))
		command.extend(self.near.to_bytes(2, 'big', signed = True)) # Conversion?
		command.extend(self.far.to_bytes(2, 'big', signed = True)) # Conversion?

		if True: # Always use function?
			command.extend(bytes.fromhex('8029AA3C'))
		return command

	def to_c(self):
		if False: # Always use function?
			return 'GEO_CAMERA_FRUSTUM(' + format(self.fov, '.4f') +\
				', ' + str(self.near) + ', ' + str(self.far) + '),'
		else:
			return 'GEO_CAMERA_FRUSTUM_WITH_FUNC(' + format(self.fov, '.4f') +\
				', ' + str(self.near) + ', ' + str(self.far) +\
				', geo_camera_fov),'

class ZBufferNode:
	def __init__(self, enable):
		self.enable = enable
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_SET_Z_BUF, 0x01 if self.enable else 0x00,
			0x00, 0x00])
		return command

	def to_c(self):
		return 'GEO_ZBUFFER(' + ('1' if self.enable else '0') + '),'

class CameraNode:
	def __init__(self, camType, position, lookAt):
		self.camType = camType
		self.position = \
			[int(round(value / sm64ToBlenderScale)) for value in position]
		self.lookAt = \
			[int(round(value / sm64ToBlenderScale)) for value in lookAt]
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_CAMERA, 0x00])
		command.extend(self.camType.to_bytes(2, 'big', signed = True))
		command.extend(self.position[0].to_bytes(2, 'big', signed = True))
		command.extend(self.position[1].to_bytes(2, 'big', signed = True))
		command.extend(self.position[2].to_bytes(2, 'big', signed = True))
		command.extend(self.lookAt[0].to_bytes(2, 'big', signed = True))
		command.extend(self.lookAt[1].to_bytes(2, 'big', signed = True))
		command.extend(self.lookAt[2].to_bytes(2, 'big', signed = True))
		command.extend(bytes.fromhex('80287D30'))
		return command

	def to_c(self):
		return 'GEO_CAMERA(' + str(self.camType) + ', ' + \
			str(self.position[0]) + ', ' + \
			str(self.position[1]) + ', ' + \
			str(self.position[2]) + ', ' + \
			str(self.lookAt[0]) + ', ' + \
			str(self.lookAt[1]) + ', ' + \
			str(self.lookAt[2]) + ', ' + \
			'geo_camera_preset_and_pos),'

class RenderObjNode:
	def __init__(self):
		pass
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_SETUP_OBJ_RENDER, 0x00, 0x00, 0x00])
		return command

	def to_c(self):
		return 'GEO_RENDER_OBJ(),'

class BackgroundNode:
	def __init__(self, isColor, backgroundValue):
		self.isColor = isColor
		self.backgroundValue = backgroundValue
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_SET_BG, 0x00])
		command.extend(self.backgroundValue.to_bytes(2, 'big', signed = False))
		if self.isColor:
			command.extend(bytes.fromhex('00000000'))
		else:
			command.extend(bytes.fromhex('802763D4'))
		return command

	def to_c(self):
		if self.isColor:
			return 'GEO_BACKGROUND_COLOR(0x' + \
				format(self.backgroundValue, '04x').upper() + '),'
		else:
			return 'GEO_BACKGROUND(0x' + \
				format(self.backgroundValue, '04x').upper() + \
				', geo_skybox_main),'

class EnvFunctionNode:
	def __init__(self, index):
		self.index = index
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_CALL_ASM, 0x00])
		command.extend(self.index.to_bytes(2, 'big', signed = False))
		command.extend(bytes.fromhex('802761D0'))
		return command

	def to_c(self):
		return 'GEO_ASM(' + str(self.index) + ', geo_enfvx_main),'

# geo_movtex_pause_control = 802D01E0 
# geo_movtex_draw_nocolor = 802D1B70 
# geo_switch_area = 8029DBD4

nodeGroupClasses = [
	StartNode,
	SwitchNode,
	TranslateRotateNode,
	TranslateNode,
	RotateNode,
	DisplayListWithOffsetNode,
	BillboardNode,
	ShadowNode,
	ScaleNode,
	StartRenderAreaNode,
	ScreenAreaNode,
	OrthoNode,
	FrustumNode,
	ZBufferNode,
	CameraNode
]