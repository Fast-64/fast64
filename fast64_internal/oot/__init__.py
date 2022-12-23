from .oot_actor import setAllActorsVisibility
import bpy
from .scene.exporter.to_c import OOTBootupSceneOptions
from ..panels import OOT_Panel
from bpy.utils import register_class, unregister_class
from .oot_level import oot_obj_panel_register, oot_obj_panel_unregister, oot_obj_register, oot_obj_unregister
from .oot_anim import oot_anim_panel_register, oot_anim_panel_unregister, oot_anim_register, oot_anim_unregister
from .oot_utility import oot_utility_register, oot_utility_unregister
from ..utility import prop_split
from ..render_settings import on_update_render_settings

from .oot_collision import (
    oot_col_panel_register,
    oot_col_panel_unregister,
    oot_col_register,
    oot_col_unregister,
    OOTCollisionExportSettings,
)

from .oot_f3d_writer import (
    OOTDLExportSettings,
    OOTDLImportSettings,
    oot_dl_writer_panel_register,
    oot_dl_writer_panel_unregister,
    oot_dl_writer_register,
    oot_dl_writer_unregister,
)

from .oot_level_writer import (
    oot_level_panel_register,
    oot_level_panel_unregister,
    oot_level_register,
    oot_level_unregister,
)

from .oot_operators import (
    oot_operator_panel_register,
    oot_operator_panel_unregister,
    oot_operator_register,
    oot_operator_unregister,
)

from .oot_skeleton import (
    oot_skeleton_panel_register,
    oot_skeleton_panel_unregister,
    oot_skeleton_register,
    oot_skeleton_unregister,
)

from .oot_spline import (
    oot_spline_panel_register,
    oot_spline_panel_unregister,
    oot_spline_register,
    oot_spline_unregister,
)

from .oot_cutscene import (
    oot_cutscene_panel_register,
    oot_cutscene_panel_unregister,
    oot_cutscene_register,
    oot_cutscene_unregister,
)


class OOT_FileSettingsPanel(OOT_Panel):
    bl_idname = "OOT_PT_file_settings"
    bl_label = "OOT File Settings"
    bl_options = set()  # default to being open

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding, makes it easier to see these main settings
        prop_split(col, context.scene, "ootBlenderScale", "OOT Scene Scale")

        prop_split(col, context.scene, "ootDecompPath", "Decomp Path")
        col.prop(context.scene.fast64.oot, "headerTabAffectsVisibility")
        col.prop(context.scene.fast64.oot, "hackerFeaturesEnabled")


class OOT_Properties(bpy.types.PropertyGroup):
    """Global OOT Scene Properties found under scene.fast64.oot"""

    version: bpy.props.IntProperty(name="OOT_Properties Version", default=0)
    hackerFeaturesEnabled: bpy.props.BoolProperty(name="Enable HackerOOT Features")
    headerTabAffectsVisibility: bpy.props.BoolProperty(
        default=False, name="Header Sets Actor Visibility", update=setAllActorsVisibility
    )
    bootupSceneOptions: bpy.props.PointerProperty(type=OOTBootupSceneOptions)
    DLExportSettings: bpy.props.PointerProperty(type=OOTDLExportSettings)
    DLImportSettings: bpy.props.PointerProperty(type=OOTDLImportSettings)
    skeletonExportSettings: bpy.props.PointerProperty(type=oot_skeleton.OOTSkeletonExportSettings)
    skeletonImportSettings: bpy.props.PointerProperty(type=oot_skeleton.OOTSkeletonImportSettings)
    animExportSettings: bpy.props.PointerProperty(type=oot_anim.OOTAnimExportSettingsProperty)
    animImportSettings: bpy.props.PointerProperty(type=oot_anim.OOTAnimImportSettingsProperty)
    collisionExportSettings: bpy.props.PointerProperty(type=OOTCollisionExportSettings)


oot_classes = (
    OOT_FileSettingsPanel,
    OOT_Properties,
)


def oot_panel_register():
    oot_operator_panel_register()
    oot_dl_writer_panel_register()
    oot_col_panel_register()
    oot_obj_panel_register()
    oot_level_panel_register()
    oot_spline_panel_register()
    oot_anim_panel_register()
    oot_skeleton_panel_register()
    oot_cutscene_panel_register()


def oot_panel_unregister():
    oot_operator_panel_unregister()
    oot_col_panel_unregister()
    oot_obj_panel_unregister()
    oot_level_panel_unregister()
    oot_spline_panel_unregister()
    oot_dl_writer_panel_unregister()
    oot_anim_panel_unregister()
    oot_skeleton_panel_unregister()
    oot_cutscene_panel_unregister()


def oot_register(registerPanels):
    oot_operator_register()
    oot_utility_register()
    oot_col_register()  # register first, so panel goes above mat panel
    oot_obj_register()
    oot_level_register()
    oot_spline_register()
    oot_dl_writer_register()
    oot_anim_register()
    oot_skeleton_register()
    oot_cutscene_register()

    for cls in oot_classes:
        register_class(cls)

    if registerPanels:
        oot_panel_register()

    bpy.types.Scene.ootBlenderScale = bpy.props.FloatProperty(
        name="Blender To OOT Scale", default=10, update=on_update_render_settings
    )
    bpy.types.Scene.ootDecompPath = bpy.props.StringProperty(name="Decomp Folder", subtype="FILE_PATH")


def oot_unregister(unregisterPanels):
    for cls in reversed(oot_classes):
        unregister_class(cls)

    oot_operator_unregister()
    oot_utility_unregister()
    oot_col_unregister()  # register first, so panel goes above mat panel
    oot_obj_unregister()
    oot_level_unregister()
    oot_spline_unregister()
    oot_dl_writer_unregister()
    oot_anim_unregister()
    oot_skeleton_unregister()
    oot_cutscene_unregister()

    if unregisterPanels:
        oot_panel_unregister()

    del bpy.types.Scene.ootBlenderScale
    del bpy.types.Scene.ootDecompPath
