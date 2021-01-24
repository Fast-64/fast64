import os
 
# Open a file
path = r"E:\oot\assets\scenes"
 
data = ''

for subdir in os.listdir(path):
	subPath = os.path.join(path, subdir)
	if os.path.isdir(subPath):
		data += 'ootScene' + subdir.capitalize() + ' = [\n'
		for sceneFolder in os.listdir(subPath):
			if os.path.isdir(os.path.join(subPath, sceneFolder)):
				data += '\t"' + sceneFolder.lower() + '",\n' 
		data += ']\n\n'

exportFile = open("sceneDirectoryLists.py", 'w')
exportFile.write(data)
exportFile.close()