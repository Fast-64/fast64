import shutil, copy, math, mathutils, bpy, os, re

from bpy.utils import register_class, unregister_class
from .oot_constants import *
from .oot_utility import *
from .oot_skeleton import *
from ..utility import *
from ..panels import OOT_Panel

class OOTAnimation:
	def __init__(self, name):
		self.name = toAlnum(name)
		self.segmentID = None
		self.indices = {}
		self.values = []
		self.frameCount = None
		self.limit = None

	def valuesName(self):
		return self.name + "FrameData"

	def indicesName(self):
		return self.name + "JointIndices"

	def toC(self):
		data = CData()
		data.source += '#include "ultra64.h"\n#include "global.h"\n\n'

		# values
		data.source += "s16 " + self.valuesName() + "[" + str(len(self.values)) + "] = {\n"
		counter = 0
		for value in self.values:
			if counter == 0:
				data.source += '\t'
			data.source += format(value, '#06x') + ", "
			counter += 1
			if counter > 14:
				counter = 0
				data.source += '\n'
		data.source += '};\n\n'

		# indices (index -1 => translation)
		data.source += "JointIndex " + self.indicesName() + "[" + str(len(self.indices)) + "] = {\n"
		for index in range(-1, len(self.indices) - 1):
			data.source += '\t{ '
			for field in range(3):
				data.source += format(self.indices[index][field], '#06x') + ", "
			data.source += '},\n'
		data.source += "};\n\n"

		# header
		data.header += "extern AnimationHeader " + self.name + ';\n'
		data.source += "AnimationHeader " + self.name + " = { { " + str(self.frameCount) + " }, " +\
			self.valuesName() + ", " + self.indicesName() + ", " + str(self.limit) + " };\n\n"

		return data

def ootConvertAnimationData(anim, armatureObj, frameInterval, restPoseRotations, convertTransformMatrix):
	checkForStartBone(armatureObj)
	bonesToProcess = [getStartBone(armatureObj)]
	currentBone = armatureObj.data.bones[bonesToProcess[0]]
	animBones = []

	# Get animation bones in order
	# must be SAME order as ootProcessBone
	while len(bonesToProcess) > 0:
		boneName = bonesToProcess[0]
		currentBone = armatureObj.data.bones[boneName]
		bonesToProcess = bonesToProcess[1:]

		animBones.append(boneName)

		childrenNames = getSortedChildren(armatureObj, currentBone)
		bonesToProcess = childrenNames + bonesToProcess
	
	# list of boneFrameData, which is [[x frames], [y frames], [z frames]]
	# boneIndex is index in animBones in ootConvertAnimationData.
	# since we are processing the bones in the same order as ootProcessBone,
	# they should be the same as the limb indices.

	# index -1 => translation
	translationData = [ValueFrameData(-1, i, []) for i in range(3)]
	rotationData = [[
		ValueFrameData(i, 0, []),
		ValueFrameData(i, 1, []),
		ValueFrameData(i, 2, [])] for i in range(len(animBones))]

	currentFrame = bpy.context.scene.frame_current
	for frame in range(frameInterval[0], frameInterval[1]):
		bpy.context.scene.frame_set(frame)
		rootBone = armatureObj.data.bones[animBones[0]]
		rootPoseBone = armatureObj.pose.bones[animBones[0]]

		# Hacky solution to handle Z-up to Y-up conversion
		translation = mathutils.Quaternion((1, 0, 0), math.radians(-90.0)) @ \
			(convertTransformMatrix @ rootPoseBone.matrix).decompose()[0]
		saveTranslationFrame(translationData, translation)

		for boneIndex in range(len(animBones)):
			boneName = animBones[boneIndex]
			currentBone = armatureObj.data.bones[boneName]
			currentPoseBone = armatureObj.pose.bones[boneName]
			
			rotationValue = \
				(currentBone.matrix.to_4x4().inverted() @ \
				currentPoseBone.matrix).to_quaternion()
			if currentBone.parent is not None:
				rotationValue = (
					currentBone.matrix.to_4x4().inverted() @ currentPoseBone.parent.matrix.inverted() @ \
					currentPoseBone.matrix).to_quaternion()
			
			saveQuaternionFrame(rotationData[boneIndex], restPoseRotations[boneName].inverted() @ rotationValue)
	
	bpy.context.scene.frame_set(currentFrame)
	removeTrailingFrames(translationData)
	for frameData in rotationData:
		removeTrailingFrames(frameData)

	# need to deepcopy?
	armatureFrameData = translationData
	for frameDataGroup in rotationData:
		for i in range(3):
			armatureFrameData.append(frameDataGroup[i])

	return armatureFrameData

def ootExportAnimationCommon(armatureObj, convertTransformMatrix, skeletonName):
	if armatureObj.animation_data is None or \
		armatureObj.animation_data.action is None:
		raise PluginError("No active animation selected.")
	anim = armatureObj.animation_data.action
	ootAnim = OOTAnimation(toAlnum(skeletonName + anim.name.capitalize() + "Anim"))
	
	skeleton, restPoseRotations = ootConvertArmatureToSkeletonWithoutMesh(armatureObj, convertTransformMatrix, skeletonName)

	frameInterval = getFrameInterval(anim)
	ootAnim.frameCount = frameInterval[1] - frameInterval[0]
	armatureFrameData = ootConvertAnimationData(anim, armatureObj, frameInterval, restPoseRotations, convertTransformMatrix)

	singleFrameData = []
	multiFrameData = []
	for frameData in armatureFrameData:
		if len(frameData.frames) == 1:
			singleFrameData.append(frameData)
		else:
			multiFrameData.append(frameData)

	for frameData in singleFrameData:
		frame = frameData.frames[0]
		if frameData.boneIndex not in ootAnim.indices:
			ootAnim.indices[frameData.boneIndex] = [None, None, None]
		if frame in ootAnim.values:
			ootAnim.indices[frameData.boneIndex][frameData.field] = ootAnim.values.index(frame)
		else:
			ootAnim.indices[frameData.boneIndex][frameData.field] = len(ootAnim.values)
			ootAnim.values.extend(frameData.frames)

	ootAnim.limit = len(ootAnim.values)
	for frameData in multiFrameData:
		if frameData.boneIndex not in ootAnim.indices:
			ootAnim.indices[frameData.boneIndex] = [None, None, None]
		ootAnim.indices[frameData.boneIndex][frameData.field] = len(ootAnim.values)
		ootAnim.values.extend(frameData.frames)
	
	return ootAnim

def exportAnimationC(armatureObj, exportPath, isCustomExport, folderName, skeletonName):
	checkEmptyName(folderName)
	checkEmptyName(skeletonName)
	convertTransformMatrix = mathutils.Matrix.Scale(bpy.context.scene.ootActorBlenderScale, 4)
	ootAnim = ootExportAnimationCommon(armatureObj, convertTransformMatrix, skeletonName)

	ootAnimC = ootAnim.toC()
	path = ootGetPath(exportPath, isCustomExport, 'assets/objects/', folderName, False, False)
	writeCData(ootAnimC, 
		os.path.join(path, ootAnim.name + '.h'),
		os.path.join(path, ootAnim.name + '.c'))

	if not isCustomExport:
		addIncludeFiles(folderName, path, ootAnim.name)

def getNextBone(boneStack, armatureObj):
	if len(boneStack) == 0:
		raise PluginError("More bones in animation than on armature.")
	bone = armatureObj.data.bones[boneStack[0]]
	boneStack = boneStack[1:]
	boneStack = getSortedChildren(armatureObj, bone) + boneStack
	return bone, boneStack

def ootImportAnimationC(armatureObj, filepath, animName, actorScale):
	animData = readFile(filepath)

	matchResult = re.search(re.escape(animName) + "\s*=\s*\{\s*\{\s*([^,\s]*)\s*\}*\s*,\s*([^,\s]*)\s*,\s*([^,\s]*)\s*,\s*([^,\s]*)\s*\}\s*;", animData)
	if matchResult is None:
		raise PluginError("Cannot find animation named " + animName + " in " + filepath)
	frameCount = hexOrDecInt(matchResult.group(1).strip())
	frameDataName = matchResult.group(2).strip()
	jointIndicesName = matchResult.group(3).strip()
	staticIndexMax = hexOrDecInt(matchResult.group(4).strip())

	frameData = getFrameData(filepath, animData, frameDataName)
	jointIndices = getJointIndices(filepath, animData, jointIndicesName)

	#print(frameDataName + " " + jointIndicesName)
	#print(str(frameData) + "\n" + str(jointIndices))

	bpy.context.scene.frame_end = frameCount
	anim = bpy.data.actions.new(animName)

	startBoneName = getStartBone(armatureObj)
	boneStack = [startBoneName]
	
	isRootTranslation = True
	# boneFrameData = [[x keyframes], [y keyframes], [z keyframes]]
	# len(armatureFrameData) should be = number of bones
	# property index = 0,1,2 (aka x,y,z)
	for jointIndex in jointIndices:
		if isRootTranslation:
			for propertyIndex in range(3):
				fcurve = anim.fcurves.new(
					data_path = 'pose.bones["' + startBoneName + '"].location',
					index = propertyIndex,
					action_group = startBoneName)
				if jointIndex[propertyIndex] < staticIndexMax:
					value = frameData[jointIndex[propertyIndex]] / actorScale
					fcurve.keyframe_points.insert(0, value)
				else:
					for frame in range(frameCount):
						value = frameData[jointIndex[propertyIndex] + frame] / actorScale
						fcurve.keyframe_points.insert(frame, value)
			isRootTranslation = False
		else:
			# WARNING: This assumes the order bones are processed are in alphabetical order.
			# If this changes in the future, then this won't work.
			bone, boneStack = getNextBone(boneStack, armatureObj)
			for propertyIndex in range(3):
				fcurve = anim.fcurves.new(
					data_path = 'pose.bones["' + bone.name + '"].rotation_euler', 
					index = propertyIndex,
					action_group = bone.name)
				if jointIndex[propertyIndex] < staticIndexMax:
					value = math.radians(frameData[jointIndex[propertyIndex]] * 360 / (2**16))
					fcurve.keyframe_points.insert(0, value)
				else:
					for frame in range(frameCount):
						value = math.radians(frameData[jointIndex[propertyIndex] + frame] * 360 / (2**16))
						fcurve.keyframe_points.insert(frame, value)

	if armatureObj.animation_data is None:
		armatureObj.animation_data_create()
	armatureObj.animation_data.action = anim

def getFrameData(filepath, animData, frameDataName):
	matchResult = re.search(re.escape(frameDataName) + "\s*\[\s*[0-9]*\s*\]\s*=\s*\{([^\}]*)\}", animData, re.DOTALL)
	if matchResult is None:
		raise PluginError("Cannot find animation frame data named " + frameDataName + " in " + filepath)
	data = matchResult.group(1)
	frameData = [int.from_bytes([int(value.strip()[2:4], 16), int(value.strip()[4:6], 16)], 
		'big', signed = True) for value in data.split(",") if value.strip() != ""]

	return frameData

def getJointIndices(filepath, animData, jointIndicesName):
	matchResult = re.search(re.escape(jointIndicesName) + "\s*\[\s*[0-9]*\s*\]\s*=\s*\{([^;]*);", animData, re.DOTALL)
	if matchResult is None:
		raise PluginError("Cannot find animation joint indices data named " + jointIndicesName + " in " + filepath)
	data = matchResult.group(1)
	jointIndicesData = [[hexOrDecInt(match.group(i)) for i in range(1,4)] for match in re.finditer("\{([^,\}]*),([^,\}]*),([^,\}]*)\}", data, re.DOTALL)]

	return jointIndicesData

class OOT_ExportAnim(bpy.types.Operator):
	bl_idname = 'object.oot_export_anim'
	bl_label = "Export Animation"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		try:
			if len(context.selected_objects) == 0 or not \
				isinstance(context.selected_objects[0].data, bpy.types.Armature):
				raise PluginError("Armature not selected.")
			if len(context.selected_objects) > 1 :
				raise PluginError("Multiple objects selected, make sure to select only one.")
			armatureObj = context.selected_objects[0]
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = "OBJECT")
		except Exception as e:
			raisePluginError(self, e)
			return {"CANCELLED"}

		try:
			isCustomExport = context.scene.ootAnimIsCustomExport
			exportPath = bpy.path.abspath(context.scene.ootAnimExportCustomPath)
			folderName = context.scene.ootAnimExportFolderName
			skeletonName = context.scene.ootAnimSkeletonName

			path = ootGetObjectPath(isCustomExport, exportPath, folderName)
			
			exportAnimationC(armatureObj, path, isCustomExport, folderName, skeletonName)
			self.report({'INFO'}, 'Success!')

		except Exception as e:
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

		return {'FINISHED'} # must return a set

class OOT_ImportAnim(bpy.types.Operator):
	bl_idname = 'object.oot_import_anim'
	bl_label = "Import Animation"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		try:
			if len(context.selected_objects) == 0 or not \
				isinstance(context.selected_objects[0].data, bpy.types.Armature):
				raise PluginError("Armature not selected.")
			if len(context.selected_objects) > 1 :
				raise PluginError("Multiple objects selected, make sure to select only one.")
			armatureObj = context.selected_objects[0]
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = "OBJECT")
		except Exception as e:
			raisePluginError(self, e)
			return {"CANCELLED"}

		try:
			isCustomImport = context.scene.ootAnimIsCustomImport
			folderName = context.scene.ootAnimImportFolderName
			importPath = bpy.path.abspath(context.scene.ootAnimImportCustomPath)
			animName = context.scene.ootAnimName
			actorScale = context.scene.ootActorBlenderScale

			path = ootGetObjectPath(isCustomImport, importPath, folderName)

			ootImportAnimationC(armatureObj, path, animName, actorScale)
			self.report({'INFO'}, 'Success!')

		except Exception as e:
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

		return {'FINISHED'} # must return a set

class OOT_ExportAnimPanel(OOT_Panel):
	bl_idname = "OOT_PT_export_anim"
	bl_label = "OOT Animation Exporter"

	# called every frame
	def draw(self, context):
		col = self.layout.column()

		col.operator(OOT_ExportAnim.bl_idname)
		prop_split(col, context.scene, 'ootAnimSkeletonName', 'Skeleton Name')
		if context.scene.ootAnimIsCustomExport:
			prop_split(col, context.scene, 'ootAnimExportCustomPath', "Folder")
		else:
			prop_split(col, context.scene, 'ootAnimExportFolderName', 'Object')
		col.prop(context.scene, 'ootAnimIsCustomExport')


		col.operator(OOT_ImportAnim.bl_idname)
		prop_split(col, context.scene, 'ootAnimName', 'Anim Name')
		
		if context.scene.ootAnimIsCustomImport:
			prop_split(col, context.scene, 'ootAnimImportCustomPath', "File")
		else:
			prop_split(col, context.scene, 'ootAnimImportFolderName', 'Object')
		col.prop(context.scene, 'ootAnimIsCustomImport')
		


oot_anim_classes = (
	OOT_ExportAnim,
	OOT_ImportAnim,
)

oot_anim_panels = (
	OOT_ExportAnimPanel,
)

def oot_anim_panel_register():
	for cls in oot_anim_panels:
		register_class(cls)

def oot_anim_panel_unregister():
	for cls in oot_anim_panels:
		unregister_class(cls)

def oot_anim_register():
	bpy.types.Scene.ootAnimIsCustomExport = bpy.props.BoolProperty(name = "Use Custom Path")
	bpy.types.Scene.ootAnimExportCustomPath =  bpy.props.StringProperty(
		name ='Folder', subtype = 'FILE_PATH')
	bpy.types.Scene.ootAnimExportFolderName = bpy.props.StringProperty(name = "Animation Folder", default = "object_geldb")

	bpy.types.Scene.ootAnimIsCustomImport = bpy.props.BoolProperty(name = "Use Custom Path")
	bpy.types.Scene.ootAnimImportCustomPath =  bpy.props.StringProperty(
		name ='Folder', subtype = 'FILE_PATH')
	bpy.types.Scene.ootAnimImportFolderName = bpy.props.StringProperty(name = "Animation Folder", default = "object_geldb")

	bpy.types.Scene.ootAnimSkeletonName = bpy.props.StringProperty(name = "Skeleton Name", default = "gGerudoRedSkel")
	bpy.types.Scene.ootAnimName = bpy.props.StringProperty(name = "Anim Name", default = "gGerudoRedSpinAttackAnim")
	for cls in oot_anim_classes:
		register_class(cls)

def oot_anim_unregister():
	del bpy.types.Scene.ootAnimIsCustomExport
	del bpy.types.Scene.ootAnimExportCustomPath
	del bpy.types.Scene.ootAnimExportFolderName

	del bpy.types.Scene.ootAnimIsCustomImport
	del bpy.types.Scene.ootAnimImportCustomPath
	del bpy.types.Scene.ootAnimImportFolderName

	del bpy.types.Scene.ootAnimSkeletonName
	del bpy.types.Scene.ootAnimName
	for cls in reversed(oot_anim_classes):
		unregister_class(cls)
