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
				else: debugLine = line
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

def getSceneParams(scene, exportInfo, idxMax):
	'''Returns the parameters that needs to be set in ``DEFINE_SCENE()``'''
	sceneIndex = getSceneIndex()
	sceneName = sceneTitle = sceneID = sceneUnk10 = sceneUnk12 = None

	# if the index is None then this is a custom scene
	if sceneIndex == None:
		sceneName = scene.name.lower() + "_scene"
		sceneTitle = "none"
		sceneID = "SCENE_" + (scene.name.upper() if scene is not None else exportInfo.name.upper())
		sceneUnk10 = sceneUnk12 = 0
		sceneIndex = idxMax

	return sceneName, sceneTitle, sceneID, sceneUnk10, sceneUnk12, sceneIndex

def isEntry(data, sceneName):
	for entry in data:
		if entry[0] == sceneName:
			return True
	return False

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
		if i == 100: fileData += debugLine

	# return the string containing the file data to write
	return fileData

def modifySceneTable(scene, exportInfo):
	'''Edit the scene table with the new data'''
	i = 0
	exportPath = exportInfo.exportPath
	fileData, header, debugLine = getSceneTable(exportPath)
	sceneName, sceneTitle, sceneID, sceneUnk10, sceneUnk12, sceneIndex = getSceneParams(scene, exportInfo, len(fileData) + 1)
	sceneParams = [sceneName, sceneTitle, sceneID, scene.sceneTableEntry.drawConfig, sceneUnk10, sceneUnk12]

	if bpy.context.scene.ootSceneOption == "Custom":
		# unfinished
		fileData.append(sceneParams)

	# edit the current data or append new one if we are in a ``Custom`` context
	for i in range(6):
		if sceneIndex < len(fileData) and sceneParams[i] != None and fileData[sceneIndex][i] != sceneParams[i]:
			fileData[sceneIndex][i] = sceneParams[i]

	# remove the scene data if scene is None (`Remove Scene` button)
	if scene == None: fileData.remove(sceneIndex)

	# write the file with the final data
	writeFile(os.path.join(exportPath, 'include/tables/scene_table.h'), sceneTableToC(fileData, header, debugLine))
