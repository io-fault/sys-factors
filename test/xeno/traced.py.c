/*
 * traced.py.c - test library for the c loader
 */
#include <Python.h>
#include <structmember.h>

/* METH_O, METH_VARARGS, METH_VARKEYWORDS, METH_NOARGS */
METHODS() = {
	{NULL}
};

INIT("")
{
	PyObj mod;
	CREATE_MODULE(&mod);
	return(mod);
}
