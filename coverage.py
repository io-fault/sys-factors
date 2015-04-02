"""
Tools for generating and extracting coverage data from C coverage tools.
"""
import subprocess
from ..routes import library as routeslib
from . import libmeta

# utility function for running processing commands
def _pipeline(inputfile, seq, popen = subprocess.Popen, pipe = subprocess.PIPE):
	with open(inputfile) as f:
		pipeline = [popen(seq[0], stdin = f, stdout = pipe, stderr = pipe)]
	r = None

	try:
		stdin = pipeline[0].stdout
		pipeline[0].stderr.close()
		for x in seq[1:]:
			p = popen(x, stdin = stdin, stdout = pipe, stderr = pipe)
			pipeline.append(p)
			p.stderr.close()
			stdin = p.stdout
		r = p.stdout.read()
	finally:
		for x in pipeline:
			p.wait()
		return r

# We are processing this file for each test, so let's avoid the overhead
# involved with instantiating Python objects. For smaller files it would be
# okay, but for larger files, it's N passes.
def crossed(filepath,
	sequence = [
		# project
		('grep', '^ *[0-9]\+'),
		('cut', '-s', '-d', ':', '-f' '1,2'),
		# collapse spaces
		('sed', 's/[\t ]*//g'),
	],
):
	"""
	Run the '.gcov' file through a pipeline that renders lines suitable for libmeta
	use.
	"""
	return _pipeline(filepath, sequence)

def crossable(filepath,
	sequence = [
		# project
		('grep', '^[ \t]*[^-]\+:'),
		('cut', '-s', '-d', ':', '-f' '2'),
	],
):
	"""
	lines(filepath)

	:param filepath: Path to the .gcov file.

	Run the coverage output, '.gcov', through a pipeline that renders coverable lines.
	"""
	return _pipeline(filepath, sequence)

def ignored(filepath,
	sequence = [
		('grep', '[ \t]XCOVERAGE$'),
		('cut', '-s', '-d', ':', '-f' '2'),
	],
):
	"""
	Get the lines of the source that were explicitly ignored.
	"""
	return _pipeline(filepath, sequence)

def llvm(data, *sources):
	"""
	:param data: Path prefix of the '.gcno' and '.gcda' files.
	:param sources: The list of sources.

	Return the command tuple for running gcov.
	"""
	return (
		'llvm-cov',
		'--object-file', data
	) + sources

def garbage(data, *sources):
	"""
	:param data: Path prefix of the '.gcno' and '.gcda' files.
	:param sources: The list of sources.

	Return the command tuple for running gcov.
	"""
	return (
		'gcov',
		'--object-file', data
	) + sources

def render(route, proc = crossed):
	"""
	Create the coverage meta data for the module.
	"""
	# get paths
	ir = route
	srcr = ir.file()

	# loader tells us where the dll and associated files are.
	l = ir.module().__bootstrap__
	src = l.path

	cached = routeslib.File.from_absolute(l.cprefix)
	dir = cached.container.fullpath

	with routeslib.File.temporary() as tr:
		# render the coverage output in a temp directory
		filename = srcr.identity
		command = garbage(cached.suffix('.gcno').fullpath, src)
		p = subprocess.Popen(command, cwd = tr.fullpath, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
		p.stdout.close() # yeah if there's a problem... good luck =\
		p.wait()

		# extract and write coverage
		return srcr.fullpath, proc((tr/filename).suffix('.gcov').fullpath)

def record(cause, fullname, metatype = 'xlines', proc = crossed):
	"""
	Update the coverage meta data for the module.
	"""
	coverage = render(routeslib.Import.from_fullname(fullname), proc = proc)
	if coverage:
		path, lines = coverage
		settings = [tuple(map(int, x.split(b':', 1)))[2::-1] for x in lines.split(b'\n') if x]
		libmeta.append(metatype, path, [(cause, settings)])
