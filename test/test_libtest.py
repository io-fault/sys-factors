##
# .test.test_libtest - libtest tests
##
from .. import libtest

def test_Test_init(test):
	f = lambda x: False
	t = libtest.Test(f)
	test.fail_if_not_exact(None, t.identity)
	test.fail_if_not_exact(f, t.focus)

def test_Test_fail(test):
	def t(test):
		test.fail("foo")
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Fail)
	test.fail_if_not_equal("foo", fate.content)

def test_Test_error(test):
	def t(test):
		raise TypeError("foo")
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Error)

def raise_parameter(excvalue):
	raise excvalue

def test_Test_finr_nothing_raised(test):
	class SomeException(Exception):
		pass
	def t(test):
		def does_not_raise():
			pass
		test.fail_if_not_raised(SomeException, does_not_raise)
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Fail)
	# XXX: check more details

def test_Test_finr_incorrect_exception(test):
	class SomeException(Exception):
		pass
	def raise_wrong_exception(test):
		# also validates that the callable is receiving the following arguments
		test.fail_if_not_raised(SomeException, raise_parameter, ValueError("eek"))
	t = libtest.Test(raise_wrong_exception)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Fail)
	# XXX: check more details

def test_Test_finr_correct_exception(test):
	class SomeException(Exception):
		pass
	def t(test):
		def raise_correct_exception():
			raise SomeException()
		test.fail_if_not_raised(SomeException, raise_correct_exception)
		test.fail_if_not_raised((SomeException,), raise_correct_exception)
		test.fail_if_not_raised((ValueError, SomeException,), raise_correct_exception)
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Pass)
	# XXX: check more details

def test_Test_fir_nothing_raised(test):
	class SomeException(Exception):
		pass
	def t(test):
		def does_not_raise():
			pass
		test.fail_if_raised(SomeException, does_not_raise)
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Pass)
	# XXX: check more details

def test_Test_fir_match_raised(test):
	class SomeException(Exception):
		pass
	def t(test):
		def raises_bad_exception():
			raise SomeException()
		test.fail_if_raised(SomeException, raises_bad_exception)
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Fail)
	# XXX: check more details

def test_Test_fir_raised(test):
	class SomeException(Exception):
		pass
	def t(test):
		def raises_okay_exception():
			raise ValueError(None)
		test.fail_if_raised(SomeException, raises_okay_exception)
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Pass)
	# XXX: check more details

def test_Test_fi_empty(test):
	# test failing
	def t(test):
		test.fail_if_empty(('foo',))
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Pass)
	# test passing
	def t(test):
		test.fail_if_empty(())
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Fail)

def test_Test_fin_empty(test):
	# test failing
	def t(test):
		test.fail_if_not_empty(('foo',))
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Fail)
	# test passing
	def t(test):
		test.fail_if_not_empty(())
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Pass)

def test_Test_skip(test):
	def t(test):
		test.skip("test")
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Skip)
	test.fail_if_not_equal("test", fate.content)

def test_Test_fih(test):
	def t(test):
		test.fail_if_hasattr(test, "fail_if_hasattr")
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Fail)

	o = object()
	def t(test):
		test.fail_if_hasattr(o, "test_if_hasattr")
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Pass)

def test_Test_finh(test):
	def t(test):
		test.fail_if_not_hasattr(test, "fail_if_hasattr")
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Pass)

	o = object()
	def t(test):
		test.fail_if_not_hasattr(o, "test_if_hasattr")
	t = libtest.Test(t)
	fate = libtest.seal(t)
	test.fail_if_not_instance(fate, libtest.Fail)

def test_Subject(test):
	t = libtest.Test(None)
	test.fail_if_not_instance(t / 1, libtest.Subject)
	test.fail_if_not_equal((t / 1).test, t)
	test.fail_if_not_equal((t / 1).object, 1)

	test.fail_if_not_raised(libtest.Fail, (t / 1).__ne__, 1)
	test.fail_if_not_raised(libtest.Fail, (t / 1).__eq__, 2)
	test.fail_if_not_raised(libtest.Fail, (t / 2).__lt__, 1)
	test.fail_if_not_raised(libtest.Fail, (t / 1).__gt__, 2)
	test.fail_if_not_raised(libtest.Fail, (t / 1).__ge__, 2)
	test.fail_if_not_raised(libtest.Fail, (t / 3).__le__, 2)
	test.fail_if_not_raised(libtest.Fail, (t / 2).__rshift__, [])
	test.fail_if_not_raised(libtest.Fail, (t / []).__lshift__, 2)
	test.fail_if_not_raised(libtest.Fail, (t / 2).__mod__, str)
	test.fail_if_not_raised(libtest.Fail, (t / int).__mul__, str)

	try:
		with t/ValueError as r:
			raise OSError("foo")
	except libtest.Fail as exc:
		test.fail_if_not_instance(exc.__cause__, OSError)
		# passed
	else:
		test.fail("subject did not catch unexpected")

	try:
		with t/ValueError as r:
			raise ValueError("foo")
		test.fail_if_not_exact(r, None)
		# passed
	except:
		test.fail("exception raised when none was expected")

	try:
		with t/ValueError as r:
			pass
		test.fail_if_not_exact(r, None)
		# failed
	except libtest.Fail as exc:
		test.fail_if_not_exact(exc.__cause__, None)
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
	test.fail_if_not_raised(libtest.Fail, (t / Exception).__xor__, (lambda: None))

	x = raise_Foo ^ Foo/test
	# return was the trapped exception
	t/x.data == 1
	test.fail_if_not_raised(libtest.Fail, (t / Exception).__rxor__, (lambda: None))

	# any exceptions are failures
	t/1 != 2
	t/1 == 1
	t/1 >= 1
	t/1 >= 0
	t/1 <= 2
	t/1 <= 1
	t/[1] << 1
	t/1 >> [1]

	# reverse
	1 != 2/t
	1 == 1/t
	1 >= 1/t
	1 >= 0/t
	1 <= 2/t
	1 <= 1/t
	[1] << 1/t
	1 >> [1]/t

	# perverse
	1/t != 2
	1/t == 1
	1/t >= 1
	1/t >= 0
	1/t <= 2
	1/t <= 1
	[1]/t << 1
	1/t >> [1]

	# iteration produces Subjects
	for ts in t/[1,2,3]:
		ts < 5
		ts > 0

	class A(object):
		pass
	class B(A):
		pass

	t/B * A
	t/B() % B
	t/B() % A

def test_Dependency(test):
	t = libtest.Test(None)
	test.fail_if_not_raised(libtest.Dependency, t.depends, 'nosuchmoduleever.bar')
	test.fail_if_not_equal(test.depends('dev.libtest'), libtest)

if __name__ == '__main__':
	from .. import libtest; libtest.execmodule()
