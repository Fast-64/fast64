import os, re
from ...utility import *

def getDmaTableEntryEntriesBySceneName(dmaTableEntries, sceneName):
	return [entry for entry in dmaTableEntries if \
		re.match(sceneName + "\_scene", entry) or re.match(sceneName + "\_room\_(\d)+", entry)]

def readDmaTableEntries(exportPath):
	fileData = readFile(os.path.join(exportPath, 'asm/dmadata.s'))

	matchResult = re.search('glabel\s*gDmaDataTable\s*(.*)\.space\s*0x100', fileData, re.DOTALL)
	if matchResult is None:
		raise PluginError("dmadata.s does not have gDmaDataTable in it.")
	dmaTableEntries = parseDmaTableEntries(matchResult.group(1))

	return dmaTableEntries, fileData, matchResult.start(1), matchResult.end(1)

def parseDmaTableEntries(data):
	dmaTableEntries = []
	for match in re.finditer('DMA_TABLE_ENTRY\s*([^\s]*)', data):
		name = match.group(1).strip()
		dmaTableEntries.append(name)

	return dmaTableEntries

def dmaTableEntriesToString(dmaTableEntries):
	data = ''
	for entry in dmaTableEntries:
		data += 'DMA_TABLE_ENTRY ' + entry + '\n'
	return data

def writeDmaTableEntries(dmaTableEntries, fileData, start, end, exportPath):
	dmaTableEntriesData = dmaTableEntriesToString(dmaTableEntries)
	newFileData = fileData[:start] + dmaTableEntriesData + fileData[end:]

	if newFileData != fileData:
		writeFile(os.path.join(exportPath, 'asm/dmadata.s'), newFileData)

def modifyDmaTableEntries(scene, exportInfo):
	exportPath = exportInfo.exportPath
	dmaTableEntries, fileData, start, end = readDmaTableEntries(exportPath)
	entries = getDmaTableEntryEntriesBySceneName(dmaTableEntries, scene.name if scene is not None else exportInfo.name)

	if len(entries) > 0:
		firstIndex = dmaTableEntries.index(entries[0])
		for entry in entries:
			dmaTableEntries.remove(entry)
	else:
		firstIndex = len(dmaTableEntries)

	if scene is not None:
		dmaTableEntries.insert(firstIndex, scene.name + "_scene")
		firstIndex += 1
		
		for i in range(len(scene.rooms)):
			dmaTableEntries.insert(firstIndex, scene.name + "_room_" + str(i))
			firstIndex += 1

	writeDmaTableEntries(dmaTableEntries, fileData, start, end, exportPath)