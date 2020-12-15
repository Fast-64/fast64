from ..utility import *

class BoxEmpty:
	def __init__(self, position, scale, emptyScale):
		# The scale ordering is due to the fact that scaling happens AFTER rotation.
		# Thus the translation uses Y-up, while the scale uses Z-up.
		self.low = (position[0] - scale[0] * emptyScale, position[2] - scale[1] * emptyScale)
		self.high = (position[0] + scale[0] * emptyScale, position[2] + scale[1] * emptyScale)
		self.height = position[1] + scale[2] * emptyScale

def drawCollectionProperty(layout, index, addOp, removeOp, moveOp):
	buttons = layout.row(align = True)
	buttons.operator(removeOp, text = 'Remove Option').option = index
	buttons.operator(addOp, text = 'Add Option').option = index + 1

	moveButtons = layout.row(align = True)
	moveUp = moveButtons.operator(moveOp, text = 'Move Up')
	moveUp.option = index
	moveUp.offset = -1
	moveDown = moveButtons.operator(moveOp, text = 'Move Down')
	moveDown.option = index
	moveDown.offset = 1

def drawEnumWithCustom(panel, data, attribute, name, customName):
	prop_split(panel, data, attribute, name)
	if getattr(data, attribute) == "Custom":
		prop_split(panel, data, attribute + "Custom", customName)

def clampShort(value):
	return min(max(round(value), -2**15), 2**15 - 1)

def convertNormalizedFloatToShort(value):
	value *= 2**15
	value = clampShort(value)
	
	return int(value.to_bytes(2, 'big', signed = True))

def convertNormalizedVectorToShort(value):
	return (
		convertNormalizedFloatToShort(value[0]),
		convertNormalizedFloatToShort(value[1]),
		convertNormalizedFloatToShort(value[2]),
	)
