"""
# Test harness access for collecting metrics.

# Invoking measure requires two or more command parameters. The first is the reporting
# directory, for collected data, and the remainder being packages to test.
"""
import sys
import os
import functools
import itertools
import pickle

from .. import metrics
from .. import library as libdev
from ...system import libfactor

from fragments.llvm import instr

from ...routes import library as libroutes
from ...system import corefile
from ...system import library as libsys
from ...computation import library as libc

RangeSet = libc.range.Set

# Expecting metrics intention to be configured.
MetricsContext = libdev.Context.from_environment()

def get_metrics_target(route):
	f = libdev.Factor(route, None, None)
	vars, mech = MetricsContext.select(f.domain)
	refs = libdev.references(f.dependencies())
	(sp, (vl, key, loc)), = f.link(dict(vars), MetricsContext, mech, refs, ())
	dll = loc['integral'] / 'pf.lnk'

	return dll

def main(target_dir, packages):
	target_fsdict = metrics.libfs.Dictionary.create(
		metrics.libfs.Hash('fnv1a_32', depth=1), target_dir
	)

	work = libroutes.File.from_path(target_dir) / '_instr_cov_'
	if work.exists():
		work.void()
	work.init('directory')

	llvm = (work / 'llvm')
	llvm.init('directory')

	os.environ['LLVM_PROFILE_FILE'] = str(llvm / 'trap.profraw')
	target_fsdict[b'metrics:packages'] = b'\n'.join(x.encode('utf-8') for x in packages)

	p = None
	for package in packages:
		p = metrics.Harness(work, target_fsdict, package, sys.stderr)
		p.execute(p.root(libroutes.Import.from_fullname(package)), ())
		# Build measurements.

	metrics.prepare(target_fsdict)

	# &metrics.prepare manages the data produced by Python,
	# but the instrumentation is managed by llvm-profdata merge.
	fct = os.environ.get('FAULT_COVERAGE_TOTALS', str(work / 'totals'))
	metrics.Harness.merge_instrumentation_metrics(work, fct)
	fct_r = libroutes.File.from_absolute(fct)

	# Collect the per-test instrumentation data from the filesystem.
	for x in fct_r.subnodes()[1]:
		cm = libfactor.extension_composite_name(str(x.identifier))
		ci = libroutes.Import.from_fullname(cm)
		src_r = libfactor.sources(ci)
		prefix = str(src_r) + '/'
		prefix_len = len(prefix) - 1
		module = ci.module()

		so = get_metrics_target(ci)
		xc = dict(instr.extract_counters(str(so), str(x)))
		xz = dict(instr.extract_zero_counters(str(so), str(x)))

		for path in instr.list_source_files(str(so)):
			if not path.startswith(prefix):
				continue

			suffix = path[prefix_len:]
			key = libfactor.canonical_name(ci) + suffix
			ek = key.encode('utf-8')
			covkey = b'coverage:' + ek

			data = pickle.loads(target_fsdict[covkey])
			data['full_counters'] = xc[path]

			# None partitioned list.
			ll = []
			i = iter(xz[path])
			while True:
				l = list(iter(i.__next__, None))
				if not l:
					break
				ll.append(l)

			data['zero_counters'] = ll

			# lines with positive counts.
			stop = start = None
			traversed_inc = []
			for lineno, offset, c in xc[path]:
				if c > 0:
					stop = lineno
					if start is None:
						start = lineno
				elif stop is not None:
					traversed_inc.append((start, stop))
					start = stop = None

			data['untraversed'] = RangeSet.from_normal_sequence([(x[0][0], x[1][0]) for x in data['zero_counters']])
			data['traversed'] = RangeSet.from_normal_sequence(traversed_inc)
			with open(str(path), 'rb') as f:
				lc = len(f.readlines())
			data['traversable'] = RangeSet.from_normal_sequence([libc.range.IRange((1, lc))])

			with target_fsdict.route(covkey).open('wb') as f:
				pickle.dump(data, f)

	raise SystemExit(0)

if __name__ == '__main__':
	import atexit
	target_dir, *packages = sys.argv[1:]
	if not packages:
		raise TypeError("command invoked with one parameter; requires: '.bin.measure target_dir packages ...'")

	# Remove core constraints if any.
	cm = corefile.constraint(None).__enter__()

	# Adjust the profile file environment to a trap file.
	# The actual file is set before each test.
	libsys.control(functools.partial(main, target_dir, packages))
