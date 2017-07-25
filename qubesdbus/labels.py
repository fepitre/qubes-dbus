# -*- encoding: utf-8 -*-
# pylint: disable=invalid-name
#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
#
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

import asyncio
import logging
import sys

import dbus
from systemd.journal import JournalHandler

import qubesadmin.label
import qubesdbus.models
import qubesdbus.serialize
from qubesdbus.service import ObjectManager

SERVICE_NAME = "org.qubes.Labels1"
SERVICE_PATH = "/org/qubes/Labels1"

log = logging.getLogger(SERVICE_NAME)
log.addHandler(JournalHandler(SYSLOG_IDENTIFIER='qubesdbus.labels'))
log.setLevel(logging.INFO)


class Labels(ObjectManager):
    ''' A `org.freedesktop.DBus.ObjectManager` interface implementation, for
	acquiring all the labels.
    '''

    def __init__(self):
        super().__init__(SERVICE_NAME, SERVICE_PATH)

        self.managed_objects = []  # type: List[qubesdbus.models.Label]
        self.managed_object = [self._new_label(l) for l in self.app.labels]

    def _new_label(self,
                   label: qubesadmin.label.Label) -> qubesdbus.models.Label:
        data = {}  # type: Dict[str, Any]
        for name in ["color", "icon", "index", "name"]:
            value = getattr(label, name)
            if name == "index":
                data[name] = dbus.Int32(value)
            else:
                data[name] = dbus.String(value)
        return qubesdbus.models.Label(self.bus_name, SERVICE_PATH, data)


def main(args=None):
    ''' Main function '''  # pylint: disable=unused-argument
    manager = Labels()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(manager.run())
    loop.stop()
    loop.run_forever()
    loop.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
