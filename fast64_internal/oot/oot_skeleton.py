import shutil, copy, mathutils

from ..f3d.f3d_writer import *
from ..f3d.f3d_material import TextureProperty, tmemUsageUI
from bpy.utils import register_class, unregister_class
from .oot_constants import *
from .oot_utility import *
from .oot_f3d_writer import *

class OOTSkeleton():
	def __init__(self):
		self.segmentID = None
		self.limbRoot = OOTLimb(0, (0,0,0), None, None)

	def createLimbList(self):
		limbList = []
		self.limbRoot.getList(limbList)
		self.limbRoot.setLinks()
		return limbList

	def getNumDLs(self):
		return self.limbRoot.getNumDLs()

	def getNumLimbs(self):
		return self.limbRoot.getNumLimbs()

def addLimbToList(limb, limbList):
	limbList.append(limb)
	return len(limbList) - 1

class OOTLimb():
	def __init__(self, index, translation, DL, lodDL):
		self.translation = translation
		self.firstChildIndex = 0xFF
		self.nextSiblingIndex = 0xFF
		self.DL = DL
		self.lodDL = lodDL

		self.index = index
		self.children = []

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

	def getList(self, limbList):
		self.index = addLimbToList(self, limbList)
		for child in self.children:
			child.getList(limbList)

	def setLinks(self):
		if len(self.children) > 0:
			self.firstChildIndex = self.children[0].index
		for i in range(len(self.children) - 1):
			self.children[i].nextSiblingIndex = self.children[i + 1].index
			self.children[i].setLinks()
		# self -> child -> sibling

# Convert to Geolayout
def ootConvertArmatureToSkeleton(armatureObj, meshObj, convertTransformMatrix, 
	f3dType, isHWv1, camera, name, DLFormat, convertTextureData):
	
	fModel = OOTModel(f3dType, isHWv1, name, DLFormat)
	skeleton = OOTSkeleton()

	if len(armatureObj.children) == 0:
		raise PluginError("No mesh parented to armature.")

	meshInfo = getInfoDict(meshObj)

	startBoneNames = sorted([bone.name for bone in armatureObj.data.bones if bone.parent is None])
	
	convertTransformMatrix = convertTransformMatrix @ \
		mathutils.Matrix.Diagonal(armatureObj.scale).to_4x4()

	boneNameIndexDict = {}
	for i in range(len(startBoneNames)):
		startBoneName = startBoneNames[i]
		ootProcessBone(fModel, startBoneName, skeleton.limbRoot, skeleton.limbRoot.index, boneNameIndexDict, 
			meshObj, armatureObj, convertTransformMatrix, meshInfo, convertTextureData)

	return skeleton, fModel

def ootProcessBone(fModel, boneName, parentLimb, nextIndex, boneNameIndexDict, meshObj, armatureObj, 
	convertTransformMatrix, meshInfo, convertTextureData):
	bone = armatureObj.data.bones[boneName]
	if bone.parent is not None:
		transform = convertTransformMatrix @ bone.parent.matrix_local.inverted() @ bone.matrix_local
	else:
		transform = convertTransformMatrix @ bone.matrix_local

	translate, rotate, scale = transform.decompose()
	translation = mathutils.Matrix.Translation(translate)

	boneNameIndexDict[boneName] = nextIndex
	meshGroup, makeLastDeformBone = ootProcessVertexGroup(
		fModel, meshObj, boneName, lastDeformName,
		finalTransform, armatureObj, 
		namePrefix, meshInfo, node.drawLayer, convertTextureData)

	DL = None
	if meshGroup is not None:
		if not bone.use_deform:
			raise PluginError(bone.name + " has vertices in its vertex group but is not set to deformable. Make sure to enable deform on this bone.")
		DL = meshGroup.mesh.draw
		
	limb = OOTLimb(nextIndex, translation, DL, None)
	parentLimb.children.append(limb)
	nextIndex += 1

	childrenNames = sorted([child.name for child in bone.children])
	for childName in childrenNames:
		nextIndex = ootProcessBone(fModel, childName, limb, nextIndex, boneNameIndexDict, meshObj, armatureObj, 
			convertTransformMatrix, meshInfo, convertTextureData)
	
	return nextIndex

def ootProcessVertexGroup(fModel, meshObj, vertexGroup, 
	parentGroup, transformMatrix, armatureObj, namePrefix,
	meshInfo, drawLayer, convertTextureData):

	mesh = meshObj.data
	currentGroupIndex = getGroupIndexFromname(meshObj, vertexGroup)
	vertIndices = [vert.index for vert in meshObj.data.vertices if\
		getGroupIndex(vert, armatureObj, meshObj) == currentGroupIndex]
	parentGroupIndex = getGroupIndexFromname(meshObj, parentGroup) \
		if parentGroup is not None else -1

	ancestorGroups = getAncestorGroups(parentGroup, vertexGroup, armatureObj, meshObj)

	if len(vertIndices) == 0:
		print("No vert indices in " + vertexGroup)
		return None, False

	bone = armatureObj.data.bones[vertexGroup]
	
	currentMatrix = mathutils.Matrix.Scale(1 * bpy.context.scene.blenderToSM64Scale, 4) @ \
		bone.matrix_local.inverted()
	
	if parentGroup is None:
		parentMatrix = mathutils.Matrix.Scale(1 * bpy.context.scene.blenderToSM64Scale, 4)
	else:
		parentBone = armatureObj.data.bones[parentGroup]
		parentMatrix = mathutils.Matrix.Scale(1 * bpy.context.scene.blenderToSM64Scale, 4) @ \
		parentBone.matrix_local.inverted()
	
	# dict of material_index keys to face array values
	groupFaces = {}
	
	# dict of material_index keys to SkinnedFace objects
	skinnedFaces = {}

	handledFaces = []
	for vertIndex in vertIndices:
		if vertIndex not in meshInfo['vert']:
			continue
		for face in meshInfo['vert'][vertIndex]:
			# Ignore repeat faces
			if face in handledFaces:
				continue
			else:
				handledFaces.append(face)

			loopsInGroup = []
			loopsNotInGroup = []
			isChildSkinnedFace = False

			# loop is interpreted as face + loop index
			for i in range(3):
				vertGroupIndex = \
					getGroupIndex(mesh.vertices[face.vertices[i]], 
						armatureObj, meshObj)
				if vertGroupIndex == currentGroupIndex:
					loopsInGroup.append((face, mesh.loops[face.loops[i]]))
				elif vertGroupIndex == parentGroupIndex:
					loopsNotInGroup.append((face, mesh.loops[face.loops[i]]))
				elif vertGroupIndex not in ancestorGroups:
					# Only want to handle skinned faces connected to parent
					isChildSkinnedFace = True
					break
				else:
					highlightWeightErrors(meshObj, [face], 'FACE')
					raise VertexWeightError("Error with " + vertexGroup + ": Verts attached to one bone can not be attached to any of its ancestor or sibling bones besides its first immediate deformable parent bone. For example, a foot vertex can be connected to a leg vertex, but a foot vertex cannot be connected to a thigh vertex.")
			if isChildSkinnedFace:
				continue
			
			if len(loopsNotInGroup) == 0:
				if face.material_index not in groupFaces:
					groupFaces[face.material_index] = []
				groupFaces[face.material_index].append(face)
			else:
				if face.material_index not in skinnedFaces:
					skinnedFaces[face.material_index] = []
				skinnedFaces[face.material_index].append(
					SkinnedFace(face, loopsInGroup, loopsNotInGroup))

	# Save skinned mesh
	if len(skinnedFaces) > 0:
		#print("Skinned")
		fMeshGroup = saveSkinnedMeshByMaterial(skinnedFaces, fModel,
			vertexGroup, meshObj, currentMatrix, parentMatrix, namePrefix, 
			meshInfo, vertexGroup, drawLayer, convertTextureData)
	elif len(groupFaces) > 0:
		fMeshGroup = FMeshGroup(toAlnum(namePrefix + \
			('_' if namePrefix != '' else '') + vertexGroup), 
			FMesh(toAlnum(namePrefix + \
			('_' if namePrefix != '' else '') + vertexGroup) + '_mesh', fModel.DLFormat), None, fModel.DLFormat)
	else:
		print("No faces in " + vertexGroup)
		return None, True
	
	# Save mesh group
	checkUniqueBoneNames(fModel, toAlnum(namePrefix + \
		('_' if namePrefix != '' else '') + vertexGroup), vertexGroup)
	fModel.meshGroups[toAlnum(namePrefix + vertexGroup)] = fMeshGroup

	# Save unskinned mesh
	for material_index, bFaces in groupFaces.items():
		material = meshObj.data.materials[material_index]
		checkForF3dMaterialInFaces(meshObj, material)
		saveMeshByFaces(material, bFaces, 
			fModel, fMeshGroup.mesh, meshObj, currentMatrix, meshInfo, drawLayer, convertTextureData)
	
	# End mesh drawing
	# Reset settings to prevent issues with other models
	#revertMatAndEndDraw(fMeshGroup.mesh.draw)
	fMeshGroup.mesh.draw.commands.extend([
		SPEndDisplayList(),
	])
	
	return fMeshGroup, True