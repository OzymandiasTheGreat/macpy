#!/usr/bin/env python3

from __future__ import print_function
try:
	from queue import Queue
except ImportError:
	from Queue import Queue
from threading import Thread
import traceback
from Xlib import display, X
from Xlib.ext import record, xtest
from Xlib.protocol import rq, event
from .xhelper import XTranslate
from ..key import Key, KeyState
from ..event import PointerAxis
from ..event import PointerEventMotion, PointerEventButton, PointerEventAxis
from ..types.tuples import MousePos, Modifiers


class XPointer(object):

	def __init__(self):

		self.translate = XTranslate()
		self.display = display.Display()
		self.root = self.display.screen().root

		self.buttonmap = {
			1: Key.BTN_LEFT,
			2: Key.BTN_MIDDLE,
			3: Key.BTN_RIGHT,
			8: Key.BTN_SIDE,
			9: Key.BTN_EXTRA}
		self.rebuttonmap = {
			Key.BTN_LEFT: 1,
			Key.BTN_MOUSE: 1,
			Key.BTN_MIDDLE: 2,
			Key.BTN_RIGHT: 3,
			Key.BTN_SIDE: 8,
			Key.BTN_EXTRA: 9}

		self.queue = Queue()
		self.mainloop = Thread(target=self._mainloop, name='XPointer mainloop')
		self.mainloop.start()
		self.hook = None

	def _mainloop(self):

		while True:
			method, args = self.queue.get()
			if method is None:
				break
			try:
				method(*args)
			except Exception as e:
				print(
					'Error in XPointer mainloop: \n',
					''.join(traceback.format_exception(
						type(e), e, e.__traceback__)))
			self.queue.task_done()

	def enqueue(self, method, *args):

		self.queue.put_nowait((method, args))

	def install_pointer_hook(self, callback):

		self.hook = Thread(target=self._hook, name='XPointer hook loop')
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
				'device_events': (X.ButtonPress, X.MotionNotify),
				'errors': (0, 0),
				'client_started': False,
				'client_died': False,
			}])
		self.hook.start()

	def uninstall_pointer_hook(self):

		if self.hook and self.hook.is_alive():
			self.display.record_disable_context(self.hook_ctx)
			self.display.flush()
			self.hook_display.record_free_context(self.hook_ctx)
			self.hook_display.close()

	def _hook(self):

		try:
			self.hook_display.record_enable_context(
				self.hook_ctx, self.process_events)
		except TypeError:
			# Supress error thrown when disabling record context
			# Record runs for a moment after disbling context but it receives
			# no data and thus throws an error
			pass

	def process_events(self, event):

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
			mods = {
				'SHIFT': False,
				'ALTGR': False,
				'CTRL': False,
				'ALT': False,
				'META': False}
			if event.state & self.translate.modmask['SHIFT']:
				mods['SHIFT'] = True
			if event.state & self.translate.modmask['ALTGR']:
				mods['ALTGR'] = True
			if event.state & self.translate.modmask['CTRL']:
				mods['CTRL'] = True
			if event.state & self.translate.modmask['ALT']:
				mods['ALT'] = True
			if event.state & self.translate.modmask['META']:
				mods['META'] = True
			if event.type == X.MotionNotify:
				self.enqueue(self.hook_callback, PointerEventMotion(
					MousePos(event.root_x, event.root_y), Modifiers(**mods)))
			elif event.type in {X.ButtonPress, X.ButtonRelease}:
				button = event.detail
				state = (KeyState.PRESSED if event.type == X.ButtonPress
					else KeyState.RELEASED)
				if button in {1, 2, 3, 8, 9}:
					self.enqueue(self.hook_callback, PointerEventButton(
						self.buttonmap[button], state, Modifiers(**mods)))
				elif button in {4, 5, 6, 7}:
					axis = (PointerAxis.VERTICAL if button in {4, 5}
						else PointerAxis.HORIZONTAL)
					if button in {4, 6}:
						value = -1
					else:
						value = 1
					self.enqueue(self.hook_callback, PointerEventAxis(
						value, axis, Modifiers(**mods)))

	def close(self):

		if self.hook and self.hook.is_alive():
			self.uninstall_pointer_hook()
		self.enqueue(None)

	def _warp(self, x, y):

		xtest.fake_input(self.display, X.MotionNotify, x=x, y=y)
		self.display.flush()

	def warp(self, x, y):

		self.enqueue(self._warp, x, y)

	def _scroll(self, axis, value):

		if axis is PointerAxis.VERTICAL:
			if value < 0:
				button = 4
			else:
				button = 5
		elif axis is PointerAxis.HORIZONTAL:
			if value < 0:
				button = 6
			else:
				button = 7
		else:
			raise TypeError('Invalid axis type')
		for i in range(abs(value)):
			xtest.fake_input(self.display, X.ButtonPress, button)
			xtest.fake_input(self.display, X.ButtonRelease, button)
			self.display.flush()

	def scroll(self, axis, value):

		self.enqueue(self._scroll, axis, value)

	def _click(self, key, state=None):

		if state is None:
			xtest.fake_input(
				self.display, X.ButtonPress, self.rebuttonmap[key])
			xtest.fake_input(
				self.display, X.ButtonRelease, self.rebuttonmap[key])
		elif state is KeyState.PRESSED:
			xtest.fake_input(
				self.display, X.ButtonPress, self.rebuttonmap[key])
		elif state is KeyState.RELEASED:
			xtest.fake_input(
				self.display, X.ButtonRelease, self.rebuttonmap[key])
		else:
			raise RuntimeError('Invalid state')
		self.display.flush()

	def click(self, key, state=None):

		self.enqueue(self._click, key, state)
