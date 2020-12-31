from ..oot_collision import *

def ootCollisionVertexToC(vertex):
	return "{ " + str(vertex.position[0]) + ", " +\
		str(vertex.position[1]) + ", " +\
		str(vertex.position[2]) + " },\n"

def ootCollisionPolygonToC(polygon, ignoreCamera, ignoreActor, ignoreProjectile, enableConveyor, polygonTypeIndex):
	return "{ " + format(polygonTypeIndex, "#06x") + ', ' +\
		format(polygon.convertShort02(ignoreCamera, ignoreActor, ignoreProjectile), "#06x") + ', ' +\
		format(polygon.convertShort04(enableConveyor), "#06x") + ', ' +\
		format(polygon.convertShort06(), "#06x") + ', ' +\
		format(polygon.normal[0], "#06x") + ', ' +\
		format(polygon.normal[1], "#06x") + ', ' +\
		format(polygon.normal[2], "#06x") + ', ' +\
		format(polygon.distance, "#06x") + ' },\n'

def ootPolygonTypeToC(polygonType):
	return " " + format(polygonType.convertHigh(), "#010x") + ', ' +\
		format(polygonType.convertLow(), "#010x") + ',\n'

def ootWaterBoxToC(waterBox):
	return "{ " + str(waterBox.low[0]) + ", " +\
		str(waterBox.height) + ", " +\
		str(waterBox.low[1]) + ", " +\
		str(waterBox.high[0] - waterBox.low[0]) + ", " +\
		str(waterBox.high[1] - waterBox.low[1]) + ", " +\
		format(waterBox.propertyData(), "#010x") + ' },\n'

def ootCameraDataToC(camData):
	data = "CamPosData " + camData.camPositionsName() + '[] =\n{\n'
	for i in range(len(camData.camPosDict)):
		data += '\t' + ootCameraPosToC(camData.camPosDict[i])
	data += '};\n'

	camDataC = "CamData " + camData.camDataName() + " = { " +\
		str(camData.camSType) + ', ' +\
		str(len(camData.camPosDict)) + ', ' +\
		"(u32) " + camData.camPositionsName() + ' };\n'

	return data + '\n' + camDataC

def ootCameraPosToC(camPos):
	return "{ " +\
		str(camPos.position[0]) + ', ' +\
		str(camPos.position[1]) + ', ' +\
		str(camPos.position[2]) + ', ' +\
		str(camPos.rotation[0]) + ', ' +\
		str(camPos.rotation[1]) + ', ' +\
		str(camPos.rotation[2]) + ', ' +\
		str(camPos.fov) + ', ' +\
		str(camPos.jfifID) + ', ' +\
		format(camPos.unknown, "#06x") + ' },\n'

# TODO: cam data
def ootCollisionToC(collision):
	data = ''

	data += ootCameraDataToC(collision.cameraData) + '\n'
	
	polygonTypeC = "u32 " + collision.polygonTypesName() + "[] = \n{\n"
	polygonC = "RoomPoly " + collision.polygonsName() + "[] = \n{\n"
	polygonIndex = 0
	for polygonType, polygons in collision.polygonGroups.items():
		polygonTypeC += '\t' + ootPolygonTypeToC(polygonType)
		for polygon in polygons:
			polygonC += '\t' + ootCollisionPolygonToC(polygon, 
				polygonType.ignoreCameraCollision,
				polygonType.ignoreActorCollision,
				polygonType.ignoreProjectileCollision,
				polygonType.enableConveyor,
				polygonIndex)
		polygonIndex += 1
	polygonTypeC += '};\n\n'
	polygonC += '};\n\n'

	data += polygonTypeC + polygonC

	data += "Vec3s " + collision.verticesName() + "[" + str(len(collision.vertices)) + "] = \n{\n"
	for vertex in collision.vertices:
		data += '\t' + ootCollisionVertexToC(vertex)
	data += '};\n\n'

	data += "WaterBoxHeader " + collision.waterBoxesName() + "[] = \n{\n"
	for waterBox in collision.waterBoxes:
		data += '\t' + ootWaterBoxToC(waterBox)
	data += '};\n\n'

	header = "CollisionHeader " + collision.headerName() + ' = { '
	for bound in range(2): # min, max bound
		for field in range(3): # x, y, z
			header += str(collision.bounds[bound][field]) + ', '
	
	header += \
		str(len(collision.vertices)) + ', ' +\
		collision.verticesName() + ', ' +\
		str(collision.polygonCount()) + ", " +\
		collision.polygonsName() + ', ' +\
		collision.polygonTypesName() + ', ' +\
		"&" + collision.camDataName() + ', ' +\
		str(len(collision.waterBoxes)) + ", " +\
		collision.waterBoxesName() + ' };\n'
	
	data += header

	return data

def exportCollisionC(obj, transformMatrix, dirPath, includeSpecials, 
	includeChildren, name, customExport, writeRoomsFile, headerType,
	groupName, levelName):

	dirPath, texDir = getExportDir(customExport, dirPath, headerType, 
		levelName, '', name)

	name = toAlnum(name)
	colDirPath = os.path.join(dirPath, toAlnum(name))

	if not os.path.exists(colDirPath):
		os.mkdir(colDirPath)

	colPath = os.path.join(colDirPath, 'collision.inc.c')

	fileObj = open(colPath, 'w', newline='\n')
	collision = exportCollisionCommon(obj, transformMatrix, includeSpecials,
		includeChildren, name, None)
	fileObj.write(collision.to_c())
	fileObj.close()

	cDefine = collision.to_c_def()
	if writeRoomsFile:
		cDefine += collision.to_c_rooms_def()
		roomsPath = os.path.join(colDirPath, 'rooms.inc.c')
		roomsFile = open(roomsPath, 'w', newline='\n')
		roomsFile.write(collision.to_c_rooms())
		roomsFile.close()

	headerPath = os.path.join(colDirPath, 'collision_header.h')
	cDefFile = open(headerPath, 'w', newline='\n')
	cDefFile.write(cDefine)
	cDefFile.close()

	if not customExport:
		if headerType == 'Actor':
			# Write to group files
			if groupName == '' or groupName is None:
				raise PluginError("Actor header type chosen but group name not provided.")

			groupPathC = os.path.join(dirPath, groupName + ".c")
			groupPathH = os.path.join(dirPath, groupName + ".h")

			writeIfNotFound(groupPathC, '\n#include "' + name + '/collision.inc.c"', '')
			if writeRoomsFile:
				writeIfNotFound(groupPathC, '\n#include "' + name + '/rooms.inc.c"', '')
			else:
				deleteIfFound(groupPathC, '\n#include "' + name + '/rooms.inc.c"')
			writeIfNotFound(groupPathH, '\n#include "' + name + '/collision_header.h"', '\n#endif')
		
		elif headerType == 'Level':
			groupPathC = os.path.join(dirPath, "leveldata.c")
			groupPathH = os.path.join(dirPath, "header.h")

			writeIfNotFound(groupPathC, '\n#include "levels/' + levelName + '/' + name + '/collision.inc.c"', '')
			if writeRoomsFile:
				writeIfNotFound(groupPathC, '\n#include "levels/' + levelName + '/' + name + '/rooms.inc.c"', '')
			else:
				deleteIfFound(groupPathC, '\n#include "levels/' + levelName + '/' + name + '/rooms.inc.c"')
			writeIfNotFound(groupPathH, '\n#include "levels/' + levelName + '/' + name + '/collision_header.h"', '\n#endif')
		
	return cDefine