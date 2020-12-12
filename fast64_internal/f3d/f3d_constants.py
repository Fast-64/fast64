import mathutils

# Equivalent of euler(-90, -90, 0)
blenderToSM64Rotation = mathutils.Matrix(
	[[0,  1, 0],
	 [0, 0, 1],
	 [1,  0, 0]]
)

blenderToSM64RotationLevel = mathutils.Matrix(
	[[1, 0, 0],
	 [0, 0, 1],
	 [0,-1, 0]]
)

colorFormats = {
	'RGBA' : 0,
	'YUV' : 1,
	'CI' : 2,
	'IA' : 3,
	'I' : 4
}

pixelBitSizes = {
	'4bit'  : 0,
	'8bit'  : 1,
	'16bit' : 2,
	'32bit' : 3
}

# Color combinations
# In SM64, environment alpha controls Mario's alpha.

# 2 cycle with specular lighting stored in primitive
S_PHONG_TEX = ['TEXEL0', '0', 'SHADE', '0',
			'TEXEL0', '0', 'ENVIRONMENT', '0', 
			'PRIMITIVE', 'COMBINED', 'TEXEL0', 'COMBINED',
			'0', '0', '0', 'COMBINED']

# MULTIPLY TWO TEXTURES
S_MULTIPLY = [
	'TEXEL0', '0', 'TEXEL1', '0',
	'0', '0', '0', 'ENVIRONMENT',
	'TEXEL0', '0', 'TEXEL1', '0',
	'0', '0', '0', 'ENVIRONMENT'
]

S_PRIM_TRANSPARENT_SHADE = ['TEXEL0', '0', 'SHADE', '0',
				'TEXEL0', '0', 'PRIMITIVE', '0',
				'TEXEL0', '0', 'SHADE', '0',
				'TEXEL0', '0', 'PRIMITIVE', '0']

# REGULAR SHADED TEXTURE
S_SHADED_TEX = ['TEXEL0', '0', 'SHADE', '0',
				'0', '0', '0', 'ENVIRONMENT',
				'TEXEL0', '0', 'SHADE', '0',
				'0', '0', '0', 'ENVIRONMENT']

# VERTEX COLOR
S_VERTEX_COLORED_TEX = ['TEXEL0', '0', 'SHADE', '0',
				'ENVIRONMENT', '0', 'SHADE', '0',
				'TEXEL0', '0', 'SHADE', '0',
				'ENVIRONMENT', '0', 'SHADE', '0']

S_VERTEX_COLORED_TEX_NO_VERT_ALPHA = ['TEXEL0', '0', 'SHADE', '0',
				'0', '0', '0', 'TEXEL0',
				'TEXEL0', '0', 'SHADE', '0',
				'0', '0', '0', 'TEXEL0',]

S_VERTEX_COLORED_TEX_TRANSPARENT = ['TEXEL0', '0', 'SHADE', '0',
				'TEXEL0', '0', 'SHADE', '0',
				'TEXEL0', '0', 'SHADE', '0',
				'TEXEL0', '0', 'SHADE', '0']

S_SHADED_TEX_CUTOUT = ['TEXEL0', '0', 'SHADE', '0',
				'TEXEL0', '0', 'ENVIRONMENT', '0',
				'TEXEL0', '0', 'SHADE', '0',
				'TEXEL0', '0', 'ENVIRONMENT', '0']

# UNLIT TEXTURE, USED FOR METAL MARIO
S_UNLIT_TEX = ['0', '0', '0', 'TEXEL0',
			  	'0', '0', '0', 'ENVIRONMENT',
			  	'0', '0', '0', 'TEXEL0',
			  	'0', '0', '0', 'ENVIRONMENT']

S_UNLIT_TEX_CUTOUT = ['0', '0', '0', 'TEXEL0',
				'TEXEL0', '0', 'ENVIRONMENT', '0',
				'0', '0', '0', 'TEXEL0',
				'TEXEL0', '0', 'ENVIRONMENT', '0']

# SM64 CUSTOM IMPORTER CC
S_SHADED_TEX_NOALPHA = ['TEXEL0', '0', 'SHADE', '0',
							'0', '0', '0', 'SHADE',
							'TEXEL0', '0', 'SHADE', '0',
							'0', '0', '0', 'SHADE']

# SM64 BODY CC
S_SHADED_SOLID = ['0', '0', '0', 'SHADE', 
					'0', '0', '0', 'ENVIRONMENT',
					'0', '0', '0', 'SHADE', 
					'0', '0', '0', 'ENVIRONMENT']

# SM64 BODY TEXTURES (FACE, SIDEBURNS, ETC.)
S_UNLIT_DECAL_ON_SHADED_SOLID = ['TEXEL0', 'SHADE', 'TEXEL0_ALPHA', 'SHADE',
									'0', '0', '0', 'ENVIRONMENT', 
									'TEXEL0', 'SHADE', 'TEXEL0_ALPHA', 'SHADE',
									'0', '0', '0', 'ENVIRONMENT']

# SHADED RANDOM NOISE
S_SHADED_NOISE = ['NOISE', '0', 'SHADE', '0',
					'0', '0', '0', 'ENVIRONMENT',
					'NOISE', '0', 'SHADE', '0',
					'0', '0', '0', 'ENVIRONMENT']

# FOG SHADED TEXTURES
S_FOG_SHADED_TEX = ['TEXEL0', '0', 'SHADE', '0',
				'0', '0', '0', 'ENVIRONMENT',
				'0', '0', '0', 'COMBINED',
				'0', '0', '0', 'COMBINED']

S_FOG_SHADED_TEX_CUTOUT = ['TEXEL0', '0', 'SHADE', '0',
				'TEXEL0', '0', 'ENVIRONMENT', '0',
				'0', '0', '0', 'COMBINED',
				'0', '0', '0', 'COMBINED']

S_FOG_PRIM_TRANSPARENT_SHADE = ['TEXEL0', '0', 'SHADE', '0',
				'TEXEL0', '0', 'PRIMITIVE', '0',
				'0', '0', '0', 'COMBINED',
				'0', '0', '0', 'COMBINED']