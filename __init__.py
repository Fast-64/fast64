import bpy
from bpy.utils import register_class, unregister_class
from . import addon_updater_ops
from .fast64_internal.operators import AddWaterBox
from .fast64_internal.panels import SM64_Panel
from .fast64_internal.utility import PluginError, raisePluginError, attemptModifierApply, prop_split

from .fast64_internal.sm64 import SM64_Properties, sm64_register, sm64_unregister
from .fast64_internal.sm64.sm64_geolayout_bone import SM64_BoneProperties
from .fast64_internal.sm64.sm64_objects import SM64_ObjectProperties
from .fast64_internal.sm64.sm64_geolayout_utility import createBoneGroups
from .fast64_internal.sm64.sm64_geolayout_parser import generateMetarig

from .fast64_internal.oot import OOT_Properties, oot_register, oot_unregister
from .fast64_internal.oot.oot_level import OOT_ObjectProperties
from .fast64_internal.utility_anim import utility_anim_register, utility_anim_unregister, ArmatureApplyWithMeshOperator

from .fast64_internal.f3d.f3d_material import mat_register, mat_unregister
from .fast64_internal.f3d.f3d_render_engine import render_engine_register, render_engine_unregister
from .fast64_internal.f3d.f3d_writer import f3d_writer_register, f3d_writer_unregister
from .fast64_internal.f3d.f3d_parser import f3d_parser_register, f3d_parser_unregister
from .fast64_internal.f3d.flipbook import flipbook_register, flipbook_unregister

from .fast64_internal.f3d_material_converter import (
    MatUpdateConvert,
    upgradeF3DVersionAll,
    bsdf_conv_register,
    bsdf_conv_unregister,
    bsdf_conv_panel_regsiter,
    bsdf_conv_panel_unregsiter,
)

from .fast64_internal.render_settings import (
    Fast64RenderSettings_Properties,
    resync_scene_props,
    on_update_render_settings,
)

# info about add on
bl_info = {
    "name": "Fast64",
    "version": (2, 0, 0),
    "author": "kurethedead",
    "location": "3DView",
    "description": "Plugin for exporting F3D display lists and other game data related to Nintendo 64 games.",
    "category": "Import-Export",
    "blender": (3, 2, 0),
}

gameEditorEnum = (
    ("SM64", "SM64", "Super Mario 64"),
    ("OOT", "OOT", "Ocarina Of Time"),
)


class AddBoneGroups(bpy.types.Operator):
    # set bl_ properties
    bl_description = (
        "Add bone groups respresenting other node types in " + "SM64 geolayouts (ex. Shadow, Switch, Function)."
    )
    bl_idname = "object.add_bone_groups"
    bl_label = "Add Bone Groups"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT" and context.mode != "POSE":
                raise PluginError("Operator can only be used in object or pose mode.")
            elif context.mode == "POSE":
                bpy.ops.object.mode_set(mode="OBJECT")

            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            elif type(context.selected_objects[0].data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            armatureObj = context.selected_objects[0]
            createBoneGroups(armatureObj)
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Created bone groups.")
        return {"FINISHED"}  # must return a set


class CreateMetarig(bpy.types.Operator):
    # set bl_ properties
    bl_description = (
        "SM64 imported armatures are usually not good for "
        + "rigging. There are often intermediate bones between deform bones "
        + "and they don't usually point to their children. This operator "
        + "creates a metarig on armature layer 4 useful for IK."
    )
    bl_idname = "object.create_metarig"
    bl_label = "Create Animatable Metarig"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            elif type(context.selected_objects[0].data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            armatureObj = context.selected_objects[0]
            generateMetarig(armatureObj)
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Created metarig.")
        return {"FINISHED"}  # must return a set


class SM64_AddWaterBox(AddWaterBox):
    bl_idname = "object.sm64_add_water_box"

    scale: bpy.props.FloatProperty(default=10)
    preset: bpy.props.StringProperty(default="Shaded Solid")
    matName: bpy.props.StringProperty(default="sm64_water_mat")

    def setEmptyType(self, emptyObj):
        emptyObj.sm64_obj_type = "Water Box"


class SM64_ArmatureToolsPanel(SM64_Panel):
    bl_idname = "SM64_PT_armature_tools"
    bl_label = "SM64 Tools"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(ArmatureApplyWithMeshOperator.bl_idname)
        col.operator(AddBoneGroups.bl_idname)
        col.operator(CreateMetarig.bl_idname)
        col.operator(SM64_AddWaterBox.bl_idname)


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
        prop_split(col, context.scene, "f3d_type", "F3D Microcode")
        col.prop(context.scene, "isHWv1")
        col.prop(context.scene, "saveTextures")
        col.prop(context.scene, "f3d_simple", text="Simple Material UI")
        col.prop(context.scene, "generateF3DNodeGraph", text="Generate F3D Node Graph For Materials")
        col.prop(context.scene, "decomp_compatible", invert_checkbox=True, text="Homebrew Compatibility")
        col.prop(context.scene, "ignoreTextureRestrictions")
        if context.scene.ignoreTextureRestrictions:
            col.box().label(text="Width/height must be < 1024. Must be png format.")


class Fast64_GlobalObjectPanel(bpy.types.Panel):
    bl_label = "Global Object Inspector"
    bl_idname = "OBJECT_PT_OOT_Global_Object_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.data is None

    def draw(self, context):
        box = self.layout
        prop_split(box, context.scene, "gameEditorMode", "Game")


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
        prop_split(col, context.scene, "gameEditorMode", "Game")
        col.prop(context.scene, "exportHiddenGeometry")
        col.prop(context.scene, "fullTraceback")
        prop_split(col, context.scene.fast64.settings, "anim_range_choice", "Anim Range")


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
        addon_updater_ops.update_notice_box_ui(self, context)


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


class Fast64_Properties(bpy.types.PropertyGroup):
    """
    Properties in scene.fast64.
    All new properties should be children of one of these three property groups.
    """

    sm64: bpy.props.PointerProperty(type=SM64_Properties, name="SM64 Properties")
    oot: bpy.props.PointerProperty(type=OOT_Properties, name="OOT Properties")
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
            box = layout.box()
            box.label(text="Materials were successfully upgraded.")
            box.label(text="Please purge your remaining materials.")

            purge_box = box.box()
            purge_box.scale_y = 0.25
            purge_box.separator(factor=0.5)
            purge_box.label(text="How to purge:")
            purge_box.separator(factor=0.5)
            purge_box.label(text="Go to the outliner, change the display mode")
            purge_box.label(text='to "Orphan Data" (broken heart icon)')
            purge_box.separator(factor=0.25)
            purge_box.label(text='Click "Purge" in the top right corner.')
            purge_box.separator(factor=0.25)
            purge_box.label(text="Purge multiple times until the node groups")
            purge_box.label(text="are gone.")
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

        upgradeF3DVersionAll(
            [obj for obj in bpy.data.objects if isinstance(obj.data, bpy.types.Mesh)],
            list(bpy.data.armatures),
            MatUpdateConvert.version,
        )
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
    Fast64_Properties,
    Fast64_BoneProperties,
    Fast64_ObjectProperties,
    AddBoneGroups,
    CreateMetarig,
    SM64_AddWaterBox,
    # Fast64_GlobalObjectPanel,
    F3D_GlobalSettingsPanel,
    Fast64_GlobalSettingsPanel,
    SM64_ArmatureToolsPanel,
    Fast64_GlobalToolsPanel,
    UpgradeF3DMaterialsDialog,
)


def upgrade_changed_props():
    """Set scene properties after a scene loads, used for migrating old properties"""
    SM64_Properties.upgrade_changed_props()
    SM64_ObjectProperties.upgrade_changed_props()
    OOT_ObjectProperties.upgrade_changed_props()


def upgrade_scene_props_node():
    """update f3d materials with SceneProperties node"""
    has_old_f3d_mats = any(mat.is_f3d and mat.mat_ver < MatUpdateConvert.version for mat in bpy.data.materials)
    if has_old_f3d_mats:
        bpy.ops.dialog.upgrade_f3d_materials("INVOKE_DEFAULT")


@bpy.app.handlers.persistent
def after_load(_a, _b):
    upgrade_changed_props()
    upgrade_scene_props_node()
    resync_scene_props()


def gameEditorUpdate(self, context):
    if self.gameEditorMode == "SM64":
        self.f3d_type = "F3D"
    elif self.gameEditorMode == "OOT":
        self.f3d_type = "F3DEX2/LX2"


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

    for cls in classes:
        register_class(cls)

    bsdf_conv_panel_regsiter()
    f3d_writer_register()
    flipbook_register()
    f3d_parser_register()

    # ROM

    bpy.types.Scene.decomp_compatible = bpy.props.BoolProperty(name="Decomp Compatibility", default=True)
    bpy.types.Scene.ignoreTextureRestrictions = bpy.props.BoolProperty(name="Ignore Texture Restrictions")
    bpy.types.Scene.fullTraceback = bpy.props.BoolProperty(name="Show Full Error Traceback", default=False)
    bpy.types.Scene.gameEditorMode = bpy.props.EnumProperty(
        name="Game", default="SM64", items=gameEditorEnum, update=gameEditorUpdate
    )
    bpy.types.Scene.saveTextures = bpy.props.BoolProperty(name="Save Textures As PNGs (Breaks CI Textures)")
    bpy.types.Scene.generateF3DNodeGraph = bpy.props.BoolProperty(name="Generate F3D Node Graph", default=True)
    bpy.types.Scene.exportHiddenGeometry = bpy.props.BoolProperty(name="Export Hidden Geometry", default=True)
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
    flipbook_unregister()
    f3d_writer_unregister()
    f3d_parser_unregister()
    sm64_unregister(True)
    oot_unregister(True)
    mat_unregister()
    bsdf_conv_unregister()
    bsdf_conv_panel_unregsiter()
    render_engine_unregister()

    del bpy.types.Scene.fullTraceback
    del bpy.types.Scene.decomp_compatible
    del bpy.types.Scene.ignoreTextureRestrictions
    del bpy.types.Scene.saveTextures
    del bpy.types.Scene.gameEditorMode
    del bpy.types.Scene.generateF3DNodeGraph
    del bpy.types.Scene.exportHiddenGeometry
    del bpy.types.Scene.blenderF3DScale

    del bpy.types.Scene.fast64
    del bpy.types.Bone.fast64
    del bpy.types.Object.fast64

    for cls in classes:
        unregister_class(cls)

    bpy.app.handlers.load_post.remove(after_load)

    addon_updater_ops.unregister()
    unregister_class(ExampleAddonPreferences)
