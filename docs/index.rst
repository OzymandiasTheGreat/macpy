Introduction
------------

This package provides easy keyboard/pointer/window management macro creation
and GUI automation for python versions 2.7 and 3.4+.
Currently it works on Windows and Linux (both under X and with limited
functionallity under Wayland).
Among it's features are:

- Low level hooks for keyboard, pointer events
- A hook for window creation, destruction and focus change
- Support for registering hotkeys and hotstrings
- Simulating keyboard/pointer events
- Providing platform independent definition/mapping of keys/buttons
- Listing open windows
- Managing open windows
- And more!

.. Note::

   Window management functionallity is not available under Wayland.

   More, keyboard and pointer functions require root access under Wayland.


.. toctree::
   :maxdepth: 2
   :caption: Contents:


.. toctree::
   :maxdepth: 2
   :caption: API

   interfaces
   events
   enums
