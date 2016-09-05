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

from __future__ import absolute_import

import logging

import dbus
from qubes import Qubes
from qubes.vm.qubesvm import QubesVM
from systemd.journal import JournalHandler

from .constants import NAME_PREFIX, PATH_PREFIX, VERSION

try:
    # Check for mypy dependencies pylint: disable=ungrouped-imports
    from typing import Any, Optional, Union  # pylint: disable=unused-import
    from qubesdbus.service import _DbusServiceObject  # pylint:disable=unused-import
except ImportError:
    pass

log = logging.getLogger('qubesdbus.proxy')
log.addHandler(JournalHandler(SYSLOG_IDENTIFIER='qubesdbus.proxy'))
log.setLevel(logging.DEBUG)

INTERFACE_NAME = "%s.QubesSignals%s" % (NAME_PREFIX, VERSION)
SESSION_BUS = dbus.SessionBus()
MANAGER_NAME = "%s.DomainManager%s" % (NAME_PREFIX, VERSION)
MANAGER_PATH = "%s/DomainManager%s" % (PATH_PREFIX, VERSION)
GARBAGE = [
    'domain-is-fully-usable',  # only important for internal core-admin?
]


class QubesDbusProxy(object):
    # pylint: disable=too-few-public-methods
    def __init__(self, *args, **kwargs):
        super(QubesDbusProxy, self).__init__(*args, **kwargs)
        self.domains = {}  # type: Dict[int, bool]

    def forward(self, obj, event_name, *args, **kwargs):
        # type: (Union[Qubes, QubesVM], str, *Any, **Any) -> None
        # pylint: disable=redefined-variable-type
        if isinstance(obj, QubesVM):
            # let's play a game called guess in which state is the domain?
            if not hasattr(obj, 'qid'):
                # just reading domain from qubes.xml and preparing for
                # populating it, we can ignore this event
                log.info('%s some domain', event_name)
                return
            else:
                qid = obj.qid
                log.info('Received %s => %s', qid, event_name)
                if qid not in self.domains.keys():
                    self.domains[qid] = False

                if event_name == 'domain-load':
                    self.domains[qid] = True

                if self.domains[qid]:
                    log.info("Would forward event to existing domain %s", qid)
        try:
            args = serialize(args)
            kwargs = zip(kwargs.keys(), serialize(kwargs.values()))
            log.info("%s : %s : %s", event_name, args, kwargs)
        except TypeError as ex:
            msg = "%s: %s" % (event_name, ex.message)
            log.error(msg)

    @staticmethod
    def old_forward(obj, event_name, *args, **kwargs):
        # pylint: disable=redefined-variable-type
        try:
            proxy = get_proxy(obj)
            if event_name.startswith('property-set'):
                log.debug('Received %s from %s', event_name, obj)
                p_name = args[0]
                p_value = str(args[1])
                set_method = proxy.get_dbus_method(
                    'Set', 'org.freedesktop.DBus.Properties')
                set_method('', p_name, p_value)
            elif event_name in GARBAGE:
                log.debug("Droping event %s", event_name)
            elif isinstance(obj, QubesVM):
                log.debug("Forwarding event %s", event_name)
                forward_signal_func = proxy.get_dbus_method(
                    'ForwardSignal', 'org.qubes.Signals')
                if not args:
                    args = ['']
                if not kwargs:
                    kwargs = {'fpp': 'bar'}

                forward_signal_func(event_name, args, kwargs)
            else:
                log.info("Do not know how to handle %s event", event_name)
                if args:
                    log.info(args)
                if kwargs:
                    log.warn(kwargs)
        except TypeError as ex:
            msg = "%s: %s" % (event_name, ex.message)
            log.error(msg)


def serialize(args):
    result = []
    for val in args:
        if isinstance(val, QubesVM):
            result.append(val.qid)
        else:
            str(val)
    return result


def get_proxy(obj):
    # type: (Union[Qubes, QubesVM]) -> dbus.proxies.ProxyObject
    identifier = str(obj)
    if isinstance(obj, Qubes):
        return SESSION_BUS.get_object(MANAGER_NAME, MANAGER_PATH)
    elif isinstance(obj, QubesVM):
        domain_path = '/'.join([MANAGER_PATH, 'domains', identifier]).replace(
            '-', '_')
        return SESSION_BUS.get_object(MANAGER_NAME, domain_path)
    else:
        log.error("Unknown sender object %s", obj)
        return
