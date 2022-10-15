import os, re, bpy
from ...utility import readFile, writeFile
from ..oot_utility import getSceneDirFromLevelName, indent

def getSegmentDefinitionEntryBySceneName(segmentDefinition, sceneName):
	entries = []
	for entry in segmentDefinition:
		matchText = "\s*name\s*\"" + sceneName + "\_"
		if re.match(matchText + "scene\"", entry) or re.match(matchText + "room\_\d+\"", entry):
			entries.append(entry)
	return entries

def readSegmentDefinition(exportPath):
	fileData = readFile(os.path.join(exportPath, 'spec'))
	segmentDefinition, compressFlag = parseSegmentDefinitionData(fileData)

	return segmentDefinition, fileData, compressFlag

def parseSegmentDefinitionData(data):
	table = []
	compressFlag = ""
	for match in re.finditer('beginseg(((?!endseg).)*)endseg', data, re.DOTALL):
		segData = match.group(1)
		table.append(segData)

		# avoid deleting compress flag if the user is using it
		# (defined by whether it is present at least once in spec or not)
		if "compress" in segData:
			compressFlag = indent + "compress\n"

	return table, compressFlag

def segmentDefinitionToString(segmentDefinitions):
	data = '/*\n * ROM spec file\n */\n\n'
	for entry in segmentDefinitions:
		data += "beginseg" + entry + "endseg\n\n"

	# return the data and remove the extra ``\n`` at the end of the file
	return data[:-1]

def writeSegmentDefinition(segmentDefinition, fileData, exportPath):
	newFileData = segmentDefinitionToString(segmentDefinition)

	if newFileData != fileData:
		writeFile(os.path.join(exportPath, 'spec'), newFileData)

def modifySegmentDefinition(scene, exportInfo, levelC):
	exportPath = exportInfo.exportPath
	segmentDefinitions, fileData, compressFlag = readSegmentDefinition(exportPath)
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
		if bpy.context.scene.ootSceneSingleFile:
			segmentDefinitions.insert(firstIndex,
				'\n' + indent + 'name "' + scene.name + '_scene"\n' +\
				compressFlag +\
				indent + "romalign 0x1000\n" +\
				indent + 'include "' + includeDir + '_scene.o"\n' +\
				indent + "number 2\n")
			firstIndex += 1

			for i in range(len(scene.rooms)):
				roomSuffix = "_room_" + str(i)
				segmentDefinitions.insert(firstIndex,
					'\n' + indent + 'name "' + scene.name + roomSuffix + '"\n' +\
					compressFlag +\
					indent + "romalign 0x1000\n" +\
					indent + 'include "' + includeDir + roomSuffix + '.o"\n' +\
					indent + "number 3\n")
				firstIndex += 1
		else:
			sceneSegInclude = '\n' + indent + 'name "' + scene.name + '_scene"\n' +\
				compressFlag +\
				indent + "romalign 0x1000\n" +\
				indent + 'include "' + includeDir + '_scene_main.o"\n' +\
				indent + 'include "' + includeDir + '_scene_col.o"\n'

			if levelC is not None:
				if (levelC.sceneTexturesIsUsed()):
					sceneSegInclude += indent + 'include "' + includeDir + '_scene_tex.o"\n'

				if (levelC.sceneCutscenesIsUsed()):
					for i in range(len(levelC.sceneCutscenesC)):
						sceneSegInclude += indent + 'include "' + includeDir + '_cs_' + str(i) + '.o"\n'

			sceneSegInclude += indent + "number 2\n"

			segmentDefinitions.insert(firstIndex, sceneSegInclude)

			firstIndex += 1

			for i in range(len(scene.rooms)):
				roomSuffix = "_room_" + str(i)
				segmentDefinitions.insert(firstIndex,
					'\n' + indent + 'name "' + scene.name + roomSuffix + '"\n' +\
					compressFlag +\
					indent + "romalign 0x1000\n" +\
					indent + 'include "' + includeDir + roomSuffix + '_main.o"\n' +\
					indent + 'include "' + includeDir + roomSuffix + '_model_info.o"\n' +\
					indent + 'include "' + includeDir + roomSuffix + '_model.o"\n' +\
					indent + "number 3\n")
				firstIndex += 1

	writeSegmentDefinition(segmentDefinitions, fileData, exportPath)
