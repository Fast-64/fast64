import traceback

import bpy
from bpy.types import PropertyGroup, UILayout, Panel, Context
from bpy.props import BoolProperty, PointerProperty

from .fast64_internal.utility import multilineLabel, prop_group_to_json, json_to_prop_group
from .fast64_internal.gltf_utility import get_gltf_settings
from .fast64_internal.f3d.glTF.f3d_gltf import (
    F3DGlTFSettings,
    F3DGlTFPanel,
    F3DExtensions,
    modify_f3d_nodes_for_export,
)

# Original implementation from github.com/Mr-Wiseguy/gltf64-blender

# Changes made from the original glTF64:
# Property names (keys) now all use the glTF standard naming, camelCase.
# Extension names all follow the glTF2 naming convention, PREFIX_scope_feature.
# Full fast64 v6 material support.
# Extendability improvements.
# Doesn´t use world defaults, as those should be left to the repo to handle.
# Hacks for broken versions
# Importing
# Better and more extensive errors


def glTF2_pre_export_callback(_gltf):
    modify_f3d_nodes_for_export(False)


def glTF2_post_export_callback(_gltf):
    modify_f3d_nodes_for_export(True)


def error_popup_handler(simple_error: str, full_error: str):
    def handler(self, _context):
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

                wm.popup_menu(
                    error_popup_handler(str(exc), full_error),
                    title=message,
                    icon="ERROR",
                )
                print(full_error)
                # TODO: Force glTF exports and imports to fail somehow?

    def __init__(self):
        from io_scene_gltf2.io.com.gltf2_io_extensions import Extension  # pylint: disable=import-error

        self.Extension = Extension

        self.settings = bpy.context.scene.fast64.settings.glTF
        self.verbose = self.settings.verbose
        self.sub_extensions = []
        if self.settings.f3d.use:
            self.sub_extensions.append(F3DExtensions(self))


class glTF2ExportUserExtension(GlTF2Extension):
    importing = False

    def gather_node_hook(self, gltf2_node, blender_object, export_settings):
        self.call_hooks(
            "gather_node_hook",
            'Object "{args[1].name}"',
            gltf2_node,
            blender_object,
            export_settings,
        )

    def gather_mesh_hook(self, gltf2_mesh, blender_mesh, blender_object, vertex_groups, modifiers, *last_args):
        materials, export_settings = last_args[-2:]  # 3.2
        self.call_hooks(
            "gather_mesh_hook",
            'Mesh "{args[1].name}"',
            gltf2_mesh,
            blender_mesh,
            blender_object,
            vertex_groups,
            modifiers,
            materials,
            export_settings,
        )

    def gather_material_hook(self, gltf2_material, blender_material, export_settings):
        self.call_hooks(
            "gather_material_hook",
            'Material "{args[1].name}"',
            gltf2_material,
            blender_material,
            export_settings,
        )

    def gather_gltf_extensions_hook(self, _gltf, _export_settings):
        modify_f3d_nodes_for_export(True)


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
            "gather_import_node_after_hook",
            'Object "{args[2].name}"',
            vnode,
            gltf_node,
            blender_object,
            gltf,
        )

    def gather_import_mesh_after_hook(self, gltf_mesh, blender_mesh, gltf):
        self.call_hooks(
            "gather_import_mesh_after_hook",
            'Mesh "{args[1].name}"',
            gltf_mesh,
            blender_mesh,
            gltf,
        )


class Fast64GlTFSettings(PropertyGroup):
    verbose: BoolProperty(
        name="Verbose",
        description="Print all appended extension data, useful for troubleshooting",
    )
    f3d: PointerProperty(type=F3DGlTFSettings)
    game: BoolProperty(default=True, name="Export current game mode")

    def to_dict(self):
        return prop_group_to_json(self)

    def from_dict(self, data: dict):
        json_to_prop_group(self, data)

    def draw_props(self, scene, layout: UILayout):
        col = layout.column()
        multilineLabel(
            col,
            "TIP: Create a repo settings file in the\n"
            "fast64 tab to save these settings for your\n"
            "repo.",  # pylint: disable=line-too-long
            icon="INFO",
        )
        col.separator()

        col.prop(self, "verbose")

        game_mode = scene.gameEditorMode
        if game_mode == "Homebrew":
            multilineLabel(
                col.box(),
                "Homebrew mode does not\nimplement any extensions",
                icon="INFO",
            )
        elif not getattr(self, game_mode.lower(), None):
            multilineLabel(
                col.box(),
                f"Current game mode ({game_mode})\nnot implemented",
                icon="INFO",
            )


class Fast64GlTFPanel(Panel):
    bl_idname = "GLTF_PT_Fast64"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOL_PROPS"
    bl_label = "Fast64"
    bl_parent_id = "FILE_PT_operator"

    @classmethod
    def poll(cls, context: Context):
        operator_idname = context.space_data.active_operator.bl_idname
        return operator_idname in ["EXPORT_SCENE_OT_gltf", "IMPORT_SCENE_OT_gltf"]

    def draw(self, context: Context):
        self.layout.use_property_decorate = False  # No animation.
        get_gltf_settings(context).draw_props(context.scene, self.layout)


classes = (F3DGlTFSettings, Fast64GlTFPanel, Fast64GlTFSettings, F3DGlTFPanel)


def gltf_extension_register():
    for cls in classes:
        bpy.utils.register_class(cls)


def gltf_extension_unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
