#!/bin/bash

# first argument is a word
# second argument is number of times to run (no argument means 10)


word=$1
many_times=10
if [[ ($2 -gt 0) ]]; then
  many_times=$2
fi

for ((i=0; i < $many_times; i++)); do
  /usr/bin/env python bigpicture.py "$word"
done
