from bpy.types import Object, PropertyGroup
from bpy.utils import register_class, unregister_class
from bpy.props import PointerProperty, BoolProperty, StringProperty, IntProperty
from ...f3d.flipbook import ootFlipbookAnimUpdate


# The update callbacks are for manually setting texture with visualize operator.
# They don't run from animation updates, see flipbookAnimHandler in flipbook.py
def ootUpdateLinkEyes(self, context):
    index = self.eyes
    ootFlipbookAnimUpdate(self, context.object, "8", index)


def ootUpdateLinkMouth(self, context):
    index = self.mouth
    ootFlipbookAnimUpdate(self, context.object, "9", index)


class OOTAnimExportSettingsProperty(PropertyGroup):
    isCustomFilename: BoolProperty(name="Use Custom Filename", description="Override filename instead of basing it off of the Blender name")
    filename: StringProperty(name="Filename")
    isCustom: BoolProperty(name="Use Custom Path", description="Determines whether or not to export to an explicitly specified folder")
    customPath: StringProperty(name="Folder", subtype="FILE_PATH")
    folderName: StringProperty(name="Animation Folder", default="object_geldb")
    isLink: BoolProperty(name="Is Link", default=False)


class OOTAnimImportSettingsProperty(PropertyGroup):
    isCustom: BoolProperty(name="Use Custom Path")
    customPath: StringProperty(name="Folder", subtype="FILE_PATH")
    folderName: StringProperty(name="Animation Folder", default="object_geldb")
    isLink: BoolProperty(name="Is Link", default=False)
    animName: StringProperty(name="Anim Name", default="gGerudoRedSpinAttackAnim")


class OOTLinkTextureAnimProperty(PropertyGroup):
    eyes: IntProperty(min=0, max=15, default=0, name="Eyes", update=ootUpdateLinkEyes)
    mouth: IntProperty(min=0, max=15, default=0, name="Mouth", update=ootUpdateLinkMouth)


classes = (
    OOTAnimExportSettingsProperty,
    OOTAnimImportSettingsProperty,
    OOTLinkTextureAnimProperty,
)


def anim_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootLinkTextureAnim = PointerProperty(type=OOTLinkTextureAnimProperty)


def anim_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)

    del Object.ootLinkTextureAnim
