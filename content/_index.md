---
title: 
---

| Downloads |
|-----|------|
|[Fedora](https://apps.fedoraproject.org/packages/ibus-typing-booster)| [OpenSUSE](https://build.opensuse.org/package/show/M17N/ibus-typing-booster)|
|[Ubuntu](https://launchpad.net/ubuntu/+source/ibus-typing-booster)|[Debian](https://packages.debian.org/sid/ibus-typing-booster)| 
|[Arch linux](https://www.archlinux.org/packages/extra/any/ibus-typing-booster)|[FreeBSD port](http://www.freshports.org/textproc/ibus-typing-booster)| 
|[Repology (Overview for all distros)](https://repology.org/project/ibus-typing-booster/versions)| [Source tarballs](https://github.com/mike-fabian/ibus-typing-booster/releases)|

----------

# Introduction

Ibus-typing-booster is a completion input method to speedup typing.

The project was started in 2010 for Fedora 15. The original purpose was to make typing of Indic languages easier and faster by providing completion and spell checking suggestions.

Originally it was forked from ibus-table whose developer was ```Yu Yuwei``` acevery@gmail.com, with contributions from ```Caius("kaio") Chance``` me@kaio.net.

Since then ibus-typing-booster has been improved to support many other languages as well (most languages except Chinese and Japanese are supported).

Recently the capapility to type different languages at the same time without having to switch between languages has been added.

Developers:
```
Mike FABIAN mfabian@redhat.com
Anish Patil anish.developer@gmail.com
```

-------------

# Features
* Context sensitive completions.
* Learns from user input.
* Can be trained by supplying files containing typical user input.
* If available, hunspell and hunspell dictionaries will also be used to provide not only completion but also spellchecking suggestions (But ibus-typing-booster works also without hunspell by learning only from user input).
* Can be used with any keyboard layout.
* Almost all input methods supplied by libm17n are supported (including the inscript2 input methods).
* Several input methods and languages can be used at the same time without switching.
* Predicts Unicode symbols and emoji as well.

-------------

# Demo

 <div class="video-container"> 
    <iframe width="560" height="315" src="https://www.youtube.com/embed/8YsBy2hiV_I" frameborder="0" allowfullscreen=""></iframe>   
 </div>  
 <style> .video-container { position:relative; padding-bottom:56.25%; padding-top:30px; height:0; overflow:hidden; } .video-container iframe, .video-container object, .video-container embed { position:absolute; top:0; left:0; width:100%; height:100%; }  
 </style>
