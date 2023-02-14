import bpy, mathutils, math, bmesh
from mathutils import Vector
from bpy.utils import register_class, unregister_class
from ..utility import *
from .f3d_enums import texBitSizeInt
from .f3d_material import getTmemWordUsage
from .f3d_texture_writer import TexInfo


def getLargeTextureInfo(material):
    f3dMat = material.f3d_mat
    if f3dMat is None:
        return "This is not a Fast3D material.", None
    if not f3dMat.use_large_textures:
        return "This is not a large texture material.", None
    largeEdges = f3dMat.large_edges
    if f3dMat.rdp_settings.g_mdsft_text_filt == "G_TF_AVERAGE":
        return 'Texture filter "Average" not supported.', None
    bilinear = f3dMat.rdp_settings.g_mdsft_text_filt == "G_TF_BILERP"
    ti0, ti1 = TexInfo(), TexInfo()
    if not ti0.fromMat(0, f3dMat):
        return ti0.errorMsg, None
    if not ti1.fromMat(1, f3dMat):
        return ti1.errorMsg, None
    isCI = ti0.isTexCI or ti1.isTexCI
    tmemSize = 256 if isCI else 512
    if not ti0.useTex and not ti1.useTex:
        return "Material does not use textures.", None
    if ti0.tmemSize + ti1.tmemSize <= tmemSize:
        return "Texture(s) fit in TMEM; not large.", None
    if ti0.useTex and ti1.useTex:
        if ti0.tmemSize <= tmemSize // 2:
            largeDims = ti1.imageDims
            largeFmt = ti1.texFormat
            largeWords = tmemSize - ti0.tmemSize
        elif ti1.tmemSize <= tmemSize // 2:
            largeDims = ti0.imageDims
            largeFmt = ti0.texFormat
            largeWords = tmemSize - ti1.tmemSize
        else:
            return "Two large textures not supported.", None
    elif ti0.useTex:
        largeDims = ti0.imageDims
        largeFmt = ti0.texFormat
        largeWords = tmemSize
    else:
        largeDims = ti1.imageDims
        largeFmt = ti1.texFormat
        largeWords = tmemSize
    return None, (largeDims, largeFmt, largeWords, largeEdges, bilinear)


enumOpLTBias = [
    (
        "Square",
        "Square (~1x1)",
        "Almost square loads, rounded up to nearest line. For meshes which will be deformed (e.g. circular) if results with Weak are not acceptable",
    ),
    ("Weak", "Weak (1x1/2x1)", "Square or twice-width loads, depending on format and free memory, e.g. 32x32 or 64x32"),
    ("Moderate", "Moderate (4x1/2x1)", "Width 4x or 2x height, e.g. 64x16 or 64x32. Good efficiency balance"),
    (
        "Strong",
        "Strong (4x1/8x1)",
        "Width 4x or 8x height, e.g. 64x16 or 128x16. More efficient than Moderate if geometry usually viewed roughly straight-on",
    ),
    (
        "Extreme",
        "Extreme (ortho+point only)",
        "Maximum width, up to full texture rows. Maximum efficiency if geometry always aligned to camera (orthographic) and point sampled. Inefficient otherwise",
    ),
]


class OpLargeTextureProperty(bpy.types.PropertyGroup):
    mat: bpy.props.PointerProperty(type=bpy.types.Material)
    clamp_border: bpy.props.FloatProperty(
        name="Extra clamped border",
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
    bias: bpy.props.EnumProperty(
        items=enumOpLTBias,
        name="Bias (see tooltips)",
        description="Generate more horizontal loads and tris, which requires fewer memory transactions",
        default="Moderate",
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
    err, info = getLargeTextureInfo(prop.mat)
    if err is not None:
        layout.row().label(icon="ERROR", text=err)
        return
    (largeDims, largeFmt, largeWords, largeEdges, bilinear) = info
    bilinInfo = "bilinear" if bilinear else "point sampled"
    sizeInfo = f", {largeDims[0]}x{largeDims[1]}" if largeEdges == "Clamp" else ""
    infoStr = f"{largeFmt}, {largeEdges} edges, {bilinInfo}{sizeInfo}"
    layout.row().label(icon="TEXTURE", text=infoStr)
    if largeEdges == "Clamp":
        prop_split(layout.row(), prop, "clamp_border", "Extra clamped border")
        if bilinear:
            layout.row().prop(prop, "lose_pixels")
    else:
        prop_split(layout.row(), prop, "total_size_s", f"S: {largeDims[0]} / total:")
        prop_split(layout.row(), prop, "total_size_t", f"T: {largeDims[1]} / total:")
    prop_split(layout.row(), prop, "bias", "Bias (see tooltips)")
    prop_split(layout.row(), prop, "scale", "Scale (texel size)")
    layout.row().operator("scene.create_large_texture_mesh")


def createLargeTextureMeshInternal(bm, prop):
    # Parameters setup
    err, info = getLargeTextureInfo(prop.mat)
    if err is not None:
        raise PluginError(err)
    (largeDims, largeFmt, largeWords, largeEdges, bilinear) = info
    is4bit = texBitSizeInt[largeFmt] == 4
    texelsPerWord = 64 // texBitSizeInt[largeFmt]
    uvScale = [1.0 / largeDims[0], 1.0 / largeDims[1]]
    wrapSize = [prop.total_size_s, prop.total_size_t]
    # Set up base tile size
    if prop.bias == "Square":
        maxTexelsInTMEM = largeWords * texelsPerWord
        tileSWords = int(math.ceil(math.sqrt(maxTexelsInTMEM) / texelsPerWord))
    elif prop.bias == "Extreme":
        targetRows = 4 if bilinear else 2
        # Start with just loading full texture rows, rounded up to lines
        tileSWords = int(math.ceil(largeDims[0] / texelsPerWord))
        if largeWords // tileSWords < targetRows:
            # If that doesn't give us enough rows, reduce to next power of 2
            d = roundDownToPowerOf2(largeDims[0])
            tileSWords = d // texelsPerWord
            while largeWords // tileSWords < targetRows:
                tileSWords >>= 1
    else:
        baseTile = [128, 64]
        while True:
            if getTmemWordUsage(largeFmt, baseTile[0], baseTile[1]) <= largeWords:
                break
            baseTile[0] >>= 1
            if getTmemWordUsage(largeFmt, baseTile[0], baseTile[1]) <= largeWords:
                break
            baseTile[1] >>= 1
        if baseTile[0] == baseTile[1]:
            shift = 0 if prop.bias == "Weak" else 1
        else:
            assert baseTile[0] == baseTile[1] << 1
            shift = 1 if prop.bias == "Strong" else 0
        baseTile[0] <<= shift
        # Even though we have baseTile already, convert back to this format,
        # in case available TMEM is not a power of 2 we might get a larger T value.
        # (Currently the plugin will always assign a power of 2 size)
        tileSWords = baseTile[0] // texelsPerWord
    baseTile = [tileSWords * texelsPerWord, largeWords // tileSWords]
    if bilinear:
        baseTile[0] -= 1
        if is4bit:
            baseTile[0] &= ~1
        baseTile[1] -= 1
    print(f"Base tile size: {baseTile[0]}x{baseTile[1]}")
    # Mesh setup
    bm.clear()
    uvlayer = bm.loops.layers.uv.new("UVMap")

    def addGrid(svals, tvals):
        ns, nt = len(svals), len(tvals)
        verts = []
        for t in tvals:
            for s in svals:
                verts.append(bm.verts.new((s * prop.scale, 0.0, -t * prop.scale)))
        bm.verts.index_update()
        faces = []
        for ti in range(nt - 1):
            for si in range(ns - 1):
                faces.append(
                    bm.faces.new(
                        (
                            verts[ti * ns + (si + 1)],
                            verts[ti * ns + si],
                            verts[(ti + 1) * ns + si],
                            verts[(ti + 1) * ns + (si + 1)],
                        )
                    )
                )
        bm.faces.index_update()
        for ti in range(nt - 1):
            for si in range(ns - 1):
                f = faces[ti * (ns - 1) + si]

                def getUV(ds, dt):
                    return Vector((svals[si + ds] * uvScale[0], 1.0 - tvals[ti + dt] * uvScale[1]))

                f.loops[0][uvlayer].uv = getUV(1, 0)
                f.loops[1][uvlayer].uv = getUV(0, 0)
                f.loops[2][uvlayer].uv = getUV(0, 1)
                f.loops[3][uvlayer].uv = getUV(1, 1)

    def clampGridDim(dim):
        vals = [-prop.clamp_border]
        d = baseTile[dim]
        imHi = largeDims[dim] - (1 if bilinear else 0)
        while d < imHi:
            vals.append(d)
            d += baseTile[dim]
        if not bilinear or not prop.lose_pixels or d == imHi:
            vals.append(imHi + prop.clamp_border)
        return vals

    def wrapGridDim(dim):
        # Could create a new grid for wrap tris at the edges, because their loads
        # can often be combined due to their smaller sizes. However, this would
        # produce a mesh with verts on other edges, and the N64 does not guarantee
        # that these meshes won't have holes in them. Prefer correct seamless results
        # over saving a few tri draws (the loads will still be combined).
        distFromWrap = (texelsPerWord, 2)[dim]
        # Number of texels such that if a wrap load could reach the end of the drawn
        # region by continuing to load this many texels into the image after wrapping,
        # it's worth it to do so (as opposed to only loading row/col 0, and drawing
        # the rest with a new tri which shares the load at the beginning of the image).
        worthItExtraEnd = max(baseTile[dim] // 8, distFromWrap) if bilinear else 0
        vals = [0]
        d = 0
        while True:
            assert d <= wrapSize[dim]
            if d == wrapSize[dim]:
                break
            nextWrapBdry = (int(math.floor(d / largeDims[dim])) + 1) * largeDims[dim]
            if wrapSize[dim] < nextWrapBdry:
                nextWrapBdry = 1000000
            if nextWrapBdry - d <= baseTile[dim]:
                # Wrap/edge tile
                if (nextWrapBdry - d) % distFromWrap != 0:
                    raise PluginError("Bug: nextWrapBdry constraint violated")
                if wrapSize[dim] - d <= baseTile[dim] and wrapSize[dim] - baseTile[dim] <= worthItExtraEnd:
                    d = wrapSize[dim]
                else:
                    d = nextWrapBdry
            elif wrapSize[dim] - d <= baseTile[dim]:
                # Final tile, not at the edge
                d = wrapSize[dim]
            else:
                # Normal tile
                d += baseTile[dim]
                if nextWrapBdry - d <= baseTile[dim]:
                    # Round up next wrap/edge tile to its constraint, so round down this
                    d -= nextWrapBdry
                    d = int(math.floor(d / distFromWrap)) * distFromWrap
                    d += nextWrapBdry
            vals.append(d)
        return vals

    func = clampGridDim if largeEdges == "Clamp" else wrapGridDim
    addGrid(func(0), func(1))


class CreateLargeTextureMesh(bpy.types.Operator):
    bl_idname = "scene.create_large_texture_mesh"
    bl_label = "Create Large Texture Mesh"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        bpy.ops.object.select_all(action="DESELECT")
        prop = context.scene.opLargeTextureProperty
        assert prop.mat is not None
        name = prop.mat.name + "Mesh"
        mesh = context.blend_data.meshes.new(name)
        obj = context.blend_data.objects.new(name, mesh)
        mesh.materials.append(prop.mat)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        createLargeTextureMeshInternal(bm, prop)
        bm.to_mesh(mesh)
        bm.free()
        bpy.context.collection.objects.link(obj)
        obj.parent_type = "OBJECT"
        for o in context.scene.objects:
            if o.name.startswith("Room"):
                obj.parent = o
                break
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.view3d.view_selected()
        self.report({"INFO"}, f"Created large texture mesh {name}.")
        return {"FINISHED"}  # must return a set


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
