"""
# Sanity checks for metrics.
"""
from ...routes import library as libroutes
from ...computation import library as libc
from .. import metrics

def test_Measurements_init(test):
	"""
	# Validate "event" initialization and iteration.
	"""
	tmp = test.exits.enter_context(libroutes.File.temporary())

	tm = metrics.Measurements(tmp)
	test/list(tm) == []

	entry = tm.event(identifier='1', type='test-entry')
	test/list(tm)[0][:2] == ('test-entry', 1)

def test_Telemetry(test):
	tmp = test.exits.enter_context(libroutes.File.temporary())

	t = metrics.Telemetry(tmp)
	test/list(t) == []

	tm = t.event('test-scope')
	test/tm / metrics.Measurements
	test/list(t) == [('test-scope', tm)]

def test_measure(test):
	"""
	# Perform measurements of contrived data.
	"""
	tmp = test.exits.enter_context(libroutes.File.temporary())

	t = metrics.Telemetry(tmp)

if __name__ == '__main__':
	from .. import libtest; import sys
	libtest.execute(sys.modules[__name__])
