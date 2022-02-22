import os
from ...utility import *
from ..oot_constants import ootEnumSceneID

def getSceneTable(exportPath):
	'''Read and remove unwanted stuff from ``scene_table.h``'''
	dataList = []
	sceneNames = []
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
				if line.startswith("/* 0x"):
					startIndex = line.find("SCENE_")
					sceneNames.append(line[startIndex : line.find(",", startIndex)])
	except FileNotFoundError:
		raise PluginError("ERROR: Can't find scene_table.h!")

	# return the parsed data, the header comment and the comment mentionning debug scenes
	return dataList, fileHeader, debugLine, sceneNames

def getSceneID(sceneID):
	'''Returns the scene ID depending on if we need a specific scene or not'''
	# makes sure this is a string
	if isinstance(sceneID, str):
		return sceneID
	else:
		return bpy.context.scene.ootSceneOption

def getSceneIndex(sceneNameList, sceneName):
	'''Returns the index (int) of the chosen scene, returns None if ``Custom`` is chosen'''
	sceneID = getSceneID(sceneName)

	if sceneID == "Custom":
		return None

	if sceneNameList is not None:
		for i in range(len(sceneNameList)):
			if sceneNameList[i] == sceneID:
				return i

	# intended return value to check if the chosen scene was removed
	return None

def getOriginalIndex(sceneName):
	'''
		Returns the index of a specific scene defined by which one the user chose
		or by the ``sceneName`` parameter if it's not set to ``None``
	'''
	i = 0

	sceneID = getSceneID(sceneName)

	if sceneID != "Custom":
		for elem in ootEnumSceneID:
			if elem[0] == sceneID:
				# returns i - 1 because the first entry is the ``Custom`` option
				return i - 1
			i += 1

	raise PluginError("ERROR: Scene Index not found!")

def getInsertionIndex(sceneNames, sceneName, index):
	'''Returns the index to know where to insert the scene, intended for "INSERT" mode'''
	# special case where the scene is "Inside the Great Deku Tree"
	# since it's the first scene simply return 0
	if sceneName == "SCENE_YDAN":
		return 0

	# if index is None this means this is looking for ``original_scene_index - 1``
	# else, this means the table is shifted
	if index is None:
		currentIndex = getOriginalIndex(sceneName)
	else:
		currentIndex = index

	for i in range(len(sceneNames)):
		if sceneNames[i] == ootEnumSceneID[currentIndex][0]:
			return i + 1

	# if the index hasn't been found yet, do it again but decrement the index
	return getInsertionIndex(sceneNames, sceneName, currentIndex - 1)

def getSceneParams(scene, exportInfo, sceneNames):
	'''Returns the parameters that needs to be set in ``DEFINE_SCENE()``'''
	# in order to replace the values of ``unk10``, ``unk12`` and basically every parameters from ``DEFINE_SCENE``,
	# you just have to make it return something other than None, not necessarily a string
	sceneIndex = getSceneIndex(sceneNames, None)
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
	fileData, header, debugLine, sceneNames = getSceneTable(exportPath)
	sceneName, sceneTitle, sceneID, sceneUnk10, sceneUnk12, sceneIndex = getSceneParams(scene, exportInfo, sceneNames)

	if scene is None:
		sceneDrawConfig = None
	else:
		sceneDrawConfig = scene.sceneTableEntry.drawConfig

	sceneParams = [sceneName, sceneTitle, sceneID, sceneDrawConfig, sceneUnk10, sceneUnk12]

	# check if it's a custom scene name
	# sceneIndex can be None and ootSceneOption not "Custom",
	# that means the selected scene has been removed from the table
	# however if the scene variable is not None
	# set it to "INSERT" because we need to insert the scene in the right place
	if sceneIndex is None and bpy.context.scene.ootSceneOption == "Custom": 
		mode = "CUSTOM"
	elif sceneIndex is None and scene is not None:
		mode = "INSERT"
	elif sceneIndex is not None:
		mode = "NORMAL"
	else:
		mode = None

	if mode is not None:
		# if so, check if the custom scene already exists in the data
		# if it already exists set mode to NORMAL to consider it like a normal scene
		if mode == "CUSTOM":
			exportName = bpy.context.scene.ootSceneName.lower()
			for i in range(len(fileData)):
				if fileData[i][0] == exportName + "_scene":
					sceneIndex = i
					mode = "NORMAL"
					break
		else:
			exportName = exportInfo.name

		# edit the current data or append new one if we are in a ``Custom`` context
		if mode == "NORMAL":
			for i in range(6):
				if sceneParams[i] is not None and fileData[sceneIndex][i] != sceneParams[i]:
					fileData[sceneIndex][i] = sceneParams[i]
		elif mode == "CUSTOM":
			fileData.append(sceneParams)
			sceneIndex = len(fileData) - 1
		elif mode == "INSERT":
			# if this the user chose a vanilla scene, removed it and want to export
			# insert the data in the normal location
			# shifted index = vanilla index - (vanilla last scene index - new last scene index)
			fileData.insert(getInsertionIndex(sceneNames, sceneID, None), sceneParams)

	# remove the scene data if scene is None (`Remove Scene` button)
	if scene is None:
		if sceneIndex is not None and sceneIndex < len(fileData):
			if (exportName + "_scene") == fileData[sceneIndex][0]:
				fileData.pop(sceneIndex)
			else:
				raise PluginError("ERROR: Scene not found in ``scene_table.h``!")

	# write the file with the final data
	writeFile(os.path.join(exportPath, 'include/tables/scene_table.h'), sceneTableToC(fileData, header, debugLine))
