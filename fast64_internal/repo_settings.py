import json
import os

from bpy.utils import register_class, unregister_class
from bpy.types import Context, Scene, UILayout
from bpy.props import StringProperty
from bpy.path import abspath

from .utility import filepath_checks, prop_split, filepath_ui_warnings, draw_and_check_tab
from .operators import OperatorBase
from .f3d.f3d_material import ui_geo_mode, ui_upper_mode, ui_lower_mode, ui_other
from .sm64.settings.repo_settings import load_sm64_repo_settings, save_sm64_repo_settings

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .f3d.f3d_material import RDPSettings

CUR_VERSION = 1.0


class SaveRepoSettings(OperatorBase):
    bl_idname = "scene.save_repo_settings"
    bl_label = "Save Repo Settings"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    bl_description = "Save repo settings to a file"
    icon = "FILE_TICK"

    path: StringProperty(name="Settings File Path", subtype="FILE_PATH")

    def execute_operator(self, context: Context):
        save_repo_settings(context.scene, self.path)
        self.report({"INFO"}, f"Saved repo settings to {self.path}")


class LoadRepoSettings(OperatorBase):
    bl_idname = "scene.load_repo_settings"
    bl_label = "Load Repo Settings"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    bl_description = "Load repo settings to a file"
    icon = "IMPORT"

    path: StringProperty(name="Settings File Path", subtype="FILE_PATH")

    def execute_operator(self, context: Context):
        load_repo_settings(context.scene, self.path)
        self.report({"INFO"}, f"Loaded repo settings from {self.path}")


def load_repo_settings(scene: Scene, path: os.PathLike, skip_if_no_auto_load=False):
    filepath_checks(
        abspath(path),
        "Repo settings file path is empty.",
        "Repo settings file path {}does not exist.",
        "Repo settings file path {}is not a file.",
    )

    try:
        with open(abspath(path), "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
    except Exception as exc:
        raise Exception(f"Failed to load repo settings json. ({str(exc)})") from exc

    if skip_if_no_auto_load and not data.get("autoLoad", True):
        return

    # Some future proofing
    if data.get("version", CUR_VERSION) > CUR_VERSION:  # Assuming latest should be fine
        raise ValueError(
            "This repo settings file is using a version higher than this fast64 version supports.",
        )

    fast64_settings = scene.fast64.settings
    fast64_settings.auto_repo_load_settings = data.get("autoLoad", fast64_settings.auto_repo_load_settings)
    fast64_settings.auto_pick_texture_format = data.get(
        "autoPickTextureFormat", fast64_settings.auto_pick_texture_format
    )
    fast64_settings.prefer_rgba_over_ci = data.get("preferRGBAOverCI", fast64_settings.prefer_rgba_over_ci)
    scene.f3d_type = data.get("microcode", scene.f3d_type)
    scene.saveTextures = data.get("saveTextures", scene.saveTextures)
    rdp_defaults: RDPSettings = scene.world.rdp_defaults
    rdp_defaults.from_dict(data.get("rdpDefaults", {}))

    if scene.gameEditorMode == "SM64":
        load_sm64_repo_settings(scene, data.get("sm64", {}))


def save_repo_settings(scene: Scene, path: os.PathLike):
    fast64_settings = scene.fast64.settings
    data = {}

    data["version"] = CUR_VERSION
    data["autoLoad"] = fast64_settings.auto_repo_load_settings
    data["microcode"] = scene.f3d_type
    data["saveTextures"] = scene.saveTextures
    data["autoPickTextureFormat"] = fast64_settings.auto_pick_texture_format
    if fast64_settings.auto_pick_texture_format:
        data["preferRGBAOverCI"] = fast64_settings.prefer_rgba_over_ci
    rdp_defaults: RDPSettings = scene.world.rdp_defaults
    data["rdpDefaults"] = rdp_defaults.to_dict()

    if scene.gameEditorMode == "SM64":
        data["sm64"] = save_sm64_repo_settings(scene)

    with open(abspath(path), "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2)


def draw_repo_settings(layout: UILayout, context: Context):
    col = layout.column()
    scene = context.scene
    fast64_settings = scene.fast64.settings
    if not draw_and_check_tab(col, fast64_settings, "repo_settings_tab", icon="PROPERTIES"):
        return
    prop_split(col, fast64_settings, "repo_settings_path", "Repo Settings Path")
    path = abspath(fast64_settings.repo_settings_path)
    if filepath_ui_warnings(col, path):
        LoadRepoSettings.draw_props(col, path=fast64_settings.repo_settings_path)
    SaveRepoSettings.draw_props(col, path=path)

    col.prop(fast64_settings, "auto_repo_load_settings")
    prop_split(col, scene, "f3d_type", "F3D Microcode")
    col.prop(scene, "saveTextures")
    col.prop(fast64_settings, "auto_pick_texture_format")
    if fast64_settings.auto_pick_texture_format:
        col.prop(fast64_settings, "prefer_rgba_over_ci")
    col.separator()

    world = scene.world
    rdp_defaults = world.rdp_defaults
    col.box().label(text="RDP Default Settings", icon="WORLD")
    col.label(text="If a material setting is a same as a default setting, then it won't be set.")
    ui_geo_mode(rdp_defaults, world, col, True)
    ui_upper_mode(rdp_defaults, world, col, True)
    ui_lower_mode(rdp_defaults, world, col, True)
    ui_other(rdp_defaults, world, col, True)


classes = (SaveRepoSettings, LoadRepoSettings)


def repo_settings_operators_register():
    for cls in classes:
        register_class(cls)


def repo_settings_operators_unregister():
    for cls in classes:
        unregister_class(cls)
