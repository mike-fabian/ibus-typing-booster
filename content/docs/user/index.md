---
title: User Documentation
date: 2021-08-30
---

## Contents

1. [Installing ibus-typing-booster](#0)
1. [Adding ibus-typing-booster to your desktop](#1)
    * [When using the Gnome3 desktop](#1_1)
    * [When using older Gnome3 desktops like in Ubuntu 21.04](#1_2)
    * [When using other desktops than Gnome3](#1_3)
    * [When using the Unity desktop on Ubuntu 16.04](#1_4)
1. [Setup](#2)
    * [Basic setup for your language](#2_1)
    * [More advanced options](#2_2)
        * [Enable suggestions by a key](#2_2_1)
            * [Simulate the behaviour of ibus-m17n](#2_2_1_1)
        * [Use inline completion](#2_2_2)
            * [Inline completion is hard to use on Wayland](#2_2_2_1)
        * [Spellchecking](#2_2_3)
1. [Key and Mouse bindings](#3)
    * [The “AltGr” key](#3_1)
    * [Table of default key bindings](#3_2)
    * [Mouse bindings](#3_3)
    * [Customizing key bindings](#3_4)
1. [Multilingual input](#4)
    * [Example using Hindi and English at the same time](#4_1)
    * [Example using Spanish and English at the same time](#4_2)
1. [Compose support (About dead keys and the Compose key)](#5)
    * [“Dead keys”](#5_1)
    * [The “Compose” key](#5_2)
    * [Customizing compose sequences](#5_3)
    * [Special “Compose” features in Typing Booster](#5_4)
        * [Why Typing Booster has its own “Compose” implementation](#5_4_1)
        * [Automatically add “missing” dead key sequences](#5_4_2)
        * [Fallbacks for “missing” keypad sequences](#5_4_3)
        * [How undefined sequences are handled](#5_4_4)
        * [Show possible completions of compose sequences](#5_4_5)
            * [A peculiarity of Gnome3 and compose completions](#5_4_5_1)
        * [Optional colour for the compose preëdit](#5_4_6)
1. [Unicode symbols and emoji predictions](#6)
    * [Emoji input](#6_1)
    * [Emoji input fuzzy matching](#6_2)
    * [Emoji input using multiple keywords](#6_3)
    * [Looking up related emoji](#6_4)
    * [Multilingual emoji input](#6_5)
        * [Emoji input using German and English](#6_5_1)
        * [Emoji input using Hindi and English](#6_5_2)
        * [Emoji input using Japanese](#6_5_3)
    * [Unicode symbol input](#6_6)
    * [Unicode code point input](#6_7)
    * [Quickly toggling emoji mode on and off](#6_8)
    * [Emoji picker](#6_9)
    * [Emoji fonts](#6_10)
        * [<span style="color:red">Historic:</span> Showing emoji in colour](#6_10_1)
1. [Using NLTK to find related words](#7)
1. [Speech recognition](#8)
---------

###### 0
## Installing ibus-typing-booster

For most distributions, there are binary packages available
already. Here are some examples for common distributions how you can
install ibus-typing-booster (and optionally emoji-picker) using
package managers on the command line:

* Fedora:
    * `sudo dnf install ibus-typing-booster`
    * `sudo dnf install emoji-picker` (optional)
* Debian, Ubuntu:
    * `sudo apt-get install ibus-typing-booster` (includes emoji-picker already! 😁)
* openSUSE:
    * `sudo zypper install ibus-typing-booster` (includes emoji-picker already! 😁)

If your distribution has no binary packages or you are want to have
the bleeding edge version and install from source, see the [Developer
Documentation](/docs/dev/). There you can also find information on how
to report bugs or translate the user interface into your language.

Some distributions also have graphical tools to install software
(“Gnome Software”, “Ubuntu Software”, ...). The following video shows
how one can install ibus-typing-booster and emoji-picker on Ubuntu
21.04 using “Ubuntu Software”. “Ubuntu Software” shows
ibus-typing-booster and emoji-picker as two entries, but after
installing ibus-typing-booster, emoji-picker has been installed as
well already, although “Ubuntu Software” does not appear to know that
and still lets me click on “Install” for emoji-picker. But as it was actually
already installed, it finishes immediately 😀.

**Note**: when using Gnome, don’t forget to log out of your desktop
and log in again after installing!  On most other desktops one can
often avoid that by calling `ibus restart` from the command line but
on Gnome one has to log out and log in again, otherwise one will not
find ibus-typing-booster when trying to [add it it in the desktop
settings](#1).

{{< video label="Installing using “Ubuntu Software” on Ubuntu 21.04" webm="/videos/user-docs/installing-using-ubuntu-software-on-ubuntu-21.04.webm" >}}

###### 1
## Adding ibus-typing-booster to your desktop

This section assumes that you have already installed ibus-typing-booster either using binary packages or from source and now want to add an ibus-typing-booster input method to your desktop.

The procedure to add an ibus-typing-booster input method differs slightly depending on which type of desktop you use, the following sections show the procedure for popular desktop choices.


###### 1_1
## When using the Gnome3 desktop

{{< video label="Adding ibus-typing-booster to the Gnome3 desktop" webm="/videos/user-docs/When-using-the-Gnome3-desktop.webm" >}}

This video shows how to add ibus-typing-booster to recent Gnome3
desktops, using Gnome3 on Fedora 34 in this example. In older versions
of Gnome3, the input method setup was in the “Region & Language”
settings instead of in the “Keyboard” settings, for example [Ubuntu
21.04 has such an older version of Gnome](#1_2).

1. First click on the panel menu in the top right corner of the desktop and then click on the “screwdriver and wrench” icon to open the Gnome3 control center.

1. Now the Gnome3 control center has opened. Click on the icon for the “Keyboard” settings.

1. At the bottom you see a list of input sources which have already been added to the desktop before. In this case there are already: “English (US, with euro on 5)” and “Japanese (Kana Kanji)”. This is just an example of course, the list of already added input methods could look different for you. The first entry, “English (US, with euro on 5)”, is not really an input engine, it is just a keyboard layout. One can see that an entry in the list of input sources is a keyboard layout if it does not have the icon showing two tooth-wheels at the right side.

    It is recommended to use a keyboard layout with ibus-typing-booster which has a real “AltGr” key and does not just make the “AltGr” or “Alt” key on the right side of the space bar basically a duplicate of the left “Alt” key. For details, see The [“AltGr” key](#3_1).

    The second entry, “Japanese (Kana Kanji)” is not just a keyboard layout, it is an input engine to type Japanese.

    Now click on the “+” button at the lower left to add another input source.

1. Then click on the three vertical dots “⋮” to open the search entry field.

1. Type the word “booster” into the search entry field. Only “Other” remains. ibus-typing-booster supports many languages, even at the same time. Therefore it is not listed under any specific language but under “Other”.

1. Click on “Other” and you should find an input method named “Other (Typing Booster)” there. There maybe lots of other input methods shown there, depending on what is installed on your system, but if you have ibus-typing-booster installed, “Other (Typing Booster)” should show up there.

    Select “Other (Typing Booster)” and click the “Add” button at the top right.

    (**Note:** If you just installed ibus-typing-booster while your current gnome session was still running, you will not find ibus-typing-booster yet. In that case you need to restart your gnome session in order to make newly installed input methods appear in the gnome setup.)

1. Now you you see the ibus-typing-booster engine listed in the “Keyboard” dialogue of Gnome3.

    At the right side of the entry “Other (Typing Booster)” there are three vertical dots “⋮”. If you click on these, a menu opens. One of the entries in that menu is “Preferences”. Clicking that opens the setup tool of the ibus-typing-booster engine.

1. Now open some programs where you could type something, for example “gedit” or “gnome-terminal”. And activate the ibus-typing-booster engine you want to use in the input source menu of the Gnome panel as shown in this screenshot.

    When the input source menu of the Gnome panel is open and an ibus-typing-booster engine is selected, there is a menu entry “Setup” which is an quicker way to open the setup tool than going to the “Region & Language” settings dialogue.

    Some options are also directly available in the input source menu of the gnome panel to have quicker access to these often used options than having to open the setup tool. There are also [key and mouse bindings](#3) for these frequently used options which are shown in the input source menu of the gnome panel as well as a reminder.

1. Now type something, for example into gedit and you should see some suggestions for completions.

    At the beginning, the suggestions only come from the hunspell dictionaries and are thus not very good yet. But ibus-typing-booster learns from your typing, it remembers which words you use often in which context. Therefore, the suggestions become much better over time.

    To switch between ibus-typing-booster and other input methods or a simple keyboard layout, you can use the input sources menu in the Gnome panel or the keyboard shortcut, which is Super+Space by default (can be changed in the gnome-control-center).

###### 1_2
## When using older Gnome3 desktops like in Ubuntu 21.04

{{< video label="Adding ibus-typing-booster to older Gnome3 desktops like in Ubuntu 21.04" webm="/videos/user-docs/When-using-Ubuntu-21.04.webm" >}}

This video shows how to add ibus-typing-booster to older Gnome3 desktops
like for example in Ubuntu 21.04 where the input method setup was still
in the “Region & Language” settings instead of in the “Keyboard” settings.
For adding ibus-typing-booster in newer versions of Gnome look [here](#1_1).

###### 1_3
## When using other desktops than Gnome3

{{< video label="When using other desktops than Gnome3" webm="/videos/user-docs/When-using-other-desktops-than-Gnome3.webm" >}}

This chapter shows how to add the ibus-typing-booster input method on most desktops except Gnome3 and Unity. The screenshots in this chapter are using XFCE on Fedora 34, but it is the same procedure on most other desktops and window managers as well, only Gnome3 and Unity are a bit special.

1. First start the `ibus-setup` program (For example by typing `ibus-setup &` into a terminal.

1. If `ibus-daemon` is not yet running, `ibus-setup` may ask whether you want to start it. In that case click on “Yes”.

1. If `ibus-daemon` was not already running, you probably also want to make it run automatically every time when you log into your desktop. If you are using Fedora you can do that for most desktops and window managers using `imsettings-switch` like this:
`imsettings-switch ibus`. Or use the graphical tool `im-chooser` and select to use Ibus.

1. This will change some settings so that when you log in next time, `ibus-daemon` will be running and the following environment variables will be set:

    `export QT_IM_MODULE=ibus`

    `export XMODIFIERS=@im=ibus`

    `export GTK_IM_MODULE=ibus`

1. If you don’t use Fedora and do not have the `imsettings-switch`, there may be some other way to start `ibus-daemon` on your system automatically and to set the above environment variables.

    Or you can put the above environment variables into your `~/.bashrc` file and start `ibus-daemon` from some X11 startup file or make your windowmanager start it. I am using the “i3” windowmanager at the moment and have added the line `exec ibus-daemon -drx` to my `~/.config/i3/config` file.

1. In the “General” tab of `ibus-setup` you see that the default shortcut key to switch between input methods is “Super+Space” and you can change this and some other options if you like.

    Personally I like the extra property panel. Therefore, I set the “Show property panel” option to “Always” here.

    You probably also want the option “Show icon on system tray” switched on.

    And I usually choose a somewhat bigger font to be able to see the details in the emoji better.

1. Now use the “Input Method” tab of `ibus-setup` to add the ibus-typing-booster engine.

    You see a list of input sources which have already been added to the desktop before. In this case there are already: “English - English (US, euro on 5)” and “Japanese - Anthy”. This is just an example of course, the list of already added input methods could look different for you. The first entry, “English - English (US, euro on 5)”, is not really an input engine, it is just a keyboard layout.

    It is recommended to use a keyboard layout with ibus-typing-booster which has a real “AltGr” key and does not just make the “AltGr” or “Alt” key on the right side of the space bar basically a duplicate of the left “Alt” key. For details, see The [“AltGr” key](#3_1). By the way, in the “Advanced” tab of `ibus-setup` there is an option “Use system keyboard layout”, if this option is selected, ibus-typing-booster will always use the system keyboard layout, otherwise it will use the keyboard layout from the list of input methods which was used last before switching to ibus-typing-booster.

    The second entry which is already there in the list of input methods, “Japanese (Kana Kanji)”, is a real input engine, not a keyboard layout.

    Now click on the “Add” button at top right to add another input source.

1. Click on the three vertical dots “⋮” at the bottom to get the full list of languages. ibus-typing-booster supports many languages, even at the same time. Therefore it is not listed under any specific language but in the “Other” at the very bottom of the list. You could either scroll down to the “Other” section, click on it and then scroll again looking for “🚀 Typing Booster”, or you could use the search entry and search for “booster” for example.

1. When you find “🚀 Typing Booster”, select it and click the “Add” button.

1. Now the ibus-typing-booster engine has been added to the list of input methods configured in `ibus-setup`. If you select that “🚀 Typing Booster” in the list of configured input methods in `ibus-setup`, you can click the “Preferences” button to open the setup tool of the typing-booster engine. There you can customize ibus-typing-booster according to your preferences (You can also open the ibus-typing-booster setup tool later from the menu in the desktop panel).

1. Now open some programs where you could type something, for example “gedit” or “gnome-terminal”. And activate the ibus-typing-booster engine by clicking on the icon for the input methods in the system tray and selecting “Typing booster” there.

1. When the input method menu of system tray icon is open and “Typing booster” is selected, there is a menu entry “Setup” which is a quicker way to open the setup tool of “Typing Booster” then starting `ibus-setup` again. Some options are also directly available in the input method menu of the system tray icon to have quicker access to these often used options. 

1. Near the top right in this video you see the “property panel” which shows the current status of some frequently used options which can also be changed by clicking on the “property panel”. The “property panel” also offers a button to open the setup tool of the ibus-typing-booster engine. You can move that “property panel” to around on your desktop to a convenient place.

1. Now type something, for example into gedit and you should see some suggestions for completions.

    At the beginning, the suggestions only come from the hunspell dictionaries and are thus not very good yet. But ibus-typing-booster learns from your typing, it remembers which words you use often in which context. Therefore, the suggestions become much better over time.

    To switch between ibus-typing-booster and other input methods or a simple keyboard layout, you can use the input methods menu you get by clicking on the system tray icon or you can use the keyboard shortcut, which is Super+Space by default (can be changed using `ibus-setup`).


###### 1_4
## When using the Unity desktop on Ubuntu 16.04

{{<
figure src="/images/user-docs/When-using-the-Unity-desktop-on-Ubuntu.gif"
caption="Setup of Typing Booster on the Unity desktop of Ubuntu 16.04"
>}}

This section shows the setup of ibus-typing-booster on the “Unity” desktop of ubuntu-16.04.

<span style="color:red">The information in this chapter is pretty old, maybe I should delete it soon. Current Ubuntu doesn’t use “Unity” anymore. It uses Gnome3 and behaves quite similar to Gnome3 on other distributions. But the “Unity” desktop was quite a bit different.</span>

These instructions are for ibus-typing-booster 1.5.x. For ibus-typing-booster >= 2.0.0, all engines have been merged into one, so you won’t find many different “Typing Booster” engines for many different languages anymore, there is only one single “Typing Booster” engine now which supports all languages. That doesn’t make a big difference in these instructions though, so I hope it is not too confusing that the screenshots in this sections are not up-to-date with ibus-typing-booster >= 2.0.0.

1. Open the system settings by clicking on the icon showing a tooth-wheel and a wrench a the left side of the screen. Then click on the “Language Support” icon there. In the dialog which opens, make sure that “Keyboard input method system” is set to “IBus”.

    Close that “Language Support” dialogue again and click on the “Text Entry” icon in the system settings.

1. Some input sources may be already be listed at the left side of this dialogue. In this example we see “English (US, with euro on 5)” which is not really an input engine, it is just a keyboard layout.

    It is recommended to use a keyboard layout with ibus-typing-booster which has a real “AltGr” key and does not just make the “AltGr” or “Alt” key on the right side of the space bar basically a duplicate of the left “Alt” key. For details, see [The “AltGr” key](#3_1).

    Now click on the “+” button at the lower left to add another input source.

1. Type the word “booster” into the search entry and you see the currently available language variants of ibus-typing-booster. Select the variant of ibus-typing-booster you want to use and click on “Add”.

1. Now you see that an ibus-typing-booster engine has been added to the list of input sources to use.

    If you select it, a n icon showing a wrench and a screwdriver appears at the bottom right of the list, to the left of the icon showing a keyboard. Click the “wrench and screwdriver” icon to open the setup tool of ibus-typing-booster.

1. Here you see the setup tool of that ibus-typing-booster engine where you can customize ibus-typing-booster according to your preferences.

1. Now open some programs where you could type something, for example “gedit” or “gnome-terminal”. And activate the ibus-typing-booster engine you want to use in the input source menu of the panel as shown in this screenshot.

    When the input source menu of the panel is open and an ibus-typing-booster engine is selected, there is a menu entry “Setup” which is an quicker way to open the setup tool ibus-typing-booster setup tool than going via the system settings.

    Some options of ibus-typing-booster are also directly available in the input source menu of the panel to have quicker access to these often used options than having to open the setup tool. For example the option to switch emoji mode on or off is available in the panel menu. There are also [key and mouse bindings](#3) for these frequently used options which are shown in the input source menu of the panel as well as a reminder.

1. Now type something, for example into gedit and you should see some suggestions for completions.

    At the beginning, the suggestions only come from the hunspell dictionaries and are thus not very good yet. But ibus-typing-booster learns from your typing, it remembers which words you use often in which context. Therefore, the suggestions become much better over time.

    To switch between ibus-typing-booster and other input methods or a simple keyboard layout, you can use the input sources menu in the panel or the keyboard shortcut, which is Super+Space by default (can be changed in the “Text Entry” dialogue of the system settings).

1. If you want to enable the ibus property panel or change the font size for the list of candidates, you can do that by starting the ibus-setup program.

    To show the property panel set “Show property panel” to “Always” in ibus-setup.

    The property panel is seen in this screenshot at the top right, just below the Unity panel. You can move the property panel anywhere you like by dragging its left edge. The property panel shows the current value of some options of ibus-typing-booster and allows to change them quickly.

    The screenshot also shows how a much bigger font was chosen for the candidate list with the “Use custom font” option in ibus-setup.


###### 2
## Setup
Ibus-typing-booster has a setup tool which allows to adapt the behaviour a lot to your preferences.


###### 2_1
## Basic setup for your language

{{< video label="Default settings in Hindi locale" webm="/videos/user-docs/hindi-locale-default-settings.webm" >}}

This video shows how to setup languages and input methods in Typing Booster.

The most important setup in Typing booster is to choose **which**
languages you want to use and **how** to input them.

ibus-typing-booster works for many languages and it may be necessary
to change the default dictionaries and input methods to different
ones.

When one uses ibus-typing-booster is started for the very first time,
it checks which locale is set in the environment and initialises its
setup with dictionaries and input methods which are useful for this
locale.

But it is probably a good idea to open the setup tool and look whether
these defaults are OK for you. You can open the setup tool by
selecting ibus-typing-booster in the input method menu of the panel
and then clicking on the “Setup” menu item in the panel.

At the beginning, this video shows the default dictionaries and input
methods for the locale “hi_IN.UTF-8” (Hindi in India).

For this locale, one will get the dictionaries “hi_IN” (Hindi) and
en_GB (British English) and the input methods “hi-inscript2” and
“NoIME” by default. “hi-inscript2” is an input method for
Hindi. “NoIME” means no input method at all, that means the characters
are used as they come from the current keyboard layout without any
transliteration. Having the British English dictionary and the “NoIME”
input method there as well makes it also possible to type English.

As English is used quite a lot in India, it is probably a good default
for the “hi_IN.UTF-8” locale to setup input for both Hindi and British
English.

But the defaults guessed from the current locale are not always what a
user wants. A user might use a “en_US.UTF-8” (American English) locale
because he prefers the user interface in English but nevertheless
might want to type Hindi. And even when running in the “hi_IN.UTF-8”
locale, the defaults might not be optimal for some
users. “hi-inscript2” is not the only input method to type Hindi,
there are other choices. And maybe a Hindi user wants to use
additional other languages and input methods completely unrelated to
the current locale.

So the video shows how to add or remove dictionaries and input methods
and move them up or down to increase or lower the priorities.
The video also shows how the “Input Method Help” button pops up
an explanation what an input method does and how to use it.

Near the end, the video shows how the “Set to default” buttons can
reset the lists of languages and input methods to the defaults
for the current locale.

Both lists can hold a maximum of 10 items, i.e. you can have up to 10
dictionaries and 10 input methods. Don’t overdo it though, don’t add
more than you really need, adding more dictionaries and input methods
than one really needs slows down the system and reduces the accuracy
of the word predictions.

The list of input methods cannot be made completely empty, as soon as
you remove the last input method, the “NoIME” input method is
automatically added back because no input at all makes no sense.

The list of dictionaries can be made empty though. That doesn’t seem
particularly useful to me, but apparently there are some users who use
ibus-typing-booster mostly as a convenient input method for emoji or
special symbols and in that case one doesn’t need a dictionary.

###### 2_2
## More advanced options
This chapter explains more advanced options how to adapt the behaviour and the look and feel of ibus-typing-booster to your preferences.


###### 2_2_1
## Enable suggestions by a key

{{< video label="Enable suggestions by key" webm="/videos/user-docs/enable-suggestions-by-key.webm" >}}

This video shows what the options “☑️ Enable suggestions by key” and
“☑️ Use preedit style only if lookup is enabled” do.

By default, ibus-typing-booster pops up a list of candidates as soon
as you type something and you can choose a candidate to complete the
word you have started typing to save some key strokes, fix a spelling
error, or select an emoji or special character.

But some users prefer **not** to have these candidate lists displayed all
the time. Maybe they are fast touch typists and usually type without
completion support and the frequent pop up of the candidate lists is
too visually disturbing. Calculating the candidate lists also takes
some time, especially if emoji predictions are enabled. These
calculations may actually interfere with the typing for very fast
typists.

But from time to time even exceptionally fast typists may still want
to see candidates to complete a very long word or check the spelling
or or input an emoji.

In that case it can be useful to check the option “☑️ Enable suggestions
by key”.

If that option is enabled, no candidate list is shown unless a special
key is pressed to request a candidate list. By default that special
key is Tab but this can be changed by the [customizing the keys](#3_4)
bound to the command “enable_lookup”.

In the beginning of the video, this option is **not** enabled. When typing
into the text editor one sees that after each single key typed a suggestion
list with word completions pops up.

Then the option “☑️ Enable suggestions by key” is enabled. Now when
typing into the text editor, no suggestions pop up unless Tab is pressed.
So one sees that “Hello Worl” is typed without andy suggestions popping up,
then Tab is pressed and suggestions containing “World” pop up.

There is another option “Minimum number of chars for completion” which
is 1 by default. If that option is set to a number greater than 1,
then a candidate list appears automatically only when that number of
characters has been typed into the preedit. But using the keys bound
to the “enable_lookup” command one can still request a candidate list
even if fewer characters have been typed.

Some users using this option to show candidate lists only on request,
request candidate lists only very rarely to complete an unusually long
and complicated word or to type an emoji. When candidate lists are
requested only very infrequently, some users dislike that the preedit,
i.e. the currently typed word, is always underlined. It is possible to
disable the underlining of the preedit in the “Appearance” tab of the
setup tool: There is a combobox where one can choose no underlining
for the preedit.

But one does not have to disable the underlining of the preedit
completely: It is even possible to hide the underline indicating the
preedit only as long as no candidate list is requested. To do this,
there is the option “Use preedit style only if lookup is enabled” in
the Appearances tab of the setup tool. Then the preedit looks like
normal text until a candidate list is requested. As soon as the
candidate list is requested, the preedit is again styled (usually
underlined), this makes it clearer which part of the text has been
used to calculate that candidate list. The use of this option
is also shown near the end of the video.

**Attention when using Wayland**: Currently it is not possible to do any
style changes to the preedit on Wayland. On Wayland the preedit is
always underlined and always has the same foreground and background
colour as normal text, no matter what options to influence the preedit
style are chosen in the setup tool of ibus-typing-booster. That is a
missing feature in Wayland.


###### 2_2_1_1
## Simulate the behaviour of ibus-m17n

{{< video label="Simulating ibus-m17n (hi-itrans)" webm="/videos/user-docs/simulating-ibus-m17n-hi-itrans.webm" >}}

This video shows how one can emulate ibus-m17n using
ibus-typing-booster by switching off all the features
ibus-typing-booster has in addition to ibus-m17n.

The ibus-m17n engines can be used to input many languages using all
the input methods from m17n-lib and m17n-db.

ibus-typing-booster can also use the same input methods from m17n-lib
and m17n-db. So one can input all the languages in the same way one
can with ibus-m17n. But ibus-typing-booster has many additional
features like completion using dictionaries, spellchecking,
predictions based on previous user input and being able to use several
input methods/transliterations at the same time.

But what if a user doesn’t need and want all the extra features of
ibus-typing-booster at all, just simple type one language with one
input method without any extra bells and whistles?

One can still use ibus-typing-booster in that case by disabling all of
the extra features. Then ibus-typing-booster behaves like any
ibus-m17n engine.

The advantage of simulating ibus-m17n using ibus-typing-booster is
that there are probably fewer bugs because ibus-typing-booster is more
actively maintained.

To simulate ibus-m17n with ibus-typing-booster, one can use the
following setup options:

* Dictionaries and input methods tab:
    * Remove all input methods except the one you want to use
* Options tab:
    * Check the option “Enable suggestions by key”
    * Check the option “Off the record mode”
* Key bindings tab:
    * Remove all keys bound to the command “enable_lookup”
* Appearance tab:
    * Set “Preedit underline” to “None”

With these settings, no candidate lists will ever pop up because one
would need to press a key to enable a suggestion but all such keys
have been removed from the “enable_lookup” command. So candidate lists
are never shown, just like in ibus-m17n.

No user input is recorded because of enabling the option “Off the
record mode”. Recording user input would be useless because stuff
learned from user input is normally used to improve the quality of the
suggestions based on previous input. But if there are never any
suggestions, there is no need to record user input at all.

Without candidate lists, dictionaries are useless, therefore it
doesn’t matter which dictionaries are setup in the “Dictionaries and
input methods” tab. One can remove them all or leave them there, it
doesn’t matter.

As one can see in the video, setting the above options one after another,
ibus-typing-booster behaves more and more similar to ibus-m17n, when
all above options are set, the behaviour looks identical.

###### 2_2_2
## Use inline completion

{{< video label="“Normal” completion versus inline completion" webm="/videos/user-docs/inline-completion.webm" >}}

The video above shows how “inline completion” looks like compared to
“normal” completion.

Very often, the first candidate shown as a suggestion is already the
desired one, especially after having used ibus-typing-booster for a
while and it has learned what the user types often in what context.

When one ends up selecting the first candidate most of the time,
popping up a candidate list with more candidates all the time is
needlessly visually distracting.

When the option “Use inline completion” is checked, the first and most
likely candidate is shown inline at the writing position without
popping up a candidate list. The characters one has already typed are
shown in the current foreground colour (black in the screenshot) and
are underlined (Unless underlining the preedit has been switched off
in the “Apperance” settings). The completion which is suggested is
shown without the underline and in a different colour. This colour is
gray by default because this works in most cases, it also works when
the foreground text colour is white and the background black. The
colour to be used for the inline completion can be chosen in the
“Appearance” tab. One can also choose not to use a different colour,
then the only difference in style between the completion and the
already typed characters is the missing underline under the
completion.

This inline completion style looks much nicer than always popping up a
candidate list when the predictions are fairly good and the first
candidate is often the desired one.

If that first candidate shown inline is what one wants, one can select
it by typing any of the keys bound to the “select_next_candidate”
command (Tab and arrow down by default).

When the candidate is selected, the style of the completion becomes
the same as the style of the already typed characters and the cursor
moves to the end of the completion.

Now one could commit it for example by typing space and continue
typing the next word of the text.

Or, if that candidate displayed inline happens to be not the desired
one, it is still possible to pop up a full candidate list with more
candidates by pressing the key bound to the “select_next_candidate”
command (Tab by default) again. And then walk down the candidate list
by continue pressing that key. If nothing appropriate can be found in
the whole candiate list, one can use the key bound to the command
“cancel” (the Escape key by default) to deselect all candidates and
close the candidate list. Then one could type more input characters
and hope that better suggestions become available after typing a bit
more.

One can also ignore the candidate displayed inline completely and just
continue typing more input characters until a better candidate is
displayed.

###### 2_2_2_1
## Inline completion is hard to use on Wayland

{{< video label="Inline completion is hard to use on Wayland" webm="/videos/user-docs/inline-completion-wayland.webm" >}}

**Attention when using Wayland**: Currently it is not possible to do any
style changes to the preedit on Wayland. On Wayland the preedit is
always underlined and always has the same foreground and background
colour as normal text, no matter what options to influence the preedit
style are chosen in the setup tool of ibus-typing-booster. That is a
missing feature in Wayland.

This makes the “Use inline completion” option quite hard to use on
Wayland. It is possible to use it, but as the characters typed and the
suggested completion are displayed in exactly the same style, it is
quite hard to see what has been typed and what is the completion. If
one looks carefully, one can still see it because the cursor can be
seen at the end of the typed characters, everything to the right of
the cursor is the suggested completion. If the completion is selected
by typing the key bound to the “select_next_candidate” command (Tab by
default), then the cursor moves to the end of the completion.

One can get used to the fact that the difference between the typed
text and the inline completion is hard to see on Wayland, but I found
this to be quite hard.


###### 2_2_3
## Spellchecking

{{< video label="Spellchecking in the preedit and candidate list" webm="/videos/user-docs/spellchecking-preedit-and-candidate-list.webm" >}}

ibus-typing-booster also does spellchecking (Using hunspell for most
languages and voikko for Finnish).

If a word is typed which might contain a spelling error, the candidate
list of suggestions may contain suggestions for spelling corrections,
i.e. words which are not just completing the text already typed to
something longer or fixing some accents but “seriously” changing the
characters already typed, more than just fixing accents,
i.e. completely different characters or another order of characters.

Optionally, such spellchecking suggestions can be marked in the
candidate list with a symbol or using a different colour in the
candidate list. The symbol and color can be chosen.

One can also choose to mark candidates which are (accent insensitive)
completions of the typed word with a symbol and/or colour if they are
valid words in one of the dictionaries.

And one can choose to mark candidates which are (accent insensitive)
completions of the typed word with a symbol and/or colour if they have
been remembered in the user database because the user has typed them
before.

All of these markings can help to get the spelling right, for example
if one uses a French dictionary and types “egali” and sees “égalité”
and “égalisation” marked as “dictionary suggestions” in the candidate
list, then one knows that these candidates are valid words in the
French dictionary and what one typed was identical to the beginning of
these candidates except for differents in accents.

It can also speed up typing not bothering typing the accents at all
(because this often requires extra key strokes) and then select the
correctly accented word from one of the “dictionary suggestions”.

Colour in the candidate list does not work when using Gnome, only on
other desktops colour can be used in the candidate list. Marking
spellchecking suggestions with a symbol also works on Gnome. By
default, neither colour nor symbols are used for suggestions.

#### Indicating spelling errors in the preedit

One can choose that the preedit changes colour when the typed word is
not a valid word in any of the dictionaries setup in the ”Dictionaries
and input methods” tab of the setup tool.

For example, if one uses an English and a French dictionary, and the
typed word in the preedit is neither a valid word in English nor in
French, then the preedit changes colour. This is also shown in the
above screenshot using the default colour red.

Dictionaries where spellchecking is not supported are ignored for this
colour change. For example, if one uses an English, a French, and a
Japanese dictionary at the same time, the preedit still changes colour
if the word is neither a valid English nor a valid French
word. Whether the typed word is in the Japanese dictionary or not
doesn’t matter because the Japanese dictionary does not support
spellchecking.

**Attention when using Wayland**: On Wayland it is not possible to
indicate a possible spelling error in the preedit.

Currently it is not possible to do any style changes to the preedit on
Wayland. On Wayland the preedit is always underlined and always has
the same foreground and background colour as normal text, no matter
what options to influence the preedit style are chosen in the setup
tool of ibus-typing-booster. That is a missing feature in Wayland.


###### 3
## Key and Mouse bindings

###### 3_1
### The “AltGr” key
Ibus-typing-booster does not change your keyboard layout, it just uses the keyboard layout which was selected last.

As some of the default key bindings in the table below use key combinations starting with “AltGr”, it is recommended to use a keyboard layout where the right “Alt” key is really an “AltGr” key and not just a duplicate of the left “Alt” key. If you do not have a real “AltGr” key, you can still use most of the key bindings in the table below but of course not those which start with “AltGr”. In that case, you might want to use the setup tool to [customize your key bindings](#3_4).

The standard “English (US)” keyboard layout makes the “AltGr” key on the right side of the space bar basically behave as a duplicate of the left “Alt” key. So if you like the US English layout, better use the keyboard layout “English (US, with euro on 5)” instead of the standard one. “English (US, with euro on 5)” is very similar to the standard “English (US)” layout but has a real “AltGr” key.

Many (but not all) keyboard layouts for other languages different from US English already have a real “AltGr” key.

You can check whether your keyboard layout has a real “AltGr” key with “xev”, “xev” should show you the keysym “ISO_Level3_Shift” when pressing the “AltGr” (right “Alt”) key and not the keysym “Alt_R”.

###### 3_2
### Table of default key bindings
Some of these key bindings can be customized in the setup tool, see [Customizing key bindings](#3_4). The following table explains the defaults.

<table border="2" cellspacing="10" cellpadding="10">
<thead>
<tr>
<th>Key combination</th>
<th>Effect</th>
</tr>
</thead>
<tbody>
<tr>
<td><code>Space</code></td>
<td>
  Commit the preëdit (or the selected candidate, if any) and send a
  space to the application, i.e. commit the typed string followed by a
  space.
</td>
</tr>
<tr>
<td><code>Return</code></td>
<td>
  Commit the preëdit (or the selected candidate, if any) and send a
  <code>Return</code> to the application.
</td>
</tr>
<tr>
<td><code>KP_Enter</code></td>
<td>
  Commit the preëdit (or the selected candidate, if any) and send a
  <code>KP_Enter</code> to the application.
</td>
</tr>
<tr>
<td><code>Tab</code></td>
<td>
  Bound by default to the commands “select_next_candidate” and “enable_lookup”.
  <br>
  <ul>
    <li>
      If the option “☐ Enable suggestions by Tab key” is <em>not</em>
      set: “Tab” always just executes “select_next_candidate”
      which selects the next candidate from the candidate list.
    </li>
    <li>
      If the option “☑ Enable suggestions by Tab key” is set, no
      candidate list is shown by default:
      <ul>
        <li>
          If no candidate list is shown: “enable_lookup” is executed
          which requests to show the candidate list (nothing might be
          shown if no candidates can be found).
        </li>
        <li>
          If a candidate list is already shown:
          “select_next_candidate” is executed which selects the next
          candidate in the list.  After each commit and after each
          change of the contents of the preëdit, the candidate list
          will be hidden again until the “enable_lookup” requests it
          again.
        </li>
      <ul>
    </li>
  </ul>
</td>
</tr>
<tr>
<td><code>Shift+Tab</code></td>
<td>
  Bound by default to the command “select_previous_candidate”.
  <br>
  Selects the previous candidate in the candidate list.
</td>
</tr>
<tr>
<td><code>Escape</code></td>
<td>
  Bound by default to the command “cancel”.
  <br>
  <ul>
    <li>
      When a candidate is selected (no matter whether this is a normal
      lookup table or a “related” lookup table): Show the first page
      of that lookup table again with no candidate selected.
    </li>
    <li>
      When no candidate is selected:
      <ul>
        <li>
          When a lookup table with related candidates is shown or a
          lookup table where upper/lower-case has been changed by
          typing the Shift key is shown: go back to the original
          lookup table.
        </li>
        <li>
          When a normal lookup table is shown: close it and clear the
          preëdit.
        </li>
      </ul>
    </li>
  </ul>
</td>
</tr>
<tr>
<td><code>Left</code> (Arrow left)</td>
<td>Move cursor one typed key left in the preëdit text. May trigger a
commit if the left end of the preëdit is reached.</td>
</tr>
<tr>
<td><code>Control+Left</code></td>
<td>Move cursor to the left end of the preëdit text. If the cursor is
already at the left end of the preëdit text, trigger a commit and send
a <code>Control+Left</code> to the application.</td>
</tr>
<tr>
<td><code>Right</code> (Arrow right)</td>
<td>Move cursor one typed key right in preëdit text. May trigger a
commit if the right end of the preëdit is reached.</td>
</tr>
<tr>
<td><code>Control+Right</code></td>
<td>Move cursor to the right end of the preëdit text. If the cursor is
already at the right end of the preëdit text, trigger a commit and
send a <code>Control+Right</code> to the application.</td>
</tr>
<tr>
<td><code>BackSpace</code></td>
<td>Remove the typed key to the left of the cursor in the preëdit
text.</td>
</tr>
<tr>
<td><code>Control+BackSpace</code></td>
<td>Remove everything to the left of the cursor in the preëdit
text.</td>
</tr>
<tr>
<td><code>Delete</code></td>
<td>Remove the typed key to the right of the cursor in the preëdit
text.</td>
</tr>
<tr>
<td><code>Control+Delete</code></td>
<td>Remove everything to the right of the cursor in the preëdit
text.</td>
</tr>
<tr>
<td><code>Down</code> (Arrow down)</td>
<td>
  Bound by default to the command “select_next_candidate”.
  <br>
  Selects the next candidate.
</td>
</tr>
<tr>
<td><code>Up</code> (Arrow up)</td>
<td>
  Bound by default to the command “select_previous_candidate”.
  <br>
  Selects the previous candidate.
</td>
</tr>
<tr>
<td><code>Page_Up</code></td>
<td>
  Bound by default to the command “lookup_table_page_up”.
  <br>
  Shows the previous page of candidates.
</td>
</tr>
<tr>
<td><code>Page_Down</code></td>
<td>
  Bound by default to the command “lookup_table_page_down”.
  <br>
  Shows the next page of candidates.
</td>
</tr>
<tr>
<td><code>F1</code></td>
<td>Commit the candidate with the label “1” followed by a space</td>
</tr>
<tr>
<td><code>F2<code></td>
<td>Commit the candidate with the label “2” followed by a space</td>
</tr>
<tr>
<td>...</td>
<td>...</td>
</tr>
<tr>
<td><code>F9</code></td>
<td>Commit the candidate with the label “9” followed by a space</td>
</tr>
<tr>
<td><code>Control+F1</code></td>
<td>
  Remove the candidate with the label “1” from the database of learned
  user input (If possible, if this candidate is not learned from user
  input, nothing happens).
</td>
</tr>
<tr>
<td><code>Control+F2</code></td>
<td>
  Remove the candidate with the label “2” from the database of learned
  user input (If possible, if this candidate is not learned from user
  input, nothing happens).
</td>
</tr>
<tr>
<td>…</td>
<td>…</td>
</tr>
<tr>
<td><code>Control+F9</code></td>
<td>
  Remove the candidate with the label “9” from the database of learned
  user input (If possible, if this candidate is not learned from user
  input, nothing happens).
</td>
</tr>
<tr>
<td><code>1</code> … <code>9</code></td>
<td>
  By default, same as <code>F1</code> … <code>F9</code>.
  <br>
  Selecting candidates with <code>1</code> … <code>9</code> is a bit easier
  because the number keys <code>1</code> … <code>9</code>
  are closer to the fingers then <code>F1</code> … <code>F9</code> on
  most keyboards. On the other hand, it makes completing when typing
  numbers impossible and it makes typing strings which are combinations
  of letters and numbers like “A4” more difficult. If digits are used as
  select keys, numbers can only be typed when no candidate list is
  shown. In most cases this means that numbers can only be typed when
  nothing else has been typed yet and the preëdit is empty.
</td>
</tr>
<tr>
<td><code>KP_1</code> … <code>KP_9</code></td>
<td>
  By default, same as <code>F1</code> … <code>F9</code>.
</td>
</tr>
<tr>
<td><code>Control+1</code> … <code>Control+9</code></td>
<td>
  By default, same as <code>Control+F1</code> … <code>Control+F9</code>.
</td>
</tr>
<tr>
  <td><code>AltGr+F6</code></td>
  <td>
    Bound by default to the command “toggle_emoji_prediction”.
    <br>
    Toggle the <a href="#6">emoji and Unicode
      symbol</a> prediction on/off. This has the same result as using
      the setup tool to change this.
  </td>
</tr>
<tr>
  <td><code>AltGr+F9</code></td>
  <td>
    Bound by default to the command “toggle_off_the_record”.
    <br>
    Toggle the “Off the record” mode.  This has the same result as
    using the setup tool to change this.
    <br>
    While “Off the record” mode is on, learning from user input is
    disabled. If learned user input is available, predictions are
    usually much better than predictions using only
    dictionaries. Therefore, one should use this option
    sparingly. Only if one wants to avoid saving secret user input to
    disk it might make sense to use this option temporarily.
  </td>
</tr>
<tr>
  <td><code>AltGr+F10</code></td>
  <td>
    Bound by default to the command “setup”.
    <br>
    Opens the setup tool.
  </td>
</tr>
<tr>
  <td><code>AltGr+F12</code></td>
  <td>
    Bound by default to the command “lookup_related”.
    <br>
    Shows related <a href="#6">emoji and Unicode symbols</a>
    or <a href="#7">related words</a>
  </td>
</tr>
<tr>
  <td><code>AltGr+Space</code></td>
  <td>
    Insert a literal space into the preëdit.
  </td>
</tr>
</tbody>
</table>

When more than one input method at the same time is used, the following additional key bindings are available:

<table border="2" cellspacing="10" cellpadding="10">
<thead>
<tr>
<th>Key combination</th>
<th>Effect</th>
</tr>
</thead>
<tbody>
<tr>
<td><code>Control+Down</code></td>
<td>
  Bound by default to the command “next_input_method”.
  <br>
  Switches the input method used for the preëdit to the next input
  method.
</td>
</tr>
<tr>
<td><code>Control+Up</code></td>
<td>
  Bound by default to the command “previous_input_method”.
  <br>
  Switches the input method used for the preëdit to the previous input
  method.
</td>
</tr>
</tbody>
</table>


###### 3_3
### Mouse bindings

 These mouse bindings are currently hardcoded and can not yet be customized. 

<table border="2" cellspacing="10" cellpadding="10">
<thead>
<tr>
<th>Mouse event</th>
<th>Effect</th>
</tr>
</thead>
<tbody>
<tr>
  <td><code>Button1</code> click on a candidate</td>
  <td>
    Commit the candidate clicked on followed by a space (Same as
    F1…F9).
  </td>
</tr>
<tr>
  <td><code>Control+Button1</code> click on a candidate</td>
  <td>
    Remove clicked candidate from database of learned user input (If
    possible, if this candidate is not learned from user input,
    nothing happens).
  </td>
</tr>
<tr>
  <td><code>Button3</code> click on a candidate</td>
  <td>
    Show related <a href="#6">emoji and Unicode symbols</a>
    or <a href="#7">related words</a> (Same as
    AltGr+F12).
  </td>
</tr>
<tr>
  <td><code>Control+Button3</code> click anywhere in the candidate list</td>
  <td>
    Toggle the <a href="#6">emoji and Unicode
      symbol</a> prediction on/off (Same as AltGr+F6). This has the same
      result as using the setup tool to change this.
  </td>
</tr>
<tr>
  <td><code>Alt+Button3</code> click anywhere in the candidate list</td>
  <td>
    Toggle the “Off the record” mode (Same as AltGr+F9). This has the
    same result as using the setup tool to change this.
    <br>
    While “Off the record” mode is on, learning from user input is
    disabled. If learned user input is available, predictions are
    usually much better than predictions using only
    dictionaries. Therefore, one should use this option
    sparingly. Only if one wants to avoid saving secret user input to
    disk it might make sense to use this option temporarily.
  </td>
</tr>
</tbody>
</table>


###### 3_4
### Customizing key bindings

{{< video label="Customizing key bindings" webm="/videos/user-docs/key-bindings-customization.webm" >}}

This video shows how one can change a keybinding.

In the “Key bindings” tab of the setup tool of ibus-typing-booster one
sees a list of commands and the key combinations bound to execute
these commands.

As an example, the video shows changing the key binding for the command
“select_next_candidate”. By default this command is bound to
`['Tab', 'ISO_Left_Tab', 'Down', 'KP_Down']`.

The video shows how to remove the key `Tab` and add `Control+Tab`
instead and then, finally use the “Set to default” button to
go back to the default setting.

And can also see in the screenshot that some commands are bound by
default to Mod5+something. Mod5 is Usually ISO_Level3_Shift and this
is mapped to the AltGr key on many keyboard layouts, see also The
“AltGr” key. If your keyboard layout does not have that key, you might
want to change these settings.


###### 4
## Multilingual input

{{< video label="Setup several dictionaries and input methods" webm="/videos/user-docs/setup-several-dictionaries-and-input-methods.webm" >}}

This video shows how to setup multiple dictionaries and input methods.

Ibus-typing-booster supports using more than one dictionary and more
than one input method/transliteration at the same time.

That makes it possible to write text in more than one language without
having to switch languages manually. If one often writes in different
languages this can save a lot of input method switching.

This works not only when the languages use same script (like using
English and Spanish at the same time), it works even when the
languages use different scripts. For example when using English (Latin
script) and Hindi (Devanagari script) at the same time. When using
languages with different scripts at the same time, it is sometimes
necessary to switch the input method for the preëdit (See the Hindi
and English example). But even in such a more complicated case,
switching is often not necessary, often one can select a suitable
candidate without switching and save a lot of input method switches.

This video shows how dictionaries can be added using the “➕” button
below the list of dictionaries in the “Dictionaries and input methods”
tab of the setup tool.

The check marks (“✔️”) and the cross marks (“❌”) indicate whether a
spellchecking dictionary and/or and emoji dictionary for that
language/locale is currently available on your system. If a dictionary
is shown with a cross mark (“❌”) as not available, that does not
necessarily mean that it is not available at all for your system,
maybe you just need to install an additional package.

For obscure technical reasons, the maximum number of dictionaries you
can use at the same time is currently limited to 10. But that should
be plenty, one should not overdo it, the more dictionaries one adds,
the slower ibus-typing-booster becomes and the prediction quality
suffers. So only add the dictionaries you really need.

This video also shows how input methods can be added to
ibus-typing-booster using the “➕” button below the list of input
methods in the “Dictionaries and input methods” tab of the setup tool.

Just like for the dictionaries, for obsure technical reasons the
maximum number of input methods you can currently use at the same time
is limited to 10. But that should be plenty.

One should only add as many input methods as one really needs, adding
more would only slow down the system and reduce the accuracy of the
predictions.

Near the end this video also shows how one can try to install missing
dictionaries, i.e. dictionaries marked with a cross mark (“❌”) by
clicking on the “Install missing dictionaries” button.

When this button is clicked, one can see a black box with the text
“Additional Packages Required” “An application is requesting
additional packages.” appearing near the top of the screen, just below
the Gnome panel.

When clicking that black box, the package manager will try to install
packages for the missing dictionaries, if possible. For “fr_FR”
(French) and “es_ES” (Spanish) this will succeed on Fedora 34 and show
options to install the “hunspell-fr” and the “hunspell-es”
package. For “zh” (Chinese) and “ja_JP” Japanese this will not
succeed, there are no hunspell dictionaries for these languages on
Fedora 34. That does not mean that adding the “zh” and “ja_JP”
dictionaries in the setup tool is pointless, the check mark (“✔️”) is
shown after emoji. That means emoji dictionaries for these languages
are available and even installed at the moment. So if you want to
match emoji in Chinese or Japanese, these dictionaries could still be
useful.

The button “Install missing dictionaries” uses the service offered by
the “Packagekit” daemon to try to install package. If the
`packagekitd` is not running, this will not work. The UI shown by
“Packagekit” differs a bit depending on whether you do this on Gnome,
XFCE, or something else.  On some distributions, the names for the
packages containing the needed hunspell dictionaries might be
different causing this to fail. If this button doesn’t work, there is always
the option to install dictionaries using the command line, for example on
Fedora:

```
sudo dnf install hunspell-es hunspell-fr
```


###### 4_1
### Example using Hindi and English at the same time

{{< video label="Example using Hindi and English at the same time" webm="/videos/user-docs/Example-using-Hindi-and-English-at-the-same-time.webm" >}}

This video shows how Hindi and English can be used at the same time in
ibus-typing-booster.

If one uses both Hindi and English often, it is possible to setup
ibus-typing-booster to use both languages at the same time. Then one
can just type in either Hindi or English and ibus-typing-booster will
show suitable candidates automatically.

In the “Dictionaries and input methods” tab of the setup tool one can
see that two dictionaries have been added, “hi_IN” for Hindi and
“en_GB” for British English.  And two input methods have been added,
“hi-itrans” to type Hindi and “NoIme” (“Native Keyboard”, i.e. direct
keyboard input) to type English (How to setup dictionaries and input
methods is described [here](#2_1).).

There are several input methods available for Hindi: “hi-inscript2”,
“hi-inscript”, “hi-phonetic”, “hi-itrans”, “hi-remington”,
“hi-typewriter”, and “hi-vedmata”. In this example we use “hi-itrans”
but one could also use any of the others or even several at once.

If more than one input/transliteration method is enabled, the typed
keys will be transliterated with each transliteration method and each
transliteration result will be looked up in the enabled dictionaries
and in the user database of previous input.

In this video, Hindi with the “hi-itrans” method and English are used
at the same time. One can see in the preedit that the input “guru” has
been typed. The candidate list shows both “गुरु” (which is the
transliteration of the input “guru” using the “hi-itrans” method) and
the English candidates “guru” and “gurus”. This is because both the
transliteration “गुरु” and the direct input “guru” are used at the same
time to lookup candidates.

Actually it is quite rare to see candidates from both Hindi and
English in a candidate list. The English word “guru” is a loanword
from Hindi, it is just the transliteration of the original Hindi word
into the Latin Alphabet. Therefore, the “Itrans” method transliterates
it back to Hindi and one gets a match in Hindi as well. Most English
words do not transliterate to anything meaningful in Hindi and most
Hindi input does not match anything in English either. The example
“guru” is carefully chosen to show how ibus-typing-booster handles
multilingual input.

In practice, as soon as one has typed a few characters, one will most
of the time see only candidates from either Hindi or English, not
both. I.e. the language one is typing in at the moment is
automatically detected because one very rarely gets matches in the
other language.

This automatic language detection works even better after
ibus-typing-booster has learned from user input for a while. Because
ibus-typing-booster remembers the context where the user has typed
words.

Whether the preëdit (i.e. the current input, i.e. the underlined text
next to the candidate list) shows Latin alphabet “guru” or Devanagari
“गुरु” depends on which input method currently has highest priority,
“NoIme” (which produces Latin alphabet) or “hi-itrans” which produces
Devanagari.

Switching the priority of the input methods is sometimes necessary
because one may not want to select any of the displayed candidates but
commit the preëdit instead by typing a space. For example, if the
preëdit is currently in English mode (direct input mode) and one types
a Hindi word, it may happen that one does not get any matches in the
candidate list, although the word has been typed correctly. This may
happen if this word can neither be found in the dictionary nor in the
user database because this word has never been typed before by the
user. Nevertheless it may be a correct Hindi word of course and the
user may want to commit it. But if the preëdit is currently in English
mode, typing space would commit the Latin characters. So one has to
switch the preëdit to “hi-itrans” first and then commit by typing a
space.

The default key bindings to switch the input method for the preëdit
are “Control+Down” and “Control+up”. With only two input methods as in
the current example, both key bindings behave the same. But there can
be more than two input methods and then “Control+Down” moves in one
direction through the list of input methods and “Control+Up” in the
other direction (see [key and mouse bindings](#3)).

As an alternative to using the “Control+Down” and “Control+Up” key
bindings, the priorities of input methods can also be switched using
the menu in the gnome panel or using the setup tool.

In the setup tool, there is an option “☐ Remember last used preëdit
input method”. If that option is disabled, ibus-typing-booster will
always start using the input method with the highest priority as set
in the setup tool for the preëdit when you log in to your desktop and
use ibus-typing-booster for the first time after the login. In that
case, changing the input method priorities with the key bindings or
the Gnome panel has no permanent effect, it will not change the order
in the setup tool in that case. With this option disabled, only
changing the priorities directly in the setup tool has a permanent
effect.

But if the option “☑️ Remember last used preëdit input method” is
enabled, ibus-typing-booster will change the priority in the setup
when you switch to a different input method for the preëdit using the
key bindings or the Gnome panel. In the video it can be seen that the
order of the input methods in the setup tool changes even though the
“↑” and “↓” buttons in the setup tools have not been clicked but the
key bindings or the menu in the Gnome panel have been used and this
had an effect on the order shown in the setup tool because the option
“☑️ Remember last used preëdit input method” was enabled during the
video.


###### 4_2
### Example using Spanish and English at the same time

{{<
figure src="/images/user-docs/Example-using-Spanish-and-English-at-the-same-time.gif"
caption="Using Spanish and English at the same time"
>}}

This animated gif shows using ibus-typing-booster for Spanish and
English at the same time. In the setup tool, dictionaries for Spanish
(“es_ES”) and British English (“en_GB”) have been added. And two input
methods “t-latn-pre” and “NoIme” (Native Keyboard, i.e. direct
keyboard input) have been added. Actually using only “NoIme” would
have been enough, both Spanish and English can be typed just fine with
direct keyboard input with a suitable keyboard layout. Adding
“t-latin-pre” makes it possible to type for example “~n” to get an
“ñ”, i.e. using “t-latn-pre” one can type accented Latin charaters
even when using a US English keyboard layout for example. But that is
completely optional, one can use only “NoIme”, only “t-latn-pre”, or
both, depending on what keyboard layout one wants to use and what is
most convenient.

When the input typed is “Yo soy un h” where the last character, the
“h” is still in preëdit (marked by the underline) and we see some
suggestions how the word starting with “h” might continue.

The suggestions shown for this input are Spanish words, not
English. This is because ibus-typing-booster has already been trained
by similar user input before. Therefore, it already knows which word
starting with “h” the user usually types following “soy un”. And these
are Spanish words.

In the second line of the editor the user now types some English after
finishing the Spanish sentence.

The input typed is now “I am h” and again the last character “h” is
still in preëdit and some suggestions for words starting with “h” are
shown.

This time, the suggestions for words starting with “h” are English,
not Spanish. This is because the words typed before were “I am” and
the user apparently types the suggested English words frequently after
“I am”.

So ibus-typing-booster can often automatically show candidates from
the correct language according to the context. This makes it quite
efficient to type multiple languages.

One can add as many dictionaries as one likes, but adding more
dictionaries than one really needs slows the system down unnessarily
and reduces the prediction accuracy.

###### 5
## Compose support (About dead keys and the Compose key)

“Compose sequences” are sequences of keys containing so
called “dead keys” or containing the “Compose key” or even both
and usually one or more “normal” keys.

###### 5_1
## “Dead keys”

Some keyboard layout have so called [“dead
keys”](https://en.wikipedia.org/wiki/Dead_key). They are called “dead”
because in traditional implementations like in the Compose sequence
implementation of
[Xorg](https://en.wikipedia.org/wiki/X_Window_System) they seem to do
nothing at first, i.e. they appear to be “dead”. For example when
typing a dead “~”, nothing appears to happen but when a base character
like “a” is typed next, an “ã” appears. Some more examples:

| Dead key sequence | Result |
| --- | --- |
| `~` `a` | ã  U+00E3 LATIN SMALL LETTER A WITH TILDE |
| `~` `^` `a` | ẫ U+1EAB LATIN SMALL LETTER A WITH CIRCUMFLEX AND TILDE |
| `~` `␠` | ~ U+007E TILDE|
| `~` `~` | ~ U+007E TILDE |
| `~` `@` | undefined sequence, i.e. no result |

But on several modern implementations, these keys are not so “dead”
anymore, the behaviour is improved and something helpful is actually
displayed while typing such sequences.

* Xorg:

  When using the Compose support of Xorg, for example when typing into
  an Xorg application like xterm (i.e. **not** a Gtk application)
  while **not** having configured any input methods systems like IBus,
  these dead keys are really “dead”, nothing is displayed until the
  dead key sequence is finished. Any illegal/impossible/undefined
  sequence is silently discarded, i.e. when typing something like dead
  `~` `@`, nothing at all happens.

* MacOS:

  Typing a dead `~` shows the `~` and highlights it, when the key for
  the base characters is pressed, the final character appears

* Gtk, IBus, Typing Booster:

  Similar to MacOS, these 3 implementations show the dead keys,
  highlight them, let the user correct unfinished sequences with
  BackSpace, and may do more helpful stuff with undefined sequences
  then just silently discarding them.

Some keyboard layouts make extensive use of dead keys. For example the
[British or American international
layouts](https://en.wikipedia.org/wiki/British_and_American_keyboards#International_or_extended_keyboard_layouts). In
Linux (or FreeBSD, ...) you can select the American international
layout by selecting “English (US, international with dead keys)” in
the setup of your desktop.

The “English (US, international with dead keys)” layout looks like this:

{{<
figure src="/images/user-docs/800px-KB_US-International.svg.png"
caption="English (US, international with dead keys) (picture from [Wikipedia](https://en.wikipedia.org/wiki/British_and_American_keyboards#/media/File:KB_US-International.svg))"
>}}

The keys marked in red on this layout are “dead” keys.

Of course that “English (US, international with dead keys)” is not the only layout with dead keys, many national layouts use dead keys as well.

###### 5_2
## The “Compose” key

Wikipedia explains nicely what a [Compose
key](https://en.wikipedia.org/wiki/Compose_key) is. It is often also
called “multi key” (because the keysym defined in
`/usr/include/X11/keysymdef.h` is `XK_Multi_key`).

Some examples for Compose sequences involving a Compose key:

| Compose sequence involving Compose key | Result |
| --- | --- |
| `compose` `~` `n` | ñ  U+00F1 LATIN SMALL LETTER N WITH TILDE |
| `compose` `o` `c` | © U+00A9 COPYRIGHT SIGN |
| `compose` `1` `2` | ½ U+00BD VULGAR FRACTION ONE HALF |
| `compose` `-` `-` `-` | — U+2014 EM DASH |
| `compose` `n` `o` `n` `s` `e` `n` `s` `e` | probably undefined sequence, i.e. no result |

The default Compose key on Xorg seems to be `Shift`+`AltGr`, but it maybe
on some other key depending on you keyboard layout.

In some desktops, for example in Gnome3, you can also easily choose which key to use
for Compose in the system settings. The following example video shows
how to do that in Gnome3 on Fedora 34:

{{< video label="Selecting the Compose key in Gnome3 on Fedora 34" webm="/videos/user-docs/selecting-compose-key-in-gnome3-fedora34.webm" >}}

“Dead key sequences” and “Compose sequences” are basically the same
thing as far as Xorg, Gtk, IBus, and Typing Booster are concerned.

* Xorg:

  Displays nothing while the sequence is typed, only the final
  result is displayed. Undefined sequences are silently discarded.

* Gtk, IBus, Typing Booster:

  Try to be more helpful and display a Compose or dead key
  sequence in progress, allow fixing sequences with BackSpace, do
  something more useful with undefined sequences and more …

The official [“ISO keyboard symbol for "Compose Character"”](https://en.wikipedia.org/wiki/File:ISOIEC-9995-7-015--ISO-7000-2021--Symbol-for-Compose-Character.svg)
according to this [Wikipedia article](https://en.wikipedia.org/wiki/Compose_key)
is ⎄ U+2384 COMPOSITION SYMBOL.

The compose sequence implementations in Gtk, IBus, and Typing Booster
used to display that symbol, for example when `compose` `~` was typed,
<span style="text-decoration: underline">`⎄~`</span> was displayed
indicating the unfinished compose sequence.

Unfortunately some people found `⎄` to big, wide and distracting 😭.
Therefore, Gtk changed to display `compose` as <span
style="text-decoration: underline">`·`</span> (· U+00B7 MIDDLE
DOT). **And**, a leading <span style="text-decoration:
underline">`·`</span> is only displayed until the next character has
been typed, then **vanishes!**

Examples how Gtk now displays compose and dead key sequences:

| Typed compose sequence | Display |
| --- | --- |
| `compose` | <span style="text-decoration:underline">`·`</span> |
| `compose` `-` | <span style="text-decoration:underline">`-`</span> |
| `compose` `-` `-` | <span style="text-decoration:underline">`--`</span> |
| `compose` `-` `-` `-` | — (sequence finished, — U+2014 EM DASH is displayed) |
| `dead ~` | <span style="text-decoration:underline">`~`</span> |
| `dead ~` `compose` | <span style="text-decoration:underline">`~·`</span> |
| `dead ~` `compose` `b` | <span style="text-decoration:underline">`~·b`</span> |
| `dead ~` `compose` `b` `a` | ẵ (sequence finished, ẵ LATIN SMALL LETTER A WITH BREVE AND TILDE is displayed. Yes, that sequence actually exists in `/usr/share/X11/locale/en_US.UTF-8/Compose` 😁) |

IBus and Typing Booster then also changed and followed the way Gtk
displays this to have a consistent user experience across these 3
compose sequence implementations.

###### 5_3
## Customizing compose sequences

The [man page for
compose](https://www.x.org/releases/X11R7.5/doc/man/man5/Compose.5.html)
(Also available as `man compose` on most distributions) explains from
which file the default compose sequence definitions are read and how a
user can override it with his own compose sequence definitions.

This man page says:

> The compose file is searched for in  the following order:
>
> - If  the  environment  variable $XCOMPOSEFILE is set, its value is used as the
>   name of the Compose file.
>
> - If the user's home directory has a file named .XCompose, it is  used  as  the
>   Compose file.
>
> - The  system  provided compose file is used by mapping the locale to a compose
>   file from the list in /usr/share/X11/locale/compose.dir.

For example, when `XCOMPOSEFILE` is not set, `~/.XCompose` does not
exist either and the current locale is `cs_CZ.UTF-8`, then the system
default compose sequence definitions are read from
`/usr/share/X11/locale/cs_CZ.UTF-8/Compose`.  When the current locale
is something like `xx_YY.UTF-8` where no
`/usr/share/X11/locale/xx_YY.UTF-8/Compose` file specific to that
locale exists, the US English one
`/usr/share/X11/locale/en_US.UTF-8/Compose` is read (These fallbacks
are defined in `/usr/share/X11/locale/compose.dir`).


However, if the users home directory has a file named `~/.XCompose` or
if the environment variable `XCOMPOSEFILE` is set, **only** that file
is used **instead** of the system default.

For example, a user Compose file `~/.XCompose` could look like this:

```
# %H  expands to the user's home directory (the $HOME environment variable)
# %L  expands to the name of the locale specific Compose file (i.e.,
#     "/usr/share/X11/locale/<localename>/Compose")
# %S  expands to the name of the system directory for Compose files (i.e.,
#     "/usr/share/X11/locale")

include "%L"

<Multi_key> <underscore> <period> <e> : "ė̄" # U+0117 LATIN SMALL LETTER E WITH DOT ABOVE U+0304 COMBINING MACRON
<Multi_key> <m> <o> <n> <k> <e> <y> <s> : "🙈🙉🙊"
<Multi_key> <m> <o> <u> <s> <e> : "🐁" # U+1F401 MOUSE
<Multi_key> <m> <o> <u> <s> <e> : "🐭" # U+1F42D MOUSE FACE
```

The `include "%L"` includes the system compose file for the current locale,
the lines below add user defined sequences. If an identical sequence
are defined again with a different result, the last definition “wins”.
I.e. of the two lines defining `<Multi_key> <m> <o> <u> <s> <e>`,
the second line overrides the first one.

As the user definitions are all **below** the `include "%L"` which
reads the system default, the user definitions override any system
default sequences in case there is a conflict.

If the `include "%L"` were not there in `~/.XCompose`, **only** the
user definitions in `~/.XCompose` would be available!

###### 5_4
## Special “Compose” features in Typing Booster

This section explains some details about the “Compose” implementation
in Typing Booster which are a bit special.

###### 5_4_1
## Why Typing Booster has its own “Compose” implementation

Typing Booster needed its own implementation of compose sequences
because it needs full control about such compose sequences **inside**
an already open preëdit.

For example, if one wants to type the German word “grün” and starts
typing “gr”, there is a preëdit displayed as

<span style="text-decoration:underline">`gr|`</span>

where <span
style="text-decoration:underline">`|`</span> indicates the cursor
position. Typing Booster then searches for completions. When a compose
sequence like `compose` `"` `u` is typed in this situation to get an
“ü”, the current preëdit must not be committed, but the compose
actually needs to add to the preëdit. That means a kind of preëdit
inside the preëdit is needed. While that compose sequence is typed it
displays:

<span style="text-decoration:underline">`gr·|`</span>
<span style="text-decoration:underline">`gr"|`</span>
<span style="text-decoration:underline">`grü|`</span>

Now “grü” is still in preëdit and Typing Booster can continue to
search for completions of “grü”.

One could even go back with Left (arrow-left) in the preëdit and
insert a compose sequence there. For example, if one types “grn” and
then Left, the preëdit displays

<span style="text-decoration:underline">`gr|n`</span>

Typing `compose` `"` `u` then displays:

<span style="text-decoration:underline">`gr·|n`</span>
<span style="text-decoration:underline">`gr"|n`</span>
<span style="text-decoration:underline">`grü|n`</span>

Now “grün” is in the preëdit and Typing Booster can continue to search
for completions.

###### 5_4_2
## Automatically add “missing” dead key sequences

To write the character ė̄ (U+0117 LATIN SMALL LETTER E WITH DOT ABOVE
U+0304 COMBINING MACRON) which is used for writing
[Samogitian](https://en.wikipedia.org/wiki/Samogitian_dialect#Writing_system)
it would be perfectly natural to write `dead ¯` `dead ˙` `e` or `dead
˙` `dead ¯` `e`.

But the Compose implementations in Xorg and IBus accept only dead key
sequences which are defined in one of the Compose files read. And
there are no such dead key sequences defined in
`/usr/share/X11/locale/en_US.UTF-8/Compose`.  Therefore, the Compose
implementations in Xorg and IBus currently just discard sequences like
`dead ¯` `dead ˙` `e` as undefined and produce no result at all.

That means to be able to write these perfectly natural and useful
dead key sequences, one would need to add something like

```
<dead_macron> <dead_abovedot> <e> : "ė̄ " # U+0117 LATIN SMALL LETTER E WITH DOT ABOVE U+0304 COMBINING MACRON
<dead_abovedot> <dead_macron> <e> : "ė̄ " # U+0117 LATIN SMALL LETTER E WITH DOT ABOVE U+0304 COMBINING MACRON
```

to the users `~/.XCompose` file and/or extend the system default file
`/usr/share/X11/locale/en_US.UTF-8/Compose`.

But the character from Samogitian used as an example here is not the
only character which could be reasonably written with dead key
sequences but the sequences are missing in
`/usr/share/X11/locale/en_US.UTF-8/Compose`.

Adding all such sequences which might make sense for some language
somewhere in the world would be a tedious, never ending project.
Hundreds, if not thousands of sequences would need to be added.

So why not interpret **any** dead key sequence which seems reasonable
but is not defined in the Compose file automatically as a fallback?
I.e. if the user types something like `dead ¯` `dead ˙` `e` and no
definition for `<dead_macron> <dead_abovedot> <e>` is found in the
Compose file(s) read, then interpret this “missing” sequence
nevertheless and produce something reasonable.

Typing Booster does this, if a sequence like

`dead first` `dead second` … `dead last` `base character`

is typed **and** no definition is found in the Compose file(s),
**and** the Unicode category of `base character` is either “Ll
(Letter, Lowercase)” or “Lu (Letter, Uppercase)”, then convert it into
a combining char sequence like

`base character` `combining char last` … `combining char second` `combining char first`

convert this combining character sequence to [Normalization Form C
(NFC)](https://unicode.org/reports/tr15/#Norm_Forms) and use that as
the result of the undefined dead key sequence?

That is very helpful and automatically adds a huge amount of perfectly
reasonable dead key sequences which are “missing” in the Compose files.

**If** a definition exists in the Compose file(s) read, this definition
has **always** priority, only if no definition exists this automatic
fallback is used.

###### 5_4_3
## Fallbacks for “missing” keypad sequences

From a user point of view, it should not matter whether
a character like `0`, `1`, …,`9`, `/`, `*`, `-`, `+`, `.` is typed
using the “normal” key or the respective key on the keypad/numberpad.

But in the Xorg Compose file, some compose sequences can be typed
only using the “normal” key. For example:

```
$ grep Ø /usr/share/X11/locale/en_US.UTF-8/Compose
<dead_stroke> <O>                       : "Ø"   Oslash # LATIN CAPITAL LETTER O WITH STROKE
<Multi_key> <slash> <O>                 : "Ø"   Oslash # LATIN CAPITAL LETTER O WITH STROKE
<Multi_key> <O> <slash>                 : "Ø"   Oslash # LATIN CAPITAL LETTER O WITH STROKE
<Multi_key> <KP_Divide> <O>             : "Ø"   Oslash # LATIN CAPITAL LETTER O WITH STROKE
```
and:

```
$ grep ½ /usr/share/X11/locale/en_US.UTF-8/Compose
<Multi_key> <1> <2>                     : "½"   onehalf # VULGAR FRACTION ONE HALF
```

I.e. one can type both orders `<Multi_key> <slash> <O>` **and**
`<Multi_key> <O> <slash>` to get “Ø” but when using KP_Divide instead
of slash only the order `<Multi_key> <KP_Divide> <O>` works and
`<Multi_key> <O> <KP_Divide>` does not work because it is
undefined. From a user point of view, both “<slash>” and “<KP_Divide>”
produce a “/”, there should be no difference in behaviour.  I think
that is the motivation for defining `<Multi_key> <KP_Divide> <O>` to
give the same result as `<Multi_key> <slash> <O>`, it should not
matter how the “/” is typed. But the reverse order `<Multi_key> <O>
<KP_Divide>` has apparently been “forgotten”.

It is similar when typing “½” using Compose, one can type it with
`compose` `1` `2` only using the “normal” `1` and `2` keys but not
using those on the keypad.

This doesn’t really make sense and I tried to make a [merge
request](https://gitlab.freedesktop.org/xorg/lib/libx11/-/merge_requests/82)
for libX11 upstream to add the apparently missing definitions.  But
this is a quite tedious undertaking, although my merge request tries
to add 246 “missing” definitions and I tried to find all missing
sequences, I still forgot to add a few sequences like the alternatives
to `<Multi_key> <1> <2>` using the keypad keys like `<Multi_key>
<KP_1> <KP_2>`, `<Multi_key> <KP_1> <2>`, `<Multi_key> <1> <KP_2>`.

So I added an automatic fallback to Typing Booster which works like this:

If something like `<Multi_key> <KP_1>` is typed and no sequence
starting like that is defined, try whether sequences starting with
`<Multi_key> <1>` can be found, if yes replace `<KP_1>` with `<1>` and
continue to interpret the sequence.

And the other way round: if something like `<Multi_key> <1>` is typed
and no sequence starting like that is defined, try whether sequences
starting with `<Multi_key> <KP_1>` can be found, if yes replace `<1>`
with `<KP_1>` and continue to interpret the sequence.

My current implementation of these fallbacks does still make a
difference between typing `<Multi_key> <KP_Divide>` and `<Multi_key>
<slash>` for example, because sequences starting **both** ways do
actually exist in the Compose file, but the number of possible
continuations is different.  `<Multi_key> <slash>` can be completed in
38 different ways but `<Multi_key> <KP_Divide>` can be completed only
in 27 different ways:

```
$ grep '^<Multi_key> <slash>' /usr/share/X11/locale/en_US.UTF-8/Compose | wc --lines
38
$ grep '^<Multi_key> <KP_Divide>' /usr/share/X11/locale/en_US.UTF-8/Compose | wc --lines
27
```

I.e. when typing `<Multi_key> <KP_Divide>`, Typing Booster currently does not
attempt to replace `<KP_Divide>` with `<slash>` because
sequences starting with `<Multi_key> <KP_Divide>` actually are defined!
So there are sometimes still subtle diffences between using the “normal”
and the keypad keys, typing `<Multi_key> <KP_Divide>` offers fewer
possibilities than typing `<Multi_key> <slash>` does.

Of course Typing Booster could easily treat “normal” and keypad keys
as 100% identical **always** in compose sequences. I did not do that
because I wanted to keep the possibility to define **really
different** results for sequences involving the “normal” versus the
keypad keys.

For example, with my current implementation, it is still possible to
possible to define something like this

```
<Multi_key> <1> <2>                     : "½"
<Multi_key> <KP_1> <KP_2>               : "1️⃣2️⃣"
```

i.e. to define different results for a sequence using the “normal”
keys and for the similar sequence using the keypad keys. Seems a bit
crazy to me, I cannot imagine why somebody would want to define
something like that, but there might be reasons for wanting to make
such differences and I didn’t want to take away that possibility.

Just as in [Automatically add “missing” dead key sequences](#5_4_2),
**if** a definition exists in the Compose file(s) read, this
definition has **always** priority, only if no definition exists
Typing Booster tries to be helpful and offers a reasonable fallback.

###### 5_4_4
## How undefined sequences are handled

When an undefined compose or dead key sequence is typed using
Xorg/libX11, the result is nothing at all, the sequence is just
silently discarded.  This can be tested by using xterm like this:

```
$ env XMODIFIERS=@im=none xterm
```

Setting `XMODIFIERS` to `@im=none` disables input methods like ibus,
i.e. this makes sure that the Compose implementation in Xorg/libX11 is
used.

IBus 1.5.24 does the same as Xorg when an undefined compose sequence
is typed, nothing happens, the sequence is silently discarded.  To
test the Compose implementation in IBus, make sure that the
`ibus-daemon` is running, configure a keyboard layout with the needed
dead keys in `ibus-setup`, then switch to that keyboard layout and
test for example in `gedit`.

Gtk3 tries to be more helpful and instead of silently discarding  the sequence
do something more useful.
The Compose implementation in Gtk3 can be tested by using `gedit` like this:

```
$ env GTK_IM_MODULE=gtk-im-context-simple gedit
```

Typing Booster also tries to be more helpful and do something more useful
than just discarding the undefined sequence.

This table shows some examples for undefined compose sequences and
what the result is when typing the sequence in the 4 different
compose implementations:

| Undefined compose sequence | Xorg (libX11 1.7.2) | IBus 1.5.24 | Gtk3 3.24.30  | Typing Booster 2.14.4 |
|---|---|---|---|---|
| `dead_circumflex` `@` | nothing | nothing | ^@ | <span style="text-decoration: underline">^</span> <br> (keep `dead_circumflex` in preëdit and beep) |
| `dead_circumflex` `x` | nothing | nothing | ^x | x̂ <br> (x +  ̂  U+0302 COMBINING CIRCUMFLEX ACCENT) <br> (Because of [automatic dead key fallback](#5_4_2)) |
| `dead_macron` `dead_abovedot` `e` | nothing | nothing | ¯ ̇e |  ė̄  <br> (ė U+0117 LATIN SMALL LETTER E WITH DOT ABOVE +  ̄  U+0304 COMBINING MACRON) <br> (Because of [automatic dead key fallback](#5_4_2)) |
| `compose` `-` `-` `x` | nothing | nothing |  nothing | <span style="text-decoration: underline">--</span> <br> (keep `compose` `-` `-` in preëdit and beep) |
| `compose` `KP_1` `KP_2` | 2 <br> (`compose` `KP_1` produces nothing, then `KP_2` produces “2”)| 2 <br> (`compose` `KP_1` produces nothing, then `KP_2` produces “2”) |  2 <br> (`compose` `KP_1` produces nothing, then `KP_2` produces “2”) | ½ <br> (Because of [fallback for “missing” keypad sequences](#5_4_3) it falls back to the defined sequence `compose` `1` `2`) |

The behaviour of Typing Booster for undefined compose sequences is:

* try [automatic dead key fallback](#5_4_2)
* try [fallback for “missing” keypad sequences](#5_4_3)

If that didn’t help, discard only the key which made the sequence
invalid, keep the valid part of the sequence in preëdit, and play an
error beep.

When hearing the error beep, the user can then type Tab to [show how
the sequence could be completed](#5_4_5).

###### 5_4_5
## Show possible completions of compose sequences

{{< video label="Show possible completions of compose sequences" webm="/videos/user-docs/show-possible-completions-of-compose-sequences.webm" >}}

This video shows how possible completions of partially typed compose
sequences can be displayed by typing a key bound to the command
“enable_lookup” (by default that is ['Tab', 'ISO_Left_Tab']).

First the keyboard layout “English (US, euro on 5)” is selected, then
“Typing Booster” (Typing Booster always uses the keyboard layout which
was used last before switching to Typing Booster!).

Then `compose` `-` is typed.

(Look [here](#5_2) for details about what the compose key is and to see a video showing
how to choose a compose key in Gnome3).

The compose sequence `compose` `-` is not complete yet.
Now Tab is typed and a candidate list pops up showing how this incomplete
compose sequence could be completed. There are 29 possible completions.
For example, in the first page of possible completions one can see:

```
(1/29)
1 ␠     ~       U+007E tilde
2 (     {       U+007B left curly bracket
3 )     }       U+007D right curly bracket
4 +     ±       U+00B1 plus-minus sign
5 ,     ¬       U+00AC not sign
6 /     ⌿       U+233F apl functional symbol slash bar
7 :     ÷       U+00F7 division sign
8 >     →       U+2192 rightwards arrow
9 A     Ā       U+0100 latin capital letter a with macron
```

The first column after the numbers of the candidates show the keys
which could be typed to continue the compose sequence, the second
column shows what the result would be and the third column shows
detailed Unicode information about that result.

So candidate number 4 tells us, that typing `compose` `-` `+` would
produce a “±”.

One can of course select a candidate as always from such a candidate
list.  Or cancel the candidate list by typing Escape and continue
typing.

If something was selected already in the candidate list, indicated by
the a blue background in Gnome3, the first Escape just cancels that
selection, the second Escape then closes the candidate list. If
nothing is selected, Escape closes the candidate list
immediately. Continuing to type the compose sequence while nothing is
selected in the candidate list, also closes the candidate list.

Next, in the video, the Page_Down and Page_Up keys are used
to scroll through the candidate list and see what is available
as completion for the unfinished compose sequence `compose` `-`.

Then, Escape is typed to cancel the selection and another `-` is typed.
Now we have the still unfinished compose sequence `compose` `-` `-`.

Another Tab brings up a list of possible completions for this unfinished sequence.

```
(1/3)
1 ␠     ­       U+00AD soft hyphen
2 -     —       U+2014 em dash
3 .     –       U+2013 en dash
```

So typing the complete sequences `compose` `-` `-` `space` would give the “soft hyphen”,
`compose` `-` `-` `-` the “em dash”, `compose` `-` `-` `.` the “en dash”.

In the video, candidate number 2, the “em dash” is selected with the mouse.

Next `compose` `'` is typed followed by Tab. We see that there are 68 possible completions.
In the video Page_Down and Page_Up are used again to scroll through the completions,
then the selection is cancelled with Escape, then an `A` is typed to
complete the compose sequence: `compose` `'` `A` gives “Á”.

Next, in the video, the Greek keyboard layout is chosen in the Gnome
panel, then “Typing Booster” is chosen again. Typing Booster now uses
a Greek keyboard layout because that was the last active one.

Again `compose` `'` is typed and then Tab to show the possible completions of the
unfinished compose sequence.

Now we have 154 possible completions, much more than the 68 when we
were using the “English (US, euro on 5)” layout! Why is that?
To avoid always showing many hundreds of completions, Typing Booster
shows only those which are actually possible to type on the current
keyboard layout. If the current keyboard layout does not have a certain
key, completions involving that key are not shown.

Scrolling down to one of the last pages of candidates shows:

```
(127/154)
…
8 💀᾿α  ἄ       U+1F04 greek small letter alpha with psili and oxia
…
```

I.e.  it is possible to type a “ἄ” (U+1F04 GREEK SMALL LETTER ALPHA WITH PSILI AND OXIA)
by typing `compose` `'` `💀᾿` `α`.

The `💀᾿` indicates a “dead psili”. Some keyboard layouts have both a
dead version of a key **and** also the non-dead version of a key.  For
example a layout may have a “tilde” **and** also a “dead tilde” key.
It is necessary to distinguish that and press the correct key, either
the dead or non-dead key while typing a compose sequence. Therefore,
the candidates showing the possible compose completions make that
distiction by showing dead keys with a `💀` prefix.  I.e. `~` is a
normal tilde, `💀~` is a “dead” tilde.

While the “English (US, euro on 5)” was used, `💀᾿` `α` was not shown
as a possible completion for `compose` `'` because that keyboard
layout neither has the dead psili nor the “α”.

Finally, in the video, that candidate number 8, “ἄ” is selected using
the mouse.

###### 5_4_5_1
## A peculiarity of Gnome3 and compose completions

This chapter is specific to Gnome3, as far as I know none of the other
desktops does this weird grouping of keyboard layouts in groups of 3.

You may have noticed that there were more than 2 keyboard layouts in the Gnome panel.
The Gnome panel showed:

|Input source name | indicator | comment |
|---|---|---|
|English (US, euro on 5)     |en₁| keyboard layout|
|Other (Typing Booster)      |🚀 | input engine|
|Japanese (Anthy)            |あ | input engine|
|English (India, with rupee) |en₂| keyboard layout|
|English (US)                |en₃| keyboard layout|
|Greek                       |gr | keyboard layout|

So there were 4 keyboard layouts and 2 input engines.
The first 3 keyboard layouts were all minor variations of
the “English (US) layout”, they differ very little in which keys are available.

The Greek layout is then the 4th layout.  Gnome3 groups layouts into
groups of 3, i.e. the first group of layouts contains the 3 US English
layouts, the second group only the Greek layout.

This grouping of keyboard layouts in Gnome3 has the side effect that
calling the function `Gdk.Keymap.get_for_display(display)` to find out
which keys are available on the current layout returns all keys
available in the current **group** of 3 layouts!

I.e. when “English (US, euro on 5)” is selected, the list of keys used
to figure out which compose sequences are possible to type with the
current layout are actually the combined lists of keys of “English
(US, euro on 5)” **and** “English (India, with rupee)” **and**
“English (US)”.  Which is not a much bigger list of keys than any of
these US English layouts on its own as the differences between these 3
layouts are very small.  I did choose 3 almost identical layouts in
the first group of 3 on purpose to be able to demonstrate in the video
in the previous section how showing the compose completions is limited
to the current layout.

If I had use a setup with only these input sources:

|Input source name | indicator | comment |
|---|---|---|
|English (US, euro on 5)     |en | keyboard layout|
|Other (Typing Booster)      |🚀 | input engine|
|Japanese (Anthy)            |あ | input engine|
|Greek                       |gr | keyboard layout|

both “English (US, euro on 5)” and “Greek” would have been in the
first group of 3 keyboard layouts and no matter whether the “English
(US, euro on 5)” or the “Greek” was active, the possible compose
completions shown would have always included all keys from both the
English and the Greek layout!

###### 5_4_6
## Optional colour for the compose preëdit

{{< video label="Optional colour for the compose preëdit" webm="/videos/user-docs/optional-color-for-the-compose-preedit.webm" >}}

The video shows how a different colour can be chosen for the compose part of the preëdit.

First the option  “☐ Use color for compose preview” is switched off.

Then “sur” is typed and then two times Left to move the cursor back behind
the “s”. Then `compose` `o` `e` is typed which produces an “œ” to turn this
into the French word “sœur”. While typing this, the preëdit changes as follows:

“s” → “su” → “sur” → “s·ur” → “sour” → “sœur”

Then the option “☑️ Use color for compose preview” is switch on again
and the same typing is repeated. Now the preëdit changes as follows:

“s” → “su” → “sur”
→ “s<span style="color:#58FF33">·</span>ur”
→ “s<span style="color:#58ff33">o</span>ur”
→ “sœur”

Without the colouring of the compose part of the preëdit, it is hard to see
that “sour” actually still  contains an unfinished compose sequence, **especially**
because the · (U+00B7 MIDDLE DOT) representing the `compose` key has vanished.

Using colour in the compose part of the preëdit makes it much more obvious
which part of the preëdit was already there before the compose sequence was
started and which part is an unfinished compose sequence.

###### 6
## Unicode symbols and emoji predictions

ibus-typing-booster supports prediction of emoji and Unicode symbols as well (actually almost all Unicode characters except letters can be typed this way). This can be enabled or disabled with the option “Emoji predictions” in the setup tool which is on by default.

To make all emoji display correctly, you need good fonts which contain all emoji, see Emoji fonts for details about available fonts and font setup.


###### 6_1
### Emoji input

{{< video label="Typing Emoji in English with Emoji option on" webm="/videos/user-docs/emoji-english-emoji-option-on.webm" >}}

When the “☑️ Unicode symbols and emoji predictions” option is on (it is
off by default), you get emoji displayed in the candidate list
automatically when typing something which matches an emoji.

For example in this video, the user has types “camel”, “Albania”, and
“castle” and suitable emoji are shown in the candidate list.

If reasonable matches for emoji are found, the first match is shown as
the last candidate of the first page of the candidate list (Unless, as
in the case of “Albania”, the candidate list has only one page, then
it might not be the last candidate).

If more than one emoji has matched the input and the candidate list
has more than one page, the other matches can be found by scrolling
down to the next page of candidates. If an emoji is selected and
committed, it will be remembered just like ibus-typing-booster
remembers other words and will be shown with higher priority next
time.

As having the “☑️ Unicode symbols and emoji predictions” option enabled
slows down the search for predictions, you might want to look
at [Quickly toggling emoji mode on and off](#6_8), especially if you
use emoji only occasionally.

###### 6_2
## Emoji input fuzzy matching

{{< video label="Emoji input fuzzy matching" webm="/videos/user-docs/emoji-english-fuzzy-castle.webm" >}}

Ibus-typing-booster tries to match the emoji names in a fuzzy way, in
many cases you will get a match even if your input contains spelling
mistakes.

In this example video, the input “casle” is typed, i.e. it is not
spelled correctly. Nevertheless, one gets the match 🏰 (U+1F3F0
EUROPEAN CASTLE).


###### 6_3
### Emoji input using multiple keywords

{{< video label="Emoji input using multiple keywords" webm="/videos/user-docs/emoji-english-multiple-keywords-castle-japanese.webm" >}}

This video shows how to use multiple keywords to search for emoji.

If typing a single word does not give you the emoji you are looking
for, you can type as many keywords as you like and concatenate them
with underscores “_” (Or spaces “ ”. Typing space usually commits the
preëdit, but you can insert literal spaces into the preëdit by typing
AltGr+Space).

In a previous example, typing “castle” gave us the match 🏰 (U+1F3F0
EUROPEAN CASTLE). If this is not what we wanted we can type
“castle_japanese” (or “japanese_castle”) to get 🏯 (U+1F3EF JAPANESE
CASTLE).

###### 6_4
### Looking up related emoji

{{< video label="Looking up related emoji" webm="/videos/user-docs/related-emoji.webm" >}}

It is also possible to look up related emoji which may not have
matched the typed text well but are related to the emoji shown because
they share keywords or categories.

To show related emoji, click an emoji shown in the candidate list with
the right mouse button (see [Mouse bindings](#3_3)).

Or, if you prefer to use a key binding instead of the mouse: select an
emoji in the candidate list by moving up or down in the candidate list
using the arrow-up/arrow-down keys or the page-up/page-down keys until
the desired emoji is highlighted, then press AltGr+F12.

AltGr+F12 is the default key binding for the command
“lookup_related”. If you press this while no candidate is selected, a
lookup of related stuff for the preëdit is tried. In this case, the
preëdit contains the text “liz” which is not an emoji. So no
related emoji will be found. But if NLTK is used, related words for
“liz” may be shown, see [Using NLTK to find related words](#7).

As seen in the screen shot, looking up related emoji for the “lizard”
gives us emoji for other types of reptiles and related animals. By
typing the “Escape” key, one can go back to the original list.


###### 6_5
### Multilingual emoji input

###### 6_5_1
#### Emoji input using German and English

{{< video label="Emoji input using German and English" webm="/videos/user-docs/emoji-german-english.webm" >}}

In this example video, Typing Booster is used with dictionaries setup for British English
and German in the setup tool.

Therefore, one can use both the English word “castle” or the German
word for castle “Schloss” to find castle emoji.

The German word “Schloss” means “castle” but also “lock”. Therefore,
typing “Schloss” not only matches 🏰 (U+1F3F0 EUROPEAN CASTLE) and 🏯
(U+1F3EF JAPANESE CASTLE but also 🔓 (U+1F513 OPEN LOCK) and other
lock emoji.

###### 6_5_2
#### Emoji input using Hindi and English

{{< video label="Emoji input using Hindi and English" webm="/videos/user-docs/emoji-hindi-english.webm" >}}

This example video shows using Hindi and English to lookup emoji.

Both languages are configured in the setup tool (See: [Basic setup for
your language](#2_1))

First “namaste” is typed. The transliteration method “hi-itrans”
transliterates this to “नमस्ते” which is shown in the preëdit because
the “hi-itrans” input method is at the highest priority (For details
about multilingual input and how to switch the script shown in the
preëdit, see [Multilingual input](#4)).

Both “namaste” and “नमस्ते” are then used to search for matching words
and emoji. Only “नमस्ते” matches an emoji which can be seen in the
candidate list (🙏 U+1F64F PERSON WITH FOLDED HANDS and skin tone
variants of this emoji).

Second, “folded_hands” is typed. As the highest priority input method
is still “hi-itrans”, this is shown as nonsensical Devanagari in the
preëdit.  But both this nonsensical Devanagari and “folded_hands” are
used to find matches and “folded_hands” finds 🙏 and skin tone
variants as well.

Typing Control+Down then changes the priority of the input methods and
puts “NoIME” on top which reveals that “folded_hands” was actually
typed as this is now shown in the preëdit.

###### 6_5_3
#### Emoji input using Japanese

{{< video label="Emoji input using Japanese" webm="/videos/user-docs/emoji-japanese.webm" >}}

This video shows that emoji can be searched using Japanese keywords as
well.

To be able to input emoji using their Japanese names, one first needs
to install the packages `m17n-db-extras`, `m17n-lib-anthy` and `anthy`
on Fedora. On Fedora 34 one can do this using the command:

`sudo dnf install m17n-db-extras m17n-lib-anthy`

This should work on other distributions as well, but the package names
may be different. You need the package which contains the
`/usr/share/m17n/ja-anthy.mim` file and other packages which are
required to make the ja-anthy input method of the m17n library work.

Then one needs to add the “ja-anthy” input method and the Japanese
dictionary (“ja_JP”) to the setup of ibus typing booster. For details
how to add input methods and dictionaries see [Basic setup for your
language](#2_1).

Now one can type emoji keywords using Japanese. For example when
typing “katasumuri” (which means “snail”), one gets the emoji 🐌
(U+1F40C SNAIL) listed as a candidate.

It is labelled in the candidate list in Japanese hiragana syllables,
i.e. “かたつむり”. The Latin “katatsumuri” was transliterated by the
ja-anthy input method to “かたつむり” and this was then looked up in
the dictionaries. The Latin text “katatsumuri” was of course looked up
as well but of course produced no match.

Switching the priority of the input methods with “Control+Down” or
“Control+Up” toogles the display of the preedit between Latin letters
“katatsumuri” (when “NoIME” has highest priority) and Hiragana letters
“かたつむり” (when “ja-anthy” has highest priority).  This makes no
difference for the matches, still both “katatsumuri” and “かたつむり”
are looked up in the dictionaries. Only when committing the preëdit
now by typing a space, it would matter because it would commit the
Hiragana “かたつむり” or the Latin “katatsumuri” as seen in the moment
when the space is typed.

Near the end of the video, a right click with the mouse on the snail
in the candidate list shows related emoji. These related emoji are
labelled with English names because the British English dictionary has
highest priority in the setup tool. When the Japanese dictionary had
the highest priority in the setup tool, the related emoji would be
shown with their Japanese names.

###### 6_6
### Unicode symbol input

{{< video label="Unicode symbol input" webm="/videos/user-docs/unicode-symbol-input.webm" >}}

This video example shows how arbitrary Unicode symbols and characters
can be input with Typing Booster.

Using the emoji input mode of Typing Booster, one cannot only input
emoji but other Unicode symbols as well. Actually almost all Unicode
characters can be typed this way (Except most letters, because letters
can usually typed much faster directly, allowing to search for normal
letters this way would make the search needlessly slow).

In the video, first “integral” is typed and one gets several
mathematical characters for integrals in the candidate list and can
scroll down to the next pages for more.

If one wants to be more specific, one can also type more than one keyword
by combining keywords with “_” (see [Emoji input using multiple keywords](#6_3)).
For example one can type something like “volume_integral” to get more specific matches
for integral signs related to volume integrals.

Next “pop_direc” is typed which matches U+202C POP DIRECTIONAL
FORMATTING and U+2069 POP DIRECTIONAL ISOLATE. These are invisible
formatting characters used in scripts which use right-to-left
direction, for example in Arabic script.

Finally “radical_turtle” is typed which finds the CJK radicals for
“turtle”.

Anything in Unicode except normal letters is possible.


###### 6_7
### Unicode code point input

{{< video label="Unicode code point input" webm="/videos/user-docs/unicode-code-point-input.webm" >}}

This example video shows how the “☑️ Unicode symbols and emoji predictions” feature
of Typing Booster can also be used to input characters using their Unicode code point.

As Unicode code points are hexadecimal numbers, it is first necessary
to make it possible to input digits at all into the preëdit. By
default, both the digits on the regular keyboard layout **and** the
digits on the keypad are bound to commands committing candidates. So
if you want to be able to type digits into the preëdit, you have to
remove either the regular digits or the keypad digits from the
keybindings, whichever you prefer.

You can also remove both from the keybindings if you want, that still
leaves you with the F1 … F9 keys to commit candidates.

The video shows the key bindings tab of the setup tool and one can see
that there are no KP_1 … KP_9 keys used in the commands to commit
candidates.  So the keypad with NumLock on can be used to type digits
into the preëdit.

First “100” is typed in the video. It matches 💯 U+1F4AF HUNDRED
POINTS SYMBOL which is an emoji which has been matched because of its
alternative name “100” **and** Ā U+0100 LATIN CAPITAL LETTER A WITH
MACRON which has been matched because it has the Unicode code point
100 (hexadecimal). It is quite rare that typing a Unicode code point
matches an emoji as well. There will never be many candidates when
typing Unicode code points.

Then “2019” is typed which matches ’ U+2019 RIGHT SINGLE QUOTATION MARK.

Then “20B9” is typed which matches ₹ U+20B9 INDIAN RUPEE SIGN.

###### 6_8
### Quickly toggling emoji mode on and off

{{< video label="Quickly toggling emoji mode on and off" webm="/videos/user-docs/emoji-quick-toggle.webm" >}}

When “☑️ Unicode symbols and emoji predictions” is enabled, finding
matching candidates can be considerably slower compared to when emoji
mode is switched off. Especially if the emoji lookup is done in
multiple languages at the same time. In this case, there may be a
noticeable delay until the candidate list pops up.

Therefore, “☐ Unicode symbols and emoji predictions” is disabled by default
to show normal word predictions with maximum speed.

Always opening the setup tool to switch emoji mode on if one
occasionally wants to input an emoji would be inconvenient. Therefore,
emoji mode can also be toggled with a mouse binding (Control+Button3
anywhere in the candidate list toogles emoji mode between on and off)
or with a key binding (AltGr+F6 toggles emoji mode between on and
off).

But there is an even faster way to temporarily switch on emoji mode
just for the current lookup.

In the example video we can see that even if emoji mode is off (which
can be seen in the options tab of the setup tool also shown in the
video) we get emoji matches by appending keywords with “_”.  “camel_”,
“frog_”, “India_” match emoji even though “☐ Unicode symbols and emoji
predictions” is disabled.

Using these trailing underscores “_” temporarily turns on emoji search
just for this one lookup.


###### 6_9
### Emoji picker

{{< video label="Emoji picker" webm="/videos/user-docs/emoji-picker.webm" >}}

ibus-typing-booster contains an “emoji-picker” tool which can be used
independently from ibus-typing-booster, i.e. even when
ibus-typing-booster is not running.

In Fedora, “emoji-picker” is packaged as sub-package of
ibus-typing-booster named “emoji-picker”, so it might not be installed
but you can install it with:

`$ sudo dnf install emoji-picker`

From the command line “emoji-picker” can be started with and optional list
of languages:

`$ emoji-picker  -l en:ja:fr:it:hi:ko:zh &`

(The `-l` option to specifying some languages is optional, see
explanation about the options below).

Clicking with the left mouse button on an emoji shown in
“emoji-picker” puts it into the clipboard and you can then paste it
somewhere using Control+V or the middle mouse button.

Clicking the right mouse button on an emoji shown in “emoji-picker”
shows the emoji much bigger and some extra information about that
emoji, like the Unicode code point(s), the name and search keywords of
the emoji in all chosen languages, the fonts really used to render
this emoji, the Unicode version this emoji first appeared in, and a
link to lookup this emoji in emojipedia.

The fonts really used to render an emoji may differ from the font
chosen in the user interface of emoji picker because:

* The chosen font may have no glyph for a certain emoji. In that case,
  if there is any other font installed on the system which has that
  emoji, a fallback font will be used to render the emoji (Unless the
  “☑️ Fallback” option at the top of emoji-picker is switched
  off!). The info popover shown on right mouse click will show which
  font was really used, i.e. it enables one to see which font was used
  as a fallback.

* Some emoji are sequences of several code points and with some fonts
  (or when there are bugs in the rendering system), it may not be
  possible to render the sequence correctly and one may see individual
  parts of the sequence rendered seperately, possibly even different
  parts of the sequence in different fonts. The info popover shown on
  right mouse click shows which font was used for which part of the
  sequence which is helpful to debug such problems.

Emoji can also be selected with different skin tones. If the mouse
hovers over an emoji for which different skin tones are available, a
tooltip says “Long press or middle click for skin tones”. Long
pressing such an emoji with the left mouse button or clicking it with
the middle mouse button pops up a menu showing all the skin tone
variants. One can then click on any variant with the left mouse button
to put it into the clipboard and paste it elsewhere.

Which skin tone was last used is remembered, i.e. the emoji shown
before opening the menu for the skin tones is the emoji with the skin
tone variant used last for this emoji.

There is also a “🕒 Recently used” section at the top left of “emoji-picker”.

Clearing the recently used characters resets all emoji to neutral skin
tone by default.

“emoji-picker” also has a “Search” feature where you can type a search
string and get matching emoji listed.

The search string can be in any of the languages specified by the
environment variables or on the command line.

In the search results as well you can do the same things as when browsing
the emoji categories:

* Click on one of the matches to put it into the clipboard and paste it elsewhere.

* Right click on one of the matches to show the emoji bigger with extra information

* Long press left mouse button or click middle mouse button to show skin tones if available for that emoji.


“emoji-picker” has some command line options to choose the languages,
the font and the fontsize. For example,

```
$ emoji-picker --languages de:en:fr
```

would enable you to use German, English, and French to browse and
search for emoji and display the names of the emoji in all of these
languages. If the command line option is not used, the languages are
taken from the environment variables. The `LANGUAGE` variable works as
well. For example,

```
LANGUAGE=de:en:fr emoji-picker
```

also chooses German, English, and French. And,

```
LANG=de_DE.UTF-8 emoji-picker
```

would choose only German (English is always implicitly added as a
fallback though.)

The command line options to choose a different font or font size can
be used like this:

```
emoji-picker --font "Noto Color Emoji" --fontsize 32
```

The command line font options override the font options in the
graphical user interface.

For more about emoji fonts and colour, see [Emoji fonts](#6_10).

###### 6_10
### Emoji fonts

Good fonts to display emoji:

* “Noto Color Emoji”:

    * On Fedora, this font is in the `google-noto-emoji-fonts` package

    * On openSUSE in the `noto-coloremoji-fonts` package

    * If the version packaged for your distribution is not up-to-date,
      you can get the most recent version here:
      https://www.google.com/get/noto/. (Search for “Noto Color
      Emoji”).

* “Twemoji”:

    * Homepage: https://twemoji.twitter.com/
    
    * On Fedora, this font is in the `twitter-twemoji-fonts` package.

* “Symbola”:

    * Created by George Douros. The latest version (Version 13.00,
      released March 25, 2020)is available here:
      https://dn-works.com/ufas/

    * Distributions usually have packages old version of this font as
    the recent versions have a licence which does not allow to include
    it in distributions: “Free use of UFAS is strictly limited to
    personal use.”

    * “Symbola” is not really an emoji font, it is a black and white
    font (not even grayscale) and it doesn’t support emoji sequences,
    i.e. emoji which consist of mor than one character. That means
    emoji sequences like 👷 (👷 U+1F477 CONSTRUCTION WORKER, U+200D
    ZERO WIDTH JOINER, ♀ U+2640 FEMALE SIGN) will display as several
    glyphs and not as a single glyph showing a female construction
    worker. The same problem occurs for the flag sequences, the family
    emoji and all other emoji sequences. And the skin tones modifiers
    are shown as seperate characters following the emoji they are
    modifying as well.  Nevertheless “Symbola” is a phantastic font
    and I absolutely recommend to download its latest version and
    unpack the Symbola.zip file in your `~/.fonts/` directory. It has
    very beautifully drawn symbols, for example mathematical symbols
    which are just fine in black and white and which most other fonts
    don’t have.

The following video shows the above mentioned fonts used in “emoji-picker”:

{{< video label="Emoji font selection in emoji-picker" webm="/videos/user-docs/emoji-font-selection-in-emoji-picker.webm" >}}

###### 6_10_1
#### <span style="color:red">Historic:</span> Showing emoji in colour

Once upon a time it was not possible at all to display colourful emoji
using Linux.  The best one could get using color emoji fonts like
“Noto Color Emoji” were grayscale emojis which looked like this:

{{<
figure src="/images/user-docs/gnome-noto-color-emoji-grayscale.png"
caption="How emoji looked like on Linux before colour became possible"
>}}

Later one could use an experimental patch for Cairo which enabled
colour display of emojis.

On top of that Cairo patch one usually also had to fiddle with the
fontconfig font setup to give a good colour emoji font highest
priority, i.e. create a file `~/.config/fontconfig/fonts.conf` with
contents like [example fonts.conf](/other-files/fonts.conf) to give
the “Noto Color Emoji” the highest priority.

Luckily these times are long gone and as far as I know all recent
Linux distributions display nice, colourful emoji by default now.

###### 7
## Using NLTK to find related words

{{<
figure src="/images/user-docs/gnome-castle-word-related.png"
caption="Finding related words for “castle” with NLTK"
>}}

ibus-typing-booster can also find words which are related to any of the candidates displayed. To show related words for a candidate, move up or down in the candidate list using the arrow-up/arrow-down keys or the page-up/page-down keys until the desired emoji is highlighted, then press AltGr+F12 (When AltGr+F12 is pressed before moving in the candidate list, i.e. when no candidate at all is highlighted in the candidate list, the word from the preëdit is used to lookup related words). In the screen shot shown, “castle” was typed followed by AltGr+F12 and synonyms for “castle” are displayed. hypernyms or hyponyms may also be displayed.

Looking up related words like this currently only works for English. When trying to find related words for non-English words, nothing will happen.

The lookup of related words uses NLTK and will only work when NLTK for Python3 and the wordnet corpus for NLTK are installed. On Fedora, you can install it like this:
```
sudo dnf install python3-nltk
python3
import nltk
nltk.download()
```

A download tool for NLTK data as seen in the next screen shot opens, select the wordnet corpus and click the “Download” button:

{{<
figure src="/images/user-docs/nltk-wordnet-corpus-download.png"
caption="Downloading the Wordnet corpus"
>}}

###### 8
## Speech recognition

ibus-typing-booster supports speech recognition using the [Google Cloud Speech-to-Text](https://cloud.google.com/speech-to-text/) service which [supports 120 languages](https://cloud.google.com/speech-to-text/docs/languages).

This service is currently only free for up to 60 minutes per month, when using it for more than 60 minutes per month one has to pay a fee. The pricing is explained [here](https://cloud.google.com/speech-to-text/pricing).

To be able to use the Google Cloud Speech-to-Text service, one has to [setup a GCP Console project](https://cloud.google.com/speech-to-text/docs/quickstart-client-libraries).

The above link explains that one has to do the following things:

* Create or select a project.
* Enable the Google Speech-to-Text API for that project.
* Create a service account.
* Download a private key as a .json file.

The link explaining how to [setup a GCP Console project](https://cloud.google.com/speech-to-text/docs/quickstart-client-libraries) also mentions that one has to [install and initialize the Google Cloud SDK](https://cloud.google.com/sdk/docs/#linux). Actually doing that seems to be optional, I tried doing the ibus-typing-booster speech recognition without installing the Google Cloud SDK and it seems to work just fine without.

And one has to [install the client library for Python3](https://cloud.google.com/speech-to-text/docs/quickstart-client-libraries#client-libraries-install-python) . This link explains that you can install the client library with the command

`pip install --upgrade google-cloud-speech`

#### Attention: 
on most Linux distributions today, the above line will install the Python2 version of this client library. But ibus-typing-booster requires Python3, so you probably have to use

`pip3 install --upgrade google-cloud-speech`

to get the Python3 version of the client library (unless on your distribution `pip` already defaults to Python3 but that is rather unlikely at the moment). You can also add the `--user` option if you want to install this in the home directory of the user:

`pip3 install --user --upgrade google-cloud-speech`

And you need to install the Python3 module of pyaudio. How to do that depends on you Linux distribution. On Fedora 29 you can do it with: 

`sudo dnf install python3-pyaudio`

Finally, after the Google setup and the software installation is done,
you can enable speech recognition in ibus-typing-booster.

One necessary thing to set up is setting a key binding for speech
recognition. By default that key binding is empty, the screen shot
shows how to set it to something:

{{<
figure src="/images/user-docs/gnome-set-keybinding-for-speech-recognition.png"
caption="Set a key binding for speech recognition"
>}}

Another necessary thing to setup is to specify the location of the
“Google application credentials” .json file which you should have
downloaded above when [setting up a GCP Console
project](https://cloud.google.com/speech-to-text/docs/quickstart-client-libraries).

The screen shot shows that you can do that in the “Speech recognition” tab of the setup tool of ibus-typing-booster:

{{<
figure src="/images/user-docs/gnome-set-google-application-credentials-file.png"
caption="Set the “Google application credentials” .json file"
>}}

The language used for speech recognition is the language of the
dictionary with the highest priority in ibus-typing-booster.

You can see these dictionary priorities by opening the setup tool of
ibus-typing-booster and looking at the “Dictionaries and input
methods” tab. The dictionary at the top of the list has the highest
priority and the language of this dictionary is used for Google
Speech-to-Text.

Here you can also see for which languages speech recognition is
officially supported. The official list of languages supported by
Google Cloud Speech-to-Text is
[here](https://cloud.google.com/speech-to-text/docs/languages). In the
ibus-typing-booster setup tool “Dictionaries and input methods” tab, a
row for a language officially supported by Google Speech-to-Text is
marked with “Speech recognition ✔️”, a row for a language not
officially supported by Google Speech-to-Text is marked with “Speech
recognition ❌”.

In Googles official list, only “de_DE” is supported among the German
variants. Therefore, one can see in the screen shot that “de_CH” is
marked with “Speech recognition ❌”:

{{<
figure src="/images/user-docs/gnome-choose-language-for-speech-recognition.png"
caption="Choose the langauge for speech recognition"
>}}

But, when I tried it, I found that “de”, “de-DE”, “de-AT”, “de-CH”,
“de-BE”, “de-LU” all seem to work the same and seem to recognize
standard German. When using “de-CH”, it uses “ß” when spelling German
words even though “ss” is used in Switzerland instead of “ß”. There
seems to be no difference between using Google Speech-to-Text for all
these variants of German.

However, for “en-GB” and “en-US”, there is a difference, the produced
text uses British or American spelling depending on which one of these
English variants is used.

I don’t want to disallow using something like “de-CH” for speech
recognition just because it is not on the list of officially supported
languages. Therefore, I allow all languages to be used for speech
recognition. But when a language is not officially supported, I mark
it with “Speech recognition ❌” and you can try whether it works well
or not.

When trying to use a language which is really not supported by Google
Speech-to-Text, for example “gsw_CH” (Alemannic German in
Switzerland), it seems to fall back to American English, i.e. it
behaves as if speech recognition for “en_US” were used.

To switch to a different language for speech recognition you don’t
always have to open the setup tool, you can also use key bindings to
change the highest priority dictionary, see the commands
“next_dictionary” and “previous_dictionary” in the key bindings tab of
the setup tool.

And you can also change the highest priority dictionary by using the
Gnome panel (or the panel of your favourite desktop) or the ibus
floating panel on non-Gnome desktops.

To input using speech recognition, press the key which is bound to the
command “speech_recognition”. A popup appears near the writing
position showing something like “🎙en_GB 🇬🇧: ”. Now speak something and
what Google Speech-to-Text recognizes appears in that popup which then
may look like “🎙en_GB 🇬🇧: This is the text I have spoken”. When a
pause is detected in the voice recording, the speech recognition is
finalized and the result is inserted at the writing position.
