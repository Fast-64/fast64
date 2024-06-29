import traceback
from io_scene_gltf2.io.com.gltf2_io_extensions import Extension
import bpy
from bpy.types import PropertyGroup, UILayout, Panel. Context
from bpy.props import BoolProperty

# Original implementation from github.com/Mr-Wiseguy/gltf64-blender

# Changes made from the original glTF64:
# Property names (keys) now all use the glTF standard naming, camelCase.
# Full fast64 material support.
# Extendability improvements.
# Doesn´t use world defaults, as those should be left to the repo to handle.


GAME_MODES = {
    # "SM64": "EXT_SM64",
    # "OOT": "EXT_OOT",
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
            from .fast64_internal.f3d.f3d_gltf import Fast64Extension

            self.sub_extensions.append(Fast64Extension(self))


class glTF2ExportUserExtension(GlTF2Extension):
    @exception_handler_decorator('Object "{args[1].name}"')
    def gather_node_hook(self, gltf2_node, blender_object, export_settings):
        self.call_hooks("gather_node_hook", gltf2_node, blender_object, export_settings)

    @exception_handler_decorator('Material "{args[1].name}""')
    def gather_material_hook(self, gltf2_material, blender_material, export_settings):
        self.call_hooks("gather_material_hook", gltf2_material, blender_material, export_settings)


class glTF2ImportUserExtension(GlTF2Extension):
    @exception_handler_decorator('Object "{args[2].name}"')
    def gather_import_node_after_hook(self, vnode, gltf_node, blender_object, gltf):
        print("glTF2ImportUserExtension: gather_import_node_after_hook")


class Fast64GlTFSettings(PropertyGroup):
    verbose: BoolProperty(name="Verbose", description="Print all appended extension data, useful for troubleshooting")
    f3d: BoolProperty(default=True, name="Export F3D extension (EXT_fast64)")
    game: BoolProperty(default=True, name="Export current game mode")

    def draw_props(self, scene, layout: UILayout, show_import=False):
        col = layout.column()
        operation_text = "Import" if show_import else "Export"
        col.prop(self, "verbose")
        col.prop(self, "f3d", text=f"{operation_text} F3D extension (EXT_fast64)")
        if scene.gameEditorMode == "Homebrew":
            return
        if scene.gameEditorMode not in GAME_MODES:
            col.label(text="Current game mode not implemented", icon="INFO")
        else:
            col.prop(self, "export_game", text=f"{operation_text} {GAME_MODES[scene.gameEditorMode]} extension")


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
    Fast64GlTFPanel,
    Fast64GlTFSettings,
)


def gltf_extension_register():
    for cls in classes:
        bpy.utils.register_class(cls)


def gltf_extension_unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
