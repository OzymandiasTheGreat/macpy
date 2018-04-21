#!/usr/bin/env python3

from collections import namedtuple


Screen = namedtuple('Screen', ('root', ))


class Display(object):

	def get_atom(self, string):

		return 0

	def close(self):

		pass

	def screen(self):

		return Screen(0)
