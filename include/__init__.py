import os.path

directory = os.path.realpath(os.path.dirname(__file__))

xpython		= os.path.join(directory, 'xpython.h')
cpython		= os.path.join(directory, 'cpython.h')
objcpython	= os.path.join(directory, 'objcpython.h')

del os
