import bpy
import math
import mathutils
from bpy.types import Node, NodeSocket, NodeSocketInterface, ShaderNode, ShaderNodeGroup, Panel
import nodeitems_utils
from nodeitems_utils import NodeCategory, NodeItem
from .f3d_gbi import F3D
from .f3d_enums import *
from bpy.utils import register_class, unregister_class

def createGroupLink(node_tree, inputSocket, outputSocket, outputType, outputName):
	if outputType is not None:
		node_tree.outputs.new(outputType, outputName)
	node_tree.links.new(inputSocket, outputSocket)

def addNodeAt(node_tree, name, label, x, y):
	node = node_tree.nodes.new(name)
	if label is not None:
		node.label = label
		node.name = label
	node.location = (x,y)
	if label == '1':
		node.outputs[0].default_value = 1
	elif label == '0':
		node.outputs[0].default_value = 0
	elif label == 'Shade Color':
		node.label = 'Shade Shader'
		colorNode = node_tree.nodes.new('ShaderNodeShaderToRGB')
		node.inputs[0].default_value = (1,1,1,1)
		if label is not None:
			colorNode.label = label
		node_tree.links.new(colorNode.inputs[0], node.outputs[0])
		colorNode.location = (x,y)
		node.location = (x - 300, y)
		node = colorNode
	elif label == 'Environment Color' or label == 'Primitive Color':
		alphaSplitNode = node_tree.nodes.new('GetAlphaFromColor')
		node_tree.links.new(alphaSplitNode.inputs[0], node.outputs[0])
		alphaSplitNode.location = (x-300, y)
		
		addNode = node_tree.nodes.new('ShaderNodeMath')
		addNode.operation = 'ADD'
		addNode.inputs[1].default_value = 0
		node_tree.links.new(addNode.inputs[0], alphaSplitNode.outputs[1])
		addNode.location = (x,y)

		mixNode = node_tree.nodes.new('ShaderNodeMixRGB')
		mixNode.inputs[0].default_value = 0
		node_tree.links.new(mixNode.inputs[1], alphaSplitNode.outputs[0])
		mixNode.location = (x,y - 100)

		node.location = (x-600,y)
		node = mixNode
	elif label == 'Noise':
		node.inputs[1].default_value = 40 # scale
		node.inputs[2].default_value = 0 # detail

	return (node, x + (node.width + 150), y - (node.height + 100))

def addNodeListAt(node_tree, nodeDict, x,y):
	newDict = {}
	for label, typename in nodeDict.items():
		node, xDiscard, y = addNodeAt(node_tree, typename, label, x, y)
		newDict[label] = node
	return newDict

# In 2.8 the Node.update function does not work.
# We can bypass this by adding an update callback to a property in the node.
# However, forcing an output socket update does NOT work when the output
# is a group node input. Thus we must add an add node in between to fix this.
def addNodeListAtWithZeroAddNode(node_tree, nodeDict, x,y, cycleIndex):
	newDict = {}
	for label, typename in nodeDict.items():
		name = label + " " + str(cycleIndex)
		node, nextX, nextY = addNodeAt(node_tree, typename, name, x, y)
		bridge, nextX, nextY = addNodeAt(
			node_tree, 'ShaderNodeMath', name + ' Bridge', nextX, y)
		bridge.operation = 'ADD'
		bridge.inputs[1].default_value = 0
		node_tree.links.new(bridge.inputs[0], node.outputs[0])
		newDict[name] = bridge
		y = nextY
	return newDict

# Assumes ascending order of cases.
def createNodeSwitch(node_tree, caseDict, caseSocket, caseName, 
	location, socketDict):
	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", name = 'Switch')
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.location = location
	location[1] = location[1] - (groupNode.height + 100)
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	output_node = group_tree.nodes.new("NodeGroupOutput")
	input_node.location = (-300, 0)
	output_node.location = (600, 0)

	# Add case node links
	groupNode.inputs.new('NodeSocketInt', caseName)
	node_tree.links.new(groupNode.inputs[0], caseSocket)
	input_node.outputs.new('NodeSocketInt', caseName)
	output_node.inputs.new('NodeSocketInt', caseName)
	caseNodeInternal = input_node.outputs[0]

	internalSocketDict = socketDictToInternalSocket(node_tree, 
		groupNode, input_node, socketDict, 1)

	nodePos = [0,0]
	for case in reversed(range (len(caseDict))):
		name = caseDict[case]
		if case == len(caseDict) - 1:
			prevSocket = internalSocketDict[name]
		else:
			greaterThanNode, mixNodeX, y = \
				addNodeAt(group_tree, 'ShaderNodeMath', None, *nodePos)
			greaterThanNode.operation = 'GREATER_THAN'
			mixNode, x, nodePos[1] = addNodeAt(group_tree, 
				'ShaderNodeMixRGB', None, mixNodeX, nodePos[1])
			
			group_tree.links.new(greaterThanNode.inputs[0], caseNodeInternal)
			group_tree.links.new(mixNode.inputs[0], 
				greaterThanNode.outputs[0])
			greaterThanNode.inputs[1].default_value = case
	   
			# Connect group input to nodes
			group_tree.links.new(mixNode.inputs[1], 
				internalSocketDict[name])
			group_tree.links.new(mixNode.inputs[2], 
				prevSocket)

			prevSocket = mixNode.outputs[0]

	group_tree.links.new(output_node.inputs[0], prevSocket)
	
	return groupNode

def createNodeCombiner(node_tree, nodeA, nodeB, nodeC, nodeD, location, isAlpha):
	# (A-B)*C + D
	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", name = 'Combiner')
	input_node = group_tree.nodes.new("NodeGroupInput")
	input_node.location = (-300, 0)
	output_node = group_tree.nodes.new("NodeGroupOutput")
	output_node.location = (600, 0)
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.node_tree = group_tree
	groupNode.location = location
	location[1] = location[1] - (groupNode.height + 100)

	# Add input source to group input
	socketType = 'NodeSocketColor' if not isAlpha else 'NodeSocketFloat'
	groupNode.inputs.new(socketType, 'A')
	input_node.outputs.new(socketType, 'A')
	inputA = groupNode.inputs[0]
	node_tree.links.new(inputA, nodeA.outputs[0])

	groupNode.inputs.new(socketType, 'B')
	input_node.outputs.new(socketType, 'B')
	inputB = groupNode.inputs[1]
	node_tree.links.new(inputB, nodeB.outputs[0])

	groupNode.inputs.new(socketType, 'C')
	input_node.outputs.new(socketType, 'C')
	inputC = groupNode.inputs[2]
	node_tree.links.new(inputC, nodeC.outputs[0])

	groupNode.inputs.new(socketType, 'D')
	input_node.outputs.new(socketType, 'D')
	inputD = groupNode.inputs[3]
	node_tree.links.new(inputD, nodeD.outputs[0])

	nodePos = [0,0]
	if not isAlpha:
		nodeSubtract, x, nodePos[1] = \
			addNodeAt(group_tree, 'ShaderNodeMixRGB', 'Subtract', *nodePos)
		nodeMultiply, x, nodePos[1] = \
			addNodeAt(group_tree, 'ShaderNodeMixRGB', 'Multiply', *nodePos)
		nodeAdd, x, nodePos[1] = \
			addNodeAt(group_tree, 'ShaderNodeMixRGB', 'Add', *nodePos)

		nodeSubtract.blend_type = 'SUBTRACT'
		nodeMultiply.blend_type = 'MULTIPLY'
		nodeAdd.blend_type = 'ADD'

		nodeSubtract.inputs['Fac'].default_value = 1
		nodeMultiply.inputs['Fac'].default_value = 1
		nodeAdd.inputs['Fac'].default_value = 1
	else:
		nodeSubtract, x, nodePos[1] = \
			addNodeAt(group_tree, 'ShaderNodeMath', 'Subtract', *nodePos)
		nodeMultiply, x, nodePos[1] = \
			addNodeAt(group_tree, 'ShaderNodeMath', 'Multiply', *nodePos)
		nodeAdd, x, nodePos[1] = \
			addNodeAt(group_tree, 'ShaderNodeMath', 'Add', *nodePos)

		nodeSubtract.operation = 'SUBTRACT'
		nodeMultiply.operation = 'MULTIPLY'
		nodeAdd.operation = 'ADD'

	index1 = 1 if not isAlpha else 0
	index2 = 2 if not isAlpha else 1
	group_tree.links.new(nodeSubtract.inputs[index1], input_node.outputs[0])
	group_tree.links.new(nodeSubtract.inputs[index2], input_node.outputs[1])
	group_tree.links.new(nodeMultiply.inputs[index1], nodeSubtract.outputs[0])
	group_tree.links.new(nodeMultiply.inputs[index2], input_node.outputs[2])
	group_tree.links.new(nodeAdd.inputs[index1], nodeMultiply.outputs[0])
	group_tree.links.new(nodeAdd.inputs[index2], input_node.outputs[3])

	output_node.inputs.new(socketType, 'Output')
	groupNode.outputs.new(socketType, 'Output')
	group_tree.links.new(output_node.inputs[0], nodeAdd.outputs[0])
	
	return groupNode

def createNodeFinal(node_tree, caseNodeDict, nodeDict, texAlphaList,
	texAlphaWithBridgeList, cycleIndex):
	group_tree = bpy.data.node_groups.new(
		type="ShaderNodeTree", name = 'Color Combiner')
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.node_tree = group_tree

	input_node = group_tree.nodes.new("NodeGroupInput")
	input_node.location = (-300, 0)
	output_node = group_tree.nodes.new("NodeGroupOutput")
	output_node.location = (900, 0)

	caseSocketDict, nextIndex = \
		nodeDictToInternalSocket(node_tree, groupNode, input_node, 
		caseNodeDict, [], [], 0)

	socketDict, nextIndex = \
		nodeDictToInternalSocket(node_tree, groupNode, input_node, 
		nodeDict, texAlphaList, texAlphaWithBridgeList, nextIndex)
	
	nodePos = [300, 0]

	caseNodes = {}
	for name, socket in caseSocketDict.items():
		caseNodes[name] = createNodeSwitch(group_tree, 
			[item[1] for item in combiner_enums[name[:-2]]],
			socket, name , nodePos, socketDict)

	nodePos = [600, 0]
	out1 = createNodeCombiner(
		group_tree, caseNodes['Case A ' + str(cycleIndex)], caseNodes['Case B ' + str(cycleIndex)], 
		caseNodes['Case C ' + str(cycleIndex)], caseNodes['Case D ' + str(cycleIndex)], nodePos, False)
	out_alpha1 = createNodeCombiner(group_tree, caseNodes['Case A Alpha ' + str(cycleIndex)],
		caseNodes['Case B Alpha ' + str(cycleIndex)], caseNodes['Case C Alpha '  + str(cycleIndex)], 
		caseNodes['Case D Alpha ' + str(cycleIndex)], nodePos, True)

	groupNode.outputs.new('NodeSocketColor', 'Color Combiner')
	output_node.inputs.new('NodeSocketColor', 'Color Combiner')
	groupNode.outputs.new('NodeSocketFloat', 'Color Combiner Alpha')
	output_node.inputs.new('NodeSocketFloat', 'Color Combiner Alpha')
	group_tree.links.new(output_node.inputs[0], out1.outputs[0])
	group_tree.links.new(output_node.inputs[1], out_alpha1.outputs[0])

	return groupNode

def createNodeToGroupLink(node, outputIndex, groupNode, groupInputNode,
	node_tree, nodeIndex, name):
	return createSocketToGroupLink(node.outputs[outputIndex], groupNode,
		groupInputNode, node_tree, nodeIndex, name)

def createSocketToGroupLink(socket, groupNode, groupInputNode, 
	node_tree, nodeIndex, name):
	inputType = str(type(socket))[18:-2] # convert class to string
	groupNode.inputs.new(inputType, name)
	groupInputNode.outputs.new(inputType, name)
	nodeExternal = groupNode.inputs[nodeIndex]
	node_tree.links.new(nodeExternal, socket)

	nodeInternal = groupInputNode.outputs[nodeIndex]
	return nodeInternal

def nodeDictToInternalSocket(node_tree, groupNode, groupInputNode, nodeDict, 
	texAlphaList, texAlphaWithBridgeList, startIndex):
	nodeIndex = startIndex
	newDict = {}
	for name, node in nodeDict.items():
		newDict[name] = createNodeToGroupLink(node, 0 if name != 'Noise' else 1,
			groupNode, groupInputNode, node_tree, nodeIndex, name)
		nodeIndex += 1
		if name in texAlphaList:
			newDict[name + " Alpha"] = createNodeToGroupLink(node, 1, groupNode,
				groupInputNode, node_tree, nodeIndex, name + " Alpha")
			nodeIndex += 1
		elif name in texAlphaWithBridgeList:
			alphaSplitNode = node.inputs[1].links[0].from_socket.node
			bridgeNode = alphaSplitNode.outputs[1].links[0].to_socket.node
			newDict[name + " Alpha"] = createNodeToGroupLink(bridgeNode, 0,
				groupNode, groupInputNode, node_tree, nodeIndex, 
				name + " Alpha")
			nodeIndex += 1

	return newDict, nodeIndex

def socketDictToInternalSocket(node_tree, groupNode, groupInputNode, socketDict, 
	startIndex):
	nodeIndex = startIndex
	newDict = {}
	for name, socket in socketDict.items():
		newDict[name] = createSocketToGroupLink(socket, groupNode, 
			groupInputNode, node_tree, nodeIndex, name)
		nodeIndex += 1

	return newDict

def createTexCoordNode(node_tree, location, uvSocket, isV):
	group_tree = bpy.data.node_groups.new(
		type="ShaderNodeTree", name = 'Create Tex Coord')
	links = group_tree.links
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.location = location
	groupNode.name = 'Create Tex Coord'
	location[1] = location[1] - (groupNode.height + 100)
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	output_node = group_tree.nodes.new("NodeGroupOutput")
	input_node.location = (-800, 0)
	output_node.location = (2800, 0)

	output_node.inputs.new('NodeSocketVector', 'UV')

	uvSocket = \
		createSocketToGroupLink(uvSocket, groupNode, 
		input_node, node_tree, 0, 'UV')
	
	normLNode, x, y = \
		addNodeAt(group_tree, 'ShaderNodeValue', 'Normalized L', -600, 0)
	normLSocket = normLNode.outputs[0]
	normLSocket.default_value = 0

	normHNode, x, y = \
		addNodeAt(group_tree, 'ShaderNodeValue', 'Normalized H', -600, y)
	normHSocket = normHNode.outputs[0]
	normHSocket.default_value = 1

	clampNode, x, y = \
		addNodeAt(group_tree, 'ShaderNodeValue', 'Clamp', -600, y)
	clampSocket = clampNode.outputs[0]
	clampSocket.default_value = 0

	normMaskNode, x, y = \
		addNodeAt(group_tree, 'ShaderNodeValue', 'Normalized Mask', -600, y)
	normMaskSocket = normMaskNode.outputs[0]
	normMaskSocket.default_value = 1

	mirrorNode, x, y = \
		addNodeAt(group_tree, 'ShaderNodeValue', 'Mirror', -600, y)
	mirrorSocket = mirrorNode.outputs[0]
	mirrorSocket.default_value = 0

	shiftNode, x, y = \
		addNodeAt(group_tree, 'ShaderNodeValue', 'Shift', -600, y)
	shiftSocket = shiftNode.outputs[0]
	shiftSocket.default_value = 0

	scaleNode, x, y = \
		addNodeAt(group_tree, 'ShaderNodeValue', 'Scale', -600, y)
	scaleSocket = scaleNode.outputs[0]
	scaleSocket.default_value = 1

	# Makes sure clamp works correctly
	normHalfPixelNode, x, y = \
		addNodeAt(group_tree, 'ShaderNodeValue','Normalized Half Pixel',-600, y)
	normHalfPixelSocket = normHalfPixelNode.outputs[0]
	normHalfPixelSocket.default_value = 1 / 64

	# Change origin to top left corner
	if isV:
		toUpperOrigin, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, -400, 200)
		toUpperOrigin.operation = "MULTIPLY_ADD"
		toUpperOrigin.inputs[1].default_value = -1
		toUpperOrigin.inputs[2].default_value = 1
		links.new(toUpperOrigin.inputs[0], uvSocket)
		prevSocket = toUpperOrigin.outputs[0]
	else:
		prevSocket = uvSocket

	# Apply shift
	shiftPower, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, -400, 0)
	shiftPower.operation = "POWER"
	shiftPower.inputs[0].default_value = 0.5
	links.new(shiftPower.inputs[1], shiftSocket)

	shiftMult, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, -400, -200)
	shiftMult.operation = 'MULTIPLY'
	links.new(shiftMult.inputs[0], prevSocket)
	links.new(shiftMult.inputs[1], shiftPower.outputs[0])

	# Apply scale
	scaleMult, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, -200,-200)
	scaleMult.operation = 'MULTIPLY'
	links.new(scaleMult.inputs[0], shiftMult.outputs[0])
	links.new(scaleMult.inputs[1], scaleSocket)

	# Revert origin to lower left corner
	if isV:
		toLowerOrigin, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, -200, -400)
		toLowerOrigin.operation = "MULTIPLY_ADD"
		toLowerOrigin.inputs[1].default_value = -1
		toLowerOrigin.inputs[2].default_value = 1
		links.new(toLowerOrigin.inputs[0], scaleMult.outputs[0])
		prevNode2 = toLowerOrigin
	else:
		prevNode2 = scaleMult
	
	# Add L
	# offsetting by L means subtracting L from UV
	addL, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 0, 0)
	addL.operation = 'SUBTRACT'
	links.new(addL.inputs[0], prevNode2.outputs[0])
	links.new(addL.inputs[1], normLSocket)

	# Clamp using H
	clampLow, x, y = addNodeAt(group_tree, 'ShaderNodeMath', 
		'Max of NOT zero', 200, 0)
	clampLow.operation = 'MAXIMUM'
	clampLow.inputs[0].default_value = 0.0000001 # so negative clamping works
	links.new(clampLow.inputs[0], normHalfPixelSocket)
	links.new(clampLow.inputs[1], addL.outputs[0])

	clampHighHalfPixelOffset, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 400, 200)
	clampHighHalfPixelOffset.operation = 'SUBTRACT'
	links.new(clampHighHalfPixelOffset.inputs[0], normHSocket)
	links.new(clampHighHalfPixelOffset.inputs[1], normHalfPixelSocket)

	clampHigh, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 400, 0)
	clampHigh.operation = 'MINIMUM'
	links.new(clampHigh.inputs[0], clampHighHalfPixelOffset.outputs[0])
	links.new(clampHigh.inputs[1], clampLow.outputs[0])

	clampMix, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 600, 0)
	links.new(clampMix.inputs[0], clampSocket)
	links.new(clampMix.inputs[1], addL.outputs[0])
	links.new(clampMix.inputs[2], clampHigh.outputs[0])

	# Apply mask 
	maskPositive, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 800,-400)
	maskPositive.operation = "MODULO"
	links.new(maskPositive.inputs[0], clampMix.outputs[0])
	links.new(maskPositive.inputs[1], normMaskSocket)

	ifNegative, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 800, 0)
	ifNegative.operation = 'LESS_THAN'
	links.new(ifNegative.inputs[0], clampMix.outputs[0])
	ifNegative.inputs[1].default_value = 0

	maskNegative, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 800,-200)
	links.new(maskNegative.inputs[0], normMaskSocket)
	links.new(maskNegative.inputs[1], maskPositive.outputs[0])

	maskSignMix, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB',None,1000,-200)
	links.new(maskSignMix.inputs[0], ifNegative.outputs[0])
	links.new(maskSignMix.inputs[1], maskPositive.outputs[0])
	links.new(maskSignMix.inputs[2], maskNegative.outputs[0])

	# Apply mirror
	mirrorAbs, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 1000,-600)
	mirrorAbs.operation = "ABSOLUTE"
	links.new(mirrorAbs.inputs[0], clampMix.outputs[0])
	mirrorAbs.inputs[1].default_value = 0

	mirrorMaskDiv, x, y = addNodeAt(group_tree, 'ShaderNodeMath',None,1200,-600)
	mirrorMaskDiv.operation = 'DIVIDE'
	links.new(mirrorMaskDiv.inputs[0], mirrorAbs.outputs[0])
	links.new(mirrorMaskDiv.inputs[1], normMaskSocket)

	mirrorFloor, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 1400,-600)
	mirrorFloor.operation = 'FLOOR'
	links.new(mirrorFloor.inputs[0], mirrorMaskDiv.outputs[0])
	mirrorFloor.inputs[1].default_value = 0

	mirrorMod, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 1600,-600)
	mirrorMod.operation = 'MODULO'
	links.new(mirrorMod.inputs[0], mirrorFloor.outputs[0])
	mirrorMod.inputs[1].default_value = 2

	mirrorSub, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 1600,-800)
	mirrorSub.operation = "SUBTRACT"
	mirrorSub.inputs[0].default_value = 1
	links.new(mirrorSub.inputs[1], mirrorMod.outputs[0])

	mirrorToggleMix, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', 
		None, 1800, -600)
	links.new(mirrorToggleMix.inputs[0], ifNegative.outputs[0])
	links.new(mirrorToggleMix.inputs[1], mirrorMod.outputs[0])
	links.new(mirrorToggleMix.inputs[2], mirrorSub.outputs[0])

	mirrorCheck, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 2000,-400)
	mirrorCheck.operation = 'MULTIPLY'
	links.new(mirrorCheck.inputs[0], mirrorToggleMix.outputs[0])
	links.new(mirrorCheck.inputs[1], mirrorSocket)

	mirrored, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 2000,-200)
	mirrored.operation = 'SUBTRACT'
	links.new(mirrored.inputs[0], normMaskSocket)
	links.new(mirrored.inputs[1], maskSignMix.outputs[0])

	mirrorMix, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 2200,-200)
	links.new(mirrorMix.inputs[0], mirrorCheck.outputs[0])
	links.new(mirrorMix.inputs[1], maskSignMix.outputs[0])
	links.new(mirrorMix.inputs[2], mirrored.outputs[0])

	# Handle 0 Mask
	check0Mask, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 800,-1000)
	check0Mask.operation = 'GREATER_THAN'
	links.new(check0Mask.inputs[0], normMaskSocket)
	check0Mask.inputs[1].default_value = 0

	mix0Mask, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 2400,-200)
	links.new(mix0Mask.inputs[0], check0Mask.outputs[0])
	links.new(mix0Mask.inputs[1], clampHigh.outputs[0])
	links.new(mix0Mask.inputs[2], mirrorMix.outputs[0])

	# Output
	links.new(output_node.inputs[0], mix0Mask.outputs[0])
	return groupNode

def createUVNode(node_tree, location, texGenNode, texGenLinearNode):
	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", name = 'Get UV')
	links = group_tree.links
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.location = location
	groupNode.name = 'Get UV'
	location[1] = location[1] - (groupNode.height + 100)
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	output_node = group_tree.nodes.new("NodeGroupOutput")
	input_node.location = (-300, 0)
	output_node.location = (2400, 0)

	output_node.inputs.new('NodeSocketVector', 'UV')

	internalTexGenSocket = \
		createSocketToGroupLink(texGenNode.outputs[0], groupNode, 
		input_node, node_tree, 0, 'Texture Generation Flag')
	internalTexGenLinearSocket = \
		createSocketToGroupLink(texGenLinearNode.outputs[0], groupNode,
		input_node, node_tree, 1, 'Texture Generation Linear Flag')

	# Regular UVs
	UVMapNode, x, y = addNodeAt(group_tree, 'ShaderNodeUVMap', None, 1200, 0)
	UVMapNode.uv_map = 'UVMap'

	# Texture size
	heightNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeValue", 'Image Height Factor', 
		-300, -400)
	widthNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeValue", 'Image Width Factor', 
		-300, -200)
	heightNode.outputs[0].default_value = 1024 / 32
	widthNode.outputs[0].default_value = 1024 / 32
	
	# Get normal
	geometryNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeNewGeometry", None, 0, 0)

	# Convert to screen space normal
	transformNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeVectorTransform", None, 0, y)
	transformNode.convert_from = 'WORLD'
	transformNode.convert_to = 'CAMERA'
	transformNode.vector_type = 'NORMAL'
	links.new(transformNode.inputs[0], geometryNode.outputs[1])

	# Convert [-1,1] to [0,1]
	addOneNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeVectorMath", None, 0, y)
	addOneNode.inputs[1].default_value = (1,1,1)
	links.new(addOneNode.inputs[0], transformNode.outputs[0])

	separateNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeSeparateXYZ", None, 0, y)
	links.new(separateNode.inputs[0], addOneNode.outputs[0])

	divideTwoX, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 300, 200)
	divideTwoY, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 300, y)
	divideTwoX.operation = 'DIVIDE'
	divideTwoY.operation = 'DIVIDE'
	divideTwoX.inputs[1].default_value = -2	# Must be negative (env, not sphere)
	divideTwoY.inputs[1].default_value = -2
	links.new(divideTwoX.inputs[0], separateNode.outputs[0])
	links.new(divideTwoY.inputs[0], separateNode.outputs[1])

	# Normalize values based on tex size.
	normalizeX, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 300, y)
	normalizeY, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 300, y)
	normalizeX.operation = 'MULTIPLY'
	normalizeY.operation = 'MULTIPLY'
	links.new(normalizeX.inputs[0], divideTwoX.outputs[0])
	links.new(normalizeY.inputs[0], divideTwoY.outputs[0])
	links.new(normalizeX.inputs[1], widthNode.outputs[0])
	links.new(normalizeY.inputs[1], heightNode.outputs[0])

	# Get UVs for tex gen, scaled by texture scale.

	texGenCombine, x, y = \
		addNodeAt(group_tree, 'ShaderNodeCombineXYZ', None, 1200, -300)
	links.new(texGenCombine.inputs[0], normalizeX.outputs[0])
	links.new(texGenCombine.inputs[1], normalizeY.outputs[0])

	# Get UVs for tex gen linear, scaled by texture scale.
	texGenLinearAcosX, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 600, -600)
	texGenLinearAcosY, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 600, y)
	texGenLinearAcosX.operation = 'ARCCOSINE'
	texGenLinearAcosY.operation = 'ARCCOSINE'
	links.new(texGenLinearAcosX.inputs[0], divideTwoX.outputs[0])
	links.new(texGenLinearAcosY.inputs[0], divideTwoY.outputs[0])
	texGenLinearAcosX.inputs[1].default_value = 0
	texGenLinearAcosY.inputs[1].default_value = 0

	# Normalize values based on tex size.
	normalizeLinearX, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 600, y)
	normalizeLinearY, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 600, y)
	normalizeLinearX.operation = 'MULTIPLY'
	normalizeLinearY.operation = 'MULTIPLY'
	links.new(normalizeLinearX.inputs[0], texGenLinearAcosX.outputs[0])
	links.new(normalizeLinearY.inputs[0], texGenLinearAcosY.outputs[0])
	links.new(normalizeLinearX.inputs[1], widthNode.outputs[0])
	links.new(normalizeLinearY.inputs[1], heightNode.outputs[0])

	texGenLinearCombine, x, y = \
		addNodeAt(group_tree, 'ShaderNodeCombineXYZ', None, 1200, -600)
	links.new(texGenLinearCombine.inputs[0], normalizeLinearX.outputs[0])
	links.new(texGenLinearCombine.inputs[1], normalizeLinearY.outputs[0])

	# Mix UV based on flags
	mixTexGen, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 1500, 0)
	links.new(mixTexGen.inputs[0], internalTexGenSocket)
	links.new(mixTexGen.inputs[1], UVMapNode.outputs[0])
	links.new(mixTexGen.inputs[2], texGenCombine.outputs[0])
	
	mixTexGenLinear, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 1500, y)
	links.new(mixTexGenLinear.inputs[0], internalTexGenLinearSocket)
	links.new(mixTexGenLinear.inputs[1], mixTexGen.outputs[0])
	links.new(mixTexGenLinear.inputs[2], texGenLinearCombine.outputs[0])

	# Apply tile attributes
	uvSplit, x, y = \
		addNodeAt(group_tree, 'ShaderNodeSeparateXYZ', None, 1800, 500)
	links.new(uvSplit.inputs[0], mixTexGenLinear.outputs[0])
	
	uv_xNode = createTexCoordNode(group_tree, [2000, 500], uvSplit.outputs[0], False)
	uv_yNode = createTexCoordNode(group_tree, [2000, 300], uvSplit.outputs[1], True)

	links.new(uv_xNode.inputs[0], uvSplit.outputs[0])
	links.new(uv_yNode.inputs[0], uvSplit.outputs[1])

	uvCombine, x, y = \
		addNodeAt(group_tree, 'ShaderNodeCombineXYZ', None, 2200, 500)

	links.new(uvCombine.inputs[0], uv_xNode.outputs[0])
	links.new(uvCombine.inputs[1], uv_yNode.outputs[0])

	links.new(output_node.inputs[0], uvCombine.outputs[0])
	return groupNode
	
def createShadeNode(node_tree, location, shadingNode, lightingNode, ambientNode):
	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", 
		name = 'Get Shade Color')
	links = group_tree.links
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.name = 'Shade Color'
	groupNode.label = 'Shade Color'
	groupNode.location = location
	location[1] = location[1] - (groupNode.height + 100)
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	output_node = group_tree.nodes.new("NodeGroupOutput")
	input_node.location = (-300, 0)
	output_node.location = (600, 0)

	shadingNodeInternal = createSocketToGroupLink(shadingNode.outputs[0], 
		groupNode, input_node, node_tree, 0, 'Shading')
	lightingNodeInternal = createSocketToGroupLink(lightingNode.outputs[0], 
		groupNode, input_node, node_tree, 1, 'Lighting')
	ambientInternal = createSocketToGroupLink(ambientNode.outputs[0], 
		groupNode, input_node, node_tree, 2, 'Ambient Color')
	groupNode.outputs.new('NodeSocketColor', 'Color')
	output_node.inputs.new('NodeSocketColor', 'Color')
	groupNode.outputs.new('NodeSocketFloat', 'Alpha')
	output_node.inputs.new('NodeSocketFloat', 'Alpha')

	diffuseNode, x, y = addNodeAt(group_tree, 'ShaderNodeBsdfDiffuse', None, 0, 0)
	colorNode, x, y = addNodeAt(group_tree, 'ShaderNodeRGB', None, 0, y)
	toRGBNode, x, y = addNodeAt(group_tree, 'ShaderNodeShaderToRGB', None, 200, 0)
	vertColorNode, x, y = addNodeAt(group_tree,'ShaderNodeAttribute',None, 200, y)
	vertAlphaNode, x, y = addNodeAt(group_tree,'ShaderNodeAttribute',None, 200, y)

	addAmbient, x, y = \
		addNodeAt(group_tree, 'ShaderNodeVectorMath', None, 400, 0)

	mixRGB, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 600, 0)
	mixRGBShadeless, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', None,600, y)
	mixAlpha, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 600, y)

	colorNode.outputs[0].default_value = (1,1,1,1)
	vertColorNode.attribute_name = 'Col'
	vertAlphaNode.attribute_name = 'Alpha'

	#links.new(diffuseNode.inputs[0], ambientInternal)
	links.new(toRGBNode.inputs[0], diffuseNode.outputs[0])
	links.new(addAmbient.inputs[0], ambientInternal)
	links.new(addAmbient.inputs[1], toRGBNode.outputs[0])
	links.new(mixRGB.inputs[0], lightingNodeInternal)
	links.new(mixRGB.inputs[1], vertColorNode.outputs[0])
	links.new(mixRGB.inputs[2], addAmbient.outputs[0])

	links.new(mixRGBShadeless.inputs[0], shadingNodeInternal)
	links.new(mixRGBShadeless.inputs[1], colorNode.outputs[0])
	links.new(mixRGBShadeless.inputs[2], mixRGB.outputs[0])

	links.new(mixAlpha.inputs[0], lightingNodeInternal)
	links.new(mixAlpha.inputs[1], vertAlphaNode.outputs[2])
	links.new(mixAlpha.inputs[2], toRGBNode.outputs[1])

	links.new(output_node.inputs[0], mixRGBShadeless.outputs[0])
	links.new(output_node.inputs[1], mixAlpha.outputs[0])

	return groupNode

def createTexFormatNodes(node_tree, location, index, nodeDict):
	# Add texture format mixes
	nodes = node_tree.nodes
	links = node_tree.links

	greyNode, x, y = addNodeAt(node_tree, 'ShaderNodeSeparateHSV', 
		None, location[0], location[1])
	links.new(greyNode.inputs[0], nodes['Texture ' + str(index)].outputs[0])

	isGreyScale, x, y = addNodeAt(node_tree, 'ShaderNodeValue', 
		"Texture " + str(index) + " Is Greyscale", location[0], y)
	isGreyScale.outputs[0].default_value = 0
	hasAlpha, x, y = addNodeAt(node_tree, 'ShaderNodeValue', 
		'Texture ' + str(index) + ' Has Alpha', location[0], y)
	hasAlpha.outputs[0].default_value = 1
	isIntensity, x, y = addNodeAt(node_tree, 'ShaderNodeValue', 
		'Texture ' + str(index) + ' Is Intensity', location[0], y)
	isIntensity.outputs[0].default_value = 0

	greyMix, x, y = addNodeAt(node_tree, 'ShaderNodeMixRGB', 
		None, location[0], y)
	links.new(greyMix.inputs[0], isGreyScale.outputs[0])
	links.new(greyMix.inputs[1], nodes['Texture ' + str(index)].outputs[0])
	links.new(greyMix.inputs[2], greyNode.outputs[2])
	nodeDict['Texture ' + str(index)] = greyMix

	alphaMix, x, y = addNodeAt(node_tree, 'ShaderNodeMixRGB', 
		None, location[0], y)
	links.new(alphaMix.inputs[0], hasAlpha.outputs[0])
	links.new(alphaMix.inputs[2], nodes['Texture ' + str(index)].outputs[1])
	alphaMix.inputs[1].default_value = (1,1,1,1)

	alphaMixIntensity, x, y = addNodeAt(node_tree, 'ShaderNodeMixRGB', 
		None, location[0], y)
	links.new(alphaMixIntensity.inputs[0], isIntensity.outputs[0])
	links.new(alphaMixIntensity.inputs[1], alphaMix.outputs[0])
	links.new(alphaMixIntensity.inputs[2], greyNode.outputs[2])
	nodeDict['Texture ' + str(index) + ' Alpha'] = alphaMixIntensity

	return y

'''
class F3DLightCollectionProperty(bpy.types.PropertyGroup):
	light1 : bpy.props.PointerProperty(type = bpy.types.Light)
	light2 : bpy.props.PointerProperty(type = bpy.types.Light)
	light3 : bpy.props.PointerProperty(type = bpy.types.Light)
	light4 : bpy.props.PointerProperty(type = bpy.types.Light)
	light5 : bpy.props.PointerProperty(type = bpy.types.Light)
	light6 : bpy.props.PointerProperty(type = bpy.types.Light)
	light7 : bpy.props.PointerProperty(type = bpy.types.Light)
'''

			
class GetAlphaFromColor(ShaderNode):

	bl_idname = 'GetAlphaFromColor'
	# Label for nice name display
	bl_label = "Get Alpha From Color"
	# Icon identifier
	bl_icon = 'NODE'

	def update_GetAlphaFromColor(self, context):
		inputSocket = self.inputs[0]
		if inputSocket.is_linked:
			for link in inputSocket.links:
				if link.is_valid:
					self.inputs[0].default_value = \
						link.from_socket.default_value
						
		if len(self.outputs) >= 2:
			out = self.outputs[0]
			if out.is_linked:
				for link in out.links:
					if link.is_valid:
						link.to_socket.default_value = self.inputs[0].default_value

			outAlpha = self.outputs[1]
			if outAlpha.is_linked:
				for link in outAlpha.links:
					if link.is_valid:
						link.to_socket.default_value = self.inputs[0].default_value[3]

	inColor : bpy.props.FloatVectorProperty(
		name = 'Input Color', subtype='COLOR', size = 4,
		update = update_GetAlphaFromColor)

	def init(self, context):
		self.inputs.new("NodeSocketColor", "Input Color")
		self.outputs.new("NodeSocketColor", "Output Color")
		self.outputs.new("NodeSocketFloat", "Output Alpha")

	# Copy function to initialize a copied node from an existing one.
	def copy(self, node):
		print("Copying from node ", node)

	# Free function to clean up on removal.
	def free(self):
		print("Removing node ", self, ", Goodbye!")

	# Additional buttons displayed on the node.
	def draw_buttons(self, context, layout):
		pass
		#layout.prop(self, 'inA')

	def draw_label(self):
		return "Get Alpha From Color"
	
	def update(self):
		inputSocket = self.inputs[0]
		if inputSocket.is_linked:
			for link in inputSocket.links:
				if link.is_valid:
					self.inputs[0].default_value = \
						link.from_socket.default_value

		if len(self.outputs) >= 2:
			out = self.outputs[0]
			if out.is_linked:
				for link in out.links:
					if link.is_valid:
						link.to_socket.default_value = self.inputs[0].default_value

			outAlpha = self.outputs[1]
			if outAlpha.is_linked:
				for link in outAlpha.links:
					if link.is_valid:
						link.to_socket.default_value = self.inputs[0].default_value[3]

class F3DNodeA(ShaderNode):

	bl_idname = 'Fast3D_A'
	# Label for nice name display
	bl_label = "Case A"
	# Icon identifier
	bl_icon = 'NODE'

	def update_F3DNodeA(self, context):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).CCMUXDict[self.inA]

	inA : bpy.props.EnumProperty(name = "A", description = "A",
		items = combiner_enums['Case A'], default = 'TEXEL0', update = update_F3DNodeA)

	def init(self, context):
		self.outputs.new("NodeSocketInt", "A")

	# Copy function to initialize a copied node from an existing one.
	def copy(self, node):
		print("Copying from node ", node)

	# Free function to clean up on removal.
	def free(self):
		print("Removing node ", self, ", Goodbye!")

	# Additional buttons displayed on the node.
	def draw_buttons(self, context, layout):
		layout.prop(self, 'inA')

	def draw_label(self):
		return "Fast3D Node A"
	
	def update(self):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).CCMUXDict[self.inA]

class F3DNodeB(ShaderNode):

	bl_idname = 'Fast3D_B'
	# Label for nice name display
	bl_label = "Case B"
	# Icon identifier
	bl_icon = 'NODE'

	def update_F3DNodeB(self, context):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).CCMUXDict[self.inB]

	inB : bpy.props.EnumProperty(name = "B", description = "B",
		items = combiner_enums['Case B'], default = '0', update = update_F3DNodeB)

	def init(self, context):
		self.outputs.new("NodeSocketInt", "B")

	# Copy function to initialize a copied node from an existing one.
	def copy(self, node):
		print("Copying from node ", node)

	# Free function to clean up on removal.
	def free(self):
		print("Removing node ", self, ", Goodbye!")

	# Additional buttons displayed on the node.
	def draw_buttons(self, context, layout):
		layout.prop(self, 'inB')

	def draw_label(self):
		return "Fast3D Node B"
	
	def update(self):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).CCMUXDict[self.inB]
		
class F3DNodeC(ShaderNode):

	bl_idname = 'Fast3D_C'
	# Label for nice name display
	bl_label = "Case C"
	# Icon identifier
	bl_icon = 'NODE'

	def update_F3DNodeC(self, context):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).CCMUXDict[self.inC]

	inC : bpy.props.EnumProperty(name = "C", description = "C",
		items = combiner_enums['Case C'], default = 'SHADE', update = update_F3DNodeC)

	def init(self, context):
		self.outputs.new("NodeSocketInt", "C")

	# Copy function to initialize a copied node from an existing one.
	def copy(self, node):
		print("Copying from node ", node)

	# Free function to clean up on removal.
	def free(self):
		print("Removing node ", self, ", Goodbye!")

	# Additional buttons displayed on the node.
	def draw_buttons(self, context, layout):
		layout.prop(self, 'inC')

	def draw_label(self):
		return "Fast3D Node C"
	
	def update(self):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).CCMUXDict[self.inC]

class F3DNodeD(ShaderNode):

	bl_idname = 'Fast3D_D'
	# Label for nice name display
	bl_label = "Case D"
	# Icon identifier
	bl_icon = 'NODE'

	def update_F3DNodeD(self, context):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).CCMUXDict[self.inD]

	inD : bpy.props.EnumProperty(name = "D", description = "D",
		items = combiner_enums['Case D'], default = '0', update = update_F3DNodeD)

	def init(self, context):
		self.outputs.new("NodeSocketInt", "D")

	# Copy function to initialize a copied node from an existing one.
	def copy(self, node):
		print("Copying from node ", node)

	# Free function to clean up on removal.
	def free(self):
		print("Removing node ", self, ", Goodbye!")

	# Additional buttons displayed on the node.
	def draw_buttons(self, context, layout):
		layout.prop(self, 'inD')

	def draw_label(self):
		return "Fast3D Node D"
	
	def update(self):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).CCMUXDict[self.inD]

class F3DNodeA_alpha(ShaderNode):

	bl_idname = 'Fast3D_A_alpha'
	# Label for nice name display
	bl_label = "Case A Alpha"
	# Icon identifier
	bl_icon = 'NODE'

	def update_F3DNodeA_alpha(self, context):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).ACMUXDict[self.inA_alpha]

	inA_alpha : bpy.props.EnumProperty(name = "A Alpha", 
		description = "A Alpha", items = combiner_enums['Case A Alpha'], 
		default = '0', update = update_F3DNodeA_alpha)

	def init(self, context):
		self.outputs.new("NodeSocketInt", "A Alpha")

	# Copy function to initialize a copied node from an existing one.
	def copy(self, node):
		print("Copying from node ", node)

	# Free function to clean up on removal.
	def free(self):
		print("Removing node ", self, ", Goodbye!")

	# Additional buttons displayed on the node.
	def draw_buttons(self, context, layout):
		layout.prop(self, 'inA_alpha')

	def draw_label(self):
		return "Fast3D Node A Alpha"
	
	def update(self):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).ACMUXDict[self.inA_alpha]

class F3DNodeB_alpha(ShaderNode):

	bl_idname = 'Fast3D_B_alpha'
	# Label for nice name display
	bl_label = "Case B Alpha"
	# Icon identifier
	bl_icon = 'NODE'

	def update_F3DNodeB_alpha(self, context):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).ACMUXDict[self.inB_alpha]

	inB_alpha : bpy.props.EnumProperty(name = "B Alpha", description = "B Alpha",
		items = combiner_enums['Case B Alpha'], default = '0', update = update_F3DNodeB_alpha)

	def init(self, context):
		self.outputs.new("NodeSocketInt", "B Alpha")

	# Copy function to initialize a copied node from an existing one.
	def copy(self, node):
		print("Copying from node ", node)

	# Free function to clean up on removal.
	def free(self):
		print("Removing node ", self, ", Goodbye!")

	# Additional buttons displayed on the node.
	def draw_buttons(self, context, layout):
		layout.prop(self, 'inB_alpha')

	def draw_label(self):
		return "Fast3D Node B Alpha"
	
	def update(self):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).ACMUXDict[self.inB_alpha]

class F3DNodeC_alpha(ShaderNode):

	bl_idname = 'Fast3D_C_alpha'
	# Label for nice name display
	bl_label = "Case C Alpha"
	# Icon identifier
	bl_icon = 'NODE'

	def update_F3DNodeC_alpha(self, context):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).ACMUXDict[self.inC_alpha]

	inC_alpha : bpy.props.EnumProperty(name = "C Alpha", description = "C Alpha",
		items = combiner_enums['Case C Alpha'], default = '0', update = update_F3DNodeC_alpha)

	def init(self, context):
		self.outputs.new("NodeSocketInt", "C Alpha")

	# Copy function to initialize a copied node from an existing one.
	def copy(self, node):
		print("Copying from node ", node)

	# Free function to clean up on removal.
	def free(self):
		print("Removing node ", self, ", Goodbye!")

	# Additional buttons displayed on the node.
	def draw_buttons(self, context, layout):
		layout.prop(self, 'inC_alpha')

	def draw_label(self):
		return "Fast3D Node C Alpha"
	
	def update(self):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).ACMUXDict[self.inC_alpha]

class F3DNodeD_alpha(ShaderNode):

	bl_idname = 'Fast3D_D_alpha'
	# Label for nice name display
	bl_label = "Case D Alpha"
	# Icon identifier
	bl_icon = 'NODE'

	def update_F3DNodeD_alpha(self, context):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = F3D('F3D', False).ACMUXDict[self.inD_alpha]

	inD_alpha : bpy.props.EnumProperty(name = "D Alpha", description = "D Alpha",
		items = combiner_enums['Case D Alpha'], default = 'ENVIRONMENT', update = update_F3DNodeD_alpha)

	def init(self, context):
		self.outputs.new("NodeSocketInt", "D Alpha")

	# Copy function to initialize a copied node from an existing one.
	def copy(self, node):
		print("Copying from node ", node)

	# Free function to clean up on removal.
	def free(self):
		print("Removing node ", self, ", Goodbye!")

	# Additional buttons displayed on the node.
	def draw_buttons(self, context, layout):
		layout.prop(self, 'inD_alpha')

	def draw_label(self):
		return "Fast3D Node D Alpha"
	
	def update(self):
		out = self.outputs[0]
		if out.is_linked:
			for link in out.links:
				if link.is_valid:
					link.to_socket.default_value = \
						F3D('F3D', False).ACMUXDict[self.inD_alpha]
