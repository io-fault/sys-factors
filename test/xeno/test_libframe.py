from .. import libframe
import itertools

# a bit overkill, yes.
def test_compile_frames(test):
	data = {
		'directories': ['foo'],
		'includes': ['bar.h'],
		'defines': [('foo', 'bar')]
	}
	paramsets = list(itertools.combinations(data.keys(), r = 2))
	paramsets.append(tuple(data.keys()))
	paramsets.append(())

	for x in paramsets:
		rec = libframe.Compile(**{k: data[k] for k in x})
		for y in x:
			test/getattr(rec,y) == tuple(data[y])

def test_link_frames(test):
	data = {
		'directories': ['/foo/lib'],
		'libraries': ['lib'],
		'objects': ['link_object_file'],
		'frameworks': ['CoreFoundation'],
	}
	paramsets = list(itertools.combinations(data.keys(), r = 2))
	paramsets.append(tuple(data.keys()))
	paramsets.append(())

	for x in paramsets:
		rec = libframe.Link(**{k: data[k] for k in x})
		for y in x:
			test/getattr(rec,y) == tuple(data[y])

def test_stack(test):
	c = libframe.Compile(directories = ('foo',))
	l = libframe.Link(directories = ('lib',), frameworks = ('CoreFoundation',))
	i = libframe.Independent(framework_directories = ('framework',))
	s = libframe.Stack()
	s.push('l1', c, l)
	s.push('l2', c, l, i)

	# validate that it's flattening the items
	test/s.compile['directories'] == ('foo',)
	test/s.link['directories'] == ('lib',)
	test/s.compile['framework_directories'] == ('framework',)
	test/s.link['framework_directories'] == ('framework',)
	test/s.link['frameworks'] == ('CoreFoundation',)

if __name__ == '__main__':
	import sys; from ...development import libtest
	libtest.execute(sys.modules['__main__'])
