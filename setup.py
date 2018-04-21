#!/usr/bin/env python3

import os.path
from imp import load_source
from setuptools import setup


version = load_source('version', os.path.abspath('macpy/version.py'))


with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as fd:
	long_description = fd.read()


classifiers = [
	'Development Status :: 4 - Beta',
	'Intended Audience :: Developers',
	'Environment :: Win32 (MS Windows)',
	'Environment :: X11 Applications',
	'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
	'Operating System :: Microsoft :: Windows',
	'Operating System :: POSIX :: Linux']


setup(
	name='macpy',
	version=version.__version__,
	description='Simple, cross-platform macros/GUI automation for python',
	long_description=long_description,
	url='https://github.com/OzymandiasTheGreat/macpy',
	author='Tomas Ravinskas',
	author_email='tomas.rav@gmail.com',
	license='LGPLv3+',
	classifiers=classifiers,
	packages=['macpy', 'macpy.constant', 'macpy.constant.XK', 'macpy.interface',
		'macpy.types', 'macpy.libxkbswitch'],
	package_dir={'macpy': 'macpy', 'macpy.constant': 'macpy/constant',
		'macpy.constant.XK': 'macpy/constant/XK',
		'macpy.interface': 'macpy/interface', 'macpy.types': 'macpy/types',
		'macpy.libxkbswitch': 'macpy/libxkbswitch'},
	package_data={'': ['*.so']},
	install_requires=[
		'python-xlib;sys_platform=="linux"',
		'evdev;sys_platform=="linux"',
		'python-libinput;sys_platform=="linux"',
		'aenum;python_version<"3.6"',
		'monotonic;python_version<"3.3"'])
