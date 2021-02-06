import shutil, copy, math, mathutils, bpy, os

from bpy.utils import register_class, unregister_class
from .oot_constants import *
from .oot_utility import *
from .oot_skeleton import *
from ..utility import *

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
			exportPath = context.scene.ootAnimCustomPath
			folderName = context.scene.ootAnimFolderName
			skeletonName = context.scene.ootAnimName
			exportAnimationC(armatureObj, exportPath, isCustomExport, folderName, skeletonName)
			self.report({'INFO'}, 'Success!')

		except Exception as e:
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

		return {'FINISHED'} # must return a set

class OOT_ExportAnimPanel(bpy.types.Panel):
	bl_idname = "OOT_PT_export_anim"
	bl_label = "OOT Animation Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'OOT'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.operator(OOT_ExportAnim.bl_idname)
		
		col.prop(context.scene, 'ootAnimIsCustomExport')
		prop_split(col, context.scene, 'ootAnimName', 'Skeleton')
		if context.scene.ootAnimIsCustomExport:
			col.prop(context.scene, 'ootAnimCustomPath')
		else:
			prop_split(col, context.scene, 'ootAnimFolderName', 'Object')
			

oot_anim_classes = (
	OOT_ExportAnim,
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
	bpy.types.Scene.ootAnimCustomPath =  bpy.props.StringProperty(
		name ='Folder', subtype = 'FILE_PATH')
	bpy.types.Scene.ootAnimFolderName = bpy.props.StringProperty(name = "Animation Folder", default = "gameplay_keep")
	bpy.types.Scene.ootAnimName = bpy.props.StringProperty(name = "Skeleton Name", default = "skeleton")
	for cls in oot_anim_classes:
		register_class(cls)

def oot_anim_unregister():
	del bpy.types.Scene.ootAnimIsCustomExport
	del bpy.types.Scene.ootAnimCustomPath
	del bpy.types.Scene.ootAnimFolderName
	del bpy.types.Scene.ootAnimName
	for cls in reversed(oot_anim_classes):
		unregister_class(cls)