/*
 * Query profile output and binaries for counts and region area information.
 */
#include <stddef.h>
#include <limits.h>

extern "C" {
#include <fault/roles.h>
#include <Python.h>
#include <fault/python/environ.h>
#include <fault/internal.h>
}

#undef isalnum
#undef isalpha
#undef islower
#undef isspace
#undef isupper
#undef tolower
#undef toupper

#undef DEBUG

#define __STDC_LIMIT_MACROS 1
#define __STDC_CONSTANT_MACROS 1

#include <ctype.h>

// CounterMappingRegion (mapping stored in binaries)
#include "llvm/ProfileData/CoverageMapping.h"

#include "llvm/ADT/DenseMap.h"
#include "llvm/ADT/Optional.h"
#include "llvm/ADT/SmallBitVector.h"

// File reader for iterating over mapping regions.
#include "llvm/ProfileData/CoverageMappingReader.h"
#include "llvm/ProfileData/InstrProfReader.h"

#include "llvm/Support/Debug.h"
#include "llvm/Support/Errc.h"
#include "llvm/Support/ErrorHandling.h"
#include "llvm/Support/ManagedStatic.h"
#include "llvm/Support/Path.h"
#include "llvm/Support/raw_ostream.h"

#include <system_error>
#include <tuple>
#include <iostream>
#include <set>

using namespace llvm;

extern "C" {

static int kind_map[] = {
	1, -1, 0,
};

// CounterMappingRegion is per-function and contains start-stop line/column pairs.
//
// CoverageArch is the target triple commonly used by clang/gcc
int
_list_regions(PyObj seq, char *object, char *arch)
{
	auto buffer = MemoryBuffer::getFile(object);
	if (std::error_code EC = buffer.getError())
	{
		PyErr_SetString(PyExc_RuntimeError, "failed to load counter mapping memory buffer from object");
		return(1);
	}

	auto CoverageReaderOrErr = coverage::BinaryCoverageReader::create(buffer.get(), arch);
	if (!CoverageReaderOrErr)
	{
		if (auto E = CoverageReaderOrErr.getError())
		{
			PyErr_SetString(PyExc_RuntimeError, E.message().c_str());
			return(1);
		}

		PyErr_SetString(PyExc_RuntimeError, "failed to load counter mapping reader from object");
		return(1);
	}

	auto CoverageReader = std::move(CoverageReaderOrErr.get());

	StringRef curfile("");
	unsigned fid = 0;
	auto needs_switch = true;

	PyObj path = NULL;
	PyObj cur = PyList_New(0);

	if (cur == NULL)
		return(1);

	PyObj range = NULL;

	/*
	 * The nested for loop will start a new section every time the fileid
	 * changes so the reader can properly associate ranges.
	 */
	for (const auto &Record : (*CoverageReader))
	{
		for (const auto &Region : Record.MappingRegions)
		{
			if (Record.Filenames[Region.FileID] != curfile)
			{
				curfile = Record.Filenames[Region.FileID];
				std::string curfile_string = curfile;

				path = PyUnicode_FromStringAndSize(curfile_string.data(), curfile_string.length());
				PyList_Append(seq, path);
				Py_DECREF(path);
				PyList_Append(seq, cur);

				Py_DECREF(cur);
				// Begin new sequence for file.
				cur = PyList_New(0);
			}

			{
				range = Py_BuildValue("lkkkk",
					kind_map[((unsigned int) (Region.Kind))],
					(unsigned long) Region.LineStart, (unsigned long) Region.ColumnStart,
					(unsigned long) Region.LineEnd, (unsigned long) Region.ColumnEnd);
				if (range == NULL)
				{
					Py_DECREF(cur); /* not in seq */

					// caller decref's &seq
					return(1);
				}

				PyList_Append(cur, range);
				Py_DECREF(range);
			}
		}
	}

	return(0);
}

// List unique files covered.
int
_list_source_files(PyObj seq, const char *object, const char *arch)
{
	auto CounterMappingBuff = MemoryBuffer::getFile(object);
	if (std::error_code EC = CounterMappingBuff.getError())
	{
		PyErr_SetString(PyExc_RuntimeError, EC.message().c_str());
		return(1);
	}

	auto CoverageReaderOrErr = coverage::BinaryCoverageReader::create(CounterMappingBuff.get(), arch);
	if (!CoverageReaderOrErr)
	{
		if (auto E = CoverageReaderOrErr.getError())
		{
			PyErr_SetString(PyExc_RuntimeError, E.message().c_str());
			return(1);
		}

		return(1);
	}

	auto CoverageReader = std::move(CoverageReaderOrErr.get());
	std::set<std::string> paths;

	/*
	 * The nested for loop will start a new section every time the fileid
	 * changes so the reader can properly associate ranges.
	 */
	for (const auto &Record : (*CoverageReader))
	{
		for (const auto path : Record.Filenames)
		{
			paths.insert((std::string) path);
		}
	}

	for (auto path : paths)
	{
		PyObj s;
		s = PyUnicode_FromStringAndSize(path.data(), path.length());
		if (s == NULL)
			return(1);
		PyList_Append(seq, s);
	}

	return(0);
}

int
_extract_counters(PyObj seq, char *object, char *profile, char *arch)
{
	auto CoverageOrErr = coverage::CoverageMapping::load(object, profile, arch);

	if (auto E = CoverageOrErr.getError())
	{
		PyErr_SetString(PyExc_RuntimeError, E.message().c_str());
		return(1);
	}

	auto coverage = std::move(CoverageOrErr.get());
	auto files = coverage.get()->getUniqueSourceFiles();

	for (auto &file : files)
	{
		auto data = coverage.get()->getCoverageForFile(file);
		std::string filestr = file;

		if (data.empty())
			continue;

		PyObj subseq, path_ob;

		path_ob = PyUnicode_FromStringAndSize(filestr.data(), filestr.size());
		subseq = PyList_New(0);
		PyObj x = PyTuple_New(2);
		PyTuple_SET_ITEM(x, 0, path_ob);
		PyTuple_SET_ITEM(x, 1, subseq);
		PyList_Append(seq, x);
		Py_DECREF(x);
		x = NULL;

		for (auto seg : data)
		{
			PyObj count_tuple = Py_BuildValue("kkk", (unsigned long) seg.Line, (unsigned long) seg.Col, (unsigned long) seg.Count);
			PyList_Append(subseq, count_tuple);
			Py_DECREF(count_tuple);
		}
	}

	return(0);
}

int
_extract_nonzero_counters(PyObj seq, char *object, char *profile, char *arch)
{
	auto CoverageOrErr = coverage::CoverageMapping::load(object, profile, arch);

	if (auto E = CoverageOrErr.getError())
	{
		PyErr_SetString(PyExc_RuntimeError, E.message().c_str());
		return(1);
	}

	auto coverage = std::move(CoverageOrErr.get());
	auto files = coverage.get()->getUniqueSourceFiles();

	for (auto &file : files)
	{
		auto data = coverage.get()->getCoverageForFile(file);

		if (data.empty())
			continue;

		std::string filestr = file;
		PyObj subseq, path_ob;

		path_ob = PyUnicode_FromStringAndSize(filestr.data(), filestr.size());
		subseq = PyList_New(0);
		PyObj x = PyTuple_New(2);
		PyTuple_SET_ITEM(x, 0, path_ob);
		PyTuple_SET_ITEM(x, 1, subseq);
		PyList_Append(seq, x);
		Py_DECREF(x);
		x = NULL;

		auto started = false;

		for (auto seg : data)
		{
			if (seg.HasCount && seg.Count > 0)
			{
				if (!started)
					started = true;

				PyObj count_tuple = Py_BuildValue("kkk", (unsigned long) seg.Line, (unsigned long) seg.Col, (unsigned long) seg.Count);
				PyList_Append(subseq, count_tuple);
				Py_DECREF(count_tuple);
			}
			else
			{
				if (started)
				{
					started = false;

					PyObj count_tuple = Py_BuildValue("kkO", (unsigned long) seg.Line, (unsigned long) seg.Col, Py_None);
					PyList_Append(subseq, count_tuple);
					Py_DECREF(count_tuple);
				}
			}
		}

		started = false;
	}

	return(0);
}

} // extern "C"
