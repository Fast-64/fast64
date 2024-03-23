combiner_enums = {
    "Case A": (
        ("COMBINED", "Combined Color", "Combined Color"),
        ("TEXEL0", "Texture 0 Color", "Texture 0 Color"),
        ("TEXEL1", "Texture 1 Color", "Texture 1 Color"),
        ("PRIMITIVE", "Primitive Color", "Primitive Color"),
        ("SHADE", "Shade Color", "Shade Color"),
        ("ENVIRONMENT", "Environment Color", "Environment Color"),
        ("1", "1", "1"),
        ("NOISE", "Noise", "Noise"),
        ("0", "0", "0"),
    ),
    "Case B": (
        ("COMBINED", "Combined Color", "Combined Color"),
        ("TEXEL0", "Texture 0 Color", "Texture 0 Color"),
        ("TEXEL1", "Texture 1 Color", "Texture 1 Color"),
        ("PRIMITIVE", "Primitive Color", "Primitive Color"),
        ("SHADE", "Shade Color", "Shade Color"),
        ("ENVIRONMENT", "Environment Color", "Environment Color"),
        ("CENTER", "Chroma Key Center", "Chroma Key Center"),
        ("K4", "YUV Convert K4", "YUV Convert K4"),
        ("0", "0", "0"),
    ),
    "Case C": (
        ("COMBINED", "Combined Color", "Combined Color"),
        ("TEXEL0", "Texture 0 Color", "Texture 0 Color"),
        ("TEXEL1", "Texture 1 Color", "Texture 1 Color"),
        ("PRIMITIVE", "Primitive Color", "Primitive Color"),
        ("SHADE", "Shade Color", "Shade Color"),
        ("ENVIRONMENT", "Environment Color", "Environment Color"),
        ("SCALE", "Chroma Key Scale", "Chroma Key Scale"),
        ("COMBINED_ALPHA", "Combined Color Alpha", "Combined Color Alpha"),
        ("TEXEL0_ALPHA", "Texture 0 Alpha", "Texture 0 Alpha"),
        ("TEXEL1_ALPHA", "Texture 1 Alpha", "Texture 1 Alpha"),
        ("PRIMITIVE_ALPHA", "Primitive Color Alpha", "Primitive Color Alpha"),
        ("SHADE_ALPHA", "Shade Color Alpha", "Shade Color Alpha"),
        ("ENV_ALPHA", "Environment Color Alpha", "Environment Color Alpha"),
        ("LOD_FRACTION", "LOD Fraction", "LOD Fraction"),
        ("PRIM_LOD_FRAC", "Primitive LOD Fraction", "Primitive LOD Fraction"),
        ("K5", "YUV Convert K5", "YUV Convert K5"),
        ("0", "0", "0"),
    ),
    "Case D": (
        ("COMBINED", "Combined Color", "Combined Color"),
        ("TEXEL0", "Texture 0 Color", "Texture 0 Color"),
        ("TEXEL1", "Texture 1 Color", "Texture 1 Color"),
        ("PRIMITIVE", "Primitive Color", "Primitive Color"),
        ("SHADE", "Shade Color", "Shade Color"),
        ("ENVIRONMENT", "Environment Color", "Environment Color"),
        ("1", "1", "1"),
        ("0", "0", "0"),
    ),
    "Case A Alpha": (
        ("COMBINED", "Combined Color Alpha", "Combined Color Alpha"),
        ("TEXEL0", "Texture 0 Alpha", "Texture 0 Alpha"),
        ("TEXEL1", "Texture 1 Alpha", "Texture 1 Alpha"),
        ("PRIMITIVE", "Primitive Color Alpha", "Primitive Color Alpha"),
        ("SHADE", "Shade Color Alpha", "Shade Color Alpha"),
        ("ENVIRONMENT", "Environment Color Alpha", "Environment Color Alpha"),
        ("1", "1", "1"),
        ("0", "0", "0"),
    ),
    "Case B Alpha": (
        ("COMBINED", "Combined Color Alpha", "Combined Color Alpha"),
        ("TEXEL0", "Texture 0 Alpha", "Texture 0 Alpha"),
        ("TEXEL1", "Texture 1 Alpha", "Texture 1 Alpha"),
        ("PRIMITIVE", "Primitive Color Alpha", "Primitive Color Alpha"),
        ("SHADE", "Shade Color Alpha", "Shade Color Alpha"),
        ("ENVIRONMENT", "Environment Color Alpha", "Environment Color Alpha"),
        ("1", "1", "1"),
        ("0", "0", "0"),
    ),
    "Case C Alpha": (
        ("LOD_FRACTION", "LOD Fraction", "LOD Fraction"),
        ("TEXEL0", "Texture 0 Alpha", "Texture 0 Alpha"),
        ("TEXEL1", "Texture 1 Alpha", "Texture 1 Alpha"),
        ("PRIMITIVE", "Primitive Color Alpha", "Primitive Color Alpha"),
        ("SHADE", "Shade Color Alpha", "Shade Color Alpha"),
        ("ENVIRONMENT", "Environment Color Alpha", "Environment Color Alpha"),
        ("PRIM_LOD_FRAC", "Primitive LOD Fraction", "Primitive LOD Fraction"),
        ("0", "0", "0"),
    ),
    "Case D Alpha": (
        ("COMBINED", "Combined Color Alpha", "Combined Color Alpha"),
        ("TEXEL0", "Texture 0 Alpha", "Texture 0 Alpha"),
        ("TEXEL1", "Texture 1 Alpha", "Texture 1 Alpha"),
        ("PRIMITIVE", "Primitive Color Alpha", "Primitive Color Alpha"),
        ("SHADE", "Shade Color Alpha", "Shade Color Alpha"),
        ("ENVIRONMENT", "Environment Color Alpha", "Environment Color Alpha"),
        ("1", "1", "1"),
        ("0", "0", "0"),
    ),
}

caseTemplateDict = {
    "Case A": "NodeSocketColor",
    "Case B": "NodeSocketColor",
    "Case C": "NodeSocketColor",
    "Case D": "NodeSocketColor",
    "Case A Alpha": "NodeSocketFloat",
    "Case B Alpha": "NodeSocketFloat",
    "Case C Alpha": "NodeSocketFloat",
    "Case D Alpha": "NodeSocketFloat",
}

otherTemplateDict = {
    "Cycle Type": "NodeSocketFloat",
    "Cull Front": "NodeSocketFloat",
    "Cull Back": "NodeSocketFloat",
}

# Given combiner value, find node and socket index
combinerToNodeDictColor = {
    "COMBINED": (None, 0),
    "TEXEL0": ("Get Texture Color", 0),
    "TEXEL1": ("Get Texture Color.001", 0),
    "PRIMITIVE": ("Primitive Color RGB", 0),
    "SHADE": ("Shade Color", 0),
    "ENVIRONMENT": ("Environment Color RGB", 0),
    "CENTER": ("Chroma Key Center", 0),
    "SCALE": ("Chroma Key Scale", 0),
    "COMBINED_ALPHA": (None, 0),
    "TEXEL0_ALPHA": ("Get Texture Color", 1),
    "TEXEL1_ALPHA": ("Get Texture Color.001", 1),
    "PRIMITIVE_ALPHA": ("Primitive Color Alpha", 0),
    "SHADE_ALPHA": ("Shade Color", 1),
    "ENV_ALPHA": ("Environment Color Alpha", 0),
    "LOD_FRACTION": ("LOD Fraction", 0),
    "PRIM_LOD_FRAC": ("Primitive LOD Fraction", 0),
    "NOISE": ("Noise", 0),
    "K4": ("YUV Convert K4", 0),
    "K5": ("YUV Convert K5", 0),
    "1": ("1", 0),
    "0": ("0", 0),
}

combinerToNodeDictAlpha = {
    "COMBINED": (None, 1),
    "TEXEL0": ("Get Texture Color", 1),
    "TEXEL1": ("Get Texture Color.001", 1),
    "PRIMITIVE": ("Primitive Color Alpha", 0),
    "SHADE": ("Shade Color", 1),
    "ENVIRONMENT": ("Environment Color Alpha", 0),
    "LOD_FRACTION": ("LOD Fraction", 0),
    "PRIM_LOD_FRAC": ("Primitive LOD Fraction", 0),
    "1": ("1", 0),
    "0": ("0", 0),
}

# hardware v2
enumAlphaDither = [
    ("G_AD_PATTERN", "Pattern", "Pattern"),
    ("G_AD_NOTPATTERN", "NOT Pattern", "NOT Pattern"),
    ("G_AD_NOISE", "Noise", "Noise"),
    ("G_AD_DISABLE", "Disable", "Disable"),
]

# hardware v2
enumRGBDither = [
    ("G_CD_MAGICSQ", "Magic Square", "Magic Square"),
    ("G_CD_BAYER", "Bayer", "Bayer"),
    ("G_CD_NOISE", "Noise", "Noise"),
    ("G_CD_DISABLE", "Disable", "Disable"),
    ("G_CD_ENABLE", "Enable", "Enable"),
]

enumCombKey = [
    ("G_CK_NONE", "None", "Disables chroma key."),
    ("G_CK_KEY", "Key", "Enables chroma key."),
]

enumTextConv = [
    ("G_TC_CONV", "Convert", "Convert YUV to RGB"),
    (
        "G_TC_FILTCONV",
        "Filter And Convert",
        "Applies chosen filter on cycle 1 and converts YUB to RGB in the second cycle",
    ),
    ("G_TC_FILT", "Filter", "Applies chosen filter on textures with no color conversion"),
]

enumTextFilt = [
    ("G_TF_POINT", "Point", "Point filtering"),
    ("G_TF_AVERAGE", "Average", "Four sample filter, not recommended except for pixel aligned texrects"),
    ("G_TF_BILERP", "Bilinear", "Standard N64 filtering with 3 point sample"),
]

enumTextLUT = [
    ("G_TT_NONE", "None", "None"),
    ("G_TT_RGBA16", "RGBA16", "RGBA16"),
    ("G_TT_IA16", "IA16", "IA16"),
]

enumTextLOD = [
    ("G_TL_TILE", "Tile", "Shows selected color combiner tiles"),
    (
        "G_TL_LOD",
        "LoD",
        "Enables LoD calculations, LoD tile is base tile + clamp(log2(texel/pixel)), remainder of log2(texel/pixel) ratio gets stored to LoD Fraction in the color combiner",
    ),
]

enumTextDetail = [
    (
        "G_TD_CLAMP",
        "Clamp",
        "Shows base tile for texel0 and texel 1 when magnifying (>1 texel/pixel), else shows LoD tiles",
    ),
    ("G_TD_SHARPEN", "Sharpen", "Sharpens pixel colors when magnifying (<1 texel/pixel), always shows LoD tiles"),
    ("G_TD_DETAIL", "Detail", "Shows base tile when magnifying (<1 texel/pixel), else shows LoD tiles + 1"),
]

enumTextPersp = [
    ("G_TP_NONE", "None", "None"),
    ("G_TP_PERSP", "Perspective", "Perspective"),
]

enumCycleType = [
    ("G_CYC_1CYCLE", "1 Cycle", "1 Cycle"),
    ("G_CYC_2CYCLE", "2 Cycle", "2 Cycle"),
    ("G_CYC_COPY", "Copy", "Copies texture values to framebuffer with no perspective correction or blending"),
    ("G_CYC_FILL", "Fill", "Uses fill color to fill primitve"),
]

enumColorDither = [("G_CD_DISABLE", "Disable", "Disable"), ("G_CD_ENABLE", "Enable", "Enable")]

enumPipelineMode = [
    (
        "G_PM_1PRIMITIVE",
        "1 Primitive",
        "Adds in pipe sync after every tri draw. Adds significant amounts of lag. Only use in vanilla SM64 hacking projects",
    ),
    (
        "G_PM_NPRIMITIVE",
        "N Primitive",
        "No additional syncs are added after tri draws. Default option for every game but vanilla SM64",
    ),
]

enumAlphaCompare = [
    ("G_AC_NONE", "None", "No alpha comparison is made, writing is based on coverage"),
    ("G_AC_THRESHOLD", "Threshold", "Writes if alpha is greater than blend color alpha"),
    ("G_AC_DITHER", "Dither", "Writes if alpha is greater than random value"),
]

enumDepthSource = [
    ("G_ZS_PIXEL", "Pixel", "Z value is calculated per primitive pixel"),
    ("G_ZS_PRIM", "Primitive", "Uses prim depth to set Z value, does not work on HLE emulation"),
]

enumCoverage = [
    ("CVG_DST_CLAMP", "Clamp", "Clamp if blending, else use new pixel coverage"),
    ("CVG_DST_WRAP", "Wrap", "Wrap coverage"),
    ("CVG_DST_FULL", "Full", "Force to full coverage"),
    ("CVG_DST_SAVE", "Save", "Don't overwrite previous framebuffer coverage value"),
]

enumZMode = [
    ("ZMODE_OPA", "Opaque", "Opaque"),
    ("ZMODE_INTER", "Interpenetrating", "Interpenetrating"),
    ("ZMODE_XLU", "Transparent (XLU)", "Transparent (XLU)"),
    ("ZMODE_DEC", "Decal", "Decal"),
]

enumBlendColor = [
    (
        "G_BL_CLR_IN",
        "Input (CC/Blender)",
        "First cycle: Color Combiner RGB, Second cycle: Blender numerator from first cycle",
    ),
    ("G_BL_CLR_MEM", "Framebuffer Color", "Framebuffer (Memory) Color"),
    ("G_BL_CLR_BL", "Blend Color", "Blend Color Register"),
    ("G_BL_CLR_FOG", "Fog Color", "Fog Color Register"),
]

enumBlendAlpha = [
    ("G_BL_A_IN", "Color Combiner Alpha", "Color Combiner Alpha"),
    ("G_BL_A_FOG", "Fog Alpha", "Fog Color Register Alpha"),
    ("G_BL_A_SHADE", "Shade Alpha", "Stepped Shade Alpha from RSP, often fog"),
    ("G_BL_0", "0", "0"),
]

enumBlendMix = [
    ("G_BL_1MA", "1 - A", "1 - A, where A is selected above"),
    ("G_BL_A_MEM", "Framebuffer Alpha", "Framebuffer (Memory) Alpha (Coverage)"),
    ("G_BL_1", "1", "1"),
    ("G_BL_0", "0", "0"),
]

enumRenderModesCycle1 = [
    # ('Use Draw Layer', 'Use Draw Layer', 'Use Draw Layer'),
    ("G_RM_ZB_OPA_SURF", "Background", "G_RM_ZB_OPA_SURF"),
    ("G_RM_AA_ZB_OPA_SURF", "Opaque", "G_RM_AA_ZB_OPA_SURF"),
    ("G_RM_AA_ZB_OPA_DECAL", "Opaque Decal", "G_RM_AA_ZB_OPA_DECAL"),
    ("G_RM_AA_ZB_OPA_INTER", "Opaque Intersecting", "G_RM_AA_ZB_OPA_INTER"),
    ("G_RM_AA_ZB_TEX_EDGE", "Cutout", "G_RM_AA_ZB_TEX_EDGE"),
    ("G_RM_AA_ZB_XLU_SURF", "Transparent", "G_RM_AA_ZB_XLU_SURF"),
    ("G_RM_AA_ZB_XLU_DECAL", "Transparent Decal", "G_RM_AA_ZB_XLU_DECAL"),
    ("G_RM_AA_ZB_XLU_INTER", "Transparent Intersecting", "G_RM_AA_ZB_XLU_INTER"),
    ("G_RM_FOG_SHADE_A", "Fog Shade", "G_RM_FOG_SHADE_A"),
    ("G_RM_FOG_PRIM_A", "Fog Primitive", "G_RM_FOG_PRIM_A"),
    ("G_RM_PASS", "Pass", "G_RM_PASS"),
    ("G_RM_ADD", "Add", "G_RM_ADD"),
    ("G_RM_NOOP", "No Op", "G_RM_NOOP"),
    ("G_RM_ZB_OPA_SURF", "Opaque (No AA)", "G_RM_ZB_OPA_SURF"),
    ("G_RM_ZB_OPA_DECAL", "Opaque Decal (No AA)", "G_RM_ZB_OPA_DECAL"),
    ("G_RM_ZB_XLU_SURF", "Transparent (No AA)", "G_RM_ZB_XLU_SURF"),
    ("G_RM_ZB_XLU_DECAL", "Transparent Decal (No AA)", "G_RM_ZB_XLU_DECAL"),
    ("G_RM_OPA_SURF", "Opaque (No AA, No ZBuf)", "G_RM_OPA_SURF"),
    ("G_RM_ZB_CLD_SURF", "Cloud (No AA)", "G_RM_ZB_CLD_SURF"),
    ("G_RM_AA_ZB_TEX_TERR", "Terrain", "G_RM_AA_ZB_TEX_TERR"),
]

enumRenderModesCycle2 = [
    # ('Use Draw Layer', 'Use Draw Layer', 'Use Draw Layer'),
    ("G_RM_ZB_OPA_SURF2", "Background", "G_RM_ZB_OPA_SURF2"),
    ("G_RM_AA_ZB_OPA_SURF2", "Opaque", "G_RM_AA_ZB_OPA_SURF2"),
    ("G_RM_AA_ZB_OPA_DECAL2", "Opaque Decal", "G_RM_AA_ZB_OPA_DECAL2"),
    ("G_RM_AA_ZB_OPA_INTER2", "Opaque Intersecting", "G_RM_AA_ZB_OPA_INTER2"),
    ("G_RM_AA_ZB_TEX_EDGE2", "Cutout", "G_RM_AA_ZB_TEX_EDGE2"),
    ("G_RM_AA_ZB_XLU_SURF2", "Transparent", "G_RM_AA_ZB_XLU_SURF2"),
    ("G_RM_AA_ZB_XLU_DECAL2", "Transparent Decal", "G_RM_AA_ZB_XLU_DECAL2"),
    ("G_RM_AA_ZB_XLU_INTER2", "Transparent Intersecting", "G_RM_AA_ZB_XLU_INTER2"),
    ("G_RM_ADD2", "Add", "G_RM_ADD2"),
    ("G_RM_NOOP", "No Op", "G_RM_NOOP"),
    ("G_RM_ZB_OPA_SURF2", "Opaque (No AA)", "G_RM_ZB_OPA_SURF2"),
    ("G_RM_ZB_OPA_DECAL2", "Opaque Decal (No AA)", "G_RM_ZB_OPA_DECAL2"),
    ("G_RM_ZB_XLU_SURF2", "Transparent (No AA)", "G_RM_ZB_XLU_SURF2"),
    ("G_RM_ZB_XLU_DECAL2", "Transparent Decal (No AA)", "G_RM_ZB_XLU_DECAL2"),
    ("G_RM_ZB_CLD_SURF2", "Cloud (No AA)", "G_RM_ZB_CLD_SURF2"),
    ("G_RM_ZB_OVL_SURF2", "Overlay (No AA)", "G_RM_ZB_OVL_SURF2"),
    ("G_RM_AA_ZB_TEX_TERR2", "Terrain", "G_RM_AA_ZB_TEX_TERR2"),
    ("G_RM_OPA_SURF2", "Opaque (No AA, No ZBuf)", "G_RM_OPA_SURF2"),
]

enumTexFormat = [
    ("I4", "Intensity 4-bit", "Intensity 4-bit"),
    ("I8", "Intensity 8-bit", "Intensity 8-bit"),
    ("IA4", "Intensity Alpha 4-bit", "Intensity Alpha 4-bit"),
    ("IA8", "Intensity Alpha 8-bit", "Intensity Alpha 8-bit"),
    ("IA16", "Intensity Alpha 16-bit", "Intensity Alpha 16-bit"),
    ("CI4", "Color Index 4-bit", "Color Index 4-bit"),
    ("CI8", "Color Index 8-bit", "Color Index 8-bit"),
    ("RGBA16", "RGBA 16-bit", "RGBA 16-bit"),
    ("RGBA32", "RGBA 32-bit", "RGBA 32-bit"),
    # ('YUV16','YUV 16-bit', 'YUV 16-bit'),
]

enumCIFormat = [
    ("RGBA16", "RGBA 16-bit", "RGBA 16-bit"),
    ("IA16", "Intensity Alpha 16-bit", "Intensity Alpha 16-bit"),
]

enumTexUV = [
    ("TEXEL0", "Texture 0", "Texture 0"),
    ("TEXEL1", "Texture 1", "Texture 1"),
]

texBitSizeInt = {
    "I4": 4,
    "IA4": 4,
    "CI4": 4,
    "I8": 8,
    "IA8": 8,
    "CI8": 8,
    "RGBA16": 16,
    "IA16": 16,
    "YUV16": 16,
    "RGBA32": 32,
}

# 512 words * 64 bits / n bitSize
maxTexelCount = {
    32: 1024,
    16: 2048,
    8: 4096,
    4: 8192,
}

enumF3D = [
    ("F3D", "F3D", "Original microcode used in SM64"),
    ("F3DEX/LX", "F3DEX/LX", "F3DEX version 1"),
    ("F3DLX.Rej", "F3DLX.Rej", "F3DLX.Rej"),
    ("F3DLP.Rej", "F3DLP.Rej", "F3DLP.Rej"),
    ("F3DEX2/LX2", "F3DEX2/LX2/ZEX", "Family of microcodes used in later N64 games including OoT and MM"),
    ("F3DEX2.Rej/LX2.Rej", "F3DEX2.Rej/LX2.Rej", "Variant of F3DEX2 family using vertex rejection instead of clipping"),
    ("F3DEX3", "F3DEX3", "Custom microcode by Sauraen"),
]

enumLargeEdges = [
    ("Clamp", "Clamp", "Clamp outside image bounds"),
    ("Wrap", "Wrap", "Wrap outside image bounds (more expensive)"),
]

enumCelThreshMode = [
    (
        "Lighter",
        "Lighter",
        "This cel level is drawn when the lighting level per-pixel is LIGHTER than (>=) the threshold",
    ),
    ("Darker", "Darker", "This cel level is drawn when the lighting level per-pixel is DARKER than (<) the threshold"),
]

enumCelTintPipeline = [
    (
        "CC",
        "CC (tint in Prim Color)",
        "Cel shading puts tint color in Prim Color and tint level in Prim Alpha. Set up CC color to LERP between source color and tint color based on tint level, or multiply source color by tint color. Source may be Tex 0 or Env Color",
    ),
    (
        "Blender",
        "Blender (tint in Fog Color)",
        "Cel shading puts tint color in Fog Color and tint level in Fog Alpha. Set up blender to LERP between CC output and tint color based on tint level. Then set CC to Tex 0 * shade color (vertex colors)",
    ),
]

enumCelCutoutSource = [
    (
        "TEXEL0",
        "Texture 0",
        "Cel shading material has binary alpha cutout from Texture 0 alpha. Does not work with I4 or I8 formats",
    ),
    (
        "TEXEL1",
        "Texture 1",
        "Cel shading material has binary alpha cutout from Texture 1 alpha. Does not work with I4 or I8 formats",
    ),
    ("ENVIRONMENT", "None / Env Alpha", "Make sure your material writes env color, and set env alpha to opaque (255)"),
]

enumCelTintType = [
    ("Fixed", "Fixed", "Fixed tint color and level stored directly in DL"),
    ("Segment", "Segment", "Call a segmented DL to set the tint, can change at runtime"),
    ("Light", "From Light", "Automatically load tint color from selectable light slot. Tint level stored in DL"),
]
