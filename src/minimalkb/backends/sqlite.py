import logging; logger = logging.getLogger("minimalKB."+__name__);
DEBUG_LEVEL=logging.DEBUG

import datetime
import sqlite3

from sqlite_queries import query, simplequery, matchingstmt

TRIPLETABLENAME = "triples"
TRIPLETABLE = '''CREATE TABLE IF NOT EXISTS %s
                    ("hash" INTEGER PRIMARY KEY NOT NULL  UNIQUE , 
                    "subject" TEXT NOT NULL , 
                    "predicate" TEXT NOT NULL , 
                    "object" TEXT NOT NULL , 
                    "model" TEXT NOT NULL ,
                    "timestamp" DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL ,
                    "expires" DATETIME ,
                    "inferred" BOOLEAN DEFAULT 0 NOT NULL)'''

def sqlhash(s,p,o,model):
    return hash("%s%s%s%s"%(s,p,o, model))

class SQLStore:

    def __init__(self):
        self.conn = sqlite3.connect('kb.db')
        self.create_kb()

    def create_kb(self):
    
        with self.conn:
            self.conn.execute(TRIPLETABLE % TRIPLETABLENAME)

    def clear(self):
        with self.conn:
            self.conn.execute("DROP TABLE %s" % TRIPLETABLENAME)

        self.create_kb()

    def add(self, stmts, model = "default"):

        timestamp = datetime.datetime.now().isoformat()

        stmts = [[sqlhash(s,p,o, model), s, p, o, model, timestamp] for s,p,o in stmts]


        with self.conn:
            self.conn.executemany('''INSERT OR IGNORE INTO %s
                     (hash, subject, predicate, object, model, timestamp)
                     VALUES (?, ?, ?, ?, ?, ?)''' % TRIPLETABLENAME, stmts)

    def delete(self, stmts, model = "default"):

        hashes = [[sqlhash(s,p,o, model)] for s,p,o in stmts]

        with self.conn:
            # removal is non-monotonic. Remove all inferred statements
            self.conn.execute("DELETE FROM %s WHERE inferred=1" % TRIPLETABLENAME)

            self.conn.executemany('''DELETE FROM %s 
                        WHERE (hash=?)''' % TRIPLETABLENAME, hashes)

    def update(self, stmts, model = "default"):

        logger.warn("With SQLite store, update is strictly equivalent to " + \
                    "add (ie, no functional property check")

        self.add(stmts, model)

    def about(self, resource, models):

        params = {'res':resource}
        # workaround to feed a variable number of models
        models = list(models)
        for i in range(len(models)):
            params["m%s"%i] = models[i]

        query = '''
                SELECT subject, predicate, object 
                FROM %s
                WHERE (subject=:res OR predicate=:res OR object=:res)
                AND model IN (%s)''' % (TRIPLETABLENAME, ",".join([":m%s" % i for i in range(len(models))]))
        with self.conn:
            res = self.conn.execute(query, params)
            return [[row[0], row[1], row[2]] for row in res]

    def has(self, stmts, models):

        candidates = set()
        for s in stmts:
            if not candidates:
                candidates = set(matchingstmt(self.conn, s, models))
            else:
                candidates &= set(matchingstmt(self.conn, s, models))

        return len(candidates) > 0


    def query(self, vars, patterns, models):
        return query(self.conn, vars, patterns, models)

    def classesof(self, concept, direct, models):
        if direct:
            logger.warn("Direct classes are assumed to be the asserted is-a relations")
            return list(simplequery(self.conn, (concept, "rdf:type", "?class"), models, assertedonly = True))
        return list(simplequery(self.conn, (concept, "rdf:type", "?class"), models))
    
    ###################################################################################

    def has_stmt(self, pattern, models):
        """ Returns True if the given statment exist in
        *any* of the provided models.
        """

        s,p,o = pattern
        query = "SELECT hash FROM %s WHERE hash=?" % TRIPLETABLENAME
        for m in models:
            if self.conn.execute(query, (sqlhash(s, p ,o , m),)).fetchone():
                return True

        return False

def get_vars(s):
    return [x for x in s if x.startswith('?')]

def nb_variables(s):
    return len(get_vars(s))

