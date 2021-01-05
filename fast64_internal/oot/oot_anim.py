import shutil, copy

from ..f3d.f3d_writer import *
from ..f3d.f3d_material import TextureProperty, tmemUsageUI
from bpy.utils import register_class, unregister_class
from .oot_constants import *
from .oot_utility import *

class OOTSkeleton():
	def __init__(self):
		self.segmentID = None
		self.limbRoot = None

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
	def __init__(self, translation, DL, lodDL):
		self.translation = translation
		self.firstChildIndex = 0xFF
		self.nextSiblingIndex = 0xFF
		self.DL = DL
		self.lodDL = lodDL

		self.index = None
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

class OOTAnimation:
	def __init__(self):
		self.segmentID = None


oot_anim_classes = (
)

oot_anim_panels = (
)

def oot_anim_panel_register():
	for cls in oot_anim_panels:
		register_class(cls)

def oot_anim_panel_unregister():
	for cls in oot_anim_panels:
		unregister_class(cls)

def oot_anim_register():
	for cls in oot_anim_classes:
		register_class(cls)

def oot_anim_unregister():
	for cls in reversed(oot_anim_classes):
		unregister_class(cls)