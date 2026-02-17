import json
import os

from bpy.utils import register_class, unregister_class
from bpy.types import Context, Scene, UILayout
from bpy.props import StringProperty
from bpy.path import abspath

from .utility import (
    filepath_checks,
    prop_split,
    filepath_ui_warnings,
    draw_and_check_tab,
    set_prop_if_in_data,
    multilineLabel,
    as_posix,
)
from .operators import OperatorBase
from .f3d.f3d_material import draw_rdp_world_defaults
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
    game: StringProperty(name="Game", default="")

    def execute_operator(self, context: Context):
        save_repo_settings(context.scene, self.path, self.game)
        self.report({"INFO"}, f"Saved repo settings to {self.path}")


class LoadRepoSettings(OperatorBase):
    bl_idname = "scene.load_repo_settings"
    bl_label = "Load Repo Settings"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    bl_description = "Load repo settings to a file"
    icon = "IMPORT"

    path: StringProperty(name="Settings File Path", subtype="FILE_PATH")
    game: StringProperty(name="Game", default="")

    def execute_operator(self, context: Context):
        load_repo_settings(context.scene, self.path, self.game)
        self.report({"INFO"}, f"Loaded repo settings from {self.path}")


def load_repo_settings(scene: Scene, path: os.PathLike, skip_if_no_auto_load=False, game: str = ""):
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
    fast64_settings.from_repo_settings(data)
    set_prop_if_in_data(scene, "f3d_type", data, "microcode")
    set_prop_if_in_data(scene, "saveTextures", data, "saveTextures")
    set_prop_if_in_data(scene, "exportInlineF3D", data, "bleedAndInline")
    set_prop_if_in_data(scene, "ignoreTextureRestrictions", data, "ignoreTextureRestrictions")
    set_prop_if_in_data(scene, "packed_normals_algorithm", data, "packedNormalsAlgorithm")

    rdp_defaults: RDPSettings = scene.world.rdp_defaults
    rdp_defaults.from_dict(data.get("rdpDefaults", {}))

    if game == "SM64":
        load_sm64_repo_settings(scene, data.get("sm64", {}))
    scene.fast64.settings.glTF.from_dict(data.get("glTF", {}))


def save_repo_settings(scene: Scene, path: os.PathLike, game: str = ""):
    fast64_settings = scene.fast64.settings
    data = {}

    data["version"] = CUR_VERSION
    data.update(fast64_settings.to_repo_settings())
    data["microcode"] = scene.f3d_type
    if scene.f3d_type in {"F3DEX3", "T3D"}:
        data["packedNormalsAlgorithm"] = scene.packed_normals_algorithm
    data["bleedAndInline"] = scene.exportInlineF3D
    data["saveTextures"] = scene.saveTextures
    data["ignoreTextureRestrictions"] = scene.ignoreTextureRestrictions
    rdp_defaults: RDPSettings = scene.world.rdp_defaults
    data["rdpDefaults"] = rdp_defaults.to_dict()

    if game == "SM64":
        data["sm64"] = save_sm64_repo_settings(scene)
    data["glTF"] = scene.fast64.settings.glTF.to_dict()

    with open(abspath(path), "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent="\t")


def draw_repo_settings(
    layout: UILayout, context: Context, game: str = "", path: os.PathLike | None = None, draw_tab=True
):
    col = layout.column()
    scene = context.scene
    fast64_settings = scene.fast64.settings
    if draw_tab:
        if not draw_and_check_tab(col, fast64_settings, "repo_settings_tab", icon="PROPERTIES"):
            return
    multilineLabel(
        col,
        text="IMPORTANT: You may edit your json file\ndirectly to take off properties you don´t want\nto set on load.",
        icon="INFO",
    )
    if path is None:
        prop_split(col, fast64_settings, "repo_settings_path", "Repo Settings Path")
        path = abspath(fast64_settings.repo_settings_path)
    if filepath_ui_warnings(col, path):
        LoadRepoSettings.draw_props(col, path=as_posix(path), game=game)
    SaveRepoSettings.draw_props(col, path=as_posix(path), game=game)

    col.prop(fast64_settings, "auto_repo_load_settings")


classes = (SaveRepoSettings, LoadRepoSettings)


def repo_settings_operators_register():
    for cls in classes:
        register_class(cls)


def repo_settings_operators_unregister():
    for cls in classes:
        unregister_class(cls)
