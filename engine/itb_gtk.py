#!/usr/bin/python3
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2025 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>
'''
Centralized version switcher for Gtk/Gdk.

All code in ibus-typing-booster must import Gtk/Gdk exclusively via:

    from itb_gtk import Gtk, Gdk, GTK_MAJOR, GTK_VERSION

This allows switching between Gtk3 and Gtk4 simply by setting:

    ITB_GTK_VERSION=3   → use Gtk 3.x
    ITB_GTK_VERSION=4   → use Gtk 4.x
    (unset)             → default = Gtk 3.x

This prevents accidental mixing of Gtk versions and ensures the
entire process uses a consistent GI setup.

This module must be imported **before** any other module imports
Gtk or Gdk.
'''
from typing import (
    Tuple,
    Dict,
)
import sys
import os
import traceback
from gi import require_version

# Prevent accidental early Gtk imports
if 'gi.repository.Gtk' in sys.modules:
    raise RuntimeError(
        'Gtk was already imported before itb_gtk! '
        'Ensure all imports of Gtk/Gdk go through itb_gtk. '
        'Import stack trace:\n' + ''.join(traceback.format_stack()))

# Prevent accidental early Gdk imports
if 'gi.repository.Gdk' in sys.modules:
    raise RuntimeError(
        'Gdk was already imported before itb_gtk! '
        'Ensure all imports of Gtk/Gdk go through itb_gtk. '
        'Import stack trace:\n' + ''.join(traceback.format_stack()))

def _os_release() -> Dict[str, str]:
    '''Return ID, VERSION_ID, ID_LIKE from /etc/os-release.'''
    result = {}
    try:
        with open('/etc/os-release', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    result[k] = v.strip('"')
    except Exception: # pylint: disable=broad-except
        pass
    return result

def _is_rhel9() -> bool:
    '''
    Detect RHEL 9 and RHEL 9 compatible rebuilds (AlmaLinux 9, Rocky 9, etc.)

    These systems ship Gtk4 but lack support for color emoji in Gtk4,
    so ibus-typing-booster should force Gtk3.
    '''
    data = _os_release()
    distro_id = data.get('ID', '')
    version = data.get('VERSION_ID', '')
    if distro_id in ('rhel', 'almalinux', 'rocky'):
        return version.startswith('9.')
    return False

def _is_ubuntu_2204_or_older() -> bool:
    '''
    Detect Ubuntu ≤ 22.04 (Jammy).

    Jammy ships Gtk 4.6 which lacks:
        Gtk.Picture.set_content_fit
    which ibus-typing-booster needs.

    Force Gtk3 on such systems.
    '''
    data = _os_release()
    distro_id = data.get('ID', '')
    version = data.get('VERSION_ID', '')
    if distro_id != 'ubuntu':
        return False
    try:
        major, minor = map(int, version.split('.')[:2])
    except Exception: # pylint: disable=broad-except
        return False
    return (major, minor) <= (22, 4)

def _gtk_available(major: int) -> bool:
    '''Check if Gtk major version is installed and introspectable.'''
    try:
        require_version('Gtk', '4.0' if major == 4 else '3.0')
        return True
    except Exception: # pylint: disable=broad-except
        return False

# Determine desired Gtk major version
requested = os.environ.get('ITB_GTK_VERSION', '').strip().lower()

if requested in ('3', 'gtk3', '3.0'):
    VERSION = '3'
elif requested in ('4', 'gtk4', '4.0'):
    VERSION = '4'
else:
    # Autodetect
    if _is_rhel9():
        # Force Gtk3 on RHEL9 due to broken emoji support in Gtk4
        VERSION = '3'
    elif _is_ubuntu_2204_or_older():
        VERSION = '3'
    else:
        VERSION = '4' if _gtk_available(4) else '3'

# Apply GI version requirements
if VERSION == '3':
    require_version('Gtk', '3.0')
    require_version('Gdk', '3.0')
else:
    require_version('Gtk', '4.0')
    require_version('Gdk', '4.0')

# Import the actual modules
# pylint: disable=wrong-import-position, unused-import
from gi.repository import Gtk, Gdk # type: ignore # noqa: F401 # Intentional re-export
# pylint: enable=wrong-import-position, unused-import

# Convenience constants for compatibility code
# pylint: disable=no-value-for-parameter
GTK_MAJOR: int = Gtk.get_major_version()
GTK_MINOR: int = Gtk.get_minor_version()
GTK_MICRO: int = Gtk.get_micro_version()
GTK_VERSION: Tuple[int, int, int] = (GTK_MAJOR, GTK_MINOR, GTK_MICRO)
# pylint: enable=no-value-for-parameter

## Re-export for external use (create mypy warnings, uncomment for the moment)
#__all__ = [
#    'Gtk',
#    'Gdk',
#    'GTK_MAJOR',
#    'GTK_MINOR',
#    'GTK_MICRO',
#    'GTK_VERSION',
#]
