"""
# Command line reporting tool for navigating uncounted regions produced by &.measure.

##!/pl/sh
	metrics/measure project
	metrics/execute reveals
"""
import sys
import collections
import pickle

from ...system import library as libsys
from ...routes import library as libroutes
from .. import metrics

delimit_reveal_start = '['
delimit_reveal_stop = ']'
delimit_reveal_start = '\x1b[38;5;23m'
delimit_reveal_stop = '\x1b[0m'

def main(inv):
	cc = libroutes.File.from_absolute(inv.environ['CONTEXT'])
	root = cc / 'telemetry'
	assert root.exists()

	projects = root.subnodes()[0]
	for datadir in projects:
		project_data = datadir/'project'
		with (project_data/'source_index').open('rb') as f:
			relevant = pickle.load(f)
		with (project_data/'counters').open('rb') as f:
			countable = pickle.load(f)

		filtered = set()
		for path in countable:
			if path not in relevant:
				filtered.add(path)
		for path in filtered:
			countable.pop(path, None)

		n_counters_per_file = {f:len(v) for f,v in countable.items()}
		n_countable = sum(n_counters_per_file.values())

		counts = collections.defaultdict(collections.Counter)
		tests = set(datadir.subnodes()[0])
		tests.discard(project_data)

		# Aggregate
		for test in tests:
			context = '.'.join((datadir.identifier, test.identifier))
			pf = test / 'counters'
			with pf.open('rb') as f:
				counters = pickle.load(f)
			for f, data in counters.items():
				counts[f].update(data)

		for path, fcounts in counts.items():
			if path not in relevant:
				continue

			regions = countable[path]
			for key, count in fcounts.items():
				if count > 0:
					regions.pop(key, None)

		n_remaining = sum(map(len, countable.values()))
		n_covered = n_countable - n_remaining
		n_files = len(countable)

		summary = 'Coverage: %.02f%% = %d / %d over %d files\n'%(
			(n_covered / n_countable)*100,
			n_covered, n_countable, n_files
		)

		print(summary)
		for path, missing in countable.items():
			n_missing = len(missing)
			if n_missing == 0:
				continue
			lines = libroutes.File.from_absolute(path).load(mode='r').split('\n')

			header = '%s [%d lines %d missed counters of %d]'%(
				relevant[path][1], len(lines), n_missing, n_counters_per_file[path]
			)
			print("%s\n%s\n%s\n" %('='*len(header), header, '='*len(header)))

			for key, d in sorted(list(missing.items()), key=lambda x:x[1][0]):
				(startl, startc, stopl, stopc), typ = d

				if typ == 'skip':
					continue

				startl -= 1
				if stopc == 0:
					stopc = len(lines[stopl-2]) + 1
					stopl -= 1

				revealed = lines[startl:stopl]

				l = revealed[0]
				start_record = l
				l = revealed[0] = delimit_reveal_start.join((l[0:startc-1], l[startc-1:]))

				# Might be bad, but the implementation was obvious so go with it despite
				# the clumsy smell.
				stopi = stopl - 1
				if stopi == startl:
					# Compensate for prior insertion. Inherit `l` from prior manipulation.
					stopc += len(delimit_reveal_start)
					stop_record = start_record
				else:
					l = stop_record = revealed[-1]

				revealed[-1] = delimit_reveal_stop.join((l[0:stopc-1], l[stopc-1:]))

				if startl == stopl-1:
					print('Line %d, %s'%(startl+1,typ))
					print(revealed[0]+'\n')
				else:
					print('Lines %d-%d, %s'%(startl+1,stopl,typ))
					initial = revealed[0]+'\n'+delimit_reveal_start
					print(initial + (('\n'+delimit_reveal_start).join(revealed[1:])))
					print()
			print()

	inv.exit(0)

if __name__ == '__main__':
	libsys.control(main, libsys.Invocation.system(environ=('CONTEXT',)))
