#!/usr/bin/env python3

from __future__ import print_function
import traceback
from threading import Thread
try:
	from queue import Queue
except ImportError:
	from Queue import Queue
import time
from itertools import combinations
from collections import deque
from Xlib import display, X
from Xlib.ext import record, xtest
from Xlib.protocol import rq
from .xhelper import XTranslate
from ..key import Key, KeyState, Modifiers
from ..constant.xmap import PRINT
from ..event import KeyboardEvent, HotKey, HotString


class XKeyboard(object):

	def __init__(self):

		self.display = display.Display()
		self.root = self.display.screen().root
		self.translate = XTranslate()
		self.translate.install_layout_hook()
		self.queue = Queue()
		self.mainloop = Thread(target=self._mainloop, name='XKeyboard mainloop')
		self.mainloop.start()
		self.hook = None
		self.hook_grab = False
		self.hotkeys = None
		self.input = deque(maxlen=128)
		self.hotstrings = {}

	def _mainloop(self):

		while True:
			method, args = self.queue.get()
			if method is None:
				break
			try:
				method(*args)
			except Exception as e:
				print('Error in XKeyboard mainloop: \n',
					''.join(traceback.format_exception(
						type(e), e, e.__traceback__)))
			self.queue.task_done()

	def enqueue(self, method, *args):

		self.queue.put_nowait((method, args))

	def close(self):

		self.enqueue(None)
		self.translate.close()
		if self.hook and self.hook.is_alive():
			self.uninstall_keyboard_hook()
		if self.hotkeys and self.hotkeys.is_alive():
			self.uninit_hotkeys()

	def get_key_state(self, key):

		def parse_bitmask(mask):

			bits = []
			for i in range(8):
				bits.append(bool(mask & (1 << i)))
			return bits

		keymap = self.display.query_keymap()
		state = [bit for mask in keymap for bit in parse_bitmask(mask)]
		return KeyState(bool(state[key.ec + self.translate.min_keycode]))

	def install_keyboard_hook(self, callback, grab=False):

		self.hook_callback = callback
		self.hook_display = display.Display()
		self.hook_ctx = self.hook_display.record_create_context(
			0,
			[record.AllClients],
			[{
				'core_requests': (0, 0),
				'core_replies': (0, 0),
				'ext_requests': (0, 0, 0, 0),
				'ext_replies': (0, 0, 0, 0),
				'delivered_events': (0, 0),
				'device_events': (X.KeyPress, X.KeyRelease),
				'errors': (0, 0),
				'client_started': False,
				'client_died': False,
			}])
		self.hook = Thread(target=self._hook, name='XKeyboard hook loop')
		self.hook_grab = grab
		self.hook.start()

	def uninstall_keyboard_hook(self):

		if self.hook and self.hook.is_alive():
			if self.hook_grab:
				self.display.ungrab_keyboard(X.CurrentTime)
				self.hook_grab = False
			self.display.record_disable_context(self.hook_ctx)
			self.display.flush()
			self.hook_display.record_free_context(self.hook_ctx)
			self.hook_display.close()

	def _hook(self):

		try:
			if self.hook_grab:
				self.root.grab_keyboard(
					True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime)
			self.hook_display.record_enable_context(
				self.hook_ctx, self.process_event)
		except TypeError:
			# Supress error thrown when disabling record context
			# Record runs for a moment after disbling context but it receives
			# no data and thus throws an error
			pass

	def process_event(self, event):

		if event.category != record.FromServer:
			return
		if event.client_swapped:
			return
		if not len(event.data) or event.data[0] < 2:
			return

		data = event.data
		while len(data):
			event, data = rq.EventField(None).parse_binary_value(
				data, self.hook_display.display, None, None)

			if event.type in {X.KeyPress, X.KeyRelease}:
				keystate = (KeyState.PRESSED if event.type == X.KeyPress
					else KeyState.RELEASED)
				keysym, mods, locks = self.translate.keycode_to_keysym(
					event.detail, event.state)
				char = None
				if (keysym in PRINT
						and not any(mods[mod] for mod in mods
							if mod not in {'SHIFT', 'ALTGR'})):
					char = PRINT[keysym]
				key = Key.from_ec(event.detail - self.translate.min_keycode)
				self.enqueue(self.hook_callback, KeyboardEvent(
					key, keystate, char, mods, locks))
				# Using KeyPress for this eats some release events
				if event.type == X.KeyRelease and self.hotstrings and char:
					self.input.append(char)
					string = ''.join(self.input)
					for hotstring in self.hotstrings:
						if (string.endswith(hotstring.string)
								and not hotstring.triggers):
							retstring = HotString(
								hotstring.string, hotstring.triggers)
							self.enqueue(self.hotstrings[hotstring], retstring)
							self.input.clear()
						elif (string[:-1].endswith(hotstring.string)
								and string[-1] in hotstring.triggers):
							retstring = HotString(
								hotstring.string, hotstring.triggers, string[-1])
							self.enqueue(self.hotstrings[hotstring], retstring)
							self.input.clear()

	def init_hotkeys(self):

		self.hotkeys = Thread(target=self._hotkeys, name='XKeyboard hotkey loop')
		self.hk_display = display.Display()
		self.hk_root = self.hk_display.screen().root
		self.hk_root.change_attributes(event_mask=X.KeyPressMask)
		self.hk_callbacks = {}
		self.hk_stop = False
		self.hotkeys.start()

	def uninit_hotkeys(self):

		for hotkey in self.hk_callbacks:
			self.unregister_hotkey(hotkey)
		self.hk_stop = True

	def _hotkeys(self):

		while not self.hk_stop:
			for nevent in range(self.hk_display.pending_events()):
				event = self.hk_display.next_event()
				if event.type == X.KeyPress:
					keysym, mods, locks = self.translate.keycode_to_keysym(
						event.detail, event.state)
					key = Key.from_ec(event.detail - self.translate.min_keycode)
					modifiers = []
					for mod, state in mods.items():
						if state:
							try:
								modifiers.append(getattr(Modifiers, mod)[0])
							except AttributeError:
								pass  # ALTGR is only defined under X so we
									  # noqa ignore it here for consistency
					hotkey = HotKey(key, modifiers)
					if hotkey in self.hk_callbacks:
						self.enqueue(self.hk_callbacks[hotkey], hotkey)
			time.sleep(0.3)

	def _register_hotkey(self, hotkey, callback):

		modmask = 0
		for mod in hotkey.modifiers:
			for Mod in Modifiers:
				if mod in Mod:
					modmask |= self.translate.modmask[Mod.name]
		seen_masks = set()
		for length in range(4):
			for masks in combinations(self.translate.lockmask.values(), length):
				if sum(masks) not in seen_masks:
					state = 0
					for mask in masks:
						state |= mask
					self.hk_root.grab_key(
						hotkey.key.ec + self.translate.min_keycode,
						modmask | state,
						1, X.GrabModeAsync, X.GrabModeAsync)
					seen_masks.add(sum(masks))
		self.hk_callbacks[hotkey] = callback
		self.hk_display.flush()

	def register_hotkey(self, key, modifiers, callback):

		mods = set()
		for mod in modifiers:
			for Mod in Modifiers:
				if mod in Mod:
					mods.add(Mod[0])
		hotkey = HotKey(key, mods)
		self.enqueue(self._register_hotkey, hotkey, callback)
		return hotkey

	def _unregister_hotkey(self, hotkey):

		modmask = 0
		for mod in hotkey.modifiers:
			for Mod in Modifiers:
				if mod in Mod:
					modmask |= self.translate.modmask[Mod.name]
		seen_masks = set()
		for length in range(4):
			for masks in combinations(self.translate.lockmask.values(), length):
				if sum(masks) not in seen_masks:
					state = 0
					for mask in masks:
						state |= mask
					self.hk_root.ungrab_key(
						hotkey.key.ec + self.translate.min_keycode,
						modmask | state)
					seen_masks.add(sum(masks))
		if hotkey in self.hk_callbacks:
			del self.hk_callbacks[hotkey]
		self.hk_display.flush()

	def unregister_hotkey(self, hotkey):

		self.enqueue(self._unregister_hotkey, hotkey)

	def register_hotstring(self, string, triggers, callback):

		if self.hook and self.hook.is_alive():
			hotstring = HotString(string, triggers)
			self.hotstrings[hotstring] = callback
			return hotstring
		else:
			raise RuntimeError('Keyboard hook not installed')

	def unregister_hotstring(self, hotstring):

		if hotstring in self.hotstrings:
			del self.hotstrings[hotstring]

	def _press_key(self, keycode):

		xtest.fake_input(self.display, X.KeyPress, keycode)

	def _release_key(self, keycode):

		xtest.fake_input(self.display, X.KeyRelease, keycode)

	def keypress(self, key, state=None):

		keycode = key.ec + self.translate.min_keycode
		if self.hook_grab:
			self.enqueue(self.display.ungrab_keyboard, X.CurrentTime)
		if state is None:
			self.enqueue(self._press_key, keycode)
			self.enqueue(self._release_key, keycode)
		elif state == KeyState.PRESSED:
			self.enqueue(self._press_key, keycode)
		elif state == KeyState.RELEASED:
			self.enqueue(self._release_key, keycode)
		else:
			raise TypeError('Invalid state')
		if self.hook_grab:
			self.enqueue(
				self.root.grab_keyboard,
				True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime)
		self.enqueue(self.display.flush)

	def _type(self, string):

		if self.hook_grab:
			self.display.ungrab_keyboard(X.CurrentTime)
		for char in string:
			keysym = self.translate.lookup_keysym(char)
			keycode, mods, locks = self.translate.keysym_to_keycode(keysym)
			if any(mods):
				for mod, state in mods.items():
					if state:
						modcode = (
							getattr(Modifiers, mod)[0].ec
							+ self.translate.min_keycode)
						self._press_key(modcode)
			self._press_key(keycode)
			self._release_key(keycode)
			if any(mods):
				for mod, state in mods.items():
					if state:
						modcode = (
							getattr(Modifiers, mod)[0].ec
							+ self.translate.min_keycode)
						self._release_key(modcode)
		self.display.flush()
		if self.hook_grab:
			self.root.grab_keyboard(
				True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime)

	def type(self, string):

		self.enqueue(self._type, string)
