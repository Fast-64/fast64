import json
from typing import Any
from bpy.utils import register_class, unregister_class
from bpy.types import Context, Scene
from bpy.props import StringProperty
from bpy.path import abspath

from .utility import filepath_checks
from .operators import OperatorBase
from .sm64.settings.repo_settings import load_sm64_repo_settings, save_sm64_repo_settings


cur_repo_settings_version = 1.0


primitive_rdp_properties = [
    "g_zbuffer",
    "g_shade",
    "g_cull_front",
    "g_cull_back",
    "g_attroffset_st_enable",
    "g_attroffset_z_enable",
    "g_packed_normals",
    "g_lighttoalpha",
    "g_ambocclusion",
    "g_fog",
    "g_lighting",
    "g_tex_gen",
    "g_tex_gen_linear",
    "g_lod",
    "g_shade_smooth",
    "g_clipping",
    "g_mdsft_alpha_dither",
    "g_mdsft_rgb_dither",
    "g_mdsft_combkey",
    "g_mdsft_textconv",
    "g_mdsft_text_filt",
    "g_mdsft_textlod",
    "g_mdsft_textdetail",
    "g_mdsft_textpersp",
    "g_mdsft_cycletype",
    "g_mdsft_color_dither",
    "g_mdsft_pipeline",
    "g_mdsft_alpha_compare",
    "g_mdsft_zsrcsel",
    "clip_ratio",
    "set_rendermode",
]

rm_rdp_properties = [
    "aa_en",
    "z_cmp",
    "z_upd",
    "im_rd",
    "clr_on_cvg",
    "cvg_dst",
    "zmode",
    "cvg_x_alpha",
    "alpha_cvg_sel",
    "force_bl",
    "blend_p1",
    "blend_p2",
    "blend_m1",
    "blend_m2",
    "blend_a1",
    "blend_a2",
    "blend_b1",
    "blend_b2",
]


class SM64_SaveRepoSettings(OperatorBase):
    bl_idname = "scene.sm64_save_repo_settings"
    bl_label = "Save Repo Settings"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    bl_description = "Save repo settings to a file"

    path: StringProperty(name="Settings File Path", subtype="FILE_PATH")

    def execute_operator(self, context: Context):
        save_repo_settings(context.scene, self.path)
        self.report({"INFO"}, "Saved repo settings")


class SM64_LoadRepoSettings(OperatorBase):
    bl_idname = "scene.sm64_load_repo_settings"
    bl_label = "Load Repo Settings"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    bl_description = "Load repo settings to a file"

    path: StringProperty(name="Settings File Path", subtype="FILE_PATH")

    def execute_operator(self, context: Context):
        load_repo_settings(context.scene, self.path)
        self.report({"INFO"}, "Loaded repo settings")


def load_repo_settings(scene: Scene, path: str, skip_if_no_auto_load: bool = False):
    filepath_checks(
        abspath(path),
        empty_error="Repo settings file path is empty.",
        doesnt_exist_error="Repo settings file path does not exist.",
        not_a_file_error="Repo settings file path is not a file.",
    )

    try:
        with open(abspath(path), "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
    except Exception as exc:
        raise Exception(f"Failed to load repo settings json. ({str(exc)})")

    if skip_if_no_auto_load and not data.get("auto_load_settings", True):
        return

    # Some future proofing
    if data.get("version", cur_repo_settings_version) > cur_repo_settings_version:
        raise ValueError(
            "This repo settings file is using a version higher than this fast64 version supports.",
        )
    scene.fast64.settings.auto_repo_load_settings = data.get(
        "auto_load_settings", scene.fast64.settings.auto_repo_load_settings
    )
    scene.f3d_type = data.get("microcode", scene.f3d_type)
    scene.saveTextures = data.get("save_textures", scene.saveTextures)

    world = scene.world
    rdp_defaults = world.rdp_defaults

    rdp_defaults_data = data["rdp_defaults"]

    for key in primitive_rdp_properties:
        if key in rdp_defaults_data:
            setattr(rdp_defaults, key, rdp_defaults_data[key])

    if "prim_depth" in rdp_defaults_data:
        prim_depth = rdp_defaults_data["prim_depth"]
        if "z" in prim_depth:
            rdp_defaults.prim_depth.z = prim_depth["z"]
        if "dz" in prim_depth:
            rdp_defaults.prim_depth.dz = prim_depth["dz"]

    if "render_mode" in rdp_defaults_data:
        rdp_rm_defaults_data = rdp_defaults_data["render_mode"]
        if "advanced_render_mode" in rdp_rm_defaults_data:
            rdp_defaults.rendermode_advanced_enabled = rdp_rm_defaults_data["advanced_render_mode"]
        for key in rm_rdp_properties:
            if key in rdp_rm_defaults_data:
                setattr(rdp_defaults, key, rdp_rm_defaults_data[key])
        if "preset_cycle_1" in rdp_rm_defaults_data:
            rdp_defaults.rendermode_preset_cycle_1 = rdp_rm_defaults_data["preset_cycle_1"]
        if "preset_cycle_2" in rdp_rm_defaults_data:
            rdp_defaults.rendermode_preset_cycle_2 = rdp_rm_defaults_data["preset_cycle_2"]

    if scene.gameEditorMode == "SM64":
        load_sm64_repo_settings(scene, data.get("sm64", {}))


def save_repo_settings(scene: Scene, path: str):
    data: dict[str, Any] = {}
    rdp_defaults_data: dict[str, Any] = {}

    data["version"] = cur_repo_settings_version
    data["auto_load_settings"] = scene.fast64.settings.auto_repo_load_settings
    data["microcode"] = scene.f3d_type
    data["save_textures"] = scene.saveTextures
    data["rdp_defaults"] = rdp_defaults_data
    
    if scene.gameEditorMode == "SM64":
        data["sm64"] = save_sm64_repo_settings(scene)

    world = scene.world
    rdp_defaults = world.rdp_defaults

    for key in primitive_rdp_properties:
        rdp_defaults_data[key] = getattr(rdp_defaults, key)

    if rdp_defaults.g_mdsft_zsrcsel == "G_ZS_PRIM":
        rdp_defaults_data["prim_depth"] = {"z": rdp_defaults.prim_depth.z, "dz": rdp_defaults.prim_depth.dz}

    if not rdp_defaults.set_rendermode:
        rdp_rm_defaults_data: dict[str, Any] = {}
        rdp_rm_defaults_data["advanced_render_mode"] = rdp_defaults.rendermode_advanced_enabled
        if not rdp_defaults.rendermode_advanced_enabled:
            for key in rm_rdp_properties:
                rdp_rm_defaults_data[key] = getattr(rdp_defaults, key)
        else:
            rdp_rm_defaults_data["preset_cycle_1"] = rdp_defaults.rendermode_preset_cycle_1
            rdp_rm_defaults_data["preset_cycle_2"] = rdp_defaults.rendermode_preset_cycle_2

        rdp_defaults_data["render_mode"] = rdp_rm_defaults_data

    with open(abspath(path), "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2)


classes = (
    SM64_SaveRepoSettings,
    SM64_LoadRepoSettings,
)


def repo_settings_operators_register():
    for cls in classes:
        register_class(cls)


def repo_settings_operators_unregister():
    for cls in classes:
        unregister_class(cls)
