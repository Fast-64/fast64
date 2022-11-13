from bpy.types import Panel, Armature, Object, PropertyGroup
from bpy.utils import register_class, unregister_class
from bpy.props import PointerProperty, BoolProperty, StringProperty, IntProperty
from ....utility import prop_split
from ....f3d.flipbook import ootFlipbookAnimUpdate


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


#############
#   Panel   #
#############
class OOT_LinkAnimPanel(Panel):
    bl_idname = "OOT_PT_link_anim"
    bl_label = "OOT Link Animation Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return (
            context.scene.gameEditorMode == "OOT"
            and hasattr(context, "object")
            and context.object is not None
            and isinstance(context.object.data, Armature)
        )

    # called every frame
    def draw(self, context):
        col = self.layout.box().column()
        col.box().label(text="OOT Link Animation Inspector")
        prop_split(col, context.object.ootLinkTextureAnim, "eyes", "Eyes")
        prop_split(col, context.object.ootLinkTextureAnim, "mouth", "Mouth")
        col.label(text="Index 0 is for auto, flipbook starts at index 1.", icon="INFO")


classes = (
    OOTLinkTextureAnimProperty,
    OOTAnimExportSettingsProperty,
    OOTAnimImportSettingsProperty,
)

panels = (OOT_LinkAnimPanel,)


def anim_props_panel_register():
    for cls in panels:
        register_class(cls)


def anim_props_panel_unregister():
    for cls in panels:
        unregister_class(cls)


def anim_props_classes_register():
    for cls in classes:
        register_class(cls)

    Object.ootLinkTextureAnim = PointerProperty(type=OOTLinkTextureAnimProperty)


def anim_props_classes_unregister():
    for cls in reversed(classes):
        unregister_class(cls)

    del Object.ootLinkTextureAnim
