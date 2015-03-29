/* Should never compile successfully. */
#include <Pythonnn.h>

static PyMethodDef methods[] = {
	{NULL}

xxxx

INIT()
{
	PyObject *mod;
	mod = PyModule_Create(&module);
	return(mod);
}
