"""
LLVM Probe for collecting compilation and linkage information.

Gathers information using (system:executable)`llvm-config`.
"""
import sys
import sysconfig
import shell_command

from .. import libprobe
#from .. import libconfig
__factor_type__ = 'system.probe'

parameters = {
	'executable':
		"The `llvm-config` executable to extract information from.",
}

libs_pipe = r"""{} profiledata --libs"""
syslibs_pipe = r"""{} profiledata --system-libs"""
incs_pipe = r"""{} --includedir"""
libdir_pipe = r"""{} --libdir"""

def deploy(*args):
	# No deployment necessary.
	libs = shell_command.shell_output(libs_pipe, 'llvm-config')
	syslibs = shell_command.shell_output(syslibs_pipe, 'llvm-config')

	libs = set(map(str.strip, libs.split('-l')))
	libs.update(map(str.strip, syslibs.split('-l')))
	libs.discard('')
	libs.add('c++')

	libdirs = shell_command.shell_output(libdir_pipe, 'llvm-config')
	libdirs = set(map(str.strip, libdirs.split('-L')))
	libdirs.discard('')

	incdirs = shell_command.shell_output(incs_pipe, 'llvm-config')
	incdirs = set(map(str.strip, incdirs.split('-I')))
	incdirs.discard('')

	rtti = shell_command.shell_output("{} --has-rtti", 'llvm-config')
	if rtti.lower() in {'yes', 'true', 'on'}:
		rtti = True
	else:
		rtti = False

	return {
		'system': {
			'library.set': libs,
			'library.directories': libdirs,
			'include.directories': incdirs,
			'standards': {
				'c++': 'c++11',
			},
			'command.option.injection': [
				'-fno-exceptions', '-fno-rtti',
			]
		},

		'software': {
			'llvm': {
				'rtti': rtti,
			}
		}
	}

if __name__ == '__main__':
	print(deploy())
