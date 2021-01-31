import os, re
from ...utility import *

def getSceneIDEntriesBySceneName(sceneIDs, sceneName):
	return [entry for entry in sceneIDs if \
		entry.name[6:] == sceneName.upper()]

def readSceneIDs(exportPath):
	fileData = readFile(os.path.join(exportPath, 'include/z64scene.h'))

	matchResult = re.search('typedef\s*enum\s*\{([^\}]*)\}\s*SceneID\s*;', fileData, re.DOTALL)
	if matchResult is None:
		raise PluginError("z64scene.h does not have the SceneID enum in it.")
	sceneIDs = parseSceneIDs(matchResult.group(1))

	return sceneIDs, fileData, matchResult.start(1), matchResult.end(1)

def parseSceneIDs(data):
	sceneIDs = []
	for match in re.finditer('([^\s\/]*)\s*,', data):
		name = match.group(1).strip()
		if name != "SCENE_ID_MAX":
			sceneIDs.append(name)

	return sceneIDs

def sceneIDsToString(sceneIDs):
	data = '\n'
	index = 0
	for entry in sceneIDs:
		data += "\t/* " + format(index, '#04x') + " */ " + entry + ',\n'
		index += 1

	data += "\t/* " + format(index, '#04x') + " */ SCENE_ID_MAX\n"
	return data

def writeSceneIDs(sceneIDs, fileData, start, end, exportPath):
	sceneIDsData = sceneIDsToString(sceneIDs)
	newFileData = fileData[:start] + sceneIDsData + fileData[end:]

	if newFileData != fileData:
		writeFile(os.path.join(exportPath, 'include/z64scene.h'), newFileData)

def modifySceneIDs(scene, exportInfo):
	exportPath = exportInfo.exportPath
	sceneID = 'SCENE_' + (scene.name.upper() if scene is not None else exportInfo.name.upper())
	sceneIDs, fileData, start, end = readSceneIDs(exportPath)

	if scene is not None:
		if sceneID not in sceneIDs:
			sceneIDs.append(sceneID)
	else:
		if sceneID in sceneIDs:
			sceneIDs.remove(sceneID)

	writeSceneIDs(sceneIDs, fileData, start, end, exportPath)