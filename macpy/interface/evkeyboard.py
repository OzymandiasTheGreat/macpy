#!/usr/bin/env python3

from __future__ import print_function
import traceback
from threading import Thread
try:
	from queue import Queue
except ImportError:
	from Queue import Queue
from selectors import DefaultSelector, EVENT_READ
from collections import deque
from evdev import ecodes, InputDevice, list_devices, categorize, UInput
from evdev.events import KeyEvent
from .xhelper import XTranslate
from ..key import Key, KeyState, Modifiers
from ..constant.xmap import PRINT
from ..event import KeyboardEvent, HotKey, HotString


class EvKeyboard(object):

	def __init__(self):

		self.translate = XTranslate()
		self.translate.install_layout_hook()
		self.keyboards = self.detect_keyboards()
		# ~ self.device = UInput.from_device(*self.keyboards, name='macpy keyboard')
		self.device = UInput(name='macpy keyboard')
		self.queue = Queue()
		self.mainloop = Thread(target=self._mainloop, name='EvKeyboard mainloop')
		self.mainloop.start()
		self.selector = DefaultSelector()
		self.events = Thread(target=self._events, name='EvKeyboard event loop')
		self.stop = False
		self.hook = False
		self.hook_callback = None
		self.hotkeys = False
		self.hk_callbacks = {}
		self.input = deque(maxlen=128)
		self.hotstrings = {}

	def detect_keyboards(self):

		keyboards = []
		for device in list_devices():
			input_device = InputDevice(device)
			if ecodes.EV_KEY in input_device.capabilities():
				keyboards.append(input_device)
		return tuple(keyboards)

	def _mainloop(self):

		while True:
			method, args = self.queue.get()
			if method is None:
				break
			try:
				method(*args)
			except Exception as e:
				print('Error in EvKeyboard mainloop: \n',
					''.join(traceback.format_exception(
						type(e), e, e.__traceback__)))
			self.queue.task_done()

	def enqueue(self, method, *args):

		self.queue.put_nowait((method, args))

	def close(self):

		self.device.close()
		self.enqueue(None)
		self.translate.close()
		self.stop = True

	def get_key_state(self, key):

		keycodes = [keycode for keyboard in self.keyboards
			for keycode in keyboard.active_keys()]
		if key.ec.value in keycodes:
			return KeyState(True)
		else:
			return KeyState(False)

	def _events(self):

		for keyboard in self.keyboards:
			self.selector.register(keyboard, EVENT_READ)
		while not self.stop:
			for key, mask in self.selector.select(timeout=0.3):
				device = key.fileobj
				for event in device.read():
					event = categorize(event)
					if isinstance(event, KeyEvent):
						if event.keystate < 2:
							key = Key.from_ec(event.event.code)
							keystate = (KeyState.PRESSED if event.keystate == 1
								else KeyState.RELEASED)
							mask = 0
							leds = [led for keyboard in self.keyboards
								for led in keyboard.leds()]
							if ecodes.LED_NUML in leds:
								mask |= self.translate.lockmask['NUMLOCK']
							if ecodes.LED_CAPSL in leds:
								mask |= self.translate.lockmask['CAPSLOCK']
							if ecodes.LED_SCROLLL in leds:
								mask |= self.translate.lockmask['SCROLLLOCK']
							keycodes = [keycode for keyboard in self.keyboards
								for keycode in keyboard.active_keys()]
							for keycode in keycodes:
								for mod, codes in self.translate.modmap.items():
									if ((keycode + self.translate.min_keycode)
											in codes):
										mask |= self.translate.modmask[mod]
							if self.translate.modmap['ALTGR'][0] in keycodes:
								mask |= self.translate.modmask['ALTGR']
							keysym, mods, locks = self.translate. \
								keycode_to_keysym(
									key.ec + self.translate.min_keycode, mask)
							char = None
							if keysym in PRINT:
								char = PRINT[keysym]
							if self.hook:
								self.enqueue(self.hook_callback, KeyboardEvent(
									key, keystate, char, mods, locks))
							if self.hotkeys and event.keystate == 1:
								modifiers = set()
								for mod, state in mods.items():
									if state:
										modifiers.add(
											getattr(Modifiers, mod)[0])
								hotkey = HotKey(key, modifiers)
								if hotkey in self.hk_callbacks:
									self.enqueue(
										self.hk_callbacks[hotkey], hotkey)
							if self.hotstrings and event.keystate == 0 and char:
								self.input.append(char)
								string = ''.join(self.input)
								for hotstring in self.hotstrings:
									if (string.endswith(hotstring.string)
											and not hotstring.triggers):
										retstring = HotString(
											hotstring.string,
											hotstring.triggers)
										self.enqueue(
											self.hotstrings[hotstring],
											retstring)
										self.input.clear()
									elif (string[:-1].endswith(hotstring.string)
											and string[-1] in hotstring.triggers):
										retstring = HotString(
											hotstring.string,
											hotstring.triggers,
											string[-1])
										self.enqueue(
											self.hotstrings[hotstring],
											retstring)
										self.input.clear()

	def install_keyboard_hook(self, callback, grab=False):

		if not self.events.is_alive():
			self.events.start()
		self.hook = True
		self.hook_callback = callback

	def uninstall_keyboard_hook(self):

		self.hook = False

	def init_hotkeys(self):

		if not self.events.is_alive():
			self.events.start()
		self.hotkeys = True

	def uninit_hotkeys(self):

		self.hotkeys = False
		self.hk_callbacks = {}

	def register_hotkey(self, key, modifiers, callback):

		mods = set()
		for mod in modifiers:
			for Mod in Modifiers:
				if mod in Mod:
					mods.add(Mod[0])
		hotkey = HotKey(key, mods)
		self.hk_callbacks[hotkey] = callback
		return hotkey

	def unregister_hotkey(self, hotkey):

		if hotkey in self.hk_callbacks:
			del self.hk_callbacks[hotkey]

	def register_hotstring(self, string, triggers, callback):

		if self.hook:
			hotstring = HotString(string, triggers)
			self.hotstrings[hotstring] = callback
			return hotstring
		else:
			raise RuntimeError('Keyboard hook not installed')

	def unregister_hotstring(self, hotstring):

		if hotstring in self.hotstrings:
			del self.hotstrings[hotstring]

	def _press_key(self, key):

		self.device.write(ecodes.EV_KEY, key.ec, 1)

	def _release_key(self, key):

		self.device.write(ecodes.EV_KEY, key.ec, 0)

	def keypress(self, key, state=None):

		if state is None:
			self.enqueue(self._press_key, key)
			self.enqueue(self._release_key, key)
		elif state == KeyState.PRESSED:
			self.enqueue(self._press_key, key)
		elif state == KeyState.RELEASED:
			self.enqueue(self._release_key, key)
		else:
			raise TypeError('Invalid state')
		self.enqueue(self.device.syn)

	def _type(self, string):

		for char in string:
			keysym = self.translate.lookup_keysym(char)
			keycode, mods, locks = self.translate.keysym_to_keycode(keysym)
			key = Key.from_ec(keycode - self.translate.min_keycode)
			if any(mods):
				for mod, state in mods.items():
					if state:
						modifier = getattr(Modifiers, mod, None)
						if modifier:
							self._press_key(modifier[0])
			self._press_key(key)
			self._release_key(key)
			if any(mods):
				for mod, state in mods.items():
					if state:
						modifier = getattr(Modifiers, mod, None)
						if modifier:
							self._release_key(modifier[0])
			self.device.syn()

	def type(self, string):

		self.enqueue(self._type, string)
