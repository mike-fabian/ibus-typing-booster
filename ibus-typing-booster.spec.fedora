Name:       ibus-typing-booster
Version:    2.27.9
Release:    %autorelease
Summary:    A completion input method
License:    GPL-3.0-or-later AND Apache-2.0
URL:        https://mike-fabian.github.io/ibus-typing-booster/
Source0:    https://github.com/mike-fabian/ibus-typing-booster/releases/download/%{version}/ibus-typing-booster-%{version}.tar.gz
Requires:   ibus >= 1.5.3
Requires:   m17n-lib
%{?__python3:Requires: %{__python3}}
Requires:   python3-dbus
Requires:   python3-distro
# because of “from packing import version”:
Requires:   python3-packaging
Requires:   python3-enchant
Requires:   python3-pyxdg
%if 0%{?fedora} >= 24 || 0%{?rhel} > 7
# Recommend reasonably good fonts which have most of the emoji:
Recommends: google-noto-emoji-color-fonts
Recommends: gdouros-symbola-fonts
# For better description of the dictionaries in the setup tool
# makes it possible to search for full language and territory names
# and not just locale codes:
Recommends: python3-langtable
# To play a sound on error:
Recommends: python3-simpleaudio
# Use better regexpressions if available:
Recommends: python3-regex
# To get the currently active window in a Gnome Wayland session:
Recommends: python3-pyatspi
%endif
%if 0%{?fedora} >= 26 || 0%{?rhel} > 7
# Save some space in the binary rpm by requiring the Fedora
# packages which contain the emoji data files:
Requires: cldr-emoji-annotation
Requires: unicode-ucd
%endif
BuildRequires:  ibus-devel
BuildRequires:  gcc
%if 0%{?fedora} >= 24 || 0%{?rhel} > 7
BuildRequires:  python3-devel >= 3.6.0
BuildRequires:  python3-pyxdg
%else
BuildRequires:  python34-devel
%endif
# for the unit tests
BuildRequires:  m17n-lib
BuildRequires:  m17n-db-extras
BuildRequires:  m17n-db-devel
BuildRequires:  python3-enchant
BuildRequires:  enchant2
BuildRequires:  hunspell-en
# because of “from packing import version”:
BuildRequires:   python3-packaging
%if 0%{?fedora} >= 35
# to make the python3-enchant test work for hunspell dictionaries which are not yet UTF-8:
BuildRequires:   glibc-gconv-extra
%endif
%if 0%{?fedora} && 0%{?fedora} >= 34
BuildRequires:  python3-libvoikko
BuildRequires:  voikko-fi
%endif
BuildRequires:  appstream
BuildRequires:  libappstream-glib
BuildRequires:  desktop-file-utils
BuildRequires:  python3-gobject
BuildRequires:  python3-gobject-base
BuildRequires:  hunspell-cs
BuildRequires:  hunspell-de
BuildRequires:  hunspell-en
BuildRequires:  hunspell-es
BuildRequires:  hunspell-fr
BuildRequires:  hunspell-it
BuildRequires:  hunspell-ko
BuildRequires:  glib2
BuildRequires:  gtk3
BuildRequires:  dconf
BuildRequires:  dbus-x11
BuildRequires:  ibus
BuildRequires:  glibc-langpack-en
BuildRequires:  glibc-langpack-cs
BuildRequires:  glibc-langpack-km
BuildRequires:  glibc-langpack-pt
BuildRequires:  glibc-langpack-am
BuildRequires:  glibc-langpack-de
BuildRequires:  glibc-langpack-ar
BuildRequires: make
BuildArch:  noarch
# Some test cases fail on ppc64 and s390x (because of some bugs on
# these platforms I think).  This makes the build fail for no good
# reason if it accidentally is build on one of these platforms.
#
# So even though this is a noarch package, tell koji to never build it
# on ppc64 and s390x:
ExcludeArch: ppc64 s390x

%description
Ibus-typing-booster is a context sensitive completion
input method to speedup typing.

%package tests
Summary:        Tests for the %{name} package
Requires:       %{name} = %{version}-%{release}

%description tests
The %{name}-tests package contains tests that can be used to verify
the functionality of the installed %{name} package.

%package -n emoji-picker
Summary: An emoji selection tool
Requires: ibus-typing-booster = %{version}-%{release}

%description -n emoji-picker
A simple application to find and insert emoji and other
Unicode symbols.

%prep
%setup -q


%build
export PYTHON=%{__python3}
%configure --disable-static --enable-installed-tests
%make_build

%install 
export PYTHON=%{__python3}
%make_install NO_INDEX=true  pkgconfigdir=%{_datadir}/pkgconfig
%py_byte_compile %{python3} /usr/share/ibus-typing-booster/engine
%py_byte_compile %{python3} /usr/share/ibus-typing-booster/setup
%if 0%{?fedora} >= 26 || 0%{?rhel} > 7
    # These files are in the required package “cldr-emoji-annotation”
    rm $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/annotations/*.xml
    rm $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/annotationsDerived/*.xml
    # Thes files are in the required package “unicode-ucd”:
    rm $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/UnicodeData.txt
    rm $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/Blocks.txt
    rm $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/DerivedAge.txt
    # At least emoji-data.txt emoji-sequences.txt emoji-zwj-sequences.txt
    # are still there even on Fedora >= 26 they are not available in any packages:
    gzip -n --force --best $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/*.txt
    # The json file from emojione is not deleted anymore because
    # the package nodejs-emojione-json has been orphaned:
    gzip -n --force --best $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/*.json
%else
    gzip -n --force --best $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/*.{txt,json}
    gzip -n --force --best $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/annotations/*.xml
    gzip -n --force --best $RPM_BUILD_ROOT/%{_datadir}/%{name}/data/annotationsDerived/*.xml
%endif

%find_lang %{name}

%check
export LC_ALL=C.UTF-8
appstreamcli validate --pedantic --no-net %{buildroot}/%{_datadir}/metainfo/*.metainfo.xml
# According to the appstream developers, appstream-util is unmaintained:
# https://github.com/ximion/appstream/issues/494#issuecomment-1521419742
# But I keep it here for the time being because the Fedora packaging guidelines ask for it:
# https://docs.fedoraproject.org/en-US/packaging-guidelines/AppData/#_app_data_validate_usage
appstream-util validate-relax --nonet %{buildroot}/%{_datadir}/metainfo/*.metainfo.xml
desktop-file-validate \
    $RPM_BUILD_ROOT%{_datadir}/applications/ibus-setup-typing-booster.desktop
desktop-file-validate \
    $RPM_BUILD_ROOT%{_datadir}/applications/emoji-picker.desktop
pushd engine
    # run doctests
    # commented out because of https://bugzilla.redhat.com/show_bug.cgi?id=2218460
    #python3 hunspell_suggest.py
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
export XDG_DATA_DIRS=/tmp:%{_datadir} # /usr/share is needed to make enchant2 work!
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

%files -f %{name}.lang
%doc AUTHORS COPYING README README.html README.md
%{_datadir}/%{name}
%{_datadir}/metainfo/org.freedesktop.ibus.engine.typing_booster.metainfo.xml
%{_datadir}/ibus/component/typing-booster.xml
%{_datadir}/icons/hicolor/16x16/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/22x22/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/32x32/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/48x48/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/64x64/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/128x128/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/256x256/apps/ibus-typing-booster.png
%{_datadir}/icons/hicolor/scalable/apps/ibus-typing-booster.svg
%{_libexecdir}/ibus-engine-typing-booster
%{_libexecdir}/ibus-setup-typing-booster
%{_datadir}/applications/ibus-setup-typing-booster.desktop
%{_datadir}/glib-2.0/schemas/org.freedesktop.ibus.engine.typing-booster.gschema.xml

%files tests
%dir %{_libexecdir}/installed-tests
%{_libexecdir}/installed-tests/%{name}
%dir %{_datadir}/installed-tests
%{_datadir}/installed-tests/%{name}

%files -n emoji-picker
%{_bindir}/emoji-picker
%{_datadir}/metainfo/org.freedesktop.ibus.engine.typing_booster.emoji_picker.metainfo.xml
%{_datadir}/applications/emoji-picker.desktop

%changelog
%autochangelog
