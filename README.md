# Ibus-typing-booster
Get faster typing experience by intelligent context sensitive completion.

## Backdrop & Introduction
_Ibus-typing-booster_ is a completion input method to speed-up typing.

The project was started in 2010 for [Fedora 15](https://en.wikipedia.org/wiki/Fedora_version_history#Fedora_15). The original purpose was to make typing of Indic languages easier and faster by providing completion and spell checking suggestions.

Originally it was forked from [ibus-table](https://github.com/acevery/ibus-table) whose developer was Yu Yuwei acevery@gmail.com, with contributions from Caius("kaio") chanceme@kaio.net.

Since then _ibus-typing-booster_ has been improved to support many other languages as well by supporting input methods from the [m17n project](https://savannah.nongnu.org/projects/m17n/).

Since version [2.27.23](https://github.com/mike-fabian/ibus-typing-booster/releases/tag/2.27.23) it finally supports **all** input methods from the [m17n project](https://savannah.nongnu.org/projects/m17n/), including those offering multiple candidates. This means that since Version [2.27.23](https://github.com/mike-fabian/ibus-typing-booster/releases/tag/2.27.23) it also supports Chinese and Japanese.

_ibus-typing-booster_ also has the capability to type several different languages at the same time without having to switch between languages.

## Developers
- Mike Fabian mfabian@redhat.com
- Anish Patil: anish.developer@gmail.com

## Features
- Context sensitive completions.
- Learns from user input.
- Can be trained by supplying files containing typical user input.
- If available, [hunspell dictionaries](https://github.com/hunspell/hunspell) will also be used to provide not only completion but also spellchecking suggestions (But _ibus-typing-booster_ can also work without _hunspell_ by learning from user input alone).
- Can be used with almost any keyboard layout.
- Almost all input methods supplied by [libm17n](https://pkgs.org/download/libm17n.so.0) are supported (including the [inscript2](https://fedoraproject.org/wiki/QA:Inscript2_Keymaps) input methods).
- Several input methods and languages can be used at the same time without switching.
- Predicts [Unicode](https://en.wikipedia.org/wiki/Unicode) symbols and emojis as well.

## Online documentation
You can find online documentation here: 
- [_ibus-typing-booster_ home page on github](http://mike-fabian.github.io/ibus-typing-booster/)
- [_ibus-typing-booster_ documentation page](http://mike-fabian.github.io/ibus-typing-booster/documentation.html)

## Feature Requests & Bug reports
- You can report bugs here:
[_ibus-typing-booster_ issue tracker on github](https://github.com/mike-fabian/ibus-typing-booster/issues)
- Request for new features here:
[_ibus-typing-booster_ pull request on github](https://github.com/mike-fabian/ibus-typing-booster/pulls)

## Contributing translations
The best (& the easiest) way to contribute translations is using this [online translation platform](https://translate.fedoraproject.org/projects/ibus-typing-booster/).

## Development
If  you want to build from  source or contribute to the development, see the
[ibus-typing-booster development page](http://mike-fabian.github.io/ibus-typing-booster/development.html).
There you'd also find the requirements for building from source
for most systems.

## Table of default key bindings
- [Default key bindings](http://mike-fabian.github.io/ibus-typing-booster/documentation.html#key-bindings)
- [Default mouse bindings](http://mike-fabian.github.io/ibus-typing-booster/documentation.html#mouse-bindings)

*Note: These bindings are also shown below for convenience. Some of these key bindings can be customized in the setup tool.*

The following table explains the defaults:

| Key Combination | Effect |
| --- | --- |
| <kbd>Space</kbd> | Commit the preëdit (or the selected candidate, if any) and send a <kbd>Space</kbd> to the application, i.e. commit the typed string followed by a space. |
| <kbd>Return</kbd> or <kbd>KP_Enter</kbd> | Commit the preëdit (or the selected candidate, if any) and send a <kbd>Return</kbd> or <kbd>KP_Enter</kbd> to the application. |
| <kbd>Tab</kbd> | Bound by default to the commands "select_next_candidate" and "enable_lookup".<ul><li> If the option "Enable suggestions by <kbd>Tab</kbd>" _is not set_ (&#9744;) then <kbd>Tab</kbd> always just executes "select_next_candidate" which selects the next candidate from the candidate list.</li><li>If the option "Enable suggestions by <kbd>Tab</kbd>" _is set_ (&#9745;), then no candidate list is shown by default: </li><ul><li>If no candidate list is shown: "enable_lookup" is executed which requests to show the candidate list (nothing might be shown if no candidates can be found).</li><li>If a candidate list is already shown: "select_next_candidate" is executed which selects the next candidate in the list. After each commit and after each change of the contents of the preëdit, the candidate list will be hidden again until the "enable_lookup" requests it again.</li></ul></ul>|
| <kbd>Shift</kbd>+<kbd>Tab</kbd> | Bound by default to the command "select_previous_candidate". Selects the previous candidate in the candidate list. |
| <kbd>Esc</kbd> | Bound by default to the command "cancel".<ul><li>When a candidate is selected (no matter whether this is a normal lookup table or a "related" lookup table): Show the first page of that lookup table again with no candidate selected.</li><li>When no candidate is selected:</li><ul><li>When a lookup table with related candidates is shown or a lookup table where upper/lower-case has been changed by typing the Shift key is shown: go back to the original lookup table.</li><li>When a normal lookup table is shown: close it and clear the preëdit.</li></ul></ul> |
| <kbd>←</kbd> | Move cursor one typed key left in the preëdit text. May trigger a commit if the left end of the preëdit is reached. |
| <kbd>Control</kbd>+<kbd>←</kbd> | Move cursor to the left end of the preëdit text. If the cursor is already at the left end of the preëdit text, trigger a commit and send a <kbd>Control</kbd>+<kbd>←</kbd> to the application. |
| <kbd>→</kbd> | Move cursor one typed key right in preëdit text. May trigger a commit if the right end of the preëdit is reached. |
| <kbd>Ctrl</kbd>+<kbd>→</kbd> | Move cursor to the right end of the preëdit text. If the cursor is already at the right end of the preëdit text, trigger a commit and send a <kbd>Ctrl</kbd>+<kbd>→</kbd> to the application. |
| <kbd>Backspace</kbd> | Remove the typed key to the left of the cursor in the preëdit text. |
| <kbd>Ctrl</kbd>+<kbd>Backspace</kbd> | Remove everything to the left of the cursor in the preëdit text. |
| <kbd>Delete</kbd> | Remove the typed key to the right of the cursor in the preëdit text. |
| <kbd>Ctrl</kbd>+<kbd>Delete</kbd> | Remove everything to the right of the cursor in the preëdit text. |
| <kbd>↓</kbd> | Bound by default to the command "select_next_candidate". Selects the next candidate. |
| <kbd>↑</kbd> | Bound by default to the command "select_previous_candidate". Selects the previous candidate. |
| <kbd>Pg Up</kbd> | Bound by default to the command "lookup_table_page_up". Shows the previous page of candidates. |
| <kbd>Pg Down</kbd> | Bound by default to the command "lookup_table_page_down". Shows the next page of candidates. |
| <kbd>F1</kbd> | Commit the candidate with the label "1" followed by a space. |
| <kbd>F2</kbd> | Commit the candidate with the label "2" followed by a space. |
| ... | ... |
| <kbd>F9</kbd> | Commit the candidate with the label "9" followed by a space. |
| <kbd>Ctrl</kbd>+<kbd>F1</kbd> | Remove the candidate with the label "1" from the database of learned user input (If possible, if this candidate is not learned from user input, nothing happens). |
| <kbd>Ctrl</kbd>+<kbd>F2</kbd> | Remove the candidate with the label "2" from the database of learned user input (If possible, if this candidate is not learned from user input, nothing happens). |
| ... | ... |
| <kbd>Ctrl</kbd>+<kbd>F9</kbd> | Remove the candidate with the label "3" from the database of learned user input (If possible, if this candidate is not learned from user input, nothing happens). |
| <kbd>1</kbd>...<kbd>9</kbd>  | Same as <kbd>F1</kbd>...<kbd>F9</kbd> if the option "Use digits as select keys" is enabled. Enabling that option makes selecting candidates a bit easier because the number keys <kbd>1</kbd>...<kbd>9</kbd> are closer to the fingers than <kbd>F1</kbd>...<kbd>F9</kbd> on most keyboards. On the other hand, it makes completing when typing numbers impossible and it makes typing strings which are combinations of letters and numbers like "A4" more difficult. If digits are used as select keys, numbers can only be typed when no candidate list is shown. In most cases this means that numbers can only be typed when nothing else has been typed yet and the preëdit is empty. |
| <kbd>Ctrl</kbd>+<kbd>1</kbd>...<kbd>Ctrl</kbd>+<kbd>9</kbd> | Same as <kbd>Ctrl</kbd>+<kbd>F1</kbd>...<kbd>Ctrl</kbd>+<kbd>F9</kbd> if the option “Use digits as select keys” is enabled. |
| <kbd>Alt</kbd>+<kbd>F6</kbd> | Bound by default to the command "toggle_emoji_prediction". Toggle the emoji and Unicode symbol prediction on/off. This has the same result as using the setup tool to change this. |
| <kbd>Alt</kbd>+<kbd>F9</kbd> | Bound by default to the command "toggle_off_the_record". Toggle the "Off the record" mode. This has the same result as using the setup tool to change this. While "Off the record" mode is on, learning from user input is disabled. If learned user input is available, predictions are usually much better than predictions using only dictionaries. Therefore, one should use this option sparingly. Only if one wants to avoid saving secret user input to disk it might make sense to use this option temporarily. |
| <kbd>Alt</kbd>+<kbd>F10</kbd> | Bound by default to the command "setup". Opens the setup tool. |
| <kbd>Alt</kbd>+<kbd>F12</kbd> | Bound by default to the command "lookup_related". Shows related emoji and Unicode symbols or related words. |
| <kbd>Alt</kbd>+<kbd>Space</kbd> | Insert a literal space into the preëdit. |

When more than one input method at the same time is used, the following additional key bindings are available:
 
| Key Combination | Effect |
| --- | --- |
| <kbd>Ctrl</kbd>+<kbd>↓</kbd> | Bound by default to the command "next_input_method". Switches the input method used for the preëdit to the next input method. |
| <kbd>Ctrl</kbd>+<kbd>↑</kbd> | Bound by default to the command "previous_input_method". Switches the input method used for the preëdit to the previous method. |

## Mouse bindings
*These mouse bindings are currently hard-coded and cannot yet be customized.*

| Mouse Event | Effect |
| --- | --- |
| Button 1 click on a candidate | Commit the candidate clicked on followed by a space (Same as <kbd>F1</kbd>...<kbd>F9</kbd>). |
| <kbd>Ctrl</kbd> + Button 1 click on a candidate | Remove clicked candidate from database of learned user input (If possible, if this candidate is not learned from user input, nothing happens). |
| Button 3 clicks on a candidate | Show related emoji and Unicode symbols or related words (Same as <kbd>Alt</kbd>+<kbd>F12</kbd>). |
| <kbd>Ctrl</kbd> + Button 3 clicks anywhere in the candidate list | Toggle the emoji and Unicode symbol prediction on/off (Same as <kbd>Alt</kbd>+<kbd>F6</kbd>). This has the same result as using the setup tool to change this. |
| <kbd>Alt</kbd> + Button 3 clicks anywhere in the candidate list | Toggle the “Off the record” mode (Same as <kbd>Alt</kbd>+<kbd>F9</kbd>).<br>This has the same result as using the setup tool to change this.<br>While "Off the record" mode is on, learning from user input is disabled. If learned user input is available, predictions are usually much better than those which predictions use only dictionaries. Therefore, one should use this option sparingly. Only if one wants to avoid saving secret user input to disk it might make sense to use this option temporarily. |

