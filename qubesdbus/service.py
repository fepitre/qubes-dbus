#!/usr/bin/env python2
# -*- encoding: utf8 -*-
#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# pylint: disable=missing-docstring,invalid-name

from __future__ import absolute_import

import dbus
import dbus.mainloop.glib

from .constants import NAME_PREFIX, PATH_PREFIX, VERSION

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


class _DbusServiceObject(dbus.service.Object):
    def __init__(self):
        self.bus_path = ''.join([PATH_PREFIX, '/', self.__class__.__name__,
                                 str(VERSION)])
        bus_name = ''.join([NAME_PREFIX, '.', self.__class__.__name__,
                            str(VERSION)])
        self.bus = dbus.SessionBus()
        self.bus_name = dbus.service.BusName(bus_name, self.bus)
        # avoid pylint super-on-old-class error
        dbus.service.Object.__init__(self, self.bus_name, self.bus_path)
