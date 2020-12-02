from .sm64_constants import *

F3DOutputCopyList = {
	'prim_color' : "Primitive Color", 
	'env_color' : "Environment Color", 
	'chroma_key_center' : "Chroma Key Center", 
	'chroma_key_scale' : "Chroma Key Scale",
	'lod_fraction' : "LOD Fraction",
	'prim_lod_fraction' : "Primitive LOD Fraction",
	'k4' : "YUV Convert K4",
	'k5' : "YUV Convert K5"}

class F3DMaterialSettings:

	def __eq__(self, other):
		for attr in dir(self):
			if not hasattr(other, attr) or getattr(self, attr) != getattr(other, attr):
				return False
		return True
	
	def __ne__(self, other):
		return not self.__eq__(other)

	def __init__(self):
		self.color_combiner = tuple(S_SHADED_TEX + S_SHADED_TEX)
		self.set_texture0 = True
		self.set_texture1 = True
		self.set_prim = True
		self.set_lights = True
		self.set_env = True
		self.set_blend = False
		self.set_key = True
		self.set_k0_5 = True
		self.set_combiner = True
		self.set_rendermode = False
		self.scale_autoprop = True
		
		self.clip_ratio = 1

		# geometry mode
		self.g_zbuffer = True
		self.g_shade = True
		self.g_cull_front = False
		self.g_cull_back = True
		self.g_fog = False
		self.set_fog = False
		self.g_lighting = True
		self.g_tex_gen = False
		self.g_tex_gen_linear = False
		self.g_shade_smooth = True
		# f3dlx2 only
		self.g_clipping = False

		# upper half mode
		self.g_mdsft_alpha_dither = 'G_AD_NOISE'
		self.g_mdsft_rgb_dither = 'G_CD_MAGICSQ'
		self.g_mdsft_combkey = 'G_CK_NONE'
		self.g_mdsft_textconv = 'G_TC_FILT'
		self.g_mdsft_text_filt = 'G_TF_BILERP'
		self.g_mdsft_textlut = 'G_TT_NONE'
		self.g_mdsft_textlod = 'G_TL_TILE'
		self.g_mdsft_textdetail = 'G_TD_CLAMP'
		self.g_mdsft_textpersp = 'G_TP_PERSP'
		self.g_mdsft_cycletype = 'G_CYC_1CYCLE'
		# v1 only
		self.g_mdsft_color_dither = 'G_CD_ENABLE'
		self.g_mdsft_pipeline = 'G_PM_1PRIMITIVE'

		# lower half mode
		self.g_mdsft_alpha_compare = 'G_AC_NONE'
		self.g_mdsft_zsrcsel = 'G_ZS_PIXEL'

		# cycle independent
		self.aa_en = False
		self.z_cmp = False
		self.z_upd = False
		self.im_rd = False
		self.clr_on_cvg = False
		self.aa_en = False
		self.cvg_dst = 'CVG_DST_CLAMP'
		self.zmode = 'ZMODE_OPA'
		self.cvg_x_alpha = False
		self.alpha_cvg_sel = False
		self.force_bl = False

		# cycle dependent - (P * A + M - B) / (A + B)
		self.rendermode_advanced_enabled = False
		self.rendermode_preset_cycle_1 = 'G_RM_AA_ZB_OPA_SURF'
		self.rendermode_preset_cycle_2 = 'G_RM_AA_ZB_OPA_SURF2'
		self.blend_p1 = 'G_BL_CLR_IN'
		self.blend_p2 = 'G_BL_CLR_IN'
		self.blend_m1 = 'G_BL_CLR_IN'
		self.blend_m2 = 'G_BL_CLR_IN'
		self.blend_a1 = 'G_BL_A_IN'
		self.blend_a2 = 'G_BL_A_IN'
		self.blend_b1 = 'G_BL_1MA'
		self.blend_b2 = 'G_BL_1MA'

		self.prim_color = [1,1,1,1]
		self.env_color = [1,1,1,1]
		self.chroma_key_center = [1,1,1,1]
		self.chroma_key_scale = [1,1,1,1]
		self.lod_fraction = 1
		self.prim_lod_fraction = 1
		self.k4 = 1
		self.k5 = 1

		self.tex0Prop = TexturePropertySettings()
		self.tex1Prop = TexturePropertySettings()

		self.use_global_fog = True
		self.fog_color = None #[0,0,0,1]
		self.fog_position = None #[970,1000]

	def loadFromMaterial(self, material, includeValues):
		if not material.is_f3d:
			print(material.name + ' is not an f3d material.')
			return

		self.color_combiner = (
			material.combiner1.A,
			material.combiner1.B,
			material.combiner1.C,
			material.combiner1.D,
			material.combiner1.A_alpha,
			material.combiner1.B_alpha,
			material.combiner1.C_alpha,
			material.combiner1.D_alpha,
			material.combiner2.A,
			material.combiner2.B,
			material.combiner2.C,
			material.combiner2.D,
			material.combiner2.A_alpha,
			material.combiner2.B_alpha,
			material.combiner2.C_alpha,
			material.combiner2.D_alpha,
		)
		self.set_prim = material.set_prim
		self.set_lights = material.set_lights
		self.set_env = material.set_env
		self.set_blend = material.set_blend
		self.set_key = material.set_key
		self.set_k0_5 = material.set_k0_5
		self.set_combiner = material.set_combiner
		self.set_rendermode = material.rdp_settings.set_rendermode
		self.scale_autoprop = material.scale_autoprop

		self.clip_ratio = material.rdp_settings.clip_ratio

		# geometry mode
		self.g_zbuffer = material.rdp_settings.g_zbuffer
		self.g_shade = material.rdp_settings.g_shade
		self.g_cull_front = material.rdp_settings.g_cull_front
		self.g_cull_back = material.rdp_settings.g_cull_back
		self.g_fog = material.rdp_settings.g_fog
		self.set_fog = material.set_fog
		self.g_lighting = material.rdp_settings.g_lighting
		self.g_tex_gen = material.rdp_settings.g_tex_gen
		self.g_tex_gen_linear = material.rdp_settings.g_tex_gen_linear
		self.g_shade_smooth = material.rdp_settings.g_shade_smooth
		# f3dlx2 only
		self.g_clipping = material.rdp_settings.g_clipping

		# upper half mode
		self.g_mdsft_alpha_dither = material.rdp_settings.g_mdsft_alpha_dither
		self.g_mdsft_rgb_dither = material.rdp_settings.g_mdsft_rgb_dither
		self.g_mdsft_combkey = material.rdp_settings.g_mdsft_combkey
		self.g_mdsft_textconv = material.rdp_settings.g_mdsft_textconv
		self.g_mdsft_text_filt = material.rdp_settings.g_mdsft_text_filt
		self.g_mdsft_textlut = material.rdp_settings.g_mdsft_textlut
		self.g_mdsft_textlod = material.rdp_settings.g_mdsft_textlod
		self.g_mdsft_textdetail = material.rdp_settings.g_mdsft_textdetail
		self.g_mdsft_textpersp = material.rdp_settings.g_mdsft_textpersp
		self.g_mdsft_cycletype = material.rdp_settings.g_mdsft_cycletype
		# v1 only
		self.g_mdsft_color_dither = material.rdp_settings.g_mdsft_color_dither
		self.g_mdsft_pipeline = material.rdp_settings.g_mdsft_pipeline

		# lower half mode
		self.g_mdsft_alpha_compare = material.rdp_settings.g_mdsft_alpha_compare
		self.g_mdsft_zsrcsel = material.rdp_settings.g_mdsft_zsrcsel

		# cycle independent
		self.aa_en = material.rdp_settings.aa_en
		self.z_cmp = material.rdp_settings.z_cmp
		self.z_upd = material.rdp_settings.z_upd
		self.im_rd = material.rdp_settings.im_rd
		self.clr_on_cvg = material.rdp_settings.clr_on_cvg
		self.aa_en = material.rdp_settings.aa_en
		self.cvg_dst = material.rdp_settings.cvg_dst
		self.zmode = material.rdp_settings.zmode
		self.cvg_x_alpha = material.rdp_settings.cvg_x_alpha
		self.alpha_cvg_sel = material.rdp_settings.alpha_cvg_sel
		self.force_bl = material.rdp_settings.force_bl

		# cycle dependent - (P * A + M - B) / (A + B)
		self.rendermode_advanced_enabled = material.rdp_settings.rendermode_advanced_enabled
		self.rendermode_preset_cycle_1 = material.rdp_settings.rendermode_preset_cycle_1
		self.rendermode_preset_cycle_2 = material.rdp_settings.rendermode_preset_cycle_2
		self.blend_p1 = material.rdp_settings.blend_p1
		self.blend_p2 = material.rdp_settings.blend_p2
		self.blend_m1 = material.rdp_settings.blend_m1
		self.blend_m2 = material.rdp_settings.blend_m2
		self.blend_a1 = material.rdp_settings.blend_a1
		self.blend_a2 = material.rdp_settings.blend_a2
		self.blend_b1 = material.rdp_settings.blend_b1
		self.blend_b2 = material.rdp_settings.blend_b2

		if includeValues:
			nodes = material.node_tree.nodes
			for name, item in F3DOutputCopyList.items():
				if material.mat_ver == 3 and item == 'Primitive Color':
					if 'Primitive Color Output' in nodes:
						setattr(self, 'prim_color', nodes['Primitive Color Output'].inputs[0].default_value)
				elif material.mat_ver == 3 and item == 'Environment Color':
					if 'Environment Color Output' in nodes:
						setattr(self, 'env_color', nodes['Environment Color Output'].inputs[0].default_value)
				else:
					if item in nodes:
						setattr(self, name, nodes[item].outputs[0].default_value)
			
			self.tex0Prop.load(material.tex0)
			self.tex1Prop.load(material.tex1)

			self.use_global_fog = material.use_global_fog
			self.fog_color = material.fog_color
			self.fog_position = material.fog_position
			self.default_light_color = material.default_light_color
			self.ambient_light_color = material.ambient_light_color
	
	def applyToMaterial(self, material, includeValues, updateFunc, context):
		if not material.is_f3d:
			print(material.name + ' is not an f3d material.')
			return
		
		material.f3d_update_flag = True
		material.combiner1.A = self.color_combiner[0]
		material.combiner1.B = self.color_combiner[1]
		material.combiner1.C = self.color_combiner[2]
		material.combiner1.D = self.color_combiner[3]
		material.combiner1.A_alpha = self.color_combiner[4]
		material.combiner1.B_alpha = self.color_combiner[5]
		material.combiner1.C_alpha = self.color_combiner[6]
		material.combiner1.D_alpha = self.color_combiner[7]
		material.combiner2.A = self.color_combiner[8]
		material.combiner2.B = self.color_combiner[9]
		material.combiner2.C = self.color_combiner[10]
		material.combiner2.D = self.color_combiner[11]
		material.combiner2.A_alpha = self.color_combiner[12]
		material.combiner2.B_alpha = self.color_combiner[13]
		material.combiner2.C_alpha = self.color_combiner[14]
		material.combiner2.D_alpha = self.color_combiner[15]

		material.set_prim = self.set_prim
		material.set_lights = self.set_lights
		material.set_env = self.set_env
		material.set_blend = self.set_blend
		material.set_key = self.set_key
		material.set_k0_5 = self.set_k0_5
		material.set_combiner = self.set_combiner
		material.rdp_settings.set_rendermode = self.set_rendermode
		material.scale_autoprop = self.scale_autoprop

		material.rdp_settings.clip_ratio = self.clip_ratio

		# geometry mode
		material.rdp_settings.g_zbuffer = self.g_zbuffer
		material.rdp_settings.g_shade = self.g_shade
		material.rdp_settings.g_cull_front = self.g_cull_front
		material.rdp_settings.g_cull_back = self.g_cull_back
		material.rdp_settings.g_fog = self.g_fog
		material.set_fog = self.set_fog
		material.rdp_settings.g_lighting = self.g_lighting
		material.rdp_settings.g_tex_gen = self.g_tex_gen
		material.rdp_settings.g_tex_gen_linear = self.g_tex_gen_linear
		material.rdp_settings.g_shade_smooth = self.g_shade_smooth
		# f3dlx2 only
		material.rdp_settings.g_clipping = self.g_clipping

		# upper half mode
		material.rdp_settings.g_mdsft_alpha_dither = self.g_mdsft_alpha_dither
		material.rdp_settings.g_mdsft_rgb_dither = self.g_mdsft_rgb_dither
		material.rdp_settings.g_mdsft_combkey = self.g_mdsft_combkey
		material.rdp_settings.g_mdsft_textconv = self.g_mdsft_textconv
		material.rdp_settings.g_mdsft_text_filt = self.g_mdsft_text_filt
		material.rdp_settings.g_mdsft_textlut = self.g_mdsft_textlut
		material.rdp_settings.g_mdsft_textlod = self.g_mdsft_textlod
		material.rdp_settings.g_mdsft_textdetail = self.g_mdsft_textdetail
		material.rdp_settings.g_mdsft_textpersp = self.g_mdsft_textpersp
		material.rdp_settings.g_mdsft_cycletype = self.g_mdsft_cycletype
		# v1 only
		material.rdp_settings.g_mdsft_color_dither = self.g_mdsft_color_dither
		material.rdp_settings.g_mdsft_pipeline = self.g_mdsft_pipeline

		# lower half mode
		material.rdp_settings.g_mdsft_alpha_compare = self.g_mdsft_alpha_compare
		material.rdp_settings.g_mdsft_zsrcsel = self.g_mdsft_zsrcsel

		# cycle independent
		if self.set_rendermode:
			material.rdp_settings.rendermode_advanced_enabled = self.rendermode_advanced_enabled
			material.rdp_settings.rendermode_preset_cycle_1 = self.rendermode_preset_cycle_1
			material.rdp_settings.rendermode_preset_cycle_2 = self.rendermode_preset_cycle_2
			material.rdp_settings.aa_en = self.aa_en
			material.rdp_settings.z_cmp = self.z_cmp
			material.rdp_settings.z_upd = self.z_upd
			material.rdp_settings.im_rd = self.im_rd
			material.rdp_settings.clr_on_cvg = self.clr_on_cvg
			material.rdp_settings.aa_en = self.aa_en
			material.rdp_settings.cvg_dst = self.cvg_dst
			material.rdp_settings.zmode = self.zmode
			material.rdp_settings.cvg_x_alpha = self.cvg_x_alpha
			material.rdp_settings.alpha_cvg_sel = self.alpha_cvg_sel
			material.rdp_settings.force_bl = self.force_bl

			# cycle dependent - (P * A + M - B) / (A + B)
			material.rdp_settings.blend_p1 = self.blend_p1
			material.rdp_settings.blend_p2 = self.blend_p2
			material.rdp_settings.blend_m1 = self.blend_m1
			material.rdp_settings.blend_m2 = self.blend_m2
			material.rdp_settings.blend_a1 = self.blend_a1
			material.rdp_settings.blend_a2 = self.blend_a2
			material.rdp_settings.blend_b1 = self.blend_b1
			material.rdp_settings.blend_b2 = self.blend_b2\
		
		if includeValues:
			nodes = material.node_tree.nodes
			for name, item in F3DOutputCopyList.items():
				if material.mat_ver == 3 and item == 'Primitive Color':
					nodes['Primitive Color Output'].inputs[0].default_value = getattr(self, 'prim_color')
				elif material.mat_ver == 3 and item == 'Environment Color':
					nodes['Environment Color Output'].inputs[0].default_value = getattr(self, 'env_color')
				else:
					nodes[item].outputs[0].default_value = getattr(self, name)
				
			
			self.tex0Prop.apply(material.tex0)
			self.tex1Prop.apply(material.tex1)

			material.use_global_fog = self.use_global_fog
			material.fog_color = self.fog_color
			material.fog_position = self.fog_position
			material.default_light_color = self.default_light_color
			material.ambient_light_color = self.ambient_light_color

		updateFunc(material, context)
		material.f3d_update_flag = False

class TexturePropertyFieldSettings:
	def __init__(self):
		self.clamp = False
		self.mirror = False
		self.low = 0
		self.high = 32
		self.mask = 5
		self.shift = 0
	
	def load(self, texField):
		self.clamp = texField.clamp
		self.mirror = texField.mirror
		self.low = texField.low
		self.high = texField.high
		self.mask = texField.mask
		self.shift = texField.shift
	
	def apply(self, texField):
		texField.clamp = self.clamp
		texField.mirror = self.mirror
		texField.low = self.low
		texField.high = self.high
		texField.mask = self.mask
		texField.shift = self.shift

class TexturePropertySettings:
	def __init__(self):
		self.tex = None
		self.tex_format = 'RGBA16'
		self.ci_format = 'RGBA16'
		self.S = TexturePropertyFieldSettings()
		self.T = TexturePropertyFieldSettings()
		self.autoprop = True
		self.tex_set = False

	def load(self, texProp):
		self.tex = texProp.tex
		self.tex_format = texProp.tex_format
		self.ci_format = texProp.ci_format
		self.S.load(texProp.S)
		self.T.load(texProp.T)
		self.autoprop = texProp.autoprop
		self.tex_set = texProp.tex_set
	
	def apply(self, texProp):
		texProp.tex = self.tex
		texProp.tex_format = self.tex_format
		texProp.ci_format = self.ci_format
		self.S.apply(texProp.S)
		self.T.apply(texProp.T)
		texProp.autoprop = self.autoprop
		texProp.tex_set = self.tex_set