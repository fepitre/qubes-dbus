# -*- encoding: utf-8 -*-
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
''' org.qubes.DeviceManager1 Service '''
import asyncio
import logging
import os
import sys

import dbus.service
import systemd.journal

import qubesdbus.serialize
import qubesdbus.service

log = logging.getLogger('qubesdbus.DomainManager1')
log.addHandler(
    systemd.journal.JournalHandler(
        level=logging.DEBUG, SYSLOG_IDENTIFIER='qubesdbus.domain_manager'))
log.propagate = True

SERVICE_NAME = "org.qubes.Devices1"
SERVICE_PATH = "/org/qubes/Devices1"
DEV_TYPES = ['block', 'pci', 'usb']  # Add 'mic' when it's implemented
DEV_IFACE = 'org.qubes.Device'

DBusSignalMatch = dbus.connection.SignalMatch


class DeviceManager(qubesdbus.service.ObjectManager):
    def __init__(self) -> None:
        super().__init__(SERVICE_NAME, SERVICE_PATH)
        self.devices = {}  # type: Dict[str, Device]

        for vm in self.app.domains:
            for dev_class in DEV_TYPES:
                for dev_info in vm.devices[dev_class].available():
                    obj_path, device = self._device(vm, dev_class, dev_info)
                    self.devices[obj_path] = device

        for vm in self.app.domains:
            for dev_class in DEV_TYPES:
                for assignment in vm.devices[dev_class].attached():
                    try:
                        obj_path, frontend_vm_path = self._frontend_domain(
                            vm, assignment, dev_class)
                        self.devices[obj_path].properties[
                            'frontend_domain'] = dbus.ObjectPath(
                                frontend_vm_path)
                        if assignment.options:
                            self.devices[obj_path].properties[
                                'attach_options'] = assignment.options
                    except TypeError:
                        continue

        for dev_class in DEV_TYPES:
            self.events_dispatcher.add_handler(
                'device-list-change:%s' % dev_class, self._device_changes)
            self.events_dispatcher.add_handler('device-attach:%s' % dev_class,
                                               self._device_attached)
            self.events_dispatcher.add_handler('device-detach:%s' % dev_class,
                                               self._device_detached)

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.ObjectManager",
                         out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        ''' Returns the domain objects paths and their supported interfaces and
            properties.
        '''  # pylint: disable=protected-access
        return {
            o._object_path: o.properties_iface()
            for o in self.devices.values()
        }

    def _device_changes(self, vm, event, **_):
        ''' Event handler for 'device-list-changes:DEV_CLASS' '''
        dev_class = event.split(':', 1)[1]
        paths = []
        for dev_info in vm.devices[dev_class].available():
            obj_path = device_path(vm, dev_class, dev_info.ident)
            paths.append(obj_path)

        vm_path_prefix = os.path.join(SERVICE_PATH, dev_class, str(vm.qid))
        known_devices = [
            p for p in self.devices if p.startswith(vm_path_prefix)
        ]

        # remove non existent devices
        for obj_path in known_devices:
            if obj_path not in paths:
                self.Removed(obj_path)
                self.devices[obj_path].remove_from_connection()
                del self.devices[obj_path]

        # add & update all other devices
        for dev_info in vm.devices[dev_class].available():
            obj_path = device_path(vm, dev_class, dev_info.ident)
            try:  # update an existing device
                original_dev = self.devices[obj_path]
                for key, value in original_dev.properties.items():
                    if original_dev.properties[key] != value:
                        original_dev.Set(None, key, value)
            except KeyError:  # add new device
                obj_path, device = self._device(vm, dev_class, dev_info)
                self.devices[obj_path] = device
                self.Added(obj_path)

        # figure out frontend_domains
        for domains in self.app.domains:
            for assignment in domains.devices[dev_class].assignments():
                if assignment.backend_domain != vm:
                    continue
                try:
                    obj_path, frontend_vm_path = self._frontend_domain(
                        vm, assignment, dev_class)
                    self.devices[obj_path].Set(
                        None, 'frontend_domain',
                        dbus.ObjectPath(frontend_vm_path))
                    self.devices[obj_path].properties[
                        'attach_options'] = assignment.options
                except TypeError:
                    continue

    def _device(self, vm, dev_class, dev_info):
        data = qubesdbus.serialize.device_data(dev_info)
        data['dev_class'] = dev_class
        obj_path = device_path(vm, dev_class, data['ident'])
        device = Device(self.bus_name, obj_path, data)
        return (obj_path, device)

    def _device_attached(self, vm, event, device=None, options={}):
        if device is None:
            return
        dev_str = device
        device = None

        qid = str(vm.qid)
        vm_obj_path = os.path.join('/org/qubes/DeviceManager1/domains', qid)
        dev_class = event.split(':', 1)[1]
        device = self._find_device(dev_class, dev_str)

        changed_properties = []
        device.properties['frontend_domain'] = vm_obj_path
        device.properties['attach_options'] = options
        changed_properties = {
            'frontend_domain': vm_obj_path,
            'attach_options': options
        }
        invalidated_properties = []
        device.PropertiesChanged(DEV_IFACE, changed_properties,
                                 invalidated_properties)
        device.Attached(vm_obj_path)

    def _device_detached(self, vm, event, device=None):
        if device is None:
            return

        dev_str = device
        device = None

        qid = str(vm.qid)
        vm_obj_path = os.path.join('/org/qubes/DeviceManager1/domains', qid)
        dev_class = event.split(':', 1)[1]
        device = self._find_device(dev_class, dev_str)
        del device.properties['frontend_domain']
        del device.properties['attach_options']
        changed_properties = {}
        invalidated_properties = ['frontend_domain', 'attach_options']
        device.PropertiesChanged(DEV_IFACE, changed_properties,
                                 invalidated_properties)
        device.Detached(vm_obj_path)

    def _find_device(self, dev_class, dev_str):
        vm_name, ident = dev_str.split(':', 1)
        vm = self.app.domains[vm_name]
        obj_path = device_path(vm, dev_class, ident)
        return self.devices[obj_path]

    def _frontend_domain(self, vm, assignment, dev_class):
        backend_domain = assignment.backend_domain
        ident = assignment.ident
        obj_path = device_path(backend_domain, dev_class, ident)
        try:
            backend_obj_path = self.devices[obj_path].Get(
                None, 'backend_domain')
            frontend_obj_path = os.path.join(
                os.path.dirname(backend_obj_path), str(vm.qid))
            return (obj_path, frontend_obj_path)
        except KeyError:
            return None  # remove this when #1082 is fixed

    @dbus.service.signal(SERVICE_NAME, signature="o")
    def Removed(self, obj_path):
        ''' Emitted when a device is removed '''

    @dbus.service.signal(SERVICE_NAME, signature="o")
    def Added(self, obj_path):
        ''' Emitted when a device is added '''


class Device(qubesdbus.service.PropertiesObject):
    ''' A D-Bus proxy for a device '''

    def __init__(self, bus_name, obj_path, data):
        self.properties = data
        self.name = data['ident']
        super().__init__(bus_name, obj_path, DEV_IFACE, data)

    @dbus.service.signal(DEV_IFACE, signature="o")
    def Attached(self, vm_obj_path):
        # type: (dbus.ObjectPath) -> None
        ''' Signal emitted when the device is attached to a domain.'''

    @dbus.service.signal(DEV_IFACE, signature="o")
    def Detached(self, vm_obj_path):
        # type: (dbus.ObjectPath) -> None
        ''' Signal emitted when the device is detached from domain.'''


def device_path(vm, dev_class, ident):
    _id = ident.replace('.', '_')
    return os.path.join(SERVICE_PATH, dev_class, str(vm.qid), _id)


def main(args=None):  # pylint: disable=unused-argument
    ''' Main function starting the DomainManager1 service. '''
    manager = DeviceManager()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(manager.run())
    loop.stop()
    loop.run_forever()
    loop.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
