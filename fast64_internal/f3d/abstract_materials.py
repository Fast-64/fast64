import numpy as np
import dataclasses

import bpy
from bpy.types import (
    Mesh,
    Material,
    ShaderNodeOutputMaterial,
    ShaderNodeMixShader,
    ShaderNodeTexImage,
    ShaderNode,
)

from ..utility import get_clean_color

from .f3d_material import (
    combiner_uses,
    get_output_method,
    all_combiner_uses,
    trunc_10_2,
    F3DMaterialProperty,
    RDPSettings,
    TextureProperty,
    CombinerProperty,
)
from .f3d_gbi import isUcodeF3DEX3
from .f3d_writer import getColorLayer


# Ideally we'd use mathutils.Color here but it does not support alpha (and mul for some reason)
@dataclasses.dataclass
class Color:
    r: float = 1.0
    g: float = 1.0
    b: float = 1.0
    a: float = 1.0

    def wrap(self, min_value: float, max_value: float):
        def wrap_value(value, min_value=min_value, max_value=max_value):
            range_width = max_value - min_value
            return ((value - min_value) % range_width) + min_value

        return Color(wrap_value(self.r), wrap_value(self.g), wrap_value(self.b), wrap_value(self.a))

    def to_clean_list(self):
        def round_and_clamp(value):
            return round(max(min(value, 1.0), 0.0), 4)

        return [
            round_and_clamp(self.r),
            round_and_clamp(self.g),
            round_and_clamp(self.b),
            round_and_clamp(self.a),
        ]

    def __sub__(self, other):
        return Color(self.r - other.r, self.g - other.g, self.b - other.b, self.a - other.a)

    def __add__(self, other):
        return Color(self.r + other.r, self.g + other.g, self.b + other.b, self.a + other.a)

    def __mul__(self, other):
        return Color(self.r * other.r, self.g * other.g, self.b * other.b, self.a * other.a)

    def __iter__(self):
        yield self.r
        yield self.g
        yield self.b
        yield self.a

    def __getitem__(self, key: int):
        return list(self)[key]


def get_color_component(inp: str, f3d_mat: F3DMaterialProperty, previous_alpha: float) -> float:
    if inp == "0":
        return 0.0
    elif inp == "1":
        return 1.0
    elif inp.startswith("COMBINED"):
        return previous_alpha
    elif inp == "LOD_FRACTION":
        return 0.0  # Fast64 always uses black, let's do that for now
    elif inp == "PRIM_LOD_FRAC":
        return f3d_mat.prim_lod_frac
    elif inp == "PRIMITIVE_ALPHA":
        return f3d_mat.prim_color[3]
    elif inp == "ENV_ALPHA":
        return f3d_mat.env_color[3]
    elif inp == "K4":
        return f3d_mat.k4
    elif inp == "K5":
        return f3d_mat.k5


def get_color_from_input(inp: str, previous_color: Color, f3d_mat: F3DMaterialProperty, is_alpha: bool) -> Color:
    if inp == "COMBINED" and not is_alpha:
        return previous_color
    elif inp == "CENTER":
        return Color(*get_clean_color(f3d_mat.key_center), previous_color.a)
    elif inp == "SCALE":
        return Color(*list(f3d_mat.key_scale), previous_color.a)
    elif inp == "PRIMITIVE":
        return Color(*get_clean_color(f3d_mat.prim_color, True))
    elif inp == "ENVIRONMENT":
        return Color(*get_clean_color(f3d_mat.env_color, True))
    elif inp == "SHADE":
        if f3d_mat.rdp_settings.g_lighting and f3d_mat.set_lights and f3d_mat.use_default_lighting:
            return Color(*get_clean_color(f3d_mat.default_light_color), previous_color.a)
        return Color(1.0, 1.0, 1.0, previous_color.a)
    else:
        value = get_color_component(inp, f3d_mat, previous_color.a)
        if value is not None:
            return Color(value, value, value, value)
        return Color(1.0, 1.0, 1.0, 1.0)


def fake_color_from_cycle(cycle: list[str], previous_color: Color, f3d_mat: F3DMaterialProperty, is_alpha=False):
    a, b, c, d = [get_color_from_input(inp, previous_color, f3d_mat, is_alpha) for inp in cycle]
    sign_extended_c = c.wrap(-1.0, 1.0001)
    unwrapped_result = (a - b) * sign_extended_c + d
    result = unwrapped_result.wrap(-0.5, 1.5)
    if is_alpha:
        result = Color(previous_color.r, previous_color.g, previous_color.b, result.a)
    return result


def get_fake_color(f3d_mat: F3DMaterialProperty):
    """Try to emulate solid colors"""
    fake_color = Color()
    cycle: CombinerProperty
    combiners = [f3d_mat.combiner1]
    if f3d_mat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
        combiners.append(f3d_mat.combiner2)
    for cycle in combiners:
        fake_color = fake_color_from_cycle([cycle.A, cycle.B, cycle.C, cycle.D], fake_color, f3d_mat)
        fake_color = fake_color_from_cycle(
            [cycle.A_alpha, cycle.B_alpha, cycle.C_alpha, cycle.D_alpha], fake_color, f3d_mat, True
        )
    return fake_color.to_clean_list()


@dataclasses.dataclass
class AbstractedN64Texture:
    """Very abstracted representation of a N64 texture"""

    tex: bpy.types.Image
    offset: tuple[float, float] = (0.0, 0.0)
    scale: tuple[float, float] = (1.0, 1.0)
    repeat: bool = False
    set_color: bool = False
    set_alpha: bool = False
    packed_alpha: bool = False
    alpha_as_color: bool = False  # tex0 alpha, gathered in bsdf to f3d


@dataclasses.dataclass
class AbstractedN64Material:
    """Very abstracted representation of a N64 material"""

    lighting: bool = False
    uv_gen: bool = False
    point_filtering: bool = False
    vertex_color: str | None | bool = False
    vertex_alpha: str | None | bool = False
    alpha_is_median: bool = False
    backface_culling: bool = False
    output_method: str = "OPA"
    color: Color = dataclasses.field(default_factory=Color)
    textures: list[AbstractedN64Texture] = dataclasses.field(default_factory=list)
    texture_sets_col: bool = False
    texture_sets_alpha: bool = False
    uv_map: str = ""

    @property
    def main_texture(self):
        return self.textures[0] if self.textures else None


def f3d_tex_to_abstracted(f3d_tex: TextureProperty, set_color: bool, set_alpha: bool):
    def to_offset(low: float, tex_size: int):
        offset = -trunc_10_2(low) * (1.0 / tex_size)
        if offset == -0.0:
            offset = 0.0
        return offset

    if f3d_tex.tex is None:
        print("No texture set")

    abstracted_tex = AbstractedN64Texture(f3d_tex.tex, repeat=not f3d_tex.S.clamp or not f3d_tex.T.clamp)
    size = f3d_tex.tex_size
    if size != [0, 0]:
        abstracted_tex.offset = (to_offset(f3d_tex.S.low, size[0]), to_offset(f3d_tex.T.low, size[1]))
    abstracted_tex.scale = (2.0 ** (f3d_tex.S.shift * -1.0), 2.0 ** (f3d_tex.T.shift * -1.0))
    abstracted_tex.set_color, abstracted_tex.set_alpha = set_color, set_alpha
    abstracted_tex.packed_alpha = f3d_tex.tex_format in {"I4", "I8"}

    return abstracted_tex


def f3d_mat_to_abstracted(material: Material):
    f3d_mat: F3DMaterialProperty = material.f3d_mat
    rdp: RDPSettings = f3d_mat.rdp_settings
    use_dict = all_combiner_uses(f3d_mat)
    textures = [f3d_mat.tex0] if use_dict["Texture 0"] and f3d_mat.tex0.tex_set else []
    textures += [f3d_mat.tex1] if use_dict["Texture 1"] and f3d_mat.tex1.tex_set else []
    g_packed_normals = rdp.g_packed_normals if isUcodeF3DEX3(bpy.context.scene.f3d_type) else False
    abstracted_mat = AbstractedN64Material(
        rdp.g_lighting and use_dict["Shade"],
        rdp.g_tex_gen and rdp.g_lighting,
        rdp.g_mdsft_text_filt == "G_TF_POINT",
        (not rdp.g_lighting or g_packed_normals) and combiner_uses(f3d_mat, ["SHADE"], checkAlpha=False),
        not rdp.g_fog and combiner_uses(f3d_mat, ["SHADE"], checkColor=False),
        False,
        rdp.g_cull_back,
        get_output_method(material, True),
        get_fake_color(f3d_mat),
    )
    for i in range(2):
        tex_prop = getattr(f3d_mat, f"tex{i}")
        check_list = [f"TEXEL{i}", f"TEXEL{i}_ALPHA"]
        sets_color = combiner_uses(f3d_mat, check_list, checkColor=True, checkAlpha=False)
        sets_alpha = combiner_uses(f3d_mat, check_list, checkColor=False, checkAlpha=True)
        if sets_color or sets_alpha:
            abstracted_mat.textures.append(f3d_tex_to_abstracted(tex_prop, sets_color, sets_alpha))
        abstracted_mat.texture_sets_col |= sets_color
        abstracted_mat.texture_sets_alpha |= sets_alpha
    # print(abstracted_mat)
    return abstracted_mat


def get_gamma_corrected(layer):
    colors = np.empty((len(layer), 4), dtype=np.float32)
    if bpy.app.version > (3, 2, 0):
        layer.foreach_get("color", colors.ravel())
    else:  # vectorized linear -> sRGB conversion
        layer.foreach_get("color", colors.ravel())
        mask = colors > 0.0031308
        colors[mask] = 1.055 * (np.power(colors[mask], (1.0 / 2.4))) - 0.055
        colors[~mask] *= 12.0
    return colors.reshape((-1, 4))


RGB_TO_LUM_COEF = np.array([0.2126729, 0.7151522, 0.0721750], np.float32)  # blender rgb -> lum coefficient


def apply_alpha(blender_mesh: Mesh):
    color_layer = getColorLayer(blender_mesh, layer="Col")
    alpha_layer = getColorLayer(blender_mesh, layer="Alpha")
    if not color_layer or not alpha_layer:
        return
    color = get_gamma_corrected(color_layer)
    rgb_alpha = get_gamma_corrected(alpha_layer)

    alpha_median = np.dot(rgb_alpha[:, :3], RGB_TO_LUM_COEF)
    color[:, 3] = alpha_median

    color = color.flatten()
    color = color.clip(0.0, 1.0)  # clamp
    color_layer.foreach_set("color", color)


def find_output_node(material: Material):
    if not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if isinstance(node, ShaderNodeOutputMaterial) and node.is_active_output:
            return node
    return None


def find_mix_shader_with_transparent(material: Material):
    """
    Find mix shader with transparent BSDF, return first one's Fac input and the non transparent BSDF input
    """
    output_node = find_output_node(material)
    if output_node is None:
        return (None, None)

    # check if transparent bsdf is connected
    shaders: list[tuple[ShaderNodeMixShader, ShaderNode, ShaderNode]] = []
    for mix_shader in find_linked_nodes(output_node, lambda node: node.bl_idname == "ShaderNodeMixShader"):
        transparent, non_transparent = None, None
        for inp in mix_shader.inputs:
            if inp.name == "Fac" and not inp.links:
                continue
            link = inp.links[0]
            if link.from_node.bl_idname == "ShaderNodeBsdfTransparent":
                transparent = link.from_node
            else:
                non_transparent = link.from_node
        if transparent and non_transparent:
            shaders.append((mix_shader, transparent, non_transparent))

    if len(shaders) == 0:
        return (None, None)
    if len(shaders) > 1:
        print(f"WARNING: More than 1 transparent shader connected to a mix shader in {material.name}. Using first one.")
    mix_shader, _transparent_bsdf, non_transparent_bsdf = shaders[0]

    return mix_shader, non_transparent_bsdf


def find_linked_nodes(
    starting_node: ShaderNode | None,
    node_check: callable,
    specific_input_sockets: list[str] | None = None,
    specific_output_sockets: list[str] | None = None,
    verbose=False,  # small debug feature
):
    if starting_node is None:
        return []
    nodes: list[ShaderNode] = []
    for inp in starting_node.inputs:
        if specific_input_sockets is not None and inp.name not in specific_input_sockets:
            continue
        if verbose:
            print(f"Searching from {inp.name}")
        for link in inp.links:
            if specific_output_sockets is None or link.from_socket.name in specific_output_sockets:
                if verbose:
                    print(f"Checking {link.from_node.bl_idname} {link.from_socket.name}")
                if node_check(link.from_node):
                    nodes.append(link.from_node)
                    if verbose:
                        print("Valid node added, recursive search is skipped")
                    continue
            elif verbose:
                print(f"Skipped output socket {link.from_socket.name}")
            if verbose:
                print(f"Searching recursively in {link.from_node.bl_idname}")
            nodes.extend(find_linked_nodes(link.from_node, node_check, specific_output_sockets=specific_output_sockets))
    return list(dict.fromkeys(nodes).keys())


def bsdf_mat_to_abstracted(material: Material):
    abstracted_mat = AbstractedN64Material()

    output_node = find_output_node(material)
    if output_node is None:
        abstracted_mat.color = material.diffuse_color
        return abstracted_mat

    mix_shader, color_shader = find_mix_shader_with_transparent(material)
    using_mix_shader = mix_shader is not None and color_shader is not None
    if using_mix_shader:
        alpha_shader, alpha_inp = mix_shader, "Fac"
    else:  # no transparent mix shader, use the first found shader's inputs for searches
        shaders = find_linked_nodes(
            output_node,
            lambda node: node.bl_idname.startswith("ShaderNodeBsdf")
            or node.bl_idname.removeprefix("ShaderNode")
            in {"Background", "Emission", "SubsurfaceScattering", "VolumeAbsorption", "VolumeScatter"},
            specific_input_sockets={"Surface"},
        )
        if len(shaders) == 0:
            abstracted_mat.color = material.diffuse_color
            print(f"WARNING: No shader connected to {material.name}. Using default color.")
            return abstracted_mat
        if len(shaders) > 1:
            print(f"WARNING: More than 1 shader connected to {material.name}. Using first shader.")
        color_shader = alpha_shader = shaders[0]
        alpha_inp = "Alpha"
    if color_shader.bl_idname in {"Background", "Emission"}:  # is unlit
        abstracted_mat.lighting = False
    else:
        abstracted_mat.lighting = True

    # set color_inp to Base Color if the input exists, otherwise try Color, if neither work assert
    color_inp = next(("Base Color" for inp in color_shader.inputs if inp.name == "Base Color"), None)
    if color_inp is None:
        color_inp = next(("Color" for inp in color_shader.inputs if inp.name == "Color"), None)
    assert color_inp is not None, f"Could not find color input in {material.name}"

    # vertex colors
    def get_vtx_layer(nodes):
        layer_names = list(dict.fromkeys([node.layer_name for node in nodes]).keys())
        if len(layer_names) > 1:
            print(f"WARNING: More than 1 color layer used in {material.name}. Using first layer.")
        return layer_names[0]

    vtx_color_nodes = find_linked_nodes(
        color_shader,
        lambda node: node.bl_idname == "ShaderNodeVertexColor",
        specific_input_sockets={color_inp},
    )
    abstracted_mat.vertex_color = get_vtx_layer(vtx_color_nodes) if len(vtx_color_nodes) > 0 else None
    # vertex alpha can sometimes be derived from the mean of the color, this is done by the f3d to bsdf converter as well
    # because of this, we need to handle both cases
    real_vtx_alpha_nodes = find_linked_nodes(
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeVertexColor",
        specific_input_sockets={alpha_inp},
        specific_output_sockets={"Alpha"},
    )
    mean_vtx_alpha_nodes = find_linked_nodes(
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeVertexColor",
        specific_input_sockets={alpha_inp},
        specific_output_sockets={"Color"},
    )
    if real_vtx_alpha_nodes and mean_vtx_alpha_nodes:
        print(f"WARNING: Mixing real and averaged (from color) vertex alpha in {material.name}.")
    vtx_alpha_nodes = list(dict.fromkeys(real_vtx_alpha_nodes + mean_vtx_alpha_nodes).keys())
    abstracted_mat.vertex_alpha = get_vtx_layer(vtx_alpha_nodes) if len(vtx_alpha_nodes) > 0 else None
    abstracted_mat.alpha_is_median = len(mean_vtx_alpha_nodes) > 0

    # textures and their respective uv maps and properties like filtering and uvgen
    found_uv_map_nodes = []
    alpha_textures = find_linked_nodes(  # textures that use alpha as alpha
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeTexImage",
        specific_input_sockets={alpha_inp},
        specific_output_sockets={"Alpha"},
    )
    packed_textures = find_linked_nodes(  # textures that use color as alpha
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeTexImage",
        specific_input_sockets={alpha_inp},
        specific_output_sockets={"Color"},
    )
    color_textures = find_linked_nodes(  # textures that use color as color
        color_shader,
        lambda node: node.bl_idname == "ShaderNodeTexImage",
        specific_input_sockets={color_inp},
        specific_output_sockets={"Color"},
    )
    alpha_as_color_textures = find_linked_nodes(  # textures that use alpha as color
        color_shader,
        lambda node: node.bl_idname == "ShaderNodeTexImage",
        specific_input_sockets={color_inp},
        specific_output_sockets={"Alpha"},
    )
    textures: list[ShaderNodeTexImage] = list(
        dict.fromkeys(color_textures + alpha_as_color_textures + packed_textures + alpha_textures).keys()
    )
    if len(textures) > 2:
        print(f"WARNING: More than 2 textures connected to {material.name}.")
    for tex_node in textures[:2]:
        abstracted_tex = AbstractedN64Texture(tex_node.image)
        found_uv_map_nodes.extend(
            find_linked_nodes(
                tex_node,
                lambda node: node.bl_idname == "ShaderNodeUVMap",
                specific_input_sockets={"Vector"},
                specific_output_sockets={"UV"},
            )
        )
        mapping = find_linked_nodes(tex_node, lambda node: node.bl_idname == "ShaderNodeMapping")
        if len(mapping) > 1:
            print(f"WARNING: More than 1 mapping node connected to {tex_node.name}.")
        elif len(mapping) == 1:
            mapping = mapping[0]
            abstracted_tex.offset = tuple(mapping.inputs["Location"].default_value)
            abstracted_tex.scale = tuple(mapping.inputs["Scale"].default_value)
        uv_gen = find_linked_nodes(
            tex_node,
            lambda node: node.bl_idname == "ShaderNodeTexCoord",
            specific_input_sockets={"Vector"},
            specific_output_sockets={"Camera", "Window", "Reflection"},
        )
        if uv_gen:
            abstracted_mat.uv_gen = True
        if tex_node.interpolation == "Closest":
            abstracted_mat.point_filtering = True
        abstracted_tex.repeat = tex_node.extension == "REPEAT"
        abstracted_tex.set_color = tex_node in color_textures
        abstracted_tex.set_alpha = tex_node in alpha_textures
        abstracted_tex.packed_alpha = tex_node in packed_textures
        abstracted_tex.alpha_as_color = tex_node in alpha_as_color_textures
        if abstracted_tex.set_color:
            abstracted_mat.texture_sets_col = True
        if abstracted_tex.set_alpha:
            abstracted_mat.texture_sets_alpha = True
        abstracted_mat.textures.append(abstracted_tex)
    found_uv_map_names = list(dict.fromkeys([node.uv_map for node in found_uv_map_nodes]).keys())
    if len(found_uv_map_names) > 1:
        print(f"WARNING: More than 1 UV map being used in {material.name}. Using first UV map.")
    abstracted_mat.uv_map = found_uv_map_names[0] if len(found_uv_map_names) > 0 else ""

    # very simple search for color mul nodes, only really for glTF import support
    # (glTF materials can have tex multiplied by base color multiplied vertex colors + lighting!)

    def get_solid_color(nodes):
        solid_colors = []
        for node in nodes:
            solid_color, non_solid = None, False
            for inp in node.inputs:  # find all nodes that are multiplied by solid colors but have another input
                if not inp.name.startswith("Fac"):
                    if inp.links:
                        non_solid = True
                    else:
                        solid_color = inp.default_value
            if solid_color is not None and non_solid:
                solid_colors.append(solid_color)
        if len(solid_colors) > 1:
            print(
                f"WARNING: More than 1 solid color/alpha multiplied by a link node in {material.name}. Using first node."
            )
        if len(solid_colors) > 0:
            return solid_colors[0]

    solid_color = get_solid_color(
        find_linked_nodes(
            color_shader,
            lambda node: node.bl_idname.startswith("ShaderNodeMix") and node.blend_type == "MULTIPLY",
            specific_input_sockets={color_inp},
        )
    )
    if solid_color:
        assert hasattr(solid_color, "__iter__"), f"Expected list, got {type(solid_color)}"
        abstracted_mat.color = Color(*solid_color[:3], abstracted_mat.color.a)
    solid_alpha = get_solid_color(
        find_linked_nodes(
            alpha_shader,
            lambda node: node.bl_idname == "ShaderNodeMath" and node.operation == "MULTIPLY",
            specific_input_sockets={alpha_inp},
        )
    )
    if solid_alpha:
        assert isinstance(solid_alpha, float | int), f"Expected float, got {type(solid_alpha)}"
        abstracted_mat.color.a = solid_alpha

    # get default color shader values given no links
    if not color_shader.inputs[color_inp].links:
        abstracted_mat.color.r, abstracted_mat.color.g, abstracted_mat.color.b = color_shader.inputs[
            color_inp
        ].default_value[:3]
    if not alpha_shader.inputs[alpha_inp].links:
        abstracted_mat.color.a = alpha_shader.inputs[alpha_inp].default_value

    abstracted_mat.backface_culling = material.use_backface_culling
    if bpy.app.version < (4, 2, 0):  # before 4.2 we can just use the blend mode
        abstracted_mat.output_method = {"CLIP": "CLIP", "BLEND": "XLU"}.get(material.blend_method, "OPA")
    elif alpha_textures or abstracted_mat.color.a < 1.0:  # otherwise we check if alpha is not 1 or uses a texture
        abstracted_mat.output_method = "XLU"
    # check if there is a "clip" node connected to alpha
    greater_than_nodes = find_linked_nodes(
        alpha_shader,
        lambda node: node.bl_idname == "ShaderNodeMath" and node.operation == "GREATER_THAN",
        specific_input_sockets={alpha_inp},
    )
    if len(greater_than_nodes) > 0:
        abstracted_mat.output_method = "CLIP"
    return abstracted_mat
