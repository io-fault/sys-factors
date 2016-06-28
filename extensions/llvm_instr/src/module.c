#include <fault/roles.h>
#include <fault/python/environ.h>

int _list_regions(PyObj, char *obj_path, char *arch);
static PyObj
list_regions(PyObj self, PyObj args)
{
	PyObj path = NULL;
	char *arch = STRING_FROM_IDENTIFIER(PRODUCT_ARCHITECTURE);
	PyObj rob;
	int r;

	if (!PyArg_ParseTuple(args, "O&|s", PyUnicode_FSConverter, &path, &arch))
		return(NULL);

	rob = PyList_New(0);
	if (rob == NULL)
		return(NULL);

	r = _list_regions(rob, PyBytes_AS_STRING(path), arch);
	if (r)
		goto fail;

	Py_DECREF(path);
	return(rob);

	fail:
	{
		Py_DECREF(path);
		Py_DECREF(rob);
		return(NULL);
	}
}

int _list_source_files(PyObj, char *obj_path, char *arch);
static PyObj
list_source_files(PyObj self, PyObj args)
{
	PyObj path = NULL;
	char *arch = STRING_FROM_IDENTIFIER(PRODUCT_ARCHITECTURE);
	PyObj rob;
	int r;

	if (!PyArg_ParseTuple(args, "O&|s", PyUnicode_FSConverter, &path, &arch))
		return(NULL);

	rob = PyList_New(0);
	if (rob == NULL)
		return(NULL);

	r = _list_source_files(rob, PyBytes_AS_STRING(path), arch);
	if (r)
		goto fail;

	Py_DECREF(path);
	return(rob);

	fail:
	{
		Py_DECREF(path);
		Py_XDECREF(rob);
		return(NULL);
	}
}

int _extract_counters(PyObj, char *obj_path, char *src, char *arch);
static PyObj
extract_counters(PyObj self, PyObj args)
{
	char *path, *src, *arch = STRING_FROM_IDENTIFIER(PRODUCT_ARCHITECTURE);
	PyObj rob;
	int r;

	if (!PyArg_ParseTuple(args, "O&O&|s", PyUnicode_FSConverter, &path, PyUnicode_FSConverter, &src, &arch))
		return(NULL);

	rob = PyList_New(0);
	if (rob == NULL)
		return(NULL);

	r = _extract_counters(rob, PyBytes_AS_STRING(path), PyBytes_AS_STRING(src), arch);
	if (r)
		goto fail;

	Py_DECREF(path);
	Py_DECREF(src);
	return(rob);

	fail:
	{
		Py_DECREF(path);
		Py_DECREF(src);
		Py_DECREF(rob);
		return(NULL);
	}
}

int _extract_nonzero_counters(PyObj, char *obj_path, char *src, char *arch);
static PyObj
extract_nonzero_counters(PyObj self, PyObj args)
{
	char *path, *src, *arch = STRING_FROM_IDENTIFIER(PRODUCT_ARCHITECTURE);
	PyObj rob;
	int r;

	if (!PyArg_ParseTuple(args, "O&O&|s", PyUnicode_FSConverter, &path, PyUnicode_FSConverter, &src, &arch))
		return(NULL);

	rob = PyList_New(0);
	if (rob == NULL)
		return(NULL);

	r = _extract_nonzero_counters(rob, PyBytes_AS_STRING(path), PyBytes_AS_STRING(src), arch);
	if (r)
		goto fail;

	Py_DECREF(path);
	Py_DECREF(src);
	return(rob);

	fail:
	{
		Py_DECREF(path);
		Py_DECREF(src);
		Py_DECREF(rob);
		return(NULL);
	}
}

int _extract_zero_counters(PyObj, char *obj_path, char *src, char *arch);
static PyObj
extract_zero_counters(PyObj self, PyObj args)
{
	char *path, *src, *arch = PRODUCT_ARCHITECTURE_STR;
	PyObj rob;
	int r;

	if (!PyArg_ParseTuple(args, "O&O&|s", PyUnicode_FSConverter, &path, PyUnicode_FSConverter, &src, &arch))
		return(NULL);

	rob = PyList_New(0);
	if (rob == NULL)
		return(NULL);

	r = _extract_zero_counters(rob, PyBytes_AS_STRING(path), PyBytes_AS_STRING(src), arch);
	if (r)
		goto fail;

	Py_DECREF(path);
	Py_DECREF(src);
	return(rob);

	fail:
	{
		Py_DECREF(path);
		Py_DECREF(src);
		Py_DECREF(rob);
		return(NULL);
	}
}

#define MODULE_FUNCTIONS() \
	PYMETHOD(list_source_files, list_source_files, METH_VARARGS, \
		"Return a list of source paths that are referenced by an instrumented object.") \
	PYMETHOD(list_regions, list_regions, METH_VARARGS, \
		"List the sequence of regions for each source file instrumented within the object.") \
	PYMETHOD(extract_counters, extract_counters, METH_VARARGS, \
		"Extract the all the counters from the merged profile data with respect to the system object.") \
	PYMETHOD(extract_nonzero_counters, extract_nonzero_counters, METH_VARARGS, \
		"Extract the all the non-zero counters from the merged profile data with respect to the system object.") \
	PYMETHOD(extract_zero_counters, extract_zero_counters, METH_VARARGS, \
		"Extract the all the zero counters from the merged profile data with respect to the system object.")

#include <fault/python/module.h>
INIT("Access LLVM instrumentation structures and profile counters.")
{
	PyObj mod;
	CREATE_MODULE(&mod);
	if (mod == NULL)
		return(NULL);

	return(mod);
}
