import traceback
import bpy

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


class glTF2ExportUserExtension:
    def __init__(self):
        from io_scene_gltf2.io.com.gltf2_io_extensions import Extension

        self.Extension = Extension
        settings = bpy.context.scene.fast64.settings.glTF
        self.verbose = settings.verbose

        self.sub_extensions = []
        if settings.export_f3d:
            from .fast64_internal.f3d.f3d_gltf import Fast64Extension

            self.sub_extensions.append(Fast64Extension(self))

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

    @exception_handler_decorator('Object "{args[1].name}"')
    def gather_node_hook(self, gltf2_node, blender_object, export_settings):
        self.call_hooks("gather_node_hook", gltf2_node, blender_object, export_settings)

    @exception_handler_decorator('Material "{args[1].name}""')
    def gather_material_hook(self, gltf2_material, blender_material, export_settings):
        self.call_hooks("gather_material_hook", gltf2_material, blender_material, export_settings)


class Fast64GlTFSettings(bpy.types.PropertyGroup):
    export_f3d: bpy.props.BoolProperty(default=True, name="Export F3D extension (EXT_fast64)")
    export_game: bpy.props.BoolProperty(default=True, name="Export current game mode")
    verbose: bpy.props.BoolProperty(
        name="Verbose", description="Print all appended extension data, useful for troubleshooting"
    )

    def draw_props(self, scene, layout: bpy.types.UILayout):
        col = layout.column()
        col.prop(self, "verbose")
        col.prop(self, "export_f3d")
        if scene.gameEditorMode == "Homebrew":
            return
        if scene.gameEditorMode not in GAME_MODES:
            col.label(text="Current game mode not implemented", icon="INFO")
        else:
            col.prop(self, "export_game", text=f"Export {GAME_MODES[scene.gameEditorMode]} extension")


class Fast64GlTFPanel(bpy.types.Panel):
    bl_idname = "GLTF_F3D_PT_export"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOL_PROPS"
    bl_label = "Fast64"
    bl_parent_id = "FILE_PT_operator"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_SCENE_OT_gltf"

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False  # No animation.
        context.scene.fast64.settings.glTF.draw_props(context.scene, layout)


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
