# vim:set ts=4
# Copyright (c) 2010-2011 Anish Patil <apatil@redhat.com>
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.



tables_DATA = en_US.conf \
	en_HK.conf \
	en_JM.conf \
	en_AG.conf \
	en_AU.conf \
	en_BS.conf \
	en_BW.conf \
	en_BZ.conf \
	en_DK.conf \
	en_GH.conf \
	en_IE.conf \
	en_IN.conf \
	en_NA.conf \
	en_NG.conf \
	en_NZ.conf \
	en_PH.conf \
	en_SG.conf \
	en_TT.conf \
	en_ZA.conf \
	en_ZW.conf \
	fr_CA.conf \
	fr_BE.conf \
	fr_CH.conf \
	fr_FR.conf \
	fr_LU.conf \
	fr_MC.conf \
	da_DK.conf \
	hi_IN.conf \
	gu_IN.conf \
	ml_IN.conf \
	bn_IN.conf \
	kn_IN.conf \
	pa_IN.conf \
	as_IN.conf \
	ta_IN.conf \
	mr_IN.conf \
	te_IN.conf \
	ur_PK.conf \
	fa_IR.conf \
	or_IN.conf \
	mai_IN.conf \
	ne_IN.conf \
	ne_NP.conf \
	en_GB.conf \
	el_GR.conf \
	ro_RO.conf \
	ar_TN.conf \
	de_AT.conf \
	de_CH.conf \
	de_DE.conf \
	he_IL.conf \
	yi_US.conf \
	hy_AM.conf \
	ko_KR.conf \
	km_KH.conf \
	th_TH.conf \
	ku_TR.conf \
	si_LK.conf \
	be_BY.conf \
	uk_UA.conf \
	bg_BG.conf \
	cs_CZ.conf \
	es_ES.conf \
	hu_HU.conf \
	is_IS.conf \
	it_IT.conf \
	nb_NO.conf \
	nl_NL.conf \
	nn_NO.conf \
	pl_PL.conf \
	pt_BR.conf \
	pt_PT.conf \
	sv_SE.conf \
	ru_RU.conf

tables_DATA += $(NULL)

tablesdir = $(datadir)/ibus-typing-booster/hunspell-tables

EXTRA_DIST = $(tables_DATA) \
	$(NULL)

DISTCLEANFILES = \
	*.conf \
	$(NULL)


install-data-local:
	$(MKDIR_P) $(DESTDIR)$(pkgdatadir)/hunspell-tables
