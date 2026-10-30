2009/09/12  Eric Firing

This repository contains a modified version of the code
from Geomag61_unix.tar.gz.  The only modification affecting the
actual calculation is the change from single to double precision;
this causes some very small differences in output.  The other
modifications are to modernize and modularize the code (which
has been done only partially so far), and to generate a
command, magdec, that produces only a single easy-to-parse
line of output.  Magdec takes full advantage of what modernization
has been done; the geomag command still uses the original
file-reading code, apart from one bugfix to prevent memory
corruption and permit compilation with modern versions of
gcc.

In addition, I added a minimal Makefile for use on Linux
systems.  If compilation on Windows is needed, then I will
probably add scons build scripts rather than trying to make
the Makefile handle Windows.

A cython interface may also be added.

================ Changes (see also the hg log) =====================

2010/03/04 EF
Modified for new Geomagnetic model, IGRF11.  The file
format was changed, so geomag and magdec no longer worked with the
older models.  This is not a problem, because the IGRF11 file includes
models for times past.  There were two basic file changes: the order
of the first two fields (indices) was reversed, and the fields
were spaced out to allow easier parsing.  The lines are still
80-characters (without the endings), and we are still using this
fact in the parsing.  Now, however, the file is compiled in, so it
no longer needs to be specified on the command line.

Rather than update the file parsing in geomag61.c, I deleted it,
so now only magdec is provided.

2010/08/20 EF
Added a Makefile.mingw32cross, so that with the ubuntu mingw32 cross
compiler packages installed, one can generate magdec.exe via:

make -f Makefile.mingw32cross

This will leave magdec.exe in the current directory.


=============== Original README.txt below this line ===================

This zip file contains the C source code for the NGDC software "Geomag"
version 6.1 that computes the estimated main magnetic field values for
given locations and dates (or ranges of dates).  Geomag requires a
magnetic field model file for input.  Two models are included in this
zip: IGRF10 and WMM2005. Use the '.cof' extensions on Windows systems
and the '.unx' extensions on Unix systems, since text files differ in
format between the two platforms. The zip and tar files also include
compiled versions (executables) of Geomag for Windows and Linux.


Background
----------
The IGRF10 is the tenth generation standard main field model adopted
by the International Association of Geomagnetism and Aeronomy (IAGA).
This is a degree and order 13 model for 2005-2010 with models for 1900
forward enabling estimation of the main field for dates between
January 1, 1900 and January 1, 2010. For more information on the IGRF
and IAGA, visit the IAGA Working Group V-MOD Web site at:
        http://www.ngdc.noaa.gov/IAGA/vmod/

The WMM is the standard model for the U.S. and U.K. Departments of Defense
and for NATO.  This is a degree and order 12 main field model for 2005.0
and degree and order 12 (computed to 8) secular variation model for 2005 -
2010. For more information on the WMM or to download the Technical Report,
visit the WMM Web site at:
        http://www.ngdc.noaa.gov/seg/WMM/


The computed magnetic elements are:
-----------------------------------
D: Declination
I: Inclination
H: Horizontal field strength
X: North component
Y: East component
Z: Down component
F: Total field strength
dD,dI,dH,dX,dY,dZ,dF: Change per year of the above quantities.


To compile this code on unix systems:
------------------------------------
for the Gnu C compiler:
1) uncomment '#include <math.h>'
2) gcc -lm geomag61.c -o geomag61.exe

For Intel:
1) uncomment '#include <mathimf.h>'
2) icc -wd1572 -static geomag61.c -o geomag61.exe


To compile this code on Windows systems:
----------------------------------------
The DOS executable in this distribution was produced with
Microsoft VisualStudio 2003 .NET, substituting its C++ compiler
with the Intel C++ compiler. Generate an empty WIN32 console
project, copy geomag61.c into the source directory,
convert the project to Intel C++, and build it.


Command line option:
--------------------
Note that the geomag program can receive parameters on
the command line. For example:
geomag61.exe IGRF10.unx 2010.32 D M133.4 10.5 10.5

The command line syntax is listed by providing the h option as
geomag61.exe h


Spread-sheet option:
--------------------
New in revision 61 is that the program can read a file of
dates and locations and create a new file with a set of extra
columns giving the magnetic components. These can then be
read as columns into a spread sheet program. The dates and
coordinates have to be given in the same format as for the
command line option. See also the sample files discussed below.

For example:
geomag61.exe IGRF10.unx f in-coords.txt output.txt
will append the magnetic components and their secualar
variation to the dates and locations given in 'in-coords.txt'
and write the result to a file 'output.txt'.

This distribution contains example files which were produced
on a Linux system using the commands:
geomag61.exe IGRF10.unx f sample_coords.txt sample_out_IGRF10.txt
geomag61.exe WMM2005.unx f sample_coords.txt sample_out_WMM2005.txt
The same result can be achieved on a Windows system by
substituting 'IGRF10.unx' with 'IGRF10.cof' and same for WMM2005.


To run the program with command line arguments under Windows:
-------------------------------------------------------------
1) Click on <Start> <Programs> <Accessories> <Command Prompt>
2) Change directory ('cd') to the folder containg geomag61.exe
3) Run the program, e.g. 'geomag61.exe IGRF10.cof f in.txt out.txt'
4) Use the '.cof' model files for Windows, while the '.unx' model
   files should work for Linux.


Contact:
--------
For further infos, or bug reports, please contact:
stefan.maus@noaa.gov
