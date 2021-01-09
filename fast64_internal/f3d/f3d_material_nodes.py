import bpy, math, mathutils, nodeitems_utils
from bpy.types import Node, NodeSocket, NodeSocketInterface, ShaderNode, ShaderNodeGroup, Panel
from nodeitems_utils import NodeCategory, NodeItem
from .f3d_gbi import F3D
from .f3d_enums import *
from bpy.utils import register_class, unregister_class

def createGroupLink(node_tree, inputSocket, outputSocket, outputType, outputName):
	if outputType is not None:
		node_tree.outputs.new(outputType, outputName)
	node_tree.links.new(inputSocket, outputSocket)

def addColorWithAlphaNode(label, x, y, node_tree):
	alphaSplitNode = node_tree.nodes.new('GetAlphaFromColor')
	alphaSplitNode.location = (x-300, y)
	alphaSplitNode.name = label + " Output"
	
	addNode = node_tree.nodes.new('ShaderNodeMath')
	addNode.operation = 'ADD'
	addNode.inputs[1].default_value = 0
	node_tree.links.new(addNode.inputs[0], alphaSplitNode.outputs[1])
	addNode.location = (x,y)
	addNode.name = label + ' Alpha'

	mixNode = node_tree.nodes.new('ShaderNodeMixRGB')
	mixNode.inputs[0].default_value = 0
	node_tree.links.new(mixNode.inputs[1], alphaSplitNode.outputs[0])
	mixNode.location = (x,y - 100)
	mixNode.name = label + ' RGB'

	y -= 100
	return x, y, alphaSplitNode

def addNodeAt(node_tree, name, label, x, y, nodeKey = None, nodeDict = None):
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
	elif label == 'Noise':
		node.inputs[1].default_value = 40 # scale
		node.inputs[2].default_value = 0 # detail

	if nodeDict is not None:
		if name in nodeDict:
			raise ValueError(name + " already in the node dictionary.")
		if nodeKey is not None:
			nodeDict[nodeKey] = node
		else:
			nodeDict[name] = node
	return (node, x, y - (node.height))

def addNodeListAt(node_tree, nodeDict, x,y, cycleIndex = None):
	newDict = {}
	for label, typename in nodeDict.items():
		if cycleIndex is not None:
			name = label + " " + str(cycleIndex)
		else:
			name = label
		node, xDiscard, y = addNodeAt(node_tree, typename, name, x, y)
		newDict[name] = node
	return newDict, x, y

def addSocketList(groupNode, groupInputNode, socketDict, cycleIndex = None):
	newDict = {}
	for label, typename in socketDict.items():
		if cycleIndex is not None:
			name = label + " " + str(cycleIndex)
		else:
			name = label
		#addNodeAt(node_tree, typename, name, x, y)
		groupNode.inputs.new(typename, name)
		groupInputNode.outputs.new(typename, name)

		# We want to get the new output socket.
		# new() doesn't actually return the socket, so we must index the collection.
		# -1 is the index for the virtual socket at the end, so we want -2 instead.
		outputSocket = groupInputNode.outputs[-2]
		
		newDict[name] = outputSocket
	return newDict

# In 2.8 the Node.update function does not work.
# We can bypass this by adding an update callback to a property in the node.
# However, forcing an output socket update does NOT work when the output
# is a group node input. Thus we must add an "add" bridge node in between to fix this.
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
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.location = location
	location[1] = location[1] - (groupNode.height + 100)

	createGroup = 'Switch ' + caseName + ' F3D v3' not in bpy.data.node_groups
	if not createGroup:
		group_tree = bpy.data.node_groups["Switch " + caseName + " F3D v3"]
		groupNode.node_tree = group_tree

		node_tree.links.new(groupNode.inputs[0], caseSocket)
		internalSocketDict, nextSocketIndex = socketDictToInternalSocket(node_tree, 
			groupNode, None, socketDict, 1, False)
		return groupNode

	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", name = 'Switch ' + caseName + ' F3D v3')
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

	internalSocketDict, nextSocketIndex = socketDictToInternalSocket(node_tree, 
		groupNode, input_node, socketDict, 1, True)

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

def createNodeCombinerMix(node_tree, nodeASocket, nodeBSocket, nodeCSocket, nodeDSocket, location, isAlpha):
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.location = location
	location[1] = location[1] - (groupNode.height + 100)

	alphaText = 'Alpha ' if isAlpha else ''

	createGroup = 'Color Combiner ' + alphaText + 'Mix F3D v3' not in bpy.data.node_groups
	if not createGroup:
		group_tree = bpy.data.node_groups['Color Combiner ' + alphaText + 'Mix F3D v3']
		groupNode.node_tree = group_tree
		
		inputA = groupNode.inputs[0]
		node_tree.links.new(inputA, nodeASocket)

		inputB = groupNode.inputs[1]
		node_tree.links.new(inputB, nodeBSocket)

		inputC = groupNode.inputs[2]
		node_tree.links.new(inputC, nodeCSocket)

		inputD = groupNode.inputs[3]
		node_tree.links.new(inputD, nodeDSocket)

		return groupNode

	# (A-B)*C + D
	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", name = 'Color Combiner ' + alphaText + 'Mix F3D v3')
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	input_node.location = (-300, 0)
	output_node = group_tree.nodes.new("NodeGroupOutput")
	output_node.location = (600, 0)

	# Add input source to group input
	socketType = 'NodeSocketColor' if not isAlpha else 'NodeSocketFloat'
	groupNode.inputs.new(socketType, 'A')
	input_node.outputs.new(socketType, 'A')
	inputA = groupNode.inputs[0]
	node_tree.links.new(inputA, nodeASocket)

	groupNode.inputs.new(socketType, 'B')
	input_node.outputs.new(socketType, 'B')
	inputB = groupNode.inputs[1]
	node_tree.links.new(inputB, nodeBSocket)

	groupNode.inputs.new(socketType, 'C')
	input_node.outputs.new(socketType, 'C')
	inputC = groupNode.inputs[2]
	node_tree.links.new(inputC, nodeCSocket)

	groupNode.inputs.new(socketType, 'D')
	input_node.outputs.new(socketType, 'D')
	inputD = groupNode.inputs[3]
	node_tree.links.new(inputD, nodeDSocket)

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

# caseSocketDict is Case A-D for color and alpha
# socketDict is all color sources
def createNodeCombiner(node_tree, cycleIndex):
	groupNode = node_tree.nodes.new("ShaderNodeGroup")

	createGroup = 'Color Combiner F3D v3' not in bpy.data.node_groups
	if not createGroup:
		group_tree = bpy.data.node_groups['Color Combiner F3D v3']
		groupNode.node_tree = group_tree
		groupNode.name = 'Color Combiner Cycle ' + str(cycleIndex) + ' F3D v3'

		#caseSocketDict, nextIndex = \
		#	socketDictToInternalSocket(node_tree, groupNode, None, caseSocketDict, 0, False)

		#socketDict, nextIndex = \
		#	socketDictToInternalSocket(node_tree, groupNode, None, socketDict, nextIndex, False)

		return groupNode

	group_tree = bpy.data.node_groups.new(
		type="ShaderNodeTree", name = 'Color Combiner F3D v3')
	groupNode.node_tree = group_tree
	groupNode.name = 'Color Combiner Cycle ' + str(cycleIndex) + ' F3D v3'
	input_node = group_tree.nodes.new("NodeGroupInput")
	input_node.location = (-300, 0)
	output_node = group_tree.nodes.new("NodeGroupOutput")
	output_node.location = (900, 0)

	caseSocketDict = addSocketList(groupNode, input_node, caseTemplateDict, cycleIndex)
	#caseSocketDict, nextIndex = \
	#	socketDictToInternalSocket(node_tree, groupNode, input_node, caseSocketDict, 0, True)

	#socketDict, nextIndex = \
	#	socketDictToInternalSocket(node_tree, groupNode, input_node, socketDict, nextIndex, True)
	
	nodePos = [300, 0]

	# Creating switch cascade
	#caseNodes = {}
	#for name, socket in caseSocketDict.items():
	#	caseNodes[name] = createNodeSwitch(group_tree, 
	#		[item[1] for item in combiner_enums[name[:-2]]],
	#		socket, name[:-2] , nodePos, socketDict)

	nodePos = [600, 0]
	out1 = createNodeCombinerMix(
		group_tree, caseSocketDict['Case A ' + str(cycleIndex)], caseSocketDict['Case B ' + str(cycleIndex)], 
		caseSocketDict['Case C ' + str(cycleIndex)], caseSocketDict['Case D ' + str(cycleIndex)], nodePos, False)
	out_alpha1 = createNodeCombinerMix(group_tree, caseSocketDict['Case A Alpha ' + str(cycleIndex)],
		caseSocketDict['Case B Alpha ' + str(cycleIndex)], caseSocketDict['Case C Alpha '  + str(cycleIndex)], 
		caseSocketDict['Case D Alpha ' + str(cycleIndex)], nodePos, True)

	groupNode.outputs.new('NodeSocketColor', 'Color Combiner')
	output_node.inputs.new('NodeSocketColor', 'Color Combiner')
	groupNode.outputs.new('NodeSocketFloat', 'Color Combiner Alpha')
	output_node.inputs.new('NodeSocketFloat', 'Color Combiner Alpha')
	group_tree.links.new(output_node.inputs[0], out1.outputs[0])
	group_tree.links.new(output_node.inputs[1], out_alpha1.outputs[0])

	return groupNode

# caseNodeDict is the A-D for color and alpha
# nodeDict is all sources
# otherDict is other shader inputs
def createNodeF3D(node_tree, location):
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.location = location
	groupNode.name = 'F3D v3'
	location[1] = location[1] - (groupNode.height + 100)

	createGroup = 'F3D v3' not in bpy.data.node_groups
	if not createGroup:
		group_tree = bpy.data.node_groups['F3D v3']
		groupNode.node_tree = group_tree

		#caseSocketDict1, nextIndex = \
		#	nodeDictToInternalSocket(node_tree, groupNode, None, 
		#	caseNodeDict1, [], [], 0, False)

		#caseSocketDict2, nextIndex = \
		#	nodeDictToInternalSocket(node_tree, groupNode, None, 
		#	caseNodeDict2, [], [], nextIndex, False)

		#socketDict, nextIndex = \
		#	nodeDictToInternalSocket(node_tree, groupNode, None, 
		#	nodeDict, ['Combined Color', 'Shade Color', "Texture 0", "Texture 1"], 
		#	['Environment Color', 'Primitive Color'], nextIndex, False)

		#otherSocketDict, nextIndex = \
		#	nodeDictToInternalSocket(node_tree, groupNode, None, 
		#	otherDict, [], [], nextIndex, False)

		return groupNode, location[0], location[1]

	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", name = 'F3D v3')
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	output_node = group_tree.nodes.new("NodeGroupOutput")
	input_node.location = (-300, 0)
	output_node.location = (600, 0)
	links = group_tree.links

	#caseSocketDict1, nextIndex = \
	#	nodeDictToInternalSocket(node_tree, groupNode, input_node, 
	#	caseNodeDict1, [], [], 0, True)

	#caseSocketDict2, nextIndex = \
	#	nodeDictToInternalSocket(node_tree, groupNode, input_node, 
	#	caseNodeDict2, [], [], nextIndex, True)

	#socketDict, nextIndex = \
	#	nodeDictToInternalSocket(node_tree, groupNode, input_node, 
	#	nodeDict, ['Combined Color', 'Shade Color', "Texture 0", "Texture 1"], 
	#	['Environment Color', 'Primitive Color'], nextIndex, True)
	
	#otherSocketDict, nextIndex = \
	#	nodeDictToInternalSocket(node_tree, groupNode, input_node, 
	#	otherDict, [], [], nextIndex, True)

	#caseSocketDict1 = addSocketList(groupNode, input_node, caseTemplateDict, 1)
	#caseSocketDict2 = addSocketList(groupNode, input_node, caseTemplateDict, 2)

	#x = 0
	#y = 0
	#combiner1 = createNodeCombiner(group_tree, caseSocketDict1, 1)
	#combiner1.location = [x, y]
#
	#combiner2 = createNodeCombiner(group_tree, caseSocketDict2, 2)
	#combiner2.location = [x, y-800]

	addSocketList(groupNode, input_node, {
		"Cycle 1 RGB" : "NodeSocketColor",
		"Cycle 1 Alpha" : "NodeSocketFloat",
		"Cycle 2 RGB" : "NodeSocketColor",
		"Cycle 2 Alpha" : "NodeSocketFloat",
	})
	
	otherSocketDict = addSocketList(groupNode, input_node, otherTemplateDict)

	x = 0
	y = 0
	mixCycleNodeRGB, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMixRGB', 'Cycle Mix RGB', x, y)
	mixCycleNodeAlpha, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMixRGB', 'Cycle Mix Alpha', x, y)
	
	links.new(mixCycleNodeRGB.inputs[1], input_node.outputs[0])
	links.new(mixCycleNodeRGB.inputs[1], input_node.outputs[0])
	links.new(mixCycleNodeRGB.inputs[2], input_node.outputs[2])
	links.new(mixCycleNodeAlpha.inputs[1], input_node.outputs[1])
	links.new(mixCycleNodeAlpha.inputs[2], input_node.outputs[3])
	links.new(mixCycleNodeRGB.inputs[0], otherSocketDict['Cycle Type'])
	links.new(mixCycleNodeAlpha.inputs[0], otherSocketDict['Cycle Type'])

	x += 300
	y = 0
	
	backFacing, x, y = \
		addNodeAt(group_tree, 'ShaderNodeNewGeometry', 'Is Backfacing', 
		x, y)
	
	x += 300
	y = 0
	multCullFront,x,y = \
		addNodeAt(group_tree, 'ShaderNodeMath','Multiply Cull Front', x, y)
	multCullFront.operation = 'MULTIPLY'
	multCullBack,x,y = \
		addNodeAt(group_tree, 'ShaderNodeMath','Multiply Cull Back', x, y)
	multCullBack.operation = 'MULTIPLY'

	finalCullAlpha,x,y = \
		addNodeAt(group_tree, 'ShaderNodeMixRGB','Cull Alpha', x, y)

	links.new(multCullFront.inputs[0], otherSocketDict['Cull Front'])
	links.new(multCullBack.inputs[0], otherSocketDict['Cull Back'])
	links.new(multCullFront.inputs[1], mixCycleNodeAlpha.outputs[0])
	links.new(multCullBack.inputs[1], mixCycleNodeAlpha.outputs[0])
	links.new(finalCullAlpha.inputs[0], backFacing.outputs[6])
	links.new(finalCullAlpha.inputs[1], multCullFront.outputs[0])
	links.new(finalCullAlpha.inputs[2], multCullBack.outputs[0])	

	# Create mix shader to allow for alpha blending
	# we cannot input alpha directly to material output, but we can mix between
	# our final color and a completely transparent material based on alpha

	x += 300
	y = 0
	output_node.location = [x,y]
	mixShaderNode = group_tree.nodes.new('ShaderNodeMixShader')
	mixShaderNode.location = [x, y - 300]
	clearNode = group_tree.nodes.new('ShaderNodeEeveeSpecular')
	clearNode.location = [x, y - 600]
	clearNode.inputs[4].default_value = 1 # transparency
	links.new(mixShaderNode.inputs[2], mixCycleNodeRGB.outputs[0])
	links.new(mixShaderNode.inputs[0], finalCullAlpha.outputs[0])
	links.new(mixShaderNode.inputs[1], clearNode.outputs[0])

	groupNode.outputs.new("NodeSocketShader", "Output")
	output_node.inputs.new("NodeSocketShader", "Output")
	links.new(output_node.inputs[0], mixShaderNode.outputs[0])

	return groupNode, location[0], location[1]

def createNodeToGroupLink(node, outputIndex, groupNode, groupInputNode,
	node_tree, nodeIndex, name, createSockets):
	return createSocketToGroupLink(node.outputs[outputIndex], groupNode,
		groupInputNode, node_tree, nodeIndex, name, createSockets)

def createSocketToGroupLink(socket, groupNode, groupInputNode, 
	node_tree, nodeIndex, name, createSockets):
	if createSockets:
		inputType = str(type(socket))[18:-2] # convert class to string
		groupNode.inputs.new(inputType, name)
		groupInputNode.outputs.new(inputType, name)
	nodeExternal = groupNode.inputs[nodeIndex]
	node_tree.links.new(nodeExternal, socket)

	if createSockets:
		nodeInternal = groupInputNode.outputs[nodeIndex]
		return nodeInternal
	else:
		return None

def nodeDictToInternalSocket(node_tree, groupNode, groupInputNode, nodeDict, 
	texAlphaList, texAlphaWithBridgeList, startIndex, createSockets):
	nodeIndex = startIndex
	newDict = {}
	for name, node in nodeDict.items():
		newDict[name] = createNodeToGroupLink(node, 0 if name != 'Noise' else 1,
			groupNode, groupInputNode, node_tree, nodeIndex, name, createSockets)
		nodeIndex += 1
		if name in texAlphaList:
			newDict[name + " Alpha"] = createNodeToGroupLink(node, 1, groupNode,
				groupInputNode, node_tree, nodeIndex, name + " Alpha", createSockets)
			nodeIndex += 1
		elif name in texAlphaWithBridgeList:
			alphaSplitNode = node.inputs[1].links[0].from_socket.node
			bridgeNode = alphaSplitNode.outputs[1].links[0].to_socket.node
			newDict[name + " Alpha"] = createNodeToGroupLink(bridgeNode, 0,
				groupNode, groupInputNode, node_tree, nodeIndex, 
				name + " Alpha", createSockets)
			nodeIndex += 1

	return newDict, nodeIndex

def socketDictToInternalSocket(node_tree, groupNode, groupInputNode, socketDict, 
	startIndex, createSockets):
	nodeIndex = startIndex
	newDict = {}
	for name, socket in socketDict.items():
		newDict[name] = createSocketToGroupLink(socket, groupNode, 
			groupInputNode, node_tree, nodeIndex, name, createSockets)
		nodeIndex += 1
	return newDict, nodeIndex

def createTexCoordNode(node_tree, location, uvSocket, socketDict, isV):
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.name = 'Create Tex Coord'
	groupNode.label = 'Create Tex Coord'
	groupNode.location = location
	location[1] = location[1] - (groupNode.height + 100)

	verticalString = "U" if not isV else "V"
	createGroup = 'Create Tex Coord ' + verticalString + ' F3D v3' not in bpy.data.node_groups
	if not createGroup:
		group_tree = bpy.data.node_groups['Create Tex Coord ' + verticalString + ' F3D v3']
		groupNode.node_tree = group_tree
		socketDict, nextSocketIndex = socketDictToInternalSocket(
			node_tree, groupNode, None, socketDict, 0, False)
		return groupNode

	group_tree = bpy.data.node_groups.new(
		type="ShaderNodeTree", name = 'Create Tex Coord ' + verticalString + ' F3D v3')
	links = group_tree.links
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	output_node = group_tree.nodes.new("NodeGroupOutput")
	input_node.location = (-800, 0)
	output_node.location = (2800, 0)

	uvSocket = \
		createSocketToGroupLink(uvSocket, groupNode, 
		input_node, node_tree, 0, 'UV', True)
	socketDict, nextSocketIndex = socketDictToInternalSocket(
		node_tree, groupNode, input_node, socketDict, 1, True)

	output_node.inputs.new('NodeSocketVector', 'UV')
	
	x = 0
	y = 0

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
	links.new(shiftPower.inputs[1], socketDict['Shift'])

	shiftMult, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, -400, -200)
	shiftMult.operation = 'MULTIPLY'
	links.new(shiftMult.inputs[0], prevSocket)
	links.new(shiftMult.inputs[1], shiftPower.outputs[0])

	# Apply scale
	scaleMult, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, -200,-200)
	scaleMult.operation = 'MULTIPLY'
	links.new(scaleMult.inputs[0], shiftMult.outputs[0])
	links.new(scaleMult.inputs[1], socketDict['Scale'])

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
	links.new(addL.inputs[1], socketDict["Normalized L"])

	# Clamp using H
	clampLow, x, y = addNodeAt(group_tree, 'ShaderNodeMath', 
		'Max of NOT zero', 200, 0)
	clampLow.operation = 'MAXIMUM'
	clampLow.inputs[0].default_value = 0.0000001 # so negative clamping works
	links.new(clampLow.inputs[0], socketDict["Normalized Half Pixel"])
	links.new(clampLow.inputs[1], addL.outputs[0])

	clampHighHalfPixelOffset, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, 400, 200)
	clampHighHalfPixelOffset.operation = 'SUBTRACT'
	links.new(clampHighHalfPixelOffset.inputs[0], socketDict["Normalized H"])
	links.new(clampHighHalfPixelOffset.inputs[1], socketDict["Normalized Half Pixel"])

	clampHigh, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 400, 0)
	clampHigh.operation = 'MINIMUM'
	links.new(clampHigh.inputs[0], clampHighHalfPixelOffset.outputs[0])
	links.new(clampHigh.inputs[1], clampLow.outputs[0])

	clampMix, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 600, 0)
	links.new(clampMix.inputs[0], socketDict["Clamp"])
	links.new(clampMix.inputs[1], addL.outputs[0])
	links.new(clampMix.inputs[2], clampHigh.outputs[0])

	# Apply mask 
	maskPositive, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 800,-400)
	maskPositive.operation = "MODULO"
	links.new(maskPositive.inputs[0], clampMix.outputs[0])
	links.new(maskPositive.inputs[1], socketDict["Normalized Mask"])

	ifNegative, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 800, 0)
	ifNegative.operation = 'LESS_THAN'
	links.new(ifNegative.inputs[0], clampMix.outputs[0])
	ifNegative.inputs[1].default_value = 0

	maskNegative, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 800,-200)
	links.new(maskNegative.inputs[0], socketDict["Normalized Mask"])
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
	links.new(mirrorMaskDiv.inputs[1], socketDict["Normalized Mask"])

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
	links.new(mirrorCheck.inputs[1], socketDict["Mirror"])

	mirrored, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 2000,-200)
	mirrored.operation = 'SUBTRACT'
	links.new(mirrored.inputs[0], socketDict["Normalized Mask"])
	links.new(mirrored.inputs[1], maskSignMix.outputs[0])

	mirrorMix, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 2200,-200)
	links.new(mirrorMix.inputs[0], mirrorCheck.outputs[0])
	links.new(mirrorMix.inputs[1], maskSignMix.outputs[0])
	links.new(mirrorMix.inputs[2], mirrored.outputs[0])

	# Handle 0 Mask
	check0Mask, x, y = addNodeAt(group_tree, 'ShaderNodeMath', None, 800,-1000)
	check0Mask.operation = 'GREATER_THAN'
	links.new(check0Mask.inputs[0], socketDict["Normalized Mask"])
	check0Mask.inputs[1].default_value = 0

	mix0Mask, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 2400,-200)
	links.new(mix0Mask.inputs[0], check0Mask.outputs[0])
	links.new(mix0Mask.inputs[1], clampHigh.outputs[0])
	links.new(mix0Mask.inputs[2], mirrorMix.outputs[0])

	# Output
	links.new(output_node.inputs[0], mix0Mask.outputs[0])
	return groupNode

def splitTextureVectorInputs(node_tree, socketDict, x, y):
	horizontalDict = {}
	verticalDict = {}
	for name, socket in socketDict.items():
		splitNode, x, y = addNodeAt(node_tree, "ShaderNodeSeparateXYZ", "Split Texture Vector", x, y)
		node_tree.links.new(splitNode.inputs[0], socket)
		horizontalDict[name] = splitNode.outputs[0]
		verticalDict[name] = splitNode.outputs[1]

	return horizontalDict, verticalDict, x, y

def createUVGroup(node_tree, location, textureIndex):
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.name = 'Get UV'
	groupNode.label = 'Get UV'
	groupNode.location = location
	groupNode.name = 'Get UV ' + str(textureIndex) + ' F3D v3'
	location[1] = location[1] - (groupNode.height + 100)

	createGroup = 'Get UV F3D v3' not in bpy.data.node_groups
	if not createGroup:
		group_tree = bpy.data.node_groups['Get UV F3D v3']
		groupNode.node_tree = group_tree
		#texGenSocketDict, nodeIndex = nodeDictToInternalSocket(node_tree, 
		#	groupNode, None, texGenDict, [], [], 0, False)
		#socketDict, nodeIndex = nodeDictToInternalSocket(node_tree, 
		#	groupNode, None, nodeDict, [], [], nodeIndex, False)
		
		return groupNode, location[0], location[1]

	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", name = 'Get UV F3D v3')
	links = group_tree.links
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	output_node = group_tree.nodes.new("NodeGroupOutput")
	input_node.location = (-300, 0)
	output_node.location = (2400, 0)

	output_node.inputs.new('NodeSocketVector', 'UV')

	#texGenSocketDict, nodeIndex = nodeDictToInternalSocket(node_tree, 
	#	groupNode, input_node, texGenDict, [], [], 0, True)
	#socketDict, nodeIndex = nodeDictToInternalSocket(node_tree, 
	#	groupNode, input_node, nodeDict, [], [], nodeIndex, True)

	texGenSocketDict = addSocketList(groupNode, input_node, {
		"Texture Gen" : "NodeSocketFloat",
		"Texture Gen Linear" : "NodeSocketFloat",
	})

	socketDict = addSocketList(groupNode, input_node, {
		"Image Factor" : "NodeSocketVector",
		'Normalized L' : "NodeSocketVector",
		'Normalized H' : "NodeSocketVector",
		'Clamp' : "NodeSocketVector",
		'Normalized Mask' : "NodeSocketVector",
		'Mirror' : "NodeSocketVector",
		'Shift' : "NodeSocketVector",
		'Scale' : "NodeSocketVector",
		'Normalized Half Pixel' : "NodeSocketVector",
	})
	
	x = 0
	y = 0
	horizontalDict, verticalDict, x, y = \
		splitTextureVectorInputs(group_tree, socketDict, x, y)

	# Regular UVs
	x += 300
	y = 0
	UVMapNode, x, y = addNodeAt(group_tree, 'ShaderNodeUVMap', None, x, y)
	UVMapNode.uv_map = 'UVMap'
	
	# Get normal
	geometryNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeNewGeometry", None, x, y)

	# Convert to screen space normal
	transformNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeVectorTransform", None, x, y)
	transformNode.convert_from = 'WORLD'
	transformNode.convert_to = 'CAMERA'
	transformNode.vector_type = 'NORMAL'
	links.new(transformNode.inputs[0], geometryNode.outputs[1])

	# Convert [-1,1] to [0,1]
	x += 300
	y = 0
	addOneNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeVectorMath", None, x, y)
	addOneNode.inputs[1].default_value = (1,1,1)
	links.new(addOneNode.inputs[0], transformNode.outputs[0])

	separateNode, x, y = \
		addNodeAt(group_tree, "ShaderNodeSeparateXYZ", None, x, y)
	links.new(separateNode.inputs[0], addOneNode.outputs[0])

	divideTwoX, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, x, y)
	divideTwoY, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, x, y)
	divideTwoX.operation = 'DIVIDE'
	divideTwoY.operation = 'DIVIDE'
	divideTwoX.inputs[1].default_value = -2	# Must be negative (env, not sphere)
	divideTwoY.inputs[1].default_value = -2
	links.new(divideTwoX.inputs[0], separateNode.outputs[0])
	links.new(divideTwoY.inputs[0], separateNode.outputs[1])

	# Normalize values based on tex size.
	x += 300
	y = 0
	normalizeX, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, x, y)
	normalizeY, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMath', None, x, y)
	normalizeX.operation = 'MULTIPLY'
	normalizeY.operation = 'MULTIPLY'
	links.new(normalizeX.inputs[0], divideTwoX.outputs[0])
	links.new(normalizeY.inputs[0], divideTwoY.outputs[0])
	links.new(normalizeX.inputs[1], horizontalDict["Image Factor"])
	links.new(normalizeY.inputs[1], verticalDict["Image Factor"])

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
	links.new(normalizeLinearX.inputs[1], horizontalDict["Image Factor"])
	links.new(normalizeLinearY.inputs[1], verticalDict["Image Factor"])

	texGenLinearCombine, x, y = \
		addNodeAt(group_tree, 'ShaderNodeCombineXYZ', None, 1200, -600)
	links.new(texGenLinearCombine.inputs[0], normalizeLinearX.outputs[0])
	links.new(texGenLinearCombine.inputs[1], normalizeLinearY.outputs[0])

	# Mix UV based on flags
	mixTexGen, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 1500, 0)
	links.new(mixTexGen.inputs[0], texGenSocketDict["Texture Gen"])
	links.new(mixTexGen.inputs[1], UVMapNode.outputs[0])
	links.new(mixTexGen.inputs[2], texGenCombine.outputs[0])
	
	mixTexGenLinear, x, y = \
		addNodeAt(group_tree, 'ShaderNodeMixRGB', None, 1500, y)
	links.new(mixTexGenLinear.inputs[0], texGenSocketDict["Texture Gen Linear"])
	links.new(mixTexGenLinear.inputs[1], mixTexGen.outputs[0])
	links.new(mixTexGenLinear.inputs[2], texGenLinearCombine.outputs[0])

	# Apply tile attributes
	uvSplit, x, y = \
		addNodeAt(group_tree, 'ShaderNodeSeparateXYZ', None, 1800, 500)
	links.new(uvSplit.inputs[0], mixTexGenLinear.outputs[0])
	
	uv_xNode = createTexCoordNode(group_tree, [2000, 500], uvSplit.outputs[0], horizontalDict, False)
	uv_yNode = createTexCoordNode(group_tree, [2000, 300], uvSplit.outputs[1], verticalDict, True)

	links.new(uv_xNode.inputs[0], uvSplit.outputs[0])
	links.new(uv_yNode.inputs[0], uvSplit.outputs[1])

	uvCombine, x, y = \
		addNodeAt(group_tree, 'ShaderNodeCombineXYZ', None, 2200, 500)

	links.new(uvCombine.inputs[0], uv_xNode.outputs[0])
	links.new(uvCombine.inputs[1], uv_yNode.outputs[0])

	links.new(output_node.inputs[0], uvCombine.outputs[0])
	return groupNode, location[0], location[1]

def createShadeNode(node_tree, location):
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.name = 'Shade Color'
	groupNode.label = 'Shade Color'
	groupNode.location = location
	location[1] = location[1] - (groupNode.height + 100)

	createGroup = 'Get Shade Color F3D v3' not in bpy.data.node_groups
	if not createGroup:
		group_tree = bpy.data.node_groups['Get Shade Color F3D v3']
		groupNode.node_tree = group_tree
		#shadingNodeInternal = createSocketToGroupLink(shadingNode.outputs[0], 
		#	groupNode, None, node_tree, 0, 'Shading', False)
		#lightingNodeInternal = createSocketToGroupLink(lightingNode.outputs[0], 
		#	groupNode, None, node_tree, 1, 'Lighting', False)
		#ambientInternal = createSocketToGroupLink(ambientNode.outputs[0], 
		#	groupNode, None, node_tree, 2, 'Ambient Color', False)
		
		return groupNode

	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", 
		name = 'Get Shade Color F3D v3')		
	links = group_tree.links
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	output_node = group_tree.nodes.new("NodeGroupOutput")
	input_node.location = (-300, 0)
	output_node.location = (600, 0)

	socketDict = addSocketList(groupNode, input_node, {
		"Shading" : "NodeSocketFloat",
		'Lighting' : "NodeSocketFloat",
		'Ambient Color' : "NodeSocketColor"
	})

	#shadingNodeInternal = createSocketToGroupLink(shadingNode.outputs[0], 
	#	groupNode, input_node, node_tree, 0, 'Shading', createGroup)
	#lightingNodeInternal = createSocketToGroupLink(lightingNode.outputs[0], 
	#	groupNode, input_node, node_tree, 1, 'Lighting', createGroup)
	#ambientInternal = createSocketToGroupLink(ambientNode.outputs[0], 
	#	groupNode, input_node, node_tree, 2, 'Ambient Color', createGroup)
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
	links.new(addAmbient.inputs[0], socketDict['Ambient Color'])
	links.new(addAmbient.inputs[1], toRGBNode.outputs[0])
	links.new(mixRGB.inputs[0], socketDict['Lighting'])
	links.new(mixRGB.inputs[1], vertColorNode.outputs[0])
	links.new(mixRGB.inputs[2], addAmbient.outputs[0])

	links.new(mixRGBShadeless.inputs[0], socketDict['Shading'])
	links.new(mixRGBShadeless.inputs[1], colorNode.outputs[0])
	links.new(mixRGBShadeless.inputs[2], mixRGB.outputs[0])

	links.new(mixAlpha.inputs[0], socketDict['Lighting'])
	links.new(mixAlpha.inputs[1], vertAlphaNode.outputs[2])
	mixAlpha.inputs[2].default_value = (1,1,1,1)

	links.new(output_node.inputs[0], mixRGBShadeless.outputs[0])
	links.new(output_node.inputs[1], mixAlpha.outputs[0])

	return groupNode

def createTexFormatNodes(node_tree, location, externalColorSocket, externalAlphaSocket):
	groupNode = node_tree.nodes.new("ShaderNodeGroup")
	groupNode.location = location
	groupNode.name = 'Get Texture Color'
	location[1] = location[1] - (groupNode.height + 100)

	createGroup = 'Get Texture Color F3D v3' not in bpy.data.node_groups
	if not createGroup:
		group_tree = bpy.data.node_groups['Get Texture Color F3D v3']
		groupNode.node_tree = group_tree

		nodeIndex = 0
		colorSocket = createSocketToGroupLink(externalColorSocket, groupNode, None, 
			node_tree, nodeIndex, "Color", createGroup)
		nodeIndex += 1
		alphaSocket = createSocketToGroupLink(externalAlphaSocket, groupNode, None, 
			node_tree, nodeIndex, "Alpha", createGroup)
		nodeIndex += 1

		#socketDict, nodeIndex = nodeDictToInternalSocket(node_tree, 
		#	groupNode, None, nodeDict, [], [], nodeIndex, createGroup)
		
		return groupNode, location[0], location[1]
	
	group_tree = bpy.data.node_groups.new(type="ShaderNodeTree", name = 'Get Texture Color F3D v3')
	links = group_tree.links
	groupNode.node_tree = group_tree
	input_node = group_tree.nodes.new("NodeGroupInput")
	output_node = group_tree.nodes.new("NodeGroupOutput")

	x = 0
	y = 0
	input_node.location = (x,y)

	output_node.inputs.new('NodeSocketColor', 'Color')
	groupNode.outputs.new("NodeSocketColor", "Color")
	output_node.inputs.new('NodeSocketFloat', 'Alpha')
	groupNode.outputs.new("NodeSocketFloat", "Alpha")

	nodeIndex = 0
	colorSocket = createSocketToGroupLink(externalColorSocket, groupNode, input_node, 
		node_tree, nodeIndex, "Color", createGroup)
	nodeIndex += 1
	alphaSocket = createSocketToGroupLink(externalAlphaSocket, groupNode, input_node, 
		node_tree, nodeIndex, "Alpha", createGroup)
	nodeIndex += 1

	socketDict = addSocketList(groupNode, input_node, {
		"Is Greyscale" : "NodeSocketFloat",
		"Has Alpha" : "NodeSocketFloat",
		'Is Intensity' : "NodeSocketFloat"
	})

	#socketDict, nodeIndex = nodeDictToInternalSocket(node_tree, 
	#	groupNode, input_node, nodeDict, [], [], nodeIndex, createGroup)

	# Add texture format mixes
	x += 300
	greyNode, x, y = addNodeAt(group_tree, 'ShaderNodeSeparateHSV', 
		None, x, y)
	links.new(greyNode.inputs[0], colorSocket)

	greyMix, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', 
		None, x, y)
	links.new(greyMix.inputs[0], socketDict["Is Greyscale"])
	links.new(greyMix.inputs[1], colorSocket)
	links.new(greyMix.inputs[2], greyNode.outputs[2])
	links.new(output_node.inputs[0], greyMix.outputs[0])

	alphaMix, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', 
		None, x, y)
	links.new(alphaMix.inputs[0], socketDict["Has Alpha"])
	links.new(alphaMix.inputs[2], alphaSocket)
	alphaMix.inputs[1].default_value = (1,1,1,1)

	alphaMixIntensity, x, y = addNodeAt(group_tree, 'ShaderNodeMixRGB', 
		None, x, y)
	links.new(alphaMixIntensity.inputs[0], socketDict["Is Intensity"])
	links.new(alphaMixIntensity.inputs[1], alphaMix.outputs[0])
	links.new(alphaMixIntensity.inputs[2], greyNode.outputs[2])
	links.new(output_node.inputs[1], alphaMixIntensity.outputs[0])
	
	x += 300
	output_node.location = (x, 0)

	return groupNode, location[0], location[1]

def createUVInputsAndGroup(node_tree, texIndex, x, y):
	uvNode, x, y = createUVGroup(node_tree, [x,y], texIndex)

	return uvNode, x + 300, 0

def createTextureInputsAndGroup(node_tree, texIndex, x, y):
	colorSocket = node_tree.nodes["Texture " + str(texIndex)].outputs[0]
	alphaSocket = node_tree.nodes["Texture " + str(texIndex)].outputs[1]

	colorNode, x, y = createTexFormatNodes(node_tree, [x,y], colorSocket, alphaSocket)
	return colorNode, x, y


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

class F3DNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'CustomTreeType'
