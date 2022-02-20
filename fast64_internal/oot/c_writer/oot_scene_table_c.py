import os
from ...utility import *
from ..oot_constants import ootEnumSceneID

def getSceneTable(exportPath):
	'''Read and remove unwanted stuff from ``scene_table.h``'''
	dataList = []
	fileHeader = ""
	debugLine = ""

	# read the scene table
	try:
		with open(os.path.join(exportPath, 'include/tables/scene_table.h')) as fileData:
			# keep the relevant data and do some formatting
			for i, line in enumerate(fileData):
				if not line.startswith("// "):
					if not (line.startswith("/**") or line.startswith(" *")):
						dataList.append(
                            line[(line.find("(") + 1) :]
                            .rstrip(")\n")
                            .replace(" ", "")
                            .split(",")
                        )
					else:
						fileHeader += line
				elif not line.startswith("// Added scenes"):
					debugLine = line
	except:
		raise PluginError("ERROR: Can't find scene_table.h!")

	# return the parsed data, the header comment and the comment mentionning debug scenes
	return dataList, fileHeader, debugLine

def getSceneIndex():
	'''Returns the index (int) of the chosen scene, returns None if ``Custom`` is chosen'''
	i = 0
	sceneID = bpy.context.scene.ootSceneOption

	if sceneID == "Custom":
		return None

	for elem in ootEnumSceneID:
		if elem[0] == sceneID:
			return i - 1
		i += 1

	raise PluginError("ERROR: Scene Index not found!")

def getSceneParams(scene, exportInfo):
	'''Returns the parameters that needs to be set in ``DEFINE_SCENE()``'''
	# in order to replace the values of ``unk10``, ``unk12`` and basically every parameters from ``DEFINE_SCENE``,
	# you just have to make it return something other than None, not necessarily a string
	sceneIndex = getSceneIndex()
	sceneName = sceneTitle = sceneID = sceneUnk10 = sceneUnk12 = None

	# if the index is None then this is a custom scene
	if sceneIndex is None and scene is not None:
		sceneName = scene.name.lower() + "_scene"
		sceneTitle = "none"
		sceneID = "SCENE_" + (scene.name.upper() if scene is not None else exportInfo.name.upper())
		sceneUnk10 = sceneUnk12 = 0

	return sceneName, sceneTitle, sceneID, sceneUnk10, sceneUnk12, sceneIndex

def sceneTableToC(data, header, debugLine):
	'''Converts the Scene Table to C code'''
	# start the data with the header comment explaining the format of the file
	fileData = header
	# used to add the "// Added scenes" comment after existing scenes
	isEndOfExistingScenes = False
	# used to add the "// Debug-only scenes" comment after non-debug scenes
	isEndOfNonDebugScenes = False

	# add the actual lines with the same formatting
	for i in range(len(data)):
		# add a comment to show when it's new scenes
		if isEndOfExistingScenes:
			fileData += "// Added scenes\n"
			isEndOfExistingScenes = False
		
		# adds the "// Debug-only scenes" comment after SCENE_GANON_TOU
		if isEndOfNonDebugScenes:
			fileData += debugLine
			isEndOfNonDebugScenes = False

		fileData += f"/* 0x{i:02X} */ DEFINE_SCENE("
		fileData += ", ".join(str(d) for d in data[i])

		if data[i][0] == "testroom_scene":
			isEndOfExistingScenes = True
		if data[i][0] == "ganon_tou_scene":
			isEndOfNonDebugScenes = True

		fileData += ")\n"

	# return the string containing the file data to write
	return fileData

def modifySceneTable(scene, exportInfo):
	'''Edit the scene table with the new data'''
	exportPath = exportInfo.exportPath
	fileData, header, debugLine = getSceneTable(exportPath)
	sceneName, sceneTitle, sceneID, sceneUnk10, sceneUnk12, sceneIndex = getSceneParams(scene, exportInfo)

	if scene is None:
		sceneDrawConfig = None
	else:
		sceneDrawConfig = scene.sceneTableEntry.drawConfig

	sceneParams = [sceneName, sceneTitle, sceneID, sceneDrawConfig, sceneUnk10, sceneUnk12]

	# check if it's a custom scene name
	if sceneIndex is None: 
		isCustom = True
	else:
		isCustom = False

	# if so, check if the custom scene already exists in the data
	# if it already exists set isCustom to False to consider it like a normal scene
	if isCustom:
		for i in range(len(fileData)):
			if fileData[i][0] == scene.name.lower() + "_scene":
				sceneIndex = i
				isCustom = False
				break

	# edit the current data or append new one if we are in a ``Custom`` context
	for i in range(6):
		if isCustom == False and sceneParams[i] is not None and fileData[sceneIndex][i] != sceneParams[i]:
			fileData[sceneIndex][i] = sceneParams[i]
		elif isCustom:
			fileData.append(sceneParams)
			sceneIndex = len(fileData) - 1
			break

	# remove the scene data if scene is None (`Remove Scene` button)
	try:
		if scene is None:
			fileData.remove(fileData[sceneIndex])
	except:
		raise PluginError("ERROR: Scene not found in ``scene_table.h``!")

	# write the file with the final data
	writeFile(os.path.join(exportPath, 'include/tables/scene_table.h'), sceneTableToC(fileData, header, debugLine))
