import shutil, copy, mathutils, bpy, math, os

from ..f3d.f3d_writer import *
from ..f3d.f3d_material import TextureProperty, tmemUsageUI
from bpy.utils import register_class, unregister_class
from .oot_constants import *
from .oot_utility import *
from .oot_f3d_writer import *
from ..utility import *

class OOTSkeleton():
	def __init__(self, name):
		self.name = name + "Skel"
		self.segmentID = None
		self.limbRoot = None

	def createLimbList(self):
		if self.limbRoot is None:
			return []

		limbList = []
		self.limbRoot.getList(limbList)
		self.limbRoot.setLinks()
		return limbList

	def getNumDLs(self):
		if self.limbRoot is not None:
			return self.limbRoot.getNumDLs()
		else:
			return 0

	def getNumLimbs(self):
		if self.limbRoot is not None:
			return self.limbRoot.getNumLimbs()
		else:
			return 0

	def isFlexSkeleton(self):
		if self.limbRoot is not None:
			return self.limbRoot.isFlexSkeleton()
		else:
			return False

	def limbsName(self):
		return self.name + "Limbs"

	def toC(self):
		limbData = CData()
		data = CData()

		if self.limbRoot is None:
			return data

		limbList = self.createLimbList()
		isFlex = self.isFlexSkeleton()

		data.source += "void* " + self.limbsName() + "[" + str(self.getNumLimbs()) + "] = {\n"
		for limb in limbList:
			limbData.source += limb.toC()
			data.source += '\t&' + limb.name() + ',\n'
		limbData.source += '\n'
		data.source += "};\n\n"

		if isFlex:
			data.source += "FlexSkeletonHeader " + self.name + " = { " + self.limbsName() + ", " +\
				str(self.getNumLimbs()) + ", " + str(self.getNumDLs()) + " };\n\n" 
			data.header = "extern FlexSkeletonHeader " + self.name + ";\n"
		else:
			data.source += "SkeletonHeader " + self.name + " = { " + self.limbsName() + ", " +\
				str(self.getNumLimbs()) + " };\n\n" 
			data.header = "extern SkeletonHeader " + self.name + ";\n"

		limbData.append(data)

		return limbData

class OOTLimb():
	def __init__(self, skeletonName, index, translation, DL, lodDL):
		self.skeletonName = skeletonName
		self.translation = translation
		self.firstChildIndex = 0xFF
		self.nextSiblingIndex = 0xFF
		self.DL = DL
		self.lodDL = lodDL

		self.isFlex = False
		self.index = index
		self.children = []
		self.inverseRotation = None

	def toC(self):
		return "StandardLimb " + self.name() + " = { " +\
			"{ " + str(int(round(self.translation[0]))) + ", " + \
			str(int(round(self.translation[1]))) + ", " + \
			str(int(round(self.translation[2]))) + " }, " + \
			str(self.firstChildIndex) + ", " +\
			str(self.nextSiblingIndex) + ", " + \
			(self.DL.name if self.DL is not None else "NULL") + " };\n" 

	def name(self):
		return self.skeletonName + "Limb_" + str(self.index)

	def getNumLimbs(self):
		numLimbs = 1
		for child in self.children:
			numLimbs += child.getNumLimbs()
		return numLimbs

	def getNumDLs(self):
		numDLs = 0
		if self.DL is not None:
			numDLs += 1
		if self.lodDL is not None:
			numDLs += 1

		for child in self.children:
			numDLs += child.getNumDLs()

		return numDLs

	def isFlexSkeleton(self):
		if self.isFlex:
			return True
		else:
			for child in self.children:
				if child.isFlexSkeleton():
					return True
			return False

	# should be same order as ootProcessBone
	def getList(self, limbList):
		limbList.append(self)
		for child in self.children:
			child.getList(limbList)

	def setLinks(self):
		if len(self.children) > 0:
			self.firstChildIndex = self.children[0].index
		for i in range(len(self.children)):
			if i < len(self.children) - 1:
				self.children[i].nextSiblingIndex = self.children[i + 1].index
			self.children[i].setLinks()
		# self -> child -> sibling

def setArmatureToNonRotatedPose(armatureObj):
	restPoseRotations = {}
	poseBoneName = getStartBone(armatureObj)
	setBoneNonRotated(armatureObj, poseBoneName, restPoseRotations)
	return restPoseRotations

def setBoneNonRotated(armatureObj, boneName, restPoseRotations):
	bone = armatureObj.data.bones[boneName]
	poseBone = armatureObj.pose.bones[boneName]

	while len(poseBone.constraints) > 0:
		poseBone.constraints.remove(poseBone.constraints[0])

	rotation = bone.matrix_local.inverted().decompose()[1]
	armatureObj.pose.bones[boneName].rotation_quaternion = rotation

	restPoseRotations[boneName] = rotation

	for child in bone.children:
		setBoneNonRotated(armatureObj, child.name, restPoseRotations)

def getGroupIndices(meshInfo, armatureObj, meshObj, rootGroupIndex):
	meshInfo.vertexGroupInfo = VertexGroupInfo()
	for vertex in meshObj.data.vertices:
		meshInfo.vertexGroupInfo.vertexGroups[vertex.index] = getGroupIndexOfVert(vertex, armatureObj, meshObj, rootGroupIndex)

def getGroupIndexOfVert(vert, armatureObj, obj, rootGroupIndex):
	actualGroups = []
	nonBoneGroups = []
	for group in vert.groups:
		groupName = getGroupNameFromIndex(obj, group.group)
		if groupName is not None:
			if groupName in armatureObj.data.bones:
				actualGroups.append(group)
			else:
				nonBoneGroups.append(groupName)

	if len(actualGroups) == 0:
		return rootGroupIndex
		#highlightWeightErrors(obj, [vert], "VERT")
		#raise VertexWeightError("All vertices must be part of a vertex group that corresponds to a bone in the armature.\n" +\
		#	"Groups of the bad vert that don't correspond to a bone: " + str(nonBoneGroups) + '. If a vert is supposed to belong to this group then either a bone is missing or you have the wrong group.')
	
	vertGroup = actualGroups[0]
	for group in actualGroups:
		if group.weight > vertGroup.weight:
			vertGroup = group
	#if vertGroup not in actualGroups:
	#raise VertexWeightError("A vertex was found that was primarily weighted to a group that does not correspond to a bone in #the armature. (" + getGroupNameFromIndex(obj, vertGroup.group) + ') Either decrease the weights of this vertex group or remove it. If you think this group should correspond to a bone, make sure to check your spelling.')
	return vertGroup.group

def ootDuplicateArmature(originalArmatureObj):
	# Duplicate objects to apply scale / modifiers / linked data
	bpy.ops.object.select_all(action = 'DESELECT')
	
	for originalMeshObj in [obj for obj in originalArmatureObj.children if isinstance(obj.data, bpy.types.Mesh)]:
		originalMeshObj.select_set(True)
		originalMeshObj.original_name = originalMeshObj.name

	originalArmatureObj.select_set(True)
	originalArmatureObj.original_name = originalArmatureObj.name
	bpy.context.view_layer.objects.active = originalArmatureObj
	bpy.ops.object.duplicate()

	armatureObj = bpy.context.view_layer.objects.active
	meshObjs = [obj for obj in bpy.context.selected_objects if obj is not armatureObj]

	try:
		# convert blender to n64 space, then set all bones to be non-rotated
		applyRotation([armatureObj], math.radians(90), 'X')
		restPoseRotations = setArmatureToNonRotatedPose(armatureObj)
			
		# Apply modifiers/data to mesh objs
		bpy.ops.object.select_all(action = 'DESELECT')
		for obj in meshObjs:
			obj.select_set(True)
			bpy.context.view_layer.objects.active = obj

		bpy.ops.object.make_single_user(obdata = True)
		bpy.ops.object.transform_apply(location = False, 
			rotation = True, scale = True, properties =  False)
		for selectedObj in meshObjs:
			bpy.ops.object.select_all(action = 'DESELECT')
			selectedObj.select_set(True)
			bpy.context.view_layer.objects.active = selectedObj

			for modifier in selectedObj.modifiers:
				attemptModifierApply(modifier)
		
		# Apply new armature rest pose
		bpy.ops.object.select_all(action = "DESELECT")
		bpy.context.view_layer.objects.active = armatureObj
		bpy.ops.object.mode_set(mode = "POSE")
		bpy.ops.pose.armature_apply()
		bpy.ops.object.mode_set(mode = "OBJECT")

		return armatureObj, meshObjs, restPoseRotations
	except Exception as e:
		cleanupDuplicatedObjects(meshObjs + [armatureObj])
		originalArmatureObj.select_set(True)
		bpy.context.view_layer.objects.active = originalArmatureObj
		raise Exception(str(e))

def ootConvertArmatureToSkeletonWithoutMesh(originalArmatureObj, convertTransformMatrix, name):
	skeleton, fModel, restPoseRotations = ootConvertArmatureToSkeleton(originalArmatureObj, convertTransformMatrix, 
		None, name, False, True)
	return skeleton, restPoseRotations

def ootConvertArmatureToSkeletonWithMesh(originalArmatureObj, convertTransformMatrix, 
	f3dType, isHWv1, name, DLFormat, convertTextureData):
	fModel = OOTModel(f3dType, isHWv1, name, DLFormat)
	skeleton, fModel, restPoseRotations = ootConvertArmatureToSkeleton(originalArmatureObj, convertTransformMatrix, 
		fModel, name, convertTextureData, False)
	return skeleton, fModel

def ootConvertArmatureToSkeleton(originalArmatureObj, convertTransformMatrix, 
	fModel, name, convertTextureData, skeletonOnly):
	checkEmptyName(name)

	armatureObj, meshObjs, restPoseRotations = ootDuplicateArmature(originalArmatureObj)
	
	try:
		skeleton = OOTSkeleton(name)

		if len(armatureObj.children) == 0:
			raise PluginError("No mesh parented to armature.")

		#startBoneNames = sorted([bone.name for bone in armatureObj.data.bones if bone.parent is None])
		#startBoneName = startBoneNames[0]
		checkForStartBone(armatureObj)
		startBoneName = getStartBone(armatureObj)
		meshObj = meshObjs[0]

		meshInfo = getInfoDict(meshObj)
		getGroupIndices(meshInfo, armatureObj, meshObj, getGroupIndexFromname(meshObj, startBoneName))

		convertTransformMatrix = convertTransformMatrix @ \
			mathutils.Matrix.Diagonal(armatureObj.scale).to_4x4()

		#for i in range(len(startBoneNames)):
		#	startBoneName = startBoneNames[i]
		ootProcessBone(fModel, startBoneName, skeleton, 0, 
			meshObj, armatureObj, convertTransformMatrix, meshInfo, convertTextureData, name, skeletonOnly)

		cleanupDuplicatedObjects(meshObjs + [armatureObj])
		originalArmatureObj.select_set(True)
		bpy.context.view_layer.objects.active = originalArmatureObj

		return skeleton, fModel, restPoseRotations
	except Exception as e:
		cleanupDuplicatedObjects(meshObjs + [armatureObj])
		originalArmatureObj.select_set(True)
		bpy.context.view_layer.objects.active = originalArmatureObj
		raise Exception(str(e))

def ootProcessBone(fModel, boneName, parentLimb, nextIndex, meshObj, armatureObj, 
	convertTransformMatrix, meshInfo, convertTextureData, namePrefix, skeletonOnly):
	bone = armatureObj.data.bones[boneName]
	if bone.parent is not None:
		transform = convertTransformMatrix @ bone.parent.matrix_local.inverted() @ bone.matrix_local
	else:
		transform = convertTransformMatrix @ bone.matrix_local

	translate, rotate, scale = transform.decompose()

	meshInfo.vertexGroupInfo.vertexGroupToLimb[getGroupIndexFromname(meshObj, boneName)] = nextIndex
	if skeletonOnly:
		mesh = None
		hasSkinnedFaces = None
	else:
		mesh, hasSkinnedFaces = ootProcessVertexGroup(fModel, meshObj, boneName, 
			convertTransformMatrix, armatureObj, namePrefix,
			meshInfo, "Opaque", convertTextureData)

	DL = None
	if mesh is not None:
		if not bone.use_deform:
			raise PluginError(bone.name + " has vertices in its vertex group but is not set to deformable. Make sure to enable deform on this bone.")
		DL = mesh.draw
		
	if isinstance(parentLimb, OOTSkeleton):
		skeleton = parentLimb
		limb = OOTLimb(skeleton.name, nextIndex, translate, DL, None)
		skeleton.limbRoot = limb
	else:
		limb = OOTLimb(parentLimb.skeletonName, nextIndex, translate, DL, None)
		parentLimb.children.append(limb)

	limb.isFlex = hasSkinnedFaces
	nextIndex += 1

	childrenNames = getSortedChildren(armatureObj, bone)
	for childName in childrenNames:
		nextIndex = ootProcessBone(fModel, childName, limb, nextIndex, meshObj, armatureObj, 
			convertTransformMatrix, meshInfo, convertTextureData, namePrefix, skeletonOnly)
	
	return nextIndex

def ootConvertArmatureToC(originalArmatureObj, convertTransformMatrix, 
	f3dType, isHWv1, skeletonName, folderName, DLFormat, convertTextureData, exportPath, isCustomExport):

	skeleton, fModel = ootConvertArmatureToSkeletonWithMesh(originalArmatureObj, convertTransformMatrix, 
		f3dType, isHWv1, skeletonName, DLFormat, convertTextureData)

	data = CData()
	staticData, dynamicData, texC = fModel.to_c(False, not convertTextureData, "test", OOTGfxFormatter(ScrollMethod.Vertex))
	skeletonC = skeleton.toC()

	data.append(staticData)
	data.append(dynamicData)
	data.append(texC)
	data.append(skeletonC)

	path = ootGetPath(exportPath, isCustomExport, 'assets/objects/', folderName)
	writeCData(data, 
		os.path.join(path, folderName + '.h'),
		os.path.join(path, folderName + '.c'))

	if not isCustomExport:
		pass # Modify other level files here

class OOT_ExportSkeleton(bpy.types.Operator):
	# set bl_ properties
	bl_idname = 'object.oot_export_skeleton'
	bl_label = "Export Skeleton"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	# Called on demand (i.e. button press, menu item)
	# Can also be called from operator search menu (Spacebar)
	def execute(self, context):
		armatureObj = None
		if context.mode != 'OBJECT':
			raise PluginError("Operator can only be used in object mode.")
		if len(context.selected_objects) == 0:
			raise PluginError("Armature not selected.")
		armatureObj = context.active_object
		if type(armatureObj.data) is not bpy.types.Armature:
			raise PluginError("Armature not selected.")

		if len(armatureObj.children) == 0 or \
			not isinstance(armatureObj.children[0].data, bpy.types.Mesh):
			raise PluginError("Armature does not have any mesh children, or " +\
				'has a non-mesh child.')

		obj = armatureObj.children[0]
		finalTransform = mathutils.Matrix.Scale(context.scene.ootBlenderScale, 4)

		try:
			#exportPath, levelName = getPathAndLevel(context.scene.geoCustomExport, 
			#	context.scene.geoExportPath, context.scene.geoLevelName, 
			#	context.scene.geoLevelOption)

			saveTextures = bpy.context.scene.ootSaveTextures or bpy.context.scene.ignoreTextureRestrictions
			isHWv1 = context.scene.isHWv1
			f3dType = context.scene.f3d_type
			skeletonName = context.scene.ootSkeletonName
			folderName = context.scene.ootSkeletonFolderName
			exportPath = context.scene.ootSkeletonCustomPath
			isCustomExport = context.scene.ootSkeletonUseCustomPath

			ootConvertArmatureToC(armatureObj, finalTransform, 
				f3dType, isHWv1, skeletonName, folderName, DLFormat.Static, saveTextures,
				exportPath, isCustomExport)

			self.report({'INFO'}, 'Success!')		
			return {'FINISHED'}

		except Exception as e:
			if context.mode != 'OBJECT':
				bpy.ops.object.mode_set(mode = 'OBJECT')
			raisePluginError(self, e)
			return {'CANCELLED'} # must return a set

class OOT_ExportSkeletonPanel(bpy.types.Panel):
	bl_idname = "OOT_PT_export_skeleton"
	bl_label = "OOT Skeleton Exporter"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'OOT'

	@classmethod
	def poll(cls, context):
		return True

	# called every frame
	def draw(self, context):
		col = self.layout.column()
		col.operator(OOT_ExportSkeleton.bl_idname)
		
		prop_split(col, context.scene, 'ootSkeletonName', "Skeleton Name")
		col.prop(context.scene, "ootSkeletonUseCustomPath")
		if context.scene.ootSkeletonUseCustomPath:
			prop_split(col, context.scene, 'ootSkeletonCustomPath', "Custom Skeleton Path")

oot_skeleton_classes = (
	OOT_ExportSkeleton,
)

oot_skeleton_panels = (
	OOT_ExportSkeletonPanel,
)

def oot_skeleton_panel_register():
	for cls in oot_skeleton_panels:
		register_class(cls)

def oot_skeleton_panel_unregister():
	for cls in oot_skeleton_panels:
		unregister_class(cls)

def oot_skeleton_register():
	bpy.types.Scene.ootSkeletonName = bpy.props.StringProperty(
		name = "Skeleton Name", default = "skeleton")
	bpy.types.Scene.ootSkeletonFolderName = bpy.props.StringProperty(
		name = "Skeleton Folder", default = "skeleton")
	bpy.types.Scene.ootSkeletonCustomPath = bpy.props.StringProperty(
		name ='Custom Skeleton Path', subtype = 'FILE_PATH')
	bpy.types.Scene.ootSkeletonUseCustomPath = bpy.props.BoolProperty(
		name = "Use Custom Path")

	for cls in oot_skeleton_classes:
		register_class(cls)

def oot_skeleton_unregister():
	del bpy.types.Scene.ootSkeletonCustomPath
	del bpy.types.Scene.ootSkeletonFolderName
	del bpy.types.Scene.ootSkeletonUseCustomPath
	del bpy.types.Scene.ootSkeletonName

	for cls in reversed(oot_skeleton_classes):
		unregister_class(cls)