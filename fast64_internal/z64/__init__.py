import bpy

from pathlib import Path
from bpy.utils import register_class, unregister_class

from ..game_data import game_data
from ..utility import PluginError

from .scene.operators import scene_ops_register, scene_ops_unregister
from .scene.properties import OOTBootupSceneOptions, scene_props_register, scene_props_unregister
from .scene.panels import scene_panels_register, scene_panels_unregister

from .props_panel_main import oot_obj_panel_register, oot_obj_panel_unregister, oot_obj_register, oot_obj_unregister
from .skeleton.properties import OOTSkeletonImportSettings, OOTSkeletonExportSettings
from .collection_utility import collections_register, collections_unregister
from .utility import setAllActorsVisibility
from .file_settings import file_register, file_unregister
from .collision.properties import OOTCollisionExportSettings

from .room.operators import room_ops_register, room_ops_unregister
from .room.properties import room_props_register, room_props_unregister

from .actor.operators import actor_ops_register, actor_ops_unregister
from .actor.properties import actor_props_register, actor_props_unregister

from .f3d.operators import f3d_ops_register, f3d_ops_unregister
from .f3d.properties import OOTDLExportSettings, OOTDLImportSettings, f3d_props_register, f3d_props_unregister
from .f3d.panels import f3d_panels_register, f3d_panels_unregister

from .collision.operators import collision_ops_register, collision_ops_unregister
from .collision.properties import collision_props_register, collision_props_unregister
from .collision.panels import collision_panels_register, collision_panels_unregister

from .animation.operators import anim_ops_register, anim_ops_unregister
from .animation.panels import anim_panels_register, anim_panels_unregister
from .animation.properties import (
    OOTAnimExportSettingsProperty,
    OOTAnimImportSettingsProperty,
    anim_props_register,
    anim_props_unregister,
)

from .cutscene.operators import cutscene_ops_register, cutscene_ops_unregister
from .cutscene.properties import cutscene_props_register, cutscene_props_unregister
from .cutscene.panels import cutscene_panels_register, cutscene_panels_unregister
from .cutscene.preview import cutscene_preview_register, cutscene_preview_unregister

from .cutscene.motion.operators import csMotion_ops_register, csMotion_ops_unregister
from .cutscene.motion.properties import csMotion_props_register, csMotion_props_unregister
from .cutscene.motion.panels import csMotion_panels_register, csMotion_panels_unregister
from .cutscene.motion.preview import csMotion_preview_register, csMotion_preview_unregister

from .skeleton.operators import skeleton_ops_register, skeleton_ops_unregister
from .skeleton.properties import skeleton_props_register, skeleton_props_unregister
from .skeleton.panels import skeleton_panels_register, skeleton_panels_unregister

from .spline.properties import spline_props_register, spline_props_unregister
from .spline.panels import spline_panels_register, spline_panels_unregister

from .animated_mats.operators import animated_mats_ops_register, animated_mats_ops_unregister
from .animated_mats.panels import animated_mats_panels_register, animated_mats_panels_unregister
from .animated_mats.properties import (
    Z64_AnimatedMaterialExportSettings,
    Z64_AnimatedMaterialImportSettings,
    animated_mats_props_register,
    animated_mats_props_unregister,
)

from .hackeroot.operators import hackeroot_ops_register, hackeroot_ops_unregister
from .hackeroot.properties import HackerOoTSettings, hackeroot_props_register, hackeroot_props_unregister
from .hackeroot.panels import hackeroot_panels_register, hackeroot_panels_unregister

from .tools import (
    oot_operator_panel_register,
    oot_operator_panel_unregister,
    oot_operator_register,
    oot_operator_unregister,
)


feature_set_enum = (
    ("default", "Default", "Default"),
    ("hacker_oot", "HackerOoT", "Hacker OoT"),
)


oot_versions_items = [
    ("Custom", "Custom", "Custom", 0),
    ("ntsc-1.0", "ntsc-1.0", "ntsc-1.0", 11),
    ("ntsc-1.1", "ntsc-1.1", "ntsc-1.1", 12),
    ("pal-1.0", "pal-1.0", "pal-1.0", 13),
    ("ntsc-1.2", "ntsc-1.2", "ntsc-1.2", 14),
    ("pal-1.1", "pal-1.1", "pal-1.1", 15),
    ("gc-jp", "gc-jp", "gc-jp", 1),
    ("gc-jp-mq", "gc-jp-mq", "gc-jp-mq", 2),
    ("gc-us", "gc-us", "gc-us", 4),
    ("gc-us-mq", "gc-us-mq", "gc-us-mq", 5),
    ("gc-eu-mq-dbg", "gc-eu-mq-dbg", "gc-eu-mq-dbg", 8),
    ("gc-eu", "gc-eu", "gc-eu", 6),
    ("gc-eu-mq", "gc-eu-mq", "gc-eu-mq", 7),
    ("gc-jp-ce", "gc-jp-ce", "gc-jp-ce", 3),
    ("ique-cn", "ique-cn", "ique-cn", 16),
    ("hackeroot-mq", "HackerOoT (Legacy)", "hackeroot-mq", 9),
    ("legacy", "Legacy", "Older Decomp Version", 10),
]

mm_versions_items = [
    ("Custom", "Custom", "Custom", 0),
    ("n64-us", "n64-us", "n64-us", 1),
    ("legacy", "Legacy", "Older Decomp Version", 2),
]


class OOT_Properties(bpy.types.PropertyGroup):
    """Global OOT Scene Properties found under scene.fast64.oot"""

    version: bpy.props.IntProperty(name="OOT_Properties Version", default=0)
    feature_set: bpy.props.EnumProperty(name="Feature Set", default="decomp", items=feature_set_enum)
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
    collisionExportSettings: bpy.props.PointerProperty(type=OOTCollisionExportSettings)
    oot_version: bpy.props.EnumProperty(name="OoT Version", items=oot_versions_items, default="gc-eu-mq-dbg")
    mm_version: bpy.props.EnumProperty(name="MM Version", items=mm_versions_items, default="n64-us")
    oot_version_custom: bpy.props.StringProperty(name="Custom Version")
    mm_features: bpy.props.BoolProperty(name="Enable MM Features", default=False)
    hackeroot_settings: bpy.props.PointerProperty(type=HackerOoTSettings)
    anim_mats_export_settings: bpy.props.PointerProperty(type=Z64_AnimatedMaterialExportSettings)
    anim_mats_import_settings: bpy.props.PointerProperty(type=Z64_AnimatedMaterialImportSettings)

    def get_extracted_path(self):
        version = self.oot_version if game_data.z64.is_oot() else self.mm_version

        if version == "legacy":
            return "."
        else:
            return f"extracted/{version if version != 'Custom' else self.oot_version_custom}"

    def is_include_present(self, include_file: str):
        decomp_path = Path(bpy.context.scene.ootDecompPath).resolve()

        if not decomp_path.exists():
            raise PluginError(f"ERROR: invalid decomp path ('{decomp_path}').")

        include_file_path = decomp_path / "include" / include_file
        return include_file_path.exists()

    def is_globalh_present(self):
        return self.is_include_present("global.h")

    def is_z64sceneh_present(self):
        return self.is_include_present("z64scene.h")

    useDecompFeatures: bpy.props.BoolProperty(
        name="Use decomp for export", description="Use names and macros from decomp when exporting", default=True
    )

    exportMotionOnly: bpy.props.BoolProperty(
        name="Export CS Motion Data Only",
        description="Export everything (unchecked) or only the camera and actor motion data (checked).",
        default=False,
    )

    use_new_actor_panel: bpy.props.BoolProperty(
        name="Use newer actor panel",
        description="Use the new actor panel which provides detailed informations to set actor parameters.",
        default=True,
    )

    @staticmethod
    def upgrade_changed_props():
        if "hackerFeaturesEnabled" in bpy.context.scene.fast64.oot:
            bpy.context.scene.fast64.oot.feature_set = (
                "hacker_oot" if bpy.context.scene.fast64.oot["hackerFeaturesEnabled"] else "decomp"
            )
            del bpy.context.scene.fast64.oot["hackerFeaturesEnabled"]


oot_classes = (OOT_Properties,)


def oot_panel_register():
    oot_operator_panel_register()
    hackeroot_panels_register()
    cutscene_panels_register()
    scene_panels_register()
    f3d_panels_register()
    collision_panels_register()
    oot_obj_panel_register()
    spline_panels_register()
    anim_panels_register()
    skeleton_panels_register()
    animated_mats_panels_register()


def oot_panel_unregister():
    oot_operator_panel_unregister()
    hackeroot_panels_unregister()
    cutscene_panels_unregister()
    collision_panels_unregister()
    oot_obj_panel_unregister()
    scene_panels_unregister()
    spline_panels_unregister()
    f3d_panels_unregister()
    anim_panels_unregister()
    skeleton_panels_unregister()
    animated_mats_panels_unregister()


def oot_register(registerPanels):
    oot_operator_register()
    collections_register()
    collision_ops_register()  # register first, so panel goes above mat panel
    collision_props_register()
    cutscene_props_register()
    animated_mats_ops_register()
    animated_mats_props_register()
    scene_ops_register()
    scene_props_register()
    room_ops_register()
    room_props_register()
    actor_ops_register()
    actor_props_register()
    spline_props_register()
    f3d_props_register()
    anim_ops_register()
    skeleton_ops_register()
    skeleton_props_register()
    cutscene_ops_register()
    f3d_ops_register()
    file_register()
    anim_props_register()
    hackeroot_props_register()
    hackeroot_ops_register()

    csMotion_ops_register()
    csMotion_props_register()
    csMotion_panels_register()
    csMotion_preview_register()
    cutscene_preview_register()

    oot_obj_register()

    for cls in oot_classes:
        register_class(cls)

    if registerPanels:
        oot_panel_register()


def oot_unregister(unregisterPanels):
    if unregisterPanels:
        oot_panel_unregister()

    for cls in reversed(oot_classes):
        unregister_class(cls)

    oot_obj_unregister()

    cutscene_preview_unregister()
    csMotion_preview_unregister()
    csMotion_panels_unregister()
    csMotion_props_unregister()
    csMotion_ops_unregister()

    hackeroot_ops_unregister()
    hackeroot_props_unregister()
    anim_props_unregister()
    file_unregister()
    f3d_ops_unregister()
    cutscene_ops_unregister()
    skeleton_props_unregister()
    skeleton_ops_unregister()
    anim_ops_unregister()
    f3d_props_unregister()
    spline_props_unregister()
    actor_props_unregister()
    actor_ops_unregister()
    room_props_unregister()
    room_ops_unregister()
    scene_props_unregister()
    scene_ops_unregister()
    animated_mats_props_unregister()
    animated_mats_ops_unregister()
    cutscene_props_unregister()
    collision_props_unregister()
    collision_ops_unregister()
    collections_unregister()
    oot_operator_unregister()
