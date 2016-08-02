"""
Used internally; emit an empty introspection XML file.

In cases where language introspection is not supported, a fallback must be
available for making product snapshots possible. &.bin.configure uses
this when a given language is not supported.
"""
import sys

output = "<?xml version='1.0' encoding='ascii'?><introspection></introspection>\n"

if __name__ == '__main__':
	sys.stdout.write(output)
	raise SystemExit(0)
