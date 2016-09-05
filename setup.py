#!/usr/bin/env python2
# -*- encoding: utf8 -*-
# pylint: disable=missing-docstring
import setuptools

if __name__ == '__main__':
    setuptools.setup(
        name='qubes-dbus',
        version=open('version').read().strip(),
        author='Bahtiar `kalkin-` Gadimov',
        author_email='bahtiar@gadimov.de',
        description='Qubes DBus package',
        license='GPL2+',
        url='https://www.qubes-os.org/',
        packages=['qubesdbus'],
        entry_points={
            'qubes.ext': [
                'qubesdbus = qubesdbus:QubesDbusProxy'
            ]
        })
