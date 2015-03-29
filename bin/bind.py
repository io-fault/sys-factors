csource = r"""
#include <Python.h>

#if __FreeBSD__
#include <floatingpoint.h>
#endif

#define PREPEND(STR) \
	PyObject_CallMethod(ob, "insert", "is", (int) 0, STR);
#define APPEND(STR) \
	PyObject_CallMethod(ob, "append", "s", STR);

static wchar_t xname[] = PYTHON_EXEC_CHARS;
int
main(int argc, char *argv[])
{
	int r;
	wchar_t **wargv;
	PyObject *ob, *mod;

#if __FreeBSD__
	/* from python.c */
	fp_except_t m;
	m = fpgetmask();
	fpsetmask(m & ~FP_X_OFL);
#endif

	Py_SetProgramName(xname);
	Py_Initialize();
	if (!Py_IsInitialized())
	{
		fprintf(stderr, "could not initialize python\n");
		return(200);
	}

	/* XXX: This is... not entirely consistent with python.c, so... */
	wargv = PyMem_Malloc(sizeof(wchar_t *) * argc);
	for (r = 0; r < argc; ++r)
	{
		wargv[r] = _Py_char2wchar(argv[r], NULL);
	}
	PySys_SetArgvEx(argc, wargv, 0);

	PyEval_InitThreads();
	if (!PyEval_ThreadsInitialized())
	{
		fprintf(stderr, "could not initialize python threading\n");
		return(199);
	}

	ob = PySys_GetObject("path");
	if (ob == NULL)
	{
		fprintf(stderr, "could not get sys.path\n");
		return(198);
	}

	APPENDS()
	PREPENDS()

	mod = PyImport_ImportModule(MODULE_NAME);
	if (mod == NULL)
	{
		fprintf(stderr, "could not import bound module: " MODULE_NAME "\n");
		return(197);
	}
	else
		Py_DECREF(mod);

	ob = PyObject_CallMethod(mod, CALL_NAME, ""); /* main entry point */
	if (ob != NULL)
	{
		if (ob == Py_None)
		{
			r = 0;
		}
		else if (PyLong_Check(ob))
		{
			r = (int) PyLong_AsLong(ob);
		}
		else
		{
			fprintf(stderr,
				"bound module's, "
				MODULE_NAME
				", callable, "
				CALL_NAME
				", did not return a long\n");
			r = 190;
		}

		Py_DECREF(ob); ob = NULL;
	}
	else
	{
		printf("bound module did not trap exceptions\n");
		r = 1; /* generic failure */
	}

	Py_Finalize();
	return(r);
}
"""

def buildcall(target, filename):
	"""
	Construct the parameters to be used to compile and link the new executable.
	"""
	import sysconfig
	libs = tuple(sysconfig.get_config_var('SHLIBS').split())
	syslibs = tuple(sysconfig.get_config_var('SYSLIBS').split())
	ldflags = tuple(sysconfig.get_config_var('LDFLAGS').split())
	pyversion = sysconfig.get_config_var('VERSION')
	pyabi = sysconfig.get_config_var('ABIFLAGS') or ''
	pyspec = 'python' + pyversion + pyabi
	return (
		'clang' or sysconfig.get_config_var('CC'), '-v',
		'-ferror-limit=3', '-Wno-array-bounds',
		'-o', target,
	) + libs + syslibs + ldflags + (
		'-I' + sysconfig.get_config_var('INCLUDEPY'),
		'-L' + sysconfig.get_config_var('LIBDIR'),
		'-l' + pyspec,
		filename,
	)

def _macrostr(func, string):
	return func + '("' + string + '")'

def bind(target, module_path, call_name, prepend_paths = [], append_paths = []):
	import tempfile
	import subprocess
	with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix='.c') as f:
		f.write("\n#define PYTHON_EXEC_CHARS " + "{'" + "','".join(sys.executable) + "', 0}")
		f.write('\n#define MODULE_NAME "' + module_path + '"')
		f.write('\n#define CALL_NAME "' + call_name + '"')
		f.write('\n#define PREPENDS() ' + ' '.join([_macrostr("PREPEND", x) for x in prepend_paths]))
		f.write('\n#define APPENDS() ' + ' '.join([_macrostr("APPEND", x) for x in append_paths]))
		f.write(csource)
		f.flush()
		f.seek(0)
		p = subprocess.Popen(buildcall(target, f.name))
		p.wait()

if __name__ == '__main__':
	import sys
	target, module_path, call_name = sys.argv[1:]
	bind(target, module_path, call_name)
