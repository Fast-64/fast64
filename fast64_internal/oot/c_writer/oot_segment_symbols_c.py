import os, re
from ...utility import *

class SegmentSymbolEntry():
	def __init__(self, segmentType, name):
		self.segmentType = segmentType
		self.name = name

	def toC(self):
		return self.segmentType + "(" + self.name + ")\n"

def getSegmentSymbolEntriesBySceneName(segmentSymbols, sceneName):
	return [entry for entry in segmentSymbols if \
		re.match(sceneName + "\_scene", entry.name) or re.match(sceneName + "\_room\_(\d)+", entry.name)]

def readSegmentSymbols(exportPath):
	fileData = readFile(os.path.join(exportPath, 'include/segment_symbols.h'))

	matchResult = re.search('(DECLARE_SEGMENT\s*\(\s*boot\s*\).*)\#endif', fileData, re.DOTALL)
	if matchResult is None:
		raise PluginError("segment_symbols.h does not have DECLARE_SEGMENT(boot) in it.")
	segmentSymbols = parseSegmentSymbols(matchResult.group(1))

	return segmentSymbols, fileData, matchResult.start(1), matchResult.end(1)

def parseSegmentSymbols(data):
	segmentSymbols = []
	for match in re.finditer('([^\(]*)\(([^\s]*)\)', data):
		segmentType = match.group(1).strip()
		name = match.group(2).strip()

		segmentSymbols.append(SegmentSymbolEntry(segmentType, name))

	return segmentSymbols

def segmentSymbolsToString(segmentSymbols):
	data = ''
	for entry in segmentSymbols:
		data += entry.toC()
	return data

def writeSegmentSymbols(segmentSymbols, fileData, start, end, exportPath):
	segmentSymbolsData = segmentSymbolsToString(segmentSymbols) + "\n"
	newFileData = fileData[:start] + segmentSymbolsData + fileData[end:]

	if newFileData != fileData:
		writeFile(os.path.join(exportPath, 'include/segment_symbols.h'), newFileData)

def modifySegmentSymbols(scene, exportInfo):
	exportPath = exportInfo.exportPath
	segmentSymbols, fileData, start, end = readSegmentSymbols(exportPath)
	entries = getSegmentSymbolEntriesBySceneName(segmentSymbols, scene.name if scene is not None else exportInfo.name)

	if len(entries) > 0:
		firstIndex = segmentSymbols.index(entries[0])
		for entry in entries:
			segmentSymbols.remove(entry)
	else:
		firstIndex = len(segmentSymbols)

	if scene is not None:
		segmentSymbols.insert(firstIndex, SegmentSymbolEntry("DECLARE_ROM_SEGMENT", scene.name + "_scene"))
		firstIndex += 1

	writeSegmentSymbols(segmentSymbols, fileData, start, end, exportPath)