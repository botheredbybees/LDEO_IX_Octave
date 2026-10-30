#!/usr/bin/env python

"""
Quick script to generate an include file from a model coefficient file,
so we can include the current set of models in the compiled program.
"""

lines = open("IGRF11.COF").readlines()
outfile = open("igrf11.h", "w")

outfile.write("char *model_lines[] = {\n")

for line in lines:
    line = line.rstrip()
    outfile.write('"%s",\n' % (line,))

outfile.write('""};\n')  # empty line as a terminator

outfile.close()

