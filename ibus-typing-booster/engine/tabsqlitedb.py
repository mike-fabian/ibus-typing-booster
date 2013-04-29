# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2011-2012 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License 
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import os
import os.path as path
from sys import stderr
import sqlite3
import tabdict
import uuid
import time
import re
import hunspell_suggest

patt_r = re.compile(r'c([ea])(\d):(.*)')
patt_p = re.compile(r'p(-{0,1}\d)(-{0,1}\d)')

# first make some number index we will used :)
#(MLEN, CLEN, M0, M1, M2, M3, M4, PHRASE, FREQ, USER_FREQ) = range (0,10)

        
class tabsqlitedb:
    '''Phrase database for hunspell-tables'''
    def __init__(self, name = 'table.db', user_db = None, filename = None ):
        # use filename when you are creating db from source
        # use name when you are using db
        # first we use the Parse in tabdict, which transform the char(a,b,c,...) to int(1,2,3,...) to fasten the sql enquiry
        self.parse = tabdict.parse
        self.deparse = tabdict.deparse
        self._add_phrase_sqlstr = ''
        self.old_phrases=[]
        
        self._conf_file_path = "/usr/share/ibus-typing-booster/hunspell-tables/"
        
        if filename:
            self.ime_property_cache = self.__parse_conf_file(self._conf_file_path+filename)
        else:
            self.ime_property_cache = self.__parse_conf_file()
        
        # share variables in this class:
        self._mlen = int ( self.get_ime_property ("max_key_length") )

        self._m17ndb = 'm17n'
        self._m17n_mim_name = ""
        self.lang_chars = self.get_ime_property('lang_chars')
        if self.lang_chars != None:
            self.lang_chars = self.lang_chars.decode('utf8')
        else:
            self.lang_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        self.lang_dict = {}
        self.lang_dict['0'] = 0
        for index,char in enumerate(self.lang_chars):
            if char:
                self.lang_dict[char] = index + 1

        self.encoding = self.get_ime_property('encoding')

        self.hunspell_obj = hunspell_suggest.Hunspell(
            lang=self.get_ime_property('languages'),
            dict_name=self.get_ime_property ("hunspell_dict"),
            aff_name=self.get_ime_property ("hunspell_dict").replace('.dic', '.aff'),
            langdict=self.lang_dict,
            encoding=self.encoding,
            lang_chars=self.lang_chars)

        # for fast add word
        self._set_add_phrase_sqlstr()
        #(ID, MLEN, CLEN, M0, M1, M2, M3, M4, CATEGORY, PHRASE, FREQ, USER_FREQ) = range (0,12)
        self._pt_index = ['id', 'mlen', 'clen']
        for i in range(self._mlen):
            self._pt_index.append ('m%d' %i)
        self._pt_index += ['phrase','freq','user_freq']
        self.user_can_define_phrase = self.get_ime_property('user_can_define_phrase')
        if self.user_can_define_phrase:
            if self.user_can_define_phrase.lower() == u'true' :
                self.user_can_define_phrase = True
            else:
                self.user_can_define_phrase = False
        else:
            print 'Could not find "user_can_define_phrase" entry from database, is it an outdated database?'
            self.user_can_define_phrase = False
        
        self.dynamic_adjust = self.get_ime_property('dynamic_adjust')
        if self.dynamic_adjust:
            if self.dynamic_adjust.lower() == u'true' :
                self.dynamic_adjust = True
            else:
                self.dynamic_adjust = False
        else:
            print 'Could not find "dynamic_adjust" entry from database, is it an outdated database?'
            self.dynamic_adjust = False
        
        self.startchars = self.get_start_chars ()
        user_db = self.get_ime_property("name")+'-user.db'
        # user database:
        if user_db != None:
            home_path = os.getenv ("HOME")
            tables_path = path.join (home_path, ".local/share/.ibus",  "hunspell-tables")
            user_db = path.join (tables_path, user_db)
            if not path.isdir (tables_path):
                os.makedirs (tables_path)
            try:
                desc = self.get_database_desc (user_db)
                if desc == None :
                    self.init_user_db (user_db)
                elif desc["version"] != "0.5":
                    new_name = "%s.%d" %(user_db, os.getpid())
                    print >> stderr, "Can not support the user db. We will rename it to %s" % new_name
                    self.old_phrases = self.extra_user_phrases( user_db )
                    os.rename (user_db, new_name)
                    self.init_user_db (user_db)
                elif self.get_table_phrase_len(user_db) != len(self._pt_index):
                    print >> stderr, "user db format outdated."
                    # store old user phrases
                    self.old_phrases = self.extra_user_phrases( user_db )
                    new_name = "%s.%d" %(user_db, os.getpid())
                    os.rename (user_db, new_name)
                    self.init_user_db (user_db)
            except:
                import traceback
                traceback.print_exc()
        else:
            user_db = ":memory:"

        # open user phrase database
        try:
            self.db = sqlite3.connect(user_db )
            self.db.execute( 'PRAGMA page_size = 8192; ' )
            self.db.execute( 'PRAGMA cache_size = 20000; ' )
            self.db.execute( 'PRAGMA temp_store = MEMORY; ' )
            self.db.execute( 'PRAGMA synchronous = OFF; ' )
            self.db.execute ('ATTACH DATABASE "%s" AS user_db;' % user_db)
        except:
            print >> stderr, "The user database was damaged. We will recreate it!"
            os.rename (user_db, "%s.%d" % (user_db, os.getpid ()))
            self.init_user_db (user_db)
            self.db.execute ('ATTACH DATABASE "%s" AS user_db;' % user_db)
        self.create_tables ("user_db")
        if self.old_phrases:
            # (mlen, phrase, freq, user_freq)
            # the phrases will be deparse again, and then be added     
            # the characters will be discard :(
            #chars = filter (lambda x: x[0] == 1, self.old_phrases)
            # print chars
            phrases = filter (lambda x: x[0] > 1, self.old_phrases)
            phrases = map(lambda x: [self.parse_phrase_to_tabkeys(x[1])]\
                    + list(x[1:]) , phrases)
 
            map (self.u_add_phrase,phrases)
            self.db.commit ()

        try:
            print "optimizing database ..."
            self.optimize_database()
        except:
            print "exception in optimize_database()"
            import traceback
            traceback.print_exc ()

        # try create all hunspell-tables in user database
        self.create_indexes ("user_db",commit=False)
        self.generate_userdb_desc ()
        
        # attach mudb for working process
        mudb = ":memory:"  
        self.db.execute ('ATTACH DATABASE "%s" AS mudb;' % mudb )
        self.create_tables ("mudb")

    def __parse_conf_file(self,conf_file="/usr/share/ibus-typing-booster/hunspell-tables/en_US.conf"):
        key_val_dict = {}
        if conf_file.find('typing-booster:') > 0 :
            conf_file=conf_file.replace('typing-booster:','')
        comment_patt = re.compile('^#')
        for line in file(conf_file):
            if not comment_patt.match(line):
                attr,val = line.strip().split ('=', 1)
                key_val_dict[attr.strip()]= val.strip()
        return key_val_dict 

    def update_phrase (self, entry, database='user_db'):
        '''update phrase freqs'''
        #print entry
        _con = [ entry[-1] ] + list(entry[1:3+entry[1]]) + [entry[-3]]
        #print _con
        _condition = u''.join( map(lambda x: 'AND m%d = ? ' % x, range(entry[1]) )    )
        #print _condition
        sqlstr = 'UPDATE %s.phrases SET user_freq = ? WHERE mlen = ? AND clen = ? %s AND phrase = ?;' % (database, _condition)
        #print sqlstr
        self.db.execute ( sqlstr , _con )
        # because we may update different db, we'd better commit every time.
        self.db.commit()

    def sync_usrdb (self):
        # we need to update the user_db
        #print 'sync userdb'
        mudata = self.db.execute ('SELECT * FROM mudb.phrases;').fetchall()
        #print mudata
        data_u = filter ( lambda x: x[-2] in [1,-3], mudata)
        data_a = filter ( lambda x: x[-2]==2, mudata)
        data_n = filter ( lambda x: x[-2]==-2, mudata)
        #print data_a
        tabdict.id_tab(self.lang_dict)
        data_a = map (lambda x: (u''.join ( map(tabdict.another_lang_deparser, x[3:3+x[1]])),x[-3],0,x[-1] ), data_a)
        data_n = map (lambda x: (u''.join ( map(tabdict.another_lang_deparser, x[3:3+x[1]])),x[-3],-1,x[-1] ), data_n)
        #print data_u
        map (self.update_phrase, data_u)
        #print self.db.execute('select * from user_db.phrases;').fetchall()
        map (self.u_add_phrase,data_a)
        map (self.u_add_phrase,data_n)
        self.db.commit ()
    
    def create_tables (self, database):
        '''Create hunspell-tables that contain all phrase'''

        try:
            self.db.execute( 'PRAGMA cache_size = 20000; ' )
            # increase the cache size to speedup sqlite enquiry
        except:
            pass
   
        # create phrase table (mabiao)
        sqlstr = 'CREATE TABLE IF NOT EXISTS %s.phrases (id INTEGER PRIMARY KEY AUTOINCREMENT,\
                mlen INTEGER, clen INTEGER, ' % database
        #for i in range(self._mlen):
        #    sqlstr += 'm%d INTEGER, ' % i 
        sqlstr += ''.join ( map (lambda x: 'm%d INTEGER, ' % x, range(self._mlen)) )
        sqlstr += 'phrase TEXT, freq INTEGER, user_freq INTEGER);'
        self.db.execute ( sqlstr )
        self.db.commit()
    
    def get_start_chars (self):
        '''return possible start chars of IME'''
        try:
            return self.get_ime_property('start_chars')
        except:
            return ''

    def get_no_check_chars (self):
        '''Get the characters which engine should not change freq'''
        _chars= self.get_ime_property('no_check_chars')
        try:
            _chars = _chars.decode('utf-8')
        except:
            pass
        return _chars

    def add_phrases (self, phrases, database = 'main'):
        '''Add phrases to database, phrases is a iterable object
        Like: [(tabkeys, phrase, freq ,user_freq), (tabkeys, phrase, freq, user_freq), ...]
        '''
        map (self.add_phrase, phrases, [database]*len(phrases),[False]*len(phrases) )
        self.db.commit()
    
    def add_new_phrases (self, nphrases, database='main'):
        '''Add new phrases into db, new phrases is a object
        of [(phrase,freq), (phrase,freq),...]'''
        n_phrases=[]
        for _ph, _freq in nphrases:
            try:
                _tabkey = self.parse_phrase_to_tabkeys(_ph)
                if not self.check_phrase_internal (_ph, _tabkey, database):
                    # we don't have this phrase
                    n_phrases.append ( (_tabkey, _ph, _freq, 0) )
            except:
                print '\"%s\" would not been added' % _ph
        if n_phrases:
            self.add_phrases ( n_phrases, database )
    
    def u_add_phrase (self,nphrase):
        '''Add a phrase to userdb'''
        self.add_phrase (nphrase,database='user_db',commit=False)

    def _set_add_phrase_sqlstr(self):
        '''Create the sqlstr for add phrase according to self._mlen.'''
        sqlstr = 'INSERT INTO %s.phrases ( mlen, clen, '
        sql_suffix = 'VALUES ( ?, ?, '
        mmlen = range(self._mlen)
        sqlstr += ''.join ( map(lambda x: 'm%d, ' %x , mmlen) )
        sql_suffix += ''.join ( map (lambda x: '?, ' , mmlen) )
        sqlstr += 'phrase, freq, user_freq) '
        sql_suffix += '?, ?, ? );'
        sqlstr += sql_suffix
        self._add_phrase_sqlstr = sqlstr

    def add_phrase (self, aphrase, database = 'main',commit=True):
        '''Add phrase to database, phrase is a object of
        (tabkeys, phrase, freq ,user_freq)
        '''
        sqlstr = self._add_phrase_sqlstr
        try:
            tabkeys,phrase,freq,user_freq = aphrase
        except:
            tabkeys,phrase,freq = aphrase
            user_freq = 0
        
        try:
            tbks = tabdict.other_lang_parser (tabkeys.decode('utf8'),self.lang_dict)

            if len(tbks) != len(tabkeys):
                print 'In %s %s: we parse tabkeys fail' % (phrase, tabkeys )
                return
            record = [None] * (5 + self._mlen)
            record [0] = len (tabkeys)
            record [1] = len (phrase)
            record [2: 2+len(tabkeys)] = map (lambda x: tbks[x].get_key_id(), range(0,len(tabkeys)))
            record[-3:] = phrase, freq, user_freq
            self.db.execute (sqlstr % database, record)
            if commit:
                self.db.commit()
        except Exception:
            import traceback
            traceback.print_exc()
    

    
    def optimize_database (self, database='main'):
        sqlstr = '''
            CREATE TABLE tmp AS SELECT * FROM %(database)s.phrases;
            DELETE FROM %(database)s.phrases;
            INSERT INTO %(database)s.phrases SELECT * FROM tmp ORDER BY
            %(tabkeystr)s mlen ASC, user_freq DESC, freq DESC, id ASC;
            DROP TABLE tmp;
            '''
        tabkeystr = ''
        for i in range(self._mlen):
            tabkeystr +='m%d, ' % i
        sqlstr = sqlstr % {'database':database,'tabkeystr':tabkeystr}
        self.db.executescript (sqlstr)
        self.db.executescript ("VACUUM;")
        self.db.commit()
    
    def drop_indexes(self, database):
        '''Drop the index in database to reduce it's size'''
        sqlstr = '''
            DROP INDEX IF EXISTS %(database)s.phrases_index_p;
            DROP INDEX IF EXISTS %(database)s.phrases_index_i;
            VACUUM; 
            ''' % { 'database':database }
        
        self.db.executescript (sqlstr)
        self.db.commit()
    
    def create_indexes(self, database, commit=True):
        tabkeystr = ''
        for i in range(self._mlen):
            tabkeystr +='m%d,' % i
        sqlstr = '''
            CREATE INDEX IF NOT EXISTS %(database)s.phrases_index_p ON phrases
            (%(tabkeystr)s mlen ASC, freq DESC, id ASC);
            CREATE INDEX IF NOT EXISTS %(database)s.phrases_index_i ON phrases (phrase, mlen ASC);
            ''' %{'database':database,'tabkeystr':tabkeystr}
        self.db.executescript (sqlstr)
        if commit:
            self.db.commit()
    
    def compare (self,x,y):
#        return cmp (x[1], y[1]) or -(cmp (x[-1], y[-1])) \
#                or -(cmp (x[-2], y[-2])) or (cmp (x[0], y[0]))
        return -(cmp (x[-1], y[-1])) or (cmp (x[1], y[1])) \
                or -(cmp (x[-2], y[-2])) or (cmp (x[0], y[0]))

    def select_words(self, tabkeys):
        '''
        Get phrases from database by tab_key objects
        ( which should be equal or less than the max key length)
        This method is called in hunspell_table.py by passing UserInput held data
        Return result[:] 
        '''
        # firstly, we make sure the len we used is equal or less than the max key length
        _len = min( len(tabkeys),self._mlen )
        # “map(str,tabkeys[:_len])” would convert the Unicode back to UTF-8.
        # This could be fixed by converting back to Unicode
        # in the end with “en_word = ''.join(en_word).decode('utf8')”
        # or by using eval(repr()) instead of str():
        en_word = map(eval,map(repr,tabkeys[:_len]))
        en_word = ''.join(en_word)
        sqlstr = '''SELECT * FROM user_db.phrases WHERE phrase LIKE "%(w1)s%%"
                    UNION ALL
                    SELECT  * FROM mudb.phrases WHERE phrase LIKE "%(w2)s%%"
                    ORDER BY user_freq DESC, freq DESC, id ASC, mlen ASC
                    limit 1000;''' %{'w1': en_word, 'w2': en_word}
        result = self.db.execute(sqlstr).fetchall()

        hunspell_list = self.hunspell_obj.suggest(en_word)
        for ele in hunspell_list:
            result.append(tuple(ele))
        # here in order to get high speed, I use complicated map
        # to substitute for
        usrdb={}
        mudb={}
        sysdb={}
        _cand = []

        searchres = map ( lambda res: [ int(res[-2]), int(res[-1]),
            [(res[1:-2],[res[:-1],res[-1:]])] ], result)
        
        reslist=filter( lambda x: not x[1], searchres )
        map (lambda x: sysdb.update(x[2]), reslist)

        # for usrdb
        reslist=filter( lambda x: ( x[0] in [0,-1] ) and x[1], searchres )
        map (lambda x: usrdb.update(x[2]), reslist)
        # for mudb
        reslist=filter( lambda x: ( x[0] not in [0,-1] ) and x[1], searchres )
        map (lambda x: mudb.update(x[2]), reslist)

        # first process mudb
        searchres = map ( lambda key: mudb[key][0] + mudb[key][1], mudb )
        #print searchres
        map (_cand.append, searchres)

        # now process usrdb
        searchres = map ( lambda key:  (not mudb.has_key(key))  and usrdb[key][0] + usrdb[key][1]\
                or None , usrdb )
        searchres = filter(lambda x: bool(x), searchres )
        #print searchres
        map (_cand.append, searchres)

        searchres = map ( lambda key: ((not mudb.has_key(key)) and (not usrdb.has_key(key)) )and sysdb[key][0] + sysdb[key][1]\
                or None, sysdb )
        searchres = filter (lambda x: bool(x), searchres)
        if searchres:
            map (_cand.append, searchres)

        #for key in usrdb:
        #    if not sysdb.has_key (key):
        #        _cand.append( usrdb[key][0] + usrdb[key][1] )
        #    else:
        #        _cand.append( sysdb[key][0] + usrdb[key][1] )
        #for key in sysdb:
        #    if not usrdb.has_key (key):
        #        _cand.append( sysdb[key][0] + sysdb[key][1] )
        _cand.sort(cmp=self.compare)
        return _cand[:]

    
    def get_all_values(self,d_name='main',t_name='inks'):
        sqlstr = 'SELECT * FROM '+d_name+'.'+t_name+';'
        _result = self.db.execute( sqlstr).fetchall()
        return _result

    def get_ime_property( self, attr ):
        '''get IME property from database, attr is the string of property,
        which should be str.lower() :)
        '''
        if not attr in self.ime_property_cache:
            return None
        else:
            return self.ime_property_cache[attr]

    def get_phrase_table_index (self):
        '''get a list of phrase table columns name'''
        return self._pt_index[:]

    def generate_userdb_desc (self):
        try:
            sqlstring = 'CREATE TABLE IF NOT EXISTS user_db.desc (name PRIMARY KEY, value);'
            self.db.executescript (sqlstring)
            sqlstring = 'INSERT OR IGNORE INTO user_db.desc  VALUES (?, ?);'
            self.db.execute (sqlstring, ('version', '0.5'))
            sqlstring = 'INSERT OR IGNORE INTO user_db.desc  VALUES (?, DATETIME("now", "localtime"));'
            self.db.execute (sqlstring, ("create-time", ))
            self.db.commit ()
        except:
            import traceback
            traceback.print_exc ()

    def init_user_db (self,db_file):
        if not path.exists (db_file):
            db = sqlite3.connect (db_file)
            db.execute('PRAGMA page_size = 4096;')
            db.execute( 'PRAGMA cache_size = 20000;' )
            db.execute( 'PRAGMA temp_store = MEMORY; ' )
            db.execute( 'PRAGMA synchronous = OFF; ' )
            db.commit()
    
    def get_database_desc (self, db_file):
        if not path.exists (db_file):
            return None
        try:
            db = sqlite3.connect (db_file)
            db.execute('PRAGMA page_size = 4096;')
            db.execute( 'PRAGMA cache_size = 20000;' )
            db.execute( 'PRAGMA temp_store = MEMORY; ' )
            db.execute( 'PRAGMA synchronous = OFF; ' )
            desc = {}
            for row in db.execute ("SELECT * FROM desc;").fetchall():
                desc [row[0]] = row[1]
            self.db.commit()
            return desc
        except:
            return None

    def get_table_phrase_len(self, db_file):
        table_patt = re.compile(r'.*\((.*)\)')
        if not path.exists (db_file):
            return 0
        try:
            db = sqlite3.connect (db_file)
            tp_res = db.execute("select sql from sqlite_master\
                    where name='phrases';").fetchall()
            self.db.commit()
            res = table_patt.match(tp_res[0][0])
            if res:
                tp = res.group(1).split(',')
                return len(tp)
            else:
                return 0
        except:
            return 0

    def parse_phrase_to_tabkeys (self,phrase):
        '''Get the Table encoding of the phrase in string form'''
        try:
            tabres = self.parse_phrase (phrase) [2:-1]
        except:
            tabres = None
        if tabres:
            tabkeys= u''.join ( map(self.deparse, tabres) )
        else:
            tabkeys= u''
        return tabkeys

    def check_phrase (self,phrase,tabkey=None,database='main'):
        # if IME didn't support user define phrase,
        # we divide user input phrase into characters,
        # and then check its frequence
        if type(phrase) != type(u''):
            phrase = phrase.decode('utf8')
        if self.user_can_define_phrase:
            self.check_phrase_internal (phrase, tabkey, database)
        else:
            map(self.check_phrase_internal, phrase)
    
    def check_phrase_internal (self,phrase,tabkey=None,database='main'):
        '''Check word freq and user_freq
        '''
        if type(phrase) != type(u''):
            phrase = phrase.decode('utf8')
            
        if len(phrase) < 4:
            return 

        tabks = tabdict.other_lang_parser (tabkey.decode('utf8'),self.lang_dict)

        tabkids = tuple( map(int,tabks) )
        condition = ' and '.join( map(lambda x: 'm%d = ?' % x, range( len(tabks) )) )
        sqlstr = '''SELECT * FROM user_db.phrases WHERE phrase = ? and %(cond)s
                UNION ALL SELECT * FROM mudb.phrases WHERE phrase = ? and %(cond)s
                ORDER BY user_freq DESC, freq DESC, id ASC;
                 ''' % {'cond':condition}
        result = self.db.execute(sqlstr, ((phrase,)+tabkids)*2 ).fetchall()
        hunspell_list = self.hunspell_obj.suggest(phrase[:-1])
        for ele in hunspell_list:
            if ele[-3] == phrase:
                result.append(tuple(ele))
        
        sysdb = {}
        usrdb = {}
        mudb = {}
        #print "result is: ", result 
        searchres = map ( lambda res: [ int(res[-2]), int(res[-1]),
            [(res[1:-2],[res[:-1],res[-1]])] ], result)
        # for sysdb
        reslist=filter( lambda x: not x[1], searchres )
        map (lambda x: sysdb.update(x[2]), reslist)
        #print "sysdb is ", sysdb
        # for usrdb
        reslist=filter( lambda x: ( x[0] in [0,-1] ) and x[1], searchres )
        map (lambda x: usrdb.update(x[2]), reslist)
        #print "usrdb is ", usrdb 
        # for mudb
        reslist=filter( lambda x: (x[0] not in [0,-1])  and x[1], searchres )
        map (lambda x: mudb.update(x[2]), reslist)
        #print "mudb is ", mudb
        
        sqlstr = 'UPDATE mudb.phrases SET user_freq = ? WHERE mlen = ? AND clen = ? %s AND phrase = ?;'
        try:        
            if len (result) == 0 and self.user_can_define_phrase:
                # this is a new phrase, we add it into user_db
                self.add_phrase ( (tabkey,phrase,-2,1), database = 'mudb')
            elif len (result) > 0:
                if not self.dynamic_adjust:
                    # we should change the frequency of words
                    return
                # we remove the keys contained in mudb from usrdb
                user_def= [elem for elem in result if elem[-3]== phrase]
                if not user_def:
                    self.add_phrase ( (tabkey,phrase,-2,1), database = 'mudb')
                keyout = filter (lambda k: mudb.has_key(k), usrdb.keys() )
                map (usrdb.pop, keyout)
                # we remove the keys contained in mudb and usrdb from sysdb
                keyout = filter (lambda k: mudb.has_key(k) or usrdb.has_key(k) , sysdb.keys() )
                map (sysdb.pop, keyout)
                map (lambda res: self.db.execute ( sqlstr % ''.join( map(lambda x: 'AND m%d = ? ' % x, range(res[0])) ) ,  [ mudb[res][1] + 1 ] + list( res[:2+res[0]]) + list (res[2+self._mlen:]) ) , mudb.keys())
                self.db.commit()
                tabdict.id_tab(self.lang_dict)
                map ( lambda res: self.add_phrase ( (''.join ( map(tabdict.another_lang_deparser,res[2:2+int(res[0])] ) ),phrase,(-3 if usrdb[res][0][-1] == -1 else 1),usrdb[res][1]+1  ), database = 'mudb') , usrdb.keys() )
                map ( lambda res: self.add_phrase ( ( ''.join ( map(tabdict.another_lang_deparser,res[2:2+int(res[0])]) ),phrase,2,1 ), database = 'mudb'), sysdb.keys() )
            else:
                # we come here when the ime doesn't support user phrase define
                pass
        except:
            import traceback
            traceback.print_exc ()

    def remove_phrase (self,phrase,database='user_db'):
        '''Remove phrase from database, default is from user_db
        phrase should be the a row of select * result from database
        Like (id, mlen,clen,m0,m1,m2,m3,phrase,freq,user_freq)
        '''
        _ph = list(phrase[:-2])
        _condition = ''    
        for i in range(_ph[1]):
            _condition += 'AND m%d = ? ' % i
        nn =_ph.count(None)
        if nn:
            for i in range(nn):
                _ph.remove(None)
        msqlstr= 'SELECT * FROM %(database)s.phrases WHERE mlen = ? and clen = ? %(condition)s AND phrase = ? ;' % { 'database':database, 'condition':_condition }

        if self.db.execute(msqlstr, _ph[1:]).fetchall():
            sqlstr = 'DELETE FROM %(database)s.phrases WHERE mlen = ? AND clen =? %(condition)s AND phrase = ?  ;' % { 'database':database, 'condition':_condition }
            self.db.execute(sqlstr,_ph[1:])
            self.db.commit()
        
        msqlstr= 'SELECT * FROM mudb.phrases WHERE mlen = ? and clen = ? %(condition)s AND phrase = ? ;' % { 'condition':_condition }

        if self.db.execute(msqlstr, _ph[1:]).fetchall():
            sqlstr = 'DELETE FROM mudb.phrases WHERE mlen = ? AND clen =? %(condition)s AND phrase = ?  ;' % {  'condition':_condition }
            self.db.execute(sqlstr,_ph[1:])
            self.db.commit()

    def extra_user_phrases(self, udb, only_defined=False):
        '''extract user phrases from database'''
        try:
            db = sqlite3.connect(udb)
        except:
            return None
        if only_defined:
            _phrases = db.execute(\
                    "SELECT clen, phrase, freq, sum(user_freq)\
                    FROM phrases \
                    WHERE freq=-1 AND mlen != 0 \
                    GROUP BY clen,phrase;").fetchall()
        else:
            _phrases = db.execute(\
                    "SELECT clen, phrase, freq, sum(user_freq)\
                    FROM phrases\
                    WHERE mlen !=0 \
                    GROUP BY clen,phrase;").fetchall()
        db.commit()
        return _phrases[:]
