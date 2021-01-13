import shutil, copy

from ..f3d.f3d_writer import *
from ..f3d.f3d_material import TextureProperty, tmemUsageUI
from bpy.utils import register_class, unregister_class
from .oot_constants import *
from .oot_utility import *

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