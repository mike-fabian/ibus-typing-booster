---
title: Developer Documentation 👩‍🔧
date: 2021-08-28
---

# Contents

* [Reporting bugs 🐞](#reporting-bugs)
* [Translation 🇺🇳](#translation)
* [Mailing list 📬](#mailing-list)
* [git repository 🐱](#git-repository)
    * [Anonymous git clone](#anonymous-git-clone)
    * [Authorized git clone](#authorized-git-clone)
* [Releases](#releases)
* [Building and installing from source 🛠️](#building-and-installing-from-source)
    * [Build requirements](#build-requirements)
    * [Runtime requirements](#runtime-requirements)
* [Running from a source tree 🌳🏃‍♀️‍➡️](#running-from-a-source-tree)
* [Distribution specific stuff for building, installing, and running](#distribution-specific-stuff)
    * [Fedora](#building-and-installing-on-fedora)
    * [openSUSE](#building-and-installing-on-opensuse)
    * [Ubuntu](#building-and-installing-on-ubuntu)
    * [Alpine Linux](#building-and-installing-on-alpine)

---------

# Reporting bugs 🐞 {#reporting-bugs}

You can report bugs and suggest improvements in the github issue tracker: https://github.com/mike-fabian/ibus-typing-booster/issues

# Translation 🇺🇳 {#translation}

You can contribute translations for ibus-typing-booster using the online translation platform weblate: https://translate.fedoraproject.org/projects/ibus-typing-booster/.

If you cannot use weblate, you can also create a pull request for new or updated translations.

# Mailing list 📬 {#mailing-list}

https://lists.fedorahosted.org/admin/lists/ibus-typing-booster.lists.fedorahosted.org/

# git repository 🐱 {#git-repository}

You can browse the source code at https://github.com/mike-fabian/ibus-typing-booster.

## Anonymous git clone {#anonymous-git-clone}
```
$ git clone git://github.com/mike-fabian/ibus-typing-booster.git
```

## Authorized git clone {#authorized-git-clone}
```
$ git clone git@github.com:mike-fabian/ibus-typing-booster.git
```
# Releases {#releases}

Release tarballs are available at https://github.com/mike-fabian/ibus-typing-booster/releases.

# Building and installing from source 🛠️ {#building-and-installing-from-source}

When using a git checkout, go to the directory of the checkout and use autogen.sh:

```
$ cd ibus-typing-booster
$ ./autogen.sh
```
`autogen.sh` automatically runs configure and you can give the same arguments to `autogen.sh` you can give to configure. See [below for the right arguments for your distribution](#distribution-specific-stuff).

When using the source from a [release tarball](https://github.com/mike-fabian/ibus-typing-booster/releases), unpack the tarball and go into the source directory:
```
$ tar xvf ibus-typing-booster-2.27.53.tar.gz
$ cd ibus-typing-booster-2.27.53
```

Now continue like this:

```
$ ./configure --prefix=/usr --libexecdir=/usr/libexec/  # on Fedora
# ./configure --prefix=/usr --libexecdir=/usr/lib/ibus/ # on most other distributions
$ make
$ make check # optional
$ make install
```

**For all distributions:** please use `--prefix=/usr` and **not** the
default `/usr/local`, installing into `/usr/local` will usually not
work!

And use the correct `--libexecdir` option for your distribution, the
default is `--libexecdir=/usr/libexec` which is correct for Fedora,
but on openSUSE and Debian based distributions and Alpine Linux it is
`--libexecdir=/usr/lib/ibus`!

# Build requirements {#build-requirements}

To build ibus-typing-booster, you will need at least (Package names
may differ depending on your
[distribution](#distribution-specific-stuff)!):

- autoconf
- automake
- gettext-devel
- python3-devel >= 3.6
- ibus-devel >= 1.5.3

If you build from a git checkout and not from a release tarball, you
also need:

- autopoint (might already be in the gettext-devel package)

If you also want to run the test-suite with “make check”, you also
need the following packages:

- m17n-lib
- m17n-db-extras
- python3-enchant or pyhunspell-python3
- hunspell-cs
- hunspell-de
- hunspell-en
- hunspell-es
- hunspell-it
- hunspell-ko

Now you can [build and install](#building-and-installing-from-source).

# Runtime requirements {#runtime-requirements}

To run `ibus-typing-booster`, the following software is required or
optional for additional features (Package names may differ depending
on your [distribution](#distribution-specific-stuff)!):

### Required

- ibus >= 1.5.3
- m17n-lib
- m17n-db
- python3 >= 3.6
- python3-dbus
- python3-pyxdg
- python3-packaging

### Optional

- **python3-enchant** or **pyhunspell-python3**: Needed if you want
    spell-checking suggestions to work. Both packages work equally
    well, it doesn’t matter which one you choose.

- **hunspell-***: Hunspell dictionaries for the languages you want to
    type. If they are not there, ibus-typing-booster will still work
    but only learn from user input. With the hunspell dictionaries and
    the above Python modules to use them one will also get
    spell-checking suggestions and if no good suggestions can be found
    in the data gathered from user input, the word lists from the
    hunspell dictionaries will be used as a fallback to offer at least
    some suggestions.

- **python3-rapidfuzz**: Makes the matching of emoji and Unicode
    characters faster.

- **Fonts**: Install fonts for all language you need. Installing a
    nice font for emoji is also recommended.

- **m17n-db-extras**: for some additional Japanese and Chinese input
    methods.

- **m17n-lib-anthy**: if you want to type Japanese using `ja-anthy`.

- **[pykakasi](https://github.com/miurahr/pykakasi)**: Only needed if
    you want to input emoji by typing their Japanese names in romaji
    (i.e. Latin transliteration). That is an alternative to using the
    Japanese input method “ja-anthy” to type the names of the emoji in
    hiragana. There is no “pykakashi” package for Fedora, if you want
    this feature you need to install it from source.

- **[pinyin](https://pypi.python.org/pypi/pinyin)**: A Python module
    to convert Chinese text into pinyin. This is only needed if you
    want to type emoji by typing the Chinese names of the emoji in
    pinyin Latin transliteration. There is no “pinyin” for Fedora, if
    you want this feature you need to install it from source.

# Running from a source tree 🌳🏃‍♀️‍➡️ {#running-from-a-source-tree}

To run Typing Booster directly from the source directory (unpacked tar
or git clone), follow these steps:

#### Build

Build as [usual](#building-and-installing-from-source), just omit the `make
install` at the end.

#### Check and Kill Any Running Instances

Before starting, ensure no other Typing Booster process is active. You
can check and terminate it using one of these methods:

**Using** `pgrep` **and** `pkill`:

```bash
$ pgrep -u ${USER} -a -f ibus-typing-booster/engine/main.py
2803020 /usr/bin/python3 /usr/share/ibus-typing-booster/engine/main.py --ibus
$ pkill -u ${USER} -f ibus-typing-booster/engine/main.py
```

**Using** `ps` **and** `kill`:

```bash
$ ps aux | grep ibus-typing-booster/engine/main.py
mfabian  2803020  8.1  1.4 2617344 474388 ?      SLl  23:33   0:04 /usr/bin/python3 /usr/share/ibus-typing-booster/engine/main.py --ibus
$ kill 2803020
```

#### Start Typing Booster from Source

From the top-level source directory, run:

```bash
$ python3 ./engine/main.py --profile
```

(Alternatively, `python3 ../ibus-typing-booster/engine/main.py
--profile` works too. Using the full path makes it easier to grep for
the process later.)

#### Switch to Typing Booster in IBus

- First, switch to any other IBus engine (e.g., a plain keyboard
  layout) using `Super+space` or the system panel.

- Then, switch back to Typing Booster. Since you already started it
  manually, IBus will reuse your local instance instead of launching
  the system-wide version.

#### Notes:

- `--profile` **flag (optional):** Enables profiling, logging performance
  data to `~/.local/share/ibus-typing-booster/debug.log` when the
  process exits.

- **Debug logging:** To monitor logs in real-time:

  ```bash
  $ tail -F ~/.local/share/ibus-typing-booster/debug.log
  ```

  Filter output for specific functions (e.g., key events or preedit updates):

  ```bash
  $ tail -F ~/.local/share/ibus-typing-booster/debug.log | grep -E 'do_process_key_event|_update_preedit'
  ```

- **Debug level:** Adjust verbosity in the setup tool—higher levels log more details.

- **New gsettings options**: If you added any new gsettings options
    (rare), the schema file needs to be installed systemwide and compiled, otherwise Typing Booster
    and the setup tool trying to use the new options will fail:

  ```bash
  $ sudo cp org.freedesktop.ibus.engine.typing-booster.gschema.xml /usr/share/glib-2.0/schemas
  $ sudo glib-compile-schemas /usr/share/glib-2.0/schemas/
  ```

# Distribution specific stuff for building, installing, and running {#distribution-specific-stuff}

## Fedora {#building-and-installing-on-fedora}

### Build requirements

To build ibus-typing-booster, you will need at least:

- autoconf
- automake
- gettext-devel
- python3-devel >= 3.6
- ibus-devel >= 1.5.3

If you build from a git checkout and not from a release tarball, you
also need:

- autopoint (is already in the gettext-devel package)

If you also want to run the test-suite with “make check”, you also
need the following packages:

- m17n-lib
- m17n-db-extras
- python3-enchant or pyhunspell-python3
- hunspell-cs
- hunspell-de
- hunspell-en
- hunspell-es
- hunspell-it
- hunspell-ko

Now you can [build and install](#building-and-installing-from-source).

### Runtime requirements

#### Required

- ibus >= 1.5.3
- m17n-lib
- m17n-db
- python3 >= 3.6
- python3-dbus
- python3-pyxdg
- python3-packaging

#### Optional

- **python3-enchant** or **pyhunspell-python3**: Needed if you want
    spell-checking suggestions to work. Both packages work equally
    well, it doesn’t matter which one you choose.

- **hunspell-***: Hunspell dictionaries for the languages you want to
    type. If they are not there, ibus-typing-booster will still work
    but only learn from user input. With the hunspell dictionaries and
    the above Python modules to use them one will also get
    spell-checking suggestions and if no good suggestions can be found
    in the data gathered from user input, the word lists from the
    hunspell dictionaries will be used as a fallback to offer at least
    some suggestions.

- **python3-rapidfuzz**: Makes the matching of emoji and Unicode
    characters faster.

- **Fonts**: Install fonts for all language you need. Installing a
    nice font for emoji is also recommended.

- **m17n-db-extras**: for some additional Japanese and Chinese input
    methods.

- **m17n-lib-anthy**: if you want to type Japanese using `ja-anthy`.

- **[pykakasi](https://github.com/miurahr/pykakasi)**: Only needed if
    you want to input emoji by typing their Japanese names in romaji
    (i.e. Latin transliteration). That is an alternative to using the
    Japanese input method “ja-anthy” to type the names of the emoji in
    hiragana. There is no “pykakashi” package for Fedora, if you want
    this feature you need to install it from source.

- **[pinyin](https://pypi.python.org/pypi/pinyin)**: A Python module
    to convert Chinese text into pinyin. This is only needed if you
    want to type emoji by typing the Chinese names of the emoji in
    pinyin Latin transliteration. There is no “pinyin” for Fedora, if
    you want this feature you need to install it from source.

## openSUSE {#building-and-installing-on-opensuse}

### Build requirements

To build ibus-typing-booster, you will need at least:

- autoconf
- automake
- python3-devel >= 3.6
- ibus-devel >= 1.5.3

If you build from a git checkout and not from a release tarball, you
also need:

- autopoint

If you also want to run the test-suite with “make check”, you also
need the following packages:

- m17n-lib
- m17n-db
- python3-pyenchant
- myspell-cs_CZ
- myspell-de
- myspell-de_DE
- myspell-en
- myspell-en_US
- myspell-es
- myspell-es_ES
- myspell-it_IT
- python3-gobject
- dbus-1-x11

Now you can [build and install](#building-and-installing-from-source)
but remember to use `--libexecdir=/usr/lib/ibus/` when running `./configure` or
`./autogen.sh`!

### Runtime requirements

#### Required

- ibus >= 1.5.3
- m17n-lib
- m17n-db
- python3 >= 3.6
- dbus-1-python3
- python3-pyxdg
- python3-packaging

#### Optional

- **python3-pyenchant**: Needed if you want spell-checking suggestions to work.

- **myspell-***: Hunspell dictionaries for the languages you want to
    type. If they are not there, ibus-typing-booster will still work
    but only learn from user input. With the hunspell dictionaries and
    the above Python modules to use them one will also get
    spell-checking suggestions and if no good suggestions can be found
    in the data gathered from user input, the word lists from the
    hunspell dictionaries will be used as a fallback to offer at least
    some suggestions.

- **Fonts**: Install fonts for all language you need. Installing a
    nice font for emoji is also recommended.

- **[pykakasi](https://github.com/miurahr/pykakasi)**: Only needed if
    you want to input emoji by typing their Japanese names in romaji
    (i.e. Latin transliteration). That is an alternative to using the
    Japanese input method “ja-anthy” from m17n-db-extras to type the
    names of the emoji in hiragana. There is no “pykakashi” package
    for Fedora, if you want this feature you need to install it from
    source.

- **[pinyin](https://pypi.python.org/pypi/pinyin)**: A Python module
    to convert Chinese text into pinyin. This is only needed if you
    want to type emoji by typing the Chinese names of the emoji in
    pinyin Latin transliteration. There is no “pinyin” for Fedora, if
    you want this feature you need to install it from source.

## Ubuntu {#building-and-installing-on-ubuntu}

### Build requirements

To build ibus-typing-booster, you will need at least:

- autoconf
- automake
- python3 >= 3.6
- ibus >= 1.5.3
- libibus-1.0-dev >= 1.5.3
- make
- gcc

If you build from a git checkout and not from a release tarball, you
also need:

- autopoint

If you also want to run the test-suite with “make check”, you also
need the following packages:

- libm17n-0
- m17n-db
- python3-enchant
- hunspell-de-de
- hunspell-cs
- hunspell-es
- hunspell-it
- hunspell-ko

Now you can [build and install](#building-and-installing-from-source)
but use `--libexecdir=/usr/lib/ibus/` when running `./configure` or
`./autogen.sh`!

### Runtime requirements

#### Required

- ibus >= 1.5.3
- libm17n-0
- m17n-db
- python3 >= 3.6
- python3-dbus
- python3-xdg
- python3-packaging

#### Optional

- **python3-enchant** : Needed if you want spell-checking suggestions to work.

- **hunspell-***: Hunspell dictionaries for the languages you want to
    type. If they are not there, ibus-typing-booster will still work
    but only learn from user input. With the hunspell dictionaries and
    the above Python modules to use them one will also get
    spell-checking suggestions and if no good suggestions can be found
    in the data gathered from user input, the word lists from the
    hunspell dictionaries will be used as a fallback to offer at least
    some suggestions.

- **Fonts**: Install fonts for all language you need. Installing a
    nice font for emoji is also recommended.

- **[pykakasi](https://github.com/miurahr/pykakasi)**: Only needed if
    you want to input emoji by typing their Japanese names in romaji
    (i.e. Latin transliteration). That is an alternative to using the
    Japanese input method “ja-anthy” from m17n-db-extras to type the
    names of the emoji in hiragana. There is no “pykakashi” package
    for Fedora, if you want this feature you need to install it from
    source.

- **[pinyin](https://pypi.python.org/pypi/pinyin)**: A Python module
    to convert Chinese text into pinyin. This is only needed if you
    want to type emoji by typing the Chinese names of the emoji in
    pinyin Latin transliteration. There is no “pinyin” for Fedora, if
    you want this feature you need to install it from source.

## Alpine Linux {#building-and-installing-on-alpine}

### Build requirements:

To build ibus-typing-booster, you will need at least:

- autoconf
- automake
- python3 >= 3.6
- gettext
- gettext-dev
- ibus
- ibus-dev
- make
- gcc

If you build from a git checkout and not from a release tarball, you also need:

- autopoint (is already in the gettext package)

If you also want to run the test-suite with “make check”, you also need the following packages:

- libm17n-core
- libm17n-flt
- m17n-db
- m17n-db-dev
- m17n-lib
- m17n-lib-dev
- hunspell-en
- hunspell-de-de
- py3-enchant

Now you can [build and install](#building-and-installing-from-source)
but use `--libexecdir=/usr/lib/ibus/` when running `./configure` or
`./autogen.sh`!

### Runtime requirements

#### Required

- ibus >= 1.5.3
- libm17n-core
- libm17n-flt
- m17n-db
- python3 >= 3.6
- py3-dbus
- py3-xdg
- py3-packaging

#### Optional

- **py3-enchant** : Needed if you want spell-checking suggestions to
    work.

- **hunspell-***: Hunspell dictionaries for the languages you want to
    type. If they are not there, ibus-typing-booster will still work
    but only learn from user input. With the hunspell dictionaries and
    the above Python modules to use them one will also get
    spell-checking suggestions and if no good suggestions can be found
    in the data gathered from user input, the word lists from the
    hunspell dictionaries will be used as a fallback to offer at least
    some suggestions.

- **Fonts**: Install fonts for all language you need. Installing a
    nice font for emoji is also recommended.

- **[pykakasi](https://github.com/miurahr/pykakasi)**: Only needed if
    you want to input emoji by typing their Japanese names in romaji
    (i.e. Latin transliteration). That is an alternative to using the
    Japanese input method “ja-anthy” from m17n-db-extras to type the
    names of the emoji. There is no “pykakashi” package for Alpine
    Linux, if you want this feature you need to install it from source
    or using pip.

- **[pinyin](https://pypi.python.org/pypi/pinyin)**: A Python module
    to convert Chinese text into pinyin. This is only needed if you
    want to type emoji by typing the Chinese names of the emoji in
    pinyin Latin transliteration. There is no “pinyin” for Fedora, if
    you want this feature you need to install it from source or using
    pip.

