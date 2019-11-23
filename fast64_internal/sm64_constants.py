import mathutils

# RAM address used in evaluating switch for hatless Mario
marioHatSwitch = 0x80277740
marioLowPolySwitch = 0x80277150

marioFaceExpressionCount = 4

loadMarioMIO0 = 0x2ABCA0
loadMarioGeo = 0x2ABCB8

# Full available rom interval for extended 0x04 bank (from SM64 Editor)
marioFullRomInterval = (0x11D8930, 0x11FFF00)
defaultExtendSegment4 = (0x11A35B8, 0x11FFF00)

mainLevelLoadScriptSegment = {
	0x15 : (0x2ABCA0, 0x2AC6B0)
}

bank0Segment = {
	0x00 : (0x000000, 0x7FFFFF)
}

# Segments for common geolayouts and Mario
loadSegmentAddresses = {
	0x03 : 0x2ABCAC,
	0x04 : 0x2ABCA0,
	0x13 : 0x2ABCD0,
	0x16 : 0x2ABCC4,
	0x17 : 0x2ABCB8
}

geoNodeRotateOrder = 'ZXY'

sm64ToBlenderScale = 0.0047
marioScale = 0.25

sm64BoneUp = mathutils.Vector([1,0,0])

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

lightIndices = [0x86, 0x88, 0x8A, 0x8C, 0x8E, 0x90, 0x92, 0x94]

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

colorCombinationCommands = [
	0x03, #load lighting data
	0xB6, #clear geometry params
	0xB7, #set geometry params
	0xBB, #set texture scaling factor
	0xF3, #set texture size
	0xF5, #set texture properties
	0xF7, #set fill color
	0xF8, #set fog color
	0xFB, #set env color
	0xFC, #set color combination 
	0xFD  #load texture 
]

drawCommands = [
	0x04, #load vertex data
	0xBF  #draw triangle
]

originalMarioHeadROMInterval = (
	0x011B4F58,
	0x011B5710
)

marioVanishOffsets = {
	"regular" : 0xB0C,
	"metal" : 0x9EC,
}

commonGeolayoutPointers = {
	'Dorrie' 	: [2039136, 'HMC'],
	'Bowser' 	: [1809204, 'BFB'],
	'Bowser 2' 	: [1809328, 'BFB'],
	'Lakitu' 	: [1985520,  'CC']
}

draw_layer_enums = [
	('1', 'Solid', '0x01'),
	('2', 'Solid Decal', '0x02'),
	('4', 'Transparent (No Blending)', '0x04'),
	('5', 'Transparent (Blending Front)', '0x05'),
	('6', 'Transparent (Blending Back)', '0x06'),
]

level_enums = [
	("HH" ,  "Haunted House" , "HH" ),
	("CCM",  "Cool Cool Mountain" , "CCM"),
	("IC" ,  "Inside Castle" , "IC" ),
	("HMC",  "Hazy Maze Cave" , "HMC"),
	("SSL",  "Shifting Sand Land" , "SSL"),
	("BOB",  "Bob-Omb's Battlefield" , "BOB"),
	("SML",  "Snow Man's land" , "SML"),
	("WDW",  "Wet Dry World" , "WDW"),
	("JRB",  "Jolly Roger Bay" , "JRB"),
	("THI",  "Tiny Huge Island" , "THI"),
	("TTC",  "Tick Tock Clock" , "TTC"),
	("RR" ,  "Rainbow Ride" , "RR" ),
	("CG" ,  "Castle Grounds" , "CG" ),
	("BFC",  "Bowser First Course" , "BFC"),
	("VC" ,  "Vanish Cap" , "VC" ),
	("BFS",  "Bowser's Fire Sea" , "BFS"),
	("SA" ,  "Secret Aquarium" , "SA" ),
	("BTC",  "Bowser Third Course" , "BTC"),
	("LLL",  "Lethal Lava Land" , "LLL"),
	("DDD",  "Dire Dire Docks" , "DDD"),
	("WF" ,  "Whomp's Fortress" , "WF" ),
	("PIC",  "Picture at the end" , "PIC"),
	("CC" ,  "Castle Courtyard" , "CC" ),
	("PSS",  "Peach's Secret Slide" , "PSS"),
	("MC" ,  "Metal Cap" , "MC" ),
	("WC" ,  "Wing Cap" , "WC" ),
	("BFB",  "Bowser First Battle" , "BFB"),
	("RC" ,  "Rainbow Clouds" , "RC" ),
	("BSB",  "Bowser Second Battle" , "BSB"),
	("BTB",  "Bowser Third Battle" , "BTB"),
	("TTM",  "Tall Tall Mountain" , "TTM"),
]

class SM64_CharacterImportData:
	def __init__(self, geoAddr, level, switchDict):
		self.geoAddr = geoAddr
		self.level = level
		self.switchDict = switchDict

character_enums = [
	("Mario" ,  "Mario" , "Mario" ),
	("Peach" ,  "Peach" , "Peach" ),
	#("Bowser" ,  "Bowser" , "Bowser" ),
	#("Koopa" ,  "Koopa" , "Koopa" ),
	#("Toad" ,  "Toad" , "Toad" )
]

# switch index starts at 1.
# switch option index starts at 0.
sm64_character_data = {

	"Mario" : SM64_CharacterImportData('12A784', 'CG', {
		1 : { # Low poly mario
			0 : 'Ignore'
		},
		2 : {
			1 : "Material", # metal mario
			2 : "Draw Layer", # vanish mario
			3 : "Material", # metal vanish mario
		},
		3 : {	# cap vs no cap	
		},
		4 : { # face animation (cap)
			0 : "Material",
			1 : "Material",
			2 : "Material",
			3 : "Material",
			4 : "Material",
			5 : "Material",
			6 : "Material",
			7 : "Material",
		},
		5 : { # face animation (no cap)
			0 : "Material",
			1 : "Material",
			2 : "Material",
			3 : "Material",
			4 : "Material",
			5 : "Material",
			6 : "Material",
			7 : "Material",
		},
		6 : { # right fist type
			# 0 = closed, 1 = open, 2 is something, 3-5 are same as 2
			3 : 'Ignore',
			4 : 'Ignore',
			5 : 'Ignore',
		},
		7 : { # left fist type
			# 0 = closed, 1 = open, 2 = peace, 3 = hold cap, 4 = hold cap wing
		},
	}),
	'Peach' : SM64_CharacterImportData('180950', 'CG', {
		1 : { # transparent peach
			1 : 'Draw Layer',
		},
		2 : { # 0-3 = face animation kissing, 4-7 = face animation normal
			0 : "Material",
			1 : "Material",
			2 : "Material",
			3 : "Material",
			4 : "Material",
			5 : "Material",
			6 : "Material",
			7 : "Material",
		}
	}),
}

level_pointers = {
	"HH" :  0x2AC094,
	"CCM":  0x2AC0A8,
	"IC" :  0x2AC0BC,
	"HMC":  0x2AC0D0,
	"SSL":  0x2AC0E4,
	"BOB":  0x2AC0F8,
	"SML":  0x2AC10C,
	"WDW":  0x2AC120,
	"JRB":  0x2AC134,
	"THI":  0x2AC148,
	"TTC":  0x2AC15C,
	"RR" :  0x2AC170,
	"CG" :  0x2AC184,
	"BFC":  0x2AC198,
	"VC" :  0x2AC1AC,
	"BFS":  0x2AC1C0,
	"SA" :  0x2AC1D4,
	"BTC":  0x2AC1E8,
	"LLL":  0x2AC1FC,
	"DDD":  0x2AC210,
	"WF" :  0x2AC224,
	"PIC":  0x2AC238,
	"CC" :  0x2AC24C,
	"PSS":  0x2AC260,
	"MC" :  0x2AC274,
	"WC" :  0x2AC288,
	"BFB":  0x2AC29C,
	"RC" :  0x2AC2B0,
	"BSB":  0x2AC2C4,
	"BTB":  0x2AC2D8,
	"TTM":  0x2AC2EC,
}