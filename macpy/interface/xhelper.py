#!/usr/bin/env python3

from subprocess import check_output
from threading import Thread, Condition
try:
	from queue import Queue
except ImportError:
	from Queue import Queue
import re
import os.path
import sys
import time
from ast import literal_eval
from ctypes import CDLL, c_char_p
from Xlib import display, X
from Xlib.error import BadValue
from ..platform import PLATFORM, Platform, ARCH, Arch
from ..constant import XK
from ..constant.xmap import PRINT, KEYPAD, NOIDX, NAME


class XTranslate(object):

	def __init__(self):

		self.display = display.Display()
		self.map_keys()
		self.map_mods()
		self.reprint = {char: sym for sym, char in PRINT.items()}
		self.layout = None

	def map_keys(self):

		self.min_keycode = getattr(self, 'min_keycode', 0)
		self.max_keycode = getattr(self, 'max_keycode', 255)
		while True:
			try:
				keymap = self.display.get_keyboard_mapping(
					self.min_keycode, self.max_keycode)
				break
			except BadValue:
				self.min_keycode += 1
				self.max_keycode -= 1
		self.keymap = tuple(tuple(keysyms) for keysyms in keymap)

	def list_keysyms(self, keycode):

		keycode -= self.min_keycode
		try:
			return self.keymap[keycode]
		except IndexError:
			return (0, )

	def map_mods(self):

		xmodmap = self.display.get_modifier_mapping()
		modmask = {
			'SHIFT': X.ShiftMask,
			'ALTGR': 0,
			'CTRL': X.ControlMask,
			'ALT': 0,
			'META': 0}
		modmap = {name: (0, ) for name in modmask}
		lockmask = {
			'NUMLOCK': 0,
			'CAPSLOCK': X.LockMask,
			'SCROLLLOCK': 0}
		lockmap = {name: (0, ) for name in lockmask}
		indices = {
			X.ShiftMapIndex: X.ShiftMask,
			X.ControlMapIndex: X.ControlMask,
			X.LockMapIndex: X.LockMask,
			X.Mod1MapIndex: X.Mod1Mask,
			X.Mod2MapIndex: X.Mod2Mask,
			X.Mod3MapIndex: X.Mod3Mask,
			X.Mod4MapIndex: X.Mod4Mask,
			X.Mod5MapIndex: X.Mod5Mask}
		ALTGR = None
		if PLATFORM == Platform.WAYLAND:
			output = check_output(['xmodmap', '-pke'], universal_newlines=True)
			for line in output.splitlines():
				line = line.split()
				if len(line) > 3:
					if line[3] == 'ISO_Level3_Shift':
						ALTGR = int(line[1])
		for index, mask in indices.items():
			keysyms = [keysym for list_ in
				(self.list_keysyms(keycode) for keycode in xmodmap[index])
					for keysym in list_ if keysym]
			keycodes = tuple(keycode for keycode in xmodmap[index] if keycode)
			if NAME['SHIFT'] in keysyms:
				modmap['SHIFT'] = keycodes
			if NAME['ALTGR'] in keysyms:
				modmask['ALTGR'] = mask
				if ALTGR:
					modmap['ALTGR'] = (ALTGR, ) + keycodes
				else:
					modmap['ALTGR'] = keycodes
			if NAME['CTRL'] in keysyms:
				modmap['CTRL'] = keycodes
			if NAME['ALT'] in keysyms:
				modmask['ALT'] = mask
				if ALTGR:
					modmap['ALT'] = tuple(kc for kc in keycodes if kc != ALTGR)
				else:
					modmap['ALT'] = keycodes
			if NAME['META'] in keysyms:
				modmask['META'] = mask
				modmap['META'] = keycodes
			if NAME['NUMLOCK'] in keysyms:
				lockmask['NUMLOCK'] = mask
				lockmap['NUMLOCK'] = keycodes
			if NAME['CAPSLOCK'] in keysyms:
				lockmap['CAPSLOCK'] = keycodes
			if NAME['SCROLLLOCK'] in keysyms:
				lockmask['SCROLLLOCK'] = mask
				lockmap['SCROLLLOCK'] = keycodes
		self.modmap = modmap
		self.modmask = modmask
		self.lockmap = lockmap
		self.lockmask = lockmask

	def keycode_to_keysym(self, keycode, state):

		index, mods, locks = self.translate_state(state, keycode)
		keysym = self.display.keycode_to_keysym(keycode, index)
		if keysym == XK.XK_Return:
			keysym = XK.XK_Linefeed
		return keysym, mods, locks

	def translate_state(self, state, keycode):

		index = 0
		mods = {mod: False for mod in self.modmask}
		locks = {lock: False for lock in self.lockmask}
		mods['SHIFT'] = bool(state & self.modmask['SHIFT'])
		mods['ALTGR'] = bool(state & self.modmask['ALTGR'])
		mods['CTRL'] = bool(state & self.modmask['CTRL'])
		mods['ALT'] = bool(state & self.modmask['ALT'])
		mods['META'] = bool(state & self.modmask['META'])
		locks['NUMLOCK'] = bool(state & self.lockmask['NUMLOCK'])
		locks['CAPSLOCK'] = bool(state & self.lockmask['CAPSLOCK'])
		locks['SCROLLLOCK'] = bool(state & self.lockmask['SCROLLLOCK'])
		keysym = self.list_keysyms(keycode)[0]
		if keysym in KEYPAD:
			if (mods['SHIFT'] ^ locks['CAPSLOCK']) ^ locks['NUMLOCK']:
				index += 1
		elif keysym in PRINT:
			if PRINT[keysym].isalpha():
				if mods['SHIFT'] ^ locks['CAPSLOCK']:
					index +=1
				if mods['ALTGR']:
					index += 4
			else:
				if mods['SHIFT']:
					index += 1
				if mods['ALTGR']:
					index += 4
		elif keysym not in NOIDX:
			if mods['SHIFT']:
				index += 1
			if mods['ALTGR']:
				index += 4
		else:
			index = 0
		return index, mods, locks

	def lookup_keysym(self, char):

		if char in self.reprint:
			return self.reprint[char]
		else:
			return None

	def keysym_to_keycode(self, keysym):

		keycode = self.display.keysym_to_keycode(keysym)
		mods = {mod: False for mod in self.modmask}
		locks = {lock: False for lock in self.lockmask}
		try:
			index = self.keymap[keycode - self.min_keycode].index(keysym)
		except ValueError:
			index = 0
		if index != 0 and index != 2:
			if index == 1:
				mods['SHIFT'] = True
			elif index == 4:
				mods['ALTGR'] = True
			elif index == 5:
				mods['SHIFT'] = True
				mods['ALTGR'] = True
		mods = mods
		locks = locks
		return keycode, mods, locks

	def install_layout_hook(self):

		self.layout_queue = Queue()
		self.layout = XLayout(self.layout_callback)
		self.layout.start()
		self.reloader = Thread(target=self._reloader, name='XTranslate reloader')
		self.reloader.start()

	def layout_callback(self, layout):

		self.layout_queue.put_nowait(layout)

	def _reloader(self):

		while True:
			layout = self.layout_queue.get()
			if layout is None:
				break
			self.reload_display(layout)

	def reload_display(self, layout):

		self.display.close()
		self.layout.set_x_layout(layout)
		self.display = display.Display()
		self.map_keys()
		self.map_mods()
		self.layout.restore_layouts(layout)
		with self.layout.monitor:
			self.layout.monitor.notify()

	def close(self):

		if self.layout:
			self.layout.close()
			self.layout_callback(None)


class XLayout(Thread):

	def __init__(self, callback):

		Thread.__init__(self, name='XLayout monitor')
		self.callback = callback
		if PLATFORM == Platform.X11:
			self.parse_xkbswitch = re.compile(
				r'(?P<group>\w+)(?:\((?P<variant>\w+)\))?')
			self.parse_xkbmap = re.compile(
				r'layout\:\s+(?P<layouts>[\w\,]+)\s*'
				+ r'(?:variant\:\s+(?P<variants>[\w\,]+)\s*)?',
				re.MULTILINE)
			self.xkbswitch = self.load_libxkbswitch()
			output = self.xkbswitch.Xkb_Switch_getXkbLayout()
			match = self.parse_xkbswitch.match(output.decode())
			variant = match.group('variant') if match.group('variant') else ''
			self.layout = (match.group('group'), variant)
		else:
			self.gsettings = [
				'gsettings', 'get', 'org.gnome.desktop.input-sources']
			self.layout = self.gsettings_get_layout()
		self.layouts = self.get_config_layouts()
		self.stop = False
		self.monitor = Condition()

	def load_libxkbswitch(self):

		if ARCH == Arch.X86_64:
			libxkbswitch = 'libxkbswitch.x86_64.so'
		else:
			libxkbswitch = 'libxkbswitch.x86.so'
		try:
			xkbswitch = CDLL(libxkbswitch)
		except OSError:
			try:
				xkbswitch = CDLL(os.path.join(
					os.path.dirname(__file__), '../libxkbswitch', libxkbswitch))
			except OSError:
				xkbswitch = CDLL(os.path.join(
					os.path.dirname(sys.executable),
					'libxkbswitch', libxkbswitch))
		xkbswitch.Xkb_Switch_setXkbLayout.argtypes = (c_char_p, )
		xkbswitch.Xkb_Switch_getXkbLayout.restype = c_char_p
		return xkbswitch

	def get_config_layouts(self):

		if PLATFORM == Platform.X11:
			output = check_output(
				['setxkbmap', '-query'], universal_newlines=True)
			match = self.parse_xkbmap.search(output)
			if match:
				layouts = match.group('layouts').split(',')
				variants = match.group('variants').split(',') if match.group('variants') else ["" for i in layouts]
				result = tuple(zip(layouts, variants))
			else:
				result = tuple()
		else:
			output = check_output(
				self.gsettings + ['sources'], universal_newlines=True)
			eval_output = literal_eval(output)
			result = tuple(tuple(lo.split('+')) if '+' in lo else (lo, '')
				for cfg, lo in eval_output)
		return result

	def run(self):

		prev_layout = None
		while not self.stop:
			if PLATFORM == Platform.X11:
				output = self.xkbswitch.Xkb_Switch_getXkbLayout()
				match = self.parse_xkbswitch.match(output.decode())
				group = match.group
				variant = group('variant') if group('variant') else ''
				self.layout = (group('group'), variant)
			else:
				self.layout = self.gsettings_get_layout()
			with self.monitor:
				if prev_layout:
					if self.layout != prev_layout:
						self.callback(self.layout)
						prev_layout = self.layout
						self.monitor.wait()
				else:
					prev_layout = self.layout
					if self.layout != self.layouts[0]:
						self.callback(self.layout)
						self.monitor.wait()
			time.sleep(0.3)

	def close(self):

		self.stop = True

	def gsettings_get_layout(self):

		output = check_output(
			self.gsettings + ['mru-sources'], universal_newlines=True)
		eval_output = literal_eval(output)
		layout = eval_output[0][1]
		return tuple(layout.split('+')) if '+' in layout else (layout, '')

	def set_x_layout(self, layout):

		check_output(['setxkbmap', '-layout', layout[0], '-variant', layout[1]])

	def restore_layouts(self, layout):

		layouts, variants = zip(*self.layouts)
		check_output(
			['setxkbmap', '-layout', ','.join(layouts),
			'-variant', ','.join(variants)])
		layout = '{0}({1})'.format(*layout)
		if PLATFORM == Platform.X11:
			self.xkbswitch.Xkb_Switch_setXkbLayout(layout.encode())
