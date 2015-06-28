import functools
from .. import libtest as library

def test_Test_fail(test):
	def test_function(local):
		local.fail("foo")
	t = library.Test(None, test_function)
	t.seal()
	test/t.fate / library.Fail
	test/"foo" == t.fate.content

def test_Test_error(test):
	def t(test):
		raise TypeError("foo")
	t = library.Test(None, t)
	t.seal()
	test/t.fate / library.Fail

def raise_parameter(excvalue):
	raise excvalue

def test_Test_skip(test):
	def f(it):
		it.skip("test")
	t = library.Test(None, f)
	t.seal()
	test/t.fate / library.Skip
	test/"test" == t.fate.content

def test_Contention(test, partial = functools.partial):
	t = library.Test(None, None)
	# protocol
	test/(t/1) / library.Contention
	test/(t/1).test == t
	test/(t/1).object == 1

	test/library.Absurdity ^ partial((t / 1).__ne__, 1)
	test/library.Absurdity ^ partial((t / 1).__eq__, 2)
	test/library.Absurdity ^ partial((t / 2).__lt__, 1)
	test/library.Absurdity ^ partial((t / 1).__gt__, 2)
	test/library.Absurdity ^ partial((t / 1).__ge__, 2)
	test/library.Absurdity ^ partial((t / 3).__le__, 2)
	test/library.Absurdity ^ partial((t / []).__contains__, 2)
	test/library.Absurdity ^ partial((t / 2).__truediv__, str)
	test/library.Absurdity ^ partial((t / int).__sub__, str)

	try:
		with t/ValueError as r:
			raise OSError("foo")
	except library.Absurdity as exc:
		test/exc.__context__ / OSError
		test/r() / OSError
	else:
		test.fail("subject did not catch unexpected")

	try:
		with t/ValueError as r:
			raise ValueError("foo")
		test/r() / ValueError
	except:
		test.fail("exception raised when none was expected")

	try:
		with t/ValueError as r:
			pass
		test.fail("did not raise")
	except library.Absurdity as exc:
		test/r() == None
		pass # passed
	except:
		test.fail("Fail exception was expected")

	class Foo(Exception):
		def __init__(self, x):
			self.data = x

	def raise_Foo():
		raise Foo(1)

	x = t/Exception ^ raise_Foo
	# return was the trapped exception
	t/x.data == 1
	test/library.Absurdity ^ partial((t / Exception).__xor__, (lambda: None))

	# any exceptions are failures
	t/1 != 2
	t/1 == 1
	t/1 >= 1
	t/1 >= 0
	t/1 <= 2
	t/1 <= 1
	1 in (t/[1])
	0 in (t//[1])

	# reverse
	1 != 2/t
	1 == 1/t
	1 >= 1/t
	1 >= 0/t
	1 <= 2/t
	1 <= 1/t

	# perverse
	1/t != 2
	1/t == 1
	1/t >= 1
	1/t >= 0
	1/t <= 2
	1/t <= 1

	class A(object):
		pass
	class B(A):
		pass

	t/B - A
	t/B() / B
	t/B() / A

if __name__ == '__main__':
	import sys; from .. import libtest
	libtest.execute(sys.modules['__main__'])
