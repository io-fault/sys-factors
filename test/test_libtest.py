import functools
from .. import libtest

def test_Test_fail(test):
	def t(test):
		test.fail("foo")
	t = libtest.Test(None, t)
	t.seal()
	test/t.fate / libtest.Fail
	test/"foo" == t.fate.content

def test_Test_error(test):
	def t(test):
		raise TypeError("foo")
	t = libtest.Test(None, t)
	t.seal()
	test/t.fate / libtest.Error

def raise_parameter(excvalue):
	raise excvalue

def test_Test_skip(test):
	def f(it):
		it.skip("test")
	t = libtest.Test(None, f)
	t.seal()
	test/t.fate / libtest.Skip
	test/"test" == t.fate.content

def test_Subject(test, partial = functools.partial):
	t = libtest.Test(None, None)
	# protocol
	test/(t/1) / libtest.Subject
	test/(t/1).test == t
	test/(t/1).object == 1

	test/libtest.Fail ^ partial((t / 1).__ne__, 1)
	test/libtest.Fail ^ partial((t / 1).__eq__, 2)
	test/libtest.Fail ^ partial((t / 2).__lt__, 1)
	test/libtest.Fail ^ partial((t / 1).__gt__, 2)
	test/libtest.Fail ^ partial((t / 1).__ge__, 2)
	test/libtest.Fail ^ partial((t / 3).__le__, 2)
	test/libtest.Fail ^ partial((t / []).__contains__, 2)
	test/libtest.Fail ^ partial((t / 2).__truediv__, str)
	test/libtest.Fail ^ partial((t / int).__sub__, str)

	try:
		with t/ValueError as r:
			raise OSError("foo")
	except libtest.Fail as exc:
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
	except libtest.Fail as exc:
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
	test/libtest.Fail ^ partial((t / Exception).__xor__, (lambda: None))

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
