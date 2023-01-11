import logging
import bpy, math, os
from bpy.types import Operator, Menu
from bl_operators.presets import AddPresetBase
from bpy.utils import register_class, unregister_class
from mathutils import Color

from .f3d_enums import *
from .f3d_gbi import get_F3D_GBI, GBL_c1, GBL_c2, enumTexScroll
from .f3d_material_presets import *
from ..utility import *
from ..render_settings import Fast64RenderSettings_Properties, update_scene_props_from_render_settings
from .f3d_material_helpers import F3DMaterial_UpdateLock
from bpy.app.handlers import persistent
from typing import Generator, Optional, Tuple, Any

F3DMaterialHash = Any  # giant tuple

logging.basicConfig(format="%(asctime)s: %(message)s", datefmt="%m/%d/%Y %I:%M:%S %p")
logger = logging.getLogger(__name__)

bitSizeDict = {
    "G_IM_SIZ_4b": 4,
    "G_IM_SIZ_8b": 8,
    "G_IM_SIZ_16b": 16,
    "G_IM_SIZ_32b": 32,
}

texBitSizeOf = {
    "I4": "G_IM_SIZ_4b",
    "IA4": "G_IM_SIZ_4b",
    "CI4": "G_IM_SIZ_4b",
    "I8": "G_IM_SIZ_8b",
    "IA8": "G_IM_SIZ_8b",
    "CI8": "G_IM_SIZ_8b",
    "RGBA16": "G_IM_SIZ_16b",
    "IA16": "G_IM_SIZ_16b",
    "YUV16": "G_IM_SIZ_16b",
    "RGBA32": "G_IM_SIZ_32b",
}

texFormatOf = {
    "I4": "G_IM_FMT_I",
    "IA4": "G_IM_FMT_IA",
    "CI4": "G_IM_FMT_CI",
    "I8": "G_IM_FMT_I",
    "IA8": "G_IM_FMT_IA",
    "CI8": "G_IM_FMT_CI",
    "RGBA16": "G_IM_FMT_RGBA",
    "IA16": "G_IM_FMT_IA",
    "YUV16": "G_IM_FMT_YUV",
    "RGBA32": "G_IM_FMT_RGBA",
}


sm64EnumDrawLayers = [
    ("0", "Background (0x00)", "Background"),
    ("1", "Opaque (0x01)", "Opaque"),
    ("2", "Opaque Decal (0x02)", "Opaque Decal"),
    ("3", "Opaque Intersecting (0x03)", "Opaque Intersecting"),
    ("4", "Cutout (0x04)", "Cutout"),
    ("5", "Transparent (0x05)", "Transparent"),
    ("6", "Transparent Decal (0x06)", "Transparent Decal"),
    ("7", "Transparent Intersecting (0x07)", "Transparent Intersecting"),
]

ootEnumDrawLayers = [
    ("Opaque", "Opaque", "Opaque"),
    ("Transparent", "Transparent", "Transparent"),
    ("Overlay", "Overlay", "Overlay"),
]


drawLayerSM64toOOT = {
    "0": "Opaque",
    "1": "Opaque",
    "2": "Opaque",
    "3": "Opaque",
    "4": "Opaque",
    "5": "Transparent",
    "6": "Transparent",
    "7": "Transparent",
}

drawLayerOOTtoSM64 = {
    "Opaque": "1",
    "Transparent": "5",
    "Overlay": "1",
}

drawLayerSM64Alpha = {
    "0": "OPAQUE",
    "1": "OPAQUE",
    "2": "OPAQUE",
    "3": "OPAQUE",
    "4": "CLIP",
    "5": "BLEND",
    "6": "BLEND",
    "7": "BLEND",
}

enumF3DMenu = [
    ("Combiner", "Combiner", "Combiner"),
    ("Sources", "Sources", "Sources"),
    ("Geo", "Geo", "Geo"),
    ("Upper", "Upper", "Upper"),
    ("Lower", "Lower", "Lower"),
]

enumF3DSource = [
    ("None", "None", "None"),
    ("Texture", "Texture", "Texture"),
    ("Tile Size", "Tile Size", "Tile Size"),
    ("Primitive", "Primitive", "Primitive"),
    ("Environment", "Environment", "Environment"),
    ("Shade", "Shade", "Shade"),
    ("Key", "Key", "Key"),
    ("LOD Fraction", "LOD Fraction", "LOD Fraction"),
    ("Convert", "Convert", "Convert"),
]

defaultMaterialPresets = {
    "Shaded Solid": {"SM64": "Shaded Solid", "OOT": "oot_shaded_solid"},
    "Shaded Texture": {"SM64": "Shaded Texture", "OOT": "oot_shaded_texture"},
}


def getDefaultMaterialPreset(category):
    game = bpy.context.scene.gameEditorMode
    if game in defaultMaterialPresets[category]:
        return defaultMaterialPresets[category][game]
    else:
        return "Shaded Solid"


def update_draw_layer(self, context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        drawLayer = material.f3d_mat.draw_layer
        if context.scene.gameEditorMode == "SM64":
            drawLayer.oot = drawLayerSM64toOOT[drawLayer.sm64]
        elif context.scene.gameEditorMode == "OOT":
            if material.f3d_mat.draw_layer.oot == "Opaque":
                if int(material.f3d_mat.draw_layer.sm64) > 4:
                    material.f3d_mat.draw_layer.sm64 = "1"
            elif material.f3d_mat.draw_layer.oot == "Transparent":
                if int(material.f3d_mat.draw_layer.sm64) < 5:
                    material.f3d_mat.draw_layer.sm64 = "5"
        material.f3d_mat.presetName = "Custom"
        update_blend_method(material, context)
        set_output_node_groups(material)


def get_blend_method(material):
    f3dMat = material.f3d_mat
    drawLayer = material.f3d_mat.draw_layer
    blend_method = drawLayerSM64Alpha[drawLayer.sm64]

    is_one_cycle = f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_1CYCLE"

    if f3dMat.rdp_settings.set_rendermode:
        if f3dMat.rdp_settings.rendermode_advanced_enabled:
            if f3dMat.rdp_settings.cvg_x_alpha:
                blend_method = "CLIP"
            elif (
                is_one_cycle
                and f3dMat.rdp_settings.force_bl
                and f3dMat.rdp_settings.blend_p1 == "G_BL_CLR_IN"
                and f3dMat.rdp_settings.blend_a1 == "G_BL_A_IN"
                and f3dMat.rdp_settings.blend_m1 == "G_BL_CLR_MEM"
                and f3dMat.rdp_settings.blend_b1 == "G_BL_1MA"
            ):
                blend_method = "BLEND"
            elif (
                not is_one_cycle
                and f3dMat.rdp_settings.force_bl
                and f3dMat.rdp_settings.blend_p2 == "G_BL_CLR_IN"
                and f3dMat.rdp_settings.blend_a2 == "G_BL_A_IN"
                and f3dMat.rdp_settings.blend_m2 == "G_BL_CLR_MEM"
                and f3dMat.rdp_settings.blend_b2 == "G_BL_1MA"
            ):
                blend_method = "BLEND"
            else:
                blend_method = "OPAQUE"
        else:
            rendermode = f3dMat.rdp_settings.rendermode_preset_cycle_1
            if not is_one_cycle:
                rendermode = f3dMat.rdp_settings.rendermode_preset_cycle_2

            f3d = get_F3D_GBI()
            r_mode = getattr(f3d, rendermode, f3d.G_RM_AA_ZB_OPA_SURF)
            if r_mode & f3d.CVG_X_ALPHA:
                blend_method = "CLIP"
            else:
                cfunc = GBL_c1 if is_one_cycle else GBL_c2
                xlu_comb = r_mode & cfunc(f3d.G_BL_CLR_IN, f3d.G_BL_A_IN, f3d.G_BL_CLR_MEM, f3d.G_BL_1MA)
                if xlu_comb and r_mode & f3d.FORCE_BL:
                    blend_method = "BLEND"
                else:
                    blend_method = "OPAQUE"

    return blend_method


def update_blend_method(material: bpy.types.Material, context):
    material.blend_method = get_blend_method(material)
    if material.blend_method == "CLIP":
        material.alpha_threshold = 0.125


class DrawLayerProperty(bpy.types.PropertyGroup):
    sm64: bpy.props.EnumProperty(items=sm64EnumDrawLayers, default="1", update=update_draw_layer)
    oot: bpy.props.EnumProperty(items=ootEnumDrawLayers, default="Opaque", update=update_draw_layer)

    def key(self):
        return (self.sm64, self.oot)


def getTmemWordUsage(texFormat, width, height):
    texelsPerLine = 64 / bitSizeDict[texBitSizeOf[texFormat]]
    return math.ceil(width / texelsPerLine) * height


def getTmemMax(texFormat):
    return 4096 if texFormat[:2] != "CI" else 2048


def F3DOrganizeLights(self, context):
    # Flag to prevent infinite recursion on update callback
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return
        lightList = []
        if self.f3d_light1 is not None:
            lightList.append(self.f3d_light1)
        if self.f3d_light2 is not None:
            lightList.append(self.f3d_light2)
        if self.f3d_light3 is not None:
            lightList.append(self.f3d_light3)
        if self.f3d_light4 is not None:
            lightList.append(self.f3d_light4)
        if self.f3d_light5 is not None:
            lightList.append(self.f3d_light5)
        if self.f3d_light5 is not None:
            lightList.append(self.f3d_light6)
        if self.f3d_light6 is not None:
            lightList.append(self.f3d_light7)

        self.f3d_light1 = lightList[0] if len(lightList) > 0 else None
        self.f3d_light2 = lightList[1] if len(lightList) > 1 else None
        self.f3d_light3 = lightList[2] if len(lightList) > 2 else None
        self.f3d_light4 = lightList[3] if len(lightList) > 3 else None
        self.f3d_light5 = lightList[4] if len(lightList) > 4 else None
        self.f3d_light6 = lightList[5] if len(lightList) > 5 else None
        self.f3d_light7 = lightList[6] if len(lightList) > 6 else None


def combiner_uses(material, checkList, is2Cycle):
    display = False
    for value in checkList:
        if value[:5] == "TEXEL":
            value1 = value
            value2 = value.replace("0", "1") if "0" in value else value.replace("1", "0")
        else:
            value1 = value
            value2 = value

        display |= material.combiner1.A == value1
        if is2Cycle:
            display |= material.combiner2.A == value2

        display |= material.combiner1.B == value1
        if is2Cycle:
            display |= material.combiner2.B == value2

        display |= material.combiner1.C == value1
        if is2Cycle:
            display |= material.combiner2.C == value2

        display |= material.combiner1.D == value1
        if is2Cycle:
            display |= material.combiner2.D == value2

        display |= material.combiner1.A_alpha == value1
        if is2Cycle:
            display |= material.combiner2.A_alpha == value2

        display |= material.combiner1.B_alpha == value1
        if is2Cycle:
            display |= material.combiner2.B_alpha == value2

        display |= material.combiner1.C_alpha == value1
        if is2Cycle:
            display |= material.combiner2.C_alpha == value2

        display |= material.combiner1.D_alpha == value1
        if is2Cycle:
            display |= material.combiner2.D_alpha == value2

    return display


def combiner_uses_alpha(material, checkList, is2Cycle):
    display = False
    for value in checkList:
        if value[:5] == "TEXEL":
            value1 = value
            value2 = value.replace("0", "1") if "0" in value else value.replace("1", "0")
        else:
            value1 = value
            value2 = value

        display |= material.combiner1.A_alpha == value1
        if is2Cycle:
            display |= material.combiner2.A_alpha == value2

        display |= material.combiner1.B_alpha == value1
        if is2Cycle:
            display |= material.combiner2.B_alpha == value2

        display |= material.combiner1.C_alpha == value1
        if is2Cycle:
            display |= material.combiner2.C_alpha == value2

        display |= material.combiner1.D_alpha == value1
        if is2Cycle:
            display |= material.combiner2.D_alpha == value2

    return display


CombinerUses = dict[str, bool]


def combiner_uses_tex0(f3d_mat: "F3DMaterialProperty"):
    return combiner_uses(f3d_mat, ["TEXEL0", "TEXEL0_ALPHA"], f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE")


def combiner_uses_tex1(f3d_mat: "F3DMaterialProperty"):
    return combiner_uses(f3d_mat, ["TEXEL1", "TEXEL1_ALPHA"], f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE")


def all_combiner_uses(f3d_mat: "F3DMaterialProperty") -> CombinerUses:
    use_tex0 = combiner_uses_tex0(f3d_mat)
    use_tex1 = combiner_uses_tex1(f3d_mat)

    useDict = {
        "Texture": use_tex0 or use_tex1,
        "Texture 0": use_tex0,
        "Texture 1": use_tex1,
        "Primitive": combiner_uses(
            f3d_mat,
            ["PRIMITIVE", "PRIMITIVE_ALPHA", "PRIM_LOD_FRAC"],
            f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE",
        ),
        "Environment": combiner_uses(
            f3d_mat, ["ENVIRONMENT", "ENV_ALPHA"], f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"
        ),
        "Shade": combiner_uses(
            f3d_mat, ["SHADE", "SHADE_ALPHA"], f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"
        ),
        "Shade Alpha": combiner_uses_alpha(
            f3d_mat, ["SHADE"], f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"
        ),
        "Key": combiner_uses(f3d_mat, ["CENTER", "SCALE"], f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"),
        "LOD Fraction": combiner_uses(
            f3d_mat, ["LOD_FRACTION"], f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"
        ),
        "Convert": combiner_uses(f3d_mat, ["K4", "K5"], f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"),
    }
    return useDict


def ui_geo_mode(settings, dataHolder, layout, useDropdown):
    inputGroup = layout.column()
    if useDropdown:
        inputGroup.prop(
            dataHolder,
            "menu_geo",
            text="Geometry Mode Settings",
            icon="TRIA_DOWN" if dataHolder.menu_geo else "TRIA_RIGHT",
        )
    if not useDropdown or dataHolder.menu_geo:
        inputGroup.prop(settings, "g_zbuffer", text="Z Buffer")
        inputGroup.prop(settings, "g_shade", text="Shading")
        inputGroup.prop(settings, "g_cull_front", text="Cull Front")
        inputGroup.prop(settings, "g_cull_back", text="Cull Back")
        inputGroup.prop(settings, "g_fog", text="Fog")
        inputGroup.prop(settings, "g_lighting", text="Lighting")
        inputGroup.prop(settings, "g_tex_gen", text="Texture UV Generate")
        inputGroup.prop(settings, "g_tex_gen_linear", text="Texture UV Generate Linear")
        inputGroup.prop(settings, "g_shade_smooth", text="Smooth Shading")
        if bpy.context.scene.f3d_type == "F3DEX_GBI_2" or bpy.context.scene.f3d_type == "F3DEX_GBI":
            inputGroup.prop(settings, "g_clipping", text="Clipping")


def ui_upper_mode(settings, dataHolder, layout: bpy.types.UILayout, useDropdown):
    inputGroup: bpy.types.UILayout = layout.column()
    if useDropdown:
        inputGroup.prop(
            dataHolder,
            "menu_upper",
            text="Other Mode Upper Settings",
            icon="TRIA_DOWN" if dataHolder.menu_upper else "TRIA_RIGHT",
        )
    if not useDropdown or dataHolder.menu_upper:
        if not bpy.context.scene.isHWv1:
            prop_split(inputGroup, settings, "g_mdsft_alpha_dither", "Alpha Dither")
            prop_split(inputGroup, settings, "g_mdsft_rgb_dither", "RGB Dither")
        else:
            prop_split(inputGroup, settings, "g_mdsft_color_dither", "Color Dither")
        prop_split(inputGroup, settings, "g_mdsft_combkey", "Chroma Key")
        prop_split(inputGroup, settings, "g_mdsft_textconv", "Texture Convert")
        prop_split(inputGroup, settings, "g_mdsft_text_filt", "Texture Filter")
        prop_split(inputGroup, settings, "g_mdsft_textlod", "Texture LOD (Mipmapping)")
        if settings.g_mdsft_textlod == "G_TL_LOD":
            inputGroup.prop(settings, "num_textures_mipmapped", text="Number of Mipmaps")
            if settings.num_textures_mipmapped > 2:
                box = inputGroup.box()
                box.alert = True
                box.label(
                    text="WARNING: Fast64 does not support setting more than two textures.", icon="LIBRARY_DATA_BROKEN"
                )
                box.label(text="Additional texture tiles will need to be set up manually.")
        prop_split(inputGroup, settings, "g_mdsft_textdetail", "Texture Detail")
        prop_split(inputGroup, settings, "g_mdsft_textpersp", "Texture Perspective Correction")
        prop_split(inputGroup, settings, "g_mdsft_cycletype", "Cycle Type")

        prop_split(inputGroup, settings, "g_mdsft_pipeline", "Pipeline Span Buffer Coherency")


def ui_lower_mode(settings, dataHolder, layout: bpy.types.UILayout, useDropdown):
    inputGroup: bpy.types.UILayout = layout.column()
    if useDropdown:
        inputGroup.prop(
            dataHolder,
            "menu_lower",
            text="Other Mode Lower Settings",
            icon="TRIA_DOWN" if dataHolder.menu_lower else "TRIA_RIGHT",
        )
    if not useDropdown or dataHolder.menu_lower:
        prop_split(inputGroup, settings, "g_mdsft_alpha_compare", "Alpha Compare")
        if settings.g_mdsft_alpha_compare == "G_AC_THRESHOLD" and settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
            inputGroup.label(text="Compares blend alpha to *first cycle* combined (CC) alpha.")
        prop_split(inputGroup, settings, "g_mdsft_zsrcsel", "Z Source Selection")
    if settings.g_mdsft_zsrcsel == "G_ZS_PRIM":
        prim_box = inputGroup.box()
        prop_split(prim_box, settings.prim_depth, "z", "Prim Depth: Z")
        prop_split(prim_box, settings.prim_depth, "dz", "Prim Depth: Delta Z")
        if settings.prim_depth.dz != 0 and settings.prim_depth.dz & (settings.prim_depth.dz - 1):
            prim_box.label(text="Warning: DZ should ideally be a power of 2 up to 0x4000", icon="TEXTURE_DATA")


def ui_other(settings, dataHolder, layout, useDropdown):
    inputGroup = layout.column()
    if useDropdown:
        inputGroup.prop(
            dataHolder, "menu_other", text="Other Settings", icon="TRIA_DOWN" if dataHolder.menu_other else "TRIA_RIGHT"
        )
    if not useDropdown or dataHolder.menu_other:
        clipRatioGroup = inputGroup.column()
        prop_split(clipRatioGroup, settings, "clip_ratio", "Clip Ratio")

        if isinstance(dataHolder, bpy.types.Material) or isinstance(dataHolder, F3DMaterialProperty):
            blend_color_group = layout.row()
            prop_input_name = blend_color_group.column()
            prop_input = blend_color_group.column()
            prop_input_name.prop(dataHolder, "set_blend", text="Blend Color")
            prop_input.prop(dataHolder, "blend_color", text="")
            prop_input.enabled = dataHolder.set_blend


def tmemUsageUI(layout, textureProp):
    tex = textureProp.tex
    if tex is not None and tex.size[0] > 0 and tex.size[1] > 0:
        tmemUsage = getTmemWordUsage(textureProp.tex_format, tex.size[0], tex.size[1]) * 8
        tmemMax = getTmemMax(textureProp.tex_format)
        layout.label(text="TMEM Usage: " + str(tmemUsage) + " / " + str(tmemMax) + " bytes")
        if tmemUsage > tmemMax:
            tmemSizeWarning = layout.box()
            tmemSizeWarning.label(text="WARNING: Texture size is too large.")
            tmemSizeWarning.label(text="Note that width will be internally padded to 64 bit boundaries.")


# UI Assumptions:
# shading = 1
# lighting = 1
# cycle type = 1 cycle
class F3DPanel(bpy.types.Panel):
    bl_label = "F3D Material"
    bl_idname = "MATERIAL_PT_F3D_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    def ui_prop(self, material, layout, name, setName, setProp, showCheckBox):
        nodes = material.node_tree.nodes
        inputGroup = layout.row()
        prop_input_name = inputGroup.column()
        prop_input = inputGroup.column()
        if showCheckBox:
            prop_input_name.prop(material, setName, text=name)
        else:
            prop_input_name.label(text=name)
        prop_input.prop(nodes[name].outputs[0], "default_value", text="")
        prop_input.enabled = setProp
        return inputGroup

    def ui_prop_non_node(self, material, layout, label, name, setName, setProp):
        inputGroup = layout.row()
        prop_input_name = inputGroup.column()
        prop_input = inputGroup.column()
        prop_input_name.prop(material, setName, text=name)
        prop_input.prop(material, name, text="")
        prop_input.enabled = setProp
        return inputGroup

    def ui_scale(self, material, layout):
        inputGroup = layout.row().split(factor=0.5)
        prop_input = inputGroup.column()
        prop_input.prop(material, "scale_autoprop", text="Texture Auto Scale")
        prop_input_group = inputGroup.row()
        prop_input_group.prop(material, "tex_scale", text="")
        prop_input_group.enabled = not material.scale_autoprop
        return inputGroup

    def ui_prim(self, material, layout, setName, setProp, showCheckBox):
        f3dMat = material.f3d_mat
        inputGroup = layout.row()
        prop_input_name = inputGroup.column()
        prop_input = inputGroup.column()
        if showCheckBox:
            prop_input_name.prop(f3dMat, setName, text="Primitive Color")
        else:
            prop_input_name.label(text="Primitive Color")

        prop_input.prop(f3dMat, "prim_color", text="")
        prop_input.prop(f3dMat, "prim_lod_frac", text="Prim LOD Fraction")
        prop_input.prop(f3dMat, "prim_lod_min", text="Min LOD Ratio")
        prop_input.enabled = setProp
        return inputGroup

    def ui_env(self, material, layout, showCheckBox):
        inputGroup = layout.row()
        prop_input_name = inputGroup.column()
        prop_input = inputGroup.column()

        if showCheckBox:
            prop_input_name.prop(material.f3d_mat, "set_env", text="Environment Color")
        else:
            prop_input_name.label(text="Environment Color")
        prop_input.prop(material.f3d_mat, "env_color", text="")
        setProp = material.f3d_mat.set_env
        prop_input.enabled = setProp
        return inputGroup

    def ui_chroma(self, material, layout, name, setName, setProp, showCheckBox):
        inputGroup = layout.row()
        prop_input_name = inputGroup.column()
        prop_input = inputGroup.column()
        if showCheckBox:
            prop_input_name.prop(material, setName, text="Chroma Key")
        else:
            prop_input_name.label(text="Chroma Key")
        prop_input.prop(material.f3d_mat, "key_center", text="Center")
        prop_input.prop(material, "key_scale", text="Scale")
        prop_input.prop(material, "key_width", text="Width")
        if material.key_width[0] > 1 or material.key_width[1] > 1 or material.key_width[2] > 1:
            layout.box().label(text="NOTE: Keying is disabled for channels with width > 1.")
        prop_input.enabled = setProp
        return inputGroup

    def ui_lights(self, f3d_mat: "F3DMaterialProperty", layout: bpy.types.UILayout, name, showCheckBox):
        inputGroup = layout.row()
        prop_input_left = inputGroup.column()
        prop_input = inputGroup.column()
        if showCheckBox:
            prop_input_left.prop(f3d_mat, "set_lights", text=name)
        else:
            prop_input_left.label(text=name)

        prop_input_left.enabled = f3d_mat.rdp_settings.g_lighting and f3d_mat.rdp_settings.g_shade
        lightSettings: bpy.types.UILayout = prop_input.column()
        if f3d_mat.rdp_settings.g_lighting:
            prop_input_left.separator(factor=0.25)
            light_controls = prop_input_left.box()
            light_controls.enabled = f3d_mat.set_lights

            light_controls.prop(f3d_mat, "use_default_lighting", text="Use Custom Lighting", invert_checkbox=True)

            if f3d_mat.use_default_lighting:
                lightSettings.prop(f3d_mat, "default_light_color", text="Light Color")
                light_controls.prop(f3d_mat, "set_ambient_from_light", text="Automatic Ambient Color")
                ambCol = lightSettings.column()
                ambCol.enabled = not f3d_mat.set_ambient_from_light
                ambCol.prop(f3d_mat, "ambient_light_color", text="Ambient Color")
            else:
                lightSettings.prop(f3d_mat, "ambient_light_color", text="Ambient Color")

                lightSettings.prop_search(f3d_mat, "f3d_light1", bpy.data, "lights", text="")
                if f3d_mat.f3d_light1 is not None:
                    lightSettings.prop_search(f3d_mat, "f3d_light2", bpy.data, "lights", text="")
                if f3d_mat.f3d_light2 is not None:
                    lightSettings.prop_search(f3d_mat, "f3d_light3", bpy.data, "lights", text="")
                if f3d_mat.f3d_light3 is not None:
                    lightSettings.prop_search(f3d_mat, "f3d_light4", bpy.data, "lights", text="")
                if f3d_mat.f3d_light4 is not None:
                    lightSettings.prop_search(f3d_mat, "f3d_light5", bpy.data, "lights", text="")
                if f3d_mat.f3d_light5 is not None:
                    lightSettings.prop_search(f3d_mat, "f3d_light6", bpy.data, "lights", text="")
                if f3d_mat.f3d_light6 is not None:
                    lightSettings.prop_search(f3d_mat, "f3d_light7", bpy.data, "lights", text="")

            prop_input.enabled = f3d_mat.set_lights and f3d_mat.rdp_settings.g_lighting and f3d_mat.rdp_settings.g_shade

        return inputGroup

    def ui_convert(self, material, layout, showCheckBox):
        inputGroup = layout.row()
        prop_input_name = inputGroup.column()
        prop_input = inputGroup.column()
        if showCheckBox:
            prop_input_name.prop(material, "set_k0_5", text="YUV Convert")
        else:
            prop_input_name.label(text="YUV Convert")

        prop_k0 = prop_input.row()
        prop_k0.prop(material, "k0", text="K0")
        prop_k0.label(text=str(int(material.k0 * 255)))

        prop_k1 = prop_input.row()
        prop_k1.prop(material, "k1", text="K1")
        prop_k1.label(text=str(int(material.k1 * 255)))

        prop_k2 = prop_input.row()
        prop_k2.prop(material, "k2", text="K2")
        prop_k2.label(text=str(int(material.k2 * 255)))

        prop_k3 = prop_input.row()
        prop_k3.prop(material, "k3", text="K3")
        prop_k3.label(text=str(int(material.k3 * 255)))

        prop_k4 = prop_input.row()
        prop_k4.prop(material, "k4", text="K4")
        prop_k4.label(text=str(int(material.k4 * 255)))

        prop_k5 = prop_input.row()
        prop_k5.prop(material, "k5", text="K5")
        prop_k5.label(text=str(int(material.k5 * 255)))

        prop_input.enabled = material.set_k0_5
        return inputGroup

    def ui_lower_render_mode(self, material, layout, useDropdown):
        # cycle independent
        inputGroup = layout.column()
        if useDropdown:
            inputGroup.prop(
                material,
                "menu_lower_render",
                text="Render Settings",
                icon="TRIA_DOWN" if material.menu_lower_render else "TRIA_RIGHT",
            )
        if not useDropdown or material.menu_lower_render:
            inputGroup.prop(material.rdp_settings, "set_rendermode", text="Set Render Mode?")

            renderGroup = inputGroup.column()
            renderGroup.prop(material.rdp_settings, "rendermode_advanced_enabled", text="Show Advanced Settings")
            if not material.rdp_settings.rendermode_advanced_enabled:
                prop_split(renderGroup, material.rdp_settings, "rendermode_preset_cycle_1", "Render Mode")
                if material.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
                    prop_split(renderGroup, material.rdp_settings, "rendermode_preset_cycle_2", "Render Mode Cycle 2")
            else:
                prop_split(renderGroup, material.rdp_settings, "aa_en", "Antialiasing")
                prop_split(renderGroup, material.rdp_settings, "z_cmp", "Z Testing")
                prop_split(renderGroup, material.rdp_settings, "z_upd", "Z Writing")
                prop_split(renderGroup, material.rdp_settings, "im_rd", "IM_RD (?)")
                prop_split(renderGroup, material.rdp_settings, "clr_on_cvg", "Color On Coverage")
                prop_split(renderGroup, material.rdp_settings, "cvg_dst", "Coverage Destination")
                prop_split(renderGroup, material.rdp_settings, "zmode", "Z Mode")
                prop_split(renderGroup, material.rdp_settings, "cvg_x_alpha", "Multiply Coverage And Alpha")
                prop_split(renderGroup, material.rdp_settings, "alpha_cvg_sel", "Use Coverage For Alpha")
                prop_split(renderGroup, material.rdp_settings, "force_bl", "Force Blending")

                # cycle dependent - (P * A + M - B) / (A + B)
                combinerBox = renderGroup.box()
                combinerBox.label(text="Blender (Color = (P * A + M * B) / (A + B)")
                combinerCol = combinerBox.row()
                rowColor = combinerCol.column()
                rowAlpha = combinerCol.column()
                rowColor.prop(material.rdp_settings, "blend_p1", text="P")
                rowColor.prop(material.rdp_settings, "blend_m1", text="M")
                rowAlpha.prop(material.rdp_settings, "blend_a1", text="A")
                rowAlpha.prop(material.rdp_settings, "blend_b1", text="B")

                if material.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
                    combinerBox2 = renderGroup.box()
                    combinerBox2.label(text="Blender Cycle 2")
                    combinerCol2 = combinerBox2.row()
                    rowColor2 = combinerCol2.column()
                    rowAlpha2 = combinerCol2.column()
                    rowColor2.prop(material.rdp_settings, "blend_p2", text="P")
                    rowColor2.prop(material.rdp_settings, "blend_m2", text="M")
                    rowAlpha2.prop(material.rdp_settings, "blend_a2", text="A")
                    rowAlpha2.prop(material.rdp_settings, "blend_b2", text="B")

            renderGroup.enabled = material.rdp_settings.set_rendermode

    def ui_uvCheck(self, layout, context):
        if (
            hasattr(context, "object")
            and context.object is not None
            and isinstance(context.object.data, bpy.types.Mesh)
        ):
            uv_layers = context.object.data.uv_layers
            if uv_layers.active is None or uv_layers.active.name != "UVMap":
                uvErrorBox = layout.box()
                uvErrorBox.label(text='Warning: This mesh\'s active UV layer is not named "UVMap".')
                uvErrorBox.label(text="This will cause incorrect UVs to display.")

    def ui_draw_layer(self, material, layout, context):
        if context.scene.gameEditorMode == "SM64":
            prop_split(layout, material.f3d_mat.draw_layer, "sm64", "Draw Layer")
        elif context.scene.gameEditorMode == "OOT":
            prop_split(layout, material.f3d_mat.draw_layer, "oot", "Draw Layer")

    def ui_fog(self, f3dMat, inputCol, showCheckBox):
        if f3dMat.rdp_settings.g_fog:
            inputGroup = inputCol.column()
            if showCheckBox:
                inputGroup.prop(f3dMat, "set_fog", text="Set Fog")
            if f3dMat.set_fog:
                inputGroup.prop(f3dMat, "use_global_fog", text="Use Global Fog (SM64)")
                if f3dMat.use_global_fog:
                    inputGroup.label(text="Only applies to levels (area fog settings).", icon="INFO")
                else:
                    fogColorGroup = inputGroup.row().split(factor=0.5)
                    fogColorGroup.label(text="Fog Color")
                    fogColorGroup.prop(f3dMat, "fog_color", text="")
                    fogPositionGroup = inputGroup.row().split(factor=0.5)
                    fogPositionGroup.label(text="Fog Range")
                    fogPositionGroup.prop(f3dMat, "fog_position", text="")

    def drawVertexColorNotice(self, layout):
        noticeBox = layout.box().column()
        noticeBox.label(text="There must be two vertex color layers.", icon="LINENUMBERS_ON")
        noticeBox.label(text='They should be called "Col" and "Alpha".')

    def drawShadeAlphaNotice(self, layout):
        layout.box().column().label(text='There must be a vertex color layer called "Alpha".', icon="IMAGE_ALPHA")

    def draw_simple(self, f3dMat, material, layout, context):
        self.ui_uvCheck(layout, context)

        inputCol = layout.column()
        useDict = all_combiner_uses(f3dMat)

        if not f3dMat.rdp_settings.g_lighting:
            self.drawVertexColorNotice(layout)
        elif useDict["Shade Alpha"]:
            self.drawShadeAlphaNotice(layout)

        useMultitexture = useDict["Texture 0"] and useDict["Texture 1"] and f3dMat.tex0.tex_set and f3dMat.tex1.tex_set

        canUseLargeTextures = material.mat_ver > 3 and material.f3d_mat.use_large_textures
        if useDict["Texture 0"] and f3dMat.tex0.tex_set:
            ui_image(canUseLargeTextures, inputCol, f3dMat.tex0, "Texture 0", False)

        if useDict["Texture 1"] and f3dMat.tex1.tex_set:
            ui_image(canUseLargeTextures, inputCol, f3dMat.tex1, "Texture 1", False)

        if useMultitexture:
            inputCol.prop(f3dMat, "uv_basis", text="UV Basis")

        if useDict["Texture"]:
            inputCol.prop(f3dMat, "use_large_textures")
            self.ui_scale(f3dMat, inputCol)

        if useDict["Primitive"] and f3dMat.set_prim:
            self.ui_prim(material, inputCol, "set_prim", f3dMat.set_prim, False)

        if useDict["Environment"] and f3dMat.set_env:
            self.ui_env(material, inputCol, False)

        showLightProperty = f3dMat.set_lights and f3dMat.rdp_settings.g_lighting and f3dMat.rdp_settings.g_shade
        if useDict["Shade"] and showLightProperty:
            self.ui_lights(f3dMat, inputCol, "Lighting", False)

        if useDict["Key"] and f3dMat.set_key:
            self.ui_chroma(material, inputCol, "Chroma Key Center", "set_key", f3dMat.set_key, False)

        if useDict["Convert"] and f3dMat.set_k0_5:
            self.ui_convert(f3dMat, inputCol, False)

        if f3dMat.set_fog:
            self.ui_fog(f3dMat, inputCol, False)

    def draw_full(self, f3dMat, material, layout: bpy.types.UILayout, context):

        layout.row().prop(material, "menu_tab", expand=True)
        menuTab = material.menu_tab
        useDict = all_combiner_uses(f3dMat)

        if menuTab == "Combiner":
            self.ui_draw_layer(material, layout, context)

            if not f3dMat.rdp_settings.g_lighting:
                self.drawVertexColorNotice(layout)
            elif useDict["Shade Alpha"]:
                self.drawShadeAlphaNotice(layout)

            combinerBox = layout.box()
            combinerBox.prop(f3dMat, "set_combiner", text="Color Combiner (Color = (A - B) * C + D)")
            combinerCol = combinerBox.row()
            combinerCol.enabled = f3dMat.set_combiner
            rowColor = combinerCol.column()
            rowAlpha = combinerCol.column()

            rowColor.prop(f3dMat.combiner1, "A")
            rowColor.prop(f3dMat.combiner1, "B")
            rowColor.prop(f3dMat.combiner1, "C")
            rowColor.prop(f3dMat.combiner1, "D")
            rowAlpha.prop(f3dMat.combiner1, "A_alpha")
            rowAlpha.prop(f3dMat.combiner1, "B_alpha")
            rowAlpha.prop(f3dMat.combiner1, "C_alpha")
            rowAlpha.prop(f3dMat.combiner1, "D_alpha")
            if (
                f3dMat.rdp_settings.g_mdsft_alpha_compare == "G_AC_THRESHOLD"
                and f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"
            ):
                combinerBox.label(text="First cycle alpha out used for compare threshold.")

            if f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
                combinerBox2 = layout.box()
                combinerBox2.label(text="Color Combiner Cycle 2")
                combinerBox2.enabled = f3dMat.set_combiner
                combinerCol2 = combinerBox2.row()
                rowColor2 = combinerCol2.column()
                rowAlpha2 = combinerCol2.column()

                rowColor2.prop(f3dMat.combiner2, "A")
                rowColor2.prop(f3dMat.combiner2, "B")
                rowColor2.prop(f3dMat.combiner2, "C")
                rowColor2.prop(f3dMat.combiner2, "D")
                rowAlpha2.prop(f3dMat.combiner2, "A_alpha")
                rowAlpha2.prop(f3dMat.combiner2, "B_alpha")
                rowAlpha2.prop(f3dMat.combiner2, "C_alpha")
                rowAlpha2.prop(f3dMat.combiner2, "D_alpha")

                if useDict["Texture 0"]:
                    cc_list = ["A", "B", "C", "D", "A_alpha", "B_alpha", "C_alpha", "D_alpha"]
                    if len([c for c in cc_list if getattr(f3dMat.combiner2, c) == "TEXEL1"]):
                        combinerBox2.label(
                            text="Warning: Using 'Texture 1' in Cycle 2 can cause display issues!",
                            icon="LIBRARY_DATA_BROKEN",
                        )

                combinerBox2.label(text="Note: In second cycle, texture 0 and texture 1 are flipped.")
        if menuTab == "Sources":
            self.ui_uvCheck(layout, context)

            inputCol = layout.column()

            useMultitexture = useDict["Texture 0"] and useDict["Texture 1"]

            canUseLargeTextures = material.mat_ver > 3 and material.f3d_mat.use_large_textures
            if useDict["Texture 0"]:
                ui_image(canUseLargeTextures, inputCol, f3dMat.tex0, "Texture 0", True)

            if useDict["Texture 1"]:
                ui_image(canUseLargeTextures, inputCol, f3dMat.tex1, "Texture 1", True)

            if useMultitexture:
                inputCol.prop(f3dMat, "uv_basis", text="UV Basis")

            if useDict["Texture"]:
                inputCol.prop(f3dMat, "use_large_textures")
                self.ui_scale(f3dMat, inputCol)

            if useDict["Primitive"]:
                self.ui_prim(material, inputCol, "set_prim", f3dMat.set_prim, True)

            if useDict["Environment"]:
                self.ui_env(material, inputCol, True)

            if useDict["Shade"]:
                self.ui_lights(f3dMat, inputCol, "Lighting", True)

            if useDict["Key"]:
                self.ui_chroma(material, inputCol, "Chroma Key Center", "set_key", f3dMat.set_key, True)

            if useDict["Convert"]:
                self.ui_convert(f3dMat, inputCol, True)

            self.ui_fog(f3dMat, inputCol, True)

        if menuTab == "Geo":
            ui_geo_mode(f3dMat.rdp_settings, f3dMat, layout, False)
        if menuTab == "Upper":
            ui_upper_mode(f3dMat.rdp_settings, f3dMat, layout, False)
        if menuTab == "Lower":
            ui_lower_mode(f3dMat.rdp_settings, f3dMat, layout, False)
            self.ui_lower_render_mode(f3dMat, layout, False)
            ui_other(f3dMat.rdp_settings, f3dMat, layout, False)

    # texture convert/LUT controlled by texture settings
    # add node support for geo mode settings
    def draw(self, context):
        layout = self.layout

        layout.operator(CreateFast3DMaterial.bl_idname)
        material = context.material
        if material is None:
            return
        elif not material.use_nodes or not material.is_f3d:
            layout.label(text="This is not a Fast3D material.")
            return

        f3dMat = material.f3d_mat
        layout.prop(context.scene, "f3d_simple", text="Show Simplified UI")
        layout = layout.box()
        titleCol = layout.column()
        titleCol.box().label(text="F3D Material Inspector")

        presetCol = layout.column()
        split = presetCol.split(factor=0.33)
        split.label(text="Preset")
        row = split.row(align=True)
        row.menu(MATERIAL_MT_f3d_presets.__name__, text=f3dMat.presetName)
        row.operator(AddPresetF3D.bl_idname, text="", icon="ZOOM_IN")
        row.operator(AddPresetF3D.bl_idname, text="", icon="ZOOM_OUT").remove_active = True

        if context.scene.f3d_simple and f3dMat.presetName != "Custom":
            self.draw_simple(f3dMat, material, layout, context)
        else:
            presetCol.prop(context.scene, "f3dUserPresetsOnly")
            self.draw_full(f3dMat, material, layout, context)


def ui_tileScroll(tex, name, layout):
    row = layout.row()
    row.label(text=name)
    row.prop(tex.tile_scroll, "s", text="S:")
    row.prop(tex.tile_scroll, "t", text="T:")
    row.prop(tex.tile_scroll, "interval", text="Interval:")


def ui_procAnimVecEnum(material, procAnimVec, layout, name, vecType, useDropdown, useTex0, useTex1):
    layout = layout.box()
    box = layout.column()
    if useDropdown:
        layout.prop(procAnimVec, "menu", text=name, icon="TRIA_DOWN" if procAnimVec.menu else "TRIA_RIGHT")
    else:
        layout.box().label(text=name)

    if not useDropdown or procAnimVec.menu:
        box = layout.column()
        combinedOption = None
        xCombined = procAnimVec.x.animType == "Rotation"
        if xCombined:
            combinedOption = procAnimVec.x.animType
        yCombined = procAnimVec.y.animType == "Rotation"
        if yCombined:
            combinedOption = procAnimVec.y.animType
        if not yCombined:
            ui_procAnimFieldEnum(procAnimVec.x, box, vecType[0], "UV" if xCombined else None)
        if not xCombined:
            ui_procAnimFieldEnum(procAnimVec.y, box, vecType[1], "UV" if yCombined else None)
        if len(vecType) > 2:
            ui_procAnimFieldEnum(procAnimVec.z, box, vecType[2])
        if xCombined or yCombined:
            box.row().prop(procAnimVec, "pivot")
            box.row().prop(procAnimVec, "angularSpeed")
            if combinedOption == "Rotation":
                pass

    if useTex0 or useTex1:
        layout.box().label(text="SM64 SetTileSize Texture Scroll")

        if useTex0:
            ui_tileScroll(material.tex0, "Texture 0 Speed", layout)

        if useTex1:
            ui_tileScroll(material.tex1, "Texture 1 Speed", layout)


def ui_procAnimFieldEnum(procAnimField, layout, name, overrideName):
    box = layout
    box.prop(procAnimField, "animType", text=name if overrideName is None else overrideName)
    if overrideName is None:
        if procAnimField.animType == "Linear":
            split0 = box.row().split(factor=1)
            split0.prop(procAnimField, "speed")
        elif procAnimField.animType == "Sine":
            split1 = box.row().split(factor=0.3333)
            split1.prop(procAnimField, "amplitude")
            split1.prop(procAnimField, "frequency")
            split1.prop(procAnimField, "offset")
        elif procAnimField.animType == "Noise":
            box.row().prop(procAnimField, "noiseAmplitude")


def ui_procAnimField(procAnimField, layout, name):
    box = layout
    box.prop(procAnimField, "animate", text=name)
    if procAnimField.animate:
        if name not in "XYZ":
            split0 = box.row().split(factor=1)
            split0.prop(procAnimField, "speed")
        split1 = box.row().split(factor=0.5)
        split1.prop(procAnimField, "amplitude")
        split1.prop(procAnimField, "frequency")
        layout.row().prop(procAnimField, "spaceFrequency")
        split2 = box.row().split(factor=0.5)
        split2.prop(procAnimField, "offset")
        split2.prop(procAnimField, "noiseAmplitude")


def ui_procAnim(material, layout, useTex0, useTex1, title, useDropdown):
    ui_procAnimVecEnum(material.f3d_mat, material.f3d_mat.UVanim0, layout, title, "UV", useDropdown, useTex0, useTex1)


def update_node_values(self, context, update_preset):
    if hasattr(context.scene, "world") and self == context.scene.world.rdp_defaults:
        pass

    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        update_node_values_of_material(material, context)
        if update_preset:
            material.f3d_mat.presetName = "Custom"


def update_node_values_with_preset(self, context):
    update_node_values(self, context, update_preset=True)


def update_node_values_without_preset(self, context):
    update_node_values(self, context, update_preset=False)


def update_light_properties(self, context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        update_light_colors(material, context)


def getSocketFromCombinerToNodeDictColor(nodes, combinerInput):
    nodeName, socketIndex = combinerToNodeDictColor[combinerInput]
    return nodes[nodeName].outputs[socketIndex] if nodeName is not None else None


def getSocketFromCombinerToNodeDictAlpha(nodes, combinerInput):
    nodeName, socketIndex = combinerToNodeDictAlpha[combinerInput]
    return nodes[nodeName].outputs[socketIndex] if nodeName is not None else None


# Maps the color combiner input name to the corresponding node name and output socket name
color_combiner_inputs = {
    "COMBINED": (None, "Color"),
    "TEXEL0": ("Tex0_I", "Color"),
    "TEXEL1": ("Tex1_I", "Color"),
    "PRIMITIVE": ("CombinerInputs", "Prim Color"),
    "SHADE": ("Shade Color", "Color"),
    "ENVIRONMENT": ("CombinerInputs", "Env Color"),
    "CENTER": ("CombinerInputs", "Chroma Key Center"),
    "SCALE": ("CombinerInputs", "Chroma Key Scale"),
    "COMBINED_ALPHA": (None, "Alpha"),
    "TEXEL0_ALPHA": ("Tex0_I", "Alpha"),
    "TEXEL1_ALPHA": ("Tex1_I", "Alpha"),
    "PRIMITIVE_ALPHA": ("CombinerInputs", "Prim Alpha"),
    "SHADE_ALPHA": ("Shade Color", "Alpha"),
    "ENV_ALPHA": ("CombinerInputs", "Env Alpha"),
    "LOD_FRACTION": ("CombinerInputs", "LOD Fraction"),
    "PRIM_LOD_FRAC": ("CombinerInputs", "Prim LOD Fraction"),
    "NOISE": ("CombinerInputs", "Noise"),
    "K4": ("CombinerInputs", "YUVConvert K4"),
    "K5": ("CombinerInputs", "YUVConvert K5"),
    "1": ("CombinerInputs", "1"),
    "0": (None, 0),
}

# Maps the alpha combiner input name to the corresponding node name and output name
alpha_combiner_inputs = {
    "COMBINED": (None, "Alpha"),
    "TEXEL0": ("Tex0_I", "Alpha"),
    "TEXEL1": ("Tex1_I", "Alpha"),
    "PRIMITIVE": ("CombinerInputs", "Prim Alpha"),
    "SHADE": ("Shade Color", "Alpha"),
    "ENVIRONMENT": ("CombinerInputs", "Env Alpha"),
    "LOD_FRACTION": ("CombinerInputs", "LOD Fraction"),
    "PRIM_LOD_FRAC": ("CombinerInputs", "Prim LOD Fraction"),
    "1": ("CombinerInputs", "1"),
    "0": (None, 0),
}


def remove_first_link_if_exists(material: bpy.types.Material, links: tuple[bpy.types.NodeLink]):
    if len(links) > 0:
        link = links[0]
        material.node_tree.links.remove(link)


def link_if_none_exist(
    material: bpy.types.Material, fromOutput: bpy.types.NodeSocket, toInput: bpy.types.NodeSocket
):  # TODO: (V5) add output/input type annotations
    if len(fromOutput.links) == 0:
        material.node_tree.links.new(fromOutput, toInput)


swaps_tex01 = {
    "TEXEL0": "TEXEL1",
    "TEXEL0_ALPHA": "TEXEL1_ALPHA",
    "TEXEL1": "TEXEL0",
    "TEXEL1_ALPHA": "TEXEL0_ALPHA",
}


def update_node_combiner(material, combinerInputs, cycleIndex):
    nodes = material.node_tree.nodes

    if cycleIndex == 1:
        cycle_node = nodes["Cycle_1"]
    else:
        cycle_node = nodes["Cycle_2"]

    for i in range(8):
        combiner_input = combinerInputs[i]
        if cycleIndex == 2:
            # Swap texel0 for texel1 and vise versa
            combiner_input = swaps_tex01.get(combiner_input, combiner_input)

        if combiner_input == "0":
            for link in cycle_node.inputs[i].links:
                material.node_tree.links.remove(link)

        if i < 4:
            node_name, output_key = color_combiner_inputs[combiner_input]
            if cycleIndex == 2:
                if combiner_input == "COMBINED":
                    node_name = "Combined_C"
                    output_key = 0  # using an index due to it being a reroute node
                elif combiner_input == "COMBINED_ALPHA":
                    node_name = "Combined_A"
                    output_key = 0  # using an index due to it being a reroute node
            if node_name is not None:
                input_node = nodes[node_name]
                input_value = input_node.outputs[output_key]
                material.node_tree.links.new(cycle_node.inputs[i], input_value)
        else:
            node_name, output_key = alpha_combiner_inputs[combiner_input]
            if cycleIndex == 2:
                if combiner_input == "COMBINED":
                    node_name = "Combined_A"
                    output_key = 0  # using an index due to it being a reroute node
            if node_name is not None:
                input_node = nodes[node_name]
                input_value = input_node.outputs[output_key]
                material.node_tree.links.new(cycle_node.inputs[i], input_value)


def check_fog_settings(material: bpy.types.Material):
    f3dMat: "F3DMaterialProperty" = material.f3d_mat
    fog_enabled: bool = f3dMat.rdp_settings.g_fog
    fog_rendermode_enabled: bool = fog_enabled

    is_one_cycle = f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_1CYCLE"

    if is_one_cycle or fog_enabled == False:
        fog_rendermode_enabled = False
    elif f3dMat.rdp_settings.set_rendermode:
        if f3dMat.rdp_settings.rendermode_advanced_enabled:
            if f3dMat.rdp_settings.blend_p1 == "G_BL_CLR_FOG" and f3dMat.rdp_settings.blend_a1 == "G_BL_A_SHADE":
                fog_rendermode_enabled = True
        else:
            f3d = get_F3D_GBI()
            r_mode = getattr(f3d, f3dMat.rdp_settings.rendermode_preset_cycle_1, f3d.G_RM_PASS)

            # Note: GBL_c1 uses (m1a) << 30 | (m1b) << 26 | (m2a) << 22 | (m2b) << 18
            # This checks if m1a is G_BL_CLR_FOG and m1b is G_BL_A_SHADE
            if r_mode & (f3d.G_BL_CLR_FOG << 30) != 0 and r_mode & (f3d.G_BL_A_SHADE << 26):
                fog_rendermode_enabled = True
    else:
        # if NOT setting rendermode, it is more likely that the user is setting rendermodes in code,
        # so to be safe we'll enable fog
        fog_rendermode_enabled = True

    return fog_enabled, fog_rendermode_enabled


def update_fog_nodes(material: bpy.types.Material, context: bpy.types.Context):
    nodes = material.node_tree.nodes
    f3dMat: "F3DMaterialProperty" = material.f3d_mat

    fog_enabled, fog_rendermode_enabled = check_fog_settings(material)

    nodes["Shade Color"].inputs["Fog"].default_value = int(fog_enabled)

    fogBlender: bpy.types.ShaderNodeGroup = nodes["FogBlender"]
    if fog_rendermode_enabled and fog_enabled:
        fogBlender.node_tree = bpy.data.node_groups["FogBlender_On"]
    else:
        fogBlender.node_tree = bpy.data.node_groups["FogBlender_Off"]

    if fog_enabled:
        inherit_fog = f3dMat.use_global_fog or not f3dMat.set_fog
        if inherit_fog:
            link_if_none_exist(material, nodes["SceneProperties"].outputs["FogColor"], nodes["FogColor"].inputs[0])
            link_if_none_exist(material, nodes["GlobalFogColor"].outputs[0], fogBlender.inputs["Fog Color"])
            link_if_none_exist(
                material, nodes["SceneProperties"].outputs["FogNear"], nodes["CalcFog"].inputs["FogNear"]
            )
            link_if_none_exist(material, nodes["SceneProperties"].outputs["FogFar"], nodes["CalcFog"].inputs["FogFar"])
        else:
            remove_first_link_if_exists(material, nodes["FogBlender"].inputs["Fog Color"].links)
            remove_first_link_if_exists(material, nodes["CalcFog"].inputs["FogNear"].links)
            remove_first_link_if_exists(material, nodes["CalcFog"].inputs["FogFar"].links)

        fogBlender.inputs["Fog Color"].default_value = f3dMat.fog_color
        nodes["CalcFog"].inputs["FogNear"].default_value = f3dMat.fog_position[0]
        nodes["CalcFog"].inputs["FogFar"].default_value = f3dMat.fog_position[1]


def update_noise_nodes(material: bpy.types.Material):
    f3dMat: "F3DMaterialProperty" = material.f3d_mat
    uses_noise = f3dMat.combiner1.A == "NOISE" or f3dMat.combiner2.A == "NOISE"
    noise_group = bpy.data.node_groups["F3DNoise_Animated" if uses_noise else "F3DNoise_NonAnimated"]

    nodes = material.node_tree.nodes
    if nodes["F3DNoiseFactor"].node_tree is not noise_group:
        nodes["F3DNoiseFactor"].node_tree = noise_group


def update_combiner_connections(
    material: bpy.types.Material, context: bpy.types.Context, combiner: (int | None) = None
):
    f3dMat: "F3DMaterialProperty" = material.f3d_mat

    update_noise_nodes(material)

    # Combiner can be specified for performance reasons
    if not combiner or combiner == 1:
        combinerInputs1 = [
            f3dMat.combiner1.A,
            f3dMat.combiner1.B,
            f3dMat.combiner1.C,
            f3dMat.combiner1.D,
            f3dMat.combiner1.A_alpha,
            f3dMat.combiner1.B_alpha,
            f3dMat.combiner1.C_alpha,
            f3dMat.combiner1.D_alpha,
        ]
        update_node_combiner(material, combinerInputs1, 1)

    if not combiner or combiner == 2:
        combinerInputs2 = [
            f3dMat.combiner2.A,
            f3dMat.combiner2.B,
            f3dMat.combiner2.C,
            f3dMat.combiner2.D,
            f3dMat.combiner2.A_alpha,
            f3dMat.combiner2.B_alpha,
            f3dMat.combiner2.C_alpha,
            f3dMat.combiner2.D_alpha,
        ]
        update_node_combiner(material, combinerInputs2, 2)


def set_output_node_groups(material: bpy.types.Material):
    nodes = material.node_tree.nodes
    f3dMat: "F3DMaterialProperty" = material.f3d_mat
    is_one_cycle = f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_1CYCLE"

    output_node = nodes["OUTPUT"]
    if is_one_cycle:
        if material.blend_method == "OPAQUE":
            output_node.node_tree = bpy.data.node_groups["OUTPUT_1CYCLE_OPA"]
        else:
            output_node.node_tree = bpy.data.node_groups["OUTPUT_1CYCLE_XLU"]
    else:
        if material.blend_method == "OPAQUE":
            output_node.node_tree = bpy.data.node_groups["OUTPUT_2CYCLE_OPA"]
        else:
            output_node.node_tree = bpy.data.node_groups["OUTPUT_2CYCLE_XLU"]


def update_light_colors(material, context):
    f3dMat: "F3DMaterialProperty" = material.f3d_mat
    nodes = material.node_tree.nodes

    if f3dMat.use_default_lighting and f3dMat.set_ambient_from_light:
        amb = Color(f3dMat.default_light_color[:3])
        # dividing by 4.672 approximates to half of the light color's value after gamma correction is performed on both ambient and light colors
        amb.v /= 4.672

        new_amb = [c for c in amb]
        new_amb.append(1.0)

        f3dMat.ambient_light_color = new_amb

    if f3dMat.set_lights:
        remove_first_link_if_exists(material, nodes["Shade Color"].inputs["Shade Color"].links)
        remove_first_link_if_exists(material, nodes["Shade Color"].inputs["Ambient Color"].links)

        # TODO: feature to toggle gamma correction
        light = f3dMat.default_light_color
        if not f3dMat.use_default_lighting:
            if f3dMat.f3d_light1 is not None:
                light = f3dMat.f3d_light1.color
            else:
                light = [1.0, 1.0, 1.0, 1.0]

        corrected_col = gammaCorrect(light)
        corrected_col.append(1.0)
        corrected_amb = gammaCorrect(f3dMat.ambient_light_color)
        corrected_amb.append(1.0)

        nodes["Shade Color"].inputs["Shade Color"].default_value = tuple(c for c in corrected_col)
        nodes["Shade Color"].inputs["Ambient Color"].default_value = tuple(c for c in corrected_amb)
    else:
        col = [1.0, 1.0, 1.0, 1.0]
        amb_col = [0.5, 0.5, 0.5, 1.0]
        nodes["Shade Color"].inputs["Shade Color"].default_value = tuple(c for c in col)
        nodes["Shade Color"].inputs["Ambient Color"].default_value = tuple(c for c in amb_col)
        link_if_none_exist(material, nodes["ShadeColOut"].outputs[0], nodes["Shade Color"].inputs["Shade Color"])
        link_if_none_exist(material, nodes["AmbientColOut"].outputs[0], nodes["Shade Color"].inputs["Ambient Color"])


def update_color_node(combiner_inputs, color: Color, prefix: str):
    """Function for updating either Prim or Env colors"""
    # TODO: feature to toggle gamma correction
    corrected_prim = gammaCorrect(color)
    combiner_inputs[f"{prefix} Color"].default_value = (
        corrected_prim[0],
        corrected_prim[1],
        corrected_prim[2],
        1.0,
    )
    combiner_inputs[f"{prefix} Alpha"].default_value = color[3]


# prim_color | Prim
# env_color | Env
def get_color_input_update_callback(attr_name="", prefix=""):
    def input_update_callback(self: bpy.types.Material, context: bpy.types.Context):
        with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
            if not material:
                return
            f3dMat: "F3DMaterialProperty" = material.f3d_mat
            nodes = material.node_tree.nodes
            combiner_inputs = nodes["CombinerInputs"].inputs
            update_color_node(combiner_inputs, getattr(f3dMat, attr_name), prefix)

    return input_update_callback


def update_node_values_of_material(material: bpy.types.Material, context):
    nodes = material.node_tree.nodes

    update_blend_method(material, context)
    if not has_f3d_nodes(material):
        return

    f3dMat: "F3DMaterialProperty" = material.f3d_mat

    update_combiner_connections(material, context)

    set_output_node_groups(material)

    if f3dMat.rdp_settings.g_tex_gen:
        if f3dMat.rdp_settings.g_tex_gen_linear:
            nodes["UV"].node_tree = bpy.data.node_groups["UV_EnvMap_Linear"]
        else:
            nodes["UV"].node_tree = bpy.data.node_groups["UV_EnvMap"]
    else:
        nodes["UV"].node_tree = bpy.data.node_groups["UV"]

    if f3dMat.rdp_settings.g_lighting:
        nodes["Shade Color"].node_tree = bpy.data.node_groups["ShdCol_L"]
    else:
        nodes["Shade Color"].node_tree = bpy.data.node_groups["ShdCol_V"]

    update_light_colors(material, context)

    combiner_inputs = nodes["CombinerInputs"].inputs

    update_color_node(combiner_inputs, f3dMat.prim_color, "Prim")
    update_color_node(combiner_inputs, f3dMat.env_color, "Env")

    combiner_inputs["Chroma Key Center"].default_value = (
        f3dMat.key_center[0],
        f3dMat.key_center[1],
        f3dMat.key_center[2],
        f3dMat.key_center[3],
    )
    combiner_inputs["Chroma Key Scale"].default_value = [value for value in f3dMat.key_scale] + [1]
    combiner_inputs["Prim LOD Fraction"].default_value = f3dMat.prim_lod_frac
    combiner_inputs["YUVConvert K4"].default_value = f3dMat.k4
    combiner_inputs["YUVConvert K5"].default_value = f3dMat.k5

    material.show_transparent_back = f3dMat.rdp_settings.g_cull_front
    material.use_backface_culling = f3dMat.rdp_settings.g_cull_back

    update_tex_values_manual(material, context)
    update_blend_method(material, context)
    update_fog_nodes(material, context)


def set_texture_settings_node(material: bpy.types.Material):
    nodes = material.node_tree.nodes
    textureSettings: bpy.types.ShaderNodeGroup = nodes["TextureSettings"]

    desired_group = bpy.data.node_groups["TextureSettings_Lite"]
    if (material.f3d_mat.tex0.tex and not material.f3d_mat.tex0.autoprop) or (
        material.f3d_mat.tex1.tex and not material.f3d_mat.tex1.autoprop
    ):
        desired_group = bpy.data.node_groups["TextureSettings_Advanced"]
    if textureSettings.node_tree is not desired_group:
        textureSettings.node_tree = desired_group


def setAutoProp(fieldProperty, pixelLength):
    fieldProperty.mask = math.ceil(math.log(pixelLength, 2) - 0.001)
    fieldProperty.shift = 0
    fieldProperty.low = 0
    fieldProperty.high = pixelLength
    if fieldProperty.clamp and fieldProperty.mirror:
        fieldProperty.high *= 2
    fieldProperty.high -= 1


def set_texture_size(self, tex_size, tex_index):
    nodes = self.node_tree.nodes
    uv_basis: bpy.types.ShaderNodeGroup = nodes["UV Basis"]
    inputs = uv_basis.inputs

    inputs[f"{tex_index} S TexSize"].default_value = tex_size[0]
    inputs[f"{tex_index} T TexSize"].default_value = tex_size[1]


def trunc_10_2(val: float):
    return int(val * 4) / 4


def update_tex_values_field(
    self: bpy.types.Material, texProperty: "TextureProperty", tex_size: list[int], tex_index: int
):
    nodes = self.node_tree.nodes
    textureSettings: bpy.types.ShaderNodeGroup = nodes["TextureSettings"]
    inputs = textureSettings.inputs

    set_texture_size(self, tex_size, tex_index)

    if texProperty.autoprop:
        setAutoProp(texProperty.S, tex_size[0])
        setAutoProp(texProperty.T, tex_size[1])

    str_index = str(tex_index)

    # S/T Low
    inputs[str_index + " S Low"].default_value = trunc_10_2(texProperty.S.low)
    inputs[str_index + " T Low"].default_value = trunc_10_2(texProperty.T.low)

    # S/T High
    inputs[str_index + " S High"].default_value = trunc_10_2(texProperty.S.high)
    inputs[str_index + " T High"].default_value = trunc_10_2(texProperty.T.high)

    # Clamp
    inputs[str_index + " ClampX"].default_value = 1 if texProperty.S.clamp else 0
    inputs[str_index + " ClampY"].default_value = 1 if texProperty.T.clamp else 0

    # Mask
    inputs[str_index + " S Mask"].default_value = texProperty.S.mask
    inputs[str_index + " T Mask"].default_value = texProperty.T.mask

    # Mirror
    inputs[str_index + " MirrorX"].default_value = 1 if texProperty.S.mirror > 0 else 0
    inputs[str_index + " MirrorY"].default_value = 1 if texProperty.T.mirror > 0 else 0

    # Shift
    inputs[str_index + " S Shift"].default_value = texProperty.S.shift
    inputs[str_index + " T Shift"].default_value = texProperty.T.shift


def iter_tex_nodes(node_tree: bpy.types.NodeTree, texIndex: int) -> Generator[bpy.types.TextureNodeImage, None, None]:
    for i in range(1, 5):
        nodeName = f"Tex{texIndex}_{i}"
        if node_tree.nodes.get(nodeName):
            yield node_tree.nodes[nodeName]


def toggle_texture_node_muting(material: bpy.types.Material, texIndex: int, isUsed: bool):
    node_tree = material.node_tree
    f3dMat: "F3DMaterialProperty" = material.f3d_mat

    # Enforce typing from generator
    texNode: None | bpy.types.TextureNodeImage = None

    node_3point_key = "3 Point Lerp" if texIndex == 0 else "3 Point Lerp.001"
    node_3point = node_tree.nodes.get(node_3point_key)

    node_tex_color_conv_key = f"Tex{texIndex}_I"
    node_tex_color_conv = node_tree.nodes.get(node_tex_color_conv_key)

    # flip bool for clarity
    shouldMute = not isUsed

    for texNode in iter_tex_nodes(node_tree, texIndex):
        if texNode.mute != shouldMute:
            texNode.mute = shouldMute

    if node_tex_color_conv and node_tex_color_conv.mute != shouldMute:
        node_tex_color_conv.mute = shouldMute

    mute_3point = shouldMute or f3dMat.rdp_settings.g_mdsft_text_filt != "G_TF_BILERP"
    if node_3point and node_3point.mute != mute_3point:
        node_3point.mute = mute_3point


def set_texture_nodes_settings(
    material: bpy.types.Material, texProperty: "TextureProperty", texIndex: int, isUsed: bool
) -> (list[int] | None):
    node_tree = material.node_tree
    f3dMat: "F3DMaterialProperty" = material.f3d_mat

    # Return value
    texSize: Optional[list[int]] = None

    toggle_texture_node_muting(material, texIndex, isUsed)

    if not isUsed:
        return texSize

    # Enforce typing from generator
    texNode: None | bpy.types.TextureNodeImage = None
    for texNode in iter_tex_nodes(node_tree, texIndex):
        if texNode.image is not texProperty.tex:
            texNode.image = texProperty.tex
        texNode.interpolation = "Linear" if f3dMat.rdp_settings.g_mdsft_text_filt == "G_TF_AVERAGE" else "Closest"

        if texSize:
            continue

        if texNode.image is not None or texProperty.use_tex_reference:
            if texNode.image is not None:
                texSize = texNode.image.size
            else:
                texSize = texProperty.tex_reference_size
    return texSize


def update_tex_values_index(self: bpy.types.Material, *, texProperty: "TextureProperty", texIndex: int, isUsed: bool):
    nodes = self.node_tree.nodes

    tex_size = set_texture_nodes_settings(self, texProperty, texIndex, isUsed)

    if tex_size:  # only returns tex size if a texture is being set
        if tex_size[0] > 0 and tex_size[1] > 0:
            if texProperty.autoprop:
                setAutoProp(texProperty.S, tex_size[0])
                setAutoProp(texProperty.T, tex_size[1])
            update_tex_values_field(self, texProperty, tex_size, texIndex)

            texFormat = texProperty.tex_format
            ciFormat = texProperty.ci_format
            if has_f3d_nodes(self):
                tex_I_node = nodes["Tex" + str(texIndex) + "_I"]
                desired_node = bpy.data.node_groups["Is not i"]
                if "IA" in texFormat or (texFormat[:2] == "CI" and "IA" in ciFormat):
                    desired_node = bpy.data.node_groups["Is ia"]
                elif texFormat[0] == "I" or (texFormat[:2] == "CI" and ciFormat[0] == "I"):
                    desired_node = bpy.data.node_groups["Is i"]

                if tex_I_node.node_tree is not desired_node:
                    tex_I_node.node_tree = desired_node


def update_tex_values_and_formats(self, context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        f3d_mat = context.material.f3d_mat
        useDict = all_combiner_uses(f3d_mat)
        isMultiTexture = (
            useDict["Texture 0"]
            and f3d_mat.tex0.tex is not None
            and useDict["Texture 1"]
            and f3d_mat.tex1.tex is not None
        )
        if self.tex is not None:
            self.tex_format = getOptimalFormat(self.tex, self.tex_format, isMultiTexture)

        update_tex_values_manual(context.material, context)


def update_tex_values(self, context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        try:
            prop_path = self.path_from_id()
        except:
            prop_path = None

        update_tex_values_manual(material, context, prop_path=prop_path)


def get_tex_basis_size(f3d_mat: "F3DMaterialProperty"):
    tex_size = None
    if f3d_mat.tex0.tex is not None and f3d_mat.tex1.tex is not None:
        return f3d_mat.tex0.tex.size if f3d_mat.uv_basis == "TEXEL0" else f3d_mat.tex1.tex.size
    elif f3d_mat.tex0.tex is not None:
        return f3d_mat.tex0.tex.size
    elif f3d_mat.tex1.tex is not None:
        return f3d_mat.tex1.tex.size
    return tex_size


def get_tex_gen_size(tex_size: list[int | float]):
    return (tex_size[0] - 1) / 1024, (tex_size[1] - 1) / 1024


def update_tex_values_manual(material: bpy.types.Material, context, prop_path=None):
    f3dMat: "F3DMaterialProperty" = material.f3d_mat
    nodes = material.node_tree.nodes
    texture_settings = nodes["TextureSettings"]
    texture_inputs: bpy.types.NodeInputs = texture_settings.inputs
    useDict = all_combiner_uses(f3dMat)

    tex0_used = useDict["Texture 0"] and f3dMat.tex0.tex is not None
    tex1_used = useDict["Texture 1"] and f3dMat.tex1.tex is not None

    if not tex0_used and not tex1_used:
        texture_settings.mute = True
        set_texture_nodes_settings(material, f3dMat.tex0, 0, False)
        set_texture_nodes_settings(material, f3dMat.tex1, 1, False)
        return
    elif texture_settings.mute:
        texture_settings.mute = False

    isTexGen = f3dMat.rdp_settings.g_tex_gen  # linear requires tex gen to be enabled as well

    if f3dMat.scale_autoprop:
        if isTexGen:
            tex_size = get_tex_basis_size(f3dMat)

            if tex_size is not None:
                # This is needed for exporting tex gen!
                f3dMat.tex_scale = get_tex_gen_size(tex_size)
        else:
            f3dMat.tex_scale = (1, 1)

        if f3dMat.tex0.tex is not None:
            texture_inputs["0 S TexSize"].default_value = f3dMat.tex0.tex.size[0]
            texture_inputs["0 T TexSize"].default_value = f3dMat.tex0.tex.size[0]
        if f3dMat.tex1.tex is not None:
            texture_inputs["1 S TexSize"].default_value = f3dMat.tex1.tex.size[0]
            texture_inputs["1 T TexSize"].default_value = f3dMat.tex1.tex.size[0]

    uv_basis: bpy.types.ShaderNodeGroup = nodes["UV Basis"]
    if f3dMat.uv_basis == "TEXEL0":
        uv_basis.node_tree = bpy.data.node_groups["UV Basis 0"]
    else:
        uv_basis.node_tree = bpy.data.node_groups["UV Basis 1"]

    if not isTexGen:
        uv_basis.inputs["S Scale"].default_value = f3dMat.tex_scale[0]
        uv_basis.inputs["T Scale"].default_value = f3dMat.tex_scale[1]
    elif f3dMat.scale_autoprop:
        # Tex gen is 1:1
        uv_basis.inputs["S Scale"].default_value = 1
        uv_basis.inputs["T Scale"].default_value = 1
    else:
        gen_size = get_tex_gen_size(get_tex_basis_size(f3dMat))
        # scale tex gen proportionally
        node_uv_scale = (f3dMat.tex_scale[0] / gen_size[0], f3dMat.tex_scale[1] / gen_size[1])
        uv_basis.inputs["S Scale"].default_value = node_uv_scale[0]
        uv_basis.inputs["T Scale"].default_value = node_uv_scale[1]

    if not prop_path or "tex0" in prop_path:
        update_tex_values_index(material, texProperty=f3dMat.tex0, texIndex=0, isUsed=tex0_used)
    if not prop_path or "tex1" in prop_path:
        update_tex_values_index(material, texProperty=f3dMat.tex1, texIndex=1, isUsed=tex1_used)

    texture_inputs["3 Point"].default_value = int(f3dMat.rdp_settings.g_mdsft_text_filt == "G_TF_BILERP")
    uv_basis.inputs["EnableOffset"].default_value = int(f3dMat.rdp_settings.g_mdsft_text_filt != "G_TF_POINT")
    set_texture_settings_node(material)


def shift_num(num: int, amt: int):
    if amt < 0:
        return num >> -amt
    return num << amt


def shift_dimensions(tex_prop: "TextureProperty", dimensions: tuple[int, int]):
    shifted = (shift_num(dimensions[0], tex_prop.S.shift), shift_num(dimensions[1], tex_prop.T.shift))
    s_mirror_scale = 2 if tex_prop.S.mirror else 1
    t_mirror_scale = 2 if tex_prop.T.mirror else 1
    return (shifted[0] * s_mirror_scale, shifted[1] * t_mirror_scale)


def getMaterialScrollDimensions(f3dMat):
    texDimensions0 = None
    texDimensions1 = None
    useDict = all_combiner_uses(f3dMat)

    if useDict["Texture 0"] and f3dMat.tex0.tex_set:
        if f3dMat.tex0.use_tex_reference:
            texDimensions0 = f3dMat.tex0.tex_reference_size
        elif f3dMat.tex0.tex:
            texDimensions0 = (f3dMat.tex0.tex.size[0], f3dMat.tex0.tex.size[1])

    if useDict["Texture 1"] and f3dMat.tex1.tex_set:
        if f3dMat.tex1.use_tex_reference:
            texDimensions1 = f3dMat.tex1.tex_reference_size
        elif f3dMat.tex0.tex:
            texDimensions1 = (f3dMat.tex1.tex.size[0], f3dMat.tex1.tex.size[1])

    if texDimensions0 is not None:
        texDimensions0 = shift_dimensions(f3dMat.tex0, texDimensions0)
    else:
        texDimensions0 = (1, 1)

    if texDimensions1 is not None:
        texDimensions1 = shift_dimensions(f3dMat.tex1, texDimensions1)
    else:
        texDimensions1 = (1, 1)

    return (max(1, texDimensions0[0], texDimensions1[0]), max(1, texDimensions0[1], texDimensions1[1]))


def update_preset_manual(material, context):
    if has_f3d_nodes(material):
        update_node_values_of_material(material, context)
    update_tex_values_manual(material, context)


def update_preset_manual_v4(material, preset):
    override = bpy.context.copy()
    override["material"] = material
    if preset == "Shaded Solid":
        preset = "sm64_shaded_solid"
    if preset == "Shaded Texture":
        preset = "sm64_shaded_texture"
    if preset.lower() != "custom":
        material.f3d_update_flag = True
        bpy.ops.script.execute_preset(
            override, filepath=findF3DPresetPath(preset), menu_idname="MATERIAL_MT_f3d_presets"
        )
        material.f3d_update_flag = False


def has_f3d_nodes(material: bpy.types.Material):
    return "Material Output F3D" in material.node_tree.nodes


@persistent
def load_handler(dummy):
    logger.info("Checking for base F3D material library.")

    for lib in bpy.data.libraries:
        lib_path = bpy.path.abspath(lib.filepath)

        # detect if this is one your addon's libraries here
        if "f3d_material_library.blend" in lib_path:

            addon_dir = os.path.dirname(os.path.abspath(__file__))
            new_lib_path = os.path.join(addon_dir, "f3d_material_library.blend")

            if lib_path != new_lib_path:
                logger.info("Reloading the library: %s : %s => %s" % (lib.name, lib_path, new_lib_path))

                lib.filepath = new_lib_path
                lib.reload()
            bpy.context.scene["f3d_lib_dir"] = None  # force node reload!
            link_f3d_material_library()


bpy.app.handlers.load_post.append(load_handler)

# bpy.context.mode returns the keys here, while the values are required by bpy.ops.object.mode_set
BLENDER_MODE_TO_MODE_SET = {"PAINT_VERTEX": "VERTEX_PAINT", "EDIT_MESH": "EDIT"}
get_mode_set_from_context_mode = lambda mode: BLENDER_MODE_TO_MODE_SET.get(mode, "OBJECT")

SCENE_PROPERTIES_VERSION = 1


def createOrUpdateSceneProperties():
    group = bpy.data.node_groups.get("SceneProperties")
    upgrade_group = bool(group and group.get("version", -1) < SCENE_PROPERTIES_VERSION)

    if group and not upgrade_group:
        # Group is ready and up to date
        return

    if upgrade_group and group:
        # Need to upgrade; remove old outputs
        for out in group.outputs:
            group.outputs.remove(out)
        new_group = group
    else:
        logger.info("Creating Scene Properties")
        # create a group
        new_group = bpy.data.node_groups.new("SceneProperties", "ShaderNodeTree")
        # create group outputs
        new_group.nodes.new("NodeGroupOutput")

    new_group["version"] = SCENE_PROPERTIES_VERSION

    # Create outputs
    _nodeFogEnable: bpy.types.NodeSocketInt = new_group.outputs.new("NodeSocketInt", "FogEnable")
    _nodeFogColor: bpy.types.NodeSocketColor = new_group.outputs.new("NodeSocketColor", "FogColor")
    _nodeF3D_NearClip: bpy.types.NodeSocketFloat = new_group.outputs.new("NodeSocketFloat", "F3D_NearClip")
    _nodeF3D_FarClip: bpy.types.NodeSocketFloat = new_group.outputs.new("NodeSocketFloat", "F3D_FarClip")
    _nodeBlender_Game_Scale: bpy.types.NodeSocketFloat = new_group.outputs.new("NodeSocketFloat", "Blender_Game_Scale")
    _nodeFogNear: bpy.types.NodeSocketInt = new_group.outputs.new("NodeSocketInt", "FogNear")
    _nodeFogFar: bpy.types.NodeSocketInt = new_group.outputs.new("NodeSocketInt", "FogFar")
    _nodeShadeColor: bpy.types.NodeSocketColor = new_group.outputs.new("NodeSocketColor", "ShadeColor")
    _nodeAmbientColor: bpy.types.NodeSocketColor = new_group.outputs.new("NodeSocketColor", "AmbientColor")
    _nodeLightDirection: bpy.types.NodeSocketVectorDirection = new_group.outputs.new(
        "NodeSocketVectorDirection", "LightDirection"
    )

    # Set outputs from render settings
    sceneOutputs: bpy.types.NodeGroupOutput = new_group.nodes["Group Output"]
    renderSettings: "Fast64RenderSettings_Properties" = bpy.context.scene.fast64.renderSettings

    update_scene_props_from_render_settings(bpy.context, sceneOutputs, renderSettings)


def createScenePropertiesForMaterial(material: bpy.types.Material):
    node_tree = material.node_tree

    # Either create or update SceneProperties if needed
    createOrUpdateSceneProperties()

    # create a new group node to hold the tree
    scene_props = node_tree.nodes.new(type="ShaderNodeGroup")
    scene_props.name = "SceneProperties"
    scene_props.location = (-420, -360)
    scene_props.node_tree = bpy.data.node_groups["SceneProperties"]
    # link the new node to correct socket
    node_tree.links.new(scene_props.outputs["FogEnable"], node_tree.nodes["FogEnable"].inputs[0])
    node_tree.links.new(scene_props.outputs["FogColor"], node_tree.nodes["FogColor"].inputs[0])
    node_tree.links.new(scene_props.outputs["FogNear"], node_tree.nodes["CalcFog"].inputs["FogNear"])
    node_tree.links.new(scene_props.outputs["FogFar"], node_tree.nodes["CalcFog"].inputs["FogFar"])
    node_tree.links.new(
        scene_props.outputs["Blender_Game_Scale"], node_tree.nodes["CalcFog"].inputs["Blender_Game_Scale"]
    )
    node_tree.links.new(scene_props.outputs["F3D_NearClip"], node_tree.nodes["CalcFog"].inputs["F3D_NearClip"])
    node_tree.links.new(scene_props.outputs["F3D_FarClip"], node_tree.nodes["CalcFog"].inputs["F3D_FarClip"])

    node_tree.links.new(scene_props.outputs["ShadeColor"], node_tree.nodes["ShadeColor"].inputs[0])
    node_tree.links.new(scene_props.outputs["AmbientColor"], node_tree.nodes["AmbientColor"].inputs[0])
    node_tree.links.new(scene_props.outputs["LightDirection"], node_tree.nodes["LightDirection"].inputs[0])


def link_f3d_material_library():
    dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "f3d_material_library.blend")

    prevMode = bpy.context.mode
    if prevMode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    with bpy.data.libraries.load(dir) as (data_from, data_to):
        dirMat = os.path.join(dir, "Material")
        dirNode = os.path.join(dir, "NodeTree")
        for mat in data_from.materials:
            if mat is not None:
                bpy.ops.wm.link(filepath=os.path.join(dirMat, mat), directory=dirMat, filename=mat)

        # linking is SUPER slow, this only links if the scene hasnt been linked yet
        # in future updates, this will likely need to be something numerated so if more nodes are added then they will be linked
        if bpy.context.scene.get("f3d_lib_dir") != dirNode:
            # link groups after to bring extra node_groups
            for node_group in data_from.node_groups:
                if node_group is not None:
                    bpy.ops.wm.link(filepath=os.path.join(dirNode, node_group), directory=dirNode, filename=node_group)
            bpy.context.scene["f3d_lib_dir"] = dirNode

    # TODO: Figure out a better way to save the user's old mode
    if prevMode != "OBJECT":
        bpy.ops.object.mode_set(mode=get_mode_set_from_context_mode(prevMode))


def shouldConvOrCreateColorAttribute(mesh: bpy.types.Mesh, attr_name="Col"):
    has_attr, conv_attr = False, False
    if attr_name in mesh.attributes:
        attribute: bpy.types.Attribute = mesh.attributes[attr_name]
        has_attr = True
        conv_attr = attribute.data_type != "FLOAT_COLOR" or attribute.domain != "CORNER"
    return has_attr, conv_attr


def convertColorAttribute(mesh: bpy.types.Mesh, attr_name="Col"):
    prev_index = mesh.attributes.active_index
    attr_index = mesh.attributes.find(attr_name)
    if attr_index < 0:
        raise PluginError(f"Failed to find the index for mesh attr {attr_name}. Attribute conversion has failed!")

    mesh.attributes.active_index = attr_index
    bpy.ops.geometry.attribute_convert(mode="GENERIC", domain="CORNER", data_type="FLOAT_COLOR")
    mesh.attributes.active_index = prev_index


def addColorAttributesToModel(obj: bpy.types.Object):
    if not isinstance(obj.data, bpy.types.Mesh):
        return

    prevMode = bpy.context.mode
    if prevMode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    selectSingleObject(obj)

    mesh: bpy.types.Mesh = obj.data

    conv_col, has_col = shouldConvOrCreateColorAttribute(mesh, attr_name="Col")
    if conv_col:
        convertColorAttribute(mesh, attr_name="Col")
    elif not has_col:
        mesh.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")

    conv_alpha, has_alpha = shouldConvOrCreateColorAttribute(mesh, attr_name="Alpha")
    if conv_alpha:
        convertColorAttribute(mesh, attr_name="Alpha")
    elif not has_alpha:
        mesh.color_attributes.new("Alpha", "FLOAT_COLOR", "CORNER")

    if prevMode != "OBJECT":
        bpy.ops.object.mode_set(mode=get_mode_set_from_context_mode(prevMode))


def createF3DMat(obj: bpy.types.Object | None, preset="Shaded Solid", index=None):
    # link all node_groups + material from addon's data .blend
    link_f3d_material_library()

    # beefwashere is a linked material containing the default layout for all the linked node_groups
    mat = bpy.data.materials["beefwashere"]
    # duplicate and rename the linked material
    material = mat.copy()
    material.name = "f3dlite_material"
    # remove the linked material so it doesn't bother anyone or get meddled with
    bpy.data.materials.remove(mat)

    createScenePropertiesForMaterial(material)

    # add material to object
    if obj is not None:
        addColorAttributesToModel(obj)
        if index is None:
            obj.data.materials.append(material)
            if bpy.context.object is not None:
                bpy.context.object.active_material_index = len(obj.material_slots) - 1
        else:
            obj.material_slots[index].material = material
            if bpy.context.object is not None:
                bpy.context.object.active_material_index = index

    material.is_f3d = True
    material.mat_ver = 5

    update_preset_manual_v4(material, preset)

    return material


def reloadDefaultF3DPresets():
    presetNameToFilename = {}
    for _, gamePresets in material_presets.items():
        for presetName, _ in gamePresets.items():
            presetNameToFilename[bpy.path.display_name(presetName)] = presetName
    for material in bpy.data.materials:
        if material.f3d_mat.presetName in presetNameToFilename:
            update_preset_manual_v4(material, presetNameToFilename[material.f3d_mat.presetName])


class CreateFast3DMaterial(bpy.types.Operator):
    bl_idname = "object.create_f3d_mat"
    bl_label = "Create Fast3D Material"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        obj = bpy.context.view_layer.objects.active
        if obj is None:
            self.report({"ERROR"}, "No active object selected.")
        else:
            preset = getDefaultMaterialPreset("Shaded Solid")
            createF3DMat(obj, preset)
            self.report({"INFO"}, "Created new Fast3D material.")
        return {"FINISHED"}


class ReloadDefaultF3DPresets(bpy.types.Operator):
    bl_idname = "object.reload_f3d_presets"
    bl_label = "Reload Default Fast3D Presets"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        reloadDefaultF3DPresets()
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


def get_tex_prop_from_path(material: bpy.types.Material, path: str) -> Tuple["TextureProperty", int]:
    if "tex0" in path:
        return material.f3d_mat.tex0, 0
    return material.f3d_mat.tex1, 1


def already_updating_material(material: bpy.types.Material | None):
    """Check if material is updating already"""
    return getattr(material, "f3d_update_flag", False)


def update_tex_field_prop(self: bpy.types.Property, context: bpy.types.Context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        prop_path = self.path_from_id()
        tex_property, tex_index = get_tex_prop_from_path(material, prop_path)
        tex_size = tex_property.get_tex_size()

        if tex_size[0] > 0 and tex_size[1] > 0:
            update_tex_values_field(material, tex_property, tex_size, tex_index)
        set_texture_settings_node(material)


def toggle_auto_prop(self, context: bpy.types.Context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        prop_path = self.path_from_id()
        tex_property, tex_index = get_tex_prop_from_path(material, prop_path)
        if tex_property.autoprop:
            tex_size = tuple([s for s in tex_property.get_tex_size()])

            setAutoProp(tex_property.S, tex_size[0])
            setAutoProp(tex_property.T, tex_size[1])
            update_tex_values_field(material, tex_property, tex_size, tex_index)

        set_texture_settings_node(material)


class TextureFieldProperty(bpy.types.PropertyGroup):
    clamp: bpy.props.BoolProperty(
        name="Clamp",
        update=update_tex_field_prop,
    )
    mirror: bpy.props.BoolProperty(
        name="Mirror",
        update=update_tex_field_prop,
    )
    low: bpy.props.FloatProperty(
        name="Low",
        min=0,
        max=1023.75,
        update=update_tex_field_prop,
    )
    high: bpy.props.FloatProperty(
        name="High",
        min=0,
        max=1023.75,
        update=update_tex_field_prop,
    )
    mask: bpy.props.IntProperty(
        name="Mask",
        min=0,
        max=15,
        default=5,
        update=update_tex_field_prop,
    )
    shift: bpy.props.IntProperty(
        name="Shift",
        min=-5,
        max=10,
        update=update_tex_field_prop,
    )

    def key(self):
        return (self.clamp, self.mirror, round(self.low * 4), round(self.high * 4), self.mask, self.shift)


class SetTileSizeScrollProperty(bpy.types.PropertyGroup):
    s: bpy.props.IntProperty(min=-4095, max=4095, default=0)
    t: bpy.props.IntProperty(min=-4095, max=4095, default=0)
    interval: bpy.props.IntProperty(min=1, soft_max=1000, default=1)

    def key(self):
        return (self.s, self.t, self.interval)


class TextureProperty(bpy.types.PropertyGroup):
    tex: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Texture",
        update=update_tex_values_and_formats,
    )

    tex_format: bpy.props.EnumProperty(
        name="Format",
        items=enumTexFormat,
        default="RGBA16",
        update=update_tex_values,
    )
    ci_format: bpy.props.EnumProperty(
        name="CI Format",
        items=enumCIFormat,
        default="RGBA16",
        update=update_tex_values,
    )
    S: bpy.props.PointerProperty(type=TextureFieldProperty)
    T: bpy.props.PointerProperty(type=TextureFieldProperty)

    use_tex_reference: bpy.props.BoolProperty(
        name="Use Texture Reference",
        default=False,
        update=update_tex_values,
    )
    tex_reference: bpy.props.StringProperty(
        name="Texture Reference",
        default="0x08000000",
    )
    tex_reference_size: bpy.props.IntVectorProperty(
        name="Texture Reference Size",
        min=1,
        size=2,
        default=(32, 32),
        update=update_tex_values,
    )
    pal_reference: bpy.props.StringProperty(
        name="Palette Reference",
        default="0x08000000",
    )
    pal_reference_size: bpy.props.IntProperty(
        name="Texture Reference Size",
        min=1,
        default=16,
    )

    menu: bpy.props.BoolProperty()
    tex_set: bpy.props.BoolProperty(
        default=True,
        update=update_node_values_with_preset,
    )
    autoprop: bpy.props.BoolProperty(
        name="Autoprop",
        update=toggle_auto_prop,
        default=True,
    )
    tile_scroll: bpy.props.PointerProperty(type=SetTileSizeScrollProperty)

    def get_tex_size(self) -> list[int]:
        if self.tex or self.use_tex_reference:
            if self.tex is not None:
                return self.tex.size
            else:
                return self.tex_reference_size
        return [0, 0]

    def key(self):
        texSet = self.tex_set
        isCI = self.tex_format == "CI8" or self.tex_format == "CI4"
        useRef = self.use_tex_reference
        return (
            self.tex_set,
            self.tex if texSet else None,
            self.tex_format if texSet else None,
            self.ci_format if texSet and isCI else None,
            self.S.key() if texSet else None,
            self.T.key() if texSet else None,
            self.autoprop if texSet else None,
            self.tile_scroll.key() if texSet else None,
            self.use_tex_reference if texSet else None,
            self.tex_reference if texSet and useRef else None,
            self.tex_reference_size if texSet and useRef else None,
            self.pal_reference if texSet and useRef and isCI else None,
            self.pal_reference_size if texSet and useRef and isCI else None,
        )


def on_tex_autoprop(texProperty, context):
    if texProperty.autoprop and texProperty.tex is not None:
        tex_size = texProperty.tex.size
        if tex_size[0] > 0 and tex_size[1] > 0:
            setAutoProp(texProperty.S, tex_size[0])
            setAutoProp(texProperty.T, tex_size[1])


def update_combiner_connections_and_preset(self, context: bpy.types.Context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        f3d_mat: "F3DMaterialProperty" = material.f3d_mat
        f3d_mat.presetName = "Custom"

        prop_path = self.path_from_id()
        combiner = 1 if "combiner1" in prop_path else 2

        update_combiner_connections(material, context, combiner=combiner)

        toggle_texture_node_muting(material, 0, f3d_mat.tex0.tex and combiner_uses_tex0(material.f3d_mat))
        toggle_texture_node_muting(material, 1, f3d_mat.tex1.tex and combiner_uses_tex1(material.f3d_mat))


def ui_image(
    canUseLargeTextures: bool, layout: bpy.types.UILayout, textureProp: TextureProperty, name: str, showCheckBox: bool
):
    inputGroup = layout.box().column()

    inputGroup.prop(
        textureProp, "menu", text=name + " Properties", icon="TRIA_DOWN" if textureProp.menu else "TRIA_RIGHT"
    )
    if textureProp.menu:
        tex = textureProp.tex
        prop_input_name = inputGroup.column()
        prop_input = inputGroup.column()

        if showCheckBox:
            prop_input_name.prop(textureProp, "tex_set", text="Set Texture")
        else:
            prop_input_name.label(text=name)
        texIndex = name[-1]

        prop_input.prop(textureProp, "use_tex_reference")
        if textureProp.use_tex_reference:
            prop_split(prop_input, textureProp, "tex_reference", "Texture Reference")
            prop_split(prop_input, textureProp, "tex_reference_size", "Texture Size")
            if textureProp.tex_format[:2] == "CI":
                prop_split(prop_input, textureProp, "pal_reference", "Palette Reference")
                prop_split(prop_input, textureProp, "pal_reference_size", "Palette Size")

        else:
            prop_input.template_ID(
                textureProp, "tex", new="image.new", open="image.open", unlink="image.tex" + texIndex + "_unlink"
            )
            prop_input.enabled = textureProp.tex_set

            if tex is not None:
                prop_input.label(text="Size: " + str(tex.size[0]) + " x " + str(tex.size[1]))

        if canUseLargeTextures:
            prop_input.label(text="Large texture mode enabled.")
            prop_input.label(text="Each triangle must fit in a single tile load.")
            prop_input.label(text="UVs must be in the [0, 1024] pixel range.")
        else:
            tmemUsageUI(prop_input, textureProp)

        prop_split(prop_input, textureProp, "tex_format", name="Format")
        if textureProp.tex_format[:2] == "CI":
            prop_split(prop_input, textureProp, "ci_format", name="CI Format")

        if not (canUseLargeTextures):
            texFieldSettings = prop_input.column()
            clampSettings = texFieldSettings.row()
            clampSettings.prop(textureProp.S, "clamp", text="Clamp S")
            clampSettings.prop(textureProp.T, "clamp", text="Clamp T")

            mirrorSettings = texFieldSettings.row()
            mirrorSettings.prop(textureProp.S, "mirror", text="Mirror S")
            mirrorSettings.prop(textureProp.T, "mirror", text="Mirror T")

            prop_input.prop(textureProp, "autoprop", text="Auto Set Other Properties")

            if not textureProp.autoprop:
                mask = prop_input.row()
                mask.prop(textureProp.S, "mask", text="Mask S")
                mask.prop(textureProp.T, "mask", text="Mask T")

                shift = prop_input.row()
                shift.prop(textureProp.S, "shift", text="Shift S")
                shift.prop(textureProp.T, "shift", text="Shift T")

                low = prop_input.row()
                low.prop(textureProp.S, "low", text="S Low")
                low.prop(textureProp.T, "low", text="T Low")

                high = prop_input.row()
                high.prop(textureProp.S, "high", text="S High")
                high.prop(textureProp.T, "high", text="T High")

            if (
                tex is not None
                and tex.size[0] > 0
                and tex.size[1] > 0
                and (math.log(tex.size[0], 2) % 1 > 0.000001 or math.log(tex.size[1], 2) % 1 > 0.000001)
            ):
                warnBox = layout.box()
                warnBox.label(text="Warning: Texture dimensions are not power of 2.")
                warnBox.label(text="Wrapping only occurs on power of 2 bounds.")


class CombinerProperty(bpy.types.PropertyGroup):
    A: bpy.props.EnumProperty(
        name="A",
        description="A",
        items=combiner_enums["Case A"],
        default="TEXEL0",
        update=update_combiner_connections_and_preset,
    )

    B: bpy.props.EnumProperty(
        name="B",
        description="B",
        items=combiner_enums["Case B"],
        default="0",
        update=update_combiner_connections_and_preset,
    )

    C: bpy.props.EnumProperty(
        name="C",
        description="C",
        items=combiner_enums["Case C"],
        default="SHADE",
        update=update_combiner_connections_and_preset,
    )

    D: bpy.props.EnumProperty(
        name="D",
        description="D",
        items=combiner_enums["Case D"],
        default="0",
        update=update_combiner_connections_and_preset,
    )

    A_alpha: bpy.props.EnumProperty(
        name="A Alpha",
        description="A Alpha",
        items=combiner_enums["Case A Alpha"],
        default="0",
        update=update_combiner_connections_and_preset,
    )

    B_alpha: bpy.props.EnumProperty(
        name="B Alpha",
        description="B Alpha",
        items=combiner_enums["Case B Alpha"],
        default="0",
        update=update_combiner_connections_and_preset,
    )

    C_alpha: bpy.props.EnumProperty(
        name="C Alpha",
        description="C Alpha",
        items=combiner_enums["Case C Alpha"],
        default="0",
        update=update_combiner_connections_and_preset,
    )

    D_alpha: bpy.props.EnumProperty(
        name="D Alpha",
        description="D Alpha",
        items=combiner_enums["Case D Alpha"],
        default="ENVIRONMENT",
        update=update_combiner_connections_and_preset,
    )

    def key(self):
        return (
            self.A,
            self.B,
            self.C,
            self.D,
            self.A_alpha,
            self.B_alpha,
            self.C_alpha,
            self.D_alpha,
        )


class ProceduralAnimProperty(bpy.types.PropertyGroup):
    speed: bpy.props.FloatProperty(name="Speed", default=1)
    amplitude: bpy.props.FloatProperty(name="Amplitude", default=1)
    frequency: bpy.props.FloatProperty(name="Frequency", default=1)
    spaceFrequency: bpy.props.FloatProperty(name="Space Frequency", default=0)
    offset: bpy.props.FloatProperty(name="Offset", default=0)
    noiseAmplitude: bpy.props.FloatProperty(name="Amplitude", default=1)
    animate: bpy.props.BoolProperty()
    animType: bpy.props.EnumProperty(name="Type", items=enumTexScroll)

    def key(self):
        anim = self.animate
        return (
            self.animate,
            round(self.speed, 4) if anim else None,
            round(self.amplitude, 4) if anim else None,
            round(self.frequency, 4) if anim else None,
            round(self.spaceFrequency, 4) if anim else None,
            round(self.offset, 4) if anim else None,
            round(self.noiseAmplitude, 4) if anim else None,
            self.animType if anim else None,
        )


class ProcAnimVectorProperty(bpy.types.PropertyGroup):
    x: bpy.props.PointerProperty(type=ProceduralAnimProperty)
    y: bpy.props.PointerProperty(type=ProceduralAnimProperty)
    z: bpy.props.PointerProperty(type=ProceduralAnimProperty)
    pivot: bpy.props.FloatVectorProperty(size=2, name="Pivot")
    angularSpeed: bpy.props.FloatProperty(default=1, name="Angular Speed")
    menu: bpy.props.BoolProperty()

    def key(self):
        return (
            self.x.key(),
            self.y.key(),
            self.z.key(),
            round(self.pivot[0], 4),
            round(self.pivot[1], 4),
            round(self.angularSpeed, 4),
        )


class PrimDepthSettings(bpy.types.PropertyGroup):
    z: bpy.props.IntProperty(
        name="Prim Depth: Z",
        default=0,
        soft_min=-1,
        soft_max=0x7FFF,
        description=(
            """The value to use for z is the screen Z position of the object you are rendering."""
            """ This is a value ranging from 0x0000 to 0x7fff, where 0x0000 usually corresponds to """
            """the near clipping plane and 0x7fff usually corresponds to the far clipping plane."""
            """ You can use -1 to force Z to be at the far clipping plane."""
        ),
    )
    dz: bpy.props.IntProperty(
        name="Prim Depth: Delta Z",
        default=0,
        soft_min=0,
        soft_max=0x4000,
        description=(
            """The dz value should be set to 0."""
            """ This value is used for antialiasing and objects drawn in decal render mode """
            """and must always be a power of 2 (0, 1, 2, 4, 8, ... 0x4000)."""
            """ If you are using decal mode and part of the decaled object is not being rendered correctly, """
            """try setting this to powers of 2. Otherwise use 0."""
        ),
    )

    def key(self):
        return (self.z, self.dz)


class RDPSettings(bpy.types.PropertyGroup):
    g_zbuffer: bpy.props.BoolProperty(
        name="Z Buffer",
        default=True,
        update=update_node_values_with_preset,
    )
    g_shade: bpy.props.BoolProperty(
        name="Shading",
        default=True,
        update=update_node_values_with_preset,
    )
    # v1/2 difference
    g_cull_front: bpy.props.BoolProperty(
        name="Cull Front",
        update=update_node_values_with_preset,
    )
    # v1/2 difference
    g_cull_back: bpy.props.BoolProperty(
        name="Cull Back",
        default=True,
        update=update_node_values_with_preset,
    )
    g_fog: bpy.props.BoolProperty(
        name="Fog",
        update=update_node_values_with_preset,
    )
    g_lighting: bpy.props.BoolProperty(
        name="Lighting",
        default=True,
        update=update_node_values_with_preset,
    )
    g_tex_gen: bpy.props.BoolProperty(
        name="Texture UV Generate",
        update=update_node_values_with_preset,
    )
    g_tex_gen_linear: bpy.props.BoolProperty(
        name="Texture UV Generate Linear",
        update=update_node_values_with_preset,
    )
    # v1/2 difference
    g_shade_smooth: bpy.props.BoolProperty(
        name="Smooth Shading",
        default=True,
        update=update_node_values_with_preset,
    )
    # f3dlx2 only
    g_clipping: bpy.props.BoolProperty(
        name="Clipping",
        update=update_node_values_with_preset,
    )

    # upper half mode
    # v2 only
    g_mdsft_alpha_dither: bpy.props.EnumProperty(
        name="Alpha Dither",
        items=enumAlphaDither,
        default="G_AD_NOISE",
        update=update_node_values_with_preset,
    )
    # v2 only
    g_mdsft_rgb_dither: bpy.props.EnumProperty(
        name="RGB Dither",
        items=enumRGBDither,
        default="G_CD_MAGICSQ",
        update=update_node_values_with_preset,
    )
    g_mdsft_combkey: bpy.props.EnumProperty(
        name="Chroma Key",
        items=enumCombKey,
        default="G_CK_NONE",
        update=update_node_values_with_preset,
    )
    g_mdsft_textconv: bpy.props.EnumProperty(
        name="Texture Convert",
        items=enumTextConv,
        default="G_TC_FILT",
        update=update_node_values_with_preset,
    )
    g_mdsft_text_filt: bpy.props.EnumProperty(
        name="Texture Filter",
        items=enumTextFilt,
        default="G_TF_BILERP",
        update=update_node_values_without_preset,
    )
    g_mdsft_textlut: bpy.props.EnumProperty(
        name="Texture LUT",
        items=enumTextLUT,
        default="G_TT_NONE",
    )
    g_mdsft_textlod: bpy.props.EnumProperty(
        name="Texture LOD",
        items=enumTextLOD,
        default="G_TL_TILE",
        update=update_node_values_with_preset,
    )
    num_textures_mipmapped: bpy.props.IntProperty(
        name="Number of Mipmaps",
        default=2,
        min=2,
        max=8,
        description="Number of mipmaps when Texture LOD set to `LOD`. First cycle combiner should be ((Tex1 - Tex0) * LOD Frac) + Tex0",
    )
    g_mdsft_textdetail: bpy.props.EnumProperty(
        name="Texture Detail",
        items=enumTextDetail,
        default="G_TD_CLAMP",
        update=update_node_values_with_preset,
    )
    g_mdsft_textpersp: bpy.props.EnumProperty(
        name="Texture Perspective Correction",
        items=enumTextPersp,
        default="G_TP_PERSP",
        update=update_node_values_with_preset,
    )
    g_mdsft_cycletype: bpy.props.EnumProperty(
        name="Cycle Type",
        items=enumCycleType,
        default="G_CYC_1CYCLE",
        update=update_node_values_with_preset,
    )
    # v1 only
    g_mdsft_color_dither: bpy.props.EnumProperty(
        name="Color Dither",
        items=enumColorDither,
        default="G_CD_ENABLE",
        update=update_node_values_with_preset,
    )
    g_mdsft_pipeline: bpy.props.EnumProperty(
        name="Pipeline Span Buffer Coherency",
        items=enumPipelineMode,
        default="G_PM_1PRIMITIVE",
        update=update_node_values_with_preset,
    )

    # lower half mode
    g_mdsft_alpha_compare: bpy.props.EnumProperty(
        name="Alpha Compare",
        items=enumAlphaCompare,
        default="G_AC_NONE",
        update=update_node_values_with_preset,
    )
    g_mdsft_zsrcsel: bpy.props.EnumProperty(
        name="Z Source Selection",
        items=enumDepthSource,
        default="G_ZS_PIXEL",
        update=update_node_values_with_preset,
    )

    prim_depth: bpy.props.PointerProperty(
        type=PrimDepthSettings,
        name="Prim Depth Settings (gDPSetPrimDepth)",
        description="gDPSetPrimDepth",
    )

    clip_ratio: bpy.props.IntProperty(
        default=1,
        min=1,
        max=2**15 - 1,
        update=update_node_values_with_preset,
    )

    # cycle independent
    set_rendermode: bpy.props.BoolProperty(
        default=False,
        update=update_node_values_with_preset,
    )
    rendermode_advanced_enabled: bpy.props.BoolProperty(
        default=False,
        update=update_node_values_with_preset,
    )
    rendermode_preset_cycle_1: bpy.props.EnumProperty(
        items=enumRenderModesCycle1,
        default="G_RM_AA_ZB_OPA_SURF",
        name="Render Mode Cycle 1",
        update=update_node_values_with_preset,
    )
    rendermode_preset_cycle_2: bpy.props.EnumProperty(
        items=enumRenderModesCycle2,
        default="G_RM_AA_ZB_OPA_SURF2",
        name="Render Mode Cycle 2",
        update=update_node_values_with_preset,
    )
    aa_en: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
    )
    z_cmp: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
    )
    z_upd: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
    )
    im_rd: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
    )
    clr_on_cvg: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
    )
    cvg_dst: bpy.props.EnumProperty(
        name="Coverage Destination",
        items=enumCoverage,
        update=update_node_values_with_preset,
    )
    zmode: bpy.props.EnumProperty(
        name="Z Mode",
        items=enumZMode,
        update=update_node_values_with_preset,
    )
    cvg_x_alpha: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
    )
    alpha_cvg_sel: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
    )
    force_bl: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
    )

    # cycle dependent - (P * A + M - B) / (A + B)
    blend_p1: bpy.props.EnumProperty(
        name="Color Source 1",
        items=enumBlendColor,
        update=update_node_values_with_preset,
    )
    blend_p2: bpy.props.EnumProperty(
        name="Color Source 1",
        items=enumBlendColor,
        update=update_node_values_with_preset,
    )
    blend_m1: bpy.props.EnumProperty(
        name="Color Source 2",
        items=enumBlendColor,
        update=update_node_values_with_preset,
    )
    blend_m2: bpy.props.EnumProperty(
        name="Color Source 2",
        items=enumBlendColor,
        update=update_node_values_with_preset,
    )
    blend_a1: bpy.props.EnumProperty(
        name="Alpha Source",
        items=enumBlendAlpha,
        update=update_node_values_with_preset,
    )
    blend_a2: bpy.props.EnumProperty(
        name="Alpha Source",
        items=enumBlendAlpha,
        update=update_node_values_with_preset,
    )
    blend_b1: bpy.props.EnumProperty(
        name="Alpha Mix",
        items=enumBlendMix,
        update=update_node_values_with_preset,
    )
    blend_b2: bpy.props.EnumProperty(
        name="Alpha Mix",
        items=enumBlendMix,
        update=update_node_values_with_preset,
    )

    def key(self):
        setRM = self.set_rendermode
        rmAdv = self.rendermode_advanced_enabled
        prim = self.g_mdsft_zsrcsel == "G_ZS_PRIM"
        return (
            self.g_zbuffer,
            self.g_shade,
            self.g_cull_front,
            self.g_cull_back,
            self.g_fog,
            self.g_lighting,
            self.g_tex_gen,
            self.g_tex_gen_linear,
            self.g_shade_smooth,
            self.g_clipping,
            self.g_mdsft_alpha_dither,
            self.g_mdsft_rgb_dither,
            self.g_mdsft_combkey,
            self.g_mdsft_textconv,
            self.g_mdsft_text_filt,
            self.g_mdsft_textlod,
            self.g_mdsft_textdetail,
            self.g_mdsft_textpersp,
            self.g_mdsft_cycletype,
            self.g_mdsft_color_dither,
            self.g_mdsft_pipeline,
            self.g_mdsft_alpha_compare,
            self.g_mdsft_zsrcsel,
            self.prim_depth.key() if prim else None,
            self.clip_ratio,
            self.set_rendermode,
            self.aa_en if setRM and rmAdv else None,
            self.z_cmp if setRM and rmAdv else None,
            self.z_upd if setRM and rmAdv else None,
            self.im_rd if setRM and rmAdv else None,
            self.clr_on_cvg if setRM and rmAdv else None,
            self.cvg_dst if setRM and rmAdv else None,
            self.zmode if setRM and rmAdv else None,
            self.cvg_x_alpha if setRM and rmAdv else None,
            self.alpha_cvg_sel if setRM and rmAdv else None,
            self.force_bl if setRM and rmAdv else None,
            self.blend_p1 if setRM and rmAdv else None,
            self.blend_p2 if setRM and rmAdv else None,
            self.blend_m1 if setRM and rmAdv else None,
            self.blend_m2 if setRM and rmAdv else None,
            self.blend_a1 if setRM and rmAdv else None,
            self.blend_a2 if setRM and rmAdv else None,
            self.blend_b1 if setRM and rmAdv else None,
            self.blend_b2 if setRM and rmAdv else None,
            self.rendermode_preset_cycle_1 if setRM and not rmAdv else None,
            self.rendermode_preset_cycle_2 if setRM and not rmAdv else None,
        )


class DefaultRDPSettingsPanel(bpy.types.Panel):
    bl_label = "RDP Default Settings"
    bl_idname = "WORLD_PT_RDP_Default_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "SM64"

    def draw(self, context):
        world = context.scene.world
        layout = self.layout
        layout.box().label(text="RDP Default Settings")
        layout.label(text="If a material setting is a same as a default setting, then it won't be set.")
        ui_geo_mode(world.rdp_defaults, world, layout, True)
        ui_upper_mode(world.rdp_defaults, world, layout, True)
        ui_lower_mode(world.rdp_defaults, world, layout, True)
        ui_other(world.rdp_defaults, world, layout, True)


def getOptimalFormat(tex, curFormat, isMultitexture):
    texFormat = "RGBA16"
    if isMultitexture:
        return curFormat
    if tex.size[0] * tex.size[1] > 8192:  # Image too big
        return curFormat

    isGreyscale = True
    hasAlpha4bit = False
    hasAlpha1bit = False
    pixelValues = []

    # N64 is -Y, Blender is +Y
    pixels = tex.pixels[:]
    for j in reversed(range(tex.size[1])):
        for i in range(tex.size[0]):
            color = [1, 1, 1, 1]
            for field in range(tex.channels):
                color[field] = pixels[(j * tex.size[0] + i) * tex.channels + field]
            if not (color[0] == color[1] and color[1] == color[2]):
                isGreyscale = False
            if color[3] < 0.9375:
                hasAlpha4bit = True
            if color[3] < 0.5:
                hasAlpha1bit = True
            pixelColor = getRGBA16Tuple(color)
            if pixelColor not in pixelValues:
                pixelValues.append(pixelColor)

    if isGreyscale:
        if tex.size[0] * tex.size[1] > 4096:
            if not hasAlpha1bit:
                texFormat = "I4"
            else:
                texFormat = "IA4"
        else:
            if not hasAlpha4bit:
                texFormat = "I8"
            else:
                texFormat = "IA8"
    else:
        if len(pixelValues) <= 16:
            texFormat = "CI4"
        elif len(pixelValues) <= 256 and tex.size[0] * tex.size[1] <= 2048:
            texFormat = "CI8"
        else:
            texFormat = "RGBA16"

    return texFormat


def getCurrentPresetDir():
    return "f3d/" + bpy.context.scene.gameEditorMode.lower()


# modules/bpy_types.py -> Menu
class MATERIAL_MT_f3d_presets(Menu):
    bl_label = "F3D Material Presets"
    preset_operator = "script.execute_preset"

    def draw(self, _context):
        """
        Define these on the subclass:
        - preset_operator (string)
        - preset_subdir (string)

        Optionally:
        - preset_add_operator (string)
        - preset_extensions (set of strings)
        - preset_operator_defaults (dict of keyword args)
        """
        ext_valid = getattr(self, "preset_extensions", {".py", ".xml"})
        props_default = getattr(self, "preset_operator_defaults", None)
        add_operator = getattr(self, "preset_add_operator", None)
        presetDir = getCurrentPresetDir()
        paths = bpy.utils.preset_paths(presetDir) if not bpy.context.scene.f3dUserPresetsOnly else []
        paths += bpy.utils.preset_paths("f3d/user")
        self.path_menu(
            paths,
            self.preset_operator,
            props_default=props_default,
            filter_ext=lambda ext: ext.lower() in ext_valid,
            add_operator=add_operator,
        )


class AddPresetF3D(AddPresetBase, Operator):
    """Add an F3D Material Preset"""

    bl_idname = "material.f3d_preset_add"
    bl_label = "Add F3D Material Preset"
    preset_menu = "MATERIAL_MT_f3d_presets"

    # variable used for all preset values
    # do NOT set "mat" in this operator, even in a for loop! it overrides this value
    preset_defines = ["f3d_mat = bpy.context.material.f3d_mat"]

    # properties to store in the preset
    preset_values = [
        "f3d_mat",
    ]

    # where to store the preset
    preset_subdir = "f3d/user"

    defaults = [
        "Custom",
        # "Shaded Texture",
    ]

    ignore_props = {
        "f3d_mat.tex0.tex",
        "f3d_mat.tex0.tex_format",
        "f3d_mat.tex0.ci_format",
        "f3d_mat.tex0.use_tex_reference",
        "f3d_mat.tex0.tex_reference",
        "f3d_mat.tex0.tex_reference_size",
        "f3d_mat.tex0.pal_reference",
        "f3d_mat.tex0.pal_reference_size",
        "f3d_mat.tex0.S",
        "f3d_mat.tex0.T",
        "f3d_mat.tex0.menu",
        "f3d_mat.tex0.autoprop",
        "f3d_mat.tex0.save_large_texture",
        "f3d_mat.tex0.tile_scroll",
        "f3d_mat.tex0.tile_scroll.s",
        "f3d_mat.tex0.tile_scroll.t",
        "f3d_mat.tex0.tile_scroll.interval",
        "f3d_mat.tex1.tex",
        "f3d_mat.tex1.tex_format",
        "f3d_mat.tex1.ci_format",
        "f3d_mat.tex1.use_tex_reference",
        "f3d_mat.tex1.tex_reference",
        "f3d_mat.tex1.tex_reference_size",
        "f3d_mat.tex1.pal_reference",
        "f3d_mat.tex1.pal_reference_size",
        "f3d_mat.tex1.S",
        "f3d_mat.tex1.T",
        "f3d_mat.tex1.menu",
        "f3d_mat.tex1.autoprop",
        "f3d_mat.tex1.save_large_texture",
        "f3d_mat.tex1.tile_scroll",
        "f3d_mat.tex1.tile_scroll.s",
        "f3d_mat.tex1.tile_scroll.t",
        "f3d_mat.tex1.tile_scroll.interval",
        "f3d_mat.tex_scale",
        "f3d_mat.scale_autoprop",
        "f3d_mat.uv_basis",
        "f3d_mat.UVanim0",
        "f3d_mat.UVanim1",
        "f3d_mat.menu_procAnim",
        "f3d_mat.menu_geo",
        "f3d_mat.menu_upper",
        "f3d_mat.menu_lower",
        "f3d_mat.menu_other",
        "f3d_mat.menu_lower_render",
        "f3d_mat.f3d_update_flag",
        "f3d_mat.name",
        "f3d_mat.use_large_textures",
    }

    def execute(self, context):
        import os
        from bpy.utils import is_path_builtin

        if hasattr(self, "pre_cb"):
            self.pre_cb(context)

        preset_menu_class = getattr(bpy.types, self.preset_menu)

        is_xml = getattr(preset_menu_class, "preset_type", None) == "XML"
        is_preset_add = not (self.remove_name or self.remove_active)

        if is_xml:
            ext = ".xml"
        else:
            ext = ".py"

        name = self.name.strip() if is_preset_add else self.name

        if is_preset_add:
            if not name:
                return {"FINISHED"}

            filename = self.as_filename(name)
            if filename in material_presets or filename == "custom":
                self.report({"WARNING"}, "Unable to delete/overwrite default presets.")
                return {"CANCELLED"}

            # Reset preset name
            wm = bpy.data.window_managers[0]
            if name == wm.preset_name:
                wm.preset_name = "New Preset"

            filename = self.as_filename(name)
            context.material.f3d_mat.presetName = bpy.path.display_name(filename)

            target_path = os.path.join("presets", self.preset_subdir)
            try:
                target_path = bpy.utils.user_resource("SCRIPTS", target_path, create=True)
            except:  # 3.0
                target_path = bpy.utils.user_resource("SCRIPTS", path=target_path, create=True)

            if not target_path:
                self.report({"WARNING"}, "Failed to create presets path")
                return {"CANCELLED"}

            filepath = os.path.join(target_path, filename) + ext

            if hasattr(self, "add"):
                self.add(context, filepath)
            else:
                logger.info("Writing Preset: %r" % filepath)

                if is_xml:
                    import rna_xml

                    rna_xml.xml_file_write(context, filepath, preset_menu_class.preset_xml_map)
                else:

                    def rna_recursive_attr_expand(value, rna_path_step, level):
                        if rna_path_step in self.ignore_props:
                            return
                        if isinstance(value, bpy.types.PropertyGroup):
                            for sub_value_attr in value.bl_rna.properties.keys():
                                if sub_value_attr == "rna_type":
                                    continue
                                sub_value = getattr(value, sub_value_attr)
                                rna_recursive_attr_expand(sub_value, "%s.%s" % (rna_path_step, sub_value_attr), level)
                        elif type(value).__name__ == "bpy_prop_collection_idprop":  # could use nicer method
                            file_preset.write("%s.clear()\n" % rna_path_step)
                            for sub_value in value:
                                file_preset.write("item_sub_%d = %s.add()\n" % (level, rna_path_step))
                                rna_recursive_attr_expand(sub_value, "item_sub_%d" % level, level + 1)
                        else:
                            # convert thin wrapped sequences
                            # to simple lists to repr()
                            try:
                                value = value[:]
                            except:
                                pass

                            file_preset.write("%s = %r\n" % (rna_path_step, value))

                    file_preset = open(filepath, "w", encoding="utf-8")
                    file_preset.write("import bpy\n")

                    if hasattr(self, "preset_defines"):
                        for rna_path in self.preset_defines:
                            exec(rna_path)
                            file_preset.write("%s\n" % rna_path)
                        file_preset.write("\n")
                    file_preset.write("bpy.context.material.f3d_update_flag = True\n")

                    for rna_path in self.preset_values:
                        value = eval(rna_path)
                        rna_recursive_attr_expand(value, rna_path, 1)

                    file_preset.write("bpy.context.material.f3d_update_flag = False\n")
                    file_preset.write(
                        "f3d_mat.use_default_lighting = f3d_mat.use_default_lighting # Force nodes update\n"
                    )
                    file_preset.close()

            presetName = bpy.path.display_name(filename)
            preset_menu_class.bl_label = presetName

            for otherMat in bpy.data.materials:
                if otherMat.f3d_mat.presetName == presetName and otherMat != context.material:
                    update_preset_manual_v4(otherMat, filename)
            context.material.f3d_mat.presetName = bpy.path.display_name(filename)

        else:
            if self.remove_active:
                name = preset_menu_class.bl_label
                filename = self.as_filename(name)
                presetName = bpy.path.display_name(filename)

                if filename in material_presets or filename == "custom":
                    self.report({"WARNING"}, "Unable to delete/overwrite default presets.")
                    return {"CANCELLED"}

            # fairly sloppy but convenient.
            filepath = bpy.utils.preset_find(name, self.preset_subdir, ext=ext)

            if not filepath:
                filepath = bpy.utils.preset_find(name, self.preset_subdir, display_name=True, ext=ext)

            if not filepath:
                return {"CANCELLED"}

            # Do not remove bundled presets
            if is_path_builtin(filepath):
                self.report({"WARNING"}, "Unable to remove default presets")
                return {"CANCELLED"}

            try:
                if hasattr(self, "remove"):
                    self.remove(context, filepath)
                else:
                    os.remove(filepath)
            except Exception as e:
                self.report({"ERROR"}, "Unable to remove preset: %r" % e)
                import traceback

                traceback.print_exc()
                return {"CANCELLED"}

            # XXX, stupid!
            preset_menu_class.bl_label = "Presets"
            for material in bpy.data.materials:
                if material.f3d_mat.presetName == presetName:
                    material.f3d_mat.presetName = "Custom"

        if hasattr(self, "post_cb"):
            self.post_cb(context)

        return {"FINISHED"}


def convertToNewMat(material, oldMat):
    material.f3d_mat.presetName = oldMat.get("presetName", "Custom")

    material.f3d_mat.scale_autoprop = oldMat["scale_autoprop"]
    material.f3d_mat.uv_basis = oldMat.get("uv_basis", material.f3d_mat.uv_basis)

    # Combiners
    recursiveCopyOldPropertyGroup(oldMat["combiner1"], material.f3d_mat.combiner1)
    recursiveCopyOldPropertyGroup(oldMat["combiner2"], material.f3d_mat.combiner2)

    # Texture animation
    material.f3d_mat.menu_procAnim = oldMat.get("menu_procAnim", material.f3d_mat.menu_procAnim)
    if "UVanim" in oldMat:
        recursiveCopyOldPropertyGroup(oldMat["UVanim"], material.f3d_mat.UVanim0)
    if "UVanim_tex1" in oldMat:
        recursiveCopyOldPropertyGroup(oldMat["UVanim_tex1"], material.f3d_mat.UVanim1)

    # material textures
    material.f3d_mat.tex_scale = oldMat["tex_scale"]
    recursiveCopyOldPropertyGroup(oldMat["tex0"], material.f3d_mat.tex0)
    recursiveCopyOldPropertyGroup(oldMat["tex1"], material.f3d_mat.tex1)

    # Should Set?
    material.f3d_mat.set_prim = oldMat["set_prim"]
    material.f3d_mat.set_lights = oldMat["set_lights"]
    material.f3d_mat.set_env = oldMat["set_env"]
    material.f3d_mat.set_blend = oldMat["set_blend"]
    material.f3d_mat.set_key = oldMat["set_key"]
    material.f3d_mat.set_k0_5 = oldMat["set_k0_5"]
    material.f3d_mat.set_combiner = oldMat["set_combiner"]
    material.f3d_mat.use_default_lighting = oldMat.get("use_default_lighting", material.f3d_mat.use_default_lighting)

    # Colors
    nodes = oldMat.node_tree.nodes

    if oldMat.mat_ver == 3:
        prim = nodes["Primitive Color Output"].inputs[0].default_value
        env = nodes["Environment Color Output"].inputs[0].default_value
    else:
        prim = nodes["Primitive Color"].outputs[0].default_value
        env = nodes["Environment Color"].outputs[0].default_value

    material.f3d_mat.blend_color = oldMat.get("blend_color", material.f3d_mat.blend_color)
    material.f3d_mat.prim_color = prim
    material.f3d_mat.env_color = env
    material.f3d_mat.key_center = nodes["Chroma Key Center"].outputs[0].default_value

    # Chroma
    material.f3d_mat.key_scale = oldMat.get("key_scale", material.f3d_mat.key_scale)
    material.f3d_mat.key_width = oldMat.get("key_width", material.f3d_mat.key_width)

    # Convert
    material.f3d_mat.k0 = oldMat.get("k0", material.f3d_mat.k0)
    material.f3d_mat.k1 = oldMat.get("k1", material.f3d_mat.k1)
    material.f3d_mat.k2 = oldMat.get("k2", material.f3d_mat.k2)
    material.f3d_mat.k3 = oldMat.get("k3", material.f3d_mat.k3)
    material.f3d_mat.k4 = oldMat.get("k4", material.f3d_mat.k4)
    material.f3d_mat.k5 = oldMat.get("k5", material.f3d_mat.k5)

    # Prim
    material.f3d_mat.prim_lod_frac = oldMat.get("prim_lod_frac", material.f3d_mat.prim_lod_frac)
    material.f3d_mat.prim_lod_min = oldMat.get("prim_lod_min", material.f3d_mat.prim_lod_min)

    # lights
    material.f3d_mat.default_light_color = oldMat.get("default_light_color", material.f3d_mat.default_light_color)
    material.f3d_mat.ambient_light_color = oldMat.get("ambient_light_color", material.f3d_mat.ambient_light_color)
    material.f3d_mat.f3d_light1 = oldMat.get("f3d_light1", material.f3d_mat.f3d_light1)
    material.f3d_mat.f3d_light2 = oldMat.get("f3d_light2", material.f3d_mat.f3d_light2)
    material.f3d_mat.f3d_light3 = oldMat.get("f3d_light3", material.f3d_mat.f3d_light3)
    material.f3d_mat.f3d_light4 = oldMat.get("f3d_light4", material.f3d_mat.f3d_light4)
    material.f3d_mat.f3d_light5 = oldMat.get("f3d_light5", material.f3d_mat.f3d_light5)
    material.f3d_mat.f3d_light6 = oldMat.get("f3d_light6", material.f3d_mat.f3d_light6)
    material.f3d_mat.f3d_light7 = oldMat.get("f3d_light7", material.f3d_mat.f3d_light7)

    # Fog Properties
    material.f3d_mat.fog_color = oldMat.get("fog_color", material.f3d_mat.fog_color)
    material.f3d_mat.fog_position = oldMat.get("fog_position", material.f3d_mat.fog_position)
    material.f3d_mat.set_fog = oldMat["set_fog"]
    material.f3d_mat.use_global_fog = oldMat.get("use_global_fog", material.f3d_mat.use_global_fog)

    # geometry mode
    material.f3d_mat.menu_geo = oldMat.get("menu_geo", material.f3d_mat.menu_geo)
    material.f3d_mat.menu_upper = oldMat.get("menu_upper", material.f3d_mat.menu_upper)
    material.f3d_mat.menu_lower = oldMat.get("menu_lower", material.f3d_mat.menu_lower)
    material.f3d_mat.menu_other = oldMat.get("menu_other", material.f3d_mat.menu_other)
    material.f3d_mat.menu_lower_render = oldMat.get("menu_lower_render", material.f3d_mat.menu_lower_render)
    recursiveCopyOldPropertyGroup(oldMat["rdp_settings"], material.f3d_mat.rdp_settings)


class F3DMaterialProperty(bpy.types.PropertyGroup):
    presetName: bpy.props.StringProperty(
        name="Preset Name",
        default="Custom",
    )

    scale_autoprop: bpy.props.BoolProperty(
        name="Auto Set Scale",
        default=True,
        update=update_tex_values,
    )
    uv_basis: bpy.props.EnumProperty(
        name="UV Basis",
        default="TEXEL0",
        items=enumTexUV,
        update=update_tex_values,
    )

    # Combiners
    combiner1: bpy.props.PointerProperty(type=CombinerProperty)
    combiner2: bpy.props.PointerProperty(type=CombinerProperty)

    # Texture animation
    menu_procAnim: bpy.props.BoolProperty()
    UVanim0: bpy.props.PointerProperty(type=ProcAnimVectorProperty)
    UVanim1: bpy.props.PointerProperty(type=ProcAnimVectorProperty)

    # material textures
    tex_scale: bpy.props.FloatVectorProperty(
        min=0,
        max=1,
        size=2,
        default=(1, 1),
        step=1,
        update=update_tex_values,
    )
    tex0: bpy.props.PointerProperty(type=TextureProperty, name="tex0")
    tex1: bpy.props.PointerProperty(type=TextureProperty, name="tex1")

    # Should Set?

    set_prim: bpy.props.BoolProperty(
        default=True,
        update=update_node_values_with_preset,
    )
    set_lights: bpy.props.BoolProperty(
        default=True,
        update=update_node_values_with_preset,
    )
    set_env: bpy.props.BoolProperty(
        default=False,
        update=update_node_values_with_preset,
    )
    set_blend: bpy.props.BoolProperty(
        default=False,
        update=update_node_values_with_preset,
    )
    set_key: bpy.props.BoolProperty(
        default=True,
        update=update_node_values_with_preset,
    )
    set_k0_5: bpy.props.BoolProperty(
        default=True,
        update=update_node_values_with_preset,
    )
    set_combiner: bpy.props.BoolProperty(
        default=True,
        update=update_node_values_with_preset,
    )
    use_default_lighting: bpy.props.BoolProperty(
        default=True,
        update=update_node_values_without_preset,
    )

    # Blend Color
    blend_color: bpy.props.FloatVectorProperty(
        name="Blend Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(0, 0, 0, 1),
    )
    prim_color: bpy.props.FloatVectorProperty(
        name="Primitive Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=get_color_input_update_callback("prim_color", "Prim"),
    )
    env_color: bpy.props.FloatVectorProperty(
        name="Environment Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=get_color_input_update_callback("env_color", "Env"),
    )
    key_center: bpy.props.FloatVectorProperty(
        name="Key Center",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=update_node_values_without_preset,
    )

    # Chroma
    key_scale: bpy.props.FloatVectorProperty(
        name="Key Scale",
        min=0,
        max=1,
        step=1,
        update=update_node_values_with_preset,
    )
    key_width: bpy.props.FloatVectorProperty(
        name="Key Width",
        min=0,
        max=16,
        update=update_node_values_with_preset,
    )

    # Convert
    k0: bpy.props.FloatProperty(
        min=-1,
        max=1,
        default=175 / 255,
        step=1,
        update=update_node_values_with_preset,
    )
    k1: bpy.props.FloatProperty(
        min=-1,
        max=1,
        default=-43 / 255,
        step=1,
        update=update_node_values_with_preset,
    )
    k2: bpy.props.FloatProperty(
        min=-1,
        max=1,
        default=-89 / 255,
        step=1,
        update=update_node_values_with_preset,
    )
    k3: bpy.props.FloatProperty(
        min=-1,
        max=1,
        default=222 / 255,
        step=1,
        update=update_node_values_with_preset,
    )
    k4: bpy.props.FloatProperty(
        min=-1,
        max=1,
        default=114 / 255,
        step=1,
        update=update_node_values_with_preset,
    )
    k5: bpy.props.FloatProperty(
        min=-1,
        max=1,
        default=42 / 255,
        step=1,
        update=update_node_values_with_preset,
    )

    # Prim
    prim_lod_frac: bpy.props.FloatProperty(
        name="Prim LOD Frac",
        min=0,
        max=1,
        step=1,
        update=update_node_values_with_preset,
    )
    prim_lod_min: bpy.props.FloatProperty(
        name="Min LOD Ratio",
        min=0,
        max=1,
        step=1,
        update=update_node_values_with_preset,
    )

    # lights
    default_light_color: bpy.props.FloatVectorProperty(
        name="Default Light Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=update_light_properties,
    )
    set_ambient_from_light: bpy.props.BoolProperty(
        "Automatic Ambient Color", default=True, update=update_light_properties
    )
    ambient_light_color: bpy.props.FloatVectorProperty(
        name="Ambient Light Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(0.5, 0.5, 0.5, 1),
        update=update_light_properties,
    )
    f3d_light1: bpy.props.PointerProperty(type=bpy.types.Light, update=F3DOrganizeLights)
    f3d_light2: bpy.props.PointerProperty(type=bpy.types.Light, update=F3DOrganizeLights)
    f3d_light3: bpy.props.PointerProperty(type=bpy.types.Light, update=F3DOrganizeLights)
    f3d_light4: bpy.props.PointerProperty(type=bpy.types.Light, update=F3DOrganizeLights)
    f3d_light5: bpy.props.PointerProperty(type=bpy.types.Light, update=F3DOrganizeLights)
    f3d_light6: bpy.props.PointerProperty(type=bpy.types.Light, update=F3DOrganizeLights)
    f3d_light7: bpy.props.PointerProperty(type=bpy.types.Light, update=F3DOrganizeLights)

    # Fog Properties
    fog_color: bpy.props.FloatVectorProperty(
        name="Fog Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(0, 0, 0, 1),
        update=update_node_values_without_preset,
    )
    # TODO: (V5) dragorn421 should ask me if this is _actually_ the fog position max because this seems wrong to him
    fog_position: bpy.props.IntVectorProperty(
        name="Fog Range",
        size=2,
        min=0,
        max=0x10000,
        default=(985, 1000),
        update=update_node_values_without_preset,
    )
    set_fog: bpy.props.BoolProperty(update=update_node_values_without_preset)
    use_global_fog: bpy.props.BoolProperty(default=False, update=update_node_values_without_preset)

    # geometry mode
    menu_geo: bpy.props.BoolProperty()
    menu_upper: bpy.props.BoolProperty()
    menu_lower: bpy.props.BoolProperty()
    menu_other: bpy.props.BoolProperty()
    menu_lower_render: bpy.props.BoolProperty()
    rdp_settings: bpy.props.PointerProperty(type=RDPSettings)

    draw_layer: bpy.props.PointerProperty(type=DrawLayerProperty)
    use_large_textures: bpy.props.BoolProperty(name="Large Texture Mode")

    def key(self) -> F3DMaterialHash:
        useDefaultLighting = self.set_lights and self.use_default_lighting
        return (
            self.scale_autoprop,
            self.uv_basis,
            self.UVanim0.key(),
            self.UVanim1.key(),
            tuple([round(value, 4) for value in self.tex_scale]),
            self.tex0.key(),
            self.tex1.key(),
            self.rdp_settings.key(),
            self.draw_layer.key(),
            self.use_large_textures,
            self.use_default_lighting,
            self.set_blend,
            self.set_prim,
            self.set_env,
            self.set_key,
            self.set_k0_5,
            self.set_combiner,
            self.set_lights,
            self.set_fog,
            tuple([round(value, 4) for value in self.blend_color]) if self.set_blend else None,
            tuple([round(value, 4) for value in self.prim_color]) if self.set_prim else None,
            round(self.prim_lod_frac, 4) if self.set_prim else None,
            round(self.prim_lod_min, 4) if self.set_prim else None,
            tuple([round(value, 4) for value in self.env_color]) if self.set_env else None,
            tuple([round(value, 4) for value in self.key_center]) if self.set_key else None,
            tuple([round(value, 4) for value in self.key_scale]) if self.set_key else None,
            tuple([round(value, 4) for value in self.key_width]) if self.set_key else None,
            round(self.k0, 4) if self.set_k0_5 else None,
            round(self.k1, 4) if self.set_k0_5 else None,
            round(self.k2, 4) if self.set_k0_5 else None,
            round(self.k3, 4) if self.set_k0_5 else None,
            round(self.k4, 4) if self.set_k0_5 else None,
            round(self.k5, 4) if self.set_k0_5 else None,
            self.combiner1.key() if self.set_combiner else None,
            self.combiner2.key() if self.set_combiner else None,
            tuple([round(value, 4) for value in self.fog_color]) if self.set_fog else None,
            tuple([round(value, 4) for value in self.fog_position]) if self.set_fog else None,
            tuple([round(value, 4) for value in self.default_light_color]) if useDefaultLighting else None,
            self.set_ambient_from_light if useDefaultLighting else None,
            tuple([round(value, 4) for value in self.ambient_light_color])
            if useDefaultLighting and not self.set_ambient_from_light
            else None,
            self.f3d_light1 if not useDefaultLighting else None,
            self.f3d_light2 if not useDefaultLighting else None,
            self.f3d_light3 if not useDefaultLighting else None,
            self.f3d_light4 if not useDefaultLighting else None,
            self.f3d_light5 if not useDefaultLighting else None,
            self.f3d_light6 if not useDefaultLighting else None,
            self.f3d_light7 if not useDefaultLighting else None,
        )


class UnlinkF3DImage0(bpy.types.Operator):
    bl_idname = "image.tex0_unlink"
    bl_label = "Unlink F3D Image"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        context.material.f3d_mat.tex0.tex = None
        return {"FINISHED"}  # must return a set


class UnlinkF3DImage1(bpy.types.Operator):
    bl_idname = "image.tex1_unlink"
    bl_label = "Unlink F3D Image"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        context.material.f3d_mat.tex1.tex = None
        return {"FINISHED"}  # must return a set


class UpdateF3DNodes(bpy.types.Operator):
    bl_idname = "material.update_f3d_nodes"
    bl_label = "Update F3D Nodes"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        if context is None or not hasattr(context, "material") or context.material is None:
            self.report({"ERROR"}, "Material not found in context.")
            return {"CANCELLED"}
        if not context.material.is_f3d:
            self.report({"ERROR"}, "Material is not F3D.")
            return {"CANCELLED"}
        material = context.material

        material.f3d_update_flag = True
        try:
            update_node_values_of_material(material, context)
            material.f3d_mat.presetName = "Custom"
        except Exception as exc:
            material.f3d_update_flag = False
            raise exc
        material.f3d_update_flag = False
        return {"FINISHED"}  # must return a set


class F3DRenderSettingsPanel(bpy.types.Panel):
    bl_label = "F3D Render Settings"
    bl_idname = "OBJECT_PT_F3D_RENDER_SETTINGS_PANEL"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        layout.ui_units_x = 16
        renderSettings = context.scene.fast64.renderSettings

        globalSettingsBox = layout.box()
        labelbox = globalSettingsBox.box()
        labelbox.label(text="Global Settings")
        labelbox.ui_units_x = 6

        globalSettingsBox.prop(renderSettings, "enableFogPreview")
        prop_split(globalSettingsBox, renderSettings, "fogPreviewColor", "Fog Color")
        prop_split(globalSettingsBox, renderSettings, "fogPreviewPosition", "Fog Position")
        prop_split(globalSettingsBox, renderSettings, "clippingPlanes", "Clipping Planes")

        globalSettingsBox.separator(factor=0.125)
        # TODO: (v5) add headings
        prop_split(globalSettingsBox, renderSettings, "ambientColor", "Ambient Light")
        prop_split(globalSettingsBox, renderSettings, "lightColor", "Light Color")
        prop_split(globalSettingsBox, renderSettings, "lightDirection", "Light Direction")
        prop_split(globalSettingsBox, renderSettings, "useWorldSpaceLighting", "Use World Space Lighting")

        if context.scene.gameEditorMode in ["SM64", "OOT"]:
            layout.separator(factor=0.5)
            gameSettingsBox = layout.box()
            gameSettingsBox.label(text="Preview Context")

            match context.scene.gameEditorMode:
                case "SM64":
                    if renderSettings.sm64Area is not None:
                        gameSettingsBox.prop(renderSettings, "useObjectRenderPreview", text="Use Area for Preview")

                    gameSettingsBox.prop(renderSettings, "sm64Area")

                case "OOT":
                    if renderSettings.ootSceneObject is not None:
                        gameSettingsBox.prop(renderSettings, "useObjectRenderPreview", text="Use Scene for Preview")

                    gameSettingsBox.prop(renderSettings, "ootSceneObject")

                    if renderSettings.ootSceneObject is not None:
                        b = gameSettingsBox.column()
                        r = b.row().split(factor=0.4)
                        r.prop(renderSettings, "ootSceneHeader")
                        header = ootGetSceneOrRoomHeader(
                            renderSettings.ootSceneObject,
                            renderSettings.ootSceneHeader,
                            False,
                        )
                        if header is None:
                            r.label(text="Header does not exist.", icon="QUESTION")
                        else:
                            numLightsNeeded = 1
                            if header.skyboxLighting == "Custom":
                                r2 = b.row()
                                r2.prop(renderSettings, "ootForceTimeOfDay")
                                if renderSettings.ootForceTimeOfDay:
                                    r2.label(text="Light Index sets first of four lights.", icon="INFO")
                                    numLightsNeeded = 4
                            if header.skyboxLighting != "0x00":
                                r.prop(renderSettings, "ootLightIdx")
                                if renderSettings.ootLightIdx + numLightsNeeded > len(header.lightList):
                                    b.label(text="Light does not exist.", icon="QUESTION")
                            if header.skyboxLighting == "0x00" or (
                                header.skyboxLighting == "Custom" and renderSettings.ootForceTimeOfDay
                            ):
                                r.prop(renderSettings, "ootTime")
                case _:
                    pass


def draw_f3d_render_settings(self, context):
    layout: bpy.types.UILayout = self.layout
    layout.popover(F3DRenderSettingsPanel.bl_idname)


mat_classes = (
    UnlinkF3DImage0,
    UnlinkF3DImage1,
    DrawLayerProperty,
    MATERIAL_MT_f3d_presets,
    AddPresetF3D,
    F3DPanel,
    CreateFast3DMaterial,
    TextureFieldProperty,
    SetTileSizeScrollProperty,
    TextureProperty,
    CombinerProperty,
    ProceduralAnimProperty,
    ProcAnimVectorProperty,
    PrimDepthSettings,
    RDPSettings,
    DefaultRDPSettingsPanel,
    F3DMaterialProperty,
    ReloadDefaultF3DPresets,
    UpdateF3DNodes,
    F3DRenderSettingsPanel,
)


def findF3DPresetPath(filename):
    try:
        presetPath = bpy.utils.user_resource("SCRIPTS", os.path.join("presets", "f3d"), create=True)
    except:  # 3.0
        presetPath = bpy.utils.user_resource("SCRIPTS", path=os.path.join("presets", "f3d"), create=True)
    for subdir in os.listdir(presetPath):
        subPath = os.path.join(presetPath, subdir)
        if os.path.isdir(subPath):
            for preset in os.listdir(subPath):
                if preset[:-3] == filename:
                    return os.path.join(subPath, filename) + ".py"
    raise PluginError("Preset " + str(filename) + " not found.")


def getF3DPresetPath(filename, subdir):
    try:
        presetPath = bpy.utils.user_resource("SCRIPTS", os.path.join("presets", subdir), create=True)
    except:  # 3.0
        presetPath = bpy.utils.user_resource("SCRIPTS", path=os.path.join("presets", subdir), create=True)
    return os.path.join(presetPath, filename) + ".py"


def savePresets():
    for subdir, presets in material_presets.items():
        for filename, preset in presets.items():
            filepath = getF3DPresetPath(filename, "f3d/" + subdir)
            file_preset = open(filepath, "w", encoding="utf-8")
            file_preset.write(preset)
            file_preset.close()


def mat_register():
    for cls in mat_classes:
        register_class(cls)

    savePresets()

    bpy.types.Scene.f3d_type = bpy.props.EnumProperty(
        name="F3D Microcode",
        items=enumF3D,
        default="F3D",
    )
    bpy.types.Scene.isHWv1 = bpy.props.BoolProperty(name="Is Hardware v1?")

    # RDP Defaults
    bpy.types.World.rdp_defaults = bpy.props.PointerProperty(type=RDPSettings)
    bpy.types.World.menu_geo = bpy.props.BoolProperty()
    bpy.types.World.menu_upper = bpy.props.BoolProperty()
    bpy.types.World.menu_lower = bpy.props.BoolProperty()
    bpy.types.World.menu_other = bpy.props.BoolProperty()
    bpy.types.World.menu_layers = bpy.props.BoolProperty()

    bpy.types.Material.is_f3d = bpy.props.BoolProperty()
    bpy.types.Material.mat_ver = bpy.props.IntProperty(default=1)
    bpy.types.Material.f3d_update_flag = bpy.props.BoolProperty()
    bpy.types.Material.f3d_mat = bpy.props.PointerProperty(type=F3DMaterialProperty)
    bpy.types.Material.menu_tab = bpy.props.EnumProperty(items=enumF3DMenu)

    bpy.types.Scene.f3dUserPresetsOnly = bpy.props.BoolProperty(name="User Presets Only")
    bpy.types.Scene.f3d_simple = bpy.props.BoolProperty(name="Display Simple", default=True)

    bpy.types.Object.use_f3d_culling = bpy.props.BoolProperty(
        name="Enable Culling (Applies to F3DEX and up)",
        default=True,
    )
    bpy.types.Object.ignore_render = bpy.props.BoolProperty(name="Ignore Render")
    bpy.types.Object.ignore_collision = bpy.props.BoolProperty(name="Ignore Collision")
    bpy.types.Object.f3d_lod_z = bpy.props.IntProperty(
        name="F3D LOD Z",
        min=1,
        default=10,
    )
    bpy.types.Object.f3d_lod_always_render_farthest = bpy.props.BoolProperty(name="Always Render Farthest LOD")

    bpy.types.VIEW3D_HT_header.append(draw_f3d_render_settings)


def mat_unregister():
    bpy.types.VIEW3D_HT_header.remove(draw_f3d_render_settings)

    del bpy.types.Material.menu_tab
    del bpy.types.Material.f3d_mat
    del bpy.types.Material.is_f3d
    del bpy.types.Material.mat_ver
    del bpy.types.Material.f3d_update_flag
    del bpy.types.Scene.f3d_simple
    del bpy.types.Object.ignore_render
    del bpy.types.Object.ignore_collision
    del bpy.types.Object.use_f3d_culling
    del bpy.types.Scene.f3dUserPresetsOnly
    del bpy.types.Object.f3d_lod_z
    del bpy.types.Object.f3d_lod_always_render_farthest

    for cls in reversed(mat_classes):
        unregister_class(cls)


# WARNING: Adding new presets will break any custom presets added afterward.

enumMaterialPresets = [
    ("Custom", "Custom", "Custom"),
    ("Unlit Texture", "Unlit Texture", "Unlit Texture"),
    ("Unlit Texture Cutout", "Unlit Texture Cutout", "Unlit Texture Cutout"),
    ("Shaded Solid", "Shaded Solid", "Shaded Solid"),
    ("Decal On Shaded Solid", "Decal On Shaded Solid", "Decal On Shaded Solid"),
    ("Shaded Texture", "Shaded Texture", "Shaded Texture"),
    ("Shaded Texture Cutout", "Shaded Texture Cutout", "Shaded Texture Cutout"),
    (
        "Shaded Texture Transparent",
        "Shaded Texture Transparent (Prim Alpha)",
        "Shaded Texture Transparent (Prim Alpha)",
    ),
    ("Vertex Colored Texture", "Vertex Colored Texture", "Vertex Colored Texture"),
    ("Environment Mapped", "Environment Mapped", "Environment Mapped"),
    ("Fog Shaded Texture", "Fog Shaded Texture", "Fog Shaded Texture"),
    ("Fog Shaded Texture Cutout", "Fog Shaded Texture Cutout", "Fog Shaded Texture Cutout"),
    (
        "Fog Shaded Texture Transparent",
        "Fog Shaded Texture Transparent (Prim Alpha)",
        "Fog Shaded Texture Transparent (Prim Alpha)",
    ),
    ("Vertex Colored Texture Transparent", "Vertex Colored Texture Transparent", "Vertex Colored Texture Transparent"),
    ("Shaded Noise", "Shaded Noise", "Shaded Noise"),
    (
        "Vertex Colored Texture (No Vertex Alpha)",
        "Vertex Colored Texture (No Vertex Alpha)",
        "Vertex Colored Texture (No Vertex Alpha)",
    ),
]
