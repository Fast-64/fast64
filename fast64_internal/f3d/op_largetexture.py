import bpy, mathutils, math
from bpy.utils import register_class, unregister_class
from ..utility import *
from .f3d_writer import getTexInfoFromMat


def getTexInfoForLarge(material):
    f3dMat = material.f3d_mat
    if f3dMat is None:
        return "This is not a Fast3D material.", None
    if not f3dMat.use_large_textures:
        return "This is not a large texture material.", None
    largeEdges = f3dMat.large_edges
    if f3dMat.rdp_settings.g_mdsft_text_filt == "G_TF_AVERAGE":
        return 'Texture filter "Average" not supported.', None
    bilinear = f3dMat.rdp_settings.g_mdsft_text_filt == "G_TF_BILERP"
    err0, info0 = getTexInfoFromMat(0, f3dMat)
    err1, info1 = getTexInfoFromMat(1, f3dMat)
    if err0 is not None:
        return err0, None
    if err1 is not None:
        return err1, None
    (useTex0, isTex0Ref, isTex0CI, tex0Fmt, _, imageDims0, tex0Tmem) = info0
    (useTex1, isTex1Ref, isTex1CI, tex1Fmt, _, imageDims1, tex1Tmem) = info1
    isCI = (useTex0 and isTex0CI) or (useTex1 and isTex1CI)
    tmemSize = 256 if isCI else 512
    if not useTex0 and not useTex1:
        return "Material does not use textures.", None
    if tex0Tmem + tex1Tmem <= tmemSize:
        return "Texture(s) fit in TMEM; not large.", None
    if useTex0 and useTex1:
        if tex0Tmem <= tmemSize // 2:
            largeDims = imageDims1
            largeFmt = tex1Fmt
            largeWords = tmemSize - tex0Tmem
        elif tex1Tmem <= tmemSize // 2:
            largeDims = imageDims0
            largeFmt = tex0Fmt
            largeWords = tmemSize - tex1Tmem
        else:
            return "Two large textures not supported.", None
    elif useTex0:
        largeDims = imageDims0
        largeFmt = tex0Fmt
        largeWords = tmemSize
    else:
        largeDims = imageDims1
        largeFmt = tex1Fmt
        largeWords = tmemSize
    return None, (largeDims, largeFmt, largeWords, largeEdges, bilinear)


class OpLargeTextureProperty(bpy.types.PropertyGroup):
    mat: bpy.props.PointerProperty(type=bpy.types.Material)
    clamp_border: bpy.props.FloatProperty(
        name="Extra border",
        description="Amount to extend mesh outwards with clamping from image. Set to 0 for no clamping, "
        + "or 0.5 for fast64 classic half-texel offset",
        default=0.5,
        min=0.0,
    )
    total_size_s: bpy.props.IntProperty(
        name="Total pixels S",
        description="Total number of texels in S after wrapping (e.g. 128 if you want to repeat a 64 size image twice)",
        default=256,
        min=0,
    )
    total_size_t: bpy.props.IntProperty(
        name="Total pixels T",
        description="Total number of texels in T after wrapping (e.g. 128 if you want to repeat a 64 size image twice)",
        default=256,
        min=0,
    )
    lose_pixels: bpy.props.BoolProperty(
        name="Lose pixels (drop thin tris at edges)",
        description="Discard thin tris, only a few pixels wide or high, at the edges of the image, "
        + "which are needed because bilinear interpolation requires loads to overlap by at least 1 pixel",
        default=False,
    )
    horizontal: bpy.props.BoolProperty(
        name="Horizontal Bias (faster)",
        description="Generate more horizontal loads and tris, which requires fewer memory transactions",
        default=True,
    )
    scale: bpy.props.FloatProperty(
        name="Scale (texel size)",
        description="Size of each texel in Blender scene units",
        default=0.1,
        min=0.0,
    )


def ui_oplargetexture(layout, context):
    layout = layout.box().column()
    prop = context.scene.opLargeTextureProperty
    layout.box().label(text="Create Large Texture Mesh:")
    prop_split(layout.row(), prop, "mat", "Large tex material:")
    if prop.mat is None:
        layout.row().label(text="Please select a material.")
        return
    err, info = getTexInfoForLarge(prop.mat)
    if err is not None:
        layout.row().label(icon="ERROR", text=err)
        return
    (largeDims, largeFmt, largeWords, largeEdges, bilinear) = info
    bilinInfo = "bilinear" if bilinear else "point sampled"
    sizeInfo = f", {largeDims[0]}x{largeDims[1]}" if largeEdges == "Clamp" else ""
    infoStr = f"{largeFmt}, {largeEdges} edges, {bilinInfo}{sizeInfo}"
    layout.row().label(icon="IMAGE", text=infoStr)
    if largeEdges == "Clamp":
        prop_split(layout.row(), prop, "clamp_border", "Extra border")
    else:
        prop_split(layout.row(), prop, "total_size_s", f"S: {largeDims[0]} / total:")
        prop_split(layout.row(), prop, "total_size_t", f"T: {largeDims[1]} / total:")
    if bilinear:
        layout.row().prop(prop, "lose_pixels")
    layout.row().prop(prop, "horizontal")
    prop_split(layout.row(), prop, "scale", "Scale (texel size)")
    layout.row().operator("scene.create_large_texture_mesh")


class CreateLargeTextureMesh(bpy.types.Operator):
    bl_idname = "scene.create_large_texture_mesh"
    bl_label = "Create Large Texture Mesh"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        return {"CANCELLED"}


op_largetexture_classes = (
    OpLargeTextureProperty,
    CreateLargeTextureMesh,
)


def op_largetexture_register():
    for cls in op_largetexture_classes:
        register_class(cls)

    bpy.types.Scene.opLargeTextureProperty = bpy.props.PointerProperty(type=OpLargeTextureProperty)


def op_largetexture_unregister():
    for cls in reversed(op_largetexture_classes):
        unregister_class(cls)

    del bpy.types.Scene.opLargeTextureProperty
