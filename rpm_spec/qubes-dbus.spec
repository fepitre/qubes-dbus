#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#

%{!?version: %define version %(cat version)}
Name: qubes-dbus
Version:    %{version}
Release:    1%{?dist}
BuildArch:  noarch
Summary:    foo bar

Group:      Qubes
Vendor:		Invisible Things Lab
License:    GPL2+
URL:		http://www.qubes-os.org

Requires: python3-dbus
Requires: python3-systemd

%define _builddir %(pwd)

%prep
rm -f %{name}-%{version}
ln -sf . %{name}-%{version}
%setup -T -D

%description
foo bar

%build
/usr/bin/python3 setup.py build

%install

python3 setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
mkdir -p $RPM_BUILD_ROOT/usr/share
mkdir -p $RPM_BUILD_ROOT/etc/xdg/autostart
cp -r dbus-1 $RPM_BUILD_ROOT/usr/share/dbus-1
cp autostart/*.desktop $RPM_BUILD_ROOT/etc/xdg/autostart

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root,-)
/usr/bin/qubes-dbus-proxy
/usr/share/dbus-1/services/org.qubes.DomainManager1.service
/usr/share/dbus-1/services/org.qubes.Labels1.service
/etc/xdg/autostart/qubes-dbus-proxy.desktop
