Observation data sorting and moving programm.

Description

This program code searches for files, in particular of the ".fits/.fit" format, inside the folder directory for subsequent sorting into the required categories. 
The program code is written in the Python programming language, using the following libraries:

Pathlib - a module offers classes representing filesystem paths with semantics appropriate for different operating systems. Path classes are divided between pure paths, which provide purely computational operations without I/O, and concrete paths, which inherit from pure paths but also provide I/O operations;

Astropy - package contains key functionality and common tools needed for performing astronomy and astrophysics with Python;

Shutil - a module offers a number of high-level operations on files and collections of files. In particular, functions are provided which support file copying and removal;

re - a module used to check if a string contains the specified search pattern.

Algorithm of the program

First, we import the required Python libraries or their tools. We specify the names of the calibration files in the array.
Then special functions are specified, within which all the work of the code is carried out. They include:

  -Search and determining whether the ".fits/.fit" file format is scientific or calibration inside the folder directory;
  
  -Identifying files not in the ".fits/.fit" format and moving them to a separate "meta" folder;
  
  -Distribute calibration files into the required folders according to the "dark/flat/bias/lamp" filter type;
  
  -Creating folders in the desired directory and move previously created folders with files into them;

Searching, sorting and creating folders occurs by specifying paths to folders. At the same time, the code will not sort copies of already sorted files and create new folders if they already exist. Along the way, the console will display the files, the path to their location, and the path to the place where they were moved. If any errors occur, they will be indicated in the console.

Python version: 3.11.5
