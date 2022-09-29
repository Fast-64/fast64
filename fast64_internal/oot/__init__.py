from . import oot_anim
from . import oot_collision
from . import oot_cutscene
from . import oot_f3d_writer
from . import oot_level
from . import oot_level_writer
from . import oot_operators
from . import oot_skeleton
from . import oot_spline
from . import oot_utility
from .c_writer import OOTBootupSceneOptions

from ..panels import OOT_Panel
from ..utility import prop_split
from ..render_settings import on_update_render_settings

import bpy
from bpy.utils import register_class, unregister_class


class OOT_FileSettingsPanel(OOT_Panel):
    bl_idname = "OOT_PT_file_settings"
    bl_label = "OOT File Settings"
    bl_options = set()  # default to being open

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding, makes it easier to see these main settings
        prop_split(col, context.scene, "ootBlenderScale", "OOT Scene Scale")
        prop_split(col, context.scene, "ootActorBlenderScale", "OOT Actor Scale")

        prop_split(col, context.scene, "ootDecompPath", "Decomp Path")
        col.prop(context.scene.fast64.oot, "hackerFeaturesEnabled")


class OOT_Properties(bpy.types.PropertyGroup):
    """Global OOT Scene Properties found under scene.fast64.oot"""

    version: bpy.props.IntProperty(name="OOT_Properties Version", default=0)
    hackerFeaturesEnabled: bpy.props.BoolProperty(name="Enable HackerOOT Features")
    bootupSceneOptions: bpy.props.PointerProperty(type=OOTBootupSceneOptions)
    DLExportSettings: bpy.props.PointerProperty(type=oot_f3d_writer.OOTDLExportSettings)
    DLImportSettings: bpy.props.PointerProperty(type=oot_f3d_writer.OOTDLImportSettings)
    skeletonExportSettings: bpy.props.PointerProperty(type=oot_skeleton.OOTSkeletonExportSettings)
    skeletonImportSettings: bpy.props.PointerProperty(type=oot_skeleton.OOTSkeletonImportSettings)


oot_classes = (
    OOT_FileSettingsPanel,
    OOT_Properties,
)


def oot_panel_register():
    oot_operators.oot_operator_panel_register()
    oot_f3d_writer.oot_dl_writer_panel_register()
    oot_collision.oot_col_panel_register()
    oot_level.oot_obj_panel_register()
    oot_level_writer.oot_level_panel_register()
    oot_spline.oot_spline_panel_register()
    oot_anim.oot_anim_panel_register()
    oot_skeleton.oot_skeleton_panel_register()
    oot_cutscene.oot_cutscene_panel_register()


def oot_panel_unregister():
    oot_operators.oot_operator_panel_unregister()
    oot_collision.oot_col_panel_unregister()
    oot_level.oot_obj_panel_unregister()
    oot_level_writer.oot_level_panel_unregister()
    oot_spline.oot_spline_panel_unregister()
    oot_f3d_writer.oot_dl_writer_panel_unregister()
    oot_anim.oot_anim_panel_unregister()
    oot_skeleton.oot_skeleton_panel_unregister()
    oot_cutscene.oot_cutscene_panel_unregister()


def oot_register(registerPanels):
    oot_operators.oot_operator_register()
    oot_utility.oot_utility_register()
    oot_collision.oot_col_register()  # register first, so panel goes above mat panel
    oot_level.oot_obj_register()
    oot_level_writer.oot_level_register()
    oot_spline.oot_spline_register()
    oot_f3d_writer.oot_dl_writer_register()
    oot_anim.oot_anim_register()
    oot_skeleton.oot_skeleton_register()
    oot_cutscene.oot_cutscene_register()

    for cls in oot_classes:
        register_class(cls)

    if registerPanels:
        oot_panel_register()

    bpy.types.Scene.ootBlenderScale = bpy.props.FloatProperty(
        name="Blender To OOT Scale", default=10, update=on_update_render_settings
    )
    bpy.types.Scene.ootActorBlenderScale = bpy.props.FloatProperty(name="Blender To OOT Actor Scale", default=1000)
    bpy.types.Scene.ootDecompPath = bpy.props.StringProperty(name="Decomp Folder", subtype="FILE_PATH")


def oot_unregister(unregisterPanels):
    for cls in reversed(oot_classes):
        unregister_class(cls)

    oot_operators.oot_operator_unregister()
    oot_utility.oot_utility_unregister()
    oot_collision.oot_col_unregister()  # register first, so panel goes above mat panel
    oot_level.oot_obj_unregister()
    oot_level_writer.oot_level_unregister()
    oot_spline.oot_spline_unregister()
    oot_f3d_writer.oot_dl_writer_unregister()
    oot_anim.oot_anim_unregister()
    oot_skeleton.oot_skeleton_unregister()
    oot_cutscene.oot_cutscene_unregister()

    if unregisterPanels:
        oot_panel_unregister()

    del bpy.types.Scene.ootBlenderScale
    del bpy.types.Scene.ootActorBlenderScale
    del bpy.types.Scene.ootDecompPath
