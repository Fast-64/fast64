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
						dataList.append(line[(line.find("(") + 1):].rstrip(")\n").replace(" ", "").split(','))
					else: fileHeader += line
				elif not line.startswith("// Added scenes"): debugLine = line
	except: raise PluginError("ERROR: Can't find scene_table.h!")

	# return the parsed data, the header comment and the comment mentionning debug scenes
	return dataList, fileHeader, debugLine

def getSceneIndex():
	'''Returns the index (int) of the chosen scene, returns None if ``Custom`` is chose'''
	i = 0
	sceneID = bpy.context.scene.ootSceneOption

	if sceneID == "Custom": return None
	for elem in ootEnumSceneID:
		if elem[0] == sceneID: return i - 1
		i += 1

	raise PluginError("ERROR: Scene Index not found!")

def getSceneParams(scene, exportInfo):
	'''Returns the parameters that needs to be set in ``DEFINE_SCENE()``'''
	sceneIndex = getSceneIndex()
	sceneName = sceneTitle = sceneID = sceneUnk10 = sceneUnk12 = None

	# if the index is None then this is a custom scene
	if sceneIndex == None:
		sceneName = scene.name.lower() + "_scene"
		sceneTitle = "none"
		sceneID = "SCENE_" + (scene.name.upper() if scene is not None else exportInfo.name.upper())
		sceneUnk10 = sceneUnk12 = 0

	return sceneName, sceneTitle, sceneID, sceneUnk10, sceneUnk12, sceneIndex

def sceneTableToC(data, header, debugLine):
	'''Converts the Scene Table to C code'''
	# start the data with the header comment explaining the format of the file
	fileData = header

	# add the actual lines with the same formatting
	for i in range(len(data)):
		fileData += f"/* 0x{i:02X} */ DEFINE_SCENE("

		for j in range(len(data[i])):
			fileData += f"{data[i][j]}"
			if j < 5: fileData += ", "

		fileData += ")\n"
		# adds the "// Debug-only scenes" comment after SCENE_GANON_TOU
		if i == 0x64: fileData += debugLine
		if i == 0x6D and len(data) > 0x6E: fileData += "// Added scenes\n"

	# return the string containing the file data to write
	return fileData

def modifySceneTable(scene, exportInfo):
	'''Edit the scene table with the new data'''
	exportPath = exportInfo.exportPath
	fileData, header, debugLine = getSceneTable(exportPath)
	sceneName, sceneTitle, sceneID, sceneUnk10, sceneUnk12, sceneIndex = getSceneParams(scene, exportInfo)
	sceneParams = [sceneName, sceneTitle, sceneID, scene.sceneTableEntry.drawConfig, sceneUnk10, sceneUnk12]
	
	# check if it's a custom scene name
	if sceneIndex == None: isCustom = True
	else: isCustom = False

	# if so, check if the custom scene already exists in the data
	# if it already exist set isCustom to false to consider it like a normal scene
	if isCustom:
		for i in range(len(fileData)):
			if fileData[i][0] == scene.name.lower() + "_scene":
				sceneIndex = i
				isCustom = False
				break

	# edit the current data or append new one if we are in a ``Custom`` context
	for i in range(6):
		if isCustom == False and sceneParams[i] != None and fileData[sceneIndex][i] != sceneParams[i]:
			fileData[sceneIndex][i] = sceneParams[i]
		elif isCustom:
			fileData.append(sceneParams)
			break

	# remove the scene data if scene is None (`Remove Scene` button)
	if scene == None: fileData.remove(sceneIndex)

	# write the file with the final data
	writeFile(os.path.join(exportPath, 'include/tables/scene_table.h'), sceneTableToC(fileData, header, debugLine))
