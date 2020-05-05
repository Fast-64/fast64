from .utility import *
import os
import re

# This is for writing framework for scroll code.
# Actual scroll code found in f3d_gbi.py (FScrollData)

def readSegmentInfo(baseDir):
	ldPath = os.path.join(baseDir, 'sm64.ld')
	ldFile = open(ldPath, 'r', newline = '\n')
	ldData = ldFile.read()
	ldFile.close()

	segDict = {}
	for matchResult in re.finditer('(?<!#define )STANDARD\_OBJECTS\(' +\
		'(((?!\,).)*)\,\s*(((?!\,).)*)\,\s*(((?!\)).)*)\)', ldData):
		segDict[matchResult.group(1).strip()] = \
			('_' + matchResult.group(1) + "_mio0SegmentRomStart",
			int(matchResult.group(3).strip()[2:4], 16), 
			int(matchResult.group(5).strip()[2:4], 16))

	levelPath = os.path.join(baseDir, 'levels/level_defines.h')
	levelFile = open(levelPath, 'r', newline = '\n')
	levelData = levelFile.read()
	levelFile.close()
	for matchResult in re.finditer('DEFINE\_LEVEL\(\s*' + \
		'(((?!\,).)*)\,\s*' + # internal name
		'(((?!\,).)*)\,\s*' + # level enum
		'(((?!\,).)*)\,\s*' + # course enum
		'(((?!\,).)*)\,\s*' + # folder name
		'(((?!\,).)*)\,\s*' + # texture bin
		'(((?!\,).)*)\,\s*' + # acoustic reach
		'(((?!\,).)*)\,\s*' + # echo level 1
		'(((?!\,).)*)\,\s*' + # echo level 2
		'(((?!\,).)*)\,\s*' + # echo level 3
		'(((?!\,).)*)\,\s*' + # dynamic music table
		'(((?!\)).)*)\)',  # camera table
		levelData):
		segDict[matchResult.group(7).strip()] = \
			('_' + matchResult.group(7) + '_segment_7SegmentRomStart', 7, None)	
	return segDict


def writeSegmentROMTable(baseDir):
	memPath = os.path.join(baseDir, 'src/game/memory.c')
	memFile = open(memPath, 'r', newline = '\n')
	memData = memFile.read()
	memFile.close()

	if 'uintptr_t sSegmentROMTable[32];' not in memData:
		memData = re.sub('(?<!extern )uintptr\_t sSegmentTable\[32\]\;', 
		'\nuintptr_t sSegmentTable[32];\nuintptr_t sSegmentROMTable[32];', memData, re.DOTALL)

		memData = re.sub("set\_segment\_base\_addr\s*\((((?!\)).)*)\)\s*;", 
			r'set_segment_base_addr(\1); sSegmentROMTable[segment] = (uintptr_t) srcStart;', memData, re.DOTALL)
	
		memFile = open( memPath, 'w', newline = '\n')
		memFile.write(memData)
		memFile.close()

	# Add extern definition of segment table
	writeIfNotFound(os.path.join(baseDir, 'src/game/memory.h'), 
		'\nextern uintptr_t sSegmentROMTable[32];', '#endif')


def writeTexScrollBase(baseDir):
	writeSegmentROMTable(baseDir)

	# Create texscroll.inc.h
	texscrollHPath = os.path.join(baseDir, 'src/game/texscroll.h')
	if not os.path.exists(texscrollHPath):
		texscrollHFile = open(texscrollHPath, 'w', newline = '\n')

		texscrollHFile.write(
			'#ifndef TEXSCROLL_H\n' +\
			'#define TEXSCROLL_H\n\n' + \
			'extern void scroll_textures();\n\n' +\
			'#endif\n')

		texscrollHFile.close()
	
	# Create texscroll.inc.c
	texscrollCPath = os.path.join(baseDir, 'src/game/texscroll.c')
	if not os.path.exists(texscrollCPath):
		texscrollCFile = open(texscrollCPath, 'w', newline = '\n')
		scrollData = '#include "types.h"\n' +\
			'#include "include/segment_symbols.h"\n' +\
			'#include "memory.h"\n' +\
			'#include "engine/math_util.h"\n' +\
			'#include "src/engine/behavior_script.h"\n' +\
			'#include "texscroll.h"\n'

		# Write global texture load function here
		# Write material.inc.c
		# Write update_materials

		scrollData += "\n\nvoid scroll_textures() {\n}\n"

		texscrollCFile.write(scrollData)
		texscrollCFile.close()
	
	# Create texscroll folder for groups
	texscrollDirPath = os.path.join(baseDir, 'src/game/texscroll')
	if not os.path.exists(texscrollDirPath):
		os.mkdir(texscrollDirPath)

	# parse level_defines.h
	# create texscroll.inc.c/h in each level folder
		# Don't have to make level scroll function, but should call scroll of groups/common

	levelUpdatePath = os.path.join(baseDir, 'src/game/level_update.c')
	levelUpdateFile = open(levelUpdatePath, 'r', newline = '\n')
	levelUpdateData = levelUpdateFile.read()
	levelUpdateFile.close()
	texscrollInclude = '#include "texscroll.h"'
	if texscrollInclude not in levelUpdateData:
		levelUpdateData = texscrollInclude + '\n' + levelUpdateData
	
		levelUpdateFunction = 'changeLevel = play_mode_normal();'
		callScrollIndex = levelUpdateData.index(levelUpdateFunction) + len(levelUpdateFunction)
		if callScrollIndex != -1:
			levelUpdateData = levelUpdateData[:callScrollIndex] + ' scroll_textures();' +\
				levelUpdateData[callScrollIndex:]
		else:
			raise PluginError("Cannot find play_mode_normal() call in level_update.c.")

	levelUpdateFile = open(levelUpdatePath, 'w', newline='\n')
	levelUpdateFile.write(levelUpdateData)
	levelUpdateFile.close()

def createTexScrollHeadersGroup(exportDir, groupName, dataInclude):
	includeH = 'src/game/texscroll/' + groupName + '_texscroll.inc.h'
	includeC = 'src/game/texscroll/' + groupName + '_texscroll.inc.c'

	# Create base scroll files
	writeTexScrollBase(exportDir)

	# Create group inc.h
	groupPathH = os.path.join(exportDir, includeH)
	if not os.path.exists(groupPathH):
		groupFileH = open(groupPathH, 'w', newline = '\n')
		groupDataH = 'extern void scroll_textures_' + groupName + "();\n"
		groupFileH.write(groupDataH)
		groupFileH.close()
	
	# Create group inc.c
	groupPathC = os.path.join(exportDir, includeC)
	if not os.path.exists(groupPathC):
		groupFileC = open(groupPathC, 'w', newline = '\n')
		groupDataC = dataInclude + '\n'
		groupDataC += 'void scroll_textures_' + groupName + "() {\n}\n"
		groupFileC.write(groupDataC)
		groupFileC.close()

	# Include group inc.h in texscroll.h
	texscrollPathH = os.path.join(exportDir, 'src/game/texscroll.h')
	texscrollFileH = open(texscrollPathH, 'r', newline = '\n')
	texscrollDataH = texscrollFileH.read()
	texscrollFileH.close()

	includeHText = '#include "' + includeH + '"'
	if includeHText not in texscrollDataH:
		scrollIndex = texscrollDataH.index('extern void scroll_textures();')
		if scrollIndex != -1:
			texscrollDataH = texscrollDataH[:scrollIndex] + includeHText + '\n' +\
				texscrollDataH[scrollIndex:]
		else:
			raise PluginError("Texture scroll function not found.")

		texscrollFileH = open(texscrollPathH, 'w', newline = '\n')
		texscrollFileH.write(texscrollDataH)
		texscrollFileH.close()	

	# Include group inc.c in texscroll.c
	includeCText = '#include "' + includeC + '"'
	texscrollPathC = os.path.join(exportDir, 'src/game/texscroll.c')
	texscrollFileC = open(texscrollPathC, 'r', newline = '\n')
	texscrollDataC = texscrollFileC.read()
	texscrollFileC.close()

	if includeCText not in texscrollDataC:
		scrollIndex = texscrollDataC.index('void scroll_textures()')
		if scrollIndex != -1:
			texscrollDataC = texscrollDataC[:scrollIndex] + includeCText + '\n' +\
				texscrollDataC[scrollIndex:]
		else:
			raise PluginError("Texture scroll function not found.")

	# Call group scroll function in scroll_textures()
	groupDict = readSegmentInfo(exportDir)
	segment = groupDict[groupName][1]
	segmentRomStart = groupDict[groupName][0]

	groupFunctionCall = "if(sSegmentROMTable[" + hex(segment) + \
		"] == (uintptr_t)" + segmentRomStart + ") {\n" +\
		'\t\tscroll_textures_' + groupName + "();\n\t}\n"
	
	matchResult = re.search('void\s*scroll\_textures'  +\
		'\s*\(\)\s*\{\s*(.*)\n\}', texscrollDataC, re.DOTALL)
	if matchResult:
		functionCalls = matchResult.group(1)
		
		if groupFunctionCall not in functionCalls:
			functionCalls += '\n\t' + groupFunctionCall

			texscrollDataC = texscrollDataC[:matchResult.start(1)] + functionCalls + \
				texscrollDataC[matchResult.end(1):]
	else:
		raise PluginError("Texture scroll function not found.")

	texscrollFileC = open(texscrollPathC, 'w', newline = '\n')
	texscrollFileC.write(texscrollDataC)
	texscrollFileC.close()	

def writeTexScrollHeadersLevel(exportDir, includeC, includeH, groupName, scrollDefines):
	pass

def writeTexScrollHeadersGroup(exportDir, includeC, includeH, groupName, scrollDefines, dataInclude):

	# Create group scroll files
	createTexScrollHeadersGroup(exportDir, groupName, dataInclude)
	
	# Write to group inc.h
	groupPathH = os.path.join(exportDir, 'src/game/texscroll/' + groupName + '_texscroll.inc.h')
	groupFileH = open(groupPathH, 'r', newline = '\n')
	groupDataH = groupFileH.read()
	groupFileH.close()
	
	if includeH not in groupDataH:
		groupDataH = includeH + '\n' + groupDataH

	groupFileH = open(groupPathH, 'w', newline = '\n')
	groupFileH.write(groupDataH)
	groupFileH.close()

	# Write to group inc.c
	groupPathC = os.path.join(exportDir, 'src/game/texscroll/' + groupName + '_texscroll.inc.c')
	groupFileC = open(groupPathC, 'r', newline = '\n')
	groupDataC = groupFileC.read()
	groupFileC.close()

	includeIndex = groupDataC.index('void scroll_textures_' + groupName + '()')
	if includeIndex != -1:
		if includeC not in groupDataC:
			groupDataC = groupDataC[:includeIndex] + includeC + '\n' + groupDataC[includeIndex:]
	else:
		raise PluginError("Could not find include string index.")
	
	# Call actor scroll functions in group scroll function
	# The last function will be the one that calls all the others
	scrollFunction = scrollDefines.split('extern void ')[-1]
	matchResult = re.search('void\s*scroll\_textures\_' + re.escape(groupName) + \
		'\s*\(\)\s*{\s*' + '(((?!\}).)*)\}', groupDataC, re.DOTALL)
	if matchResult:
		functionCalls = matchResult.group(1)
		if scrollFunction not in functionCalls:
			functionCalls += '\t' + scrollFunction
		groupDataC = groupDataC[:matchResult.start(1)] + functionCalls + \
			groupDataC[matchResult.end(1):]
	else:
		raise PluginError("Texture scroll function not found.")

	groupFileC = open(groupPathC, 'w', newline = '\n')
	groupFileC.write(groupDataC)
	groupFileC.close()


def writeTexScrollFiles(exportDir, assetDir, header, data):
	texscrollCPath = os.path.join(assetDir, 'texscroll.inc.c')
	texscrollHPath = os.path.join(assetDir, 'texscroll.inc.h')

	texscrollCFile = open(texscrollCPath, 'w', newline = '\n')
	texscrollCFile.write(data)
	texscrollCFile.close()

	texscrollHFile = open(texscrollHPath, 'w', newline = '\n')
	texscrollHFile.write(header)
	texscrollHFile.close()