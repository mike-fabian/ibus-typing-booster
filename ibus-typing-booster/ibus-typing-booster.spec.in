Name:       ibus-typing-booster
Version:    0.0.1
Release:    1%{?dist}
Summary:    The Table engine for IBus platform
License:    GPLv2+
Group:      System Environment/Libraries
URL:        http://git.fedorahosted.org/git/?p=ibus-typing-booster.git
Source0:    https://fedorahosted.org/releases/i/b/ibus-typing-booster/%{name}-%{version}.tar.gz
Requires:       ibus
BuildRequires:  ibus-devel


BuildArch:  noarch

%description
The Typing Booster engine for IBus platform.

%prep
%setup -q


%build
%configure --disable-static --disable-additional
make %{?_smp_mflags}

%install 
make DESTDIR=${RPM_BUILD_ROOT} NO_INDEX=true install -p  pkgconfigdir=%{_datadir}/pkgconfig

%files 
%doc AUTHORS COPYING README 
%{_datadir}/%{name}
%{_datadir}/ibus/component/typing-booster.xml
%{_libexecdir}/ibus-engine-typing-booster
%{_datadir}/pkgconfig/%{name}.pc

%changelog
* Thu Jul 12 2012 Anish Patil <apatil@redhat.com> - 0.0.1-1
- The first version.
- derieved from ibus-table developed by Yu Yuwei <acevery@gmail.com>
