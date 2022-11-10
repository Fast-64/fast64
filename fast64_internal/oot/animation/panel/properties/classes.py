from bpy.types import PropertyGroup
from bpy.props import BoolProperty, StringProperty, IntProperty
from .....f3d.flipbook import ootFlipbookAnimUpdate


# The update callbacks are for manually setting texture with visualize operator.
# They don't run from animation updates, see flipbookAnimHandler in flipbook.py
def ootUpdateLinkEyes(self, context):
    index = self.eyes
    ootFlipbookAnimUpdate(self, context.object, "8", index)


def ootUpdateLinkMouth(self, context):
    index = self.mouth
    ootFlipbookAnimUpdate(self, context.object, "9", index)


class OOTAnimExportSettingsProperty(PropertyGroup):
    isCustom: BoolProperty(name="Use Custom Path")
    customPath: StringProperty(name="Folder", subtype="FILE_PATH")
    folderName: StringProperty(name="Animation Folder", default="object_geldb")
    isLink: BoolProperty(name="Is Link", default=False)
    skeletonName: StringProperty(name="Skeleton Name", default="gGerudoRedSkel")


class OOTAnimImportSettingsProperty(PropertyGroup):
    isCustom: BoolProperty(name="Use Custom Path")
    customPath: StringProperty(name="Folder", subtype="FILE_PATH")
    folderName: StringProperty(name="Animation Folder", default="object_geldb")
    isLink: BoolProperty(name="Is Link", default=False)
    animName: StringProperty(name="Anim Name", default="gGerudoRedSpinAttackAnim")


class OOTLinkTextureAnimProperty(PropertyGroup):
    eyes: IntProperty(min=0, max=15, default=0, name="Eyes", update=ootUpdateLinkEyes)
    mouth: IntProperty(min=0, max=15, default=0, name="Mouth", update=ootUpdateLinkMouth)
