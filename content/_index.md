---
title: 
---

{{<
figure src="images/typing-emoji-and-context-sensitive-completion.png"
>}}

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
* Open source (GPL 3)

-------------

# Demo

{{<
video label="Demo of Typing Booster and Emoji Picker"
webm="videos/overview-demo-setup-use-typing-booster-emoji-picker.webm"
>}}

-------------

[🐞 Bugs](https://github.com/mike-fabian/ibus-typing-booster/issues)
|
[🇺🇳 Translations](https://translate.fedoraproject.org/projects/ibus-typing-booster)
|
[🐱 Github](https://github.com/mike-fabian/ibus-typing-booster)
|
[📖 Documentation](https://mike-fabian.github.io/ibus-typing-booster/docs/)
|
[🎁 Downloads](https://mike-fabian.github.io/ibus-typing-booster/downloads/)