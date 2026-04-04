import contextlib
import ctypes
import os
import shutil
import subprocess
import tempfile

import bpy
try:
    import addon_utils
except Exception:
    addon_utils = None
from bpy.props import BoolProperty, StringProperty
from bpy.types import Context
from bpy.utils import register_class, unregister_class
from bpy_extras.io_utils import ImportHelper

from .f3d_material_converter import convertAllBSDFtoF3D
from .operators import OperatorBase
from .utility import PluginError, deselectAllObjects


GR2_IMPORT_OPERATOR_CANDIDATES = (
    "import_scene.divinitycollada",
    "import_scene.gr2",
    "import_scene.granny2",
    "import_scene.granny",
    "import_mesh.gr2",
    "wm.gr2_import",
    "wm.granny2_import",
    "wm.granny_import",
)

DEFAULT_GRANNY_INCLUDE_DIR = r"C:\mt2009 - FULL SOURCE\Source\Extern\include"
DEFAULT_FAST64_ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_GRANNY_RESOURCE_ROOT = os.path.abspath(
    os.path.join(DEFAULT_FAST64_ROOT, "Granny_Common_2_11_8_0_Release")
)
DEFAULT_DIVINE_CANDIDATES = (
    os.path.join(DEFAULT_FAST64_ROOT, "_github_addons", "ExportTool-v1.20.4", "Packed", "Tools", "Divine.exe"),
    os.path.join(
        DEFAULT_FAST64_ROOT,
        "_github_addons",
        "Blender_GR2_Format",
        "src",
        "io_scene_gr2",
        "ExportTool-v1.14.2",
        "divine.exe",
    ),
)
DEFAULT_DAE_VIA_OBJ_SCRIPT = os.path.join(
    DEFAULT_FAST64_ROOT, "_github_addons", "Blender-Collada-importer-Via-OBJ", "dea2obj2import.py"
)


def default_granny_dll_path() -> str:
    candidates = (
        os.path.join(DEFAULT_GRANNY_RESOURCE_ROOT, "lib", "win64", "granny2_x64.dll"),
        os.path.join(DEFAULT_GRANNY_RESOURCE_ROOT, "lib", "win32", "granny2.dll"),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return ""


def ensure_existing_or_empty(path: str) -> str:
    return path if path and os.path.exists(path) else ""


def default_divine_path() -> str:
    for candidate in DEFAULT_DIVINE_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return ""


def resolve_operator_module(module_name: str):
    module = getattr(bpy.ops, module_name, None)
    if module is None and module_name == "import":
        module = getattr(bpy.ops, "import_", None)
    return module


def operator_exists(operator_path: str) -> bool:
    module_name, operator_name = operator_path.split(".", 1)
    operator_module = resolve_operator_module(module_name)
    if operator_module is None:
        return False
    try:
        return operator_name in dir(operator_module)
    except Exception:
        return False


def call_operator(operator_path: str, filepath: str) -> tuple[bool, str]:
    module_name, operator_name = operator_path.split(".", 1)
    operator_module = resolve_operator_module(module_name)
    if operator_module is None:
        return False, f"{module_name} module not found."

    if not operator_exists(operator_path):
        return False, "operator not found."
    operator = getattr(operator_module, operator_name)

    try:
        result = operator(filepath=filepath)
    except Exception as exc:
        return False, str(exc)

    if "FINISHED" in result:
        return True, ""

    return False, f"operator returned {result}"


def ensure_dae_via_obj_importer() -> bool:
    module_name = "dea2obj2import"
    if addon_utils is None:
        return operator_exists("import_scene.dae_via_obj")

    try:
        enabled, _loaded = addon_utils.check(module_name)
    except Exception:
        enabled = False

    if not enabled and os.path.isfile(DEFAULT_DAE_VIA_OBJ_SCRIPT):
        try:
            bpy.ops.preferences.addon_install(filepath=DEFAULT_DAE_VIA_OBJ_SCRIPT, overwrite=False)
        except Exception:
            pass
        try:
            bpy.ops.preferences.addon_enable(module=module_name)
        except Exception:
            pass

    return operator_exists("import_scene.dae_via_obj")


def ensure_granny_dll_for_divine(divine_path: str, dll_path: str):
    if not divine_path or not os.path.isfile(divine_path):
        return
    divine_dir = os.path.dirname(divine_path)
    if not divine_dir or not os.path.isdir(divine_dir):
        return
    target = os.path.join(divine_dir, "granny2.dll")
    if os.path.isfile(target):
        return

    candidates = []
    if dll_path and os.path.isfile(dll_path):
        candidates.append(dll_path)
    candidates.extend(
        [
            os.path.join(DEFAULT_GRANNY_RESOURCE_ROOT, "lib", "win64", "granny2_x64.dll"),
            os.path.join(DEFAULT_GRANNY_RESOURCE_ROOT, "lib", "win32", "granny2.dll"),
        ]
    )

    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        try:
            shutil.copy2(candidate, target)
            return
        except Exception:
            continue


def divine_gr2_to_dae(filepath: str, divine_path: str) -> tuple[str, str]:
    if not divine_path or not os.path.isfile(divine_path):
        return "", "Divine.exe path is not configured or does not exist."

    temp_file = tempfile.NamedTemporaryFile(prefix="fast64_granny_", suffix=".dae", delete=False)
    temp_file.close()
    dae_path = temp_file.name
    game_profiles = ("bg3", "dos2de")
    errors = []
    for profile in game_profiles:
        command = [
            divine_path,
            "--loglevel",
            "warn",
            "-g",
            profile,
            "-s",
            filepath,
            "-d",
            dae_path,
            "-i",
            "gr2",
            "-o",
            "dae",
            "-a",
            "convert-model",
            "-e",
            "flip-uvs",
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode == 0 and os.path.isfile(dae_path) and os.path.getsize(dae_path) > 0:
            return dae_path, ""
        details = (result.stderr or result.stdout or "").strip()
        if len(details) > 300:
            details = details[:300] + "..."
        errors.append(f"{profile}: rc={result.returncode} {details}")
    return "", " | ".join(errors) if errors else "GR2->DAE conversion failed."


def import_dae_with_best_operator(filepath: str) -> tuple[bool, str]:
    ensure_dae_via_obj_importer()
    for operator_path in ("import_scene.dae_via_obj", "wm.collada_import"):
        ok, message = call_operator(operator_path, filepath)
        if ok:
            return True, ""
        if message != "operator not found.":
            return False, message
    return False, "No DAE importer operator was found."


def try_divine_dae_fallback(filepath: str, dll_path: str, divine_path: str) -> tuple[bool, str]:
    divine_path = ensure_existing_or_empty(divine_path) or default_divine_path()
    if not divine_path:
        return False, "Divine.exe not found for GR2->DAE fallback."

    ensure_granny_dll_for_divine(divine_path, dll_path)
    dae_path, conversion_error = divine_gr2_to_dae(filepath, divine_path)
    if not dae_path:
        return False, f"GR2->DAE conversion failed. {conversion_error}"

    imported_ok, import_error = import_dae_with_best_operator(dae_path)
    if imported_ok:
        return True, ""
    return False, f"DAE import failed. {import_error}"


@contextlib.contextmanager
def granny_environment(dll_path: str, include_dir: str, resource_root: str):
    old_values = {}
    updates = {}

    dll_dir = os.path.dirname(dll_path) if dll_path else ""
    if dll_dir and os.path.isdir(dll_dir):
        updates["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
        updates["GRANNY2_DIR"] = dll_dir
        updates["GRANNY2_DLL"] = dll_path

    if include_dir and os.path.isdir(include_dir):
        updates["GRANNY2_INCLUDE"] = include_dir
    if resource_root and os.path.isdir(resource_root):
        updates["GRANNY2_RESOURCE_ROOT"] = resource_root

    for key, value in updates.items():
        old_values[key] = os.environ.get(key)
        os.environ[key] = value

    dll_handle = None
    try:
        if dll_path and os.path.isfile(dll_path):
            try:
                dll_handle = ctypes.WinDLL(dll_path)
            except OSError:
                dll_handle = None
        yield
    finally:
        dll_handle = None
        for key, old_value in old_values.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def select_objects(context: Context, objects: list[bpy.types.Object]):
    deselectAllObjects()
    for obj in objects:
        obj.select_set(True)
    if objects:
        context.view_layer.objects.active = objects[0]


class Fast64ImportGranny2(OperatorBase, ImportHelper):
    bl_idname = "fast64.import_granny2"
    bl_label = "Import Granny2 (.gr2)"
    bl_description = "Import Granny2 files and optionally convert imported materials to F3D"
    bl_options = {"REGISTER", "UNDO"}
    context_mode = "OBJECT"
    icon = "IMPORT"

    filter_glob: StringProperty(default="*.gr2", options={"HIDDEN"})
    auto_convert_materials: BoolProperty(
        name="Auto Convert BSDF Materials To F3D",
        description="Convert imported mesh materials to Fast64 F3D materials after import",
        default=True,
    )
    rename_uv_maps: BoolProperty(
        name="Rename UV Maps To UVMap",
        description="Rename imported UV maps to UVMap before conversion",
        default=True,
    )
    dll_path: StringProperty(
        name="granny2 DLL",
        description="Path to granny2_x64.dll or granny2.dll",
        subtype="FILE_PATH",
        default="",
    )
    include_dir: StringProperty(
        name="Granny Include Dir",
        description="Directory containing granny headers",
        subtype="DIR_PATH",
        default="",
    )
    resource_root: StringProperty(
        name="Granny Resource Root",
        description="Root folder for Granny common package",
        subtype="DIR_PATH",
        default="",
    )
    use_divine_fallback: BoolProperty(
        name="Fallback: GR2->DAE",
        description="If native GR2 import fails, convert GR2 to DAE with Divine and import DAE",
        default=True,
    )
    divine_path: StringProperty(
        name="Divine Path",
        description="Path to Divine.exe used for GR2->DAE fallback",
        subtype="FILE_PATH",
        default="",
    )

    def invoke(self, context: Context, _event):
        scene = context.scene
        self.auto_convert_materials = scene.fast64_granny_auto_convert
        self.rename_uv_maps = scene.fast64_granny_rename_uv_maps
        self.dll_path = scene.fast64_granny_dll_path
        self.include_dir = scene.fast64_granny_include_dir
        self.resource_root = scene.fast64_granny_resource_root
        self.use_divine_fallback = scene.fast64_granny_use_divine_fallback
        self.divine_path = scene.fast64_granny_divine_path
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute_operator(self, context: Context):
        filepath = bpy.path.abspath(self.filepath).strip()
        if not filepath:
            raise PluginError("Please select a .gr2 file.")
        if not os.path.isfile(filepath):
            raise PluginError(f"File does not exist: {filepath}")

        extension = os.path.splitext(filepath)[1].lower()
        if extension != ".gr2":
            raise PluginError("Only .gr2 files are supported by this operator.")

        dll_path = bpy.path.abspath(self.dll_path).strip() if self.dll_path else ""
        include_dir = bpy.path.abspath(self.include_dir).strip() if self.include_dir else ""
        resource_root = bpy.path.abspath(self.resource_root).strip() if self.resource_root else ""
        divine_path = bpy.path.abspath(self.divine_path).strip() if self.divine_path else ""

        if not dll_path:
            fallback_dll = default_granny_dll_path()
            if fallback_dll:
                dll_path = fallback_dll

        dll_path = ensure_existing_or_empty(dll_path)
        include_dir = ensure_existing_or_empty(include_dir)
        resource_root = ensure_existing_or_empty(resource_root)

        before = {obj.name for obj in bpy.data.objects}
        errors = []
        imported_ok = False
        used_divine_fallback = False
        with granny_environment(dll_path, include_dir, resource_root):
            for operator_path in GR2_IMPORT_OPERATOR_CANDIDATES:
                ok, message = call_operator(operator_path, filepath)
                if ok:
                    imported_ok = True
                    break
                errors.append(f"{operator_path}: {message}")

            if not imported_ok and self.use_divine_fallback:
                ok, message = try_divine_dae_fallback(filepath, dll_path, divine_path)
                if ok:
                    imported_ok = True
                    used_divine_fallback = True
                else:
                    errors.append(f"divine_dae_fallback: {message}")

        if not imported_ok:
            details = "\n".join(errors[:8])
            raise PluginError(
                "No working Granny2 import path succeeded in this Blender setup.\n"
                "Install/enable a compatible .gr2 importer add-on or configure Divine fallback.\n"
                f"Configured DLL: {dll_path or '<none>'}\n"
                f"Tried operators:\n{details}"
            )

        imported_objects = [obj for obj in bpy.data.objects if obj.name not in before]
        if not imported_objects and self.use_divine_fallback and not used_divine_fallback:
            ok, message = try_divine_dae_fallback(filepath, dll_path, divine_path)
            if ok:
                used_divine_fallback = True
                imported_objects = [obj for obj in bpy.data.objects if obj.name not in before]
            else:
                errors.append(f"divine_dae_fallback_after_empty_import: {message}")
        if not imported_objects:
            details = "\n".join(errors[-4:]) if errors else "No additional importer details."
            raise PluginError(
                "Import command finished but no new objects were added to the scene.\n"
                f"Details:\n{details}"
            )

        imported_meshes = [obj for obj in imported_objects if obj.type == "MESH"]
        converted_materials = False
        if self.auto_convert_materials and imported_meshes:
            convertAllBSDFtoF3D(imported_meshes, self.rename_uv_maps)
            converted_materials = True

        scene = context.scene
        scene.fast64_granny_auto_convert = self.auto_convert_materials
        scene.fast64_granny_rename_uv_maps = self.rename_uv_maps
        scene.fast64_granny_dll_path = self.dll_path
        scene.fast64_granny_include_dir = self.include_dir
        scene.fast64_granny_resource_root = self.resource_root
        scene.fast64_granny_use_divine_fallback = self.use_divine_fallback
        scene.fast64_granny_divine_path = self.divine_path

        select_objects(context, imported_objects)

        message = f"Imported {len(imported_objects)} object(s)"
        if converted_materials:
            message += " and converted materials to F3D"
        if used_divine_fallback:
            message += " using Divine DAE fallback"
        self.report({"INFO"}, message + ".")


class Fast64Granny2Panel(bpy.types.Panel):
    bl_idname = "FAST64_PT_granny2_tools"
    bl_label = "Granny2"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fast64"

    @classmethod
    def poll(cls, _context: Context):
        return True

    def draw(self, context: Context):
        layout = self.layout.column()
        scene = context.scene

        layout.prop(scene, "fast64_granny_resource_root")
        layout.prop(scene, "fast64_granny_include_dir")
        layout.prop(scene, "fast64_granny_dll_path")
        layout.prop(scene, "fast64_granny_use_divine_fallback")
        if scene.fast64_granny_use_divine_fallback:
            layout.prop(scene, "fast64_granny_divine_path")
        layout.prop(scene, "fast64_granny_auto_convert")
        layout.prop(scene, "fast64_granny_rename_uv_maps")

        op = layout.operator(Fast64ImportGranny2.bl_idname, icon="IMPORT")
        op.auto_convert_materials = scene.fast64_granny_auto_convert
        op.rename_uv_maps = scene.fast64_granny_rename_uv_maps
        op.dll_path = scene.fast64_granny_dll_path
        op.include_dir = scene.fast64_granny_include_dir
        op.resource_root = scene.fast64_granny_resource_root
        op.use_divine_fallback = scene.fast64_granny_use_divine_fallback
        op.divine_path = scene.fast64_granny_divine_path

        info = layout.box().column()
        info.label(text="Uses Granny2 DLL/resource paths before import.")
        info.label(text="Tries GR2 add-ons first; optional Divine DAE fallback.")


classes = (Fast64ImportGranny2, Fast64Granny2Panel)


def granny_register():
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.fast64_granny_auto_convert = BoolProperty(
        name="Auto Convert BSDF Materials",
        description="Automatically convert imported materials to F3D",
        default=True,
    )
    bpy.types.Scene.fast64_granny_rename_uv_maps = BoolProperty(
        name="Rename UV Maps",
        description="Rename imported UV maps to UVMap before conversion",
        default=True,
    )
    bpy.types.Scene.fast64_granny_dll_path = StringProperty(
        name="Granny2 DLL Path",
        subtype="FILE_PATH",
        default=default_granny_dll_path(),
    )
    bpy.types.Scene.fast64_granny_include_dir = StringProperty(
        name="Granny Include Dir",
        subtype="DIR_PATH",
        default=ensure_existing_or_empty(DEFAULT_GRANNY_INCLUDE_DIR),
    )
    bpy.types.Scene.fast64_granny_resource_root = StringProperty(
        name="Granny Resource Root",
        subtype="DIR_PATH",
        default=ensure_existing_or_empty(DEFAULT_GRANNY_RESOURCE_ROOT),
    )
    bpy.types.Scene.fast64_granny_use_divine_fallback = BoolProperty(
        name="Fallback: GR2->DAE",
        description="Use Divine conversion and DAE import fallback if direct GR2 import fails",
        default=True,
    )
    bpy.types.Scene.fast64_granny_divine_path = StringProperty(
        name="Divine Path",
        subtype="FILE_PATH",
        default=default_divine_path(),
    )


def granny_unregister():
    if hasattr(bpy.types.Scene, "fast64_granny_auto_convert"):
        del bpy.types.Scene.fast64_granny_auto_convert
    if hasattr(bpy.types.Scene, "fast64_granny_rename_uv_maps"):
        del bpy.types.Scene.fast64_granny_rename_uv_maps
    if hasattr(bpy.types.Scene, "fast64_granny_dll_path"):
        del bpy.types.Scene.fast64_granny_dll_path
    if hasattr(bpy.types.Scene, "fast64_granny_include_dir"):
        del bpy.types.Scene.fast64_granny_include_dir
    if hasattr(bpy.types.Scene, "fast64_granny_resource_root"):
        del bpy.types.Scene.fast64_granny_resource_root
    if hasattr(bpy.types.Scene, "fast64_granny_use_divine_fallback"):
        del bpy.types.Scene.fast64_granny_use_divine_fallback
    if hasattr(bpy.types.Scene, "fast64_granny_divine_path"):
        del bpy.types.Scene.fast64_granny_divine_path

    for cls in reversed(classes):
        unregister_class(cls)
