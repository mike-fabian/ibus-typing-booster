---
title: Developer Documentation 👩‍🔧
date: 2021-08-28
---

Ibus-typing-booser is open source and licensed under the GPL version 3.

## Reporting bugs 🐞
You can report bugs and suggest improvements in the github issue tracker: https://github.com/mike-fabian/ibus-typing-booster/issues

## Translation 🇺🇳
You can contribute translations for ibus-typing-booster using the online translation platform weblate: https://translate.fedoraproject.org/projects/ibus-typing-booster/.

If you cannot use weblate, you can also create a pull request for new or updated translations.

## Mailing list 📬
https://lists.fedorahosted.org/admin/lists/ibus-typing-booster.lists.fedorahosted.org/

## Browse git repository 🐱

You can browse the source code at https://github.com/mike-fabian/ibus-typing-booster.

## Anonymous git clone
```
$ git clone git://github.com/mike-fabian/ibus-typing-booster.git
```

## Authorized git clone
```
$ git clone git@github.com:mike-fabian/ibus-typing-booster.git
```
## Release tarballs
Release tarballs are available at https://github.com/mike-fabian/ibus-typing-booster/releases.

## Building and installing from source 🛠️

### Required packages for building
To build ibus-typing-booster, you will need at least:
- **Fedora:** autoconf, automake, gettext-devel, python3-devel >= 3.3, ibus-devel >= 1.5.3
- **openSUSE:** autoconf, automake, python3-devel >= 3.5, ibus-devel >= 1.5.3
- **Ubuntu 20.04:** autoconf, automake, python3 >= 3.5, ibus >= 1.5.3, libibus-1.0-dev >= 1.5.3, make, gcc

If you build from a git checkout and not from a release tarball, you also need:

- **Fedora:** autopoint
- **openSUSE:** autopoint
- **Ubuntu 20.04:** autopoint

If you also want to run the test-suite with “make check”, you also need the following packages:

- **Fedora:** m17n-lib, m17n-db-extras, python3-enchant or pyhunspell-python3, hunspell-cs, hunspell-de, hunspell-en, hunspell-es, hunspell-it, hunspell-ko
- **openSUSE Leap 42.1 and newer:** m17n-lib, m17n-db, python3-pyenchant, myspell-cs_CZ, myspell-de, myspell-de_DE, myspell-en, myspell-en_US, myspell-es, myspell-es_ES, myspell-it_IT, python3-gobject, dbus-1-x11
- **Ubuntu 20.04:** libm17n-0, m17n-db, python3-enchant, hunspell-de-de, hunspell-cs, hunspell-es, hunspell-it, hunspell-ko

## Building and installing using the source 🛠️

When using a git checkout, go to the directory of the checkout and use autogen.sh:
```
$ cd ibus-typing-booster
$ ./autogen.sh
```
`autogen.sh` automatically runs configure and you can give the same arguments to `autogen.sh` you can give to configure. See below for the right arguments for your distribution.

When using the source from a [release tarball](https://github.com/mike-fabian/ibus-typing-booster/releases), unpack the tarball and go into the source directory:
```
$ tar xvf ibus-typing-booster-2.7.0.tar.gz
$ cd ibus-typing-booster-2.7.0
```

Now continue like this:

**Fedora:**
```
$ ./configure --prefix=/usr --libexecdir=/usr/libexec/
$ make
$ make check # optional
$ make install
```

**openSUSE Leap 42.1 and newer:**
```
$ ./configure --prefix=/usr --libexecdir=/usr/lib/ibus
$ make
$ make check # optional
$ make install
```

**Ubuntu 20.04:**
```
$ ./configure --prefix=/usr --libexecdir=/usr/lib/ibus
$ make
$ make check # optional
$ make install
```

**For all distributions:** please use `--prefix=/usr` and **not** the default `/usr/local`, installing into `/usr/local` will usually not work! And use the correct `--libexecdir` option for your distribution, the default is `--libexecdir=/usr/libexec` which is correct for Fedora, but on openSUSE and Debian based distributions it is `--libexecdir=/usr/lib/ibus`!

### Required and optional packages for running

**Note about m17n-lib:** m17n-lib is required to use ibus-typing-booster but unfortunately the latest released version (currently 1.7.0) has a serious bug which causes a crash when using ibus-typing-booster. To fix this bug you need my [patch](http://git.savannah.nongnu.org/cgit/m17n/m17n-lib.git/commit/?id=70126a8fd252ee5c0cb8ab66b72cea39b472121e) from the upstream git repository (Patch also discussed [here](https://lists.nongnu.org/archive/html/m17n-list/2015-08/msg00001.html) and [here](https://lists.nongnu.org/archive/html/m17n-list/2015-08/msg00002.html)). Some distributions like Fedora >= 23 already have this patch, some don’t. For Debian there is [this bugreport](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=856959) requesting to include the patch.

To run `ibus-typing-booster`, the following software is required or optional for additional features:
### Fedora

**Required:**
* ibus >= 1.5.3
* m17n-lib
* m17n-db
* python3 >= 3.3
* python3-dbus
* python3-pyxdg
* python3-packaging

**Optional:**
* **python3-enchant** or **pyhunspell-python3**: Needed if you want spell-checking suggestions to work. Both packages work equally well, it doesn’t matter which one you choose.
* **hunspell-***: Hunspell dictionaries for the languages you want to type. If they are not there, ibus-typing-booster will still work but only learn from user input. With the hunspell dictionaries and the above Python modules to use them one will also get spell-checking suggestions and if no good suggestions can be found in the data gathered from user input, the word lists from the hunspell dictionaries will be used as a fallback to offer at least some suggestions.
* **gdouros-symbola-fonts** (or any other good font for symbols and emoji): Only needed if you want to input emoji, without a good emoji font you will see lots of boxes or replacement characters when trying to type emoji.
* **m17n-db-extras**: for some additional Japanese and Chinese input methods, most users won’t need this, it is only helpful if you want to match emoji by typing their Japanese names in hiragana by using the “ja-anthy” input method.
* **[pykakasi](https://github.com/miurahr/pykakasi)**: Only needed if you want to input emoji by typing their Japanese names in romaji (i.e. Latin transliteration). That is an alternative to using the Japanese input method “ja-anthy” from m17n-db-extras to type the names of the emoji in hiragana. There is no “pykakashi” package for Fedora, if you want this feature you need to install it from source.
* **[pinyin](https://pypi.python.org/pypi/pinyin)**: A Python module to convert Chinese text into pinyin. This is only needed if you want to type emoji by typing the Chinese names of the emoji in pinyin Latin transliteration. There is no “pinyin” for Fedora, if you want this feature you need to install it from source.

### openSUSE

**Required:**
* ibus >= 1.5.3
* m17n-lib
* m17n-db
* python3 >= 3.3
* dbus-1-python3
* python3-pyxdg
* python3-packaging

**Optional:**
* **python3-pyenchant**: Needed if you want spell-checking suggestions to work.
* **myspell-***: Hunspell dictionaries for the languages you want to type. If they are not there, ibus-typing-booster will still work but only learn from user input. With the hunspell dictionaries and the above Python modules to use them one will also get spell-checking suggestions and if no good suggestions can be found in the data gathered from user input, the word lists from the hunspell dictionaries will be used as a fallback to offer at least some suggestions.
* **gdouros-symbola-fonts** (or any other good font for symbols and emoji): Only needed if you want to input emoji, without a good emoji font you will see lots of boxes or replacement characters when trying to type emoji. The version in openSUSE might be quite old, if it is not for the currently released version of Unicode, better get the latest version of the Symbola font from [upstream](http://users.teilar.gr/~g1951d/).
* **[pykakasi](https://github.com/miurahr/pykakasi)**: Only needed if you want to input emoji by typing their Japanese names in romaji (i.e. Latin transliteration). That is an alternative to using the Japanese input method “ja-anthy” from m17n-db-extras to type the names of the emoji in hiragana. There is no “pykakashi” package for Fedora, if you want this feature you need to install it from source.
* **[pinyin](https://pypi.python.org/pypi/pinyin)**: A Python module to convert Chinese text into pinyin. This is only needed if you want to type emoji by typing the Chinese names of the emoji in pinyin Latin transliteration. There is no “pinyin” for Fedora, if you want this feature you need to install it from source.

### Ubuntu 20.04

**Required:**
* ibus >= 1.5.3
* libm17n-0
* m17n-db
* python3 >= 3.3
* python3-dbus
* python3-xdg
* python3-packaging

**Optional:**
* **python3-enchant** : Needed if you want spell-checking suggestions to work.
* **hunspell-***: Hunspell dictionaries for the languages you want to type. If they are not there, ibus-typing-booster will still work but only learn from user input. With the hunspell dictionaries and the above Python modules to use them one will also get spell-checking suggestions and if no good suggestions can be found in the data gathered from user input, the word lists from the hunspell dictionaries will be used as a fallback to offer at least some suggestions.
* **fonts-symbola** (or any other good font for symbols and emoji): Only needed if you want to input emoji, without a good emoji font you will see lots of boxes or replacement characters when trying to type emoji. The version in Ubuntu 16.04 seems to be quite old (for Unicode 7.0), better get the latest version of the Symbola font from [upstream](http://users.teilar.gr/~g1951d/).
* **[pykakasi](https://github.com/miurahr/pykakasi)**: Only needed if you want to input emoji by typing their Japanese names in romaji (i.e. Latin transliteration). That is an alternative to using the Japanese input method “ja-anthy” from m17n-db-extras to type the names of the emoji in hiragana. There is no “pykakashi” package for Fedora, if you want this feature you need to install it from source.
* **[pinyin](https://pypi.python.org/pypi/pinyin)**: A Python module to convert Chinese text into pinyin. This is only needed if you want to type emoji by typing the Chinese names of the emoji in pinyin Latin transliteration. There is no “pinyin” for Fedora, if you want this feature you need to install it from source.
