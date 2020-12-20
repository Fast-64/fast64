import re

objFile = open("z64object.h", 'r')
objData = objFile.read()
objFile.close()

class BlenderEnumItem:
	def __init__(self, key, name, description):
		self.key = key
		self.name = name
		self.description = description
	
	def toC(self):
		return '\t("' + self.key + '", "' + self.name + '", "' + self.description + '"),\n'

enumList = [BlenderEnumItem("Custom", "Custom", "Custom")]
ignoreList = [
	'GAMEPLAY_KEEP',
	'GAMEPLAY_DANGEON_KEEP',
	'GAMEPLAY_FIELD_KEEP',
	'LINK_BOY',
	'LINK_CHILD',
]

for matchResult in re.finditer('OBJECT\_(.*),', objData):
	oldName = matchResult.group(1)
	if oldName[:5] == "UNSET" or oldName in ignoreList:
		continue
	spacedName = oldName.replace("_", " ")
	words = spacedName.split(" ")
	capitalizedWords = [word.capitalize() for word in words]
	newName = " ".join(capitalizedWords)
	enumList.append(BlenderEnumItem("OBJECT_" + oldName, newName, newName))

enumData = 'ootEnumObjects = [\n'
for item in enumList:
	enumData += item.toC()
enumData += ']'

enumFile = open("oot_obj_enum.py", 'w')
enumFile.write(enumData)
enumFile.close()