import bpy
import math
from mathutils import * 
from bgl import * 
import time
from bpy.utils import register_class, unregister_class

vertexShader = '''
#version 330 core
layout (location = 0) in vec3 pos;
  
out vec3 vertexColor;

void main()
{
	gl_Position = vec4(aPos, 1.0); // see how we directly give a vec3 to vec4's constructor
	vertexColor = vec4(0.5, 0.0, 0.0, 1.0); // set the output variable to a dark-red color
}
'''

fragmentShader = '''
#version 330 core
out vec4 color;
  
in vec4 vertexColor; // the input variable from the vertex shader (same name and same type)  

void main()
{
	color = vertexColor;
} 
'''

class F3DRenderEngine(bpy.types.RenderEngine):

	bl_idname = "f3d_renderer"
	bl_label = "Fast3D"
	use_preview = True

	# Init is called whenever a new render engine instance is created. Multiple
	# instances may exist at the same time, for example for a viewport and final
	# render.
	def __init__(self):
		self.draw_data = F3DDrawData()
		self.first_time = False

	# When the render engine instance is destroy, this is called. Clean up any
	# render engine data here, for example stopping running render threads.
	def __del__(self):
		pass

	# This is the method called by Blender for both final renders (F12) and
	# small preview for materials, world and lights.
	def render(self, depsgraph):
		scene = depsgraph.scene
		scale = scene.render.resolution_percentage / 100.0
		self.size_x = int(scene.render.resolution_x * scale)
		self.size_y = int(scene.render.resolution_y * scale)

		# Fill the render result with a flat color. The framebuffer is
		# defined as a list of pixels, each pixel itself being a list of
		# R,G,B,A values.
		if self.is_preview:
			color = [0.1, 0.2, 0.1, 1.0]
		else:
			color = [0.2, 0.1, 0.1, 1.0]

		pixel_count = self.size_x * self.size_y
		rect = [color] * pixel_count

		# Here we write the pixel values to the RenderResult
		result = self.begin_result(0, 0, self.size_x, self.size_y)
		layer = result.layers[0].passes["Combined"]
		layer.rect = rect
		self.end_result(result)

	# For viewport renders, this method gets called once at the start and
	# whenever the scene or 3D viewport changes. This method is where data
	# should be read from Blender in the same thread. Typically a render
	# thread will be started to do the work while keeping Blender responsive.

	# Not called when viewport camera transform changes.
	def view_update(self, context, depsgraph):
		region = context.region
		view3d = context.space_data
		scene = depsgraph.scene

		# Get viewport dimensions
		dimensions = region.width, region.height

		if not self.first_time:
			# First time initialization
			self.first_time = True
			for datablock in depsgraph.ids:
				if isinstance(datablock, bpy.types.Image):
					self.draw_data.textures[datablock.name] = F3DRendererTexture(datablock)
				elif isinstance(datablock, bpy.types.Material):
					self.draw_data.materials[datablock.name] = F3DRendererMaterial(datablock)
				elif isinstance(datablock, bpy.types.Mesh):
					pass
				elif isinstance(datablock, bpy.types.Object) and isinstance(datablock.data, bpy.types.Mesh):
					self.draw_data.objects[datablock.name] = F3DRendererObject(datablock.data, self.draw_data)
		else:
			# Test which datablocks changed
			for update in depsgraph.updates:
				print("Datablock updated: ", update.id.name)
				#if isinstance(update.id, bpy.types.Scene):
				#	for self.draw_data

			# Test if any material was added, removed or changed.
			if depsgraph.id_type_updated('MATERIAL'):
				print("Materials updated")

		# Loop over all object instances in the scene.
		if self.first_time or depsgraph.id_type_updated('OBJECT'):
			print("Updated object.")
			for instance in depsgraph.object_instances:
				pass

		context.region_data.perspective_matrix

	# For viewport renders, this method is called whenever Blender redraws
	# the 3D viewport. The renderer is expected to quickly draw the render
	# with OpenGL, and not perform other expensive work.
	# Blender will draw overlays for selection and editing on top of the
	# rendered image automatically.
	def view_draw(self, context, depsgraph):
		region = context.region
		scene = depsgraph.scene

		# Get viewport dimensions
		dimensions = region.width, region.height

		glEnable(GL_BLEND)
		glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)
		self.draw_data.draw()
		glDisable(GL_BLEND)

class F3DRendererTexture:
	def __init__(self, image):
		self.image = image
		width, height = image.size

		self.texture_buffer = Buffer(GL_INT, 1)
		image.gl_load()
		self.texture_buffer[0] = image.bindcode

		#glGenTextures(1, self.texture)
		glActiveTexture(GL_TEXTURE0)
		glBindTexture(GL_TEXTURE_2D, self.texture_buffer[0])
		#glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16F, width, height, 0, GL_RGBA, GL_FLOAT, pixels)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
		glBindTexture(GL_TEXTURE_2D, 0)

	def __del__(self):
		glBindTexture(GL_TEXTURE_2D, 0)
		glDeleteTextures(1, self.texture_buffer)
	
	def bind(self):
		glBindTexture(GL_TEXTURE_2D, self.texture_buffer[0])

class F3DRendererMaterial:
	def __init__(self, material):
		self.material = material
	
	def __del__(self):
		pass

	def update(self, viewport, projection, time):
		pass

	def apply(self):
		pass

class F3DRendererObject:
	def __init__(self, mesh, render_data):
		self.submeshes = []
		facesByMat = {}
		for face in mesh.loop_triangles:
			if face.material_index not in facesByMat:
				facesByMat[face.material_index] = []
			facesByMat[face.material_index].append(face)
		
		for material_index, faces in facesByMat.items():
			material = mesh.materials[material_index]
			# Material should always be added in view_update
			f3d_material = render_data.materials[material]

			self.submeshes.append(F3DRendererSubmesh(f3d_material, mesh, faces))

	def draw(self):
		for submesh in self.submeshes:
			submesh.draw()

class F3DRendererSubmesh:
	def __init__(self, f3d_material, mesh, triangles):
		loops = []
		for triangle in triangles:
			for loop in triangle.loops:
				loops.append(loop)

		self.material = f3d_material

		self.vertex_array = Buffer(GL_INT, 1)
		glGenVertexArrays(1, self.vertex_array)
		glBindVertexArray(self.vertex_array[0])

		self.vertex_buffer = Buffer(GL_INT, 3)
		self.size = len(loops)
		
		position = []
		for loop in loops:
			position += mesh.vertices[loop.vertex_index].co
		self.position_buffer = Buffer(GL_FLOAT, len(position), position)
		
		uv = []
		if mesh.uv_layers.active is None:
			uv = [0, 0] * len(loops)
		else:
			for loopUV in mesh.uv_layers.active.data:
				uv += loopUV.uv
		self.uv_buffer = Buffer(GL_FLOAT, len(uv), uv)
		
		colorOrNormal = []
		if True: # TODO: Choose normal or vertex color
			for loop in loops:
				colorOrNormal += loop.normal
		else:
			if 'Col' in mesh.vertex_colors:
				color_data = mesh.vertex_colors['Col'].data
			else:
				color_data = [0,0,0] * len(loops)

			if 'Alpha' in mesh.vertex_colors:
				alpha_data = mesh.vertex_colors['Alpha'].data
			else:
				alpha_data = [0,0,0] * len(loops)
			
			for loop in loops:
				# TODO: Fix Alpha
				colorOrNormal += color_data[loop.index][0:3] + [alpha_data[loop.index][0]]
		self.colorOrNormal_buffer = Buffer(GL_FLOAT, len(colorOrNormal), colorOrNormal)

		position_location = glGetAttribLocation(shader_program[0], "pos")
		uv_location = glGetAttribLocation(shader_program[0], "uv")
		colorOrNormal_location = glGetAttribLocation(shader_program[0], "colorOrNormal")
		
		# Floats and Ints are 4 bytes?
		glBindBuffer(GL_ARRAY_BUFFER, self.vertex_buffer[0])
		glBufferData(GL_ARRAY_BUFFER, len(position) * 3 * 4, position_buffer, GL_STATIC_DRAW)
		glVertexAttribPointer(position_location, 2, GL_FLOAT, GL_FALSE, 0, None)

		glBindBuffer(GL_ARRAY_BUFFER, self.vertex_buffer[1])
		glBufferData(GL_ARRAY_BUFFER, len(uv) * 2 * 4, uv_buffer, GL_STATIC_DRAW)
		glVertexAttribPointer(uv_location, 2, GL_FLOAT, GL_FALSE, 0, None)

		glBindBuffer(GL_ARRAY_BUFFER, self.vertex_buffer[2])
		glBufferData(GL_ARRAY_BUFFER, len(colorOrNormal) * 4 * 4, colorOrNormal_buffer, GL_STATIC_DRAW)
		glVertexAttribPointer(colorOrNormal_location, 2, GL_FLOAT, GL_FALSE, 0, None)

		glBindBuffer(GL_ARRAY_BUFFER, 0)
		glBindVertexArray(0)


	def draw(self):
		#glActiveTexture(GL_TEXTURE0)
		#glBindTexture(GL_TEXTURE_2D, self.texture[0])
		self.material.apply()
		glBindVertexArray(self.vertex_array[0])
		glDrawArrays(GL_TRIANGLES, 0, self.size)
		glBindVertexArray(0)
		glBindTexture(GL_TEXTURE_2D, 0)

	def __del__(self):
		glDeleteBuffers(3, self.vertex_buffer)

		glDeleteBuffers(1, self.position_buffer)
		glDeleteBuffers(1, self.uv_buffer)
		glDeleteBuffers(1, self.colorOrNormal_buffer)

		glDeleteVertexArrays(1, self.vertex_array)
		glBindTexture(GL_TEXTURE_2D, 0)
		#glDeleteTextures(1, self.texture)

class F3DDrawData:
	def __init__(self):
		self.textures = {}
		self.materials = {}
		self.objects = {}

		# Create shader program
		vertexHandle = glCreateShader(GL_VERTEX_SHADER)
		fragmentHandle = glCreateShader(GL_FRAGMENT_SHADER)
		glShaderSource(vertexHandle, vertexShader)
		glShaderSource(vertexHandle, fragmentShader)
		glCompileShader(vertexHandle)
		glCompileShader(fragmentHandle)

		self.shaderProgram = glCreateProgram()
		glAttachShader(self.shaderProgram, vertexHandle)
		glAttachShader(self.shaderProgram, fragmentHandle)
		glLinkProgram(self.shaderProgram)
		glDeleteShader(vertexHandle)
		glDeleteShader(fragmentHandle)

		messageSize = Buffer(GL_INT, 1)
		message = Buffer(GL_BYTE, 1000)
		glGetShaderInfoLog(self.shaderProgram, 1000, messageSize, message)
		print(message[:])

	def __del__(self):
		for idName, f3dObject in self.objects.items():
			del f3dObject

	def draw(self):
		glClearColor(0.2, 0.3, 0.3, 1.0)
		glClear(GL_COLOR_BUFFER_BIT)

		glUseProgram(self.shaderProgram)
		for idName, f3dObject in self.objects.items():
			f3dObject.draw()


# RenderEngines also need to tell UI Panels that they are compatible with.
# We recommend to enable all panels marked as BLENDER_RENDER, and then
# exclude any panels that are replaced by custom panels registered by the
# render engine, or that are not supported.
def get_panels():
	exclude_panels = {
		'VIEWLAYER_PT_filter',
		'VIEWLAYER_PT_layer_passes',
	}

	panels = []
	for panel in bpy.types.Panel.__subclasses__():
		if hasattr(panel, 'COMPAT_ENGINES') and 'BLENDER_RENDER' in panel.COMPAT_ENGINES:
			if panel.__name__ not in exclude_panels:
				panels.append(panel)

	return panels

render_engine_classes = [
	#F3DRenderEngine,
]

def render_engine_register() :
	for cls in render_engine_classes:
		register_class(cls)
	
	for panel in get_panels():
		panel.COMPAT_ENGINES.add('CUSTOM')

	#from bl_ui import (properties_render)
	#properties_render.RENDER_PT_render.COMPAT_ENGINES.add(CustomRenderEngine.bl_idname)

def render_engine_unregister() :
	for cls in render_engine_classes:
		unregister_class(cls)

	for panel in get_panels():
		if 'CUSTOM' in panel.COMPAT_ENGINES:
			panel.COMPAT_ENGINES.remove('CUSTOM')

	#from bl_ui import (properties_render)
	#properties_render.RENDER_PT_render.COMPAT_ENGINES.remove(CustomRenderEngine.bl_idname)