#
# spec file for package ibus-typing-booster
#
# Copyright (c) 2023 SUSE LLC
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via https://bugs.opensuse.org/
#


Name:           ibus-typing-booster
Version:        2.27.9
Release:        0
Summary:        An input completion utility
License:        GPL-3.0-or-later
Group:          System/X11/Utilities
URL:            https://mike-fabian.github.io/ibus-typing-booster/
Source0:        https://github.com/mike-fabian/ibus-typing-booster/releases/download/%{version}/%{name}-%{version}.tar.gz
Source1:        https://releases.pagure.org/inscript2/inscript2-20210820.tar.gz
BuildRequires:  AppStream
BuildRequires:  appstream-glib
BuildRequires:  desktop-file-utils
BuildRequires:  fdupes
BuildRequires:  glib2
BuildRequires:  glibc-locale
BuildRequires:  gtk3
BuildRequires:  ibus-devel
BuildRequires:  m17n-db
# for the unit tests
BuildRequires:  m17n-lib
BuildRequires:  python3
BuildRequires:  python3-devel
BuildRequires:  python3-gobject
BuildRequires:  python3-gobject-Gdk
# Because of “from packing import version”:
BuildRequires:  python3-packaging
BuildRequires:  python3-pyenchant
# To avoid requiring Python >= 3.8
BuildRequires:  python3-typing_extensions
BuildRequires:  update-desktop-files
Requires:       dbus-1-python3
# Workaround bug with python3-enchant: https://bugzilla.opensuse.org/show_bug.cgi?id=1141993
Requires:       enchant-1-backend
#
Requires:       ibus >= 1.5.3
Requires:       m17n-lib
Requires:       python3 >= 3.6
Requires:       python3-distro
# Because of “from packing import version”:
Requires:       python3-packaging
Requires:       python3-pyenchant
Requires:       python3-pyxdg
Recommends:     gdouros-symbola-fonts
# Recommend reasonably good fonts which have most of the emoji:
Recommends:     noto-coloremoji-fonts
# For speech recognition:
Recommends:     python3-PyAudio
# To make the setup tool look nicer and the search for dictionaries and imes better:
Recommends:     python3-langtable
# Better regexpressions (optional):
Recommends:     python3-regex
# To play a sound on error:
Recommends:     python3-simpleaudio
%if 0%{?sle_version} >= 120200
BuildRequires:  python3-pyxdg
%endif
%if 0%{?suse_version} == 1320
BuildRequires:  myspell-de
BuildRequires:  myspell-en
BuildRequires:  myspell-es
BuildRequires:  myspell-it_IT
%else
BuildRequires:  myspell-de
BuildRequires:  myspell-de_DE
BuildRequires:  myspell-en
BuildRequires:  myspell-en_US
BuildRequires:  myspell-es
BuildRequires:  myspell-es_ES
BuildRequires:  myspell-fr_FR
BuildRequires:  myspell-it_IT
%endif

%description
Ibus-typing-booster is a context sensitive completion
input method to speedup typing.

%prep
%setup -q
%if 0%{?suse_version} < 1550
##extract inscript2 maps
tar xzf %{SOURCE1}
%endif

%build
export PYTHON=%{_bindir}/python3
%configure --disable-static --libexecdir=%{_ibus_libexecdir}
%make_build

%install
export PYTHON=%{_bindir}/python3
make install DESTDIR=%{buildroot} NO_INDEX=true
gzip -n --force --best %{buildroot}/%{_datadir}/%{name}/data/*.{txt,json} \
    %{buildroot}/%{_datadir}/%{name}/data/annotations/*.xml \
    %{buildroot}/%{_datadir}/%{name}/data/annotationsDerived/*.xml

%if 0%{?suse_version} < 1550
#install inscript2 keymaps
test -d %{buildroot}%{_datadir}/m17n/icons || mkdir -p %{buildroot}%{_datadir}/m17n/icons
cp -p inscript2/IM/* %{buildroot}%{_datadir}/m17n/
cp -p inscript2/icons/* %{buildroot}%{_datadir}/m17n/icons
%endif

%suse_update_desktop_file -i -u emoji-picker GTK Utility

%fdupes %{buildroot}/%{_prefix}

%find_lang %{name}

%check
export LC_ALL=en_US.UTF-8
export M17NDIR=%{buildroot}%{_datadir}/m17n/
%if 0%{?suse_version} > 1520
#AS_VALIDATE_NONET=1 appstreamcli validate --pedantic --no-net %{buildroot}/%{_datadir}/metainfo/*.metainfo.xml
%endif
desktop-file-validate \
    %{buildroot}%{_datadir}/applications/ibus-setup-typing-booster.desktop
desktop-file-validate \
    %{buildroot}%{_datadir}/applications/emoji-picker.desktop
pushd engine
    # run doctests
    # hunspell_suggest.py test currently doesn't work on SuSE because
    # the en_US dictionary changed apparently:
    # python3 hunspell_suggest.py -v
    if [ -e /usr/share/m17n/si-wijesekara.mim ] ; then
        python3 m17n_translit.py -v
    else
        echo "/usr/share/m17n/si-wijesekara.mim does not exist, m17n-db probably < 1.8.6, skipping doctest of m17n_translit.py"
    fi
    python3 itb_emoji.py -v
    python3 itb_util.py -v
popd
mkdir -p /tmp/glib-2.0/schemas/
cp org.freedesktop.ibus.engine.typing-booster.gschema.xml \
   /tmp/glib-2.0/schemas/org.freedesktop.ibus.engine.typing-booster.gschema.xml
glib-compile-schemas /tmp/glib-2.0/schemas #&>/dev/null || :

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
%license COPYING
%doc AUTHORS README README.html README.md
%{_bindir}/emoji-picker
%{_datadir}/%{name}
%dir %{_datadir}/metainfo
%{_datadir}/metainfo/*.metainfo.xml
%{_datadir}/ibus/component/typing-booster.xml
%{_datadir}/icons/hicolor/16x16/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/22x22/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/32x32/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/48x48/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/64x64/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/128x128/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/256x256/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/scalable/apps/ibus-typing-booster.svg
%{_ibus_libexecdir}/ibus-engine-typing-booster
%{_ibus_libexecdir}/ibus-setup-typing-booster
%{_datadir}/applications/*.desktop
%{_datadir}/glib-2.0/schemas/org.freedesktop.ibus.engine.typing-booster.gschema.xml
%if 0%{?suse_version} < 1550
%dir %{_datadir}/m17n
%{_datadir}/m17n/*.mim
%dir %{_datadir}/m17n/icons
%{_datadir}/m17n/icons/*.png
%endif

%changelog
