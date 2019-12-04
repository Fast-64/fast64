import re

# function map.txt is build/us/sm64.us.map, but
# only the text after "Linker script and memory map"
# and before "build/us/src/game/main.o(.data*)"

function_map_path = './function map.txt'
output_map_path = './sm64_function_map.py'

def parse_func_map():
    mapfile = open(function_map_path, 'r')
    outfile = open(output_map_path, 'w')

    outfile.write('func_map = {\n')

    nextLine = mapfile.readline()
    while nextLine != '':
        if nextLine[:17] == ' ' * 16 + '0':
            outfile.write('\t"' + nextLine[26:34] + '" : ')
            searchName = nextLine[34:]
            searchResult = re.search(r'\s*(\S*).*', searchName)
            outfile.write('"' + searchResult.group(1) + '",\n')
        nextLine = mapfile.readline()
    outfile.write("}\n")

    mapfile.close()
    outfile.close()