#!/usr/bin/env python -tt
import sqlite3 as sqlite, re

def get_words_from_wordnet(types):
  # this is very naive, just get words based on type, ignore everything else
  index = 'wordnet/index.'
  words = list()
  i = 0
  for t in types:
    f = open(index + t)
    for line in f:
      entries = re.split("\s+", line)
      word = entries[0]
      if re.match(r'[A-Za-z]', word):
        words.append((i, t, word)) 
        i += 1
    f.close()
  return words

def get_types():
  t = ('noun', 'pronoun', 'verb', 'adverb', 'adjective', 'preposition', 'conjunction')
  return t


def main():

  words = get_words_from_wordnet(get_types())

  with sqlite.connect(r'words.db') as con:
    cur = con.cursor()
    cur.execute('drop table if exists word')

    sql ="""
    create table word (
      word_id integer primary key autoincrement,
      word_type text,
      word text
    )"""
    cur.execute(sql)
    cur.executemany("insert into word values (?,?,?)", words)
    con.commit()

    print "done"

if __name__ == '__main__':
  main()
