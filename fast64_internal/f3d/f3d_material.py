import logging
import bpy, math, os
from bpy.types import (
    Attribute,
    Context,
    Event,
    Image,
    Light,
    Material,
    Menu,
    Mesh,
    NodeGroupOutput,
    NodeInputs,
    NodeLink,
    NodeSocket,
    NodeTree,
    Object,
    Operator,
    Panel,
    Property,
    PropertyGroup,
    Scene,
    ShaderNodeGroup,
    TextureNodeImage,
    UILayout,
    VIEW3D_HT_header,
    World,
)
from bl_operators.presets import AddPresetBase
from bpy.utils import register_class, unregister_class
from mathutils import Color

from .f3d_enums import *
from .f3d_gbi import (
    get_F3D_GBI,
    enumTexScroll,
    isUcodeF3DEX1,
    isUcodeF3DEX3,
    is_ucode_f3d,
    is_ucode_t3d,
    default_draw_layers,
)
from .f3d_material_presets import *
from ..utility import *
from ..render_settings import (
    Fast64RenderSettings_Properties,
    update_scene_props_from_render_settings,
    ManualUpdatePreviewOperator,
)
from .f3d_material_helpers import F3DMaterial_UpdateLock, node_tree_copy
from bpy.app.handlers import persistent
from typing import Generator, Optional, Tuple, Any, Dict, Union

F3D_MAT_CUR_VERSION = 6  # Increment this when changing the nodes

F3DMaterialHash = Any  # giant tuple

logging.basicConfig(format="%(asctime)s: %(message)s", datefmt="%m/%d/%Y %I:%M:%S %p")
logger = logging.getLogger(__name__)

bitSizeDict = {
    "G_IM_SIZ_4b": 4,
    "G_IM_SIZ_8b": 8,
    "G_IM_SIZ_16b": 16,
    "G_IM_SIZ_32b": 32,
}

texBitSizeF3D = {
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


def menu_items_enum(_self, context):
    items = ["Combiner", "Sources"]
    if len(geo_modes_in_ucode(context.scene.f3d_type)) > 1:
        items.append("Geo")
    items.extend(["Upper", "Lower"])
    return [(item, item, item) for item in items]


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

F3D_GEO_MODES = {
    "zBuffer": "g_zbuffer",
    "shade": "g_shade",
    "cullFront": "g_cull_front",
    "cullBack": "g_cull_back",
    "fog": "g_fog",
    "lighting": "g_lighting",
    "texGen": "g_tex_gen",
    "texGenLinear": "g_tex_gen_linear",
    "lod": "g_lod",
    "shadeSmooth": "g_shade_smooth",
}

F3DLX_GEO_MODES = {
    "clipping": "g_clipping",
}

F3DEX3_GEO_MODES = {
    "ambientOcclusion": "g_ambocclusion",
    "attroffsetZ": "g_attroffset_z_enable",
    "attroffsetST": "g_attroffset_st_enable",
    "packedNormals": "g_packed_normals",
    "lightToAlpha": "g_lighttoalpha",
    "specularLighting": "g_lighting_specular",
    "fresnelToColor": "g_fresnel_color",
    "fresnelToAlpha": "g_fresnel_alpha",
}


T3D_GEO_MODES = {
    "cullFront": "g_cull_front",
    "cullBack": "g_cull_back",
    "fog": "g_fog",
    "texGen": "g_tex_gen",
}


def geo_modes_in_ucode(UCODE_VER: str):
    geo_modes = {}
    if is_ucode_f3d(UCODE_VER):
        geo_modes.update(F3D_GEO_MODES)
        if isUcodeF3DEX1(UCODE_VER):
            geo_modes.update(F3DLX_GEO_MODES)
        if isUcodeF3DEX3(UCODE_VER):
            geo_modes.update(F3DEX3_GEO_MODES)
    if is_ucode_t3d(UCODE_VER):
        geo_modes.update(T3D_GEO_MODES)
    return geo_modes


def sources_in_ucode(UCODE_VER: str):
    sources = ["Primitive", "Environment", "Key", "Convert", "Fog"]
    if not is_ucode_t3d(UCODE_VER) or is_ucode_f3d(UCODE_VER):
        sources.extend(["Lighting", "Clip Ratio"])
    if isUcodeF3DEX3(UCODE_VER):
        sources.extend(["AO", "Fresnel", "ST Attr Offset", "Z Attr Offset"])
    return sources


def inherit_light_and_fog():
    return is_ucode_t3d(bpy.context.scene.f3d_type)


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


def get_world_layer_defaults(scene, game_mode: str, layer: str):
    world = scene.world
    if world is None:
        return default_draw_layers.get(game_mode, {}).get(layer, ("", ""))
    if game_mode == "SM64":
        return (
            getattr(world, f"draw_layer_{layer}_cycle_1", ""),
            getattr(world, f"draw_layer_{layer}_cycle_2", ""),
        )
    elif game_mode == "OOT":
        return (
            getattr(world.ootDefaultRenderModes, f"{layer.lower()}Cycle1", ""),
            getattr(world.ootDefaultRenderModes, f"{layer.lower()}Cycle2", ""),
        )
    else:
        assert (
            False
        ), f"game_mode={game_mode} has no draw layer defaults, this function should not have been called at all with it"


def rendermode_preset_to_advanced(material: bpy.types.Material):
    """
    Set all individual controls for the rendermode from the preset rendermode.
    """
    scene = bpy.context.scene
    f3d_mat = material.f3d_mat
    settings = f3d_mat.rdp_settings
    f3d = get_F3D_GBI()

    if settings.rendermode_advanced_enabled and settings.set_rendermode:
        # Rendermode is being set by the material and in advanced mode, don't overwrite any settings
        return

    cycle_1, cycle_2 = settings.rendermode_preset_cycle_1, settings.rendermode_preset_cycle_2
    if not settings.set_rendermode:
        game_mode = scene.gameEditorMode
        layer = getattr(f3d_mat.draw_layer, game_mode.lower(), None)
        if layer is None:  # Game mode has no layer, don´t change anything
            return

        possible_cycle_1, possible_cycle_2 = get_world_layer_defaults(scene, game_mode, layer)
        if getattr(f3d, possible_cycle_1, None) is not None and getattr(f3d, possible_cycle_2, None) is not None:
            cycle_1, cycle_2 = possible_cycle_1, possible_cycle_2

            # Some presets are not implemented in the blender enum, so print a warning and turn on advanced
            try:
                settings.rendermode_preset_cycle_1, settings.rendermode_preset_cycle_2 = cycle_1, cycle_2
                settings.rendermode_advanced_enabled = False
            except TypeError as exc:
                print(
                    f"Render mode presets {cycle_1} or {cycle_2} probably not included in render mode preset enum:\n{exc}",
                )
                settings.rendermode_advanced_enabled = True

    def get_with_default(preset, default):
        # Use the material's settings even if we are not setting rendermode.
        # This allows the user to enable setting rendermode, set it up as they
        # want, then disable it, and have it still previewed that way.
        return getattr(f3d, preset, default)

    is_two_cycle = settings.g_mdsft_cycletype == "G_CYC_2CYCLE"
    if is_two_cycle:
        r1 = get_with_default(cycle_1, f3d.G_RM_FOG_SHADE_A)
        r2 = get_with_default(cycle_2, f3d.G_RM_AA_ZB_OPA_SURF2)
        r = r1 | r2
    else:
        r = get_with_default(cycle_1, f3d.G_RM_AA_ZB_OPA_SURF)
        r1 = r
        # The cycle 1 bits are copied to the cycle 2 bits at export if in 1-cycle mode
        # (the hardware requires them to be the same). So, here we also move the cycle 1
        # bits to the cycle 2 slots. r2 is only read for the cycle dependent settings below.
        r2 = r >> 2

    # cycle independent
    settings.aa_en = (r & f3d.AA_EN) != 0
    settings.z_cmp = (r & f3d.Z_CMP) != 0
    settings.z_upd = (r & f3d.Z_UPD) != 0
    settings.im_rd = (r & f3d.IM_RD) != 0
    settings.clr_on_cvg = (r & f3d.CLR_ON_CVG) != 0
    settings.cvg_dst = f3d.cvgDstDict[r & f3d.CVG_DST_SAVE]
    settings.zmode = f3d.zmodeDict[r & f3d.ZMODE_DEC]
    settings.cvg_x_alpha = (r & f3d.CVG_X_ALPHA) != 0
    settings.alpha_cvg_sel = (r & f3d.ALPHA_CVG_SEL) != 0
    settings.force_bl = (r & f3d.FORCE_BL) != 0

    # cycle dependent / lerp
    settings.blend_p1 = f3d.blendColorDict[(r1 >> 30) & 3]
    settings.blend_p2 = f3d.blendColorDict[(r2 >> 28) & 3]
    settings.blend_a1 = f3d.blendAlphaDict[(r1 >> 26) & 3]
    settings.blend_a2 = f3d.blendAlphaDict[(r2 >> 24) & 3]
    settings.blend_m1 = f3d.blendColorDict[(r1 >> 22) & 3]
    settings.blend_m2 = f3d.blendColorDict[(r2 >> 20) & 3]
    settings.blend_b1 = f3d.blendMixDict[(r1 >> 18) & 3]
    settings.blend_b2 = f3d.blendMixDict[(r2 >> 16) & 3]


def does_blender_use_mix(settings: "RDPSettings", mix: str, default_for_no_rendermode: bool = False) -> bool:
    if not settings.set_rendermode:
        return default_for_no_rendermode
    is_two_cycle = settings.g_mdsft_cycletype == "G_CYC_2CYCLE"
    return settings.blend_b1 == mix or (is_two_cycle and settings.blend_b2 == mix)


def is_blender_equation_equal(settings: "RDPSettings", cycle: int, p: str, a: str, m: str, b: str) -> bool:
    assert cycle in {1, 2, -1}  # -1 = last cycle
    if cycle == -1:
        cycle = 2 if settings.g_mdsft_cycletype == "G_CYC_2CYCLE" else 1
    return (
        getattr(settings, f"blend_p{cycle}") == p
        and getattr(settings, f"blend_a{cycle}") == a
        and getattr(settings, f"blend_m{cycle}") == m
        and getattr(settings, f"blend_b{cycle}") == b
    )


def is_blender_doing_fog(settings: "RDPSettings") -> bool:
    return is_blender_equation_equal(
        settings,
        # If 2 cycle, fog must be in first cycle.
        1,
        "G_BL_CLR_FOG",
        "G_BL_A_SHADE",
        # While technically it being fog only requires that P and A be fog color
        # and shade alpha, the only reasonable choice for M and B in this case
        # is color in and 1-A.
        "G_BL_CLR_IN",
        "G_BL_1MA",
    )


def get_output_method(material: bpy.types.Material) -> str:
    rendermode_preset_to_advanced(material)  # Make sure advanced settings are updated
    settings = material.f3d_mat.rdp_settings
    if settings.cvg_x_alpha:
        return "CLIP"
    if settings.force_bl and is_blender_equation_equal(
        settings, -1, "G_BL_CLR_IN", "G_BL_A_IN", "G_BL_CLR_MEM", "G_BL_1MA"
    ):
        return "XLU"
    return "OPA"


def update_blend_method(material: Material, context):
    blend_mode = get_output_method(material)
    if material.f3d_mat.rdp_settings.zmode == "ZMODE_DEC":
        blend_mode = "DECAL"
    if bpy.app.version >= (4, 2, 0):
        if blend_mode == "CLIP":
            material.surface_render_method = "DITHERED"
        else:
            material.surface_render_method = "BLENDED"
    elif blend_mode == "OPA":
        material.blend_method = "OPAQUE"
    elif blend_mode == "CLIP":
        material.blend_method = "CLIP"
    elif blend_mode in {"XLU", "DECAL"}:
        material.blend_method = "BLEND"


class DrawLayerProperty(PropertyGroup):
    sm64: bpy.props.EnumProperty(items=sm64EnumDrawLayers, default="1", update=update_draw_layer)
    oot: bpy.props.EnumProperty(items=ootEnumDrawLayers, default="Opaque", update=update_draw_layer)

    def key(self):
        return (self.sm64, self.oot)


def getTmemWordUsage(texFormat, width, height):
    texelsPerWord = 64 // texBitSizeInt[texFormat]
    return (width + texelsPerWord - 1) // texelsPerWord * height


def getTmemMax(texFormat):
    return 4096 if texFormat[:2] != "CI" else 2048


# Necessary for UV half pixel offset (see 13.7.5.3)
def isTexturePointSampled(material):
    f3dMat = material.f3d_mat
    return f3dMat.rdp_settings.g_mdsft_text_filt == "G_TF_POINT"


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


def combiner_uses(
    f3dMat: "F3DMaterialProperty",
    checkList,
    checkCycle1=True,
    checkCycle2=True,
    checkColor=True,
    checkAlpha=True,
    swapTexelsCycle2=True,
):
    is_two_cycle = f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"
    for i in range(1, 3):
        if i == 1 and not checkCycle1 or i == 2 and (not checkCycle2 or not is_two_cycle):
            continue
        combiner = getattr(f3dMat, f"combiner{i}")
        for isAlpha in [False, True]:
            if not isAlpha and not checkColor or isAlpha and not checkAlpha:
                continue
            for letter in ["A", "B", "C", "D"]:
                value = getattr(combiner, letter + ("_alpha" if isAlpha else ""))
                if i == 2 and swapTexelsCycle2 and value.startswith("TEXEL"):
                    value = "TEXEL" + chr(ord(value[5]) ^ 1)  # Swap 0 and 1
                if value in checkList:
                    return True
    return False


def combiner_uses_tex0(f3d_mat: "F3DMaterialProperty"):
    return combiner_uses(f3d_mat, ["TEXEL0", "TEXEL0_ALPHA"])


def combiner_uses_tex1(f3d_mat: "F3DMaterialProperty"):
    return combiner_uses(f3d_mat, ["TEXEL1", "TEXEL1_ALPHA"])


def all_combiner_uses(f3d_mat: "F3DMaterialProperty") -> dict[str, bool]:
    use_tex0 = combiner_uses_tex0(f3d_mat)
    use_tex1 = combiner_uses_tex1(f3d_mat)

    useDict = {
        "Texture": use_tex0 or use_tex1,
        "Texture 0": use_tex0,
        "Texture 1": use_tex1,
        "Primitive": combiner_uses(
            f3d_mat,
            ["PRIMITIVE", "PRIMITIVE_ALPHA", "PRIM_LOD_FRAC"],
        ),
        "Environment": combiner_uses(f3d_mat, ["ENVIRONMENT", "ENV_ALPHA"]),
        "Shade": combiner_uses(f3d_mat, ["SHADE"], checkAlpha=False),
        "Shade Alpha": combiner_uses(f3d_mat, ["SHADE"], checkColor=False)
        or combiner_uses(f3d_mat, ["SHADE_ALPHA"], checkAlpha=False),
        "Key": combiner_uses(f3d_mat, ["CENTER", "SCALE"]),
        "LOD Fraction": combiner_uses(f3d_mat, ["LOD_FRACTION"]),
        "Convert": combiner_uses(f3d_mat, ["K4", "K5"]),
    }
    return useDict


def ui_geo_mode(settings, dataHolder, layout, useDropdown):
    f3d = get_F3D_GBI()
    inputGroup = layout.column()
    if useDropdown:
        inputGroup.prop(
            dataHolder,
            "menu_geo",
            text="Geometry Mode Settings",
            icon="TRIA_DOWN" if dataHolder.menu_geo else "TRIA_RIGHT",
        )
    if not useDropdown or dataHolder.menu_geo:
        disable_dependent = False  # Don't disable dependent props in world defaults

        def should_draw(*props):
            return any(settings.has_prop_in_ucode(prop) for prop in props)

        def is_on(*props):
            return all(settings.is_geo_mode_on(prop) for prop in props)

        def draw_mode(layout: UILayout, *props):
            failed = False
            for prop in props:
                if settings.has_prop_in_ucode(prop):
                    layout.prop(settings, prop)
                else:
                    failed = True
            return not failed

        def indentGroup(parent: UILayout, textOrProp: Union[str, "F3DMaterialProperty"], isText: bool) -> UILayout:
            if not isText and not should_draw(textOrProp):
                return parent.column(align=True)
            c = parent.column(align=True)
            if isText:
                c.label(text=textOrProp)
                enable = True
            else:
                c.prop(settings, textOrProp)
                enable = getattr(settings, textOrProp)
            c = c.split(factor=0.1)
            c.label(text="")
            c = c.column(align=True)
            c.enabled = enable or not disable_dependent
            return c

        ccWarnings = shadeInCC = False
        blendWarnings = shadeInBlender = zInBlender = False
        if isinstance(dataHolder, F3DMaterialProperty):
            ccWarnings = True
            ccUse = all_combiner_uses(dataHolder)
            shadeInCC = ccUse["Shade"] or ccUse["Shade Alpha"]
            disable_dependent = True
            if settings.set_rendermode:
                blendWarnings = True
                shadeInBlender = settings.does_blender_use_input("G_BL_A_SHADE")
                zInBlender = settings.z_cmp or settings.z_upd

        draw_mode(inputGroup, "g_shade_smooth")

        c = indentGroup(inputGroup, "g_lighting", False)
        if ccWarnings and not shadeInCC and is_on("g_lighting") and not is_on("g_tex_gen"):
            multilineLabel(c, "Shade not used in CC, can disable\nlighting.", icon="INFO")
        draw_mode(c, "g_packed_normals", "g_lighting_specular", "g_ambocclusion", "g_fresnel_color")
        if should_draw("g_tex_gen_linear"):
            d = indentGroup(c, "g_tex_gen", False)
        else:
            draw_mode(c, "g_tex_gen")
            d = c
        draw_mode(d, "g_tex_gen_linear")

        if is_ucode_t3d(f3d.F3D_VER):
            shadeColorLabel = "Lighting * vertex color"
        if is_on("g_fresnel_color"):
            shadeColorLabel = "Fresnel"
        elif not is_on("g_lighting") or is_on("g_lighttoalpha"):
            shadeColorLabel = "Vertex color"
        elif is_on("g_lighting") and is_on("g_packed_normals") and not is_on("g_lighttoalpha"):
            shadeColorLabel = "Lighting * vertex color"
        else:
            shadeColorLabel = "Lighting"

        inputGroup.column().label(text=f"Shade color = {shadeColorLabel}")

        draw_mode(inputGroup, "g_fog")
        shadowMapInShadeAlpha = False
        if is_on("g_fog"):
            shadeAlphaLabel = "Fog"
        elif is_on("g_lighting", "g_fresnel_alpha"):
            shadeAlphaLabel = "Fresnel"
        elif is_on("g_lighting", "g_lighttoalpha"):
            shadeAlphaLabel = "Light intensity"
        elif is_on("g_lighting", "g_ambocclusion"):
            shadeAlphaLabel = "Shadow map / AO in vtx alpha"
            shadowMapInShadeAlpha = True
        else:
            shadeAlphaLabel = "Vtx alpha"

        warnings, errors = [], []
        if is_on("g_lighting", "g_fog", "g_fresnel_alpha"):
            errors.append("Fog overrides Fresnel Alpha.")
        if is_on("g_lighting", "g_fog", "g_lighttoalpha"):
            errors.append("Fog overrides Light-to-Alpha.")
        if is_on("g_lighting", "g_fresnel_alpha", "g_lighttoalpha"):
            errors.append("Fresnel Alpha overrides Light-to-Alpha.")
        if shadowMapInShadeAlpha and ccWarnings and ccUse["Shade Alpha"]:
            warnings.append("Shadow map = shade alpha used in CC, probably wrong.")
        if is_on("g_fog") and ccWarnings and ccUse["Shade Alpha"]:
            warnings.append("Fog = shade alpha used in CC, probably wrong.")
        if blendWarnings and shadeInBlender and not is_on("g_fog"):
            warnings.append("Rendermode uses shade alpha, probably fog.")
        elif blendWarnings and not shadeInBlender and is_on("g_fog"):
            warnings.append("Fog not used in rendermode / blender, can disable.")

        if should_draw("g_lighttoalpha", "g_fresnel_alpha") or warnings or errors:
            c = indentGroup(inputGroup, f"Shade alpha = {shadeAlphaLabel}:", True)
            draw_mode(c, "g_lighttoalpha", "g_fresnel_alpha")
            if warnings:
                multilineLabel(c, "\n".join(warnings), "INFO")
            if errors:
                multilineLabel(c, "\n".join(errors), "ERROR")
        else:
            inputGroup.column().label(text=f"Shade alpha = {shadeAlphaLabel}")

        if should_draw("g_attroffset_st_enable", "g_attroffset_z_enable"):
            indentGroup(inputGroup, "Attribute offsets:", True)
            draw_mode(inputGroup, "g_attroffset_st_enable", "g_attroffset_z_enable")

        if should_draw("g_cull_front", "g_cull_back"):
            c = indentGroup(inputGroup, "Face culling:", True)
            draw_mode(c, "g_cull_front", "g_cull_back")
            if is_on("g_cull_front", "g_cull_back"):
                c.label(text="Nothing will be drawn.", icon="ERROR")

        if should_draw("g_zbuffer", "g_shade"):
            c = indentGroup(inputGroup, "Disable if not using:", True)
            draw_mode(c, "g_zbuffer", "g_shade")
            if blendWarnings and not is_on("g_zbuffer") and zInBlender:
                c.label(text="Rendermode / blender using Z, must enable.", icon="ERROR")
            elif blendWarnings and is_on("g_zbuffer") and not zInBlender:
                c.label(text="Z is not being used, can disable.", icon="INFO")
            if ccWarnings and not is_on("g_shade") and (shadeInCC or shadeInBlender):
                if shadeInCC and shadeInBlender:
                    where = "CC and blender"
                elif shadeInCC:
                    where = "CC"
                else:
                    where = "rendermode / blender"
                c.label(text=f"Shade in use in {where}, must enable.", icon="ERROR")
            elif ccWarnings and is_on("g_shade") and not shadeInCC and not shadeInBlender:
                c.label(text="Shade is not being used, can disable.", icon="INFO")

        if should_draw("g_lod", "g_clipping"):
            c = indentGroup(inputGroup, "Not useful:", True)
            draw_mode(c, "g_lod", "g_clipping")


def ui_upper_mode(settings, dataHolder, layout: UILayout, useDropdown):
    inputGroup: UILayout = layout.column()
    if useDropdown:
        inputGroup.prop(
            dataHolder,
            "menu_upper",
            text="Other Mode Upper Settings",
            icon="TRIA_DOWN" if dataHolder.menu_upper else "TRIA_RIGHT",
        )
    if not useDropdown or dataHolder.menu_upper:
        prop_split(inputGroup, settings, "g_mdsft_alpha_dither", "Alpha Dither")
        prop_split(inputGroup, settings, "g_mdsft_rgb_dither", "RGB Dither")
        prop_split(inputGroup, settings, "g_mdsft_combkey", "Chroma Key")
        prop_split(inputGroup, settings, "g_mdsft_textconv", "Texture Convert")
        prop_split(inputGroup, settings, "g_mdsft_text_filt", "Texture Filter")
        textlut_col = inputGroup.column()
        tlut_mode = get_textlut_mode(dataHolder, True) if isinstance(dataHolder, F3DMaterialProperty) else None
        if tlut_mode:
            textlut_col.enabled = False
            split = textlut_col.split(factor=0.5)
            split.label(text="Texture LUT (Auto)")
            box = split.box()
            box.label(text={"G_TT_NONE": "None"}.get(tlut_mode, tlut_mode.lstrip("G_TT_")))
            box.scale_y = 0.5
        else:
            prop_split(textlut_col, settings, "g_mdsft_textlut", "Texture LUT")
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


def ui_lower_mode(settings, dataHolder, layout: UILayout, useDropdown):
    inputGroup: UILayout = layout.column()
    if useDropdown:
        inputGroup.prop(
            dataHolder,
            "menu_lower",
            text="Other Mode Lower Settings",
            icon="TRIA_DOWN" if dataHolder.menu_lower else "TRIA_RIGHT",
        )
    if not useDropdown or dataHolder.menu_lower:
        prop_split(inputGroup, settings, "g_mdsft_alpha_compare", "Alpha Compare")
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
        if "Clip Ratio" in sources_in_ucode(bpy.context.scene.f3d_type):
            clipRatioGroup = inputGroup.column()
            prop_split(clipRatioGroup, settings, "clip_ratio", "Clip Ratio")

        if isinstance(dataHolder, Material) or isinstance(dataHolder, F3DMaterialProperty):
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
class F3DPanel(Panel):
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

    def ui_large(self, material, layout):
        layout.prop(material, "use_large_textures")
        if material.use_large_textures:
            inputGroup = layout.row().split(factor=0.5)
            inputGroup.label(text="Large texture edges:")
            inputGroup.prop(material, "large_edges", text="")

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
        f3d_mat = material.f3d_mat
        if showCheckBox:
            prop_input_name.prop(f3d_mat, setName, text="Chroma Key")
        else:
            prop_input_name.label(text="Chroma Key")
        prop_input.prop(f3d_mat, "key_center", text="Center")
        prop_input.prop(f3d_mat, "key_scale", text="Scale")
        prop_input.prop(f3d_mat, "key_width", text="Width")
        if f3d_mat.key_width[0] > 1 or f3d_mat.key_width[1] > 1 or f3d_mat.key_width[2] > 1:
            layout.box().label(text="NOTE: Keying is disabled for channels with width > 1.")
        prop_input.enabled = setProp
        return inputGroup

    def ui_lights(self, f3d_mat: "F3DMaterialProperty", layout: UILayout, name, showCheckBox):
        if inherit_light_and_fog():
            return
        inputGroup = layout.row()
        prop_input_left = inputGroup.column()
        prop_input = inputGroup.column()
        if showCheckBox:
            prop_input_left.prop(f3d_mat, "set_lights", text=name)
        else:
            prop_input_left.label(text=name)

        settings = f3d_mat.rdp_settings
        prop_input_left.enabled = settings.is_geo_mode_on("g_lighting") and settings.is_geo_mode_on("g_shade")
        lightSettings: UILayout = prop_input.column()
        if settings.is_geo_mode_on("g_lighting"):
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
        is_two_cycle = material.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"
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
                f3d = get_F3D_GBI()
                prop_split(renderGroup, material.rdp_settings, "rendermode_preset_cycle_1", "Render Mode")
                no_flags_1 = material.rdp_settings.rendermode_preset_cycle_1 in f3d.rendermodePresetsWithoutFlags
                if is_two_cycle:
                    prop_split(renderGroup, material.rdp_settings, "rendermode_preset_cycle_2", "Render Mode Cycle 2")
                    no_flags_2 = material.rdp_settings.rendermode_preset_cycle_2 in f3d.rendermodePresetsWithoutFlags
                    if no_flags_1 and no_flags_2:
                        multilineLabel(
                            renderGroup.box(),
                            "Invalid combination of rendermode presets.\n"
                            + "Neither of these presets sets the rendermode flags.",
                            "ERROR",
                        )
                    elif not no_flags_1 and not no_flags_2:
                        multilineLabel(
                            renderGroup.box(),
                            "Invalid combination of rendermode presets.\n"
                            + "Both of these presets set the rendermode flags.",
                            "ERROR",
                        )
                else:
                    if no_flags_1:
                        multilineLabel(
                            renderGroup.box(),
                            "Invalid rendermode preset in 1-cycle.\n"
                            + "This preset does not set the rendermode flags.",
                            "ERROR",
                        )
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

                if is_two_cycle:
                    combinerBox2 = renderGroup.box()
                    combinerBox2.label(text="Blender Cycle 2")
                    combinerCol2 = combinerBox2.row()
                    rowColor2 = combinerCol2.column()
                    rowAlpha2 = combinerCol2.column()
                    rowColor2.prop(material.rdp_settings, "blend_p2", text="P")
                    rowColor2.prop(material.rdp_settings, "blend_m2", text="M")
                    rowAlpha2.prop(material.rdp_settings, "blend_a2", text="A")
                    rowAlpha2.prop(material.rdp_settings, "blend_b2", text="B")

            if is_two_cycle:
                if (
                    material.rdp_settings.blend_b1 == "G_BL_A_MEM"
                    or material.rdp_settings.blend_p1 == "G_BL_CLR_MEM"
                    or material.rdp_settings.blend_m1 == "G_BL_CLR_MEM"
                ):
                    multilineLabel(
                        renderGroup.box(),
                        "RDP silicon bug: Framebuffer color / alpha in blender\n"
                        + "cycle 1 is broken, actually value from PREVIOUS pixel.",
                        "ORPHAN_DATA",
                    )
                if material.rdp_settings.blend_a2 == "G_BL_A_SHADE":
                    multilineLabel(
                        renderGroup.box(),
                        "RDP silicon bug: Shade alpha in blender cycle 2\n"
                        + "is broken, actually shade alpha from NEXT pixel.",
                        "ORPHAN_DATA",
                    )

            renderGroup.enabled = material.rdp_settings.set_rendermode

    def ui_uvCheck(self, layout, context):
        if hasattr(context, "object") and context.object is not None and isinstance(context.object.data, Mesh):
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

    def ui_misc(self, f3dMat: "F3DMaterialProperty", inputCol: UILayout, showCheckBox: bool) -> None:
        sources = sources_in_ucode(bpy.context.scene.f3d_type)
        if "AO" in sources and f3dMat.rdp_settings.g_ambocclusion:
            if showCheckBox or f3dMat.set_ao:
                inputGroup = inputCol.column()
            if showCheckBox:
                inputGroup.prop(f3dMat, "set_ao", text="Set Ambient Occlusion")
            if f3dMat.set_ao:
                prop_split(inputGroup.row(), f3dMat, "ao_ambient", "AO Ambient")
                prop_split(inputGroup.row(), f3dMat, "ao_directional", "AO Directional")
                prop_split(inputGroup.row(), f3dMat, "ao_point", "AO Point")

        if "Fresnel" in sources and f3dMat.rdp_settings.g_fresnel_color or f3dMat.rdp_settings.g_fresnel_alpha:
            if showCheckBox or f3dMat.set_fresnel:
                inputGroup = inputCol.column()
            if showCheckBox:
                inputGroup.prop(f3dMat, "set_fresnel", text="Set Fresnel")
            if f3dMat.set_fresnel:
                prop_split(inputGroup.row(), f3dMat, "fresnel_lo", "Fresnel Lo")
                prop_split(inputGroup.row(), f3dMat, "fresnel_hi", "Fresnel Hi")

        if "ST Attr Offset" in sources and f3dMat.rdp_settings.g_attroffset_st_enable:
            if showCheckBox or f3dMat.set_attroffs_st:
                inputGroup = inputCol.column()
            if showCheckBox:
                inputGroup.prop(f3dMat, "set_attroffs_st", text="Set ST Attr Offset")
            if f3dMat.set_attroffs_st:
                prop_split(inputGroup.row(), f3dMat, "attroffs_st", "ST Attr Offset")

        if "Z Attr Offset" in sources and f3dMat.rdp_settings.g_attroffset_z_enable:
            if showCheckBox or f3dMat.set_attroffs_z:
                inputGroup = inputCol.column()
            if showCheckBox:
                inputGroup.prop(f3dMat, "set_attroffs_z", text="Set Z Attr Offset")
            if f3dMat.set_attroffs_z:
                prop_split(inputGroup.row(), f3dMat, "attroffs_z", "Z Attr Offset")

        if "Fog" in sources and f3dMat.rdp_settings.using_fog and not inherit_light_and_fog():
            if showCheckBox or f3dMat.set_fog:
                inputGroup = inputCol.column()
            if showCheckBox:
                inputGroup.prop(f3dMat, "set_fog", text="Set Fog")
            if f3dMat.set_fog:
                draw_fog = True
                if bpy.context.scene.gameEditorMode == "SM64":
                    obj, area_obj = bpy.context.object.parent, None
                    while obj:
                        if obj.type == "EMPTY" and obj.sm64_obj_type == "Area Root" and obj.fast64.sm64.area.set_fog:
                            area_obj = obj
                            break
                        obj = obj.parent
                    if area_obj:
                        inputGroup.prop(f3dMat, "use_global_fog", text=f'Use Area "{area_obj.name}"\'s Fog')
                        if f3dMat.use_global_fog:
                            settings_col = inputGroup.column()
                            settings_col.enabled = not f3dMat.use_global_fog
                            prop_split(settings_col.row(), area_obj, "area_fog_color", "Fog Color")
                            prop_split(settings_col.row(), area_obj, "area_fog_position", "Fog Range")
                            draw_fog = False
                    else:
                        # show setting for preview
                        inputGroup.prop(f3dMat, "use_global_fog", text="Use Area's Fog")
                        inputGroup.label(
                            text="Preview only in this context, no area fog settings to pick up", icon="INFO"
                        )
                if draw_fog:
                    prop_split(inputGroup.row(), f3dMat, "fog_color", "Fog Color")
                    prop_split(inputGroup.row(), f3dMat, "fog_position", "Fog Range")

    def ui_cel_shading(self, material: Material, layout: UILayout):
        inputGroup = layout.box().column()
        r = inputGroup.row(align=True)
        r.prop(
            material.f3d_mat,
            "expand_cel_shading_ui",
            text="",
            icon="TRIA_DOWN" if material.f3d_mat.expand_cel_shading_ui else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        r.prop(material.f3d_mat, "use_cel_shading")
        if not material.f3d_mat.expand_cel_shading_ui:
            return
        if not material.f3d_mat.use_cel_shading:
            inputGroup = inputGroup.column()
            inputGroup.enabled = False
        cel = material.f3d_mat.cel_shading
        prop_split(inputGroup.row(), cel, "tintPipeline", "Tint pipeline:")
        prop_split(inputGroup.row(), cel, "cutoutSource", "Cutout:")

        if material.f3d_mat.rdp_settings.zmode != "ZMODE_OPA":
            inputGroup.label(text="zmode in blender / rendermode must be opaque.", icon="ERROR")

        if cel.cutoutSource == "ENVIRONMENT":
            if not material.f3d_mat.set_env or material.f3d_mat.env_color[3] != 1.0:
                inputGroup.label(text="Enable env color, and set env alpha to 255.", icon="ERROR")
        else:
            tex = material.f3d_mat.tex0 if cel.cutoutSource == "TEXEL0" else material.f3d_mat.tex1
            if tex.tex is None or not tex.tex_set:
                inputGroup.label(text=f"Texture {cel.cutoutSource[5]} is not set up correctly.", icon="ERROR")

        if (
            len(cel.levels) >= 3
            and cel.levels[0].threshMode == cel.levels[1].threshMode
            and not all([cel.levels[0].threshMode == lvl.threshMode for lvl in cel.levels[1:]])
        ):
            multilineLabel(
                inputGroup.box(),
                "If using both lighter and darker cel\n" + "levels, one of each must be at the beginning",
                "ERROR",
            )

        r = inputGroup.row(align=True)
        r.label(text="Cel levels:")
        op = r.operator(CelLevelAdd.bl_idname, text="", icon="ADD")
        op.materialName = material.name
        if len(cel.levels) > 0:
            op = r.operator(CelLevelRemove.bl_idname, text="", icon="REMOVE")
            op.materialName = material.name

        showSegHelp = False
        for level in cel.levels:
            box = inputGroup.box().column()
            r = box.row().split(factor=0.2)
            r.label(text="Draw when")
            r = r.split(factor=0.3)
            r.prop(level, "threshMode", text="")
            r = r.split(factor=0.2)
            r.label(text="than")
            r.prop(level, "threshold")
            r = box.row().split(factor=0.08)
            r.label(text="Tint:")
            r = r.split(factor=0.27)
            r.prop(level, "tintType", text="")
            r = r.split(factor=0.45)
            if level.tintType == "Fixed":
                r.prop(level, "tintFixedLevel")
                r = r.split(factor=0.3)
                r.label(text="Color:")
                r.prop(level, "tintFixedColor", text="")
            elif level.tintType == "Segment":
                r.prop(level, "tintSegmentNum")
                r.prop(level, "tintSegmentOffset")
                showSegHelp = True
            elif level.tintType == "Light":
                r.prop(level, "tintFixedLevel")
                r.prop(level, "tintLightSlot")
            else:
                raise PluginError("Invalid tintType")
        if showSegHelp:
            tintName, tintNameCap = ("prim", "Prim") if cel.tintPipeline == "CC" else ("fog", "Fog")
            multilineLabel(
                inputGroup,
                "Segments: In your code, set up DL in segment(s) used with\n"
                + f"gsDPSet{tintNameCap}Color then gsSPEndDisplayList at appropriate offset\n"
                + f"with {tintName} color = tint color and {tintName} alpha = tint level.",
                "INFO",
            )

    def checkDrawLayersWarnings(self, f3dMat: "F3DMaterialProperty", useDict: Dict[str, bool], layout: UILayout):
        settings = f3dMat.rdp_settings
        f3d_type = bpy.context.scene.f3d_type
        anyUseShadeAlpha = useDict["Shade Alpha"] or settings.does_blender_use_input("G_BL_A_SHADE")

        g_lighting = settings.is_geo_mode_on("g_lighting") or is_ucode_t3d(f3d_type)
        g_fog = settings.is_geo_mode_on("g_fog")
        g_packed_normals = settings.is_geo_mode_on("g_packed_normals") or is_ucode_t3d(f3d_type)
        g_ambocclusion = settings.is_geo_mode_on("g_ambocclusion")
        g_lighttoalpha = settings.is_geo_mode_on("g_lighttoalpha")
        g_fresnel_color = settings.is_geo_mode_on("g_fresnel_color")
        g_fresnel_alpha = settings.is_geo_mode_on("g_fresnel_alpha")

        usesVertexColor = useDict["Shade"] and (not g_lighting or (g_packed_normals and not g_fresnel_color))
        usesVertexAlpha = anyUseShadeAlpha and (g_ambocclusion or not (g_fog or g_lighttoalpha or g_fresnel_alpha))
        if not usesVertexColor and not usesVertexAlpha:
            return
        noticeBox = layout.box().column()
        if not usesVertexColor:
            noticeBox.label(text='Mesh must have Color Attribute (vtx color) layer called "Alpha".', icon="IMAGE_ALPHA")
        elif not usesVertexAlpha:
            noticeBox.label(
                text='Mesh must have Color Attribute (vtx color) layer called "Col".', icon="IMAGE_RGB_ALPHA"
            )
        else:
            noticeBox.label(text="Mesh must have two Color Attribute (vtx color) layers.", icon="IMAGE_RGB_ALPHA")
            noticeBox.label(text='They must be called "Col" and "Alpha".', icon="IMAGE_ALPHA")

    def checkDrawMixedCIWarning(self, layout, useDict, f3dMat):
        useTex0 = useDict["Texture 0"] and f3dMat.tex0.tex_set
        useTex1 = useDict["Texture 1"] and f3dMat.tex1.tex_set
        if not useTex0 or not useTex1:
            return
        isTex0CI = f3dMat.tex0.tex_format[:2] == "CI"
        isTex1CI = f3dMat.tex1.tex_format[:2] == "CI"
        if isTex0CI != isTex1CI:
            layout.box().column().label(text="Can't have one CI tex and one non-CI.", icon="ERROR")
        if isTex0CI and isTex1CI and (f3dMat.tex0.ci_format != f3dMat.tex1.ci_format):
            layout.box().column().label(text="Two CI textures must use the same CI format.", icon="ERROR")

    def draw_simple(self, f3dMat, material, layout, context):
        f3d = get_F3D_GBI()
        self.ui_uvCheck(layout, context)

        inputCol = layout.column()
        useDict = all_combiner_uses(f3dMat)

        self.checkDrawLayersWarnings(f3dMat, useDict, layout)

        useMultitexture = useDict["Texture 0"] and useDict["Texture 1"] and f3dMat.tex0.tex_set and f3dMat.tex1.tex_set

        self.checkDrawMixedCIWarning(inputCol, useDict, f3dMat)
        canUseLargeTextures = material.mat_ver > 3 and material.f3d_mat.use_large_textures
        if useDict["Texture 0"] and f3dMat.tex0.tex_set:
            ui_image(canUseLargeTextures, inputCol, material, f3dMat.tex0, "Texture 0", False)

        if useDict["Texture 1"] and f3dMat.tex1.tex_set:
            ui_image(canUseLargeTextures, inputCol, material, f3dMat.tex1, "Texture 1", False)

        if useMultitexture:
            inputCol.prop(f3dMat, "uv_basis", text="UV Basis")

        if useDict["Texture"]:
            self.ui_large(f3dMat, inputCol)
            self.ui_scale(f3dMat, inputCol)

        if useDict["Primitive"] and f3dMat.set_prim:
            self.ui_prim(material, inputCol, "set_prim", f3dMat.set_prim, False)

        if useDict["Environment"] and f3dMat.set_env:
            self.ui_env(material, inputCol, False)

        showLightProperty = (
            f3dMat.set_lights
            and "Lighting" in sources_in_ucode(bpy.context.scene.f3d_type)
            and f3dMat.rdp_settings.is_geo_mode_on("g_lighting")
            and f3dMat.rdp_settings.is_geo_mode_on("g_shade")
        )
        if useDict["Shade"] and showLightProperty:
            self.ui_lights(f3dMat, inputCol, "Lighting", False)

        if useDict["Key"] and f3dMat.set_key:
            self.ui_chroma(material, inputCol, "Chroma Key Center", "set_key", f3dMat.set_key, False)

        if useDict["Convert"] and f3dMat.set_k0_5:
            self.ui_convert(f3dMat, inputCol, False)

        self.ui_misc(f3dMat, inputCol, False)

    def draw_full(self, f3dMat, material, layout: UILayout, context):
        layout.row().prop(material, "menu_tab", expand=True)
        menuTab = material.menu_tab
        useDict = all_combiner_uses(f3dMat)
        f3d = get_F3D_GBI()

        if menuTab == "Combiner":
            self.ui_draw_layer(material, layout, context)

            self.checkDrawLayersWarnings(f3dMat, useDict, layout)

            def drawCCProps(ui: UILayout, combiner: "CombinerProperty", isAlpha: bool, enabled: bool = True) -> None:
                ui = ui.column()
                ui.enabled = enabled
                for letter in ["A", "B", "C", "D"]:
                    r = ui.row().split(factor=0.25 if isAlpha else 0.1)
                    r.label(text=f"{letter}{' Alpha' if isAlpha else ''}:")
                    r.prop(combiner, f"{letter}{'_alpha' if isAlpha else ''}", text="")

            is_two_cycle = f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE"

            combinerBox = layout.box()
            combinerBox.prop(f3dMat, "set_combiner", text="Color Combiner (Color = (A - B) * C + D)")
            combinerCol = combinerBox.row().split(factor=0.45)
            combinerCol.enabled = f3dMat.set_combiner
            drawCCProps(combinerCol, f3dMat.combiner1, False)
            drawCCProps(combinerCol, f3dMat.combiner1, True, not f3dMat.use_cel_shading)
            if f3dMat.use_cel_shading:
                r = combinerBox.column().label(
                    text=f"CC alpha{' cycle 1' if is_two_cycle else ''} is occupied by cel shading."
                )

            if is_two_cycle:
                combinerBox2 = layout.box()
                combinerBox2.label(text="Color Combiner Cycle 2")
                combinerBox2.enabled = f3dMat.set_combiner
                combinerCol2 = combinerBox2.row().split(factor=0.45)
                drawCCProps(combinerCol2, f3dMat.combiner2, False)
                drawCCProps(combinerCol2, f3dMat.combiner2, True)

                if combiner_uses(f3dMat, ["TEXEL0", "TEXEL0_ALPHA"], checkCycle1=False, swapTexelsCycle2=False):
                    combinerBox2.label(text="'Texture 0' in Cycle 2 is actually Texture 1.", icon="INFO")
                if combiner_uses(f3dMat, ["TEXEL1", "TEXEL1_ALPHA"], checkCycle1=False, swapTexelsCycle2=False):
                    multilineLabel(
                        combinerBox2,
                        "RDP silicon bug: 'Texture 1' in Cycle 2 is actually\n"
                        + "Texture 0 for the NEXT pixel, causes visual issues.",
                        "ORPHAN_DATA",
                    )

        if menuTab == "Sources":
            self.ui_uvCheck(layout, context)

            inputCol = layout.column()

            useMultitexture = useDict["Texture 0"] and useDict["Texture 1"]

            self.checkDrawMixedCIWarning(inputCol, useDict, f3dMat)
            canUseLargeTextures = material.mat_ver > 3 and material.f3d_mat.use_large_textures
            if useDict["Texture 0"]:
                ui_image(canUseLargeTextures, inputCol, material, f3dMat.tex0, "Texture 0", True)

            if useDict["Texture 1"]:
                ui_image(canUseLargeTextures, inputCol, material, f3dMat.tex1, "Texture 1", True)

            if useMultitexture:
                inputCol.prop(f3dMat, "uv_basis", text="UV Basis")

            if useDict["Texture"]:
                self.ui_large(f3dMat, inputCol)
                self.ui_scale(f3dMat, inputCol)

            if useDict["Primitive"]:
                self.ui_prim(material, inputCol, "set_prim", f3dMat.set_prim, True)

            if useDict["Environment"]:
                self.ui_env(material, inputCol, True)

            if useDict["Shade"] and "Lighting" in sources_in_ucode(bpy.context.scene.f3d_type):
                self.ui_lights(f3dMat, inputCol, "Lighting", True)

            if useDict["Key"]:
                self.ui_chroma(material, inputCol, "Chroma Key Center", "set_key", f3dMat.set_key, True)

            if useDict["Convert"]:
                self.ui_convert(f3dMat, inputCol, True)

            self.ui_misc(f3dMat, inputCol, True)

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
        settings = f3dMat.rdp_settings
        layout.prop(context.scene, "f3d_simple", text="Show Simplified UI")
        layout = layout.box()
        titleCol = layout.column()
        titleCol.box().label(text="F3D Material Inspector")

        if material.mat_ver < 5:
            box = layout.box().column()
            box.label(
                text=f"Material version is outdated (V{material.mat_ver})",
                icon="ORPHAN_DATA",
            )
            box.operator("object.convert_f3d_update")
            return

        presetCol = layout.column()
        split = presetCol.split(factor=0.33)
        split.label(text="Preset")
        row = split.row(align=True)
        row.menu(MATERIAL_MT_f3d_presets.__name__, text=f3dMat.presetName)
        row.operator(AddPresetF3D.bl_idname, text="", icon="ADD")
        row.operator(AddPresetF3D.bl_idname, text="", icon="REMOVE").remove_active = True

        if settings.g_mdsft_alpha_compare == "G_AC_THRESHOLD" and settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
            multilineLabel(
                layout.box(),
                "RDP silicon bug: Alpha compare in 2-cycle mode is broken.\n"
                + "Compares to FIRST cycle CC alpha output from NEXT pixel.",
                "ORPHAN_DATA",
            )

        if context.scene.f3d_simple and f3dMat.presetName != "Custom":
            self.draw_simple(f3dMat, material, layout, context)
        else:
            presetCol.prop(context.scene, "f3dUserPresetsOnly")
            self.draw_full(f3dMat, material, layout, context)

        if context.scene.f3d_type == "F3DEX3":
            self.ui_cel_shading(material, layout)
        else:
            r = layout.row()
            r.enabled = False
            r.label(text="Use Cel Shading (requires F3DEX3)", icon="TRIA_RIGHT")

        layout.operator(RecreateF3DNodes.bl_idname)


class F3DMeshPanel(Panel):
    bl_label = "F3D Mesh Inspector"
    bl_idname = "F3D_PT_Mesh_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.object.type == "MESH"

    def draw(self, context):
        new_gbi = not get_F3D_GBI().F3D_OLD_GBI
        col = self.layout.box().column()
        col.box().label(text=self.bl_label, icon="MESH_DATA")
        row = col.row()
        row.enabled = new_gbi
        row.prop(context.object, "use_f3d_culling")
        if not new_gbi:
            col.label(text="Only available in F3DEX and up", icon="INFO")


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
    if hasattr(context.scene, "world") and self == create_or_get_world(context.scene).rdp_defaults:
        pass

    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        update_node_values_of_material(material, context)
        if update_preset:
            material.f3d_mat.presetName = "Custom"


def update_all_node_values(material, context):
    update_node_values_without_preset(material, context)
    update_tex_values_manual(material, context)
    update_rendermode_preset(material, context)


def update_all_material_nodes(self, context):
    for material in bpy.data.materials:
        if material.is_f3d and material.mat_ver >= F3D_MAT_CUR_VERSION:
            with context.temp_override(material=material):
                update_all_node_values(material, context)


def update_world_default_rendermode(self, context):
    for material in bpy.data.materials:
        if material.is_f3d and material.mat_ver >= F3D_MAT_CUR_VERSION:
            with context.temp_override(material=material):
                update_rendermode_preset(material, context)


def update_node_values_with_preset(self, context):
    update_node_values(self, context, update_preset=True)


def update_node_values_without_preset(self, context):
    update_node_values(self, context, update_preset=False)


def update_light_properties(self, context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        update_light_colors(material, context)


def update_cel_cutout_source(self, context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return
        if not material.f3d_mat.use_cel_shading:
            return

        f3dMat = material.f3d_mat
        cel = f3dMat.cel_shading
        firstDarker = len(cel.levels) >= 1 and cel.levels[0].threshMode == "Darker"

        f3dMat.combiner1.A_alpha, f3dMat.combiner1.B_alpha = ("1", "SHADE") if firstDarker else ("SHADE", "0")
        f3dMat.combiner1.C_alpha = cel.cutoutSource
        f3dMat.combiner1.D_alpha = "0"


def update_rendermode_preset(self, context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if material:
            rendermode_preset_to_advanced(material)

    update_node_values_with_preset(self, context)


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


def remove_first_link_if_exists(material: Material, links: tuple[NodeLink]):
    if len(links) > 0:
        link = links[0]
        material.node_tree.links.remove(link)


def link_if_none_exist(
    material: Material, fromOutput: NodeSocket, toInput: NodeSocket
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


def update_fog_nodes(material: Material, context: Context):
    nodes = material.node_tree.nodes
    f3dMat: "F3DMaterialProperty" = material.f3d_mat

    fogBlender: ShaderNodeGroup = nodes["FogBlender"]
    # if NOT setting rendermode, it is more likely that the user is setting
    # rendermodes in code, so to be safe we'll enable fog. Plus we are checking
    # that fog is enabled in the geometry mode, so if so that's probably the intent.
    fogBlender.node_tree = bpy.data.node_groups[
        ("FogBlender_On" if is_blender_doing_fog(material.f3d_mat.rdp_settings) else "FogBlender_Off")
    ]

    remove_first_link_if_exists(material, fogBlender.inputs["FogAmount"].links)
    if material.f3d_mat.rdp_settings.g_fog:
        material.node_tree.links.new(nodes["CalcFog"].outputs["FogAmount"], fogBlender.inputs["FogAmount"])
    else:  # If fog is not being calculated, pass in shade alpha
        material.node_tree.links.new(nodes["Shade Color"].outputs["Alpha"], fogBlender.inputs["FogAmount"])

    if (
        (bpy.context.scene.gameEditorMode == "SM64" and f3dMat.use_global_fog)
        or not f3dMat.set_fog
        or inherit_light_and_fog()
    ):  # Inherit fog
        link_if_none_exist(material, nodes["SceneProperties"].outputs["FogColor"], nodes["FogColor"].inputs[0])
        link_if_none_exist(material, nodes["GlobalFogColor"].outputs[0], fogBlender.inputs["Fog Color"])
        link_if_none_exist(material, nodes["SceneProperties"].outputs["FogNear"], nodes["CalcFog"].inputs["FogNear"])
        link_if_none_exist(material, nodes["SceneProperties"].outputs["FogFar"], nodes["CalcFog"].inputs["FogFar"])
    else:
        remove_first_link_if_exists(material, nodes["FogBlender"].inputs["Fog Color"].links)
        remove_first_link_if_exists(material, nodes["CalcFog"].inputs["FogNear"].links)
        remove_first_link_if_exists(material, nodes["CalcFog"].inputs["FogFar"].links)
        fogBlender.inputs["Fog Color"].default_value = s_rgb_alpha_1_tuple(f3dMat.fog_color)
        nodes["CalcFog"].inputs["FogNear"].default_value = f3dMat.fog_position[0]
        nodes["CalcFog"].inputs["FogFar"].default_value = f3dMat.fog_position[1]


def update_noise_nodes(material: Material):
    f3dMat: "F3DMaterialProperty" = material.f3d_mat
    uses_noise = f3dMat.combiner1.A == "NOISE" or f3dMat.combiner2.A == "NOISE"
    noise_group = bpy.data.node_groups["F3DNoise_Animated" if uses_noise else "F3DNoise_NonAnimated"]

    nodes = material.node_tree.nodes
    if nodes["F3DNoiseFactor"].node_tree is not noise_group:
        nodes["F3DNoiseFactor"].node_tree = noise_group


def update_combiner_connections(material: Material, context: Context, combiner: int | None = None):
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


def set_output_node_groups(material: Material):
    nodes = material.node_tree.nodes
    output_node = nodes["OUTPUT"]
    f3dMat: "F3DMaterialProperty" = material.f3d_mat
    cycle = f3dMat.rdp_settings.g_mdsft_cycletype.lstrip("G_CYC_").rstrip("_CYCLE")
    output_method = get_output_method(material)
    if bpy.app.version < (4, 2, 0) and output_method == "CLIP":
        output_method = "XLU"
        material.alpha_threshold = 0.125

    output_group_name = f"OUTPUT_{cycle}CYCLE_{output_method}"
    output_group = bpy.data.node_groups[output_group_name]
    output_node.node_tree = output_group

    for inp in output_node.inputs:
        remove_first_link_if_exists(material, inp.links)
    output_node.inputs["Cycle_C_1"].default_value = (0.0, 0.0, 0.0, 1.0)
    output_node.inputs["Cycle_A_1"].default_value = 0.5
    output_node.inputs["Cycle_C_2"].default_value = (0.0, 0.0, 0.0, 1.0)
    output_node.inputs["Cycle_A_2"].default_value = 0.5
    if output_method == "CLIP":
        output_node.inputs["Alpha Threshold"].default_value = 0.125
    material.node_tree.links.new(nodes["Cycle_1"].outputs["Color"], output_node.inputs["Cycle_C_1"])
    material.node_tree.links.new(nodes["Cycle_1"].outputs["Alpha"], output_node.inputs["Cycle_A_1"])
    material.node_tree.links.new(nodes["FogBlender"].outputs["Color"], output_node.inputs["Cycle_C_2"])
    material.node_tree.links.new(nodes["Cycle_2"].outputs["Alpha"], output_node.inputs["Cycle_A_2"])
    material.node_tree.links.new(output_node.outputs[0], nodes["Material Output F3D"].inputs[0])


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

    if f3dMat.set_lights or inherit_light_and_fog():
        remove_first_link_if_exists(material, nodes["Shade Color"].inputs["AmbientColor"].links)
        remove_first_link_if_exists(material, nodes["Shade Color"].inputs["Light0Color"].links)
        remove_first_link_if_exists(material, nodes["Shade Color"].inputs["Light1Color"].links)

        # TODO: feature to toggle gamma correction
        light0 = f3dMat.default_light_color
        light1 = [0.0, 0.0, 0.0, 1.0]
        if not f3dMat.use_default_lighting:
            light0 = f3dMat.f3d_light1.color if f3dMat.f3d_light1 is not None else [1.0, 1.0, 1.0, 1.0]
            light1 = f3dMat.f3d_light2.color if f3dMat.f3d_light2 is not None else light1

        nodes["Shade Color"].inputs["AmbientColor"].default_value = s_rgb_alpha_1_tuple(f3dMat.ambient_light_color)
        nodes["Shade Color"].inputs["Light0Color"].default_value = s_rgb_alpha_1_tuple(light0)
        nodes["Shade Color"].inputs["Light1Color"].default_value = s_rgb_alpha_1_tuple(light1)
    else:
        nodes["Shade Color"].inputs["AmbientColor"].default_value = (0.5, 0.5, 0.5, 1.0)
        nodes["Shade Color"].inputs["Light0Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        nodes["Shade Color"].inputs["Light1Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        link_if_none_exist(material, nodes["AmbientColorOut"].outputs[0], nodes["Shade Color"].inputs["AmbientColor"])
        link_if_none_exist(material, nodes["Light0ColorOut"].outputs[0], nodes["Shade Color"].inputs["Light0Color"])
        link_if_none_exist(material, nodes["Light1ColorOut"].outputs[0], nodes["Shade Color"].inputs["Light1Color"])


def update_color_node(combiner_inputs, color: Color, prefix: str):
    """Function for updating either Prim or Env colors"""
    # TODO: feature to toggle gamma correction
    combiner_inputs[f"{prefix} Color"].default_value = s_rgb_alpha_1_tuple(color)
    combiner_inputs[f"{prefix} Alpha"].default_value = color[3]


# prim_color | Prim
# env_color | Env
def get_color_input_update_callback(attr_name="", prefix=""):
    def input_update_callback(self: Material, context: Context):
        with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
            if not material:
                return
            f3dMat: "F3DMaterialProperty" = material.f3d_mat
            nodes = material.node_tree.nodes
            combiner_inputs = nodes["CombinerInputs"].inputs
            update_color_node(combiner_inputs, getattr(f3dMat, attr_name), prefix)

    return input_update_callback


def update_node_values_of_material(material: Material, context):
    check_or_ask_color_management(context)

    update_blend_method(material, context)
    if not has_f3d_nodes(material):
        return

    f3dMat: "F3DMaterialProperty" = material.f3d_mat
    settings: RDPSettings = f3dMat.rdp_settings

    update_combiner_connections(material, context)

    set_output_node_groups(material)

    nodes = material.node_tree.nodes

    if (settings.is_geo_mode_on("g_lighting") or inherit_light_and_fog()) and settings.is_geo_mode_on("g_tex_gen"):
        if settings.is_geo_mode_on("g_tex_gen_linear"):
            nodes["UV"].node_tree = bpy.data.node_groups["UV_EnvMap_Linear"]
        else:
            nodes["UV"].node_tree = bpy.data.node_groups["UV_EnvMap"]
    else:
        nodes["UV"].node_tree = bpy.data.node_groups["UV"]

    shdcol_inputs = nodes["Shade Color"].inputs
    for propName in [
        "g_ambocclusion",
        "g_packed_normals",
        "g_lighttoalpha",
        "g_lighting_specular",
        "g_fresnel_color",
        "g_fresnel_alpha",
        "g_fog",
        "g_lighting",
    ]:
        shdcol_inputs[propName.upper()].default_value = f3dMat.rdp_settings.is_geo_mode_on(propName)
    if is_ucode_t3d(bpy.context.scene.f3d_type):  # Tiny3d always uses lighting * vertex color
        shdcol_inputs["G_LIGHTING"].default_value = shdcol_inputs["G_PACKED_NORMALS"].default_value = True

    shdcol_inputs["AO Ambient"].default_value = f3dMat.ao_ambient
    shdcol_inputs["AO Directional"].default_value = f3dMat.ao_directional
    shdcol_inputs["AO Point"].default_value = f3dMat.ao_point
    shdcol_inputs["Fresnel Lo"].default_value = f3dMat.fresnel_lo
    shdcol_inputs["Fresnel Hi"].default_value = f3dMat.fresnel_hi

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
    update_fog_nodes(material, context)


def set_texture_settings_node(material: Material):
    nodes = material.node_tree.nodes
    textureSettings: ShaderNodeGroup = nodes["TextureSettings"]

    desired_group = bpy.data.node_groups["TextureSettings_Lite"]
    if (material.f3d_mat.tex0.tex and not material.f3d_mat.tex0.autoprop) or (
        material.f3d_mat.tex1.tex and not material.f3d_mat.tex1.autoprop
    ):
        desired_group = bpy.data.node_groups["TextureSettings_Advanced"]
    if textureSettings.node_tree is not desired_group:
        textureSettings.node_tree = desired_group


def setAutoProp(fieldProperty, pixelLength):
    fieldProperty.mask = log2iRoundUp(pixelLength)
    fieldProperty.shift = 0
    fieldProperty.low = 0
    fieldProperty.high = pixelLength
    if fieldProperty.clamp and fieldProperty.mirror:
        fieldProperty.high *= 2
    fieldProperty.high -= 1


def set_texture_size(self, tex_size, tex_index):
    nodes = self.node_tree.nodes
    uv_basis: ShaderNodeGroup = nodes["UV Basis"]
    inputs = uv_basis.inputs

    inputs[f"{tex_index} S TexSize"].default_value = tex_size[0]
    inputs[f"{tex_index} T TexSize"].default_value = tex_size[1]


def trunc_10_2(val: float):
    return int(val * 4) / 4


def update_tex_values_field(self: Material, texProperty: "TextureProperty", tex_size: list[int], tex_index: int):
    nodes = self.node_tree.nodes
    textureSettings: ShaderNodeGroup = nodes["TextureSettings"]
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


def iter_tex_nodes(node_tree: NodeTree, texIndex: int) -> Generator[TextureNodeImage, None, None]:
    for i in range(1, 5):
        nodeName = f"Tex{texIndex}_{i}"
        if node_tree.nodes.get(nodeName):
            yield node_tree.nodes[nodeName]


def toggle_texture_node_muting(material: Material, texIndex: int, isUsed: bool):
    node_tree = material.node_tree
    f3dMat: "F3DMaterialProperty" = material.f3d_mat

    # Enforce typing from generator
    texNode: None | TextureNodeImage = None

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
    material: Material, texProperty: "TextureProperty", texIndex: int, isUsed: bool
) -> list[int] | None:
    node_tree = material.node_tree
    f3dMat: "F3DMaterialProperty" = material.f3d_mat

    # Return value
    texSize: Optional[list[int]] = None

    toggle_texture_node_muting(material, texIndex, isUsed)

    if not isUsed:
        return texSize

    # Enforce typing from generator
    texNode: None | TextureNodeImage = None
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


def update_tex_values_index(self: Material, *, texProperty: "TextureProperty", texIndex: int, isUsed: bool):
    nodes = self.node_tree.nodes

    tex_size = set_texture_nodes_settings(self, texProperty, texIndex, isUsed)

    if tex_size:  # only returns tex size if a texture is being set
        if tex_size[0] > 0 and tex_size[1] > 0:
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


def get_color_info_from_tex(tex: bpy.types.Image):
    is_greyscale, has_alpha_4_bit, has_alpha_1_bit = True, False, False
    rgba_colors: set[int] = set()

    pixels, channel_count = tex.pixels, tex.channels

    for x in range(tex.size[0]):
        for y in range(tex.size[1]):  # N64 is -Y, Blender is +Y, in this context this doesn´t matter
            pixel_color = [1, 1, 1, 1]
            for field in range(channel_count):
                pixel_color[field] = pixels[(y * tex.size[0] + x) * channel_count + field]
            rgba_colors.add(getRGBA16Tuple(pixel_color))

            if not (pixel_color[0] == pixel_color[1] and pixel_color[1] == pixel_color[2]):
                is_greyscale = False

            if pixel_color[3] < 0.9375:
                has_alpha_4_bit = True
            if pixel_color[3] < 0.5:
                has_alpha_1_bit = True

    return is_greyscale, has_alpha_1_bit, has_alpha_4_bit, rgba_colors


def get_optimal_format(tex: bpy.types.Image | None, prefer_rgba_over_ci: bool):
    if not tex:
        return "RGBA16"

    n_size = tex.size[0] * tex.size[1]
    if n_size > 8192:  # Image is too big
        return "RGBA16"

    is_greyscale, has_alpha_1_bit, has_alpha_4_bit, rgba_colors = get_color_info_from_tex(tex)

    if is_greyscale:
        if n_size > 4096:
            if has_alpha_1_bit:
                return "IA4"
            return "I4"

        if has_alpha_4_bit:
            return "IA8"

        return "I8"
    else:
        if len(rgba_colors) <= 16 and (not prefer_rgba_over_ci or n_size > 2048):
            return "CI4"
        if not prefer_rgba_over_ci and len(rgba_colors) <= 256:
            return "CI8"

    return "RGBA16"


def update_tex_values_and_formats(self, context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        settings_props = context.scene.fast64.settings
        if not settings_props.auto_pick_texture_format:
            update_tex_values_manual(material, context)
            return

        f3d_mat: F3DMaterialProperty = material.f3d_mat
        useDict = all_combiner_uses(f3d_mat)
        tex0_props = f3d_mat.tex0
        tex1_props = f3d_mat.tex1

        tex0, tex1 = tex0_props.tex if useDict["Texture 0"] else None, (
            tex1_props.tex if useDict["Texture 1"] else None
        )

        if tex0:
            tex0_props.tex_format = get_optimal_format(tex0, settings_props.prefer_rgba_over_ci)
        if tex1:
            tex1_props.tex_format = get_optimal_format(tex1, settings_props.prefer_rgba_over_ci)

        if tex0 and tex1:
            if tex0_props.tex_format.startswith("CI") and not tex1_props.tex_format.startswith("CI"):
                tex0_props.tex_format = "RGBA16"
            elif tex1_props.tex_format.startswith("CI") and not tex0_props.tex_format.startswith("CI"):
                tex1_props.tex_format = "RGBA16"

        update_tex_values_manual(material, context)


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


def get_textlut_mode(f3d_mat: "F3DMaterialProperty", inherit_from_tex: bool = False):
    use_dict = all_combiner_uses(f3d_mat)
    textures = [f3d_mat.tex0] if use_dict["Texture 0"] and f3d_mat.tex0.tex_set else []
    textures += [f3d_mat.tex1] if use_dict["Texture 1"] and f3d_mat.tex1.tex_set else []
    tlut_modes = [tex.tlut_mode for tex in textures]
    if tlut_modes and tlut_modes[0] == tlut_modes[-1]:
        return tlut_modes[0]
    return None if inherit_from_tex else f3d_mat.rdp_settings.g_mdsft_textlut


def update_tex_values_manual(material: Material, context, prop_path=None):
    f3dMat: "F3DMaterialProperty" = material.f3d_mat
    nodes = material.node_tree.nodes
    texture_settings = nodes["TextureSettings"]
    texture_inputs: NodeInputs = texture_settings.inputs
    useDict = all_combiner_uses(f3dMat)

    f3dMat.rdp_settings.g_mdsft_textlut = get_textlut_mode(f3dMat)

    tex0_used = useDict["Texture 0"] and f3dMat.tex0.tex is not None
    tex1_used = useDict["Texture 1"] and f3dMat.tex1.tex is not None

    if not tex0_used and not tex1_used:
        texture_settings.mute = True
        set_texture_nodes_settings(material, f3dMat.tex0, 0, False)
        set_texture_nodes_settings(material, f3dMat.tex1, 1, False)
        return
    elif texture_settings.mute:
        texture_settings.mute = False

    # linear requires tex gen to be enabled as well
    isTexGen = f3dMat.rdp_settings.g_lighting and f3dMat.rdp_settings.g_tex_gen

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

    uv_basis: ShaderNodeGroup = nodes["UV Basis"]
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
    if preset == "Shaded Solid":
        preset = "sm64_shaded_solid"
    if preset == "Shaded Texture":
        preset = "sm64_shaded_texture"
    if preset.lower() != "custom":
        material_apply_preset(material, findF3DPresetPath(preset))


def material_apply_preset(material, filepath):
    material.f3d_update_flag = True
    with bpy.context.temp_override(material=material):
        bpy.ops.script.execute_preset(filepath=filepath, menu_idname="MATERIAL_MT_f3d_presets")

    # Since the material preset is executed under f3d_update_flag,
    # it setting the rendermode presets does not propagate to the individual
    # rendermode values.
    # So manually call the function to propagate the preset.
    # Also that function will set props, which results in the material preset name
    # being set to Custom (as if changed by the user).
    # So save the preset name and restore it after the rendermode propagation.
    savedPresetName = material.f3d_mat.presetName
    rendermode_preset_to_advanced(material)
    material.f3d_mat.presetName = savedPresetName

    material.f3d_update_flag = False


def has_f3d_nodes(material: Material):
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

    for mat in bpy.data.materials:
        if mat is not None and mat.use_nodes and mat.is_f3d:
            rendermode_preset_to_advanced(mat)


bpy.app.handlers.load_post.append(load_handler)

SCENE_PROPERTIES_VERSION = 2


def createOrUpdateSceneProperties():
    group = bpy.data.node_groups.get("SceneProperties")
    upgrade_group = bool(group and group.get("version", -1) < SCENE_PROPERTIES_VERSION)

    if group and not upgrade_group:
        # Group is ready and up to date
        return

    if upgrade_group and group:
        # Need to upgrade; remove old outputs
        if bpy.app.version >= (4, 0, 0):
            for item in group.interface.items_tree:
                if item.item_type == "SOCKET" and item.in_out == "OUTPUT":
                    group.interface.remove(item)
        else:
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
    if bpy.app.version >= (4, 0, 0):
        tree_interface = new_group.interface

        _nodeFogEnable: NodeSocketFloat = tree_interface.new_socket(
            "FogEnable", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeFogColor: NodeSocketColor = tree_interface.new_socket(
            "FogColor", socket_type="NodeSocketColor", in_out="OUTPUT"
        )
        _nodeF3D_NearClip: NodeSocketFloat = tree_interface.new_socket(
            "F3D_NearClip", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeF3D_FarClip: NodeSocketFloat = tree_interface.new_socket(
            "F3D_FarClip", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeBlender_Game_Scale: NodeSocketFloat = tree_interface.new_socket(
            "Blender_Game_Scale", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeFogNear: NodeSocketFloat = tree_interface.new_socket(
            "FogNear", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeFogFar: NodeSocketFloat = tree_interface.new_socket(
            "FogFar", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )

        _nodeAmbientColor: NodeSocketColor = tree_interface.new_socket(
            "AmbientColor", socket_type="NodeSocketColor", in_out="OUTPUT"
        )
        _nodeLight0Color: NodeSocketColor = tree_interface.new_socket(
            "Light0Color", socket_type="NodeSocketColor", in_out="OUTPUT"
        )
        _nodeLight0Dir: NodeSocketVector = tree_interface.new_socket(
            "Light0Dir", socket_type="NodeSocketVector", in_out="OUTPUT"
        )
        _nodeLight0Size: NodeSocketFloat = tree_interface.new_socket(
            "Light0Size", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )
        _nodeLight1Color: NodeSocketColor = tree_interface.new_socket(
            "Light1Color", socket_type="NodeSocketColor", in_out="OUTPUT"
        )
        _nodeLight1Dir: NodeSocketVector = tree_interface.new_socket(
            "Light1Dir", socket_type="NodeSocketVector", in_out="OUTPUT"
        )
        _nodeLight1Size: NodeSocketFloat = tree_interface.new_socket(
            "Light1Size", socket_type="NodeSocketFloat", in_out="OUTPUT"
        )

    else:
        _nodeFogEnable: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "FogEnable")
        _nodeFogColor: NodeSocketColor = new_group.outputs.new("NodeSocketColor", "FogColor")
        _nodeF3D_NearClip: NodeSocketFloat = new_group.outputs.new("NodeSocketFloat", "F3D_NearClip")
        _nodeF3D_FarClip: NodeSocketFloat = new_group.outputs.new("NodeSocketFloat", "F3D_FarClip")
        _nodeBlender_Game_Scale: NodeSocketFloat = new_group.outputs.new("NodeSocketFloat", "Blender_Game_Scale")
        _nodeFogNear: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "FogNear")
        _nodeFogFar: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "FogFar")

        _nodeAmbientColor: NodeSocketColor = new_group.outputs.new("NodeSocketColor", "AmbientColor")
        _nodeLight0Color: NodeSocketColor = new_group.outputs.new("NodeSocketColor", "Light0Color")
        _nodeLight0Dir: NodeSocketVectorDirection = new_group.outputs.new("NodeSocketVectorDirection", "Light0Dir")
        _nodeLight0Size: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "Light0Size")
        _nodeLight1Color: NodeSocketColor = new_group.outputs.new("NodeSocketColor", "Light1Color")
        _nodeLight1Dir: NodeSocketVectorDirection = new_group.outputs.new("NodeSocketVectorDirection", "Light1Dir")
        _nodeLight1Size: NodeSocketInt = new_group.outputs.new("NodeSocketInt", "Light1Size")

    # Set outputs from render settings
    sceneOutputs: NodeGroupOutput = new_group.nodes["Group Output"]
    renderSettings: "Fast64RenderSettings_Properties" = bpy.context.scene.fast64.renderSettings

    update_scene_props_from_render_settings(sceneOutputs, renderSettings)


def createScenePropertiesForMaterial(material: Material):
    node_tree = material.node_tree

    # Either create or update SceneProperties if needed
    createOrUpdateSceneProperties()

    # create a new group node to hold the tree
    scene_props = node_tree.nodes.new(type="ShaderNodeGroup")
    scene_props.name = "SceneProperties"
    scene_props.location = (-320, -23)
    scene_props.node_tree = bpy.data.node_groups["SceneProperties"]

    # Fog links to reroutes and the CalcFog block
    node_tree.links.new(scene_props.outputs["FogEnable"], node_tree.nodes["FogEnable"].inputs[0])
    node_tree.links.new(scene_props.outputs["FogColor"], node_tree.nodes["FogColor"].inputs[0])
    node_tree.links.new(scene_props.outputs["F3D_NearClip"], node_tree.nodes["CalcFog"].inputs["F3D_NearClip"])
    node_tree.links.new(scene_props.outputs["F3D_FarClip"], node_tree.nodes["CalcFog"].inputs["F3D_FarClip"])
    node_tree.links.new(
        scene_props.outputs["Blender_Game_Scale"], node_tree.nodes["CalcFog"].inputs["Blender_Game_Scale"]
    )
    node_tree.links.new(scene_props.outputs["FogNear"], node_tree.nodes["CalcFog"].inputs["FogNear"])
    node_tree.links.new(scene_props.outputs["FogFar"], node_tree.nodes["CalcFog"].inputs["FogFar"])

    # Lighting links to reroutes. The colors are connected to other reroutes for update_light_colors,
    # the others go directly to the Shade Color block.
    node_tree.links.new(scene_props.outputs["AmbientColor"], node_tree.nodes["AmbientColor"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light0Color"], node_tree.nodes["Light0Color"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light0Dir"], node_tree.nodes["Light0Dir"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light0Size"], node_tree.nodes["Light0Size"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light1Color"], node_tree.nodes["Light1Color"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light1Dir"], node_tree.nodes["Light1Dir"].inputs[0])
    node_tree.links.new(scene_props.outputs["Light1Size"], node_tree.nodes["Light1Size"].inputs[0])


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


def get_f3d_node_tree() -> bpy.types.NodeTree:
    try:
        link_f3d_material_library()
        mat = bpy.data.materials["fast64_f3d_material_library_beefwashere"]
        return mat.node_tree.copy()
    finally:
        bpy.data.materials.remove(mat)


def shouldConvOrCreateColorAttribute(mesh: Mesh, attr_name="Col"):
    has_attr, conv_attr = False, False
    if attr_name in mesh.attributes:
        attribute: Attribute = mesh.attributes[attr_name]
        has_attr = True
        conv_attr = attribute.data_type != "FLOAT_COLOR" or attribute.domain != "CORNER"
    return has_attr, conv_attr


def convertColorAttribute(mesh: Mesh, attr_name="Col"):
    prev_index = mesh.attributes.active_index
    attr_index = mesh.attributes.find(attr_name)
    if attr_index < 0:
        raise PluginError(f"Failed to find the index for mesh attr {attr_name}. Attribute conversion has failed!")

    mesh.attributes.active_index = attr_index
    bpy.ops.geometry.attribute_convert(mode="GENERIC", domain="CORNER", data_type="FLOAT_COLOR")
    mesh.attributes.active_index = prev_index


def addColorAttributesToModel(obj: Object):
    if obj.type != "MESH":
        return

    prevMode = bpy.context.mode
    if prevMode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    selectSingleObject(obj)

    mesh: Mesh = obj.data

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


def add_f3d_mat_to_obj(obj: bpy.types.Object, material, index=None):
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


def createF3DMat(obj: Object | None, preset="Shaded Solid", index=None):
    # link all node_groups + material from addon's data .blend
    link_f3d_material_library()

    # a linked material containing the default layout for all the linked node_groups
    mat = bpy.data.materials["fast64_f3d_material_library_beefwashere"]
    # duplicate and rename the linked material
    material = mat.copy()
    material.name = "f3dlite_material"
    # remove the linked material so it doesn't bother anyone or get meddled with
    bpy.data.materials.remove(mat)

    createScenePropertiesForMaterial(material)

    add_f3d_mat_to_obj(obj, material, index)

    material.is_f3d = True
    material.mat_ver = F3D_MAT_CUR_VERSION

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


def check_or_ask_color_management(context: Context):
    scene = context.scene
    fast64_props: "Fast64_Properties" = scene.fast64
    fast64settings_props: "Fast64Settings_Properties" = fast64_props.settings
    view_settings = scene.view_settings
    # Check if color management settings are correct
    if not fast64settings_props.dont_ask_color_management and (
        scene.display_settings.display_device != "sRGB"
        or view_settings.view_transform != "Standard"
        or view_settings.look != "None"
        or view_settings.exposure != 0.0
        or view_settings.gamma != 1.0
    ):
        bpy.ops.dialog.fast64_update_color_management("INVOKE_DEFAULT")


class UpdateColorManagementPopup(Operator):
    bl_label = "Update Color Management"
    bl_idname = "dialog.fast64_update_color_management"
    bl_description = "Update color management settings to help material preview accuracy"
    bl_options = {"UNDO"}

    already_invoked = False  # HACK: used to prevent multiple dialogs from popping up

    def invoke(self, context: Context, event: Event):
        if UpdateColorManagementPopup.already_invoked:
            return {"FINISHED"}
        UpdateColorManagementPopup.already_invoked = True
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context: Context):
        col = self.layout.column()
        multilineLabel(
            col,
            (
                (
                    f'The color management settings for the current scene "{context.scene.name}"\n'
                    # use is_library_indirect to not count the scene from f3d_material_library.blend and other "external" scenes
                    if len([_s for _s in bpy.data.scenes if not _s.is_library_indirect]) >= 2
                    else "The color management settings\n"
                )
                + "will cause inaccurate preview compared to N64.\n"
                + "Would you like to update it?"
            ),
            icon="INFO",
        )
        fast64_props: "Fast64_Properties" = context.scene.fast64
        fast64settings_props: "Fast64Settings_Properties" = fast64_props.settings
        col.prop(fast64settings_props, "dont_ask_color_management", text="Don't ask again")

    def cancel(self, context: Context):
        UpdateColorManagementPopup.already_invoked = False

    def execute(self, context):
        try:
            scene = context.scene
            scene.display_settings.display_device = "sRGB"
            scene.view_settings.view_transform = "Standard"
            scene.view_settings.look = "None"
            scene.view_settings.exposure = 0.0
            scene.view_settings.gamma = 1.0
            self.report({"INFO"}, "Updated color management settings.")
            return {"FINISHED"}
        except Exception as exc:
            raisePluginError(self, exc)
            return {"CANCELLED"}
        finally:
            UpdateColorManagementPopup.already_invoked = False


class RecreateF3DNodes(Operator):
    bl_idname = "material.recreate_f3d_nodes"
    bl_label = "Recreate F3D Shader Nodes"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    bl_description = "Recreates the node tree for f3d materials, use if material preview is broken."

    def execute(self, context):
        material = context.material
        if material is None:
            self.report({"ERROR"}, "No active material.")
        else:
            node_tree_copy(get_f3d_node_tree(), material.node_tree)
            createScenePropertiesForMaterial(material)
            update_all_node_values(material, context)
            self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class CreateFast3DMaterial(Operator):
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


class ReloadDefaultF3DPresets(Operator):
    bl_idname = "object.reload_f3d_presets"
    bl_label = "Reload Default Fast3D Presets"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        reloadDefaultF3DPresets()
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


def get_tex_prop_from_path(material: Material, path: str) -> Tuple["TextureProperty", int]:
    if "tex0" in path:
        return material.f3d_mat.tex0, 0
    return material.f3d_mat.tex1, 1


def already_updating_material(material: Material | None):
    """Check if material is updating already"""
    return getattr(material, "f3d_update_flag", False)


def update_tex_field_prop(self: Property, context: Context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        prop_path = self.path_from_id()
        tex_property, tex_index = get_tex_prop_from_path(material, prop_path)
        tex_size = tex_property.get_tex_size()

        if tex_size[0] > 0 and tex_size[1] > 0:
            update_tex_values_field(material, tex_property, tex_size, tex_index)
        set_texture_settings_node(material)


def toggle_auto_prop(self, context: Context):
    with F3DMaterial_UpdateLock(get_material_from_context(context)) as material:
        if not material:
            return

        prop_path = self.path_from_id()
        tex_property, tex_index = get_tex_prop_from_path(material, prop_path)
        if tex_property.autoprop:
            tex_size = tuple([s for s in tex_property.get_tex_size()])
            if tex_size[0] > 0 and tex_size[1] > 0:
                update_tex_values_field(material, tex_property, tex_size, tex_index)

        set_texture_settings_node(material)


class TextureFieldProperty(PropertyGroup):
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


class SetTileSizeScrollProperty(PropertyGroup):
    s: bpy.props.IntProperty(min=-4095, max=4095, default=0)
    t: bpy.props.IntProperty(min=-4095, max=4095, default=0)
    interval: bpy.props.IntProperty(min=1, soft_max=1000, default=1)

    def key(self):
        return (self.s, self.t, self.interval)


class TextureProperty(PropertyGroup):
    tex: bpy.props.PointerProperty(
        type=Image,
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
        name="Palette Reference Size",
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

    @property
    def is_ci(self):
        self.tex_format: str
        return self.tex_format.startswith("CI")

    @property
    def tlut_mode(self):
        return f"G_TT_{self.ci_format if self.is_ci else 'NONE'}"

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


def update_combiner_connections_and_preset(self, context: Context):
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
    canUseLargeTextures: bool,
    layout: UILayout,
    material: Material,
    textureProp: TextureProperty,
    name: str,
    showCheckBox: bool,
    hide_lowhigh=False,
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
                flipbook = getattr(material.flipbookGroup, "flipbook" + texIndex)
                if flipbook is None or not flipbook.enable:
                    prop_split(prop_input, textureProp, "pal_reference", "Palette Reference")
                    prop_split(prop_input, textureProp, "pal_reference_size", "Palette Size")

        else:
            prop_input.template_ID(
                textureProp, "tex", new="image.new", open="image.open", unlink="image.tex" + texIndex + "_unlink"
            )
            prop_input.enabled = textureProp.tex_set

            if tex is not None:
                prop_input.label(text="Size: " + str(tex.size[0]) + " x " + str(tex.size[1]))

        if textureProp.use_tex_reference:
            width, height = textureProp.tex_reference_size[0], textureProp.tex_reference_size[1]
        elif tex is not None:
            width, height = tex.size[0], tex.size[1]
        else:
            width = height = 0

        if canUseLargeTextures:
            availTmem = 512
            if textureProp.tex_format[:2] == "CI":
                availTmem /= 2
            useDict = all_combiner_uses(material.f3d_mat)
            if useDict["Texture 0"] and useDict["Texture 1"]:
                availTmem /= 2
            isLarge = getTmemWordUsage(textureProp.tex_format, width, height) > availTmem
        else:
            isLarge = False

        if isLarge:
            msg = prop_input.box().column()
            msg.label(text="This is a large texture.", icon="INFO")
            msg.label(text="Recommend using Create Large Texture Mesh tool.")
        else:
            tmemUsageUI(prop_input, textureProp)

        prop_split(prop_input, textureProp, "tex_format", name="Format")
        if textureProp.tex_format[:2] == "CI":
            prop_split(prop_input, textureProp, "ci_format", name="CI Format")

        if not isLarge:
            if width > 0 and height > 0:
                texelsPerWord = 64 // texBitSizeInt[textureProp.tex_format]
                if width % texelsPerWord != 0:
                    msg = prop_input.box().column()
                    msg.label(text=f"Suggest {textureProp.tex_format} tex be multiple ", icon="INFO")
                    msg.label(text=f"of {texelsPerWord} pixels wide for fast loading.")
                warnClampS = (
                    not isPowerOf2(width)
                    and not textureProp.S.clamp
                    and (not textureProp.autoprop or textureProp.S.mask != 0)
                )
                warnClampT = (
                    not isPowerOf2(height)
                    and not textureProp.T.clamp
                    and (not textureProp.autoprop or textureProp.T.mask != 0)
                )
                if warnClampS or warnClampT:
                    msg = prop_input.box().column()
                    msg.label(text=f"Clamping required for non-power-of-2 image", icon="ERROR")
                    msg.label(text=f"dimensions. Enable clamp or set mask to 0.")

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
                if hide_lowhigh:
                    return
                low = prop_input.row()
                low.prop(textureProp.S, "low", text="S Low")
                low.prop(textureProp.T, "low", text="T Low")

                high = prop_input.row()
                high.prop(textureProp.S, "high", text="S High")
                high.prop(textureProp.T, "high", text="T High")


class CombinerProperty(PropertyGroup):
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


class ProceduralAnimProperty(PropertyGroup):
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


class ProcAnimVectorProperty(PropertyGroup):
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


class PrimDepthSettings(PropertyGroup):
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

    def to_dict(self):
        return prop_group_to_json(self)

    def from_dict(self, data: dict):
        json_to_prop_group(self, data)

    def key(self):
        return frozenset(self.to_dict().items())


class RDPSettings(PropertyGroup):
    g_zbuffer: bpy.props.BoolProperty(
        name="Z Buffer",
        default=False,
        update=update_node_values_with_preset,
        description="Enables calculation of Z value for primitives. Disable if not reading or writing Z-Buffer in the blender",
    )
    g_shade: bpy.props.BoolProperty(
        name="Shading",
        default=False,
        update=update_node_values_with_preset,
        description="Computes shade coordinates for primitives. Disable if not using lighting, vertex colors or fog",
    )
    g_ambocclusion: bpy.props.BoolProperty(
        name="Ambient Occlusion",
        default=False,
        update=update_node_values_with_preset,
        description="F3DEX3: Scales each type light intensity differently with vertex alpha. Bake scene shadows / AO into vertex alpha, not vertex color",
    )
    g_attroffset_z_enable: bpy.props.BoolProperty(
        name="Z Offset (for decal fix)",
        default=False,
        update=update_node_values_with_preset,
        description="F3DEX3: Enables offset to vertex Z. To fix decals, set the Z mode to opaque and enable this",
    )
    g_attroffset_st_enable: bpy.props.BoolProperty(
        name="ST Offset (for UV scroll)",
        default=False,
        update=update_node_values_with_preset,
        description="F3DEX3: Enables offsets to vertex ST values, usually for UV scrolling",
    )
    # v1/2 difference
    g_cull_front: bpy.props.BoolProperty(
        name="Cull Front",
        default=False,
        update=update_node_values_with_preset,
        description="Disables drawing of front faces",
    )
    # v1/2 difference
    g_cull_back: bpy.props.BoolProperty(
        name="Cull Back",
        default=False,
        update=update_node_values_with_preset,
        description="Disables drawing of back faces",
    )
    g_packed_normals: bpy.props.BoolProperty(
        name="Packed Normals (Vtx Colors + Lighting)",
        default=False,
        update=update_node_values_with_preset,
        description="F3DEX3: Packs vertex normals in unused 16 bits of each vertex, enabling simultaneous vertex colors and lighting",
    )
    g_lighttoalpha: bpy.props.BoolProperty(
        name="Light to Alpha (for cel shading)",
        default=False,
        update=update_node_values_with_preset,
        description="F3DEX3: Moves light intensity to shade alpha, used for cel shading and other effects",
    )
    g_lighting_specular: bpy.props.BoolProperty(
        name="Specular Lighting",
        default=False,
        update=update_node_values_with_preset,
        description="F3DEX3: Microcode lighting computes specular instead of diffuse component. If using, must set size field of every light in code",
    )
    g_fresnel_color: bpy.props.BoolProperty(
        name="Fresnel to Color",
        default=False,
        update=update_node_values_with_preset,
        description="F3DEX3: Shade color derived from how much each vertex normal faces the camera. For bump mapping",
    )
    g_fresnel_alpha: bpy.props.BoolProperty(
        name="Fresnel to Alpha",
        default=False,
        update=update_node_values_with_preset,
        description="F3DEX3: Shade alpha derived from how much each vertex normal faces the camera. For water, glass, ghosts, etc., or toon outlines",
    )
    g_fog: bpy.props.BoolProperty(
        name="Fog",
        default=False,
        update=update_node_values_with_preset,
        description="Turns on/off fog calculation. Fog variable gets stored into shade alpha",
    )
    g_lighting: bpy.props.BoolProperty(
        name="Lighting",
        default=False,
        update=update_node_values_with_preset,
        description="Enables calculating shade color using lights. Turn off for vertex colors as shade color",
    )
    g_tex_gen: bpy.props.BoolProperty(
        name="Texture UV Generate",
        default=False,
        update=update_node_values_with_preset,
        description="Generates texture coordinates for reflection mapping based on vertex normals and lookat direction. On a skybox texture, maps the sky to the center of the texture and the ground to a circle inscribed in the border. Requires lighting enabled to use",
    )
    g_tex_gen_linear: bpy.props.BoolProperty(
        name="Texture UV Generate Linear",
        default=False,
        update=update_node_values_with_preset,
        description="Modifies the texgen mapping; enable with texgen. Use a normal panorama image for the texture, with the sky at the top and the ground at the bottom. Requires lighting enabled to use",
    )
    g_lod: bpy.props.BoolProperty(
        name="LoD (does nothing)",
        default=False,
        update=update_node_values_with_preset,
        description="Not implemented in any known microcodes. No effect whether enabled or disabled",
    )
    g_shade_smooth: bpy.props.BoolProperty(
        name="Smooth Shading",
        default=False,
        update=update_node_values_with_preset,
        description="Shades primitive smoothly using interpolation between shade values for each vertex (Gouraud shading)",
    )
    g_clipping: bpy.props.BoolProperty(
        name="Clipping",
        default=True,
        update=update_node_values_with_preset,
        description="F3DEX1/LX only, exact function unknown",
    )

    # upper half mode
    # v2 only
    g_mdsft_alpha_dither: bpy.props.EnumProperty(
        name="Alpha Dither",
        items=enumAlphaDither,
        default="G_AD_NOISE",
        update=update_node_values_with_preset,
        description="Applies your choice dithering type to output framebuffer alpha. Dithering is used to convert high precision source colors into lower precision framebuffer values",
    )
    # v2 only
    g_mdsft_rgb_dither: bpy.props.EnumProperty(
        name="RGB Dither",
        items=enumRGBDither,
        default="G_CD_MAGICSQ",
        update=update_node_values_with_preset,
        description="Applies your choice dithering type to output framebuffer color. Dithering is used to convert high precision source colors into lower precision framebuffer values",
    )
    g_mdsft_combkey: bpy.props.EnumProperty(
        name="Chroma Key",
        items=enumCombKey,
        default="G_CK_NONE",
        update=update_node_values_with_preset,
        description="Turns on/off the chroma key. Chroma key requires a special setup to work properly",
    )
    g_mdsft_textconv: bpy.props.EnumProperty(
        name="Texture Convert",
        items=enumTextConv,
        default="G_TC_CONV",
        update=update_node_values_with_preset,
        description="Sets the function of the texture convert unit, to do texture filtering, YUV to RGB conversion, or both",
    )
    g_mdsft_text_filt: bpy.props.EnumProperty(
        name="Texture Filter",
        items=enumTextFilt,
        default="G_TF_POINT",
        update=update_node_values_without_preset,
        description="Applies your choice of filtering to texels",
    )
    g_mdsft_textlut: bpy.props.EnumProperty(
        name="Texture LUT",
        items=enumTextLUT,
        default="G_TT_NONE",
        description="Changes texture look up table (LUT) behavior. This property is auto set if you choose a CI texture",
    )
    g_mdsft_textlod: bpy.props.EnumProperty(
        name="Texture LOD",
        items=enumTextLOD,
        default="G_TL_TILE",
        update=update_node_values_with_preset,
        description="Turns on/off the use of LoD on textures. LoD textures change the used tile based on the texel/pixel ratio",
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
        description="Changes type of LoD usage. Affects how tiles are selected based on texel magnification. Only works when G_TL_LOD is selected",
    )
    g_mdsft_textpersp: bpy.props.EnumProperty(
        name="Texture Perspective Correction",
        items=enumTextPersp,
        default="G_TP_NONE",
        update=update_node_values_with_preset,
        description="Turns on/off texture perspective correction",
    )
    g_mdsft_cycletype: bpy.props.EnumProperty(
        name="Cycle Type",
        items=enumCycleType,
        default="G_CYC_1CYCLE",
        update=update_node_values_with_preset,
        description="Changes RDP pipeline configuration. For normal textured triangles use one or two cycle mode",
    )
    # v1 only
    g_mdsft_color_dither: bpy.props.EnumProperty(
        name="Color Dither",
        items=enumColorDither,
        default="G_CD_ENABLE",
        update=update_node_values_with_preset,
        description="Applies your choice dithering type to output frambuffer",
    )
    g_mdsft_pipeline: bpy.props.EnumProperty(
        name="Pipeline Span Buffer Coherency",
        items=enumPipelineMode,
        default="G_PM_NPRIMITIVE",
        update=update_node_values_with_preset,
        description="Changes primitive rasterization timing by adding syncs after tri draws. Vanilla SM64 has synchronization issues which could cause a crash if not using 1 prim. For any modern SM64 hacking project or other game N-prim should always be used",
    )

    # lower half mode
    g_mdsft_alpha_compare: bpy.props.EnumProperty(
        name="Alpha Compare",
        items=enumAlphaCompare,
        default="G_AC_NONE",
        update=update_node_values_with_preset,
        description="Uses alpha comparisons to decide if a pixel should be written. Applies before blending",
    )
    g_mdsft_zsrcsel: bpy.props.EnumProperty(
        name="Z Source Selection",
        items=enumDepthSource,
        default="G_ZS_PIXEL",
        update=update_node_values_with_preset,
        description="Changes screen-space Z value source used for Z-Buffer calculations",
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
        update=update_rendermode_preset,
    )
    rendermode_preset_cycle_2: bpy.props.EnumProperty(
        items=enumRenderModesCycle2,
        default="G_RM_AA_ZB_OPA_SURF2",
        name="Render Mode Cycle 2",
        update=update_rendermode_preset,
    )
    aa_en: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
        description="Enables anti-aliasing to rasterized primitive edges. Uses coverage to determine edges",
    )
    z_cmp: bpy.props.BoolProperty(
        update=update_node_values_with_preset, description="Checks pixel Z value against Z-Buffer to test writing"
    )
    z_upd: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
        description="Updates the Z-Buffer with the most recently written pixel Z value",
    )
    im_rd: bpy.props.BoolProperty(
        update=update_node_values_with_preset, description="Enables reading from framebuffer for blending calculations"
    )
    clr_on_cvg: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
        description="Only draw on coverage (amount primitive covers target pixel) overflow",
    )
    cvg_dst: bpy.props.EnumProperty(
        name="Coverage Destination",
        items=enumCoverage,
        update=update_node_values_with_preset,
        description="Changes how coverage (amount primitive covers target pixel) gets retrieved/stored",
    )
    zmode: bpy.props.EnumProperty(
        name="Z Mode",
        items=enumZMode,
        update=update_node_values_with_preset,
        description="Changes Z calculation for different types of primitives",
    )
    cvg_x_alpha: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
        description="Multiply coverage (amount primitive covers target pixel) with alpha and store result as coverage",
    )
    alpha_cvg_sel: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
        description="Use coverage (amount primitive covers target pixel) as alpha instead of color combiner alpha",
    )
    force_bl: bpy.props.BoolProperty(
        update=update_node_values_with_preset,
        description="Always uses blending on. Default blending is conditionally only applied during partial coverage. Forcing blending will disable division step of the blender, so B input must be 1-A or there may be rendering issues. Always use this option when Z Buffering is off",
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

    @property
    def using_fog(self):
        return self.g_fog or self.does_blender_use_input("G_BL_CLR_FOG") or self.does_blender_use_input("G_BL_A_FOG")

    @property
    def blend_color_inputs(self):
        yield from (getattr(self, f"blend_{val}") for val in ("p1", "p2", "m1", "m2"))

    @property
    def blend_alpha_inputs(self):
        yield from (getattr(self, f"blend_{val}") for val in ("a1", "a2", "b1", "b2"))

    @property
    def blend_inputs(self):
        yield from self.blend_color_inputs
        yield from self.blend_alpha_inputs

    def has_prop_in_ucode(self, prop: str) -> bool:
        return prop in geo_modes_in_ucode(bpy.context.scene.f3d_type).values()

    def is_geo_mode_on(self, prop: str) -> bool:
        return getattr(self, prop) if self.has_prop_in_ucode(prop) else False

    def does_blender_use_input(self, setting: str) -> bool:
        return any(input == setting for input in self.blend_inputs)

    def attributes_to_dict(self, info: dict):
        data = {}
        for key, attr, default in info:
            value = getattr(self, attr)
            if value != default:
                data[key] = value
        return data

    def attributes_from_dict(self, data: dict, info: dict):
        for key, attr, default in info:
            setattr(self, attr, data.get(key, default))

    geo_mode_attributes = {**F3D_GEO_MODES, **F3DLX_GEO_MODES, **F3DEX3_GEO_MODES}

    def geo_mode_to_dict(self):
        data = {}
        for key, attr in geo_modes_in_ucode(bpy.context.scene.f3d_type).items():
            if getattr(self, attr):
                data[key] = True
        return data

    def geo_mode_from_dict(self, data: dict):
        for key, attr in self.geo_mode_attributes.items():
            setattr(self, attr, data.get(key, False))

    other_mode_h_attributes = [
        ("alphaDither", "g_mdsft_alpha_dither", "G_AD_DISABLE"),
        ("colorDither", "g_mdsft_rgb_dither", "G_CD_MAGICSQ"),
        ("chromaKey", "g_mdsft_combkey", "G_CK_NONE"),
        ("textureConvert", "g_mdsft_textconv", "G_TC_CONV"),
        ("textureFilter", "g_mdsft_text_filt", "G_TF_POINT"),
        ("lutFormat", "g_mdsft_textlut", "G_TT_NONE"),
        ("textureLoD", "g_mdsft_textlod", "G_TL_TILE"),
        ("textureDetail", "g_mdsft_textdetail", "G_TD_CLAMP"),
        ("perspectiveCorrection", "g_mdsft_textpersp", "G_TP_NONE"),
        ("cycleType", "g_mdsft_cycletype", "G_CYC_1CYCLE"),
        ("pipelineMode", "g_mdsft_pipeline", "G_PM_NPRIMITIVE"),
    ]

    def other_mode_h_to_dict(self, lut_format=None):
        data = self.attributes_to_dict(self.other_mode_h_attributes)
        if lut_format:
            data["lutFormat"] = lut_format
        return data

    def other_mode_h_from_dict(self, data: dict):
        self.attributes_from_dict(data, self.other_mode_h_attributes)

    other_mode_l_attributes = [
        ("alphaCompare", "g_mdsft_alpha_compare", "G_AC_NONE"),
        ("zSourceSelection", "g_mdsft_zsrcsel", "G_ZS_PIXEL"),
    ]

    rendermode_flag_attributes = [
        ("aa", "aa_en", False),
        ("zTest", "z_cmp", False),
        ("zWrite", "z_upd", False),
        ("colorOnCvg", "clr_on_cvg", False),
        ("alphaOnCvg", "alpha_cvg_sel", False),
        ("mulCvgXAlpha", "cvg_x_alpha", False),
        ("forceBlend", "force_bl", False),
        ("readFB", "im_rd", False),
        ("cvgDst", "cvg_dst", "CVG_DST_CLAMP"),
        ("zMode", "zmode", "ZMODE_OPA"),
    ]

    def other_mode_l_to_dict(self):
        data = self.attributes_to_dict(self.other_mode_l_attributes)
        if self.g_mdsft_zsrcsel == "G_ZS_PRIM":
            data["primDepth"] = self.prim_depth.to_dict()
        if self.set_rendermode:
            two_cycle = self.g_mdsft_cycletype == "G_CYC_2CYCLE"
            if self.rendermode_advanced_enabled:
                blender_data = []
                for i in range(2 if two_cycle else 1):
                    num = i + 1
                    color_attrs, alpha_attrs = (f"blend_p{num}", f"blend_m{num}"), (f"blend_a{num}", f"blend_b{num}")
                    blender_data.append(
                        {
                            "color": (getattr(self, color_attrs[0]), getattr(self, color_attrs[1])),
                            "alpha": (getattr(self, alpha_attrs[0]), getattr(self, alpha_attrs[1])),
                        }
                    )
                data["renderMode"] = {
                    "flags": self.attributes_to_dict(self.rendermode_flag_attributes),
                    "blender": blender_data,
                }
            else:
                data["renderMode"] = {
                    "presets": [self.rendermode_preset_cycle_1]
                    + ([self.rendermode_preset_cycle_2] if two_cycle else [])
                }

        return data

    def other_mode_l_from_dict(self, data: dict):
        self.attributes_from_dict(data, self.other_mode_l_attributes)
        self.prim_depth.from_dict(data.get("primDepth", {}))

        render_mode = data.get("renderMode", {})
        blender = render_mode.get("blender", [])
        flags = render_mode.get("flags", {})
        if render_mode:
            self.set_rendermode = True
        if not render_mode.get("presets", None) and (flags or blender):
            self.rendermode_advanced_enabled = True

        self.rendermode_preset_cycle_1, self.rendermode_preset_cycle_2 = render_mode.get(
            "presets", [self.rendermode_preset_cycle_1, self.rendermode_preset_cycle_2]
        )

        self.attributes_from_dict(flags, self.rendermode_flag_attributes)
        color_attrs = ("blend_p", "blend_m")
        alpha_attrs = ("blend_a", "blend_b")
        for i, cycle in enumerate(blender * 2 if len(blender) == 1 else blender):
            num = str(i + 1)
            color_attrs, alpha_attrs = (f"blend_p{num}", f"blend_m{num}"), (f"blend_a{num}", f"blend_b{num}")
            self[color_attrs[0]], self[color_attrs[1]] = cycle.get(
                "color", [self.get(color_attrs[0]), self.get(color_attrs[1])]
            )
            self[alpha_attrs[0]], self[alpha_attrs[1]] = cycle.get(
                "alpha", [self.get(alpha_attrs[0]), self.get(alpha_attrs[1])]
            )

    def other_to_dict(self):
        data = {}
        if self.clip_ratio != 1.0:
            data["clipRatio"] = self.clip_ratio
        if self.g_mdsft_textlod == "G_TL_LOD" and self.num_textures_mipmapped != 1:
            data["mipmapCount"] = self.num_textures_mipmapped
        return data

    def other_from_dict(self, data: dict):
        self.clip_ratio = data.get("clipRatio", self.clip_ratio)
        self.num_textures_mipmapped = data.get("mipmapCount", self.num_textures_mipmapped)

    def to_dict(self):
        data = {}
        data["geometryMode"] = self.geo_mode_to_dict()
        data["otherModeH"] = self.other_mode_h_to_dict()
        data["otherModeL"] = self.other_mode_l_to_dict()
        data["other"] = self.other_to_dict()
        return data

    def from_dict(self, data: dict):
        self.geo_mode_from_dict(data.get("geometryMode", {}))
        self.other_mode_h_from_dict(data.get("otherModeH", {}))
        self.other_mode_l_from_dict(data.get("otherModeL", {}))
        self.other_from_dict(data.get("other", {}))

    def key(self):
        return str(self.to_dict().items())


def draw_rdp_world_defaults(layout: UILayout, scene: Scene):
    world = scene.world
    if world is None:
        layout.box().label(text="No World Selected In Scene", icon="WORLD")
        return
    rdp_defaults = world.rdp_defaults
    col = layout.column()
    col.box().label(text="RDP Default Settings", icon="WORLD")
    multilineLabel(
        col,
        text="If a material setting is the same as the default setting\n"
        "it won't be set, otherwise a revert will be added.",
    )
    if scene.gameEditorMode == "Homebrew":
        multilineLabel(
            col.box(),
            text="Homebrew mode defaults to ucode defaults,\nmake sure to set your own.",
            icon="INFO",
        )
    ui_geo_mode(rdp_defaults, world, col, True)
    ui_upper_mode(rdp_defaults, world, col, True)
    ui_lower_mode(rdp_defaults, world, col, True)
    ui_other(rdp_defaults, world, col, True)


class DefaultRDPSettingsPanel(Panel):
    bl_label = "RDP Default Settings"
    bl_idname = "WORLD_PT_RDP_Default_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        draw_rdp_world_defaults(self.layout, context.scene)


class CelLevelProperty(PropertyGroup):
    threshMode: bpy.props.EnumProperty(
        items=enumCelThreshMode, name="Draw when", default="Lighter", update=update_cel_cutout_source
    )
    threshold: bpy.props.IntProperty(
        name="Threshold",
        description="Light level at which the boundary between cel levels occurs. One level is >= this value, the other is < it",
        min=2,
        max=255,
        default=128,
    )
    tintType: bpy.props.EnumProperty(items=enumCelTintType, name="Tint type", default="Fixed")
    tintFixedLevel: bpy.props.IntProperty(
        name="Level",
        description="0: original color <=> 255: fully tint color",
        min=0,
        max=255,
        default=50,
    )
    tintFixedColor: bpy.props.FloatVectorProperty(
        name="Tint color",
        size=3,
        min=0.0,
        max=1.0,
        subtype="COLOR",
    )
    tintSegmentNum: bpy.props.IntProperty(
        name="Segment",
        description="Segment number to store tint DL in",
        min=8,
        max=0xD,
        default=8,
    )
    tintSegmentOffset: bpy.props.IntProperty(
        name="Offset (instr)",
        description="Number of instructions (8 bytes) within this DL to jump to",
        min=0,
        max=1000,
        default=0,
    )
    tintLightSlot: bpy.props.IntProperty(
        name="Light (/end)",
        description="Which light to load RGB color from, counting from the end. 0 = ambient, 1 = last directional / point light, 2 = second-to-last, etc.",
        min=0,
        max=9,
        default=1,
    )


class CelShadingProperty(PropertyGroup):
    tintPipeline: bpy.props.EnumProperty(items=enumCelTintPipeline, name="Tint pipeline", default="CC")
    cutoutSource: bpy.props.EnumProperty(
        items=enumCelCutoutSource,
        name="Cutout",
        default="ENVIRONMENT",
        update=update_cel_cutout_source,
    )
    levels: bpy.props.CollectionProperty(type=CelLevelProperty, name="Cel levels")


def celGetMaterialLevels(materialName):
    material = bpy.data.materials.get(materialName)
    if material is None:
        raise PluginError(f"Could not find material {materialName}")
    return material.f3d_mat.cel_shading.levels


class CelLevelAdd(bpy.types.Operator):
    bl_idname = "material.f3d_cel_level_add"
    bl_label = "Add Cel Level"
    bl_options = {"REGISTER", "UNDO"}

    materialName: bpy.props.StringProperty()

    def execute(self, context):
        levels = celGetMaterialLevels(self.materialName)
        levels.add()
        return {"FINISHED"}


class CelLevelRemove(bpy.types.Operator):
    bl_idname = "material.f3d_cel_level_remove"
    bl_label = "Remove Last Level"
    bl_options = {"REGISTER", "UNDO"}

    materialName: bpy.props.StringProperty()

    def execute(self, context):
        levels = celGetMaterialLevels(self.materialName)
        levels.remove(len(levels) - 1)
        return {"FINISHED"}


def getCurrentPresetDir():
    return "f3d/" + bpy.context.scene.gameEditorMode.lower()


class ApplyMaterialPresetOperator(Operator):
    bl_idname = "material.f3d_preset_apply"
    bl_label = "Apply F3D Material Preset"

    filepath: bpy.props.StringProperty()

    def execute(self, context: Context):
        material_apply_preset(context.material, self.filepath)
        return {"FINISHED"}


def getCurrentPresetDir():
    return "f3d/" + bpy.context.scene.gameEditorMode.lower()


# modules/bpy_types.py -> Menu
class MATERIAL_MT_f3d_presets(Menu):
    bl_label = "F3D Material Presets"
    preset_operator = ApplyMaterialPresetOperator.bl_idname

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

        paths = bpy.utils.preset_paths("f3d/user")
        if not bpy.context.scene.f3dUserPresetsOnly:
            paths += bpy.utils.preset_paths(presetDir)
            if bpy.context.scene.f3d_type == "F3DEX3":
                paths += bpy.utils.preset_paths(f"{presetDir}_f3dex3")
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
                        if isinstance(value, PropertyGroup):
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


def convertToNewMat(material):
    old_to_new_props = {
        "presetName": "presetName",
        "scale_autoprop": "scale_autoprop",
        "uv_basis": "uv_basis",
        "combiner1": "combiner1",
        "combiner2": "combiner2",
        "menu_procAnim": "menu_procAnim",
        "UVanim0": "UVanim",
        "UVanim1": "UVanim_tex1",
        "tex_scale": "tex_scale",
        "tex0": "tex0",
        "tex1": "tex1",
        "set_prim": "set_prim",
        "set_lights": "set_lights",
        "set_env": "set_env",
        "set_blend": "set_blend",
        "set_key": "set_key",
        "set_k0_5": "set_k0_5",
        "set_combiner": "set_combiner",
        "use_default_lighting": "use_default_lighting",
        "blend_color": "blend_color",
        "key_scale": "key_scale",
        "key_width": "key_width",
        "k0": "k0",
        "k1": "k1",
        "k2": "k2",
        "k3": "k3",
        "k4": "k4",
        "k5": "k5",
        "prim_lod_frac": "prim_lod_frac",
        "prim_lod_min": "prim_lod_min",
        "default_light_color": "default_light_color",
        "ambient_light_color": "ambient_light_color",
        "fog_color": "fog_color",
        "fog_position": "fog_position",
        "set_fog": "set_fog",
        "use_global_fog": "use_global_fog",
        "menu_geo": "menu_geo",
        "menu_upper": "menu_upper",
        "menu_lower": "menu_lower",
        "menu_other": "menu_other",
        "menu_lower_render": "menu_lower_render",
        "rdp_settings": "rdp_settings",
    }
    for new, old in old_to_new_props.items():
        upgrade_old_prop(material.f3d_mat, new, material, old)

    # Colors
    nodes = material.node_tree.nodes

    if material.mat_ver == 3:
        prim = nodes["Primitive Color Output"].inputs[0].default_value
        env = nodes["Environment Color Output"].inputs[0].default_value
    else:
        prim = nodes["Primitive Color"].outputs[0].default_value
        env = nodes["Environment Color"].outputs[0].default_value

    material.f3d_mat.prim_color = prim
    material.f3d_mat.env_color = env
    if "Chroma Key Center" in nodes:
        material.f3d_mat.key_center = nodes["Chroma Key Center"].outputs[0].default_value

    # lights
    for i in range(1, 8):
        light_attr = f"f3d_light{str(i)}"
        upgrade_old_prop(material.f3d_mat, light_attr, material, light_attr)


class F3DMaterialProperty(PropertyGroup):
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
    f3d_light1: bpy.props.PointerProperty(type=Light, update=F3DOrganizeLights)
    f3d_light2: bpy.props.PointerProperty(type=Light, update=F3DOrganizeLights)
    f3d_light3: bpy.props.PointerProperty(type=Light, update=F3DOrganizeLights)
    f3d_light4: bpy.props.PointerProperty(type=Light, update=F3DOrganizeLights)
    f3d_light5: bpy.props.PointerProperty(type=Light, update=F3DOrganizeLights)
    f3d_light6: bpy.props.PointerProperty(type=Light, update=F3DOrganizeLights)
    f3d_light7: bpy.props.PointerProperty(type=Light, update=F3DOrganizeLights)

    # Ambient Occlusion
    ao_ambient: bpy.props.FloatProperty(
        name="AO Ambient",
        min=0.0,
        max=1.0,
        default=1.0,
        description="How much ambient occlusion (vertex alpha) affects ambient light intensity",
        update=update_node_values_without_preset,
    )
    ao_directional: bpy.props.FloatProperty(
        name="AO Directional",
        min=0.0,
        max=1.0,
        default=0.625,
        description="How much ambient occlusion (vertex alpha) affects directional light intensity",
        update=update_node_values_without_preset,
    )
    ao_point: bpy.props.FloatProperty(
        name="AO Point",
        min=0.0,
        max=1.0,
        default=0.0,
        description="How much ambient occlusion (vertex alpha) affects point light intensity",
        update=update_node_values_without_preset,
    )
    set_ao: bpy.props.BoolProperty(update=update_node_values_without_preset)

    # Fresnel
    fresnel_lo: bpy.props.FloatProperty(
        name="Fresnel lo",
        min=-1000.0,
        max=1000.0,
        default=0.7,
        description="Dot product value which gives shade alpha = 0. The dot product ranges from 1 when the normal points directly at the camera, to 0 when it points sideways",
        update=update_node_values_without_preset,
    )
    fresnel_hi: bpy.props.FloatProperty(
        name="Fresnel hi",
        min=-1000.0,
        max=1000.0,
        default=0.4,
        description="Dot product value which gives shade alpha = FF. The dot product ranges from 1 when the normal points directly at the camera, to 0 when it points sideways",
        update=update_node_values_without_preset,
    )
    set_fresnel: bpy.props.BoolProperty(update=update_node_values_without_preset)

    # Attribute Offsets
    attroffs_st: bpy.props.FloatVectorProperty(
        name="ST Attr Offset",
        size=2,
        min=-1024.0,
        max=1024.0,
        default=(0.0, 0.0),
        description="Offset applied to ST (UV) coordinates, after texture scale. Units are texels. Usually for UV scrolling",
        update=update_node_values_without_preset,
    )
    attroffs_z: bpy.props.IntProperty(
        name="Z Attr Offset",
        min=-0x8000,
        max=0x7FFF,
        default=-2,
        description="Offset applied to Z coordinate. To fix decals, set Z mode to opaque and set Z attr offset to something like -2",
        update=update_node_values_without_preset,
    )
    set_attroffs_st: bpy.props.BoolProperty(update=update_node_values_without_preset)
    set_attroffs_z: bpy.props.BoolProperty(update=update_node_values_without_preset)

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
    large_edges: bpy.props.EnumProperty(items=enumLargeEdges, default="Clamp")

    expand_cel_shading_ui: bpy.props.BoolProperty(name="Expand Cel Shading UI")
    use_cel_shading: bpy.props.BoolProperty(name="Use Cel Shading", update=update_cel_cutout_source)
    cel_shading: bpy.props.PointerProperty(type=CelShadingProperty)

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
            self.use_cel_shading,
            self.cel_shading.tintPipeline if self.use_cel_shading else None,
            (
                tuple(
                    [
                        (
                            c.threshMode,
                            c.threshold,
                            c.tintType,
                            c.tintFixedLevel,
                            c.tintFixedColor,
                            c.tintSegmentNum,
                            c.tintSegmentOffset,
                            c.tintLightSlot,
                        )
                        for c in self.cel_shading.levels
                    ]
                )
                if self.use_cel_shading
                else None
            ),
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
            (
                tuple([round(value, 4) for value in (self.ao_ambient, self.ao_directional, self.ao_point)])
                if self.set_ao
                else None
            ),
            tuple([round(value, 4) for value in (self.fresnel_lo, self.fresnel_hi)]) if self.set_fresnel else None,
            tuple([round(value, 4) for value in self.attroffs_st]) if self.set_attroffs_st else None,
            self.attroffs_z if self.set_attroffs_z else None,
            tuple([round(value, 4) for value in self.fog_color]) if self.set_fog else None,
            tuple([round(value, 4) for value in self.fog_position]) if self.set_fog else None,
            tuple([round(value, 4) for value in self.default_light_color]) if useDefaultLighting else None,
            self.set_ambient_from_light if useDefaultLighting else None,
            (
                tuple([round(value, 4) for value in self.ambient_light_color])
                if useDefaultLighting and not self.set_ambient_from_light
                else None
            ),
            self.f3d_light1 if not useDefaultLighting else None,
            self.f3d_light2 if not useDefaultLighting else None,
            self.f3d_light3 if not useDefaultLighting else None,
            self.f3d_light4 if not useDefaultLighting else None,
            self.f3d_light5 if not useDefaultLighting else None,
            self.f3d_light6 if not useDefaultLighting else None,
            self.f3d_light7 if not useDefaultLighting else None,
        )


class UnlinkF3DImage0(Operator):
    bl_idname = "image.tex0_unlink"
    bl_label = "Unlink F3D Image"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        context.material.f3d_mat.tex0.tex = None
        return {"FINISHED"}  # must return a set


class UnlinkF3DImage1(Operator):
    bl_idname = "image.tex1_unlink"
    bl_label = "Unlink F3D Image"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        context.material.f3d_mat.tex1.tex = None
        return {"FINISHED"}  # must return a set


class UpdateF3DNodes(Operator):
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


class F3DRenderSettingsPanel(Panel):
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
        isF3DEX3 = bpy.context.scene.f3d_type == "F3DEX3"

        globalSettingsBox = layout.box()
        labelbox = globalSettingsBox.box()
        labelbox.label(text="Global Settings")
        labelbox.ui_units_x = 6

        # Only show the update preview UI if the render engine is EEVEE,
        # as there's no point in updating the nodes otherwise.
        if context.scene.render.engine in {
            "BLENDER_EEVEE",  # <4.2
            "BLENDER_EEVEE_NEXT",  # 4.2+
        }:
            updatePreviewRow = globalSettingsBox.row()
            updatePreviewRow.prop(renderSettings, "enableAutoUpdatePreview")
            if not renderSettings.enableAutoUpdatePreview:
                updatePreviewRow.operator(ManualUpdatePreviewOperator.bl_idname)
            globalSettingsBox.separator()

        globalSettingsBox.prop(renderSettings, "enableFogPreview")
        prop_split(globalSettingsBox, renderSettings, "fogPreviewColor", "Fog Color")
        prop_split(globalSettingsBox, renderSettings, "fogPreviewPosition", "Fog Position")
        prop_split(globalSettingsBox, renderSettings, "clippingPlanes", "Clipping Planes")

        globalSettingsBox.separator(factor=0.125)
        # TODO: (v5) add headings
        prop_split(globalSettingsBox, renderSettings, "ambientColor", "Ambient Light")
        prop_split(globalSettingsBox, renderSettings, "light0Color", "Light 0 Color")
        prop_split(globalSettingsBox, renderSettings, "light0Direction", "Light 0 Direction")
        if isF3DEX3:
            prop_split(globalSettingsBox, renderSettings, "light0SpecSize", "Light 0 Specular Size")
        prop_split(globalSettingsBox, renderSettings, "light1Color", "Light 1 Color")
        prop_split(globalSettingsBox, renderSettings, "light1Direction", "Light 1 Direction")
        if isF3DEX3:
            prop_split(globalSettingsBox, renderSettings, "light1SpecSize", "Light 1 Specular Size")
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
                                r2 = b.row().split(factor=0.4)
                                r2.prop(renderSettings, "ootForceTimeOfDay")
                                if renderSettings.ootForceTimeOfDay:
                                    r2.label(text="Light Index sets first of four lights.", icon="INFO")
                                    numLightsNeeded = 4
                            if header.skyboxLighting != "LIGHT_MODE_TIME":
                                r.prop(renderSettings, "ootLightIdx")
                                if renderSettings.ootLightIdx + numLightsNeeded > len(header.lightList):
                                    b.label(text="Light does not exist.", icon="QUESTION")
                            if header.skyboxLighting == "LIGHT_MODE_TIME" or (
                                header.skyboxLighting == "Custom" and renderSettings.ootForceTimeOfDay
                            ):
                                r.prop(renderSettings, "ootTime")
                case _:
                    pass


def draw_f3d_render_settings(self, context):
    layout: UILayout = self.layout
    layout.popover(F3DRenderSettingsPanel.bl_idname)


mat_classes = (
    UpdateColorManagementPopup,
    UnlinkF3DImage0,
    UnlinkF3DImage1,
    DrawLayerProperty,
    ApplyMaterialPresetOperator,
    MATERIAL_MT_f3d_presets,
    AddPresetF3D,
    F3DPanel,
    CreateFast3DMaterial,
    RecreateF3DNodes,
    TextureFieldProperty,
    SetTileSizeScrollProperty,
    TextureProperty,
    CombinerProperty,
    ProceduralAnimProperty,
    ProcAnimVectorProperty,
    PrimDepthSettings,
    RDPSettings,
    DefaultRDPSettingsPanel,
    CelLevelProperty,
    CelShadingProperty,
    CelLevelAdd,
    CelLevelRemove,
    F3DMaterialProperty,
    ReloadDefaultF3DPresets,
    UpdateF3DNodes,
    F3DRenderSettingsPanel,
    F3DMeshPanel,
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

    Scene.f3d_type = bpy.props.EnumProperty(
        name="Microcode", items=enumF3D, default="F3D", update=update_all_material_nodes
    )

    # RDP Defaults
    World.rdp_defaults = bpy.props.PointerProperty(type=RDPSettings)
    World.menu_geo = bpy.props.BoolProperty()
    World.menu_upper = bpy.props.BoolProperty()
    World.menu_lower = bpy.props.BoolProperty()
    World.menu_other = bpy.props.BoolProperty()
    World.menu_layers = bpy.props.BoolProperty()

    Material.is_f3d = bpy.props.BoolProperty()
    Material.mat_ver = bpy.props.IntProperty(default=1)
    Material.f3d_update_flag = bpy.props.BoolProperty()
    Material.f3d_mat = bpy.props.PointerProperty(type=F3DMaterialProperty)
    Material.menu_tab = bpy.props.EnumProperty(items=menu_items_enum)

    Scene.f3dUserPresetsOnly = bpy.props.BoolProperty(name="User Presets Only")
    Scene.f3d_simple = bpy.props.BoolProperty(name="Display Simple", default=True)

    Object.use_f3d_culling = bpy.props.BoolProperty(
        name="Use Culling", description="F3DEX: Adds culling vertices", default=True
    )
    Object.ignore_render = bpy.props.BoolProperty(name="Ignore Render")
    Object.ignore_collision = bpy.props.BoolProperty(name="Ignore Collision")
    Object.bleed_independently = bpy.props.BoolProperty(
        name="Bleed Independently",
        description="While bleeding, this object will not inherit properties from previously drawn meshes in the drawing graph",
    )
    Object.f3d_lod_z = bpy.props.IntProperty(
        name="F3D LOD Z",
        min=1,
        default=10,
    )
    Object.f3d_lod_always_render_farthest = bpy.props.BoolProperty(name="Always Render Farthest LOD")
    Object.is_occlusion_planes = bpy.props.BoolProperty(name="Is Occlusion Planes")

    VIEW3D_HT_header.append(draw_f3d_render_settings)


def mat_unregister():
    VIEW3D_HT_header.remove(draw_f3d_render_settings)

    del Material.menu_tab
    del Material.f3d_mat
    del Material.is_f3d
    del Material.mat_ver
    del Material.f3d_update_flag
    del Scene.f3d_simple
    del Object.ignore_render
    del Object.ignore_collision
    del Object.bleed_independently
    del Object.use_f3d_culling
    del Scene.f3dUserPresetsOnly
    del Object.f3d_lod_z
    del Object.f3d_lod_always_render_farthest
    del Object.is_occlusion_planes

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
