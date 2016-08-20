---
layout: post
title:  "Multilingual input implemented in ibus-typing-booster >= 1.4.0"
author: Mike FABIAN
---

<p>Since version 1.4.0, ibus-typing-booster supports using more than
one input method/transliteration at the same time. I.e. one can use
several languages at the same time without having to switch between
different language engines of ibus-typing-booster.</p>

<p>Using the graphical setup tool one can currently only add English
as a second language to whatever the main language of that engine
is. But that is only a limitation of the setup tool, when doing the
setup manually from the command line, up to 10 transliterations (input
methods) and an unlimited number of dictionaries can be used at the
same time.</p>

<p>But a user should enable only the transliterations and dictionaries
which are really useful to him.  All enabled transliterations are
searched in all enabled dictionaries. This slows down the system and
if the user doesn’t really need these transliterations and dictionaries
it would lower the prediction/completion quality for him because
some completions might come from these unneeded transliterations
and dictionaries.
</p>

<p>For details how to setup this new feature see <a
href="{{ site.github.url }}/documentation#multilingual-input">Multilingual input</a>.</p>