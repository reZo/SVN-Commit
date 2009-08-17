#!/usr/bin/python

from optparse import OptionParser
from hashlib import md5
import sys, glob, os, re, MySQLdb, pysvn

class svnc:
   
   """
   set default arguments for CLI variables
   """
   
   def __init__ (self):
      self.options = False
      self.list = []
      self.parseCLI()
      self.db = {}
      
      db = MySQLdb.connect(host   = 'localhost',
                           user   = 'svnc',
                           passwd = 'svnc',
                           db     = 'svnc')
      
      self.cursor = db.cursor()
   
   """
   parse CLI arguments
   """
   
   def parseCLI (self):
      parser = OptionParser()
      parser.add_option_version = 'beta'
      parser.add_option('-d', '--daemon', dest='daemon', default=False, metavar='(yes|no)', help='run as daemon')
      parser.add_option('-c', '--checkout', dest='checkout', metavar='/path/to/checkout/', help='path to repository checkout')
      parser.add_option('-e', '--extensions', dest='extensions', metavar='ext,ext,...', help='extensions to check')
      parser.add_option('-u', '--username', dest='username', metavar='username', help='username for svn repository login')
      parser.add_option('-p', '--password', dest='password', metavar='password', help='password for svn repository login')
      parser.add_option('-q', '--quiet', dest='quiet', metavar='quiet', help='display nothing to stdout')
      (self.options, args) = parser.parse_args()
      try:
         self.options.extensions = self.options.extensions.split(',')
      except AttributeError:
         parser.print_help()
         sys.exit(1)
   
   """
   get value parsed from CLI
   """
   
   def get (self, key):
      return eval("self.options.%s" % key)
   
   def scan (self, path):
      files = []
      for i in os.listdir(path):
         name = os.path.join(path, i)
         if os.path.isfile('%s' % name):
            # check for extensions
            for extension in self.options.extensions:
               if  name[-2:] == extension:
                  files.append(name)
         elif os.path.isdir('%s' % name):
            for j in self.scan(name):
               files.append(j)
      return files
   
   """
   extract @commit comment from filename
   """
   
   def extract (self, filename):
      contents = open(filename).read()
      # regex @commit till and excluding \n (r == raw)
      match = re.search(r"@commit(.*)", contents)
      if match:
         return { 'comment' : match.group(1).strip(), 'filename' : filename, 'hash' : md5(contents).hexdigest() }
   
   """
   checks for legit changes within self.list
   removes any non-legit files
   """
   
   def check (self, current):
      
      self.cursor.execute('SELECT hash, comment FROM svnc WHERE filename = "%s"' % current['filename'])
      client = pysvn.Client()
      row = self.cursor.fetchone()
      
      # add file to database
      if self.cursor.rowcount == 0 or row == None:
         print current['filename'], "not currently in database, adding."
         self.cursor.execute('INSERT INTO svnc (filename, hash, comment) VALUES ("%s", "%s", "%s")' % (current['filename'], current['hash'], current['comment']))
         try:
            client.add(current['filename'])
         except pysvn._pysvn_2_5.ClientError:
            print current['filename'], "does not belong to a SVN repository, adding"
            try:
               client.checkin(current['filename'], current['comment'])
            except pysvn._pysvn_2_5.ClientError:
               print current['filename'], "added."
         return
      
      # return if there has been no comment changes
      if row[1] == current['comment']:
         return
      
      # replace new comment with old
      # check md5 checksum
      replacedChecksum = md5(re.sub('@commit %s' % current['comment'], '@commit %s' % row[1], open(current['filename'], 'r').read())).hexdigest()
      currentChecksum = md5(open(current['filename'], 'r').read()).hexdigest()
      
      if replacedChecksum != currentChecksum:
         print current['filename'], "has changed, commiting changes to SVN repository."
         self.cursor.execute('UPDATE svnc SET comment = "%s", hash = "%s" WHERE filename = "%s"' % (current['comment'], replacedChecksum, current['filename']))
         client.checkin([current['filename']], current['comment'])

#  gogogo, rgr that!
sc = svnc
for i in sc().scan(sc().get("checkout")):
   if sc().extract(i) != None:
      sc().check(sc().extract(i))
