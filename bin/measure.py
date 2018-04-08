"""
# Collect metrics from the project tests using the tools installed into the metrics context.
"""
import sys
import os
import itertools
import contextlib
import collections
import pickle

from fault.system import libfactor
from fault.routes import library as libroutes
from fault.system import corefile
from fault.system import library as libsys

from .. import metrics
from .. import cc

def test(context, telemetry, tools, route):
	"""
	# Collect telemetry from the tests of the project identified by &route.
	"""
	factor_map = collections.defaultdict(dict)
	source_path_map = dict()

	# Gather the mechanisms used to performa build of all the factor and identify
	# the tooling used to manage the telemetry for a given language.
	simulated_factors = cc.gather_simulations([route])
	composites = [
		cc.Factor(target, target.module(trap=False), None)
		for target in route.tree()[0]
		if libfactor.composite(target)
	]

	for f in composites:
		variants, mech = context.select(f.domain)
		varset = f.link(variants, context, mech, [], [])
		tool_set = collections.defaultdict(set)
		factor_path = str(f.route)
		source_prefix = len(str(f.source_directory))+1

		lmech = None
		for src_params, (vl, key, locations) in varset:
			for src in f.sources():
				build = cc.Build((context, mech, f, [], [], dict(vl), locations, src_params))
				lmech = mech.adaption(build, f.domain, src)
				if lmech is not None:
					tool_ref = lmech.get('telemetry')
					tool_set[tool_ref].add(src)

				qfactor_path = "%s/%s" %(factor_path, str(src)[source_prefix:])
				source_path_map[str(src)] = ('fraction', qfactor_path, factor_path)

			target_link = locations['integral'] / 'pf.lnk'
			target = target_link.from_relative(target_link.container, os.readlink(str(target_link)))
			for tool_name, sources in tool_set.items():
				target_data = (f.route, target, sources)
				factor_map[tool_name][factor_path] = target_data
				ean = libfactor.extension_access_name(factor_path)
				factor_map[tool_name][ean] = target_data

			# Variants should be irrelevant here as we're strictly interested
			# the instrumentation tool associated with the transformation.
			break

	# Shortcut and compensation for simulated composites.
	# The simulated composites pretend packages are the targets,
	# but reality is that each module is an independent factor,
	# not a fraction of a composite, so the simulations need to be unrolled here.
	variants, domain = context.select('bytecode.python')
	mech = domain.descriptor['transformations']['python']
	tool_ref = mech.get('telemetry')
	for f in simulated_factors:
		for src in f.sources():
			module_name = src.identifier.rsplit('.', 1)[0]
			if module_name == '__init__':
				s_route = f.route
			else:
				s_route = f.route / module_name

			source_path_map[str(src)] = ('whole', str(s_route), str(s_route.container))
			factor_map[tool_ref][str(s_route)] = (s_route, None, [src])

	division = metrics.Telemetry(telemetry / str(route) / 'test')
	division.init()
	os.environ['PROJECT'] = str(route)

	# Make entry for countable region information identified by the tools.
	project_region_map = telemetry / str(route) / 'project'
	project_region_map.init('directory')

	# Store the mapping for use by other tools.
	with (project_region_map / 'source_index').open('wb') as f:
		pickle.dump(source_path_map, f)

	# Extract coverage mapping information from the factors.
	counter_data = collections.defaultdict(dict)
	for probe, data in tools:
		relevant = factor_map[probe.name]

		counter_data.update(probe.project(division, route, relevant))

	with (project_region_map / 'counters').open('wb') as f:
		pickle.dump(counter_data, f)

	harness = metrics.Harness(tools, context, division, str(route), sys.stderr)
	harness.execute(harness.root(route), ())

	captures = [
		metrics.Measurements(x) for x in (telemetry/str(route)).subdirectories()
		if x.identifier != 'project'
	]

	# Convert, filter, and combine counters and profile data emitted by the probes.
	for capture in captures:
		profile = collections.defaultdict(lambda: collections.defaultdict(list))
		counters = collections.defaultdict(collections.Counter)

		for probe, data in tools:
			for path, data in probe.counters(factor_map[probe.name], capture):
				l = collections.Counter(dict(data))
				counters[path].update(l)

			for path, data in probe.profile(factor_map[probe.name], capture):
				for key, times in data.items():
					profile[path][key].extend(times)

		with (capture.route / 'counters').open('wb') as f:
			pickle.dump(counters, f)

		with (capture.route / 'profile').open('wb') as f:
			kprofile = {
				k: dict(v)
				for k, v in profile.items()
			}
			pickle.dump(kprofile, f)

	return harness

def update_tool_contexts(harness):
	"""
	# Upon forking, the data collected by the tools need to be purged and their
	# target files updated to refer to the new process.
	"""
	process_data = harness.telemetry.event(harness.test).event()

	# XXX: atfork handler used by tests.
	atfork = (lambda: update(lharness))

	# Update default profile locations to the per process directory.
	libsys.fork_child_cleanup.add(atfork)
	libsys.fork_child_cleanup.discard(atfork)
	del atfork

def main(inv):
	packages = inv.args
	if not packages:
		# No work.
		return inv.exit(0)

	# Discover projects from any context packages.
	projects = []
	for package in packages:
		route = libroutes.Import.from_fullname(package)
		module = route.module()
		factor_type = getattr(module, '__factor_type__', 'python')

		if factor_type == 'context':
			for possible_project in route.subnodes()[0]:
				pkg_type = getattr(possible_project.module(), '__factor_type__', None)
				if pkg_type == 'project':
					projects.append(possible_project)
		elif factor_type == 'project':
			projects.append(route)
		else:
			sys.stderr.write("! ERROR: factor %s is not a project" %(package,))
			return inv.exit(1)
	projects.sort(key=(lambda x: str(x)))

	# Expecting metrics intention to be configured.
	ctx = cc.Context.from_environment()
	ctx_route = libroutes.File.from_absolute(os.environ.get('CONTEXT'))
	if not ctx_route.exists():
		sys.stderr.write("! ERROR: construction context %r does not exist" %(ctx_route,))
		return inv.exit(1)

	if 'TELEMETRY' not in os.environ or not os.environ['TELEMETRY'].strip():
		# Telemetry unspecified, default to context/telemetry
		telemetry = ctx_route / 'telemetry'
		os.environ['TELEMETRY'] = str(telemetry)
	else:
		telemetry = libroutes.File.from_absolute(os.environ['TELEMETRY'])

	if telemetry.exists():
		telemetry.void()
	telemetry.init('directory')

	# Collect tools from the metrics context.
	tools = ctx.parameters.tree('tools') # llvm and python normally
	tool_stack = contextlib.ExitStack()
	tools = [
		(libroutes.Import.dereference(tdata['constructor'])(t), tdata)
		for t, tdata in tools.items()
		if 'constructor' in tdata
	]

	# Make sure fragments.python is placed last in the sequence.
	# Avoids the collection of data regarding other tooling.
	tools.sort(key=lambda k:(k[1]['constructor']=='fragments.python.library.Probe'))
	for t, d in tools:
		tool_stack.enter_context(t.setup(ctx, telemetry, d)) # (Harness, tool Data)

	# global tool instance initialization
	# tools[n].connect() constructs the per-test contextmanager inside
	# &metrics.Harness.seal
	tool_stack.__enter__()

	try:
		for project in projects:
			sys.stderr.write(str(project))
			sys.stderr.flush()
			test(ctx, telemetry, tools, project)
			sys.stderr.write('\n')
	except libsys.Fork:
		# Process is being forked. Likely from libsys.concurrently
		# to perform a test with process isolation.
		raise
	except:
		tool_stack.__exit__(*sys.exc_info())
		raise
	else:
		tool_stack.__exit__(None, None, None)

	return inv.exit(0)

if __name__ == '__main__':
	# Suspend core constraints if any.
	cm = corefile.constraint(None).__enter__()

	# Adjust the profile file environment to a trap file.
	# The actual file is set before each test.
	libsys.control(main, libsys.Invocation.system(environ=['CONTEXT']))
