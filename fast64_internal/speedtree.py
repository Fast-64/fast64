import os
import shutil
import subprocess
import tempfile
import zipfile
from collections import deque

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


IMPORT_OPERATOR_CANDIDATES = {
    ".srt": (
        "import.srt_json",
        "import_scene.srt",
        "import_scene.speedtree",
        "import_mesh.speedtree",
        "wm.srt_import",
        "wm.speedtree_import",
    ),
    ".st": (
        "import_scene.st",
        "import_scene.speedtree",
        "import_mesh.speedtree",
        "wm.st_import",
        "wm.speedtree_import",
    ),
    ".spm": (
        "import_scene.spm",
        "import_scene.speedtree",
        "import_mesh.speedtree",
        "wm.spm_import",
        "wm.speedtree_import",
    ),
    ".fbx": ("import_scene.fbx",),
    ".obj": ("wm.obj_import", "import_scene.obj"),
    ".dae": ("wm.collada_import",),
    ".gltf": ("import_scene.gltf",),
    ".glb": ("import_scene.gltf",),
}

SPEEDTREE_EXTENSIONS = {".srt", ".st", ".spm"}
ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar"}
MODEL_PRIORITY = [".srt", ".st", ".spm", ".fbx", ".obj", ".dae", ".gltf", ".glb"]
SAFE_SUPPORT_EXTENSIONS = {
    ".mtl",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".tga",
    ".dds",
    ".bmp",
    ".tif",
    ".tiff",
    ".exr",
    ".hdr",
    ".webp",
    ".ktx",
    ".ktx2",
    ".xml",
    ".json",
    ".txt",
    ".ini",
    ".stf",
}
SAFE_EXTRACT_EXTENSIONS = set(IMPORT_OPERATOR_CANDIDATES.keys()) | SAFE_SUPPORT_EXTENSIONS | ARCHIVE_EXTENSIONS
MAX_NESTED_ARCHIVES = 40
MAX_NESTED_DEPTH = 3
BUILTIN_IMPORT_ADDONS = {
    ".fbx": ("io_scene_fbx",),
    ".obj": ("io_scene_obj",),
    ".dae": ("io_scene_dae",),
    ".gltf": ("io_scene_gltf2",),
    ".glb": ("io_scene_gltf2",),
}
_attempted_builtin_enable_ext = set()
_available_addon_modules_cache = None


def resolve_operator_module(module_name: str):
    module = getattr(bpy.ops, module_name, None)
    # Some Blender builds expose keyword namespaces with a trailing underscore.
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


def detect_srt_version(filepath: str) -> str | None:
    if os.path.splitext(filepath)[1].lower() != ".srt":
        return None
    try:
        with open(filepath, "rb") as handle:
            header = handle.read(16)
    except Exception:
        return None

    if not header.startswith(b"SRT "):
        return None

    try:
        version_raw = header[4:16].split(b"\x00", 1)[0]
        version_text = version_raw.decode("ascii", errors="ignore").strip()
    except Exception:
        return None

    return version_text or None


def find_local_fallback_models(filepath: str) -> list[str]:
    directory = os.path.dirname(filepath)
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    candidates = []

    for ext in MODEL_PRIORITY:
        alt_path = os.path.join(directory, base_name + ext)
        if alt_path == filepath:
            continue
        if os.path.isfile(alt_path):
            candidates.append(alt_path)

    if candidates:
        return candidates

    fallback_files = []
    try:
        for entry in os.scandir(directory):
            if not entry.is_file():
                continue
            if entry.path == filepath:
                continue
            extension = os.path.splitext(entry.name)[1].lower()
            if extension in IMPORT_OPERATOR_CANDIDATES:
                fallback_files.append(entry.path)
    except Exception:
        return []

    return sort_model_files(fallback_files)


def try_enable_builtin_import_addons(extension: str):
    global _available_addon_modules_cache

    if addon_utils is None:
        return

    if extension in _attempted_builtin_enable_ext:
        return
    _attempted_builtin_enable_ext.add(extension)

    if _available_addon_modules_cache is None:
        try:
            _available_addon_modules_cache = {mod.__name__ for mod in addon_utils.modules()}
        except Exception:
            _available_addon_modules_cache = set()

    addon_modules = BUILTIN_IMPORT_ADDONS.get(extension, ())
    for addon_module in addon_modules:
        if _available_addon_modules_cache and addon_module not in _available_addon_modules_cache:
            continue
        try:
            enabled, _loaded = addon_utils.check(addon_module)
        except Exception:
            enabled = False
        if enabled:
            continue
        try:
            bpy.ops.preferences.addon_enable(module=addon_module)
        except Exception:
            continue


def select_objects(context: Context, objects: list[bpy.types.Object]):
    deselectAllObjects()
    for obj in objects:
        obj.select_set(True)
    if objects:
        context.view_layer.objects.active = objects[0]


def find_model_files(root: str) -> list[str]:
    models = []
    for current_root, _dirs, files in os.walk(root):
        for file_name in files:
            extension = os.path.splitext(file_name)[1].lower()
            if extension in IMPORT_OPERATOR_CANDIDATES:
                models.append(os.path.join(current_root, file_name))
    return models


def pick_best_model_file(model_files: list[str]) -> str:
    if not model_files:
        raise PluginError("No supported model files were found in the extracted archive.")

    def score(path: str):
        extension = os.path.splitext(path)[1].lower()
        try:
            ext_rank = MODEL_PRIORITY.index(extension)
        except ValueError:
            ext_rank = 999
        depth = path.count(os.sep)
        return (ext_rank, depth, len(path), path.lower())

    return sorted(model_files, key=score)[0]


def sort_model_files(model_files: list[str]) -> list[str]:
    if not model_files:
        return []

    def score(path: str):
        extension = os.path.splitext(path)[1].lower()
        try:
            ext_rank = MODEL_PRIORITY.index(extension)
        except ValueError:
            ext_rank = 999
        depth = path.count(os.sep)
        return (ext_rank, depth, len(path), path.lower())

    return sorted(model_files, key=score)


def is_supported_extension(path: str, allowed_extensions: set[str]) -> bool:
    return os.path.splitext(path)[1].lower() in allowed_extensions


def extract_zip_filtered(archive_path: str, extract_dir: str) -> int:
    extracted = 0
    extract_root = os.path.abspath(extract_dir)
    with zipfile.ZipFile(archive_path, "r") as zip_file:
        for member in zip_file.infolist():
            if member.is_dir():
                continue

            member_name = member.filename.replace("\\", "/")
            if not is_supported_extension(member_name, SAFE_EXTRACT_EXTENSIONS):
                continue

            normalized = os.path.normpath(member_name)
            if os.path.isabs(normalized) or normalized.startswith(".."):
                continue

            target = os.path.abspath(os.path.join(extract_root, normalized))
            if not target.startswith(extract_root + os.sep) and target != extract_root:
                continue

            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zip_file.open(member, "r") as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted += 1
    return extracted


def seven_zip_include_patterns() -> list[str]:
    patterns = []
    for ext in sorted(SAFE_EXTRACT_EXTENSIONS):
        patterns.append(f"-i!*{ext}")
        upper = ext.upper()
        if upper != ext:
            patterns.append(f"-i!*{upper}")
    return patterns


def extract_7z_filtered(archive_path: str, extract_dir: str) -> int:
    seven_zip = shutil.which("7z")
    if seven_zip is None:
        raise PluginError("7z executable was not found. Install NanaZip/7-Zip command-line support to extract this archive.")

    command = [seven_zip, "x", "-y", "-bb0", "-r", archive_path, f"-o{extract_dir}", *seven_zip_include_patterns()]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        if len(details) > 600:
            details = details[:600] + "..."
        raise PluginError(f"Archive extraction failed ({result.returncode}). {details}")

    try:
        return int(sum(1 for _ in os.scandir(extract_dir)))
    except Exception:
        return 0


def extract_single_archive(archive_path: str, extract_dir: str) -> int:
    extension = os.path.splitext(archive_path)[1].lower()
    if extension == ".zip":
        return extract_zip_filtered(archive_path, extract_dir)
    if extension in {".7z", ".rar"}:
        return extract_7z_filtered(archive_path, extract_dir)
    raise PluginError(f"Unsupported archive extension: {extension}")


def find_nested_archives(root: str, processed_archives: set[str]) -> list[str]:
    nested_archives = []
    for current_root, _dirs, files in os.walk(root):
        for file_name in files:
            full_path = os.path.abspath(os.path.join(current_root, file_name))
            if full_path in processed_archives:
                continue
            if is_supported_extension(full_path, ARCHIVE_EXTENSIONS):
                nested_archives.append(full_path)
    return nested_archives


def extract_archive(archive_path: str) -> tuple[str, str, int]:
    root_extract_dir = tempfile.mkdtemp(prefix="fast64_speedtree_")
    queue = deque([(os.path.abspath(archive_path), root_extract_dir, 0)])
    processed_archives = set()
    queued_archives = {os.path.abspath(archive_path)}
    extracted_archives = 0

    while queue:
        current_archive, current_extract_dir, depth = queue.popleft()
        if current_archive in processed_archives:
            continue
        os.makedirs(current_extract_dir, exist_ok=True)

        extract_single_archive(current_archive, current_extract_dir)
        processed_archives.add(current_archive)
        extracted_archives += 1
        if extracted_archives >= MAX_NESTED_ARCHIVES:
            break
        if depth >= MAX_NESTED_DEPTH:
            continue

        nested_archives = find_nested_archives(current_extract_dir, processed_archives)
        for nested_archive in nested_archives:
            if nested_archive in queued_archives:
                continue
            queued_archives.add(nested_archive)
            nested_target = nested_archive + "_unpacked"
            queue.append((nested_archive, nested_target, depth + 1))

    model_files = find_model_files(root_extract_dir)
    if not model_files:
        raise PluginError(
            "Archive extracted safely but no supported model file was found.\n"
            "Supported model extensions: "
            + ", ".join(sorted(IMPORT_OPERATOR_CANDIDATES.keys()))
        )
    selected_model = pick_best_model_file(model_files)
    return root_extract_dir, selected_model, len(model_files)


class Fast64ImportSpeedTree(OperatorBase, ImportHelper):
    bl_idname = "fast64.import_speedtree"
    bl_label = "Import SpeedTree Asset"
    bl_description = "Import SpeedTree data and optionally convert imported materials to F3D"
    bl_options = {"REGISTER", "UNDO"}
    context_mode = "OBJECT"
    icon = "IMPORT"

    filter_glob: StringProperty(
        default="*.srt;*.st;*.spm;*.fbx;*.obj;*.dae;*.gltf;*.glb;*.zip;*.7z;*.rar",
        options={"HIDDEN"},
    )
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

    def invoke(self, context: Context, _event):
        self.auto_convert_materials = context.scene.fast64_speedtree_auto_convert
        self.rename_uv_maps = context.scene.fast64_speedtree_rename_uv_maps
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute_operator(self, context: Context):
        filepath = bpy.path.abspath(self.filepath).strip()
        if not filepath:
            raise PluginError("Please select a model file.")
        if not os.path.isfile(filepath):
            raise PluginError(f"File does not exist: {filepath}")

        selected_from_archive = False
        archive_extract_dir = ""
        archive_model_count = 0
        model_paths_to_try = []
        extension = os.path.splitext(filepath)[1].lower()
        if extension in ARCHIVE_EXTENSIONS:
            archive_extract_dir, filepath, archive_model_count = extract_archive(filepath)
            selected_from_archive = True
            model_paths_to_try = sort_model_files(find_model_files(archive_extract_dir))
        else:
            model_paths_to_try = [filepath]

        if not model_paths_to_try:
            raise PluginError("No supported model file candidate could be resolved for import.")

        before = {obj.name for obj in bpy.data.objects}
        errors = []
        imported_ok = False
        imported_filepath = ""
        imported_extension = ""

        def try_import_paths(paths: list[str]) -> bool:
            nonlocal imported_ok, imported_filepath, imported_extension, errors
            for model_path in paths:
                extension = os.path.splitext(model_path)[1].lower()
                candidates = IMPORT_OPERATOR_CANDIDATES.get(extension)
                if not candidates:
                    continue
                try_enable_builtin_import_addons(extension)

                for operator_path in candidates:
                    ok, message = call_operator(operator_path, model_path)
                    if ok:
                        imported_ok = True
                        imported_filepath = model_path
                        imported_extension = extension
                        return True
                    errors.append(f"{os.path.basename(model_path)} -> {operator_path}: {message}")
            return False

        try_import_paths(model_paths_to_try)

        if not imported_ok and not selected_from_archive and extension in SPEEDTREE_EXTENSIONS:
            fallback_paths = find_local_fallback_models(filepath)
            if fallback_paths:
                try_import_paths(fallback_paths)

        if not imported_ok:
            details = "\n".join(errors[:6])
            tried_extensions = {os.path.splitext(path)[1].lower() for path in model_paths_to_try}
            has_runtime_import_error = any(
                ("operator not found." not in error and "module not found." not in error) for error in errors
            )
            if tried_extensions and all(ext in SPEEDTREE_EXTENSIONS for ext in tried_extensions):
                srt_version = detect_srt_version(filepath)
                version_note = f"\nDetected SRT version: {srt_version}." if srt_version else ""
                if has_runtime_import_error:
                    raise PluginError(
                        "A SpeedTree importer add-on was found but failed to import this file.\n"
                        "The file may use an unsupported SpeedTree version for the installed importer.\n"
                        "Try a compatible importer or export the model as FBX/OBJ/glTF and import that.\n"
                        f"{version_note}"
                        f"Tried operators:\n{details}"
                    )
                raise PluginError(
                    "No SpeedTree importer operator was found for this Blender setup.\n"
                    "Enable/install a SpeedTree importer add-on, or export the model as FBX/OBJ/glTF and import that.\n"
                    f"{version_note}"
                    f"Tried operators:\n{details}"
                )
            if selected_from_archive:
                raise PluginError(
                    "Import failed for all model candidates extracted from archive.\n"
                    f"Candidates: {len(model_paths_to_try)}\n"
                    f"Tried operators:\n{details}"
                )
            raise PluginError(f"Import failed.\nTried operators:\n{details}")

        imported_objects = [obj for obj in bpy.data.objects if obj.name not in before]
        if not imported_objects:
            raise PluginError("Import succeeded but no new objects were added to the scene.")

        imported_meshes = [obj for obj in imported_objects if obj.type == "MESH"]
        converted_materials = False
        if self.auto_convert_materials and imported_meshes:
            convertAllBSDFtoF3D(imported_meshes, self.rename_uv_maps)
            converted_materials = True

        context.scene.fast64_speedtree_auto_convert = self.auto_convert_materials
        context.scene.fast64_speedtree_rename_uv_maps = self.rename_uv_maps
        select_objects(context, imported_objects)

        message = f"Imported {len(imported_objects)} object(s)"
        if converted_materials:
            message += " and converted materials to F3D"
        if selected_from_archive:
            imported_file = os.path.basename(imported_filepath) if imported_filepath else os.path.basename(filepath)
            message += (
                f". Extracted archive to: {archive_extract_dir} "
                f"(found {archive_model_count} model file(s), imported {imported_file})"
            )
        self.report({"INFO"}, message + ".")


class Fast64SpeedTreePanel(bpy.types.Panel):
    bl_idname = "FAST64_PT_speedtree_tools"
    bl_label = "SpeedTree"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fast64"

    @classmethod
    def poll(cls, _context: Context):
        return True

    def draw(self, context: Context):
        layout = self.layout.column()
        scene = context.scene
        layout.prop(scene, "fast64_speedtree_auto_convert")
        layout.prop(scene, "fast64_speedtree_rename_uv_maps")

        op = layout.operator(Fast64ImportSpeedTree.bl_idname, icon="IMPORT")
        op.auto_convert_materials = scene.fast64_speedtree_auto_convert
        op.rename_uv_maps = scene.fast64_speedtree_rename_uv_maps

        info = layout.box().column()
        info.label(text="Formats: .srt/.st/.spm, .fbx, .obj, .dae, .gltf/.glb")
        info.label(text="Archives: .zip/.7z/.rar (auto extract + auto pick model)")
        info.label(text="SRT/ST/SPM import requires a SpeedTree add-on.")


classes = (Fast64ImportSpeedTree, Fast64SpeedTreePanel)


def speedtree_register():
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.fast64_speedtree_auto_convert = BoolProperty(
        name="Auto Convert BSDF Materials",
        description="Automatically convert imported materials to F3D",
        default=True,
    )
    bpy.types.Scene.fast64_speedtree_rename_uv_maps = BoolProperty(
        name="Rename UV Maps",
        description="Rename imported UV maps to UVMap before conversion",
        default=True,
    )


def speedtree_unregister():
    if hasattr(bpy.types.Scene, "fast64_speedtree_auto_convert"):
        del bpy.types.Scene.fast64_speedtree_auto_convert
    if hasattr(bpy.types.Scene, "fast64_speedtree_rename_uv_maps"):
        del bpy.types.Scene.fast64_speedtree_rename_uv_maps

    for cls in reversed(classes):
        unregister_class(cls)
