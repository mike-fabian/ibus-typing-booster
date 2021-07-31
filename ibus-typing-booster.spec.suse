# spec file for package ibus-typing-booster
#
# Copyright (c) 2017 SUSE LINUX GmbH, Nuernberg, Germany.
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via http://bugs.opensuse.org/
#

Name:           ibus-typing-booster
Version:        2.13.0
Release:        0 
Summary:        An input completion utility
License:        GPL-3.0+
Group:          System/X11/Utilities
URL:            https://mike-fabian.github.io/ibus-typing-booster/
Source0:        https://github.com/mike-fabian/ibus-typing-booster/releases/download/%{version}/%{name}-%{version}.tar.gz
Source1:        https://releases.pagure.org/inscript2/inscript2-20160423.tar.gz
Patch0:         m17n-db-1.8.0-inscript2-mni-sat.patch
BuildRequires:  ibus-devel
BuildRequires:  python3
BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
BuildRequires:  python3-gobject
BuildRequires:  python3-gobject-Gdk
BuildRequires:  dbus-1-x11
BuildRequires:  fdupes
BuildRequires:  update-desktop-files
# for the unit tests
BuildRequires:  m17n-lib
BuildRequires:  m17n-db
BuildRequires:  python3-pyenchant
BuildRequires:  AppStream
BuildRequires:  appstream-glib
BuildRequires:  glib2
BuildRequires:  gtk3
BuildRequires:  xorg-x11-server
# Because of “from packing import version”:
BuildRequires:  python3-packaging
%if 0%{?sle_version} >= 120200
BuildRequires:  python3-pyxdg
%endif
%if 0%{?suse_version} == 1320
BuildRequires:  myspell-cs_CZ
BuildRequires:  myspell-de
BuildRequires:  myspell-en
BuildRequires:  myspell-es
BuildRequires:  myspell-it_IT
%else
BuildRequires:  myspell-cs_CZ
BuildRequires:  myspell-de
BuildRequires:  myspell-de_DE
BuildRequires:  myspell-en
BuildRequires:  myspell-en_US
BuildRequires:  myspell-es
BuildRequires:  myspell-es_ES
BuildRequires:  myspell-fr_FR
BuildRequires:  myspell-it_IT
%endif
#
Requires:       ibus >= 1.5.3
Requires:       m17n-lib
Requires:       python3 >= 3.3
Requires:       dbus-1-python3
Requires:       python3-distro
Requires:       python3-pyenchant
# Because of “from packing import version”:
Requires:       python3-packaging
# Workaround bug with python3-enchant: https://bugzilla.opensuse.org/show_bug.cgi?id=1141993
Requires:  enchant-1-backend
Requires:       python3-pyxdg
# Recommend reasonably good fonts which have most of the emoji:
Recommends:     noto-coloremoji-fonts
Recommends:     gdouros-symbola-fonts
# For speech recognition:
Recommends:     python3-PyAudio
# To play a sound on error:
Recommends:     python3-simpleaudio


%description
Ibus-typing-booster is a context sensitive completion
input method to speedup typing.

%prep
%setup -q
##extract inscript2 maps
tar xzf %{SOURCE1}
%patch0 -p0

%build
export PYTHON=%{_bindir}/python3
%configure --disable-static --disable-additional --libexecdir=%{_libdir}/ibus
make %{?_smp_mflags}

%install
export PYTHON=%{_bindir}/python3
make install DESTDIR=%{buildroot} NO_INDEX=true
gzip -n --force --best %{buildroot}/%{_datadir}/%{name}/data/*.{txt,json} \
    %{buildroot}/%{_datadir}/%{name}/data/annotations/*.xml \
    %{buildroot}/%{_datadir}/%{name}/data/annotationsDerived/*.xml

#install inscript2 keymaps
test -d %{buildroot}%{_datadir}/m17n/icons || mkdir -p %{buildroot}%{_datadir}/m17n/icons
cp -p inscript2/IM/* %{buildroot}%{_datadir}/m17n/
cp -p inscript2/icons/* %{buildroot}%{_datadir}/m17n/icons

%suse_update_desktop_file -i -u emoji-picker GTK Utility

%fdupes %{buildroot}/%{_prefix}

%find_lang %{name}

%check
export LC_ALL=en_US.UTF-8
export M17NDIR=%{buildroot}%{_datadir}/m17n/
#appstreamcli validate --pedantic --nonet %{buildroot}/%{_datadir}/metainfo/*.appdata.xml
appstream-util validate-relax --nonet %{buildroot}/%{_datadir}/metainfo/*.appdata.xml
desktop-file-validate \
    %{buildroot}%{_datadir}/applications/ibus-setup-typing-booster.desktop
desktop-file-validate \
    $RPM_BUILD_ROOT%{_datadir}/applications/emoji-picker.desktop
pushd engine
    # run doctests
    # hunspell_suggest.py test currently doesn't work on SuSE because
    # the en_US dictionary changed apparently:
    # python3 hunspell_suggest.py -v
    python3 m17n_translit.py -v
    python3 itb_emoji.py -v
    python3 itb_util.py -v
popd
mkdir -p /tmp/glib-2.0/schemas/
cp org.freedesktop.ibus.engine.typing-booster.gschema.xml \
   /tmp/glib-2.0/schemas/org.freedesktop.ibus.engine.typing-booster.gschema.xml
glib-compile-schemas /tmp/glib-2.0/schemas #&>/dev/null || :
export XDG_DATA_DIRS=/tmp
eval $(dbus-launch --sh-syntax)
dconf dump /
dconf write /org/freedesktop/ibus/engine/typing-booster/offtherecord false
dconf write /org/freedesktop/ibus/engine/typing-booster/usedigitsasselectkeys true
dconf write /org/freedesktop/ibus/engine/typing-booster/addspaceoncommit true
dconf write /org/freedesktop/ibus/engine/typing-booster/tabenable false
dconf write /org/freedesktop/ibus/engine/typing-booster/inputmethod "'NoIME'"
dconf write /org/freedesktop/ibus/engine/typing-booster/rememberlastusedpreeditime true
dconf write /org/freedesktop/ibus/engine/typing-booster/mincharcomplete 1
dconf write /org/freedesktop/ibus/engine/typing-booster/dictionary "'en_US'"
dconf write /org/freedesktop/ibus/engine/typing-booster/emojipredictions true
dconf write /org/freedesktop/ibus/engine/typing-booster/autocommitcharacters "''"
dconf write /org/freedesktop/ibus/engine/typing-booster/pagesize 6
dconf write /org/freedesktop/ibus/engine/typing-booster/shownumberofcandidates true
dconf write /org/freedesktop/ibus/engine/typing-booster/showstatusinfoinaux true
dconf write /org/freedesktop/ibus/engine/typing-booster/inlinecompletion false
dconf write /org/freedesktop/ibus/engine/typing-booster/keybindings "{'next_input_method': <['Control+Down', 'Control+KP_Down']>, 'previous_input_method': <['Control+Up', 'Control+KP_Up']>, 'lookup_related': <['Mod5+F12']>, 'enable_lookup': <['Tab', 'ISO_Left_Tab', 'KP_Divide']>, 'select_next_candidate': <['Tab', 'ISO_Left_Tab', 'Down', 'KP_Down']>, 'lookup_table_page_down': <['Page_Down', 'KP_Page_Down', 'KP_Next']>, 'toggle_emoji_prediction': <['Mod5+F6']>, 'lookup_table_page_up': <['Page_Up', 'KP_Page_Up', 'KP_Prior']>, 'toggle_off_the_record': <['Mod5+F9']>, 'cancel': <['Escape']>, 'setup': <['Mod5+F10']>, 'select_previous_candidate': <['Shift+Tab', 'Shift+ISO_Left_Tab', 'Up', 'KP_Up']>}"
dconf dump /
export DISPLAY=:1
Xvfb $DISPLAY -screen 0 1024x768x16 &
# A window manager and and ibus-daemon are needed to run the GUI
# test tests/test_gtk.py, for example i3 can be used.
#
# To debug what is going on if there is a problem with the GUI test
# add BuildRequires: x11vnc and start a vnc server:
#
#     x11vnc -display $DISPLAY -unixsock /tmp/mysock -bg -nopw -listen localhost -xkb
#
# Then one can view what is going on outside of the chroot with vncviewer:
#
#     vncviewer /var/lib/mock/fedora-32-x86_64/root/tmp/mysock
#
# The GUI test will be skipped if XDG_SESSION_TYPE is not x11 or wayland.
#
#ibus-daemon -drx
#touch /tmp/i3config
#i3 -c /tmp/i3config &
#export XDG_SESSION_TYPE=x11

make check && rc=0 || rc=1
cat tests/*.log
if [ $rc != 0 ] ; then
    exit $rc
fi

%post
[ -x %{_bindir}/ibus ] && \
  %{_bindir}/ibus write-cache --system &>/dev/null || :

%postun
[ -x %{_bindir}/ibus ] && \
  %{_bindir}/ibus write-cache --system &>/dev/null || :

%files -f %{name}.lang
%doc AUTHORS COPYING README README.html README.md
%{_bindir}/emoji-picker
%{_datadir}/%{name}
%dir %{_datadir}/metainfo
%{_datadir}/metainfo/*.appdata.xml
%{_datadir}/ibus/component/typing-booster.xml
%{_datadir}/icons/hicolor/16x16/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/22x22/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/32x32/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/48x48/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/64x64/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/128x128/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/256x256/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/scalable/apps/ibus-typing-booster.svg
%{_libdir}/ibus/ibus-engine-typing-booster
%{_libdir}/ibus/ibus-setup-typing-booster
%{_datadir}/applications/*.desktop
%{_datadir}/glib-2.0/schemas/org.freedesktop.ibus.engine.typing-booster.gschema.xml
%dir %{_datadir}/m17n
%{_datadir}/m17n/*.mim
%dir %{_datadir}/m17n/icons
%{_datadir}/m17n/icons/*.png

%changelog
