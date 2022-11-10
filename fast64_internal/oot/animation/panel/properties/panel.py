from bpy.types import Panel, Armature, Object
from bpy.utils import register_class, unregister_class
from bpy.props import PointerProperty
from .....utility import prop_split
from .classes import OOTAnimImportSettingsProperty, OOTAnimExportSettingsProperty, OOTLinkTextureAnimProperty


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

panels = (
    OOT_LinkAnimPanel,
)


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
