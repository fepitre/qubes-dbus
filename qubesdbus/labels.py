# -*- encoding: utf8 -*-
# pylint: disable=invalid-name
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
''' org.qubes.Labels1 service '''

from __future__ import absolute_import, print_function

import logging
import sys

import qubesadmin
from gi.repository import GLib
from systemd.journal import JournalHandler

import qubesdbus.serialize
from qubesdbus.service import (DbusServiceObject, ObjectManager,
                               PropertiesObject)

log = logging.getLogger('org.qubes.Labels1')
log.addHandler(JournalHandler(SYSLOG_IDENTIFIER='qubesdbus.labels'))
log.setLevel(logging.INFO)


class Labels(ObjectManager):
    ''' A `org.freedesktop.DBus.ObjectManager` interface implementation, for
	acquiring all the labels.
    '''

    def __init__(self, labels_data):
        super(Labels, self).__init__()
        self.managed_objects = [self._new_label(d) for d in labels_data]

    def _new_label(self, label_data):
        return Label(self.bus, self.bus_name, self.bus_path, label_data)


class Label(PropertiesObject):
    ''' Represents a qubes label. Its D-Bus object path is
	`org/qubes/Labels1/labels/COLORNAME`
    '''

    def __init__(self, bus, bus_name, bus_path, data):
        bus_path = '/'.join([bus_path, 'labels', data['name']])
        name = data['name']
        super(Label, self).__init__(name, 'org.qubes.Label1', data, bus=bus,
                                    bus_name=bus_name, bus_path=bus_path)


def main(args=None):
    ''' Main function '''  # pylint: disable=unused-argument
    loop = GLib.MainLoop()
    app = qubesadmin.Qubes()

    labels_data = [qubesdbus.serialize.label_data(label)
                   for label in app.labels]
    _ = Labels(labels_data)
    print("Service running...")
    loop.run()
    print("Service stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
