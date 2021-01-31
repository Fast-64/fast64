import os, re
from ...utility import *
from ..oot_utility import *

def getSegmentDefinitionEntryBySceneName(segmentDefinition, sceneName):
	entries = []
	for entry in segmentDefinition:
		matchText = "\s*name\s*\"" + sceneName + "\_"
		if re.match(matchText + "scene\"", entry) or re.match(matchText + "room\_\d+\"", entry):
			entries.append(entry)
	return entries

def readSegmentDefinition(exportPath):
	fileData = readFile(os.path.join(exportPath, 'spec'))
	segmentDefinition = parseSegmentDefinitionData(fileData)

	return segmentDefinition, fileData

def parseSegmentDefinitionData(data):
	table = []
	for match in re.finditer('beginseg(((?!endseg).)*)endseg', data, re.DOTALL):
		segData = match.group(1)
		table.append(segData)

	return table

def segmentDefinitionToString(segmentDefinitions):
	data = '/*\n * ROM spec file\n */\n\n'
	for entry in segmentDefinitions:
		data += "beginseg" + entry + "endseg\n\n"
	return data

def writeSegmentDefinition(segmentDefinition, fileData, exportPath):
	newFileData = segmentDefinitionToString(segmentDefinition)

	if newFileData != fileData:
		writeFile(os.path.join(exportPath, 'spec'), newFileData)

def modifySegmentDefinition(scene, exportInfo):
	exportPath = exportInfo.exportPath
	segmentDefinitions, fileData = readSegmentDefinition(exportPath)
	sceneName = scene.name if scene is not None else exportInfo.name
	entries = getSegmentDefinitionEntryBySceneName(segmentDefinitions, sceneName)

	if exportInfo.customSubPath is not None:
		includeDir = 'build/' + exportInfo.customSubPath + sceneName + '/' + sceneName
	else:
		includeDir = 'build/' + getSceneDirFromLevelName(sceneName) + '/' + sceneName

	if len(entries) > 0:
		firstIndex = segmentDefinitions.index(entries[0])
		for entry in entries:
			segmentDefinitions.remove(entry)
	else:
		firstIndex = len(segmentDefinitions)

	if scene is not None:
		segmentDefinitions.insert(firstIndex,
			'\n\tname "' + scene.name + '_scene"\n' +\
			"\tromalign 0x1000\n" +\
			'\tinclude "' + includeDir + '_scene.o"\n' +\
			"\tnumber 2\n")
		firstIndex += 1

		for i in range(len(scene.rooms)):
			roomSuffix = "_room_" + str(i)
			segmentDefinitions.insert(firstIndex, 
				'\n\tname "' + scene.name + roomSuffix + '"\n' +\
				"\tromalign 0x1000\n" +\
				'\tinclude "' + includeDir + roomSuffix + '.o"\n' +\
				"\tnumber 3\n")
			firstIndex += 1

	writeSegmentDefinition(segmentDefinitions, fileData, exportPath)