from .sm64_geolayout_constants import *
from .sm64_geolayout_utility import *
from .utility import *
from .sm64_constants import *
from .sm64_function_map import func_map 
import struct
import copy

drawLayerNames = {
	0 : 'LAYER_FORCE',
	1 : 'LAYER_OPAQUE',
	2 : 'LAYER_OPAQUE_DECAL',
	3 : 'LAYER_OPAQUE_INTER',
	4 : 'LAYER_ALPHA',
	5 : 'LAYER_TRANSPARENT',
	6 : 'LAYER_TRANSPARENT_DECAL',
	7 : 'LAYER_TRANSPARENT_INTER',
}

def getDrawLayerName(drawLayer):
	if drawLayer in drawLayerNames:
		return drawLayerNames[drawLayer]
	else:
		return str(drawLayer)

def addFuncAddress(command, func):
	try:
		command.extend(bytes.fromhex(func))
	except ValueError:
		raise PluginError("In geolayout node, could not convert function \"" + str(func) + '\" to hexadecimal.')

class GeolayoutGraph:
	def __init__(self, name):
		self.startGeolayout = Geolayout(name, True)
		# dict of Object : Geolayout
		self.secondaryGeolayouts = {}
		# dict of Geolayout : Geolayout List (which geolayouts are called)
		self.geolayoutCalls = {}
		self.sortedList = []
		self.sortedListGenerated = False

	def checkListSorted(self):
		if not self.sortedListGenerated:
			raise PluginError("Must generate sorted geolayout list first " +\
				'before calling this function.')

	def get_ptr_addresses(self):
		self.checkListSorted()
		addresses = []
		for geolayout in self.sortedList:
			addresses.extend(geolayout.get_ptr_addresses())
		return addresses

	def size(self):
		self.checkListSorted()
		size = 0
		for geolayout in self.sortedList:
			size += geolayout.size()

		return size

	def addGeolayout(self, obj, name):
		geolayout = Geolayout(name, False)
		self.secondaryGeolayouts[obj] = geolayout
		return geolayout

	def addJumpNode(self, parentNode, caller, callee, index = None):
		if index is None:
			parentNode.children.append(TransformNode(JumpNode(
				True, callee)))
		else:
			parentNode.children.insert(index, TransformNode(JumpNode(
				True, callee)))
		self.addGeolayoutCall(caller, callee)

	def addGeolayoutCall(self, caller, callee):
		if caller not in self.geolayoutCalls:
			self.geolayoutCalls[caller] = []
		self.geolayoutCalls[caller].append(callee)

	def sortGeolayouts(self, geolayoutList, geolayout, callOrder):
		if geolayout in self.geolayoutCalls:
			for calledGeolayout in self.geolayoutCalls[geolayout]:
				geoIndex = geolayoutList.index(geolayout)
				if calledGeolayout in geolayoutList:
					callIndex = geolayoutList.index(calledGeolayout)
					if callIndex < geoIndex:
						continue
					else:
						raise PluginError('Circular geolayout dependency.' +\
							str(callOrder))
				else:
					geolayoutList.insert(geolayoutList.index(geolayout),
						calledGeolayout)
					callOrder = copy.copy(callOrder)
					callOrder.append(calledGeolayout)
					self.sortGeolayouts(geolayoutList, calledGeolayout,
						callOrder)
		return geolayoutList

	def generateSortedList(self):
		self.sortedList = self.sortGeolayouts([self.startGeolayout],
			self.startGeolayout, [self.startGeolayout])
		self.sortedListGenerated = True

	def set_addr(self, address):
		self.checkListSorted()
		for geolayout in self.sortedList:
			geolayout.startAddress = address
			address += geolayout.size()
			print(geolayout.name + " - " + \
				str(geolayout.startAddress))
		return address
	
	def to_binary(self, segmentData):
		self.checkListSorted()
		data = bytearray(0)
		for geolayout in self.sortedList:
			data += geolayout.to_binary(segmentData)
		return data

	def save_binary(self, romfile, segmentData):
		for geolayout in self.sortedList:
			geolayout.save_binary(romfile, segmentData)

	def to_c(self):
		self.checkListSorted()
		data = '#include "src/game/envfx_snow.h"\n\n'
		for geolayout in self.sortedList:
			data += geolayout.to_c()
		return data
	
	def to_c_def(self):
		self.checkListSorted()
		data = ''
		for geolayout in self.sortedList:
			data += geolayout.to_c_def()
		return data

	def toTextDump(self, segmentData):
		self.checkListSorted()
		data = ''
		for geolayout in self.sortedList:
			data += geolayout.toTextDump(segmentData) + '\n'
		return data

	def convertToDynamic(self):
		self.checkListSorted()
		for geolayout in self.sortedList:
			for node in geolayout.nodes:
				node.convertToDynamic()
	
	def getDrawLayers(self):
		drawLayers = self.startGeolayout.getDrawLayers()
		for obj, geolayout in self.secondaryGeolayouts.items():
			drawLayers |= geolayout.getDrawLayers()

		return drawLayers

class Geolayout:
	def __init__(self, name, isStartGeo):
		self.nodes = []
		self.name = toAlnum(name)
		self.startAddress = 0
		self.isStartGeo = isStartGeo
	
	def size(self):
		size = 4 # end command
		for node in self.nodes:
			size += node.size()
		return size
	
	def get_ptr_addresses(self):
		address = self.startAddress
		addresses = []
		for node in self.nodes:
			address, ptrs = node.get_ptr_addresses(address)
			addresses.extend(ptrs)
		return addresses

	def to_binary(self, segmentData):
		endCmd = GEO_END if self.isStartGeo else GEO_RETURN
		data = bytearray(0)
		for node in self.nodes:
			data += node.to_binary(segmentData)
		data += bytearray([endCmd, 0x00, 0x00, 0x00])
		return data

	def save_binary(self, romfile, segmentData):
		romfile.seek(self.startAddress)
		romfile.write(self.to_binary(segmentData))

	def to_c(self):
		endCmd = 'GEO_END' if self.isStartGeo else 'GEO_RETURN'
		data = 'const GeoLayout ' + self.name + '[] = {\n'
		for node in self.nodes:
			data += node.to_c(1)
		data += '\t' + endCmd + '(),\n'
		data += '};\n'
		return data
	
	def to_c_def(self):
		return 'extern const GeoLayout ' + self.name + '[];\n'

	def toTextDump(self, segmentData):
		endCmd = '01' if self.isStartGeo else '03'
		data = ''
		for node in self.nodes:
			data += node.toTextDump(0, segmentData)
		data += endCmd + ' 00 00 00\n'
		return data

	def getDrawLayers(self):
		drawLayers = set()
		for node in self.nodes:
			drawLayers |= node.getDrawLayers()
		return drawLayers
		
class TransformNode:
	def __init__(self, node):
		self.node = node
		self.children = []
		self.parent = None
		self.skinned = False
		self.skinnedWithoutDL = False

	def convertToDynamic(self):
		if self.node.hasDL:
			funcNode = FunctionNode(self.node.DLmicrocode.name, self.node.drawLayer)

			if isinstance(self.node, DisplayListNode):
				self.node = funcNode
			else:
				self.node.hasDL = False
				transformNode = TransformNode(funcNode)
				self.children.insert(0, transformNode)
		
		for child in self.children:
			child.convertToDynamic()
	
	def get_ptr_addresses(self, address):
		addresses = []
		if self.node is not None:
			if type(self.node) in DLNodes:
				for offset in self.node.get_ptr_offsets():
					addresses.append(address + offset)
			else:
				addresses = []
			address += self.node.size()
		if len(self.children) > 0:
			address += 4
			for node in self.children:
				address, ptrs = node.get_ptr_addresses(address)
				addresses.extend(ptrs)
			address += 4
		return address, addresses

	def size(self):
		size = self.node.size() if self.node is not None else 0
		if len(self.children) > 0 and type(self.node) in nodeGroupClasses:
			size += 8 # node open/close
			for child in self.children:
				size += child.size()
			
		return size

	# Function commands usually effect the following command, so it is similar
	# to a parent child relationship.
	def to_binary(self, segmentData):
		if self.node is not None:
			data = self.node.to_binary(segmentData)
		else:
			data = bytearray(0)
		if len(self.children) > 0:
			if type(self.node) is FunctionNode:
				raise PluginError("An FunctionNode cannot have children.")

			if data[0] in nodeGroupCmds:
				data.extend(bytearray([GEO_NODE_OPEN, 0x00, 0x00, 0x00]))
			for child in self.children:
				data.extend(child.to_binary(segmentData))
			if data[0] in nodeGroupCmds:
				data.extend(bytearray([GEO_NODE_CLOSE, 0x00, 0x00, 0x00]))
		elif type(self.node) is SwitchNode:
			raise PluginError("A switch bone must have at least one child bone.")
		return data

	def to_c(self, depth):
		if self.node is not None:
			nodeC = self.node.to_c()
			if nodeC is not None: # Should only be the case for DisplayListNode with no DL
				data = depth * '\t' + self.node.to_c() + '\n'
			else:
				data = ''
		else:
			data = ''
		if len(self.children) > 0:
			if type(self.node) in nodeGroupClasses:
				data += depth * '\t' + 'GEO_OPEN_NODE(),\n'
			for child in self.children:
				data += child.to_c(depth + (1 if \
					type(self.node) in nodeGroupClasses else 0))
			if type(self.node) in nodeGroupClasses:
				data += depth * '\t' + 'GEO_CLOSE_NODE(),\n'
		elif type(self.node) is SwitchNode:
			raise PluginError("A switch bone must have at least one child bone.")
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
			raise PluginError("A switch bone must have at least one child bone.")
		return data

	def getDrawLayers(self):
		if self.node is not None and self.node.hasDL:
			drawLayers = set([self.node.drawLayer])	
		else:
			drawLayers = set()
		for child in self.children:
			drawLayers |= child.getDrawLayers()
		return drawLayers

class SwitchOverrideNode:
	def __init__(self, material, specificMat, drawLayer, overrideType):
		self.material = material
		self.specificMat = specificMat
		self.drawLayer = drawLayer
		self.overrideType = overrideType

class JumpNode:
	def __init__(self, storeReturn, geolayout):
		self.geolayout = geolayout
		self.storeReturn = storeReturn
		self.hasDL = False
	
	def size(self):
		return 8
	
	def get_ptr_offsets(self):
		return [4]

	def to_binary(self, segmentData):
		if segmentData is not None:
			startAddress = encodeSegmentedAddr(self.geolayout.startAddress,
				segmentData)
		else:
			startAddress = bytearray([0x00] * 4)
		command = bytearray([GEO_BRANCH, 
			0x01 if self.storeReturn else 0x00, 0x00, 0x00])
		command.extend(startAddress)
		return command

	def to_c(self):
		return "GEO_BRANCH(" + ('1, ' if self.storeReturn else '0, ') + \
			self.geolayout.name + '),'

def convertAddrToFunc(addr):
	if addr == '':
		raise PluginError("Geolayout node cannot have an empty function name/address.")
	refresh_func_map = func_map[bpy.context.scene.refreshVer]
	if addr.lower() in refresh_func_map:
		return refresh_func_map[addr.lower()]
	else:
		return toAlnum(addr)

# We add Function commands to nonDeformTransformData because any skinned
# 0x15 commands should go before them, as they are usually preceding
# an empty transform command (of which they modify?)
class FunctionNode:
	def __init__(self, geo_func, func_param):
		self.geo_func = geo_func
		self.func_param = func_param
		self.hasDL = False

	def size(self):
		return 8
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_CALL_ASM, 0x00])
		command.extend(self.func_param.to_bytes(2, 'big', signed = True))
		addFuncAddress(command, self.geo_func)
		return command

	def to_c(self):
		return "GEO_ASM(" + str(self.func_param) + ', ' + \
			convertAddrToFunc(self.geo_func) + '),'

class HeldObjectNode:
	def __init__(self, geo_func, translate):
		self.geo_func = geo_func
		self.translate = translate
		self.hasDL = False

	def size(self):
		return 12
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_HELD_OBJECT, 0x00])
		command.extend(bytearray([0x00] * 6))
		writeVectorToShorts(command, 2, self.translate)
		addFuncAddress(command, self.geo_func)
		return command
	
	def to_c(self):
		return "GEO_HELD_OBJECT(0, " + \
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) + ', ' +\
			convertAddrToFunc(self.geo_func) + '),'

class StartNode:
	def __init__(self):
		self.hasDL = False
	
	def size(self):
		return 4
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_START, 0x00, 0x00, 0x00])
		return command

	def to_c(self):
		return "GEO_NODE_START(),"

class EndNode:
	def __init__(self):
		self.hasDL = False

	def size(self):
		return 4
	
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
	def __init__(self, geo_func, func_param, name):
		self.switchFunc = geo_func
		self.defaultCase = func_param
		self.hasDL = False
		self.name = name

	def size(self):
		return 8
	
	def to_binary(self, segmentData):
		command = bytearray([GEO_SWITCH, 0x00])
		command.extend(self.defaultCase.to_bytes(2, 'big', signed = True))
		addFuncAddress(command, self.switchFunc)
		return command

	def to_c(self):
		return "GEO_SWITCH_CASE(" + \
			str(self.defaultCase) + ', ' +\
			convertAddrToFunc(self.switchFunc) + '),'

class TranslateRotateNode:
	def __init__(self, drawLayer, fieldLayout, hasDL, translate, rotate):

		self.drawLayer = drawLayer
		self.fieldLayout = fieldLayout
		self.hasDL = hasDL

		self.translate = translate
		self.rotate = rotate

		self.fMesh = None
		self.DLmicrocode = None
	
	def get_ptr_offsets(self):
		if self.hasDL:
			if self.fieldLayout == 0:
				return [16]
			elif self.fieldLayout == 1:
				return [8]
			elif self.fieldLayout == 2:
				return [8]
			elif self.fieldLayout == 3:
				return [4]
		else:
			return []
	
	def size(self):
		if self.fieldLayout == 0:
			size = 16
		elif self.fieldLayout == 1:
			size = 8
		elif self.fieldLayout == 2:
			size = 8
		elif self.fieldLayout == 3:
			size = 4

		if self.hasDL:
			size += 4
		return size
		
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
				getDrawLayerName(self.drawLayer) + ', ' +\
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
				getDrawLayerName(self.drawLayer) + ', ' +\
				str(convertFloatToShort(self.translate[0])) + ', ' +\
				str(convertFloatToShort(self.translate[1])) + ', ' +\
				str(convertFloatToShort(self.translate[2])) +\
				((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')
		elif self.fieldLayout == 2:
			return ("GEO_ROTATE_WITH_DL" if self.hasDL else \
				"GEO_ROTATE") + "(" + \
				getDrawLayerName(self.drawLayer) + ', ' +\
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
				getDrawLayerName(self.drawLayer) + ', ' +\
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
	
	def get_ptr_offsets(self):
		return [8] if self.hasDL else []

	def size(self):
		return 12 if self.hasDL else 8
		
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
			getDrawLayerName(self.drawLayer) + ', ' +\
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
	
	def get_ptr_offsets(self):
		return [8] if self.hasDL else []
	
	def size(self):
		return 12 if self.hasDL else 8
		
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
			getDrawLayerName(self.drawLayer) + ', ' +\
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
	
	def get_ptr_offsets(self):
		return [8] if self.hasDL else []
	
	def size(self):
		return 12 if self.hasDL else 8

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
			getDrawLayerName(self.drawLayer) + ', ' +\
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
	
	def get_ptr_offsets(self):
		return [4]
	
	def size(self):
		return 8

	def to_binary(self, segmentData):
		command = bytearray([GEO_LOAD_DL, self.drawLayer, 0x00, 0x00])
		if self.hasDL and self.DLmicrocode is not None and segmentData is not None:
			command.extend(encodeSegmentedAddr(self.DLmicrocode.startAddress,segmentData))
		else:
			command.extend(bytearray([0x00] * 4))
		return command

	def to_c(self):
		if not self.hasDL:
			return None
		return "GEO_DISPLAY_LIST(" + \
			getDrawLayerName(self.drawLayer) + ', ' +\
			(self.DLmicrocode.name if self.hasDL else 'NULL') + '),'

class ShadowNode:
	def __init__(self, shadow_type, shadow_solidity, shadow_scale):
		self.shadowType = int(shadow_type)
		self.shadowSolidity = int(round(shadow_solidity * 0xFF))
		self.shadowScale = shadow_scale
		self.hasDL = False

	def size(self):
		return 8

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
	
	def get_ptr_offsets(self):
		return [8] if self.hasDL else []
	
	def size(self):
		return 12 if self.hasDL else 8
	
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
			getDrawLayerName(self.drawLayer) + ', ' +\
			str(int(round(self.scaleValue * 0x10000))) +\
			((', ' + self.DLmicrocode.name + '),') if self.hasDL else '),')

class StartRenderAreaNode:
	def __init__(self, cullingRadius):
		self.cullingRadius = cullingRadius
		self.hasDL = False
	
	def size(self):
		return 4

	def to_binary(self, segmentData):
		command = bytearray([GEO_START_W_RENDERAREA, 0x00])
		command.extend(convertFloatToShort(self.cullingRadius).to_bytes(2, 'big'))
		return command
	
	def to_c(self):
		cullingRadius = convertFloatToShort(self.cullingRadius)
		#if abs(cullingRadius) > 2**15 - 1:
		#	raise PluginError("A render area node has a culling radius that does not fit an s16.\n Radius is " +\
		#		str(cullingRadius) + ' when converted to SM64 units.')
		return 'GEO_CULLING_RADIUS(' + str(convertFloatToShort(self.cullingRadius)) + '),'

class RenderRangeNode:
	def __init__(self, minDist, maxDist):
		self.minDist = minDist
		self.maxDist = maxDist
		self.hasDL = False
	
	def size(self):
		return 8

	def to_binary(self, segmentData):
		command = bytearray([GEO_SET_RENDER_RANGE, 0x00, 0x00, 0x00])
		command.extend(convertFloatToShort(self.minDist).to_bytes(2, 'big'))
		command.extend(convertFloatToShort(self.maxDist).to_bytes(2, 'big'))
		return command
	
	def to_c(self):
		minDist = convertFloatToShort(self.minDist)
		maxDist = convertFloatToShort(self.maxDist)
		#if (abs(minDist) > 2**15 - 1) or (abs(maxDist) > 2**15 - 1):
		#	raise PluginError("A render range (LOD) node has a range that does not fit an s16.\n Range is " +\
		#		str(minDist) + ', ' + str(maxDist) + ' when converted to SM64 units.')
		return 'GEO_RENDER_RANGE(' + str(minDist) + ', ' +\
			str(maxDist) + '),'

class DisplayListWithOffsetNode:
	def __init__(self, drawLayer, use_deform, translate):
		self.drawLayer = drawLayer
		self.hasDL = use_deform
		self.translate = translate
		self.fMesh = None
		self.DLmicrocode = None
	
	def size(self):
		return 12
	
	def get_ptr_offsets(self):
		return [8] if self.hasDL else []

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
			getDrawLayerName(self.drawLayer) + ', ' +\
			str(convertFloatToShort(self.translate[0])) + ', ' +\
			str(convertFloatToShort(self.translate[1])) + ', ' +\
			str(convertFloatToShort(self.translate[2])) + ', ' +\
			(self.DLmicrocode.name if self.hasDL else 'NULL') + '),'

class ScreenAreaNode:
	def __init__(self, useDefaults, entryMinus2Count, position, dimensions):
		self.useDefaults = useDefaults
		self.entryMinus2Count = entryMinus2Count
		self.position = position
		self.dimensions = dimensions
		self.hasDL = False
	
	def size(self):
		return 12
		
	def to_binary(self, segmentData):
		position = [160, 120] if self.useDefaults else self.position
		dimensions = [160, 120] if self.useDefaults else self.dimensions
		entryMinus2Count = 0xA if self.useDefaults else self.entryMinus2Count
		command = bytearray([GEO_SET_RENDER_AREA, 0x00])
		command.extend(entryMinus2Count.to_bytes(2, 'big', signed = False))
		command.extend(position[0].to_bytes(2, 'big', signed = True))
		command.extend(position[1].to_bytes(2, 'big', signed = True))
		command.extend(dimensions[0].to_bytes(2, 'big', signed = True))
		command.extend(dimensions[1].to_bytes(2, 'big', signed = True))
		return command

	def to_c(self):
		if self.useDefaults:
			return 'GEO_NODE_SCREEN_AREA(10, ' +\
				'SCREEN_WIDTH/2, SCREEN_HEIGHT/2, ' +\
				'SCREEN_WIDTH/2, SCREEN_HEIGHT/2),'
		else:
			return 'GEO_NODE_SCREEN_AREA(' + str(self.entryMinus2Count) +\
				', ' + str(self.position[0]) + ', ' + str(self.position[1]) +\
				', ' + str(self.dimensions[0]) + ', ' + \
				str(self.dimensions[1]) + '),'

class OrthoNode:
	def __init__(self, scale):
		self.scale = scale
		self.hasDL = False
	
	def size(self):
		return 4
		
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
		self.near = int(round(near))
		self.far = int(round(far))
		self.useFunc = True # Always use function?
		self.hasDL = False
	
	def size(self):
		return 12 if self.useFunc else 8
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_SET_CAMERA_FRUSTRUM, 
			0x01 if self.useFunc else 0x00])
		command.extend(bytearray(struct.pack(">f", self.fov)))
		command.extend(self.near.to_bytes(2, 'big', signed = True)) # Conversion?
		command.extend(self.far.to_bytes(2, 'big', signed = True)) # Conversion?

		if self.useFunc: 
			command.extend(bytes.fromhex('8029AA3C'))
		return command

	def to_c(self):
		if not self.useFunc:
			return 'GEO_CAMERA_FRUSTUM(' + format(self.fov, '.4f') +\
				', ' + str(self.near) + ', ' + str(self.far) + '),'
		else:
			return 'GEO_CAMERA_FRUSTUM_WITH_FUNC(' + format(self.fov, '.4f') +\
				', ' + str(self.near) + ', ' + str(self.far) +\
				', geo_camera_fov),'

class ZBufferNode:
	def __init__(self, enable):
		self.enable = enable
		self.hasDL = False

	def size(self):
		return 4
		
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
			[int(round(value * bpy.context.scene.blenderToSM64Scale)) for value in position]
		self.lookAt = \
			[int(round(value * bpy.context.scene.blenderToSM64Scale)) for value in lookAt]
		self.geo_func = '80287D30'
		self.hasDL = False
	
	def size(self):
		return 20

	def to_binary(self, segmentData):
		command = bytearray([GEO_CAMERA, 0x00])
		command.extend(self.camType.to_bytes(2, 'big', signed = True))
		command.extend(self.position[0].to_bytes(2, 'big', signed = True))
		command.extend(self.position[1].to_bytes(2, 'big', signed = True))
		command.extend(self.position[2].to_bytes(2, 'big', signed = True))
		command.extend(self.lookAt[0].to_bytes(2, 'big', signed = True))
		command.extend(self.lookAt[1].to_bytes(2, 'big', signed = True))
		command.extend(self.lookAt[2].to_bytes(2, 'big', signed = True))
		addFuncAddress(command, self.geo_func)
		return command

	def to_c(self):
		return 'GEO_CAMERA(' + str(self.camType) + ', ' + \
			str(self.position[0]) + ', ' + \
			str(self.position[1]) + ', ' + \
			str(self.position[2]) + ', ' + \
			str(self.lookAt[0]) + ', ' + \
			str(self.lookAt[1]) + ', ' + \
			str(self.lookAt[2]) + ', ' + \
			convertAddrToFunc(self.geo_func) + '),'

class RenderObjNode:
	def __init__(self):
		self.hasDL = False
		pass

	def size(self):
		return 4
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_SETUP_OBJ_RENDER, 0x00, 0x00, 0x00])
		return command

	def to_c(self):
		return 'GEO_RENDER_OBJ(),'

class BackgroundNode:
	def __init__(self, isColor, backgroundValue):
		self.isColor = isColor
		self.backgroundValue = backgroundValue
		self.geo_func = '802763D4'
		self.hasDL = False

	def size(self):
		return 8
		
	def to_binary(self, segmentData):
		command = bytearray([GEO_SET_BG, 0x00])
		command.extend(self.backgroundValue.to_bytes(2, 'big', signed = False))
		if self.isColor:
			command.extend(bytes.fromhex('00000000'))
		else:
			addFuncAddress(command, self.geo_func)
		return command

	def to_c(self):
		if self.isColor:
			return 'GEO_BACKGROUND_COLOR(0x' + \
				format(self.backgroundValue, '04x').upper() + '),'
		else:
			return 'GEO_BACKGROUND(' + \
				str(self.backgroundValue) + \
				', ' + convertAddrToFunc(self.geo_func) + '),'

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
	CameraNode,
	RenderRangeNode,
]

DLNodes = [
	JumpNode,
	TranslateRotateNode,
	TranslateNode,
	RotateNode,
	ScaleNode,
	DisplayListNode,
	DisplayListWithOffsetNode
]