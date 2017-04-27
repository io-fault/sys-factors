"""
# Basic sanity checks for the metrics.
"""

def test_measure(test):
	"Perform measurements of already taken data."
	test.skip("not implemented")
	m = libtrace.measure(events)
	call_times, exact, lc = m
	libtrace.profile_aggregate(call_times, exact, mode=True, median=True)

