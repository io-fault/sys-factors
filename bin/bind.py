"""
# Create a Python executable bound to the execution of a particular module.
"""

csource = r"""
#include <Python.h>

#if __FreeBSD__
#include <floatingpoint.h>
#endif

#define PREPEND(STR) \
	PyObject_CallMethod(ob, "insert", "is", (int) 0, STR);
#define APPEND(STR) \
	PyObject_CallMethod(ob, "append", "s", STR);

#if PY_VERSION_HEX < 0x03050000
	/* Renamed in 3.5+ */
	#define Py_DecodeLocale _Py_char2wchar
#endif

static wchar_t xname[] = PYTHON_EXEC_CHARS;
int
main(int argc, char *argv[])
{
	int r, nbytes;
	wchar_t **wargv;
	PyObject *ob, *mod;

	#if __FreeBSD__
		/* from python.c */
		fp_except_t m;
		m = fpgetmask();
		fpsetmask(m & ~FP_X_OFL);
	#endif

	Py_DebugFlag = 0;
	Py_NoUserSiteDirectory = 1;
	Py_IgnoreEnvironmentFlag = 1;
	Py_DontWriteBytecodeFlag = 1;

	Py_SetProgramName(xname);
	Py_Initialize();
	if (!Py_IsInitialized())
	{
		fprintf(stderr, "[!# ERROR: could not initialize python]\n");
		return(200);
	}
	_PyRandom_Init();

	nbytes = sizeof(wchar_t *) * (argc+1);
	wargv = PyMem_RawMalloc(nbytes);
	if (wargv == NULL)
	{
		fprintf(stderr, "[!# ERROR: failed to allocate %d bytes of memory for system arguments]\n", nbytes);
		return(210);
	}

	for (r = 0; r < argc; ++r)
	{
		wargv[r] = Py_DecodeLocale(argv[r], NULL);
		if (wargv[r] == NULL)
		{
			fprintf(stderr, "[!# ERROR: failed to decode system arguments]\n");
			return(210);
		}
	}

	PySys_SetArgvEx(argc, wargv, 0);

	PyEval_InitThreads();
	if (!PyEval_ThreadsInitialized())
	{
		fprintf(stderr, "[!# ERROR: failed to initialize threading]\n");
		return(199);
	}

	ob = PySys_GetObject("path");
	if (ob == NULL)
	{
		fprintf(stderr, "[!# ERROR: failed to initialize execution context]\n");
		return(198);
	}

	APPENDS()
	PREPENDS()

	mod = PyImport_ImportModule(MODULE_NAME);
	if (mod == NULL)
	{
		fprintf(stderr, "[!# ERROR: failed to import implementation module: " MODULE_NAME "]\n");
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

		Py_DECREF(ob);
		ob = NULL;
	}
	else
	{
		if (PyErr_ExceptionMatches(PyExc_SystemExit))
		{
			PyObject *exc, *val, *tb;
			PyErr_Fetch(&exc, &val, &tb);
			PyObject *pi;

			if (val)
			{
				pi = PyObject_GetAttrString(val, "code");
				if (pi)
				{
					r = (int) PyLong_AsLong(pi);
					Py_DECREF(pi);
				}
			}

			Py_DECREF(exc);
			Py_XDECREF(val);
			Py_XDECREF(tb);

			PyErr_Clear();
		}
		else
		{
			fprintf(stderr, "[!# CONTROL: implementation module raised exception]\n");
			PyErr_Print();
			fflush(stderr);
			r = 1;
		}
	}

	Py_Exit(r);
	return(r);
}
"""

def buildcall(target, filename):
	"""
	# Construct the parameters to be used to compile and link the new executable.
	"""
	import sysconfig

	ldflags = tuple(sysconfig.get_config_var('LDFLAGS').split())
	pyversion = sysconfig.get_config_var('VERSION')
	pyabi = sysconfig.get_config_var('ABIFLAGS') or ''
	pyspec = 'python' + pyversion + pyabi

	return (
		'clang' or sysconfig.get_config_var('CC'), '-v',
		'-ferror-limit=3', '-Wno-array-bounds',
		'-o', target,
	) + ldflags + (
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
		syscall = buildcall(target, f.name)
		p = subprocess.Popen(syscall)
		p.wait()

if __name__ == '__main__':
	import sys
	target, module_path, call_name, *paths = sys.argv[1:]
	bind(target, module_path, call_name, prepend_paths = paths)
