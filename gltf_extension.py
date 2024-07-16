import traceback
from io_scene_gltf2.io.com.gltf2_io_extensions import Extension
import bpy
from bpy.types import PropertyGroup, UILayout, Panel, Context
from bpy.props import BoolProperty, PointerProperty

from .fast64_internal.utility import multilineLabel, prop_group_to_json, json_to_prop_group
from .fast64_internal.f3d.glTF.f3d_gltf import F3DGlTFSettings, F3DExtensions

# Original implementation from github.com/Mr-Wiseguy/gltf64-blender

# Changes made from the original glTF64:
# Property names (keys) now all use the glTF standard naming, camelCase.
# Extension names all follow the glTF2 naming convention, PREFIX_scope_feature.
# Full fast64 material support.
# Extendability improvements.
# Doesn´t use world defaults, as those should be left to the repo to handle.


def error_popup_handler(simple_error: str, full_error: str):
    def handler(self, context):
        col = self.layout.column()
        multilineLabel(col, simple_error, icon="INFO")
        col.separator()
        multilineLabel(col, full_error)

    return handler


class GlTF2Extension:
    def call_hooks(self, hook: str, message_template: str, *args):
        for extension in self.sub_extensions:
            try:
                if hasattr(extension, hook):
                    getattr(extension, hook)(*args)
            except Exception as exc:
                wm = bpy.context.window_manager
                message = f"Error in {message_template.format(self=self, args=args)}"
                error_location = f"{extension.__class__.__name__}.{hook}"
                full_error = f"{error_location}:\n{traceback.format_exc().rstrip()}"

                wm.popup_menu(error_popup_handler(str(exc), full_error), title=message, icon="ERROR")
                print(full_error)
                raise Exception from exc

    def __init__(self):
        self.Extension = Extension
        self.settings = bpy.context.scene.fast64.settings.glTF
        self.verbose = self.settings.verbose
        self.sub_extensions = []
        if self.settings.f3d:
            self.sub_extensions.append(F3DExtensions(self))


class glTF2ExportUserExtension(GlTF2Extension):
    importing = False

    def gather_node_hook(self, gltf2_node, blender_object, export_settings):
        self.call_hooks("gather_node_hook", 'Object "{args[1].name}"', gltf2_node, blender_object, export_settings)

    def gather_material_hook(self, gltf2_material, blender_material, export_settings):
        self.call_hooks(
            "gather_material_hook", 'Material "{args[1].name}"', gltf2_material, blender_material, export_settings
        )


class glTF2ImportUserExtension(GlTF2Extension):
    importing = True

    def gather_import_material_after_hook(self, gltf_material, vertex_color, blender_mat, gltf):
        self.call_hooks(
            "gather_import_material_after_hook",
            'Material "{args[2].name}""',
            gltf_material,
            vertex_color,
            blender_mat,
            gltf,
        )

    def gather_import_node_after_hook(self, vnode, gltf_node, blender_object, gltf):
        self.call_hooks(
            "gather_import_node_after_hook", 'Object "{args[1].name}"', vnode, gltf_node, blender_object, gltf
        )


class Fast64GlTFSettings(PropertyGroup):
    verbose: BoolProperty(name="Verbose", description="Print all appended extension data, useful for troubleshooting")
    f3d: PointerProperty(type=F3DGlTFSettings)
    game: BoolProperty(default=True, name="Export current game mode")

    def to_dict(self):
        return prop_group_to_json(self)

    def from_dict(self, data: dict):
        json_to_prop_group(self, data)

    def draw_props(self, scene, layout: UILayout, import_context=False):
        col = layout.column()
        multilineLabel(
            col,
            "TIP: Create a repo settings file in the\nfast64 tab to save these settings for your\nrepo.",
            icon="INFO",
        )
        col.separator()

        col.prop(self, "verbose")

        self.f3d.draw_props(col.box(), import_context)
        col.separator()

        game_mode = scene.gameEditorMode
        if game_mode == "Homebrew":
            col.box().label(text="Homebrew mode does not implement any extensions", icon="INFO")
        else:
            game_props = getattr(self, game_mode, None)
            if game_props:
                game_props.draw_props(col, import_context)
            else:
                col.label(text=f"Current game mode ({game_mode}) not implemented", icon="INFO")


class Fast64GlTFPanel(Panel):
    bl_idname = "GLTF_F3D_PT_export"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOL_PROPS"
    bl_label = "Fast64"
    bl_parent_id = "FILE_PT_operator"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context: Context):
        operator_idname = context.space_data.active_operator.bl_idname
        return operator_idname in ["EXPORT_SCENE_OT_gltf", "IMPORT_SCENE_OT_gltf"]

    def draw(self, context: Context):
        is_import = context.space_data.active_operator.bl_idname == "IMPORT_SCENE_OT_gltf"
        self.layout.use_property_decorate = False  # No animation.
        context.scene.fast64.settings.glTF.draw_props(context.scene, self.layout, is_import)


classes = (
    F3DGlTFSettings,
    Fast64GlTFPanel,
    Fast64GlTFSettings,
)


def gltf_extension_register():
    for cls in classes:
        bpy.utils.register_class(cls)


def gltf_extension_unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
