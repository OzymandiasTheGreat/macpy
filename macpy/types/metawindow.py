#!/usr/bin/env python3

from weakref import WeakValueDictionary


class MetaWindow(type):

	instances = WeakValueDictionary()

	def __call__(cls, id_):

		if id_ not in cls.instances:
			window = cls.__new__(cls, id_)
			window.__init__(id_)
			cls.instances[id_] = window
		return cls.instances[id_]
