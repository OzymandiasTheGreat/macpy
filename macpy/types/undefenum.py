#!/usr/bin/env python3

import sys
from collections import Sequence
if sys.version_info >= (3, 6):
	from enum import Enum
else:
	from aenum import Enum


class UndefEnum(Enum):

	@classmethod
	def _missing_(cls, value):

		if hasattr(cls, '__value_type__'):
			if not isinstance(value, cls.__value_type__):
				raise ValueError(
					'{0} is not a valid {1}'.format(value, cls.__name__))

		metacls = cls.__class__
		bases = cls.__mro__

		member_type = first_enum = None
		if bases == (UndefEnum, Enum, object):
			member_type = object
			first_enum = UndefEnum
		else:
			if not issubclass(bases[0], Enum):
				member_type = bases[0]
				first_enum = bases[-1]
			else:
				for base in bases[0].__mro__:
					if issubclass(base, Enum):
						if first_enum is None:
							first_enum = base
					else:
						if member_type is None:
							member_type = base

		__new__, save_new, use_args = metacls._find_new_(
			{}, member_type, first_enum)

		if not isinstance(value, tuple):
			args = (value, )
		else:
			args = value
		if member_type is tuple:
			args = (args, )
		if not use_args:
			undef_member = __new__(cls)
			if not hasattr(undef_member, '_value_'):
				undef_member._value_ = value
		else:
			undef_member = __new__(cls, *args)
			if not hasattr(undef_member, '_value_'):
				if member_type is object:
					undef_member._value_ = value
				else:
					undef_member._value_ = member_type(*args)
		undef_member._name_ = '_UNDEFINED_'
		undef_member.__objclass__ = cls
		undef_member.__init__(*args)

		return undef_member


def export(enum, namespace):

	for name, member in enum.__members__.items():
		namespace[name] = member
