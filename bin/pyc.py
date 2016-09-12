"""
System executable access to the Python bytecode compiler.

Exposes the ability to designate the output bytecode file so
libconstruct can manage Python bytecode in the same fashion as
other targets.
"""
import sys
import py_compile

def compile_python_bytecode(outfile, infile, optimize=2):
	try:
		return py_compile.compile(
			infile, cfile=outfile, optimize=int(optimize), doraise=True)
	except py_compile.PyCompileError as err:
		exc = err.__context__
		exc.__traceback__ = None
		raise exc # SyntaxError

if __name__ == '__main__':
	compile_python_bytecode(*sys.argv[1:])
	raise SystemExit(0)
