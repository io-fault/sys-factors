import tempfile
from .. import libprobe

def test_Context(test):
	result = "#define foo\n"
	result += "#define bar 1\n"
	result += "#define foobar \"string!\"\n"
	result += "#include <header.h>\n"

	with tempfile.NamedTemporaryFile(mode='w') as tf:
		context = libprobe.Context(tf.name)
		with context:
			context.define(foo = None)
			context.define(bar = 1)
			context.define(foobar = '"string!"')
			context.include('header.h')

			context.add_library_directory('/foo')
			context.add_include_directory('/foo-includes')
			context.dynamic_link('footools')
			test/context.stack.compile['directories'] == ()
			test/context.stack.link['directories'] == ()
			test/context.stack.link['libraries'] == ()

			# not flushed
			with open(tf.name) as f:
				test/f.read() == ""
			context.commit()
			test/context.stack.compile['directories'] == ('/foo-includes',)
			test/context.stack.link['directories'] == ('/foo',)
			test/context.stack.link['libraries'] == ('footools',)

			with open(tf.name) as f:
				test/f.read() == result

		# context header file should persist
		with open(tf.name) as f:
			test/f.read() == result

def test_Report(test):
	r = libprobe.Report()
	r.update([
		('foo', 'bar', 1)
	])
	test/r.get('foo', 'bar') == 1
	test/r.get('foo', 'meh', 'bleh') == None

def test_Probe(test):
	'requires a c compiler'
	p = libprobe.Probe(
		stdio = libprobe.Sensor(
			['stdio.h', 'NOSUCHHEADER__x1_'],
		),
	)
	report = p.deploy()
	test/'NOSUCHHEADER__x1_' >> report.get('headers','absent')
	test/'stdio.h' >> report.get('headers','present')
	test/len(report.get('headers','absent')) == 1
	test/len(report.get('headers','present')) == 1

if __name__ == '__main__':
	import sys; from ...development import libtest
	libtest.execute(sys.modules['__main__'])
