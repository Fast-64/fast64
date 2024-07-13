import traceback
from io_scene_gltf2.io.com.gltf2_io_extensions import Extension
import bpy
from bpy.types import PropertyGroup, UILayout, Panel, Context
from bpy.props import BoolProperty, PointerProperty

from .fast64_internal.utility import multilineLabel
from .fast64_internal.f3d.glTF.f3d_gltf import F3DGlTFSettings

# Original implementation from github.com/Mr-Wiseguy/gltf64-blender

# Changes made from the original glTF64:
# Property names (keys) now all use the glTF standard naming, camelCase.
# Extension names all follow the glTF2 naming convention, PREFIX_scope_feature.
# Full fast64 material support.
# Extendability improvements.
# Doesn´t use world defaults, as those should be left to the repo to handle.


GAME_MODES = {
    # "SM64": {"FAST64_node_sm64"},
    # "OOT": {"FAST64_node_oot"},
}


def exception_handler_decorator(message_template=""):
    def decorator(method):
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Exception as exc:
                message = message_template.format(self=self, args=args, kwargs=kwargs)
                raise Exception(f"{message}\n" + traceback.format_exc()) from exc

        return wrapper

    return decorator


class GlTF2Extension:
    def call_hooks(self, hook: str, *args):
        exceptions = []
        for extension in self.sub_extensions:
            try:
                if hasattr(extension, hook):
                    getattr(extension, hook)(*args)
            except Exception as e:
                exceptions.append(e)
        for e in exceptions:
            raise e

    def __init__(self):
        self.Extension = Extension
        self.settings = bpy.context.scene.fast64.settings.glTF
        self.verbose = self.settings.verbose
        self.sub_extensions = []
        if self.settings.f3d:
            from .fast64_internal.f3d.glTF.f3d_gltf import F3DExtensions

            self.sub_extensions.append(F3DExtensions(self))


class glTF2ExportUserExtension(GlTF2Extension):
    importing = False

    @exception_handler_decorator('Object "{args[1].name}"')
    def gather_node_hook(self, gltf2_node, blender_object, export_settings):
        self.call_hooks("gather_node_hook", gltf2_node, blender_object, export_settings)

    @exception_handler_decorator('Material "{args[1].name}""')
    def gather_material_hook(self, gltf2_material, blender_material, export_settings):
        self.call_hooks("gather_material_hook", gltf2_material, blender_material, export_settings)


class glTF2ImportUserExtension(GlTF2Extension):
    importing = True

    @exception_handler_decorator('Material "{args[2].name}""')
    def gather_import_material_after_hook(self, gltf_material, vertex_color, blender_mat, gltf):
        self.call_hooks("gather_import_material_after_hook", gltf_material, vertex_color, blender_mat, gltf)

    @exception_handler_decorator('Object "{args[1].name}"')
    def gather_import_node_after_hook(self, vnode, gltf_node, blender_object, gltf):
        self.call_hooks("gather_import_node_after_hook", vnode, gltf_node, blender_object, gltf)


class Fast64GlTFSettings(PropertyGroup):
    verbose: BoolProperty(name="Verbose", description="Print all appended extension data, useful for troubleshooting")
    f3d: PointerProperty(type=F3DGlTFSettings)
    game: BoolProperty(default=True, name="Export current game mode")

    def draw_props(self, scene, layout: UILayout, import_context=False):
        col = layout.column()
        col.prop(self, "verbose")
        self.f3d.draw_props(col.box(), import_context)

        game_mode = scene.gameEditorMode
        if game_mode != "Homebrew":
            col.separator()
            operation_text = "Import" if import_context else "Export"
            if game_mode not in GAME_MODES:
                col.label(text="Current game mode not implemented", icon="INFO")
            else:
                col.prop(self, "game", text=f"{operation_text} {game_mode} extensions")
                multilineLabel(col.box(), ",\n".join(GAME_MODES[game_mode]))


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
