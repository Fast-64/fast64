import re

refresh_name = 'Refresh 5'
function_map_path = './sm64.us.map.txt'
output_map_path = './sm64_function_map_output.py'

def parse_func_map():
    mapfile = open(function_map_path, 'r')
    outfile = open(output_map_path, 'w')

    outfile.write('\t"' + refresh_name + '" : {\n')

    nextLine = mapfile.readline()
    while nextLine != '' and nextLine != 'Linker script and memory map\n':
        nextLine = mapfile.readline()
    while nextLine != '' and nextLine != ' build/us/src/game/main.o(.data*)\n':
        if nextLine[:17] == ' ' * 16 + '0':
            outfile.write('\t\t"' + nextLine[26:34] + '" : ')
            searchName = nextLine[34:]
            searchResult = re.search(r'\s*(\S*).*', searchName)
            outfile.write('"' + searchResult.group(1) + '",\n')
        nextLine = mapfile.readline()
    outfile.write("\t}\n")

    mapfile.close()
    outfile.close()