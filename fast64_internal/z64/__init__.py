import bpy
from bpy.utils import register_class, unregister_class

from .scene.operators import scene_ops_register, scene_ops_unregister
from .scene.properties import OOTBootupSceneOptions, scene_props_register, scene_props_unregister
from .scene.panels import scene_panels_register, scene_panels_unregister

from .props_panel_main import oot_obj_panel_register, oot_obj_panel_unregister, oot_obj_register, oot_obj_unregister
from .skeleton.properties import OOTSkeletonImportSettings, OOTSkeletonExportSettings
from .oot_utility import oot_utility_register, oot_utility_unregister, setAllActorsVisibility
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

from .tools import (
    oot_operator_panel_register,
    oot_operator_panel_unregister,
    oot_operator_register,
    oot_operator_unregister,
)

oot_versions_items = [
    ("Custom", "Custom", "Custom"),
    ("gc-jp", "gc-jp", "gc-jp"),
    ("gc-jp-mq", "gc-jp-mq", "gc-jp-mq"),
    ("gc-jp-ce", "gc-jp-ce", "gc-jp-ce"),
    ("gc-us", "gc-us", "gc-us"),
    ("gc-us-mq", "gc-us-mq", "gc-us-mq"),
    ("gc-eu", "gc-eu", "gc-eu"),
    ("gc-eu-mq", "gc-eu-mq", "gc-eu-mq"),
    ("gc-eu-mq-dbg", "gc-eu-mq-dbg", "gc-eu-mq-dbg"),
    ("hackeroot-mq", "HackerOoT", "hackeroot-mq"),  # TODO: force this value if HackerOoT features are enabled?
    ("legacy", "Legacy", "Older Decomp Version"),
]


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
    collisionExportSettings: bpy.props.PointerProperty(type=OOTCollisionExportSettings)
    oot_version: bpy.props.EnumProperty(name="OoT Version", items=oot_versions_items, default="gc-eu-mq-dbg")
    oot_version_custom: bpy.props.StringProperty(name="Custom Version")

    def get_extracted_path(self):
        if self.oot_version == "legacy":
            return "."
        else:
            return f"extracted/{self.oot_version if self.oot_version != 'Custom' else self.oot_version_custom}"

    useDecompFeatures: bpy.props.BoolProperty(
        name="Use decomp for export", description="Use names and macros from decomp when exporting", default=True
    )

    exportMotionOnly: bpy.props.BoolProperty(
        name="Export CS Motion Data Only",
        description=(
            "Export everything or only the camera and actor motion data.\n"
            + "This will insert the data into the cutscene."
        ),
        default=False,
    )


oot_classes = (OOT_Properties,)


def oot_panel_register():
    oot_operator_panel_register()
    cutscene_panels_register()
    scene_panels_register()
    f3d_panels_register()
    collision_panels_register()
    oot_obj_panel_register()
    spline_panels_register()
    anim_panels_register()
    skeleton_panels_register()


def oot_panel_unregister():
    oot_operator_panel_unregister()
    cutscene_panels_unregister()
    collision_panels_unregister()
    oot_obj_panel_unregister()
    scene_panels_unregister()
    spline_panels_unregister()
    f3d_panels_unregister()
    anim_panels_unregister()
    skeleton_panels_unregister()


def oot_register(registerPanels):
    oot_operator_register()
    oot_utility_register()
    collision_ops_register()  # register first, so panel goes above mat panel
    collision_props_register()
    cutscene_props_register()
    scene_ops_register()
    scene_props_register()
    room_ops_register()
    room_props_register()
    actor_ops_register()
    actor_props_register()
    oot_obj_register()
    spline_props_register()
    f3d_props_register()
    anim_ops_register()
    skeleton_ops_register()
    skeleton_props_register()
    cutscene_ops_register()
    f3d_ops_register()
    file_register()
    anim_props_register()

    csMotion_ops_register()
    csMotion_props_register()
    csMotion_panels_register()
    csMotion_preview_register()
    cutscene_preview_register()

    for cls in oot_classes:
        register_class(cls)

    if registerPanels:
        oot_panel_register()


def oot_unregister(unregisterPanels):
    for cls in reversed(oot_classes):
        unregister_class(cls)

    oot_operator_unregister()
    oot_utility_unregister()
    collision_ops_unregister()  # register first, so panel goes above mat panel
    collision_props_unregister()
    oot_obj_unregister()
    cutscene_props_unregister()
    scene_ops_unregister()
    scene_props_unregister()
    room_ops_unregister()
    room_props_unregister()
    actor_ops_unregister()
    actor_props_unregister()
    spline_props_unregister()
    f3d_props_unregister()
    anim_ops_unregister()
    skeleton_ops_unregister()
    skeleton_props_unregister()
    cutscene_ops_unregister()
    f3d_ops_unregister()
    file_unregister()
    anim_props_unregister()

    cutscene_preview_unregister()
    csMotion_preview_unregister()
    csMotion_panels_unregister()
    csMotion_props_unregister()
    csMotion_ops_unregister()

    if unregisterPanels:
        oot_panel_unregister()
