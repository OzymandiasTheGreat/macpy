#!/usr/bin/env python3

import sys
import os
import getpass
from subprocess import check_output, CalledProcessError
if sys.version_info >= (3, 6):
	from enum import Enum, auto
else:
	from aenum import Enum, auto


class Platform(Enum):

	WINDOWS = auto()
	X11 = auto()
	WAYLAND = auto()

class Arch(Enum):

	X86_64 = auto()
	X86 = auto()


if sys.platform.startswith('win32'):
	PLATFORM = Platform.WINDOWS
elif sys.platform.startswith('linux'):
	try:
		sessions = check_output(
			['loginctl', 'list-sessions'], universal_newlines=True)
		current_user = getpass.getuser()
		current_user = current_user if current_user != 'root' else os.getlogin()
		for line in sessions.splitlines():
			if current_user in line:
				session = line.split()[0]
		session_type = check_output(
			['loginctl', 'show-session', session, '-p', 'Type'],
			universal_newlines=True)
		if session_type.startswith('Type=wayland'):
			PLATFORM = Platform.WAYLAND
		else:
			PLATFORM = Platform.X11
	except (FileNotFoundError, NameError, CalledProcessError):
		PLATFORM = Platform.X11
else:
	PLATFORM = Platform.X11


if sys.maxsize > 2**32:
	ARCH = Arch.X86_64
else:
	ARCH = Arch.X86
