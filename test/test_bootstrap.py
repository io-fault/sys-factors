from .. import bootstrap as library
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
		rec = library.Compile(**{k: data[k] for k in x})
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
		rec = library.Link(**{k: data[k] for k in x})
		for y in x:
			test/getattr(rec,y) == tuple(data[y])

def test_stack(test):
	c = library.Compile(directories = ('foo',))
	l = library.Link(directories = ('lib',), frameworks = ('CoreFoundation',))
	i = library.Independent(framework_directories = ('framework',))
	s = library.Stack()
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
