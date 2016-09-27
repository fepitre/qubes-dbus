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

import dbus
import qubes
import qubes.vm.qubesvm

from libvirt import libvirtError  # pylint: disable=import-error

try:
    # Check mypy dependencies. pylint: disable=ungrouped-imports,unused-import
    from typing import Any, Callable, Tuple, List, Dict
    from qubes.vm.qubesvm import QubesVM
    from qubes import Qubes, Label
except ImportError:
    pass

QUBES_PROPERTIES = ['clockvm', 'default_dispvm', 'default_fw_netvm',
                    'default_kernel', 'default_netvm', 'default_template',
                    'updatevm']

DOMAIN_PROPERTIES = ['attached_volumes',
                     'autostart',
                     'backup_timestamp',
                     # 'block_devices',
                     'conf_file',
                     # 'connected_vms',
                     'default_dispvm',
                     'default_user',
                     # 'devices',
                     'dir_path',
                     'dir_path_prefix',
                     'dns',
                     'features',
                     'firewall_conf',
                     'hvm',
                     'icon_path',
                     'include_in_backups',
                     'installed_by_rpm',
                     'internal',
                     'ip',
                     'is_networked',
                     'is_halted',
                     'is_paused',
                     'is_running',
                     'is_qrexec_running',
                     'is_outdated',
                     'kernel',
                     'kernelopts',
                     'label',
                     'mac',
                     'maxmem',
                     'memory',
                     'name',
                     'netmask',
                     'netvm',
                     'qid',
                     'qrexec_timeout',
                     # 'storage',
                     # 'tags',
                     'template',
                     'updateable',
                     'uuid',
                     'vcpus',
                     # 'volumes',
                     'xid', ]

DOMAIN_STATE_PROPERTIES = ['is_halted',
                           'is_paused',
                           'is_running',
                           'is_qrexec_running', ]


def qubes_data(app):
    ''' Serialize `qubes.Qubes` to a dictionary '''
    # type: (Qubes) -> Dict[dbus.String, Any]
    result = {}
    for name in QUBES_PROPERTIES:
        key = dbus.String(name)
        try:
            result[key] = dbus.String(getattr(app, name))
        except AttributeError:
            result[key] = dbus.String('')

    return result

def domain_data(vm):
    ''' Serializes a `qubes.vm.qubesvm.QubesVM` to a dictionary '''
    # type: (QubesVM) -> Dict[dbus.String, Any]
    result = dbus.Dictionary({'state': 'halted'}, signature='sv')
    for name in DOMAIN_PROPERTIES:
        if name in DOMAIN_STATE_PROPERTIES:
            key = 'state'
        elif name.startswith("is_"):
            _, key = name.split("_", 1)
        else:
            key = name

        key = dbus.String(key)
        try:
            tmp = getattr(vm, name)
            if tmp is None:
                value = dbus.String('')
            if isinstance(tmp, qubes.vm.qubesvm.QubesVM):
                value = serialize_val(str(tmp))
            else:
                value = serialize_val(tmp)

            result[key] = value
        except (AttributeError, libvirtError):
            result[key] = dbus.String('')
    return result


def label_data(lab):
    # type: (Label) -> Dict[dbus.String, Any]
    result = {}
    for name in dir(lab):
        if name.startswith('_') or callable(getattr(lab, name)):
            continue
        try:
            value = getattr(lab, name)
            result[name] = dbus.String(value)
        except AttributeError:
            result[name] = ''
    return result


def serialize_val(value):
    # pylint: disable=too-many-return-statements
    if isinstance(value, dict):
        return dbus.Dictionary(value, signature='sv')
    elif isinstance(value, bool):
        return dbus.Boolean(value)
    elif isinstance(value, int):
        return dbus.Int32(value)
    elif callable(value):
        return serialize_val(value())
    elif isinstance(value, qubes.Label):
        return label_path(value)
    elif isinstance(value, qubes.vm.qubesvm.QubesVM):
        return domain_data(value)
    elif isinstance(value, qubes.Qubes):
        return qubes_data(value)
    else:
        return dbus.String(value)


def label_path(label):
    return dbus.ObjectPath('/org/qubes/Labels1/labels/' + label.name)
