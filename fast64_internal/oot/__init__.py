import bpy
from bpy.utils import register_class, unregister_class
from .oot_level import oot_obj_panel_register, oot_obj_panel_unregister, oot_obj_register, oot_obj_unregister
from .skeleton.panel.viewport import OOTSkeletonImportSettings, OOTSkeletonExportSettings
from .oot_utility import oot_utility_register, oot_utility_unregister, setAllActorsVisibility
from .other.panel.viewport.display_list import OOTDLExportSettings, OOTDLImportSettings
from .other.panel.viewport.file_settings import file_register, file_unregister
from .oot_anim import OOTAnimExportSettingsProperty, OOTAnimImportSettingsProperty
from .c_writer import OOTBootupSceneOptions

from .scene.panel.properties import scene_props_classes_register, scene_props_classes_unregister
from .cutscene.panel.properties import cutscene_props_classes_register, cutscene_props_classes_unregister
from .room.panel.properties import room_props_classes_register, room_props_classes_unregister
from .actor.panel.properties import actor_props_classes_register, actor_props_classes_unregister

from .oot_f3d_writer import (
    oot_dl_writer_panel_register,
    oot_dl_writer_panel_unregister,
    oot_dl_writer_register,
    oot_dl_writer_unregister,
)

from .other.panel.viewport.display_list import (
    dl_writer_panel_register,
    dl_writer_panel_unregister,
    dl_writer_register,
    dl_writer_unregister,
)

from .collision.panel.viewport import (
    collision_viewport_panel_register,
    collision_viewport_panel_unregister,
    collision_viewport_classes_register,
    collision_viewport_classes_unregister,
)

from .collision.panel.properties import (
    collision_props_panel_register,
    collision_props_panel_unregister,
    collision_props_classes_register,
    collision_props_classes_unregister,
)

from .scene.panel.viewport import (
    oot_level_panel_register,
    oot_level_panel_unregister,
    oot_level_register,
    oot_level_unregister,
)

from .animation.panel.viewport import (
    anim_viewport_panel_register,
    anim_viewport_panel_unregister,
    anim_viewport_classes_register,
    anim_viewport_classes_unregister,
)

from .animation.panel.properties import (
    anim_props_panel_register,
    anim_props_panel_unregister,
    anim_props_classes_register,
    anim_props_classes_unregister,
)

from .other.panel.viewport.tools import (
    oot_operator_panel_register,
    oot_operator_panel_unregister,
    oot_operator_register,
    oot_operator_unregister,
)

from .cutscene.panel.viewport import (
    oot_cutscene_panel_register,
    oot_cutscene_panel_unregister,
    oot_cutscene_register,
    oot_cutscene_unregister,
)

from .skeleton.panel.viewport import (
    skeletonPanelRegister,
    skeletonPanelUnregister,
    skeletonRegister,
    skeletonUnregister,
)

from .skeleton.panel.properties import (
    skeleton_props_panel_register,
    skeleton_props_panel_unregister,
    skeleton_props_classes_register,
    skeleton_props_classes_unregister,
)

from .spline.panel.properties import (
    spline_props_panel_register,
    spline_props_panel_unregister,
    spline_props_classes_register,
    spline_props_classes_unregister,
)


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
    skeletonExportSettings: bpy.props.PointerProperty(type=OOTSkeletonExportSettings)
    skeletonImportSettings: bpy.props.PointerProperty(type=OOTSkeletonImportSettings)
    animExportSettings: bpy.props.PointerProperty(type=OOTAnimExportSettingsProperty)
    animImportSettings: bpy.props.PointerProperty(type=OOTAnimImportSettingsProperty)


oot_classes = (
    OOT_Properties,
)


def oot_panel_register():
    oot_operator_panel_register()
    oot_dl_writer_panel_register()
    collision_viewport_panel_register()
    collision_props_panel_register()
    oot_obj_panel_register()
    oot_level_panel_register()
    spline_props_panel_register()
    anim_viewport_panel_register()
    skeleton_props_panel_register()
    oot_cutscene_panel_register()
    skeletonPanelRegister()
    dl_writer_panel_register()
    anim_props_panel_register()



def oot_panel_unregister():
    oot_operator_panel_unregister()
    collision_viewport_panel_unregister()
    collision_props_panel_unregister()
    oot_obj_panel_unregister()
    oot_level_panel_unregister()
    spline_props_panel_unregister()
    oot_dl_writer_panel_unregister()
    anim_viewport_panel_unregister()
    skeleton_props_panel_unregister()
    oot_cutscene_panel_unregister()
    skeletonPanelUnregister()
    dl_writer_panel_unregister()
    anim_props_panel_unregister()


def oot_register(registerPanels):
    oot_operator_register()
    oot_utility_register()
    collision_viewport_classes_register()  # register first, so panel goes above mat panel
    collision_props_classes_register()
    oot_level_register()
    cutscene_props_classes_register()
    scene_props_classes_register()
    room_props_classes_register()
    actor_props_classes_register()
    oot_obj_register()
    spline_props_classes_register()
    oot_dl_writer_register()
    anim_viewport_classes_register()
    skeleton_props_classes_register()
    oot_cutscene_register()
    skeletonRegister()
    dl_writer_register()
    file_register()
    anim_props_classes_register()

    for cls in oot_classes:
        register_class(cls)

    if registerPanels:
        oot_panel_register()


def oot_unregister(unregisterPanels):
    for cls in reversed(oot_classes):
        unregister_class(cls)

    oot_operator_unregister()
    oot_utility_unregister()
    collision_viewport_classes_unregister()  # register first, so panel goes above mat panel
    collision_props_classes_unregister()
    oot_obj_unregister()
    oot_level_unregister()
    cutscene_props_classes_unregister()
    scene_props_classes_unregister()
    room_props_classes_unregister()
    actor_props_classes_unregister()
    spline_props_classes_unregister()
    oot_dl_writer_unregister()
    anim_viewport_classes_unregister()
    skeleton_props_classes_unregister()
    oot_cutscene_unregister()
    skeletonUnregister()
    dl_writer_unregister()
    file_unregister()
    anim_props_classes_unregister()

    if unregisterPanels:
        oot_panel_unregister()
