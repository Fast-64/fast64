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

def ootCollisionToC(collision):
	data = CData()

	data.source += ootCameraDataToC(collision.cameraData) + '\n'
	
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

	data.source += polygonTypeC + polygonC

	data.source += "Vec3s " + collision.verticesName() + "[" + str(len(collision.vertices)) + "] = \n{\n"
	for vertex in collision.vertices:
		data.source += '\t' + ootCollisionVertexToC(vertex)
	data.source += '};\n\n'

	data.source += "WaterBoxHeader " + collision.waterBoxesName() + "[] = \n{\n"
	for waterBox in collision.waterBoxes:
		data.source += '\t' + ootWaterBoxToC(waterBox)
	data.source += '};\n\n'

	data.header = "extern CollisionHeader " + collision.headerName() + ';\n'
	data.source += "CollisionHeader " + collision.headerName() + ' = { '
	for bound in range(2): # min, max bound
		for field in range(3): # x, y, z
			data.source += str(collision.bounds[bound][field]) + ', '
	
	data.source += \
		str(len(collision.vertices)) + ', ' +\
		collision.verticesName() + ', ' +\
		str(collision.polygonCount()) + ", " +\
		collision.polygonsName() + ', ' +\
		collision.polygonTypesName() + ', ' +\
		"&" + collision.camDataName() + ', ' +\
		str(len(collision.waterBoxes)) + ", " +\
		collision.waterBoxesName() + ' };\n\n'

	return data
