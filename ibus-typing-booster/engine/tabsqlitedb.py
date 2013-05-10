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
import sys
import sqlite3
import uuid
import time
import re
import hunspell_suggest

user_database_version = '0.61'

patt_r = re.compile(r'c([ea])(\d):(.*)')
patt_p = re.compile(r'p(-{0,1}\d)(-{0,1}\d)')

class ImeProperties:
    def __init__(self, configfile_path=None):
        '''
        configfile_path is the full path to the config file, for example
        “/usr/share/ibus-typing-booster/hunspell-tables/en_US.conf”
        '''
        self.ime_property_cache = {}
        if configfile_path.find('typing-booster:') > 0:
            configfile_path=configfile_path.replace(
                'typing-booster:','')
        if os.path.exists(configfile_path) and os.path.isfile(configfile_path):
            comment_patt = re.compile('^#')
            for line in file(configfile_path):
                if not comment_patt.match(line):
                    attr,val = line.strip().split ('=', 1)
                    self.ime_property_cache[attr.strip()]= val.strip()
        else:
            sys.stderr.write("Error: ImeProperties: No such file: %s" %configfile_path)

    def get(self, key):
        if key in self.ime_property_cache:
            return self.ime_property_cache[key]
        else:
            return None

class tabsqlitedb:
    '''Phrase database for hunspell-tables'''
    def __init__(self, name = 'table.db', user_db = None, filename = None ):
        # use filename when you are creating db from source
        # use name when you are using db
        self.old_phrases=[]
        
        self._conf_file_path = "/usr/share/ibus-typing-booster/hunspell-tables/"

        self.ime_properties = ImeProperties(self._conf_file_path+filename)

        # share variables in this class:
        self._mlen = int(self.ime_properties.get("max_key_length"))

        self._m17ndb = 'm17n'
        self._m17n_mim_name = ""
        self.lang_chars = self.ime_properties.get('lang_chars')
        if self.lang_chars != None:
            self.lang_chars = self.lang_chars.decode('utf8')
        else:
            self.lang_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

        self.encoding = self.ime_properties.get('encoding')

        self.hunspell_obj = hunspell_suggest.Hunspell(
            lang=self.ime_properties.get('languages'),
            dict_name=self.ime_properties.get("hunspell_dict"),
            aff_name=self.ime_properties.get("hunspell_dict").replace('.dic', '.aff'),
            encoding=self.encoding,
            lang_chars=self.lang_chars)

        self._phrase_table_column_names = ['id', 'mlen', 'clen', 'input_phrase', 'phrase','freq','user_freq']
        self.user_can_define_phrase = self.ime_properties.get('user_can_define_phrase')
        if self.user_can_define_phrase:
            if self.user_can_define_phrase.lower() == u'true' :
                self.user_can_define_phrase = True
            else:
                self.user_can_define_phrase = False
        else:
            print 'Could not find "user_can_define_phrase" entry from database, is it an outdated database?'
            self.user_can_define_phrase = False
        
        self.dynamic_adjust = self.ime_properties.get('dynamic_adjust')
        if self.dynamic_adjust:
            if self.dynamic_adjust.lower() == u'true' :
                self.dynamic_adjust = True
            else:
                self.dynamic_adjust = False
        else:
            print 'Could not find "dynamic_adjust" entry from database, is it an outdated database?'
            self.dynamic_adjust = False
        
        self.startchars = self.get_start_chars ()
        user_db = self.ime_properties.get("name")+'-user.db'
        # user database:
        if user_db != None:
            home_path = os.getenv ("HOME")
            tables_path = path.join (home_path, ".local/share/.ibus",  "hunspell-tables")
            user_db = path.join (tables_path, user_db)
            if not path.isdir (tables_path):
                os.makedirs (tables_path)
            try:
                desc = self.get_database_desc (user_db)
                if desc == None \
                    or desc["version"] != user_database_version \
                    or self.get_number_of_columns_of_phrase_table(user_db) != len(self._phrase_table_column_names):
                    sys.stderr.write("The user database %(udb)s seems to be incompatible.\n" %{'udb': user_db})
                    if desc == None:
                        sys.stderr.write("There is no version information in the database.\n")
                    elif desc["version"] != user_database_version:
                        sys.stderr.write("The version of the database does not match (too old or too new?).\n")
                        sys.stderr.write("ibus-typing-booster wants version=%s\n" %user_database_version)
                        sys.stderr.write("But the  database actually has version=%s\n" %desc["version"])
                    elif self.get_number_of_columns_of_phrase_table(user_db) != len(self._phrase_table_column_names):
                        sys.stderr.write("The number of columns of the database does not match.\n")
                        sys.stderr.write("ibus-typing-booster expects %(col)s columns.\n" 
                            %{'col': len(self._phrase_table_column_names)})
                        sys.stderr.write("But the database actually has %(col)s columns.\n"
                            %{'col': self.get_number_of_columns_of_phrase_table(user_db)})
                    sys.stderr.write("Trying to recover the phrases from the old, incompatible database.\n")
                    self.old_phrases = self.extract_user_phrases( user_db )
                    new_name = "%s.%d" %(user_db, os.getpid())
                    sys.stderr.write("Renaming the incompatible database to \"%(name)s\".\n" %{'name': new_name})
                    os.rename (user_db, new_name)
                    sys.stderr.write("Creating a new, empty database \"%(name)s\".\n"  %{'name': user_db})
                    self.init_user_db (user_db)
                    sys.stderr.write("If user phrases were successfully recovered from the old,\n")
                    sys.stderr.write("incompatible database, they will be used to initialize the new database.\n")
                else:
                    sys.stderr.write("Compatible database %(db)s found.\n" %{'db': user_db})
            except:
                import traceback
                traceback.print_exc()
        else:
            user_db = ":memory:"

        # open user phrase database
        try:
            self.db = sqlite3.connect(user_db)
            self.db.execute('PRAGMA page_size = 8192; ')
            self.db.execute('PRAGMA cache_size = 20000; ')
            self.db.execute('PRAGMA temp_store = MEMORY; ')
            self.db.execute('PRAGMA synchronous = OFF; ')
            self.db.execute('ATTACH DATABASE "%s" AS user_db;' % user_db)
        except:
            sys.stderr.write("Could not open the database %(name)s.\n" %{'name': user_db})
            new_name = "%s.%d" %(user_db, os.getpid())
            sys.stderr.write("Renaming the incompatible database to \"%(name)s\".\n" %{'name': new_name})
            os.rename(user_db, new_name)
            sys.stderr.write("Creating a new, empty database \"%(name)s\".\n"  %{'name': user_db})
            self.init_user_db(user_db)
            self.db.execute('ATTACH DATABASE "%s" AS user_db;' % user_db)
        self.create_tables("user_db")
        if self.old_phrases:
            # (mlen, phrase, freq, user_freq)
            phrases = filter(lambda x: x[0] > 1, self.old_phrases)
            phrases = map(lambda x: [x[1]] + list(x[1:]), phrases)
            map(self.u_add_phrase, phrases)
            self.db.commit()

        # do not call this always on intialization for the moment.
        # It makes the already slow “python engine/main.py --xml”
        # to list the engines even slower and may break the listing
        # of the engines completely if there is a problem with
        # optimizing the databases. Probably bring this back as an
        # option later if the code in self.optimize_database() is
        # improved to do anything useful.
        #try:
        #    self.optimize_database()
        #except:
        #    print "exception in optimize_database()"
        #    import traceback
        #    traceback.print_exc ()

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
        input_phrase, phrase, freq, user_freq = entry
        sqlstr = '''UPDATE %(database)s.phrases
                    SET user_freq = %(user_freq)s
                    WHERE mlen = %(mlen)s
                    AND clen = %(clen)s
                    AND input_phrase = "%(input_phrase)s"
                    AND phrase = "%(phrase)s";
        ''' %{'database':database,
              'user_freq': user_freq,
              'mlen': len(input_phrase),
              'clen': len(phrase),
              'input_phrase': input_phrase,
              'phrase': phrase}
        self.db.execute(sqlstr)
        self.db.commit()

    def sync_usrdb (self):
        # we need to update the user_db
        #print 'sync userdb'
        mudata = self.db.execute ('SELECT * FROM mudb.phrases;').fetchall()
        data_u = filter ( lambda x: x[-2] in [1,-3], mudata)
        data_a = filter ( lambda x: x[-2]==2, mudata)
        data_n = filter ( lambda x: x[-2]==-2, mudata)
        data_u = map (lambda x: (x[3],x[-3],x[-2],x[-1] ), data_u)
        data_a = map (lambda x: (x[3],x[-3],0,x[-1] ), data_a)
        data_n = map (lambda x: (x[3],x[-3],-1,x[-1] ), data_n)
        map (self.update_phrase, data_u)
        #print self.db.execute('select * from user_db.phrases;').fetchall()
        map (self.u_add_phrase,data_a)
        map (self.u_add_phrase,data_n)
        self.db.commit ()
    
    def create_tables (self, database):
        '''Create table for the phrases.'''
        try:
            self.db.execute( 'PRAGMA cache_size = 20000; ' )
            # increase the cache size to speedup sqlite enquiry
        except:
            pass
        sqlstr = '''CREATE TABLE IF NOT EXISTS %s.phrases
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mlen INTEGER, clen INTEGER,
                    input_phrase TEXT, phrase TEXT,
                    freq INTEGER, user_freq INTEGER);''' % database
        self.db.execute(sqlstr)
        self.db.commit()
    
    def get_start_chars (self):
        '''return possible start chars of IME'''
        try:
            return self.ime_properties.get('start_chars')
        except:
            return ''

    def u_add_phrase (self,nphrase):
        '''Add a phrase to userdb'''
        self.add_phrase (nphrase,database='user_db',commit=False)

    def add_phrase (self, aphrase, database = 'main',commit=True):
        '''
        Add phrase to database, phrase is a object of
        (input_phrase, phrase, freq ,user_freq)
        '''
        sqlstr = '''INSERT INTO %(database)s.phrases
                    (mlen, clen, input_phrase, phrase, freq, user_freq)
                    VALUES ( ?, ?, ?, ?, ?, ? );''' %{'database': database}
        try:
            input_phrase,phrase,freq,user_freq = aphrase
        except:
            input_phrase,phrase,freq = aphrase
            user_freq = 0
        
        try:
            record = [len(input_phrase), len(phrase),
                      input_phrase, phrase,
                      freq, user_freq]
            self.db.execute (sqlstr, record)
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
            input_phrase, mlen ASC, user_freq DESC, freq DESC, id ASC;
            DROP TABLE tmp;''' %{'database':database,}
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
        sqlstr = '''
            CREATE INDEX IF NOT EXISTS %(database)s.phrases_index_p ON phrases
            (input_phrase, mlen ASC, freq DESC, id ASC);
            CREATE INDEX IF NOT EXISTS %(database)s.phrases_index_i ON phrases
            (phrase, mlen ASC);''' %{'database':database}
        self.db.executescript (sqlstr)
        if commit:
            self.db.commit()
    
    def compare (self,x,y):
#        return cmp (x[1], y[1]) or -(cmp (x[-1], y[-1])) \
#                or -(cmp (x[-2], y[-2])) or (cmp (x[0], y[0]))
        return -(cmp (x[-1], y[-1])) or (cmp (x[1], y[1])) \
                or -(cmp (x[-2], y[-2])) or (cmp (x[0], y[0]))

    def select_words(self, input_phrase):
        '''
        Get phrases from database by tab_key objects
        ( which should be equal or less than the max key length)
        This method is called in hunspell_table.py by passing UserInput held data
        Returns a list of matches where each match is a tuple
        in the form of a database row, i.e. returns something like
        [(id, mlen, clen, input_phrase, phrase, freq, user_freq), ...]
        '''
        if type(input_phrase) != type(u''):
            input_phrase = input_phrase.decode('utf8')
        # limit length of input phrase to max key length
        # (Now that the  input_phrase is stored in a single
        # column of type TEXT in sqlite3, this limit can be set as high
        # as the maximum string length in sqlite3
        # (by default 10^9, see http://www.sqlite.org/limits.html))
        input_phrase = input_phrase[:self._mlen]
        sqlstr = '''SELECT * FROM user_db.phrases WHERE phrase LIKE "%(input_phrase)s%%"
                    UNION ALL
                    SELECT  * FROM mudb.phrases WHERE phrase LIKE "%(input_phrase)s%%"
                    ORDER BY user_freq DESC, freq DESC, id ASC, mlen ASC
                    limit 1000;''' %{'input_phrase': input_phrase}
        result = self.db.execute(sqlstr).fetchall()
        hunspell_list = self.hunspell_obj.suggest(input_phrase)
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

    def get_phrase_table_column_names (self):
        '''get a list of phrase table columns name'''
        return self._phrase_table_column_names[:]

    def generate_userdb_desc (self):
        try:
            sqlstring = 'CREATE TABLE IF NOT EXISTS user_db.desc (name PRIMARY KEY, value);'
            self.db.executescript (sqlstring)
            sqlstring = 'INSERT OR IGNORE INTO user_db.desc  VALUES (?, ?);'
            self.db.execute (sqlstring, ('version', user_database_version))
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
    
    def get_database_desc(self, db_file):
        if not path.exists(db_file):
            return None
        try:
            db = sqlite3.connect(db_file)
            desc = {}
            for row in db.execute("SELECT * FROM desc;").fetchall():
                desc[row[0]] = row[1]
            return desc
        except:
            return None

    def get_number_of_columns_of_phrase_table(self, db_file):
        '''
        Get the number of columns in the 'phrases' table in
        the database in db_file.

        Determines the number of columns by parsing this:

        sqlite> select sql from sqlite_master where name='phrases';
CREATE TABLE phrases (id INTEGER PRIMARY KEY AUTOINCREMENT,                mlen INTEGER, clen INTEGER, input_phrase TEXT, phrase TEXT, freq INTEGER, user_freq INTEGER)
        sqlite>

        This result could be on a single line, as above, or on multiple
        lines.
        '''
        if not path.exists (db_file):
            return 0
        try:
            db = sqlite3.connect (db_file)
            tp_res = db.execute(
                "select sql from sqlite_master where name='phrases';"
            ).fetchall()
            # Remove possible line breaks from the string where we
            # want to match:
            str = ' '.join(tp_res[0][0].splitlines())
            res = re.match(r'.*\((.*)\)', str)
            if res:
                tp = res.group(1).split(',')
                return len(tp)
            else:
                return 0
        except:
            return 0

    def check_phrase(self, phrase, input_phrase=None, database='main'):
        # if IME didn't support user define phrase,
        # we divide user input phrase into characters,
        # and then check its frequence
        if type(phrase) != type(u''):
            phrase = phrase.decode('utf8')
        if type(input_phrase) != type(u''):
            input_phrase = input_phrase.decode('utf8')
        if self.user_can_define_phrase:
            self.check_phrase_internal (phrase, input_phrase, database)
        else:
            map(self.check_phrase_internal, phrase)
    
    def check_phrase_internal (self,phrase,input_phrase=None,database='main'):
        '''Check word freq and user_freq
        '''
        if type(phrase) != type(u''):
            phrase = phrase.decode('utf8')
        if type(input_phrase) != type(u''):
            input_phrase = input_phrase.decode('utf8')
            
        if len(phrase) < 4:
            return 

        sqlstr = '''
                SELECT * FROM user_db.phrases WHERE phrase = "%(phrase)s" and input_phrase = "%(input_phrase)s"
                UNION ALL
                SELECT * FROM mudb.phrases WHERE phrase = "%(phrase)s" and input_phrase = "%(input_phrase)s"
                ORDER BY user_freq DESC, freq DESC, id ASC;''' %{'phrase': phrase, 'input_phrase': input_phrase}
        result = self.db.execute(sqlstr).fetchall()
        hunspell_list = self.hunspell_obj.suggest(phrase) #phrase[:-1])
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
        
        try:        
            if len (result) == 0 and self.user_can_define_phrase:
                # this is a new phrase, we add it into user_db
                self.add_phrase ( (input_phrase,phrase,-2,1), database = 'mudb')
            elif len (result) > 0:
                if not self.dynamic_adjust:
                    # we should change the frequency of words
                    return
                # we remove the keys contained in mudb from usrdb
                user_def= [elem for elem in result if elem[-3]== phrase]
                if not user_def:
                    self.add_phrase ( (input_phrase,phrase,-2,1), database = 'mudb')
                keyout = filter (lambda k: mudb.has_key(k), usrdb.keys() )
                map (usrdb.pop, keyout)
                # we remove the keys contained in mudb and usrdb from sysdb
                keyout = filter (lambda k: mudb.has_key(k) or usrdb.has_key(k) , sysdb.keys() )
                map (sysdb.pop, keyout)
                sqlstr = '''UPDATE mudb.phrases SET user_freq = ? WHERE mlen = ? AND clen = ? AND input_phrase = ? AND phrase = ?;'''
                map (lambda res: self.db.execute (sqlstr, [mudb[res][1] + 1] + list(res[:2+res[0]]) + list(res[2+self._mlen:])), mudb.keys())
                self.db.commit()
                map(lambda res: self.add_phrase((res[2],phrase,2,1), database = 'mudb'), sysdb.keys())
                map(lambda res: self.add_phrase((res[2],phrase,(-3 if usrdb[res][0][-1] == -1 else 1),usrdb[res][1]+1), database = 'mudb'), usrdb.keys())
                map(lambda res: self.add_phrase((res[2],phrase,2,1), database = 'mudb'), sysdb.keys())
            else:
                # we come here when the ime doesn't support user phrase define
                pass
        except:
            import traceback
            traceback.print_exc ()

    def remove_phrase (self,phrase,database='user_db'):
        '''
        Remove phrase from database.
        phrase should be a tuple like a row in the database, i.e.
        like the result lines of a "select * from phrases;"
        Like (id, mlen,clen,input_phrase,phrase,freq,user_freq)
        '''
        id, mlen, clen, input_phrase, phrase, freq, user_freq = phrase
        select_sqlstr= '''
        SELECT * FROM %(database)s.phrases
        WHERE mlen = %(mlen)s
        AND clen = %(clen)s
        AND input_phrase = "%(input_phrase)s"
        AND phrase = "%(phrase)s";
        ''' %{'database': database,
              'mlen': mlen,
              'clen': clen,
              'input_phrase': input_phrase,
              'phrase': phrase}

        if self.db.execute(select_sqlstr).fetchall():
            delete_sqlstr = '''
            DELETE FROM %(database)s.phrases
            WHERE mlen = %(mlen)s
            AND clen =%(clen)s
            AND input_phrase = "%(input_phrase)s"
            AND phrase = "%(phrase)s";
            ''' %{'database': database,
                  'mlen': mlen,
                  'clen': clen,
                  'input_phrase': input_phrase,
                  'phrase': phrase}
            self.db.execute(delete_sqlstr)
            self.db.commit()

    def extract_user_phrases(self, udb, only_defined=False):
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
