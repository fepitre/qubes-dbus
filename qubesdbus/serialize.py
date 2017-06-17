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
''' Collection of serialization helpers '''

import re

import dbus
import qubesadmin
import qubesadmin.devices as devices
import qubesadmin.vm

try:
    # Check mypy dependencies. pylint: disable=ungrouped-imports,unused-import
    from typing import Any, Callable, Tuple, List, Dict
    from qubesadmin.vm import QubesVM
    from qubesadmin import Qubes
    from qubesadmin.label import Label
except ImportError:
    pass

DOMAIN_STATE_PROPERTIES = ['is_halted',
                           'is_paused',
                           'is_running',
                           'is_qrexec_running', ]


def qubes_data(app):
    ''' Serialize `qubes.Qubes` to a dictionary '''
    # type: (Qubes) -> Dict[dbus.String, Any]
    result = {}
    for prop in app.property_list():
        name = str(prop)
        key = dbus.String(name)
        try:
            result[key] = serialize_val(getattr(app, name))
        except AttributeError:
            result[key] = dbus.String('')

    return result


def serialize_state(state):
    state = state.lower()
    if state == 'crashed':
        return 'Failed'
    elif state in ['transient', 'na']:
        return 'Unknown'
    elif state == 'halted':
        return 'Halted'
    elif state == 'transient':
        return 'Starting'
    elif state == 'running':
        return 'Started'
    else:
        return '=>%s<=' % state

def domain_data(vm):
    ''' Serializes a `qubes.vm.qubesvm.QubesVM` to a dictionary '''
    # type: (QubesVM) -> Dict[dbus.String, Any]
    result = dbus.Dictionary({}, signature='sv')
    for prop in vm.property_list():
        name = str(prop)
        try:
            value = serialize_val(getattr(vm, name))
        except AttributeError:
            value = dbus.String('')
        result[name] = value

    # Additional data
    result['state'] = serialize_state(vm.get_power_state())
    result['networked'] = serialize_val(vm.is_networked())
    return result


def devices_data(app):
    result = []
    for vm in app.domains:
        for dev_class, dev_collection in vm.devices.items():
            result += serialize_val(dev_collection)
    return result


def label_data(lab):
    ''' Serialize a `qubes.Label` to a dictionary '''
    # type: (Label) -> Dict[dbus.String, Any]
    result = {}
    for name in dir(lab):
        if name.startswith('_') or callable(getattr(lab, name)):
            continue
        try:
            value = getattr(lab, name)
            result[name] = dbus.String(value)
        except AttributeError:
            result[name] = dbus.String('')
    return result


def serialize_val(value):
    ''' Serialize a property value '''
    # pylint: disable=too-many-return-statements
    if value is None:
        return dbus.String('')
    if isinstance(value, dict):
        return dbus.Dictionary(value, signature='sv')
    elif isinstance(value, bool):
        return dbus.Boolean(value)
    elif isinstance(value, int):
        return dbus.Int32(value)
    elif callable(value):
        return serialize_val(value())
    elif isinstance(value, qubesadmin.label.Label):
        return label_path(value)
    elif isinstance(value, qubesadmin.vm.QubesVM):
        return domain_path(value)
    elif isinstance(value, devices.DeviceCollection):
        return dbus.Array(device_collection_data(value), signature='a{sv}')
    elif isinstance(value, devices.DeviceInfo):
        return dbus.Dictionary(device_data(value), signature='sv')
    elif isinstance(value, re._pattern_type):
        return dbus.String(value.pattern)
    else:
        return dbus.String(value)


def device_collection_data(collection):
    return [device_data(dev) for dev in collection.available()]


def device_data(dev):
    return {serialize_val(prop): serialize_val(getattr(dev, prop))
            for prop in dir(dev) if not prop.startswith('_')}


def label_path(label):
    # type: (Label) -> dbus.ObjectPath
    ''' Return the D-Bus object path for a `qubes.Label` '''
    return dbus.ObjectPath('/org/qubes/Labels1/labels/' + label.name)


def domain_path(vm):
    ''' Return the D-Bus object path for a `qubes.vm.qubesvm.QubesVM` '''
    # type: (qubes.vm.qubesvm.QubesVM) -> dbus.ObjectPath
    return dbus.ObjectPath('/org/qubes/DomainManager1/domains/' + str(vm.qid))
