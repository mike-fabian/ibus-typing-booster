---
title: Downloads
---

* [Fedora](https://src.fedoraproject.org/rpms/ibus-typing-booster)
* [Fedora Updates System](https://bodhi.fedoraproject.org/updates/?search=ibus-typing-booster) (The latest “official” updates of ibus-typing-booster for Fedora)
* [Fedora copr](https://copr.fedorainfracloud.org/coprs/mfabian/ibus-typing-booster/)
  🥼🧪 (Experimental updates for Fedora)
* [openSUSE:Leap:15.4](https://build.opensuse.org/package/show/openSUSE:Leap:15.4/ibus-typing-booster)
* [openSUSE:Leap:15.5](https://build.opensuse.org/package/show/openSUSE:Leap:15.5/ibus-typing-booster)
* [openSUSE:Leap:15.6](https://build.opensuse.org/package/show/openSUSE:Leap:15.6/ibus-typing-booster)
* [openSUSE:Factory](https://build.opensuse.org/package/show/openSUSE:Factory/ibus-typing-booster)
  🏭 (The next openSUSE distribution)
* [openSUSE M17N project](https://build.opensuse.org/package/show/M17N/ibus-typing-booster)
  (The latest “official” updates of ibus-typing-booster for openSUSE)
* [openSUSE home:mike-fabian project](
  https://build.opensuse.org/package/show/home:mike-fabian/ibus-typing-booster)
  🥼🧪 (Experimental updates for openSUSE, Debian, and Ubuntu)
* [Debian](https://packages.debian.org/sid/ibus-typing-booster)
* [Ubuntu](https://launchpad.net/ubuntu/+source/ibus-typing-booster)
* [Arch linux](https://www.archlinux.org/packages/extra/any/ibus-typing-booster)
* [FreeBSD port](http://www.freshports.org/textproc/ibus-typing-booster)
* [Source tarballs](https://github.com/mike-fabian/ibus-typing-booster/releases)

Overview of ibus-typing-booster packages for all distros: [Repology](https://repology.org/project/ibus-typing-booster/versions)

## 🥼🧪 Repositories for Debian and Ubuntu with my latest updates


This page https://software.opensuse.org/package/ibus-typing-booster
lists for which distributions builds from the openSUSE build service
are available.

Clicking on `Show community packages` leads to this page:

https://software.opensuse.org/download/package?package=ibus-typing-booster&project=home%3Amike-fabian

There one can choose *Debian* or *Ubuntu* and either click on `Grab
binary packages directly` to get links to download `.deb` files or
click on `Add repository and install manually` to get the following
instructions on how to add a repository for my latest updates for
ibus-typing-booster for various versions of Debian and Ubuntu:

If you don’t yet have `curl` installed, install that first:

`sudo apt install curl`

Then:

* For **Debian Unstable** run the following:
  ```
  echo 'deb http://download.opensuse.org/repositories/home:/mike-fabian/Debian_Unstable/ /' | sudo tee /etc/apt/sources.list.d/home:mike-fabian.list
  curl -fsSL https://download.opensuse.org/repositories/home:mike-fabian/Debian_Unstable/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_mike-fabian.gpg > /dev/null
  sudo apt update
  sudo apt install ibus-typing-booster
  ```
* For **Debian Testing** run the following:
  ```
  echo 'deb http://download.opensuse.org/repositories/home:/mike-fabian/Debian_Testing/ /' | sudo tee /etc/apt/sources.list.d/home:mike-fabian.list
  curl -fsSL https://download.opensuse.org/repositories/home:mike-fabian/Debian_Testing/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_mike-fabian.gpg > /dev/null
  sudo apt update
  sudo apt install ibus-typing-booster
  ```
* For **Debian 13** run the following:
  ```
  echo 'deb http://download.opensuse.org/repositories/home:/mike-fabian/Debian_13/ /' | sudo tee /etc/apt/sources.list.d/home:mike-fabian.list
  curl -fsSL https://download.opensuse.org/repositories/home:mike-fabian/Debian_13/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_mike-fabian.gpg > /dev/null
  sudo apt update
  sudo apt install ibus-typing-booster
  ```
* For **Debian 12** run the following:
  ```
  echo 'deb http://download.opensuse.org/repositories/home:/mike-fabian/Debian_12/ /' | sudo tee /etc/apt/sources.list.d/home:mike-fabian.list
  curl -fsSL https://download.opensuse.org/repositories/home:mike-fabian/Debian_12/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_mike-fabian.gpg > /dev/null
  sudo apt update
  sudo apt install ibus-typing-booster
  ```
* For **Ubuntu 25.10** run the following:
  ```
  echo 'deb http://download.opensuse.org/repositories/home:/mike-fabian/xUbuntu_25.10/ /' | sudo tee /etc/apt/sources.list.d/home:mike-fabian.list
  curl -fsSL https://download.opensuse.org/repositories/home:mike-fabian/xUbuntu_25.10/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_mike-fabian.gpg > /dev/null
  sudo apt update
  sudo apt install ibus-typing-booster
  ```
* For **Ubuntu 25.04** run the following:
  ```
  echo 'deb http://download.opensuse.org/repositories/home:/mike-fabian/xUbuntu_25.04/ /' | sudo tee /etc/apt/sources.list.d/home:mike-fabian.list
  curl -fsSL https://download.opensuse.org/repositories/home:mike-fabian/xUbuntu_25.04/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_mike-fabian.gpg > /dev/null
  sudo apt update
  sudo apt install ibus-typing-booster
  ```
* For **Ubuntu 24.04** run the following:
  ```
  echo 'deb http://download.opensuse.org/repositories/home:/mike-fabian/xUbuntu_24.04/ /' | sudo tee /etc/apt/sources.list.d/home:mike-fabian.list
  curl -fsSL https://download.opensuse.org/repositories/home:mike-fabian/xUbuntu_24.04/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_mike-fabian.gpg > /dev/null
  sudo apt update
  sudo apt install ibus-typing-booster
  ```
* For **Ubuntu 22.04** run the following:
  ```
  echo 'deb http://download.opensuse.org/repositories/home:/mike-fabian/xUbuntu_22.04/ /' | sudo tee /etc/apt/sources.list.d/home:mike-fabian.list
  curl -fsSL https://download.opensuse.org/repositories/home:mike-fabian/xUbuntu_22.04/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/home_mike-fabian.gpg > /dev/null
  sudo apt update
  sudo apt install ibus-typing-booster
  ```
