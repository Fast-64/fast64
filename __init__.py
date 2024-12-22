import bpy
from bpy.utils import register_class, unregister_class
from bpy.path import abspath

from . import addon_updater_ops

from .fast64_internal.utility import prop_split, multilineLabel, set_prop_if_in_data

from .fast64_internal.repo_settings import (
    draw_repo_settings,
    load_repo_settings,
    repo_settings_operators_register,
    repo_settings_operators_unregister,
)

from .fast64_internal.sm64 import sm64_register, sm64_unregister
from .fast64_internal.sm64.sm64_constants import sm64_world_defaults
from .fast64_internal.sm64.settings.properties import SM64_Properties
from .fast64_internal.sm64.sm64_geolayout_bone import SM64_BoneProperties
from .fast64_internal.sm64.sm64_objects import SM64_ObjectProperties

from .fast64_internal.oot import OOT_Properties, oot_register, oot_unregister
from .fast64_internal.oot.oot_constants import oot_world_defaults
from .fast64_internal.oot.props_panel_main import OOT_ObjectProperties
from .fast64_internal.utility_anim import utility_anim_register, utility_anim_unregister, ArmatureApplyWithMeshOperator

from .fast64_internal.mk64 import MK64_Properties, mk64_register, mk64_unregister

from .fast64_internal.f3d.f3d_material import (
    F3D_MAT_CUR_VERSION,
    mat_register,
    mat_unregister,
    check_or_ask_color_management,
)
from .fast64_internal.f3d.f3d_render_engine import render_engine_register, render_engine_unregister
from .fast64_internal.f3d.f3d_writer import f3d_writer_register, f3d_writer_unregister
from .fast64_internal.f3d.f3d_parser import f3d_parser_register, f3d_parser_unregister
from .fast64_internal.f3d.flipbook import flipbook_register, flipbook_unregister
from .fast64_internal.f3d.op_largetexture import op_largetexture_register, op_largetexture_unregister, ui_oplargetexture

from .fast64_internal.f3d_material_converter import (
    MatUpdateConvert,
    upgrade_f3d_version_all_meshes,
    bsdf_conv_register,
    bsdf_conv_unregister,
    bsdf_conv_panel_regsiter,
    bsdf_conv_panel_unregsiter,
)

from .fast64_internal.render_settings import (
    Fast64RenderSettings_Properties,
    ManualUpdatePreviewOperator,
    resync_scene_props,
    on_update_render_settings,
)

# info about add on
bl_info = {
    "name": "Fast64",
    "version": (2, 3, 0),
    "author": "kurethedead",
    "location": "3DView",
    "description": "Plugin for exporting F3D display lists and other game data related to Nintendo 64 games.",
    "category": "Import-Export",
    "blender": (3, 2, 0),
}

gameEditorEnum = (
    ("SM64", "SM64", "Super Mario 64", 0),
    ("OOT", "OOT", "Ocarina Of Time", 1),
    ("MK64", "MK64", "Mario Kart 64", 3),
    ("Homebrew", "Homebrew", "Homebrew", 2),
)


class F3D_GlobalSettingsPanel(bpy.types.Panel):
    bl_idname = "F3D_PT_global_settings"
    bl_label = "F3D Global Settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fast64"

    @classmethod
    def poll(cls, context):
        return True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding
        prop_split(col, context.scene, "f3d_type", "Microcode")
        col.prop(context.scene, "saveTextures")
        col.prop(context.scene, "f3d_simple", text="Simple Material UI")
        col.prop(context.scene, "exportInlineF3D", text="Bleed and Inline Material Exports")
        if context.scene.exportInlineF3D:
            multilineLabel(
                col.box(),
                "While inlining, all meshes will be restored to world default values.\n         You can configure these values in the world properties tab.",
                icon="INFO",
            )
        col.prop(context.scene, "ignoreTextureRestrictions")
        if context.scene.ignoreTextureRestrictions:
            col.box().label(text="Width/height must be < 1024. Must be png format.")


class Fast64_GlobalSettingsPanel(bpy.types.Panel):
    bl_idname = "FAST64_PT_global_settings"
    bl_label = "Fast64 Global Settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fast64"

    @classmethod
    def poll(cls, context):
        return True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding

        scene = context.scene
        fast64_settings: Fast64Settings_Properties = scene.fast64.settings

        prop_split(col, scene, "gameEditorMode", "Game")
        col.prop(scene, "exportHiddenGeometry")
        col.prop(scene, "fullTraceback")

        prop_split(col, fast64_settings, "anim_range_choice", "Anim Range")

        draw_repo_settings(col.box(), context)
        if not fast64_settings.repo_settings_tab:
            col.prop(fast64_settings, "auto_pick_texture_format")
            if fast64_settings.auto_pick_texture_format:
                col.prop(fast64_settings, "prefer_rgba_over_ci")


class Fast64_GlobalToolsPanel(bpy.types.Panel):
    bl_idname = "FAST64_PT_global_tools"
    bl_label = "Fast64 Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fast64"

    @classmethod
    def poll(cls, context):
        return True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(ArmatureApplyWithMeshOperator.bl_idname)
        # col.operator(CreateMetarig.bl_idname)
        ui_oplargetexture(col, context)
        addon_updater_ops.update_notice_box_ui(self, context)


def repo_path_update(self, context):
    load_repo_settings(context.scene, abspath(self.repo_settings_path), True)


class Fast64Settings_Properties(bpy.types.PropertyGroup):
    """Settings affecting exports for all games found in scene.fast64.settings"""

    version: bpy.props.IntProperty(name="Fast64Settings_Properties Version", default=0)

    anim_range_choice: bpy.props.EnumProperty(
        name="Anim Range",
        description="What to use to determine what frames of the animation to export",
        items=[
            ("action", "Action", "Export all frames from the action", 0),
            (
                "scene",
                "Playback",
                (
                    "Export all frames in the scene's animation preview playback range.\n"
                    "(export frames being played in Blender)"
                ),
                1,
            ),
            (
                "intersect_action_and_scene",
                "Smart",
                (
                    "Intersect Action & Scene\n"
                    "Export all frames from the action that are also in the scene playback range.\n"
                    "(export frames being played in Blender that also are part of the action frames)"
                ),
                2,
            ),
        ],
        default="intersect_action_and_scene",
    )
    auto_pick_texture_format: bpy.props.BoolProperty(
        name="Auto Pick Texture Format",
        description="When enabled, fast64 will try to pick the best texture format whenever a texture is selected.",
        default=True,
    )
    prefer_rgba_over_ci: bpy.props.BoolProperty(
        name="Prefer RGBA Over CI",
        description="When enabled, fast64 will default colored textures's format to RGBA even if they fit CI requirements, with the exception of textures that would not fit into TMEM otherwise",
    )
    dont_ask_color_management: bpy.props.BoolProperty(name="Don't ask to set color management properties")

    repo_settings_tab: bpy.props.BoolProperty(default=True, name="Repo Settings")
    repo_settings_path: bpy.props.StringProperty(name="Path", subtype="FILE_PATH", update=repo_path_update)
    auto_repo_load_settings: bpy.props.BoolProperty(
        name="Auto Load Repo's Settings",
        description="When enabled, this will make fast64 automatically load repo settings if they are found after picking a decomp path",
        default=True,
    )
    internal_fixed_4_2: bpy.props.BoolProperty(default=False)

    internal_game_update_ver: bpy.props.IntProperty(default=0)

    def to_repo_settings(self):
        data = {}
        data["autoLoad"] = self.auto_repo_load_settings
        data["autoPickTextureFormat"] = self.auto_pick_texture_format
        if self.auto_pick_texture_format:
            data["preferRGBAOverCI"] = self.prefer_rgba_over_ci
        return data

    def from_repo_settings(self, data: dict):
        set_prop_if_in_data(self, "auto_repo_load_settings", data, "autoLoad")
        set_prop_if_in_data(self, "auto_pick_texture_format", data, "autoPickTextureFormat")
        set_prop_if_in_data(self, "prefer_rgba_over_ci", data, "preferRGBAOverCI")


class Fast64_Properties(bpy.types.PropertyGroup):
    """
    Properties in scene.fast64.
    All new properties should be children of one of these three property groups.
    """

    sm64: bpy.props.PointerProperty(type=SM64_Properties, name="SM64 Properties")
    oot: bpy.props.PointerProperty(type=OOT_Properties, name="OOT Properties")
    mk64: bpy.props.PointerProperty(type=MK64_Properties, name="MK64 Properties")
    settings: bpy.props.PointerProperty(type=Fast64Settings_Properties, name="Fast64 Settings")
    renderSettings: bpy.props.PointerProperty(type=Fast64RenderSettings_Properties, name="Fast64 Render Settings")


class Fast64_BoneProperties(bpy.types.PropertyGroup):
    """
    Properties in bone.fast64 (bpy.types.Bone)
    All new bone properties should be children of this property group.
    """

    sm64: bpy.props.PointerProperty(type=SM64_BoneProperties, name="SM64 Properties")


class Fast64_ObjectProperties(bpy.types.PropertyGroup):
    """
    Properties in object.fast64 (bpy.types.Object)
    All new object properties should be children of this property group.
    """

    sm64: bpy.props.PointerProperty(type=SM64_ObjectProperties, name="SM64 Object Properties")
    oot: bpy.props.PointerProperty(type=OOT_ObjectProperties, name="OOT Object Properties")


class UpgradeF3DMaterialsDialog(bpy.types.Operator):
    bl_idname = "dialog.upgrade_f3d_materials"
    bl_label = "Upgrade F3D Materials"
    bl_options = {"REGISTER", "UNDO"}

    done = False

    def draw(self, context):
        layout = self.layout
        if self.done:
            layout.label(text="Success!")
            layout.label(text="Materials were successfully upgraded.")
            layout.separator(factor=0.25)
            layout.label(text="You may click anywhere to close this dialog.")
            return
        layout.alert = True
        box = layout.box()
        box.label(text="Your project contains F3D materials that need to be upgraded in order to continue!")
        box.label(text="Before upgrading, make sure to create a duplicate (backup) of this blend file.")
        box.separator()

        col = box.column()
        col.alignment = "CENTER"
        col.alert = True
        col.label(text="Upgrade F3D Materials?")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=600)

    def execute(self, context: "bpy.types.Context"):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        upgrade_f3d_version_all_meshes()
        self.done = True
        return {"FINISHED"}


# def updateGameEditor(scene, context):
# 	if scene.currentGameEditorMode == 'SM64':
# 		sm64_panel_unregister()
# 	elif scene.currentGameEditorMode == 'Z64':
# 		oot_panel_unregister()
# 	else:
# 		raise PluginError("Unhandled game editor mode " + str(scene.currentGameEditorMode))
#
# 	if scene.gameEditorMode == 'SM64':
# 		sm64_panel_register()
# 	elif scene.gameEditorMode == 'Z64':
# 		oot_panel_register()
# 	else:
# 		raise PluginError("Unhandled game editor mode " + str(scene.gameEditorMode))
#
# 	scene.currentGameEditorMode = scene.gameEditorMode


class ExampleAddonPreferences(bpy.types.AddonPreferences, addon_updater_ops.AddonUpdaterPreferences):
    bl_idname = __package__

    def draw(self, context):
        addon_updater_ops.update_settings_ui(self, context)


classes = (
    Fast64Settings_Properties,
    Fast64RenderSettings_Properties,
    ManualUpdatePreviewOperator,
    Fast64_Properties,
    Fast64_BoneProperties,
    Fast64_ObjectProperties,
    F3D_GlobalSettingsPanel,
    Fast64_GlobalSettingsPanel,
    Fast64_GlobalToolsPanel,
    UpgradeF3DMaterialsDialog,
)


def upgrade_changed_props():
    """Set scene properties after a scene loads, used for migrating old properties"""
    SM64_Properties.upgrade_changed_props()
    MK64_Properties.upgrade_changed_props()
    SM64_ObjectProperties.upgrade_changed_props()
    OOT_ObjectProperties.upgrade_changed_props()
    for scene in bpy.data.scenes:
        settings: Fast64Settings_Properties = scene.fast64.settings
        if settings.internal_game_update_ver != 1:
            set_game_defaults(scene, False)
            settings.internal_game_update_ver = 1
        if scene.get("decomp_compatible", False):
            scene.gameEditorMode = "Homebrew"
            del scene["decomp_compatible"]

        settings = scene.fast64.renderSettings
        light0Color = settings.pop("lightColor", None)
        if light0Color is not None:
            settings.light0Color = light0Color
        light0Direction = settings.pop("lightDirection", None)
        if light0Direction is not None:
            settings.light0Direction = light0Direction


def upgrade_scene_props_node():
    """update f3d materials with SceneProperties node"""
    has_old_f3d_mats = any(mat.is_f3d and mat.mat_ver < F3D_MAT_CUR_VERSION for mat in bpy.data.materials)
    if has_old_f3d_mats:
        bpy.ops.dialog.upgrade_f3d_materials("INVOKE_DEFAULT")


@bpy.app.handlers.persistent
def after_load(_a, _b):
    settings = bpy.context.scene.fast64.settings
    if any(mat.is_f3d for mat in bpy.data.materials):
        check_or_ask_color_management(bpy.context)
        if not settings.internal_fixed_4_2 and bpy.app.version >= (4, 2, 0):
            upgrade_f3d_version_all_meshes()
    if bpy.app.version >= (4, 2, 0):
        settings.internal_fixed_4_2 = True
    upgrade_changed_props()
    upgrade_scene_props_node()
    resync_scene_props()
    try:
        if settings.repo_settings_path:
            load_repo_settings(bpy.context.scene, abspath(settings.repo_settings_path), True)
    except Exception as exc:
        print(exc)


def set_game_defaults(scene: bpy.types.Scene, set_ucode=True):
    world_defaults = None
    if scene.gameEditorMode == "SM64":
        f3d_type = "F3D"
        world_defaults = sm64_world_defaults
    elif scene.gameEditorMode == "OOT":
        f3d_type = "F3DEX2/LX2"
        world_defaults = oot_world_defaults
    elif scene.gameEditorMode == "MK64":
        f3d_type = "F3DEX/LX"
    elif scene.gameEditorMode == "Homebrew":
        f3d_type = "F3D"
        world_defaults = {}  # This will set some pretty bad defaults, but trust the user
    if set_ucode:
        scene.f3d_type = f3d_type
    if scene.world is not None:
        scene.world.rdp_defaults.from_dict(world_defaults)


def gameEditorUpdate(scene: bpy.types.Scene, _context):
    set_game_defaults(scene)


# called on add-on enabling
# register operators and panels here
# append menu layout drawing function to an existing window
def register():
    if bpy.app.version < (3, 2, 0):
        msg = "\n".join(
            (
                "This version of Fast64 does not support Blender 3.1.x and earlier Blender versions.",
                "Your Blender version is: " + ".".join(str(i) for i in bpy.app.version),
                "Please upgrade Blender to 3.2.0 or above.",
            )
        )
        print(msg)
        unsupported_exc = Exception("\n\n" + msg)
        raise unsupported_exc

    # Register addon updater first,
    # this way if a broken version fails to register the user can still pick another version.
    register_class(ExampleAddonPreferences)
    addon_updater_ops.register(bl_info)

    utility_anim_register()
    mat_register()
    render_engine_register()
    bsdf_conv_register()
    sm64_register(True)
    oot_register(True)
    mk64_register(True)

    repo_settings_operators_register()

    for cls in classes:
        register_class(cls)

    bsdf_conv_panel_regsiter()
    f3d_writer_register()
    flipbook_register()
    f3d_parser_register()
    op_largetexture_register()

    # ROM

    bpy.types.Scene.ignoreTextureRestrictions = bpy.props.BoolProperty(name="Ignore Texture Restrictions")
    bpy.types.Scene.fullTraceback = bpy.props.BoolProperty(name="Show Full Error Traceback", default=False)
    bpy.types.Scene.gameEditorMode = bpy.props.EnumProperty(
        name="Game", default="SM64", items=gameEditorEnum, update=gameEditorUpdate
    )
    bpy.types.Scene.saveTextures = bpy.props.BoolProperty(name="Save Textures As PNGs (Breaks CI Textures)")
    bpy.types.Scene.exportHiddenGeometry = bpy.props.BoolProperty(name="Export Hidden Geometry", default=True)
    bpy.types.Scene.exportInlineF3D = bpy.props.BoolProperty(
        name="Bleed and Inline Material Exports",
        description="Inlines and bleeds materials in a single mesh. GeoLayout + Armature exports bleed over entire model",
        default=False,
    )
    bpy.types.Scene.blenderF3DScale = bpy.props.FloatProperty(
        name="F3D Blender Scale", default=100, update=on_update_render_settings
    )

    bpy.types.Scene.fast64 = bpy.props.PointerProperty(type=Fast64_Properties, name="Fast64 Properties")
    bpy.types.Bone.fast64 = bpy.props.PointerProperty(type=Fast64_BoneProperties, name="Fast64 Bone Properties")
    bpy.types.Object.fast64 = bpy.props.PointerProperty(type=Fast64_ObjectProperties, name="Fast64 Object Properties")

    bpy.app.handlers.load_post.append(after_load)


# called on add-on disabling
def unregister():
    utility_anim_unregister()
    op_largetexture_unregister()
    flipbook_unregister()
    f3d_writer_unregister()
    f3d_parser_unregister()
    sm64_unregister(True)
    oot_unregister(True)
    mk64_unregister(True)
    mat_unregister()
    bsdf_conv_unregister()
    bsdf_conv_panel_unregsiter()
    render_engine_unregister()

    del bpy.types.Scene.fullTraceback
    del bpy.types.Scene.ignoreTextureRestrictions
    del bpy.types.Scene.saveTextures
    del bpy.types.Scene.gameEditorMode
    del bpy.types.Scene.exportHiddenGeometry
    del bpy.types.Scene.blenderF3DScale

    del bpy.types.Scene.fast64
    del bpy.types.Bone.fast64
    del bpy.types.Object.fast64

    repo_settings_operators_unregister()

    for cls in classes:
        unregister_class(cls)

    bpy.app.handlers.load_post.remove(after_load)

    addon_updater_ops.unregister()
    unregister_class(ExampleAddonPreferences)
