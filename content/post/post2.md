---
title: "All engines are merged into one for ibus-typing-booster >= 2.0.0"
date: 2018-05-28
author: "Mike FABIAN"
---

ibus-typing-booster has supported multiple languages in one engine since version >= 1.4.0, i.e. for quite a long time already. But to set this up it was necessary to use dconf on the command line, one could not do it with the graphical setup tool yet.

For ibus-typing-booster >= 2.0.0, the setup tool has been improved to make it easy to configure multiple dictionaries and input methods (transliteration methods).

Until now, there were different engines like “German - DE (Typing Booster)”, “Hindi - HI (Typing Booster)”, for more than 70 different languages. But all these different engines were using the same code anyway, they only differed by using different dictionaries and offering different input methods in the setup tool.

Now that the setup tool can configure arbitrary combinations of dictionaries and input methods, the differences between all these language specific engines have disappeared completely and having so many engines became superfluous. Therefore, all these different engines have been replaced by one single generic “Typing Booster” engine.

Unfortunately, this made it necessary for the many old engine names to be replaced by a single new engine name. This means if one had an input method like “German - DE (Typing Booster)” added in the Gnome control centre (or with ibus-setup on other desktops), this input method will not be available anymore after updating to ibus-typing-booster >= 2.0.0. The entry in the Gnome control centre will still be there but it will not work anymore. Instead an input method named “Other (Typing Booster)” will be available. To continue using ibus-typing-booster after the upgrade, one has to add this new input method “Other (Typing Booster)” in the Gnome control centre (or adding it using ibus-setup on other desktops). And remove the non-working entries with the old names.

When the new “Typing Booster” engine is used for the first time, default dictionaries and input methods will be setup automatically depending on the locale of the user. And one can add or remove dictionaries and input methods or change their order using the setup tool.

The learned user data is preserved during the update to ibus-typing-booster >= 2.0.0. The data learned from user input or from reading text files is saved into a single database

~/.local/share/ibus-typing-booster/user.db
for a long time already. The same database continues to be used with ibus-typing-booster >= 2.0.0.
I’ll update the documentation and screenshots during the next days.