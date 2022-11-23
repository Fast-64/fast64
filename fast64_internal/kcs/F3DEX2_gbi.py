import re
from bitstring import *
import math
import time


#start f3dex2 words to binary
EncodeFmtEx2 = {
    'G_SNOOP':'uint:64=0',
    'G_VTX':'uint:12=%s,uint:8,uint:4=0,uint:8,uint:32' % 0x010,
    'G_MODIFYVTX':'uint:8=2,uint:8,uint:16,uint:32',
    'G_CULLDL':'uint:8=3,uint:8=0,uint:16,uint:16=0,uint:16',
    'G_BRANCH_Z':'uint:32=%s,uint:32,uint:8=4,uint:12,uint:12,uint:32' % 0xE1000000,
    'G_TRI1':'uint:8=5,3*uint:8,uint:32=0',
    'G_TRI2':'uint:8=6,3*uint:8,uint:8=0,3*uint:8',
    'G_QUAD':'uint:8=7,3*uint:8,uint:8=0,3*uint:8',
    'G_DMA_IO':'uint:8=%s,uint:1,uint:10,uint:1=0,uint:12,uint:32' %0xd6,
    'G_TEXTURE':'uint:16=%s,uint:2=0,uint:3,uint:3,uint:8,2*int:16' % 0xd700,
    'G_POPMTX':'0xd8380002,uint:32',
    'G_GEOMETRYMODE':'uint:8=%s,uint:24,uint:32' % 0xd9,
    'G_MTX':'uint:24=%s,uint:8,uint:32' %0xda3800,
    'G_MOVEWORD':'uint:8=%s,uint:8,uint:16,uint:32' % 0xdb,
    'G_MOVEMEM':'uint:8=%s,3*uint:8,uint:32' %0xdc,
    'G_LOAD_UCODE':'uint:32=%s,uint:32,uint:16=%s,uint:16,uint:32' %(0xe1000000, 0xdd00),
    'G_DL':'uint:8=%s,uint:8,uint:16=0,uint:32' %0xde,
    'G_ENDDL':'0xDF00000000000000',
    'G_NOOP':'0XE000000000000000',
    'G_RDPHALF_1':'uint:32=%s,uint:32' %0xe1000000,
    'G_SETOTHERMODE_L':'uint:16=%s,2*uint:8,uint:32' %0xe200,
    'G_SETOTHERMODE_H':'uint:16=%s,2*uint:8,uint:32' %0xe300,
    'G_TEXRECT':'uint:8=%s,2*uint:12,uint:4=0,uint:4,2*uint:12,uint:32=%s,2*uint:16,uint:32=%s,2*uint:16' %(0xe4,0xe1000000,0xf1000000),
    'G_TEXRECTFLIP':'uint:8=%s,2*uint:12,uint:4=0,uint:4,2*uint:12,uint:32=%s,2*uint:16,uint:32=%s,2*uint:16' %(0xe5,0xe1000000,0xf1000000),
    'G_RDPLOADSYNC':'0Xe600000000000000',
    'G_RDPPIPESYNC':'0xe700000000000000',
    'G_RDPTILESYNC':'0Xe800000000000000',
    'G_RDPFULLSYNC':'0xe900000000000000',
    'G_SETKEYGB':'uint:8=%s,2*uint:12,4*uint:8' %0xea,
    'G_SETKEYR':'uint:36=%s,uint:12,2*uint:8' %0xeb0000000,
    'G_SETCONVERT':'uint:8=236,int:2=0,6*int:9',
    'G_SETSCISSOR':'uint:8=%s,2*uint:12,uint:4=0,uint:4,2*uint:12' %0xed,
    'G_SETPRIMDEPTH':'uint:32=%s,2*uint:16' %0xee000000,
    'G_RDPSETOTHERMODE':'uint:8=%s,uint:24,uint:32' %0xef,
    'G_LOADTLUT':'uint:36=%s,uint:4,uint:12,uint:12=0' %0xf00000000,
    'G_RDPHALF_2':'uint:32=%s,uint:32' %0xf1000000,'G_SETTILESIZE':'uint:8=%s,2*uint:12,uint:4=0,uint:4,2*uint:12' %0xf2,
    'G_LOADBLOCK':'uint:8=%s,2*uint:12,uint:4=0,uint:4,2*uint:12' %0xf3,
    'G_LOADTILE':'uint:8=%s,2*uint:12,uint:4=0,uint:4,2*uint:12' %0xf4,
    'G_SETTILE':'uint:8=%s,uint:3,uint:2,uint:1=0,uint:9,uint:9,uint:5=0,uint:3,uint:4,uint:2,2*uint:4,uint:2,2*uint:4' %0xf5,
    'G_FILLRECT':'uint:8=%s,2*uint:12,uint:8=0,2*uint:12' %0xf6,
    'G_SETFILLCOLOR':'uint:32=%s,4*uint:8' %0xf7000000,
    'G_SETFOGCOLOR':'uint:32=%s,4*uint:8' %0xf8000000,
    'G_SETBLENDCOLOR':'uint:32=%s,4*uint:8' %0xf9000000,
    'G_SETPRIMCOLOR':'uint:16=%s,6*uint:8' %0xfA00,
    'G_SETENVCOLOR':'uint:32=%s,4*uint:8' %0xfB000000,
    'G_SETCOMBINE':'uint:8=%s,uint:4,uint:5,2*uint:3,uint:4,uint:5,2*uint:4,8*uint:3' %0xfc,
    'G_SETTIMG':'uint:8=%s,uint:3,uint:2,uint:19=0,uint:32' %0xfd,
    'G_SETZIMG':'uint:32=%s,uint:32' %0xfe000000,
    'G_SETCIMG':'uint:8=%s,uint:3,uint:2,uint:7=0,uint:12,uint:32' %0xff
}

Render_Modes = {
	0x00442078: 'G_RM_AA_ZB_OPA_SURF',
	0x00112078: 'G_RM_AA_ZB_OPA_SURF2',
	0x004049D8: 'G_RM_AA_ZB_XLU_SURF',
	0x001049D8: 'G_RM_AA_ZB_XLU_SURF2',
	0x00442D58: 'G_RM_AA_ZB_OPA_DECAL',
	0x00112D58: 'G_RM_AA_ZB_OPA_DECAL2',
	0x00404DD8: 'G_RM_AA_ZB_XLU_DECAL',
	0x00104DD8: 'G_RM_AA_ZB_XLU_DECAL2',
	0x00442478: 'G_RM_AA_ZB_OPA_INTER',
	0x00112478: 'G_RM_AA_ZB_OPA_INTER2',
	0x004045D8: 'G_RM_AA_ZB_XLU_INTER',
	0x001045D8: 'G_RM_AA_ZB_XLU_INTER2',
	0x00407858: 'G_RM_AA_ZB_XLU_LINE',
	0x00107858: 'G_RM_AA_ZB_XLU_LINE2',
	0x00407F58: 'G_RM_AA_ZB_DEC_LINE',
	0x00107F58: 'G_RM_AA_ZB_DEC_LINE2',
	0x00443078: 'G_RM_AA_ZB_TEX_EDGE',
	0x00113078: 'G_RM_AA_ZB_TEX_EDGE2',
	0x00443478: 'G_RM_AA_ZB_TEX_INTER',
	0x00113478: 'G_RM_AA_ZB_TEX_INTER2',
	0x00442278: 'G_RM_AA_ZB_SUB_SURF',
	0x00112278: 'G_RM_AA_ZB_SUB_SURF2',
	0x0040007B: 'G_RM_AA_ZB_PCL_SURF',
	0x0010007B: 'G_RM_AA_ZB_PCL_SURF2',
	0x00402078: 'G_RM_AA_ZB_OPA_TERR',
	0x00102078: 'G_RM_AA_ZB_OPA_TERR2',
	0x00403078: 'G_RM_AA_ZB_TEX_TERR',
	0x00103078: 'G_RM_AA_ZB_TEX_TERR2',
	0x00402278: 'G_RM_AA_ZB_SUB_TERR',
	0x00102278: 'G_RM_AA_ZB_SUB_TERR2',
	0x00442038: 'G_RM_RA_ZB_OPA_SURF',
	0x00112038: 'G_RM_RA_ZB_OPA_SURF2',
	0x00442D18: 'G_RM_RA_ZB_OPA_DECAL',
	0x00112D18: 'G_RM_RA_ZB_OPA_DECAL2',
	0x00442438: 'G_RM_RA_ZB_OPA_INTER',
	0x00112438: 'G_RM_RA_ZB_OPA_INTER2',
	0x00442048: 'G_RM_AA_OPA_SURF',
	0x00112048: 'G_RM_AA_OPA_SURF2',
	0x004041C8: 'G_RM_AA_XLU_SURF',
	0x001041C8: 'G_RM_AA_XLU_SURF2',
	0x00407048: 'G_RM_AA_XLU_LINE',
	0x00107048: 'G_RM_AA_XLU_LINE2',
	0x00407248: 'G_RM_AA_DEC_LINE',
	0x00107248: 'G_RM_AA_DEC_LINE2',
	0x00443048: 'G_RM_AA_TEX_EDGE',
	0x00113048: 'G_RM_AA_TEX_EDGE2',
	0x00442248: 'G_RM_AA_SUB_SURF',
	0x00112248: 'G_RM_AA_SUB_SURF2',
	0x0040004B: 'G_RM_AA_PCL_SURF',
	0x0010004B: 'G_RM_AA_PCL_SURF2',
	0x00402048: 'G_RM_AA_OPA_TERR',
	0x00102048: 'G_RM_AA_OPA_TERR2',
	0x00403048: 'G_RM_AA_TEX_TERR',
	0x00103048: 'G_RM_AA_TEX_TERR2',
	0x00402248: 'G_RM_AA_SUB_TERR',
	0x00102248: 'G_RM_AA_SUB_TERR2',
	0x00442008: 'G_RM_RA_OPA_SURF',
	0x00112008: 'G_RM_RA_OPA_SURF2',
	0x00442230: 'G_RM_ZB_OPA_SURF',
	0x00112230: 'G_RM_ZB_OPA_SURF2',
	0x00404A50: 'G_RM_ZB_XLU_SURF',
	0x00104A50: 'G_RM_ZB_XLU_SURF2',
	0x00442E10: 'G_RM_ZB_OPA_DECAL',
	0x00112E10: 'G_RM_ZB_OPA_DECAL2',
	0x00404E50: 'G_RM_ZB_XLU_DECAL',
	0x00104E50: 'G_RM_ZB_XLU_DECAL2',
	0x00404B50: 'G_RM_ZB_CLD_SURF',
	0x00104B50: 'G_RM_ZB_CLD_SURF2',
	0x00404F50: 'G_RM_ZB_OVL_SURF',
	0x00104F50: 'G_RM_ZB_OVL_SURF2',
	0x0C080233: 'G_RM_ZB_PCL_SURF',
	0x03020233: 'G_RM_ZB_PCL_SURF2',
	0x0C084000: 'G_RM_OPA_SURF',
	0x03024000: 'G_RM_OPA_SURF2',
	0x00404240: 'G_RM_XLU_SURF',
	0x00104240: 'G_RM_XLU_SURF2',
	0x00404340: 'G_RM_CLD_SURF',
	0x00104340: 'G_RM_CLD_SURF2',
	0x0C087008: 'G_RM_TEX_EDGE',
	0x03027008: 'G_RM_TEX_EDGE2',
	0x0C084203: 'G_RM_PCL_SURF',
	0x03024203: 'G_RM_PCL_SURF2',
	0x04484340: 'G_RM_ADD',
	0x01124340: 'G_RM_ADD2',
	0x00000000: 'G_RM_NOOP2',
	0x0C844040: 'G_RM_VISCVG',
	0x03214040: 'G_RM_VISCVG2',
	0x03020000: 'G_RM_OPA_CI2',
	0x004049F8: 'G_RM_CUSTOM_AA_ZB_XLU_SURF',
	0x001049F8: 'G_RM_CUSTOM_AA_ZB_XLU_SURF2',
	0x00000000: "G_RM_NOOP",
	0x0C080000: "G_RM_PASS", #anything at the tail end is fine
	0xC8000000: 'G_RM_FOG_SHADE_A', #anything at the tail end is fine
	0xC4000000: 'G_RM_FOG_PRIM_A', #anything at the tail end is fine

	#ones I didn't get from GBI
	
	#OPA / TEX_EDGE stuff
	
	#same as OPA_DECAL but has Z_UPD and CVG_DST_CLAMP instead of CVG_DST_WRAP, aka a TERR mode
	#terrain modes are for large polygons, fixes Z inaccuracies at the cost of not handling aliasing in "pinwheels"
	0x00442C78: 'G_RM_AA_ZB_OPA_DECAL_TERR', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_CLAMP | ALPHA_CVG_SEL | ZMODE_DEC | (CLR, CLR, MEM, MEM)
	0x00112C78: 'G_RM_AA_ZB_OPA_DECAL_TERR2', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_CLAMP | ALPHA_CVG_SEL | ZMODE_DEC | (CLR, CLR, MEM, MEM)

	#doesn't update Z, but otherwise the same, there is no fitting name for this distinction
	0x00442058: 'G_RM_AA_ZB_OPA_SURF', #AA_EN | Z_CMP | IM_RD | CVG_DST_CLAMP | ALPHA_CVG_SEL | ZMODE_OPA | (CLR, CLR, MEM, MEM)
	0x00112058: 'G_RM_AA_ZB_OPA_SURF2', #AA_EN | Z_CMP | IM_RD | CVG_DST_CLAMP | ALPHA_CVG_SEL | ZMODE_OPA | (CLR, CLR, MEM, MEM)
	0x00442018: 'G_RM_RA_ZB_OPA_SURF', #AA_EN | Z_CMP | CVG_DST_CLAMP | ALPHA_CVG_SEL | ZMODE_OPA | (CLR, CLR, MEM, MEM)
	0x00112018: 'G_RM_RA_ZB_OPA_SURF2', #AA_EN | Z_CMP | CVG_DST_CLAMP | ALPHA_CVG_SEL | ZMODE_OPA | (CLR, CLR, MEM, MEM)
	
	#I guess this is an option
	0x00443C58: 'G_RM_AA_ZB_TEX_DECAL_TERR', #AA_EN | Z_CMP | IM_RD | CVG_DST_CLAMP | CVG_X_ALPHA | ALPHA_CVG_SEL | ZMODE_DEC | (CLR, CLR, MEM, MEM)
	0x00113C58: 'G_RM_AA_ZB_TEX_DECAL_TERR2', #AA_EN | Z_CMP | IM_RD | CVG_DST_CLAMP | CVG_X_ALPHA | ALPHA_CVG_SEL | ZMODE_DEC | (CLR, CLR, MEM, MEM)

	#add Z_UPD, no idea what that makes this mode called then, seems redundant
	0x00443C78: 'G_RM_AA_ZB_TEX_DECAL_TERR', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_CLAMP | CVG_X_ALPHA | ALPHA_CVG_SEL | ZMODE_DEC | (CLR, CLR, MEM, MEM)
	0x00113C78: 'G_RM_AA_ZB_TEX_DECAL_TERR2', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_CLAMP | CVG_X_ALPHA | ALPHA_CVG_SEL | ZMODE_DEC | (CLR, CLR, MEM, MEM)

	#names fit
	0x00443038: 'G_RM_RA_TEX_EDGE', #AA_EN | IM_RD | Z_CMP | Z_UPD | CVG_DST_CLAMP | ZMODE_OPA | (CLR, CLR, MEM, MEM)
	0x00113038: 'G_RM_RA_TEX_EDGE2', #AA_EN | IM_RD | Z_CMP | Z_UPD | CVG_DST_CLAMP | ZMODE_OPA | (CLR, CLR, MEM, MEM)
	0x00442030: 'G_RM_ZB_OPA_TERR', #Z_CMP | Z_UPD | CVG_DST_CLAMP | ALPHA_CVG_SEL | ZMODE_OPA | (CLR, CLR, MEM, MEM)
	0x00112030: 'G_RM_ZB_OPA_TERR2', #Z_CMP | Z_UPD | CVG_DST_CLAMP | ALPHA_CVG_SEL | ZMODE_OPA | (CLR, CLR, MEM, MEM)

	#fitting name
	0x00443008: 'G_RM_RA_TEX_EDGE', #AA_EN | CVG_DST_CLAMP | CVG_X_ALPHA | ALPHA_CVG_SEL | ZMODE_OPA | (CLR, CLR, MEM, MEM)
	0x00113008: 'G_RM_RA_TEX_EDGE2', #AA_EN | CVG_DST_CLAMP | CVG_X_ALPHA | ALPHA_CVG_SEL | ZMODE_OPA | (CLR, CLR, MEM, MEM)

	#not sure what is up here, doesn't seem to fit the logic of any particular mode
	0x00442040: 'G_RM_OPA_TERR', #IM_RD | CVG_DST_CLAMP | CVG_X_ALPHA | ZMODE_OPA | (CLR, CLR, MEM, MEM)
	0x00112040: 'G_RM_OPA_TERR2', #IM_RD | CVG_DST_CLAMP | CVG_X_ALPHA | ZMODE_OPA | (CLR, CLR, MEM, MEM)


	#XLU STUFF

	#G_RM_AA_XLU_SURF but it has no IM_RD, so I'm not sure how it is supposed to blend
	0x004049C8: 'G_RM_RA_XLU_SURF', #AA_EN | IM_RD | CLR_ON_CVG | CVG_DST_WRAP | FORCE_BL | ZMODE_XLU | (CLR, CLR, MEM, 1-A)
	0x001049C8: 'G_RM_RA_XLU_SURF2', #AA_EN | IM_RD | CLR_ON_CVG | CVG_DST_WRAP | FORCE_BL | ZMODE_XLU | (CLR, CLR, MEM, 1-A)
	
	#with no AA, this mode is supposed to 'ZAP' which means CVG_DST_FULL, assuming pt filter, not sure what to name this with that in mind
	0x00404950: 'G_RM_ZB_XLU_SURF', #Z_CMP | IM_RD | CVG_DST_WRAP | ZMODE_XLU | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x00104950: 'G_RM_ZB_XLU_SURF2', #Z_CMP | IM_RD | CVG_DST_WRAP | ZMODE_XLU | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x00404D50: 'G_RM_ZB_XLU_DECAL', #Z_CMP | IM_RD | CVG_DST_WRAP | ALPHA_CVG_SEL | ZMODE_DEC | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x00104D50: 'G_RM_ZB_XLU_DECAL2', #Z_CMP | IM_RD | CVG_DST_WRAP | ALPHA_CVG_SEL | ZMODE_DEC | FORCE_BL | (CLR, CLR, MEM, 1-A)

	#a XLU decal terrain polygon with z buffering. not 100% on if this even makes sense
	0x00404C78: 'G_RM_AA_ZB_XLU_DECAL_TERR', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_CLAMP | ZMODE_DEC | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x00104C78: 'G_RM_AA_ZB_XLU_DECAL_TERR2', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_CLAMP | ZMODE_DEC | FORCE_BL | (CLR, CLR, MEM, 1-A)

	#I don't get how this is supposed to work or what this really looks like
	0x00404BD0: 'G_RM_ZB_CLD_SURF_CLR', #Z_CMP | IM_RD | CLR_ON_CVG | CVG_DST_SAVE | FORCE_BL | ZMODE_XLU | (CLR, CLR, MEM, 1-A)
	0x00104BD0: 'G_RM_ZB_CLD_SURF_CLR2', #Z_CMP | IM_RD | CLR_ON_CVG | CVG_DST_SAVE | FORCE_BL | ZMODE_XLU | (CLR, CLR, MEM, 1-A)

	#should be close to accurate name, same as OVL_SURF but with CLR_ON_CVG, not sure of significance
	0x00404FD0: 'G_RM_ZB_OVL_DECAL', #Z_CMP | IM_RD | CLR_ON_CVG | CVG_DST_SAVE | FORCE_BL | ZMODE_DEC | (CLR, CLR, MEM, 1-A)
	0x00104FD0: 'G_RM_ZB_OVL_DECAL2',  #Z_CMP | IM_RD | CLR_ON_CVG | CVG_DST_SAVE | FORCE_BL | ZMODE_DEC | (CLR, CLR, MEM, 1-A)

	#isn't OVL and AA+ZB illegal? I don't know, but kirby seems to think it is ok
	0x00404F78: 'G_RM_AA_ZB_OVL_SURF', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_SAVE | ZMODE_DEC | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x00104F78: 'G_RM_AA_ZB_OVL_SURF2', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_SAVE | ZMODE_DEC | FORCE_BL | (CLR, CLR, MEM, 1-A)

	#Cloud, but it is not OPA, which is the normal way according to manual
	0x00404B40: 'G_RM_CLD_SURF', #IM_RD | CVG_DST_SAVE | ALPHA_CVG_SEL | ZMODE_XLU | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x00104B40: 'G_RM_OVL_SURF2', #IM_RD | CVG_DST_SAVE | ALPHA_CVG_SEL | ZMODE_XLU | FORCE_BL | (CLR, CLR, MEM, 1-A)

	#XLU even though z mode isn't XLU, same as G_RM_AA_XLU_SURF but with Z_CMP, not sure on naming
	0x004041D8: 'G_RM_AA_ZB_XLU_SURF', #AA_EN | Z_CMP | IM_RD | CVG_DST_WRAP | ZMODE_OPA | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x001041D8: 'G_RM_AA_ZB_XLU_SURF2', #AA_EN | Z_CMP | IM_RD | CVG_DST_WRAP | ZMODE_OPA | FORCE_BL | (CLR, CLR, MEM, 1-A)

	#several 2 cycle modes
	
	#I actually have no clue on these
	0x00104038: 'G_RM_RA_ZB_OPA_SURF2', #AA_EN | Z_CMP | Z_UPD | CVG_DST_CLAMP | ZMODE_OPA | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x00104008: 'G_RM_RA_OPA_SURF2', #AA_EN | CVG_DST_CLAMP | ZMODE_OPA | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x00104858: 'G_RM_RA_ZB_XLU_SURF2', #AA_EN | Z_CMP | IM_RD | CVG_DST_CLAMP | ZMODE_XLU | FORCE_BL | (CLR, CLR, MEM, 1-A)
	0x01024078: 'G_RM_AA_ZB_OPA_FOG2', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_CLAMP | ZMODE_OPA | FORCE_BL | (CLR, FOG, CLR, 1) ???

	#I don't believe there is a name for this, this is prob a 1 cycle mode only
	0x08802038: 'G_RM_RA_ZB_OPA_BLEND_SURF', #AA_EN | Z_CMP | Z_UPD | CVG_DST_CLAMP | ZMODE_OPA | ALPHA_CVG_SEL | FORCE_BL | (CLR, SHD, BLND, 1-A)
	0x08802078: 'G_RM_AA_ZB_OPA_BLEND_SURF', #AA_EN | Z_CMP | Z_UPD | IM_RD | CVG_DST_CLAMP | ZMODE_OPA | ALPHA_CVG_SEL | FORCE_BL | (CLR, SHD, BLND, 1-A)

	0x08004DD8: 'G_RM_AA_ZB_DECAL_FOG_ALPHA', #AA_EN | Z_CMP | IM_RD | CVG_DST_WRAP | ZMODE_DEC | FORCE_BL | (CLR, SHD, CLR, 1-A)
}

Mode_Bits = {
	'G_RM_AA_ZB_OPA_SURF': '0x00552078',
	'G_RM_AA_ZB_OPA_SURF2': '0x00112078',
	'G_RM_AA_ZT_OPA_SURF': '0x00552058',
	'G_RM_AA_ZT_OPA_SURF': '0x00112058',
	'G_RM_RA_OPA_SURF': '0x00552008',
	'G_RM_RA_OPA_SURF2': '0x00112008',
	'G_RM_ID_OPA_SURF': '0x00552040',
	'G_RM_ID_OPA_SURF2': '0x00112040',
	'G_RM_RA_ZT_OPA_SURF': '0x00552018',
	'G_RM_RA_ZT_OPA_SURF2': '0x00112018',
	'G_RM_AA_ZB_XLU_SURF': '0x005049D8',
	'G_RM_AA_ZB_XLU_SURF2': '0x001049D8',
	'G_RM_AA_XLU_SURF': '0x005049c8',
	'G_RM_AA_XLU_SURF2': '0x001049c8',
	'G_RM_AA_ZB_XLU_SURF_REVERSE': '0x0C1849D8',
	'G_RM_RA_TEX_EDGE': '0x00553008',
	'G_RM_RA_TEX_EDGE2': '0x00113008',
	'G_RM_RA_ZB_OPA_SURF': '0x00552038',
	'G_RM_RA_ZB_OPA_SURF2': '0x00112038',
	'G_RM_RA_ZB_TEX_EDGE': '0x00553038',
	'G_RM_RA_ZB_TEX_EDGE2': '0x00113038',
	'G_RM_AA_TEX_EDGE': '0x00553048',
	'G_RM_AA_TEX_EDGE2': '0x00113048',
	'G_RM_AA_ZB_OPA_DECAL': '0x00552C78',
	'G_RM_AA_ZB_OPA_DECAL2': '0x00112C78',
	'G_RM_AA_ZB_TEX_EDGE_DECAL': '0x00553C78',
	'G_RM_AA_ZB_TEX_EDGE_DECAL2': '0x00113C78',
	'G_RM_AA_OPA_SURF': '0x00552048',
	'G_RM_AA_OPA_SURF2': '0x00112048',
	'G_RM_AA_ZB_TEX_EDGE': '0x00553078',
	'G_RM_AA_ZB_TEX_EDGE2': '0x00113078',
	"G_RM_ZB_CLD_SURF":"0x00404B50",
	"G_RM_ZB_CLD_SURF2":"0x00104B50",
	"G_RM_ZB_OVL_SURF":"0x00404F50",
	"G_RM_ZB_OVL_SURF2":"0x00104F50",
	'G_RM_AA_ZB_TEX_TERR': '0x00503078',
	'G_RM_AA_ZB_TEX_TERR2': '0x00103078',
	'G_RM_AA_ZB_OPA_INVERT': '0x0C192078',
	'G_RM_AA_ZB_TEX_EDGE_INVERT': '0x0C193078',
	'G_RM_RA_ZB_TEX_EDGE_INVERT': '0x0C193038',
	'G_RM_AA_TEX_EDGE_INVERT': '0x0C193048',
	'G_RM_RA_ZB_OPA_INVERT': '0x0C192038',
	'G_RM_RA_ZB_TEX_DECAL_INVERT': '0x0C193C78',
	'G_RM_AA_OPA_INVERT': '0x0C192048',
	'G_RM_RA_OPA_INVERT': '0x0C192008',
	'G_RM_AA_ZB_XLU_DECAL': '0x00504DD8',
	'G_RM_AA_ZB_XLU_DECAL_INVERT': '0x0C194DD8',
	'G_RM_AA_ZB_XLU_DECAL_REVERSE': '0x0C184DD8',
	'G_RM_AA_ZB_XLU_SURF_REVERSE': '0x0C184078',
	'G_RM_RA_ZB_XLU_SURF_REVERSE': '0x0C184038',
	'G_RM_AA_XLU_SURF_REVERSE': '0x0C1849c8',
	'G_RM_RA_XLU_SURF_REVERSE': '0x0C184008',
	'G_RM_AA_ZB_OPA_SURF_FOG_ALPHA': '0xC8112078',
	'G_RM_NOOP': '0x00000000'
}

EncodeMacro={
	#type, depth, BankID, width, height, Tflags, Sflags
	'G_LoadTextureBlock':[
		(lambda x: ('G_SETTIMG',(x[0],x[1],x[2]))),
		(lambda x: ('G_SETTILE',(x[0],x[1],0,0,7,0,x[6],x[4],0,x[5],x[3],0))),
		(lambda x: ('G_RDPLOADSYNC',())),
		(lambda x: ('G_LOADBLOCK',(0,0,7,x[4]*x[3],CalcDxT(x[3],int(math.log(x[1]//4,2)))))),
		(lambda x: ('G_RDPPIPESYNC',())),
		(lambda x: ('G_SETTILE',(x[0],x[1],((int(math.log(x[1]//4,2))*x[3])+7)>>3,0,0,0,x[6],x[4],0,x[5],x[3],0))),
		(lambda x: ('G_SETTILESIZE',(0,0,0,x[3],x[4])))
	],
	#type, BankID, width, height, Tflags, Sflags
	'G_LoadTextureBlock4B':[
		(lambda x: ('G_SETTIMG',(x[0],16,x[1]))),
		(lambda x: ('G_SETTILE',(x[0],16,0,0,7,0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_RDPLOADSYNC',())),
		(lambda x: ('G_LOADBLOCK',(0,0,7,(((x[2]*x[3])+3)>>2),CalcDxT(x[2],.5)))),
		(lambda x: ('G_RDPPIPESYNC',())),
		(lambda x: ('G_SETTILE',(x[0],4,(((x[2]>>1)+7)>>3),0,0,0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_SETTILESIZE',(0,0,0,x[2],x[3])))
	],
	#type, BankID, width, height, Tflags, Sflags
	'G_LoadTextureBlock8B':[
		(lambda x: ('G_SETTIMG',(x[0],16,x[1]))),
		(lambda x: ('G_SETTILE',(x[0],16,0,0,7,0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_RDPLOADSYNC',())),
		(lambda x: ('G_LOADBLOCK',(0,0,7,(((x[2]*x[3])+1)>>1),CalcDxT(x[2],1)))),
		(lambda x: ('G_RDPPIPESYNC',())),
		(lambda x: ('G_SETTILE',(x[0],8,((x[2]+7)>>3),0,0,0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_SETTILESIZE',(0,0,0,x[2],x[3])))
	],
	#type, BankID, width, height, Tflags, Sflags, PaletteBankID
	'G_LoadTextureBlock4BCI':[
		(lambda x: ('G_RDPTILESYNC', ())),
		(lambda x: ('G_SETTILE', ('RGBA', 4, 0, 256, 5, 0, 'wrap', 1, 0, 'wrap', 1, 0))),
		(lambda x: ('G_SETTILE',('CI',16,0,0,7,0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_SETTIMG',('RGBA',16,x[6]))),
		(lambda x: ('G_RDPLOADSYNC',())),
		(lambda x: ('G_LOADTLUT', (5, 128))),
		(lambda x: ('G_RDPPIPESYNC', ())),
		(lambda x: ('G_SETTIMG',('CI',16,x[1]))),
		(lambda x: ('G_RDPLOADSYNC',())),
		(lambda x: ('G_LOADBLOCK',(0,0,7,(((x[2]*x[3])+3)>>2),CalcDxT(x[2],.5)))),
		(lambda x: ('G_RDPPIPESYNC',())),
		(lambda x: ('G_SETTILE',('CI',4,(((x[2]>>1)+7)>>3),0,0,0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_SETTILESIZE',(0,0,0,x[2],x[3])))
	],
	#fmt, T addr, width, height, T flags, S flags, tile, mem offset
	'G_LoadTextureBlock4B_Tile':[
		(lambda x: ('G_SETTIMG',(x[0],16,x[1]))),
		(lambda x: ('G_SETTILE',(x[0],16,0,x[7],7,0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_RDPLOADSYNC',())),
		(lambda x: ('G_LOADBLOCK',(0,0,7,(((x[2]*x[3])+3)>>2),CalcDxT(x[2],.5)))),
		(lambda x: ('G_RDPPIPESYNC',())),
		(lambda x: ('G_SETTILE',(x[0],4,(((x[2]>>1)+7)>>3),x[7],x[6],0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_SETTILESIZE',(0,0,x[6],x[2],x[3])))
	],
	#fmt, T addr, width, height, T flags, S flags, tile, mem offset
	'G_LoadTextureBlock8B_Tile':[
		(lambda x: ('G_SETTIMG',(x[0],16,x[1]))),
		(lambda x: ('G_SETTILE',(x[0],16,0,x[7],7,0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_RDPLOADSYNC',())),
		(lambda x: ('G_LOADBLOCK',(0,0,7,(((x[2]*x[3])+1)>>1),CalcDxT(x[2],1)))),
		(lambda x: ('G_RDPPIPESYNC',())),
		(lambda x: ('G_SETTILE',(x[0],8,((x[2]+7)>>3),x[7],x[6],0,x[5],x[3],0,x[4],x[2],0))),
		(lambda x: ('G_SETTILESIZE',(0,0,x[6],x[2],x[3])))
		],
	#fmt, depth, T addr, width, height, T flags, S flags, tile, mem offset
	'G_LoadTextureBlock_Tile':[
		(lambda x: ('G_SETTIMG',(x[0],x[1],x[2]))),
		(lambda x: ('G_SETTILE',(x[0],x[1],0,x[8],7,0,x[6],x[4],0,x[5],x[3],0))),
		(lambda x: ('G_RDPLOADSYNC',())),
		(lambda x: ('G_LOADBLOCK',(0,0,7,x[3]*x[4],CalcDxT(x[3],int(math.log(x[1]//4,2)))))),
		(lambda x: ('G_RDPPIPESYNC',())),
		(lambda x: ('G_SETTILE',(x[0],x[1],((int(math.log(x[1]//4,2))*x[3])+7)>>3,x[8],x[7],0,x[6],x[4],0,x[5],x[3],0))),
		(lambda x: ('G_SETTILESIZE',(0,0,x[7],x[3],x[4])))
	]
}

def CalcDxT(width, bitsiz):
	a = ((1 << 11) + max(1, width * bitsiz // 8) - 1)
	b = max(1, width * bitsiz // 8)
	return int(a // b)

class F3DEX2_encode():
	def __init__(self, cmd):
		self.cmd = cmd
		self.fmt = EncodeFmtEx2[cmd]
	def encode(self, *args):
		func = self.cmd + '_Encode'
		args = globals()[func](*args)
		return pack(self.fmt, *args)

#give cmd as string, and tuple of arguments to make parameter.
#use empty tuple () for no args
#single arg is tuple like this (arg,)
def Ex2Bin(cmd, V):
	c = F3DEX2_encode(cmd)
	return c.encode(*V)

#encode a macro
def Ex2Macro(macro, V):
    #each macro is a list of lambdas, which will take
    #a tuple of args and map to an Ex2Bin arg
    L = EncodeMacro[macro]
    m = 0
    for l in L:
        m += Ex2Encode(*l(V))
    return m

def Ex2Encode(cmd, V):
	try:
		return Ex2Macro(cmd, V)
	except:
		return Ex2Bin(cmd, V)

#take cmd label and tuple of args
#convert to binary
def G_SNOOP_Encode():
	return ()

def G_NOOP_Encode():
	return ()
	
def G_VTX_Encode(num, start, segment):
	start = start * 2 + num * 2
	return (num, start, segment)

def G_MODIFYVTX_Encode(param, buffer, value):
	enum = {
		'G_MWO_POINT_RGBA': 0x10,
		'G_MWO_POINT_ST': 0x14,
		'G_MWO_POINT_XYSCREEN': 0x18,
		'G_MWO_POINT_ZSCREEN': 0x1C
	}
	try:
		param = enum[param]
	except:
		pass
	return (param, buffer*2, value)

def G_CULLDL_Encode(first, last):
	return (first*2, last*2)

def G_BRANCH_Z_Encode(seg, t1, t2, zval):
	return (seg, t1*5, t2*2, zval)
	
def G_TRI1_Encode(v1, v2, v3):
	return (v1*2, v2*2, v3*2)

def G_TRI2_Encode(v1, v2, v3, v4, v5, v6):
	return (v1*2, v2*2, v3*2, v4*2, v5*2, v6*2)

def G_QUAD_Encode(v1, v2, v3, v4, v5, v6):
	return (v1*2, v2*2, v3*2, v4*2, v5*2, v6*2)

def G_DMA_IO_Encode(f, addr, size, dram):
	format = {
		'read': 0,
		'write': 1
	}
	try:
		f = format[f]
	except:
		pass
	return (f, addr >> 3 & 0x3ff, size, dram)

def G_TEXTURE_Encode(mip, tile, state, Sscale, Tscale):
	return (mip, tile, state, Sscale, Tscale)

def G_POPMTX_Encode(num):
	return (num * 64,)

def G_GEOMETRYMODE_Encode(clear, set):
	enums = {
		"Clear": 0,
		'G_ZBUFFER': 1,
		'G_SHADE': 4,
		'G_CULL_FRONT': 0X200,
		'G_CULL_BACK': 0X400,
		'G_FOG': 0X10000,
		'G_LIGHTING': 0X20000,
		'G_TEXTURE_GEN': 0X40000,
		'G_TEXTURE_GEN_LINEAR': 0X80000,
		'G_SHADING_SMOOTH': 0X200000,
		'G_CLIPPING': 0X800000,
		"All": 0xFFFFFF
	}
	clr = 0
	st = 0
	ORs = clear.split("|")
	VALs = set.split("|")
	#can't zip because they aren't gaurenteed to be same length
	for o in VALs:
		O = enums.get(o)
		if O is not None:
			st += O
	for o in ORs:
		O = enums.get(o)
		if O is not None:
			clr +=O 
	clr = ~clr & 0xFFFFFF
	return (clr, st)

def G_MTX_Encode(param, seg):
	return (param, seg)

def G_MOVEWORD_Encode(index, offset, value):
	indices = {
		'G_MW_MATRIX': 0,
		'G_MW_NUMLIGHT': 2,
		'G_MW_CLIP': 4,
		'G_MW_SEGMENT': 6,
		'G_MW_FOG': 8,
		'G_MV_LIGHTCOL': 10,
		'G_MW_FORCEMTX': 12,
		'G_MW_PERSPNORM': 14
	}
	try:
		index = indices[index]
	except:
		pass
	return (index, offset, value)

def G_MOVEMEM_Encode(size, offset, index, seg):
	indices = {
		'G_MV_MMTX': 2,
		'G_MV_PMTX': 6,
		'G_MV_VIEWPORT': 8,
		'G_MV_LIGHT': 10,
		'G_MV_POINT': 12,
		'G_MV_MATRIX': 14
	}
	try:
		index = indices[index]
	except:
		pass
	return ((((size >> 3) + 1) << 3), offset * 8, index, seg)

def G_LOAD_UCODE_Encode(data, size, text):
	return (data, size, text)

def G_DL_Encode(store, seg):
	return (store, seg)

def G_ENDDL_Encode():
	return ()

def G_SETOTHERMODE_L_Encode(clr, value):
	clrs = {
		'None': 0,
		'Render_Mode': 0xFFFFFFF8,
		'All': 4294967295
	}
	a = clrs.get(clr)
	if a:
		clr = str(a)
	b = Mode_Bits.get(value)
	if b:
		value = str(int(b, 16))
	Fields = {
		'None': 0,
		'G_MDSFT_AC_TRESHDITHER': 2,
		'G_MDSFT_ALPHACOMPARE': 3,
		'G_MDSFT_ZSRCSEL': 4,
		'G_MDSFT_RENDERMODE_CYCLE_IND': 65528,
		'G_MDSFT_RENDERMODE_CYCLE_DEP': 4294901760
	}
	Ind_MASK = {
		"AA_EN": 1 << 3,
		"Z_CMP": 1 << 4,
		"Z_UPD": 1 << 5,
		"IM_RD": 1 << 6,
		"CLR_ON_CVG": 1 << 7,
		"CVG_DST_CLAMP": 0,
		"CVG_DST_WRAP": 1 << 8,
		"CVG_DST_FULL": 2 << 8,
		"CVG_DST_SAVE": 3 << 8,
		"ZMODE_OPAQUE": 0,
		"ZMODE_INTER": 1 << 10,
		"ZMODE_XLU": 2 << 10,
		"ZMODE_DEC": 3 << 10,
		"CVG_X_ALPHA": 1 << 12,
		"ALPHA_CVG_SEL": 1 << 13,
		"FORCE_BL": 1 << 14
	}
	AC_Values = {
		"G_AC_NONE": 0,
		"G_AC_THRESHOLD": 1,
		"G_AC_DITHER": 3
	}
	ZSRC = {
		"Z_SEL_PRIMITIVE": 0,
		"Z_SEL_PIXEL": 4
	}
	ORs = clr.split("|")
	mask = 0
	for a in ORs:
		if a in Fields.keys():
			mask += Fields[a]
		elif a in Ind_MASK.keys():
			mask += Ind_MASK[a]
		else:
			mask += int(a)
	if type(value) == int:
		value = str(value)
	q = value.split("|")
	value = 0
	for a in q:
		if a in Fields.keys():
			value += Fields[a]
		elif a in Ind_MASK.keys():
			value += Ind_MASK[a]
		elif a in AC_Values.keys():
			value += AC_Values[a]
		elif a in ZSRC.keys():
			value += ZSRC[a]
		else:
			value += int(a)
	shift = 1
	while(True):
		if mask == 0:
			shift = 0
			break
		if mask & shift:
			break
		shift *= 2
	if shift:
		shift = int(math.log(shift, 2))
	bits = mask>>shift
	bits = int(math.log(bits + 1, 2))
	return (32 - (shift + bits), bits - 1, value)

def G_SETOTHERMODE_H_Encode(mask, value):
	enums = {
		'G_MDSFT_BLENDMASK':[0, 0],
		'G_MDSFT_ALPHADITHER':[32 - 4 - 2, 1],
		'G_MDSFT_RGBDITHER':[32 - 6 - 2, 1],
		'G_MDSFT_COMBKEY':[32 - 1 - 8, 0],
		'G_MDSFT_TEXTCONV':[32 - 3 - 9, 2],
		'G_MDSFT_TCFILT':[32 - 1 - 10, 0],
		'G_MDSFT_TEXTFILT':[32 - 2 - 12, 1],
		'G_MDSFT_BILERP':[32 - 1 - 13, 0],
		'G_MDSFT_TEXTLUT':[32 - 2 - 14, 1],
		'G_MDSFT_RGBALUT':[32 - 1 - 15, 0],
		'G_MDSFT_TEXTLOD':[32 - 1 - 16, 0],
		'G_MDSFT_TEXTDETAIL':[32 - 2 - 17, 1],
		'G_MDSFT_TD_DETAIL':[32 - 1 - 18, 0],
		'G_MDSFT_TEXTPERSP':[32 - 1 - 19, 0],
		'G_MDSFT_CYCLETYPE':[32 - 2 - 20, 1],
		'G_MDSFT_COLORDITHER':[32 - 1 - 22, 0],
		'G_MDSFT_PIPELINE':[32 - 1 - 23, 0]
	}
	clr = enums.get(mask)
	if clr:
		[shift,bits] = [clr[0] - clr[1] - 33, clr[1] + 1]
	else:
		mask = int(mask)
		shift = 1
		while(True):
			if mask == 0:
				shift = 0
				break
			if mask&shift:
				break
			shift *= 2
		if shift:
			shift = int(math.log(shift, 2))
		bits = mask >> shift
		bits = int(math.log(bits + 1, 2))
	return (shift + bits + 32, bits - 1, value)

def G_TEXRECT_Encode(Xstart, Ystart, tile, Xend, Yend, Sstart, Tstart, dsdx, dtdy):
	return (Xstart, Ystart, tile, Xend, Yend, Sstart, Tstart, dsdx, dtdy)

def G_TEXRECTFLIP_Encode(Xstart, Ystart, tile, Xend, Yend, Sstart, Tstart, dsdx, dtdy):
	return (Xstart, Ystart, tile, Xend, Yend, Sstart, Tstart, dsdx, dtdy)

def G_RDPLOADSYNC_Encode():
	return()
def G_RDPPIPESYNC_Encode():
	return()
def G_RDPTILESYNC_Encode():
	return()
def G_RDPFULLSYNC_Encode():
	return()


def G_SETKEYGB_Encode(Gwidth, Bwidth, Gint, Grecip, Bint, Brecip):
	return (Gwidth, Bwidth, Gint, Grecip, Bint, Brecip)

def G_SETKEYR_Encode(Rwidth, Rint, Rrecip):
	return (Rwidth, Rint, Rrecip)

def G_SETCONVERT_Encode(*arg):
	return arg

def G_SETSCISSOR_Encode(Xstart, Ystart, mode, Xend, Yend):
	try:
		modes = {
			'G_SC_NON_INTERLACE': 0,
			'G_SC_EVEN_INTERLACE': 2,
			'G_SC_ODD_INTERLACE': 3
		}
		mode = modes[mode]
	except:
		pass
	return (Xstart, Ystart, mode, Xend, Yend)

def G_SETPRIMDEPTH_Encode(zval, depth):
	return (zval, depth)

def G_RDPSETOTHERMODE_Encode(hi, lo):
	return (hi, lo)

def G_LOADTLUT_Encode(tile, color):
	return (tile, (((color - 1) & 0x3ff) << 2))

def G_RDPHALF_2_Encode(bits):
	return (bits,)

def G_SETTILESIZE_Encode(Sstart, Tstart, tile, width, height):
	return (Sstart, Tstart, tile, (width - 1) << 2, (height - 1) <<2)

def G_LOADBLOCK_Encode(Sstart, Tstart, tile, texels, dxt):
	return (Sstart, Tstart, tile, texels - 1, dxt)

def G_LOADTILE_Encode(Sstart, Tstart, tile, Send, Tend):
	return (Sstart * 4, Tstart * 4, tile, Send * 4, Tend * 4)

def G_SETTILE_Encode(fmt, bitsize, numrows, offset, tile, palette, Tflag,
					Tmask, Tshift, Sflag, Smask, Sshift):
	flags = {
		'wrap': 0,
		'clamp': 2,
		'mirror': 1,
		'clamp & mirror': 3
	}
	fmts = {
		'RGBA': 0,
		'YUV': 1,
		'CI': 2,
		'IA': 3,
		'I': 4
	}
	try:
		fmt = fmts[fmt]
	except:
		pass
	bitsize = math.log(bitsize / 4, 2)
	try:
		Sflag = flags[Sflag]
	except:
		pass
	try:
		Tflag = flags[Tflag]
	except:
		pass
	return (fmt, bitsize, numrows, offset, tile, palette, Tflag, math.log2(Tmask), Tshift, Sflag, math.log2(Smask), Sshift)

def G_FILLRECT_Encode(Sstart, Tstart, Send, Tend):
	return (Sstart, Tstart, Send, Tend)

#fog,env,blend,fill
def G_SETFILLCOLOR_Encode(r, g, b, a):
	return (r, g, b, a)

def G_SETFOGCOLOR_Encode(r, g, b, a):
	return (r, g, b, a)

def G_SETENVCOLOR_Encode(r, g, b, a):
	return (r, g, b, a)

def G_SETBLENDCOLOR_Encode(r, g, b, a):
	return (r, g, b, a)

def G_SETPRIMCOLOR_Encode(min, fraction, r, g, b, a):
	return (min*256, fraction*256, r, g, b, a)

def G_SETCOMBINE_Encode(a, g, b, k, c, l, d, m, e, h, f, n, i, o, j, p):
	Basic = {
		'Texel 0': 1,
		'Texel 1': 2,
		'Primitive': 3,
		'Shade': 4,
		'Environment': 5
	}
	One = {
		'1.0': 6
	}
	Combined = {
		'Combined': 0
	}
	CombinedA = {
		'Combined Alpha': 0
	}
	C = {
		'Key: Scale': 6,
		'Combined Alpha': 7,
		'Texel 0 Alpha': 8,
		'Texel 1 Alpha': 9,
		'Primitive Alpha': 10,
		'Shade Alpha': 11,
		'Environment Alpha': 12,
		'LOD fraction': 13,
		'Primitive LOD fraction': 14,
		'Convert K5': 15
	}
	Noise = {
		'Noise': 7
	}
	Key = {
		'Key: Center': 6,
		'Key: 4': 7
	}
	BasicA = {
		'Texel 0 Alpha': 1,
		'Texel 1 Alpha': 2,
		'Primitive Alpha': 3,
		'Shade Alpha': 4,
		'Environment Alpha': 5
	}
	LoD = {
		'LoD Fraction': 0
	}
	#a color = basic+one+combined+7as noise
	#b color = basic+combined+6 as key center+7 as key4
	#c color = basic+combined+C
	#d color = basic+combined+one
	
	#a alpha = basicA+one+combined
	#b alpha = a alpha
	#c alpha = basic+one+0 asLoD fraction
	#d alpha = a alpha
	#zero will be default, aka out of range
	
	ACmode = {**Basic, **Noise, **Combined, **One}
	BCmode = {**Basic, **Key, **Combined}
	CCmode = {**Basic, **C, **Combined}
	DCmode = {**Basic, **One, **Combined}

	AAmode = {**BasicA, **CombinedA, **One}
	BAmode = {**BasicA, **One, **CombinedA}
	CAmode = {**BasicA, **LoD}
	DAmode = {**BasicA, **One, **CombinedA}

	Acolor = (a, e)
	Bcolor = (g, h)
	Ccolor = (b, f)
	Dcolor = (k, n)

	Aalpha = (c, i)
	Balpha = (l, o)
	Calpha = (d, j)
	Dalpha = (m, p)

	[a, e] = [ACmode.get(color, 15) for color in Acolor]
	[g, h] = [BCmode.get(color, 15) for color in Bcolor]
	[b, f] = [CCmode.get(color, 31) for color in Ccolor]
	[k, n] = [DCmode.get(color, 7) for color in Dcolor]

	[c, i] = [AAmode.get(color, 7) for color in Aalpha]
	[l, o] = [BAmode.get(color, 7) for color in Balpha]
	[d, j] = [CAmode.get(color, 7) for color in Calpha]
	[m, p] = [DAmode.get(color, 7) for color in Dalpha]

	return (a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p)

def G_SETTIMG_Encode(fmt, bit, seg):
	fmts = {
		'RGBA': 0,
		'YUV': 1,
		'CI': 2,
		'IA': 3,
		'I': 4
	}
	try:
		fmt = fmts[fmt]
	except:
		pass
	bit = math.log(bit / 4, 2)
	return (fmt, bit, seg)

def G_SETZIMG_Encode(addr):
	return (addr,)

def G_SETCIMG_Encode(fmt, bit, width, addr):
	return (fmt, bit, width, addr)

#end f3dex2 words to binary
#still really rough I will improve

#f3dex2 binary start
#takes bin, and returns a string matching gbi macro


class F3DEX2_decode():
	def __init__(self, cmd):
		self.fmt, self.func = DecodeFmtEx2[cmd]
	def decode(self, cmd, *args):
		if self.fmt == 'gsSPDisplayList':
			if args[0][0]:
				self.fmt = 'gsSPBranchList'
			args = ((args[0][1],),)
		if self.fmt == 'gsMoveWd':
			return MoveWd(args)
		if self.fmt == 'G_SETOTHERMODE_L':
			return OtherModeL(args)
		if self.fmt == 'G_SETOTHERMODE_H':
			return OtherModeH(args)
		return f"{self.fmt}{','.join([str(a) for a in args])}".replace("'",'')

#give cmd as binary.
#should return cmd as string, and args as tuple
def Ex2String(cmd):
	cmd = BitArray(cmd)
	c = F3DEX2_decode(cmd[0:8].uint)
	V = c.func(cmd[8:])
	return c.decode(c.fmt, V)

#othermode L just needs a bit of massaging
def OtherModeL(args):
	m = args[0][0]
	a = args[0][1:]
	q = f"{m}({', '.join(a)})"
	return q

#move word is split into several macros, so I should decode it as much as possible
def MoveWd(args):
	#just a lambda to do math on the args if possible
	enum = args[0][0]
	offset = args[0][1]
	value = args[0][2]
	if enum == 'gsSPLightColor':
		num = offset // 0x18 + 1
		b = (offset % 0x18) == 4
		return f"{enum}(G_MWO_{'a'*(not b) + 'b'*b}LIGHT_{num}, 0x{value:02X})"
	if enum == "gsSPSegment":
		return f"{enum}(G_MWO_SEGMENT_{offset//4}, 0x{value:02X})"
	if enum == "gsSPFogPosition":
		high = (value >> 16) & ((1 << 16) - 1)
		low = (value & ((1 << 16) - 1))
		if high > 0x8000:
			high = -0x10000 + high
		if low > 0x8000:
			low = -0x10000 + low
		diff = 128000 / high
		minn = 500 - (low * diff / 256)
		maxx = diff + minn
		return f"{enum}({int(minn)}, {int(maxx)})"
	if enum == "gsSPNumLights":
		return f"{enum}(G_MWO_NUMLIGHT, 0x{value // 24:02X})"
	#tbh the rest are probably not used, so just return the gsMoveWd
	return f"gsMoveWd({args[0]})"

#othermode H doesn't really fit the scheme well so take the args and unfuck them
def OtherModeH(args):
	#macro name of set/unset: (gbi macro name, dict of values for values)
	Macros = {
		"G_MDSFT_ALPHADITHER": ("gsDPSetAlphaDither",
			{
				0 << 4: "G_AD_PATTERN",
				1 << 4: "G_AD_NOTPATTERN",
				2 << 4: "G_AD_NOISE",
				3 << 4: "G_AD_DISABLE",
			}
			),
		"G_MDSFT_RGBDITHER": ("gsDPSetColorDither",
			{
				0 << 6: "G_CD_MAGICSQ",
				1 << 6: "G_CD_BAYER",
				2 << 6: "G_CD_NOISE",
			}
			),
		"G_MDSFT_COMBKEY": ("gsDPSetCombineKey",
			{
				0 << 8: "G_CK_NONE",
				1 << 8: "G_CK_KEY",
			}
			),
		"G_MDSFT_TEXTCONV": ("gsDPSetTextureConvert",
			{
				0 << 9: "G_TC_CONV",
				5 << 9: "G_TC_FILTCONV",
				6 << 9: "G_TC_FILT",
			}
			),
		"G_MDSFT_TEXTFILT": ("gsDPSetTextureFilter",
			{
				0 << 12: "G_TF_POINT",
				3 << 12: "G_TF_AVERAGE",
				2 << 12: "G_TF_BILERP",
			}
			),
		"G_MDSFT_TEXTLUT": ("gsDPSetTextureLUT",
			{
				0 << 14: "G_TT_NONE",
				2 << 14: "G_TT_RGBA16",
				3 << 14: "G_TT_IA16",
			}
			),
		"G_MDSFT_TEXTLOD": ("gsDPSetTextureLOD",
			{
				0 << 16: "G_TL_TILE",
				1 << 16: "G_TL_LOD",
			}
			),
		"G_MDSFT_TEXTDETAIL": ("gsDPSetTextureDetail",
			{
				0 << 17: "G_TD_CLAMP",
				1 << 17: "G_TD_SHARPEN",
				2 << 17: "G_TD_DETAIL",
			}
			),
		"G_MDSFT_TEXTPERSP": ("gsDPSetTexturePersp",
			{
				0 << 19: "G_TP_NONE",
				1 << 19: "G_TP_PERSP",
			}
			),
		"G_MDSFT_CYCLETYPE": ("gsDPSetCycleType",
			{
				0 << 20: "G_CYC_1CYCLE",
				1 << 20: "G_CYC_2CYCLE",
				2 << 20: "G_CYC_COPY",
				3 << 20: "G_CYC_FILL",
			}
			),
		"G_MDSFT_PIPELINE": ("gsDPPipelineMode",
			{
				0 << 23: "G_PM_1PRIMITIVE",
				1 << 23: "G_PM_NPRIMITIVE",
			}
			),
	}
	affect = args[0][0]
	arg = args[0][1]
	gbi = Macros.get(affect)
	#not a macro
	if not gbi:
		shift = 0
		while(True):
			if (affect >> shift) & 1:
				break
			shift += 1
		num = math.ceil(math.log2(affect >> shift))
		return f"gsSPSetOtherMode(G_SETOTHERMODE_H, {shift}, {num}, {arg})"
	name = gbi[0]
	arg = gbi[1].get(arg)
	return f"{name}({arg})"


#take argument bits and make tuple of args

def G_SNOOP_Decode(bin):
	return ()

def G_VTX_Decode(bin):
	pad, num, pad1, start, segment = bin.unpack('int:4, uint:8, int:4, uint:8, uint:32')
	return (segment, num, int((start - num * 2) / 2))

def G_MODIFYVTX_Decode(bin):
	param, buffer, value = bin.unpack('uint:8, uint:16, uint:32')
	enum = {
		0x10: 'G_MWO_POINT_RGBA',
		0x14: 'G_MWO_POINT_ST',
		0x18: 'G_MWO_POINT_XYSCREEN',
		0x1c: 'G_MWO_POINT_ZSCREEN'
	}
	try:
		param = enum[param]
	except:
		pass
	return (param, int(buffer / 2), value)

def G_CULLDL_Decode(bin):
	pad, first, pad1, last = bin.unpack('int:8, 3*uint:16')
	return (first // 2, last // 2)

def G_BRANCH_Z_Decode(bin):
	seg, t1, t2, zval = bin.unpack('4*int:4')
	return (seg, t1*5, t2*2, zval)

def G_TRI1_Decode(bin):
	v = bin.unpack('3*uint:8')
	return (*(a // 2 for a in v), 1)

def G_TRI2_Decode(bin):
	v = bin.unpack('7*uint:8')
	return (*(a // 2 for a in v[0:3]), 1, *(a // 2 for a in v[4:7]), 1)

def G_QUAD_Decode(bin):
	v1, v2, v3, pad, v4, v5, v6 = bin.unpack('7*uint:8')
	return (int(v1 / 2), int(v2 / 2), int(v3 / 2), int(v4 / 2), int(v5 / 2), int(v6 / 2), 1)

def G_DMA_IO_Decode(bin):
	f, addr, pad, size, dram = bin.unpack('uint:1, uint:10, int:1, uint:12, uint:32')
	format = {
		0: 'read',
		1: 'write'
	}
	try:
		f = format[f]
	except:
		pass
	return (f, addr << 3, size, dram)

def G_TEXTURE_Decode(bin):
	pad, mip, tile, state, Sscale, Tscale = bin.unpack('int:10, 2*uint:3, uint:8, 2*int:16')
	return (Sscale, Tscale, mip, tile, state)

def G_POPMTX_Decode(bin):
	pad, num = bin.unpack('int:24, uint:32')
	return (int(num / 64),)

def G_GEOMETRYMODE_Decode(bin):
	clear, set = bin.unpack('uint:24, uint:32')
	clear = ~clear & 0xFFFFFF
	enums = {
		1: 'G_ZBUFFER',
		4: 'G_SHADE',
		0x200: 'G_CULL_FRONT',
		0x400: 'G_CULL_BACK',
		65536: 'G_FOG',
		131072: 'G_LIGHTING',
		262144: 'G_TEXTURE_GEN',
		524288: 'G_TEXTURE_GEN_LINEAR',
		2097152: 'G_SHADING_SMOOTH',
		8388608: 'G_CLIPPING',
		0xFFFFFF: 'All'
	}
	clr = []
	st = []
	if clear == 0:
		clr.append("0")
	if set == 0:
		st.append("0")
	for k, v in enums.items():
		if clear & k:
			clr.append(v)
			clear ^= k
		if set & k:
			st.append(v)
			set ^= k
	if clear != 0:
		clr.append(str(clear))
	if set != 0:
		st.append(str(set))
	return (' | '.join(clr), ' | '.join(st))

def G_MTX_Decode(bin):
	pad, param, seg = bin.unpack('int:16, uint:8, uint:32')
	return (param, seg)

def G_MOVEWORD_Decode(bin):
	index, offset, value = bin.unpack('uint:8, uint:16, uint:32')
	#use gbi names where possible for macros instead of enumerations
	indices={
		0: 'gsSPInsertMatrix', #no longer supported in ex2
		2: 'gsSPNumLights',
		4: 'G_MW_CLIP', #this is actually 4 cmds so don't do it because no support for that
		6: 'gsSPSegment',
		8: 'gsSPFogPosition',
		10: 'gsSPLightColor',
		12: 'G_MW_FORCEMTX', #actually two cmds, so again don't fix
		14: 'gsSPPerspNormalize'
	}
	try:
		index = indices[index]
	except:
		pass
	return (index, offset, value)

def G_MOVEMEM_Decode(bin):
	size, offset, index, seg = bin.unpack('3*uint:8, uint:32')
	indices={
		2: 'G_MV_MMTX',
		6: 'G_MV_PMTX',
		8: 'G_MV_VIEWPORT',
		10: 'G_MV_LIGHT',
		12: 'G_MV_POINT',
		14: 'G_MV_MATRIX'
	}
	try:
		index = indices[index]
	except:
		pass
	return ((((size >> 3) - 1) << 3), int(offset / 8), index, seg)

def G_LOAD_UCODE_Decode(bin):
	#idk yet
	return (data, size, text)

def G_DL_Decode(bin):
	store, pad, seg = bin.unpack('uint:8, int:16, uint:32')
	return (store, seg)

def G_ENDDL_Decode(bin):
	return ()

def G_RDPHALF_1_Decode(bin):
	pad, bits = bin.unpack('int:24, uint:32')
	return (bits,)

def G_SETOTHERMODE_L_Decode(bin):
	pad, shift, bits, value = bin.unpack('3*uint:8, uint:32')
	mask = ((1 << (bits + 1)) - 1) << (32 - shift - bits - 1)
	skip = 0xFFFFFFF8
	all = 0xFFFFFFFF
	none = 0
	# if not a and mask==skip:
		# print(Macro)
		# time.sleep(1)
	if mask == skip:
		clk1 = value & (((3 << 12) + (3 << 8) + (3 << 4) + 3) << 18) + (0x1FFF << 3)
		#if pass, don't take cycle dependent args for 1 cycle, same with fog shade
		if clk1 & 0x0C080000 == 0x0C080000:
			clk1 = 0x0C080000
		#fog shade surf
		if clk1 & 0xC8000000 == 0xC8000000:
			clk1 = 0xC8000000
		#fog shade prim
		if clk1 & 0xC4000000 == 0xC4000000:
			clk1 = 0xC4000000
		clk2 = value & (((3 << 12) + (3 << 8) + (3 << 4) + 3) << 16) + (0x1FFF << 3)
		#print(f"0x{clk1:08X} cycle 1 - 0x{clk2:08X} cycle 2  - 0x{value:08X} value")
		a, b = Render_Modes.get(clk1, f"0x{clk1:08X}"), Render_Modes.get(clk2, f"0x{clk2:08X}")
		if a not in Render_Modes.values() or b not in Render_Modes.values() :
			print(f"{a} - cycle 1 {b} - cycle 2")
		return ("gsDPSetRenderMode", a, b)
	if mask == all and a:
		return ("All",a)
	if mask == none:
		return ("None","None")
	
	Z_Values = {
		0: "ZMODE_OPAQUE",
		1 << 10: "ZMODE_INTER",
		2 << 10: "ZMODE_XLU",
		3 << 10: "ZMODE_DEC",
	}
	
	CVG_Values = {
		0: "CVG_DST_CLAMP",
		1 << 8: "CVG_DST_WRAP",
		2 << 8: "CVG_DST_FULL",
		3 << 8: "CVG_DST_SAVE"
	}
	
	Ind_Clr = {
		1 << 3: ["AA_EN", 0],
		1 << 4: ["Z_CMP", 0],
		1 << 5: ["Z_UPD", 0],
		1 << 6: ["IM_RD", 0],
		1 << 7: ["CLR_ON_CVG", 0],
		3 << 8: ["CVG_DST_", CVG_Values],
		3 << 10: ["ZMODE_", Z_Values],
		1 << 12: ["CVG_X_ALPHA", 0],
		1 << 13: ["ALPHA_CVG_SEL", 0],
		1 << 14: ["FORCE_BL", 0]
	}
	
	AC_Values = {
		3: ["G_AC_DITHER", 0],
		0: ["G_AC_NONE", 0],
		1: ["G_AC_THRESHOLD", 0]
	}
	
	ZSRC = {
		4: ["Z_SEL_PIXEL", 0],
		0: ["Z_SEL_PRIMITIVE", 0]
	}
	empty = {}
	Fields = {
		3: ['gsDPSetAlphaCompare', AC_Values],
		4: ['gsDPSetDepthSource', ZSRC],
		65528: ['G_MDSFT_RENDERMODE_CYCLE_IND', Ind_Clr],
		4294901760: ['G_MDSFT_RENDERMODE_CYCLE_DEP', empty]
	}
	
	clr = []
	set = []
	count = 0
	for f,m in Fields.items():
		if mask==f:
			clr.append(m[0])
			for v,s in m[1].items():
				if s[1]:
					for q,w in s[1].items():
						if (value&v)==q:
							set.append(w)
							value = value ^ q
							break
				elif (value & v) == v and v != 0:
					set.append(s[0])
					value = value ^ v
				elif value == 0 and v == 0:
					set.append(s[0])
					break
			break
		elif mask&f == f:
			clr.append(m[0])
			for v, s in m[1].items():
				if f == 65528:
					if s[1]:
						for q,w in s[1].items():
							if (value & v) == q:
								set.append(w)
								value = value^q
								break
					elif (value&v) == v:
						set.append(s[0])
						value = value^v
				elif (value&f)==v:
					set.append(s[0])
					value = value^v
		elif mask&f:
			if f==65528:
				for v,s in Ind_Clr.items():
					if mask&v==v:
						clr.append(s[0])
						if s[1]:
							for q,w in s[1].items():
								if value&v==q:
									set.append(w)
									value = value ^ q
									break
						else:
							if value&v==v:
								set.append(s[0])
								value = value^v
			else:
				clr.append(str(mask&f))
	if value:
		set.append(str(value))
	if clr == []:
		clr = [str(mask)]
	return (' | '.join(clr), ' | '.join(set))

def G_SETOTHERMODE_H_Decode(bin):
	pad, shift, bits, value = bin.unpack('3*uint:8, uint:32')
	enums = {
		0: 'G_MDSFT_BLENDMASK',
		48: 'G_MDSFT_ALPHADITHER',
		192: 'G_MDSFT_RGBDITHER',
		256: 'G_MDSFT_COMBKEY',
		3584: 'G_MDSFT_TEXTCONV',
		1024: 'G_MDSFT_TCFILT',
		12288: 'G_MDSFT_TEXTFILT',
		8192: 'G_MDSFT_BILERP',
		49152:'G_MDSFT_TEXTLUT',
		65536: 'G_MDSFT_TEXTLOD',
		393216: 'G_MDSFT_TEXTDETAIL',
		524288: 'G_MDSFT_TEXTPERSP',
		3145728: 'G_MDSFT_CYCLETYPE',
		4194304: 'G_MDSFT_COLORDITHER',
		8388608: 'G_MDSFT_PIPELINE'
	}
	mask = ((1 << bits + 1) - 1) << (32 -shift - bits - 1)
	clr = enums.get(mask)
	if clr:
		mask = clr
	return (mask, value)

def G_TEXRECT_Decode(bin):
	Xstart,Ystart,pad,tile,Xend,Yend,pad1,Sstart,Tstart,pad2,dsdx,dtdy=bin.unpack('2*uint:12,2*int:4,2*uint:12,uint:32,2*uint:16,uint:32,2*uint:16')
	return (Xstart,Ystart,Xend,Yend,tile,Sstart,Tstart,dsdx,dtdy)

def G_SETKEYGB_Decode(bin):
	Gwidth,Bwidth,Gint,Grecip,Bint,Brecip=bin.unpack('2*uint:12,4*uint:8')
	return (Gint,Grecip,Gwidth,Bint,Brecip,Bwidth)

def G_SETKEYR_Decode(bin):
	pad,Rwidth,Rint,Rrecip=bin.unpack('int:28,uint:12,2*uint:8')
	return (Rrecip,Rwidth,Rint)

def G_SETCONVERT_Decode(bin):
	p,k0,k1,k2,k3,k4,k5=bin.unpack('int:2,6*int:9')
	return (k0,k1,k2,k3,k4,k5)

def G_SETSCISSOR_Decode(bin):
	Xstart,Ystart,pad,mode,Xend,Yend=bin.unpack('2*uint:12,2*uint:4,2*uint:12')
	try:
		modes={0:'G_SC_NON_INTERLACE',
		2:'G_SC_EVEN_INTERLACE',
		3:'G_SC_ODD_INTERLACE'}
		mode=modes[mode]
	except:
		mode='invalid mode'
	return (mode,Xstart,Ystart,Xend,Yend)

def G_SETPRIMDEPTH_Decode(bin):
	pad,zval,depth=bin.unpack('int:24,2*uint:16')
	return (zval,depth)

def G_RDPSETOTHERMODE_Decode(bin):
	hi,lo=bin.unpack('uint:24,uint:32')
	return (hi,lo)

def G_LOADTLUT_Decode(bin):
	pad,tile,color,pad1=bin.unpack('int:28,uint:4,2*uint:12')
	return (tile,(((color>>2)&0x3ff)+1))

def G_RDPHALF_2_Decode(bin):
	pad,bits=bin.unpack('int:24,uint:32')
	return (bits,)

def G_SETTILESIZE_Decode(bin):
	Sstart,Tstart,pad,tile,width,height=bin.unpack('2*uint:12,2*uint:4,2*uint:12')
	return (tile,Sstart,Tstart,(width>>2)+1,(height>>2)+1)

def G_LOADBLOCK_Decode(bin):
	Sstart,Tstart,pad,tile,texels,dxt=bin.unpack('2*uint:12,2*uint:4,2*uint:12')
	return (tile,Sstart,Tstart,texels+1,dxt)

def G_LOADTILE_Decode(bin):
	Sstart,Tstart,pad,tile,Send,Tend=bin.unpack('2*uint:12,2*uint:4,2*uint:12')
	return (tile,Sstart>>2,Tstart>>2,Send>>2,Tend>>2)

def G_SETTILE_Decode(bin):
	fmt,bitsize,pad,numrows,offset,pad1,tile,palette,Tflag,Tmask,Tshift,Sflag,Smask,Sshift=bin.unpack('uint:3,uint:2,int:1,2*uint:9,int:5,uint:3,uint:4,uint:2,2*uint:4,uint:2,2*uint:4')
	flags={
		0:'G_TX_WRAP',
		2:'G_TX_CLAMP',
		1:'G_TX_MIRROR',
		3:'G_TX_CLAMP | G_TX_MIRROR'
	}
	try:
		Tflag = flags[Tflag]
		Sflag = flags[Sflag]
		fmt = fmts_dec[fmt]
		bitsize = bits_dec[bitsize]
	except:
		pass
	return (fmt,bitsize,numrows,offset,tile,palette,Tflag,Tmask,Tshift,Sflag,Smask,Sshift)

def G_FILLRECT_Decode(bin):
	Xstart,Ystart,pad,Xend,Yend=bin.unpack('2*uint:12,uint:8,2*uint:12')
	return (Xstart,Ystart,Xend,Yend)

#fog,env,blend,fill
def G_COLOR_Decode(bin):
	pad, r, g, b, a = bin.unpack('int:24,4*uint:8')
	return (r, g, b, a)

def G_FILLCOLOR_Decode(bin):
	p, d = bin.unpack('int:24,int:32')
	return d

def G_SETPRIMCOLOR_Decode(bin):
	pad, min, fraction, r, g, b, a=bin.unpack('7*uint:8')
	return (min, fraction, r, g, b, a)

def G_SETCOMBINE_Decode(bin):
	a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p = bin.unpack('uint:4,uint:5,2*uint:3,uint:4,uint:5,2*uint:4,8*uint:3')
	Basic = {
		1: 'TEXEL0',
		2: 'TEXEL1',
		3: 'PRIMITIVE',
		4: 'SHADE',
		5: 'ENVIRONMENT'
	}
	One = {
		6: '1'
	}
	Combined = {
		0: 'COMBINED'
	}
	C = {
		6: 'SCALE',
		7: 'COMBINED_ALPHA',
		8: 'TEXEL0_ALPHA',
		9: 'TEXEL1_ALPHA',
		10: 'PRIMITIVE_ALPHA',
		11: 'SHADE_ALPHA',
		12: 'ENV_ALPHA',
		13: 'LOD_FRACTION',
		14: 'PRIM_LOD_FRAC',
		15: 'K5'
	}
	Noise = {
		7: 'NOISE'
	}
	Key = {
		6: 'CENTER',
		7: 'K4'
	}
	BasicA = {
		1: 'TEXEL0',
		2: 'TEXEL1',
		3: 'PRIMITIVE',
		4: 'SHADE',
		5: 'ENVIRONMENT'
	}
	LoD = {
		0: 'LOD_FRACTION'
	}
	#a color = basic+one+combined+7as noise
	#b color = basic+combined+6 as key center+7 as key4
	#c color = basic+combined+C
	#d color = basic+combined+one
	
	#a alpha = basicA+one+combined
	#b alpha = a alpha
	#c alpha = basic+one+0 asLoD fraction
	#d alpha = a alpha
	#zero will be default, aka out of range
	ACmode = {**Basic, **Noise, **Combined, **One}
	BCmode = {**Basic, **Key, **Combined}
	CCmode = {**Basic, **C, **Combined}
	DCmode = {**Basic, **One, **Combined}

	AAmode = {**BasicA, **Combined, **One}
	BAmode = {**BasicA, **One, **Combined}
	CAmode = {**BasicA, **LoD}
	DAmode = {**BasicA, **One, **Combined}

	Acolor = (a, e)
	Bcolor = (g, h)
	Ccolor = (b, f)
	Dcolor = (k, n)

	Aalpha = (c, i)
	Balpha = (l, o)
	Calpha = (d, j)
	Dalpha = (m, p)
	[a, e] = [ACmode.get(color, '0') for color in Acolor]
	[g, h] = [BCmode.get(color, '0') for color in Bcolor]
	[b, f] = [CCmode.get(color, '0') for color in Ccolor]
	[k, n] = [DCmode.get(color, '0') for color in Dcolor]

	[c, i] = [AAmode.get(color, '0') for color in Aalpha]
	[l, o] = [BAmode.get(color, '0') for color in Balpha]
	[d, j] = [CAmode.get(color, '0') for color in Calpha]
	[m, p] = [DAmode.get(color, '0') for color in Dalpha]

	return (a, g, b, k, c, l, d, m, e, h, f, n, i, o, j, p)

def G_SETTIMG_Decode(bin):
	fmt, bit, pad, seg = bin.unpack('uint:3,uint:2,uint:19,uint:32')
	try:
		fmt = fmts_dec[fmt]
		bit = bits_dec[bit]
	except:
		pass
	return ('G_SETTIMG', fmt, bit, seg)

def G_SETZIMG_Decode(bin):
	pad, addr = bin.unpack('int:24,uint:32')
	return (addr,)

def G_SETCIMG_Decode(bin):
	fmt, bit, pad, width, addr = bin.unpack('uint:3,uint:2,int:7,uint:12,uint:32')
	return ('G_SETCIMG', fmt, bit, width, addr)

fmts_dec = {
	0: 'G_IM_FMT_RGBA',
	1: 'G_IM_FMT_YUV',
	2: 'G_IM_FMT_CI',
	3: 'G_IM_FMT_IA',
	4: 'G_IM_FMT_I'
}

bits_dec = {
	0: 'G_IM_SIZ_4b',
	1: 'G_IM_SIZ_8b',
	2: 'G_IM_SIZ_16b',
	3: 'G_IM_SIZ_32b',
	5: 'G_IM_SIZ_DD'
}

DecodeFmtEx2={
	0x0:('gsSPNoOp',G_SNOOP_Decode),
	0x01:('gsSPVertex',G_VTX_Decode),
	0x02:('gsSPModifyVertex',G_MODIFYVTX_Decode),
	0x03:('gsSPCullDisplayList',G_CULLDL_Decode),
	0x04:('gsSPBranchLessZ',G_BRANCH_Z_Decode),
	0x05:('gsSP1Triangle',G_TRI1_Decode),
	0x06:('gsSP2Triangles',G_TRI2_Decode),
	0x07:('gsSP1Quadrangle',G_QUAD_Decode),
	0xd6:('G_DMA_IO',G_DMA_IO_Decode),
	0xd7:('gsSPTexture',G_TEXTURE_Decode),
	0xd8:('gsSPPopMatrix',G_POPMTX_Decode),
	0xd9:('gsSPGeometryMode',G_GEOMETRYMODE_Decode),
	0xda:('gsSPMatrix',G_MTX_Decode),
	0xdb:('gsMoveWd',G_MOVEWORD_Decode),
	0xdc:('gsSPMoveMem',G_MOVEMEM_Decode),
	0xdd:('G_LOAD_UCODE',G_LOAD_UCODE_Decode),
	0xde:('gsSPDisplayList',G_DL_Decode),
	0xdf:('gsSPEndDisplayList',G_ENDDL_Decode),
	0xe0:('gsSPNoOp',G_SNOOP_Decode),
	0xe1:('G_RDPHALF_1',G_RDPHALF_1_Decode),
	0xe2:('G_SETOTHERMODE_L',G_SETOTHERMODE_L_Decode),
	0xe3:('G_SETOTHERMODE_H',G_SETOTHERMODE_H_Decode),
	0xe4:('gsDPTextureRectangle',G_TEXRECT_Decode),
	0xe5:('gsDPTextureRectangleFlip',G_TEXRECT_Decode),
	0xe6:('gsDPLoadSync',G_SNOOP_Decode),
	0xe7:('gsDPPipeSync',G_SNOOP_Decode),
	0xe8:('gsDPTileSync',G_SNOOP_Decode),
	0xe9:('gsDPFullSync',G_SNOOP_Decode),
	0xea:('gsDPSetKeyGB',G_SETKEYGB_Decode),
	0xeb:('gsDPSetKeyR',G_SETKEYR_Decode),
	0xec:('gsDPSetConvert',G_SETCONVERT_Decode),
	0xed:('gsDPScissor',G_SETSCISSOR_Decode),
	0xee:('gsDPSetPrimDepth',G_SETPRIMDEPTH_Decode),
	0xef:('gsSPSetOtherMode',G_RDPSETOTHERMODE_Decode),
	0xf0:('gsDPLoadTLUT',G_LOADTLUT_Decode),
	0xf1:('G_RDPHALF_2',G_RDPHALF_2_Decode),
	0xf2:('gsDPSetTileSize',G_SETTILESIZE_Decode),
	0xf3:('gsDPLoadBlock',G_LOADBLOCK_Decode),
	0xf4:('gsDPLoadTile',G_LOADTILE_Decode),
	0xf5:('gsDPSetTile',G_SETTILE_Decode),
	0xf6:('gsDPFillRectangle',G_FILLRECT_Decode),
	0xf7:('gsDPSetFillColor',G_FILLCOLOR_Decode),
	0xf8:('gsDPSetFogColor',G_COLOR_Decode),
	0xf9:('gsDPSetBlendColor',G_COLOR_Decode),
	0xfa:('gsDPSetPrimColor',G_SETPRIMCOLOR_Decode),
	0xfb:('gsDPSetEnvColor',G_COLOR_Decode),
	0xfc:('gsDPSetCombineLERP',G_SETCOMBINE_Decode),
	0xfd:('gsDPSetTextureImage',G_SETTIMG_Decode),
	0xfe:('gsDPSetDepthImage',G_SETZIMG_Decode),
	0xff:('gsDPSetColorImage',G_SETCIMG_Decode)
}
