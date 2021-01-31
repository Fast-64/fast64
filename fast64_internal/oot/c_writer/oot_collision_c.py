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
	posC = CData()
	camC = CData()
	if len(camData.camPosDict) > 0:
		
		camDataName = "CamData " + camData.camDataName() + "[" + str(len(camData.camPosDict)) + "]"

		camC.source = camDataName + ' = {\n'
		camC.header = "extern " + camDataName + ';\n'
		
		camPosIndex = 0
		for i in range(len(camData.camPosDict)):
			camC.source += '\t' + ootCameraEntryToC(camData.camPosDict[i], camData, camPosIndex)
			if camData.camPosDict[i].hasPositionData:
				posC.source += ootCameraPosToC(camData.camPosDict[i])
				camPosIndex += 3
		posC.source += '};\n\n'
		camC.source += '};\n\n'

		posDataName = "Vec3s " + camData.camPositionsName() + '[' + str(camPosIndex) + ']'
		posC.header = "extern " + posDataName + ';\n'
		posC.source = posDataName + " = {\n" + posC.source 

	posC.append(camC)
	return posC

def ootCameraPosToC(camPos):
	return "\t{ " +\
		str(camPos.position[0]) + ', ' +\
		str(camPos.position[1]) + ', ' +\
		str(camPos.position[2]) + ' },\n\t{ ' +\
		str(camPos.rotation[0]) + ', ' +\
		str(camPos.rotation[1]) + ', ' +\
		str(camPos.rotation[2]) + ' },\n\t{ ' +\
		str(camPos.fov) + ', ' +\
		str(camPos.jfifID) + ', ' +\
		str(camPos.unknown) + ' },\n'

def ootCameraEntryToC(camPos, camData, camPosIndex):
	return "{ " +\
		str(camPos.camSType) + ', ' +\
		('3' if camPos.hasPositionData else '0') + ', ' +\
		(("&" + camData.camPositionsName()  + '[' + str(camPosIndex) + ']') 
		if camPos.hasPositionData else "0") + ' },\n'

def ootCollisionToC(collision):
	data = CData()

	data.append(ootCameraDataToC(collision.cameraData))
	
	if len(collision.polygonGroups) > 0:
		data.header += "extern u32 " + collision.polygonTypesName() + "[];\n"
		data.header += "extern CollisionPoly " + collision.polygonsName() + "[];\n"
		polygonTypeC = "u32 " + collision.polygonTypesName() + "[] = {\n"
		polygonC = "CollisionPoly " + collision.polygonsName() + "[] = {\n"
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
		polygonTypesName = collision.polygonTypesName()
		polygonsName = collision.polygonsName()
	else:
		polygonTypesName = '0'
		polygonsName = '0'

	if len(collision.vertices) > 0:
		data.header += "extern Vec3s " + collision.verticesName() + "[" + str(len(collision.vertices)) + "];\n"
		data.source += "Vec3s " + collision.verticesName() + "[" + str(len(collision.vertices)) + "] = {\n"
		for vertex in collision.vertices:
			data.source += '\t' + ootCollisionVertexToC(vertex)
		data.source += '};\n\n'
		collisionVerticesName = collision.verticesName()
	else:
		collisionVerticesName = '0'

	if len(collision.waterBoxes) > 0:
		data.header += "extern WaterBox " + collision.waterBoxesName() + "[];\n"
		data.source += "WaterBox " + collision.waterBoxesName() + "[] = {\n"
		for waterBox in collision.waterBoxes:
			data.source += '\t' + ootWaterBoxToC(waterBox)
		data.source += '};\n\n'
		waterBoxesName = collision.waterBoxesName()
	else:
		waterBoxesName = '0'

	if len(collision.cameraData.camPosDict) > 0:
		camDataName = "&" + collision.camDataName()
	else:
		camDataName = '0'

	data.header += "extern CollisionHeader " + collision.headerName() + ';\n'
	data.source += "CollisionHeader " + collision.headerName() + ' = { '
	for bound in range(2): # min, max bound
		for field in range(3): # x, y, z
			data.source += str(collision.bounds[bound][field]) + ', '
	
	data.source += \
		str(len(collision.vertices)) + ', ' +\
		collisionVerticesName + ', ' +\
		str(collision.polygonCount()) + ", " +\
		polygonsName + ', ' +\
		polygonTypesName + ', ' +\
		camDataName + ', ' +\
		str(len(collision.waterBoxes)) + ", " +\
		waterBoxesName + ' };\n\n'

	return data
