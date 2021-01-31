import os, re
from ...utility import *

def getDmaMgrFileNameEntriesBySceneName(dmaMgrFileNames, sceneName):
	return [entry for entry in dmaMgrFileNames if \
		re.match(sceneName + "\_scene", entry) or re.match(sceneName + "\_room\_(\d)+", entry)]

def readDmaMgrFileNames(exportPath):
	fileData = readFile(os.path.join(exportPath, 'src/boot/z_std_dma.c'))

	matchResult = re.search('sDmaMgrFileNames\s*\[[^\]]*\]\s*=\s*{([^\}]*)\}', fileData, re.DOTALL)
	if matchResult is None:
		raise PluginError("z_std_dma.c does not have sDmaMgrFileNames in it.")
	dmaMgrFileNames = parseDmaMgrFileNames(matchResult.group(1))

	return dmaMgrFileNames, fileData, matchResult.start(0), matchResult.end(0)

def parseDmaMgrFileNames(data):
	dmaMgrFileNames = []
	for match in re.finditer('"([^"]*)",', data):
		name = match.group(1).strip()

		dmaMgrFileNames.append(name)

	return dmaMgrFileNames

def dmaMgrFileNamesToString(dmaMgrFileNames):
	data = ''
	for entry in dmaMgrFileNames:
		data += '\t"' + entry + '",\n'
	return data

def writeDmaMgrFileNames(dmaMgrFileNames, fileData, start, end, exportPath):
	dmaMgrFileNamesData = "sDmaMgrFileNames[" + format(len(dmaMgrFileNames), "#05x") + "] = {\n" +\
		dmaMgrFileNamesToString(dmaMgrFileNames) + '}'
	newFileData = fileData[:start] + dmaMgrFileNamesData + fileData[end:]

	if newFileData != fileData:
		writeFile(os.path.join(exportPath, 'src/boot/z_std_dma.c'), newFileData)

def modifyDmaMgrFileNames(scene, exportInfo):
	exportPath = exportInfo.exportPath
	dmaMgrFileNames, fileData, start, end = readDmaMgrFileNames(exportPath)
	entries = getDmaMgrFileNameEntriesBySceneName(dmaMgrFileNames, scene.name if scene is not None else exportInfo.name)

	if len(entries) > 0:
		firstIndex = dmaMgrFileNames.index(entries[0])
		for entry in entries:
			dmaMgrFileNames.remove(entry)
	else:
		firstIndex = len(dmaMgrFileNames)

	if scene is not None:
		dmaMgrFileNames.insert(firstIndex, scene.name + "_scene")
		firstIndex += 1

		for i in range(len(scene.rooms)):
			dmaMgrFileNames.insert(firstIndex, scene.name + "_room_" + str(i))
			firstIndex += 1

	writeDmaMgrFileNames(dmaMgrFileNames, fileData, start, end, exportPath)