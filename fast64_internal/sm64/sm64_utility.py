import bpy

def starSelectWarning(operator, fileStatus):
	if fileStatus is not None and not fileStatus.starSelectC:
		operator.report({'WARNING'}, "star_select.c not found, skipping star select scrolling.")

def cameraWarning(operator, fileStatus):
	if fileStatus is not None and not fileStatus.cameraC:
		operator.report({'WARNING'}, "camera.c not found, skipping camera volume and zoom mask exporting.")