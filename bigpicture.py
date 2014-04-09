#!/usr/bin/env python -tt
import json, urllib2, re, urlparse, os, errno, random, operator
import sqlite3 as sqlite, sys, glob, urllib

# http://stackoverflow.com/a/11658182
# http://docs.wand-py.org/en/0.3.5/
from wand.image import Image
from wand.color import Color
# http://docs.wand-py.org/en/0.3.5/guide/read.html#read-a-input-stream
from urllib2 import urlopen


# Get a Bing/Azure developer key, sign up: http://datamarket.azure.com/dataset/bing/search
# The free account gives 5000 transactions per month
AZURE_KEY = ''
# Change these paths to match your environment
IMAGE_STORE = '/path/to/put/downloaded/images'
RESULTS_STORE = '/path/to/put/final/image-result'


def get_word(rules):
  with sqlite.connect(r'words.db') as con:
    cur = con.cursor()
    if not rules:
      sql = "select word from word where word_type = 'noun' order by random() limit 1"
      cur.execute(sql)
      return cur.fetchone()[0] 
    else: 
      # TODO: it should be possible to pass 'rules' like "adjective noun preposition noun"
      # maybe someday
      return "testing" 


def get_json(word):
  word = urllib.quote_plus(word)
  url = 'https://api.datamarket.azure.com/Data.ashx/Bing/Search/v1/Image?Query=%27' + word + '%27&$top=20&$format=JSON'

  # http://stackoverflow.com/a/11742802 for the aunthentication part 
  password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
  password_mgr.add_password(None, url ,'', AZURE_KEY)
  handler = urllib2.HTTPBasicAuthHandler(password_mgr)
  opener = urllib2.build_opener(handler)
  urllib2.install_opener(opener)

  response = urllib2.urlopen(url).read().decode('utf-8')
  return response


''' get a list of (image_urls, ids_for_images) from the azure json '''
def get_image_url_list(data):
  image_list = list()
  images = json.loads(data)
  for image in images['d']['results']:
    image_url = image['MediaUrl']
    # use azure's id as part of the id we'll use (should be random enough so no duplicates)
    parsed_thumb_url = urlparse.urlparse(image['Thumbnail']['MediaUrl'])
    id = urlparse.parse_qs(parsed_thumb_url.query)['id'][0]
    image_url_path = urlparse.urlparse(image_url).path
    ext = os.path.splitext(image_url_path)[1] 
    if ext == '.jpg':
      m = re.search(r'.*/(.*?)$', image_url)
      # we also want a human readable name in addition to the azure id because that's nice to have
      filename = id + '--' + m.group(1)
      image_list.append((image_url, filename))
  return image_list



def mkdir_p(path):
  # 'mkdir -p' functionality taken from: http://stackoverflow.com/a/600612
  try:
    os.makedirs(path)
  except OSError as exc:
    if exc.errno == errno.EEXIST and os.path.isdir(path):
      pass
    else: raise


''' download images, write to filesystem '''
def get_images(word, image_url_list):
  mkdir_p(IMAGE_STORE + '/' + word)
  images = list()
  for row in image_url_list:
    image_file_location = IMAGE_STORE + '/' + word + '/' + row[1]
    # don't re-download the same file twice
    if not os.path.isfile(image_file_location):
      try:
        response = urlopen(row[0])
        try:
          with Image(file=response) as img:
            img.format = 'jpeg'
            img.save(filename=image_file_location)
            images.append(image_file_location)
        except:
          pass
      except:
        pass
    else:
      images.append(image_file_location)
  return images


''' the largest image determines the canvas size '''
def get_biggest_image(images):
  big_x = 0
  big_y = 0
  for image in images:
    print image
    with Image(filename=image) as im:
      if im.width > big_x:
        big_x = im.width
      if im.height > big_y:
        big_y = im.height
  return (big_x, big_y) 


''' 
Sample all images, decide what background the canvas should be based on this.
This matters when we start applying random filters
'''
def get_canvas_background_color(word, images):
  mkdir_p(RESULTS_STORE + '/' + word)
  colors = dict()
  i=0
  for image in images:
    with Image(filename=image, resolution=8) as im:
      # make a small low-rez image first, otherwise histogram takes forever and
      # it's not *that* important if the background is exactly right
      im.sample(8, 8)
      im.format = 'ppm'
      # put these in the store for later
      im.save(filename=IMAGE_STORE + '/' + word + '/' + 'small-' + str(i) + '.ppm')
      i = i + 1
      for color in im.histogram:
        # TODO: this is the slow part: fix
        if color in colors:
          colors[color] = im.histogram[color] + colors[color]
        else:
          colors[color] = im.histogram[color]
  # http://stackoverflow.com/a/613218 sort dict by value
  sorted_colors = sorted(colors.iteritems(), key=operator.itemgetter(1))
  return sorted_colors[len(sorted_colors)-1][0]


def composite_operators():
  # wand.image.COMPOSITE_OPERATORS
  # http://docs.wand-py.org/en/latest/wand/image.html
  return ['add',
          'color_burn',
          'color_dodge',
          'darken',
          'difference',
          'exclusion',
          'hard_light',
          'lighten',
          'linear_light',
          'multiply',
          'plus',
          'screen',
          'soft_light',
          'subtract',
          'saturate',
          'replace',
          'threshold'
        ]


def add_bitmaps_to_canvas(word, canvas):
  # Thought it might be fun to add the histogram samples to the final image as a signature
  # These are really intriguing on their own, but this needs work, not sure how it fits
  bitmaps = glob.glob(IMAGE_STORE + '/' + word + '/' + 'small-*.ppm')
  x = canvas.height/50
  y = canvas.height - canvas.height/50
  for image in bitmaps:
    with Image(filename=image) as img:
      img.resize(img.width, img.height)
      #img.transparentize(.5)
      canvas.composite(img, left=x, top=y)
      x = x + img.width * 2
  return canvas


def get_final_canvas_name(path):
  images = glob.glob(path + '--*.jpg')
  highest = 0
  for image in images:
    m = re.search(r'.*--(\d+).jpg', image)
    if m:
      if int(m.group(1)) > int(highest):
        highest = m.group(1)
  highest = int(highest)
  highest += 1
  highest = str(highest)
  return path + '--' + highest.zfill(3) 


def main():

  if len(sys.argv) > 1:
    word          = urllib.quote_plus(sys.argv[1])
  else:
    word          = get_word(False)
  print word

  json            = get_json(word)
  image_url_list  = get_image_url_list(json)
  images          = get_images(word, image_url_list)
  canvas_size     = get_biggest_image(images)
  bg_color        = get_canvas_background_color(word, images)

  mkdir_p(RESULTS_STORE)
  with Image(width=canvas_size[0], height=canvas_size[1], background=bg_color) as canvas:
    for image in images:
      with Image(filename=image) as img:
        x = canvas_size[0] - img.width + 1
        x = random.randint(1, x)
        y = canvas_size[1] - img.height + 1
        y = random.randint(1, y)
        # get random composite operator
        co = composite_operators()[random.randint(1, len(composite_operators()))-1]
        canvas.composite_channel(
            channel='all_channels',
            image=img,
            operator=co,
            left=x,
            top=y
        )

    canvas = add_bitmaps_to_canvas(word, canvas)

    canvas.format = 'jpeg'
    canvas_name = get_final_canvas_name(RESULTS_STORE + '/' + word + '/' + word)
    canvas.save(filename=canvas_name + '.jpg')
    print 'wrote: ' + canvas_name + '.jpg'

if __name__ == '__main__':
  main()

