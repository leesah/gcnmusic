#!/usr/bin/env python

from argparse import ArgumentParser
from HTMLParser import HTMLParser
from urllib import urlopen, urlretrieve, unquote, ContentTooShortError
from os import makedirs, access, F_OK, listdir, rename, remove
from sys import stdout
from socket import error
from eyeD3 import Tag, UTF_8_ENCODING, ID3_V2_4
from subprocess import call

parser = ArgumentParser(description='Download music from music.google.cn.')
parser.add_argument('-p', '--path', required=True, help='the path where you want the files to be saved to')
parser.add_argument('-t', '--title', help='the title of either an artist, an album, or a song, depending on the type of the given id')
parser.add_argument('-r', '--refresher', help='a command line utilily that can refresh your IP address')
parser.add_argument('-v', '--verbose', action='store_const', const=True, default=False, help='turn on verbose mode')
parser.add_argument('id', help='an id of either an artist, an album, or a song')
args = parser.parse_args()

def main():

    try:
        download(args.id, args.title, args.path if args.path.endswith('/') else args.path + '/')
        
    except InvalidId:
        print 'Invalid ID:', args.id
        exit(-1)
        
    except UnfixableCaptcha:
        print
        print 'CAPTCHA!', 'Refresh IP and retry.'
        exit(100)
        
    except KeyboardInterrupt:
        print
        print 'Cancelled.'
        exit(0)

    except Exception as e:
        print
        print 'Network failure or other error.', 'Check connection and retry.'
        print e
        exit(-1)

    else:
        print 'ALL DONE.'
        exit(0)
    
def download(id, t, path = './'):
    if id.startswith('A'):
        Artist(id, 'http://www.google.cn/music/artist?id=' + id).entitle(t).download(path)
    elif id.startswith('B'):
        Album(id, 'http://www.google.cn/music/album?id=' + id).entitle(t).download(path)
    elif id.startswith('S'):
        Song(id, 'http://www.google.cn/music/top100/musicdownload?id=' + id).entitle(t).download(path)
    else:
        raise InvalidId(id)

class GoogleMusicParser(HTMLParser):
    def handle_charref(self, name):
        self.handle_data(unichr(int(name)))
    
    def feed(self, data):
        HTMLParser.feed(self, data.decode('utf-8', 'ignore'))
    
class Artist(GoogleMusicParser):
    def __init__(self, id, url):
        HTMLParser.__init__(self)
        self.id = id
        self.url = url

        self.title = ''
        self.albumList = {}
        
        # Process controlers
        self.albumFound = False
        self.albumTitleFound = False
        self.artistFound = False
        self.artistTitleFound = False
        self.titleGiven = False

        self.feed(urlopen(url).read())
    
    def entitle(self, t):
        if t is not None:
            debug('Using given title:' + t)
            self.title = t.decode('utf-8', 'ignore')
            self.titleGiven = True

        return self
        
    def download(self, path):
        print self.id, self.title
        dirname = self.id + '.' + self.title if len(self.title) > 0 else self.id
        path += dirname + '/'
        
        # Make the directory
        if not access(path, F_OK):
            print 'Making directory "%s"...' % path,
            makedirs(path)
            print 'Done.'
            print
            
        # Process all albums
        items = self.albumList.items()
        count = len(items)
        for index in range(0, count):
            print self.id, self.title, '[%02d/%02d]' % (index + 1, count),
            Album(items[index][0], items[index][1], self).download(path)
            print

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        
        # <table id="album_item"
        if not self.albumFound and tag == 'table' and attrs.has_key('id') and attrs['id'] == 'album_item':
            self.albumFound = True
        
        # <td class="Title"
        elif self.albumFound and tag =='td' and attrs.has_key('class') and attrs['class'] == 'Title':
            self.albumTitleFound = True
        
        # <a href="/music/url?q=/music/album?id...
        elif self.albumTitleFound and tag == 'a' and attrs.has_key('href') and attrs.has_key('name') and attrs['name'] == "LandingPageLink":
            url = attrs['href']
            self.albumList[url.split('id%3D')[1].split('&')[0]] = 'http://www.google.cn' + url
        
        # <table class="ArtistInfo" or <table class="ArtistInfo rightmargininnerinfo"
        elif not self.artistFound and tag == 'table' and attrs.has_key('class') and attrs['class'].startswith("ArtistInfo"):
            self.artistFound = True
        
        # <td class="Title"
        elif self.artistFound and tag == 'td' and attrs.has_key('class') and attrs['class'] == "Title":
            self.artistTitleFound = True
        
    def handle_endtag(self, tag):
        if self.albumFound and tag == 'table':
            self.albumFound = False
            
        elif self.albumTitleFound and tag =='table':
            self.albumTitleFound = False
        
        elif self.artistFound and tag == 'table':
            self.artistFound = False
            
        elif self.artistTitleFound and tag =='td':
            self.artistTitleFound = False
    
    def handle_data(self, data):
        if self.artistTitleFound and not self.titleGiven:
            debug('Raw data for title: ' + data)
            self.title += data

class Album(GoogleMusicParser):
    def __init__(self, id, url, artist = None):
        HTMLParser.__init__(self)
        self.id = id
        self.url = url
        self.artist = artist

        self.title = ''
        self.songList = {}
        self.existings = {}
        
        # Process controlers
        self.songListFound = False
        self.albumImageFound = False
        self.albumFound = False
        self.albumTitleFound = False
        self.titleGiven = False
        

        self.feed(urlopen(self.url).read().replace('下载', '__DOWNLOAD__').replace('《','').replace('》',''))

    def entitle(self, t):
        if t is not None:
            debug('Using given title:' + t)
            self.title = t.decode('utf-8', 'ignore')
            self.titleGiven = True

        return self
        
    def download(self, path):
        print self.id, self.title
        dirname = self.id + '.' + self.title if len(self.title) > 0 else self.id
        path += dirname + '/'
        cover = path + 'cover.jpg'
        
        if access(path, F_OK):
            # List all files in the directory
            self.existings = listdir(path)
        else:
            # Make the directory
            print 'Making directory "%s"...' % path,
            makedirs(path)
            print 'Done.'
            print
        
        # Download the cover image
        if not access(cover, F_OK):
            print 'Downloading cover image...',
            urlretrieve(self.imageUrl, cover)
            print 'Done.'
            print
        
        
        items = self.songList.items()
        count = len(items)
        
        # For all songs
        for index in range(0, count):
            print self.id, self.title, '[%02d/%02d]' % (index + 1, count),
            
            # Skip all those that exist
            existing = self.lookup_existings(items[index][0])
            if existing is not None:
                print
                print 'File found:', existing
            
            # ..., and for those that don't...
            else:
                retried = False            
                # Keep trying until succeeds or runs into unfixable errors
                while True:
                    try:
                        Song(items[index][0], items[index][1], self, cover).download(path)

                    # Captcha is fixable by refreshing IP address
                    except Captcha as c:
                        print 'CAPTCHA!', 'Trying to fix it...'
                        fix_captcha(c)
                    
                    # Network errors worth retrying, but only once
                    except (ContentTooShortError, error):
                        if retried:
                            raise
                        else:
                            print 'Will retry once.'
                            retried = True
                            continue
                    
                    # Simply stop trying if succeeded
                    else:
                        break
            print
                        

    def lookup_existings(self, keyword):
        for existing in self.existings:
            if existing.startswith(keyword) and not existing.endswith('.tmp'):
                return existing
        return None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        
        # <table id="song_list"
        if not self.songListFound and tag == 'table' and attrs.has_key('id') and attrs['id'] == "song_list":
            self.songListFound = True
        
        # <tbody id="...
        elif self.songListFound and tag =='tbody' and attrs.has_key('id'):
            self.songList[attrs['id']] = 'http://www.google.cn/music/top100/musicdownload?id=' + attrs['id']
        
        # <div class="big-thumb big-thumb-album"
        elif not self.albumImageFound and tag == 'div' and attrs.has_key('class') and attrs['class'] == "big-thumb big-thumb-album":
            self.albumImageFound = True
        
        # <img class="thumb-img"
        elif self.albumImageFound and tag =='img' and attrs.has_key('class') and attrs['class'] == "thumb-img" and attrs.has_key('src'):
            self.imageUrl = attrs['src']
        
        # <table class="AlbumInfo" or <table class="AlbumInfo rightmargininnerinfo"
        elif not self.albumFound and tag == 'table' and attrs.has_key('class') and attrs['class'].startswith("AlbumInfo"):
            self.albumFound = True
        
        # <span class="Title"
        elif self.albumFound and tag == 'span' and attrs.has_key('class') and attrs['class'] == "Title":
            self.albumTitleFound = True
    
    def handle_endtag(self, tag):
        if self.songListFound and tag == 'table':
            self.songListFound = False
        
        elif self.albumImageFound and tag == 'div':
            self.albumImageFound = False
        
        elif self.albumFound and tag == 'table':
            self.albumFound = False
        
        elif self.albumTitleFound and tag == 'span':
            self.albumTitleFound = False
    
    def handle_data(self, data):
        if self.albumTitleFound and not self.titleGiven:
            debug('Raw data for title: ' + data)
            self.title += data
    
class Song(GoogleMusicParser):
    def __init__(self, id, url, album = None, cover = None):
        HTMLParser.__init__(self)
        self.id = id
        self.url = url
        self.album = album
        self.cover = cover

        self.title = ''
        
        # Process controlers
        self.metaDataFound = False
        self.songTitleFound = False
        self.fileFormatFound = False
        self.fileUrlFound = False
        self.contractInfoFound = False
        self.titleGiven = False
        
        self.feed(urlopen(url).read())
    
    def entitle(self, t):
        if t is not None:
            debug('Using given title:' + t)
            self.title = t.decode('utf-8', 'ignore')
            self.titleGiven = True

        return self
        
    def download(self, path):
        print self.id, self.title
        debug('id = ' + self.id)
        debug('url = ' + self.url)

        if not hasattr(self, 'fileUrl'):
            print 'File URL unavailable.'
            return
            
        debug('fileUrl = ' + self.fileUrl)
        
        tmpname = path + self.id + '.tmp'
        realname = path + self.id + '.' + self.title + '.' + self.fileFormat

        # This is where the downloading actually happens.
        try:
            urlretrieve(self.fileUrl, tmpname, download_progress)
        except:
            if access(tmpname, F_OK):
                remove(tmpname)
            raise

        # Update ID3 info.
        print 'Updating ID3 info...'
        tag = Tag()
        tag.link(tmpname)
        tag.setVersion(ID3_V2_4)
        tag.setTextEncoding(UTF_8_ENCODING)
        tag.setTitle(self.title)
        if self.cover is not None:
            tag.addImage(3, self.cover)
        if self.album is not None: 
            tag.setAlbum(self.album.title)
            if self.album.artist is not None:
                tag.setArtist(self.album.artist.title)
        tag.removeComments()
        tag.update(ID3_V2_4)

        # Save with real name.
        rename(tmpname, realname)

        print 'Done.'
        
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        
        # <div class="captcha"
        if tag == 'div' and attrs.has_key('class') and attrs['class'] == "captcha":
            print
            raise Captcha(self.id)
                    
        # <tr class="meta-data-tr"
        elif not self.metaDataFound and tag == 'tr' and attrs.has_key('class') and attrs['class'] == "meta-data-tr":
            self.metaDataFound = True
        
        # <td class="td-song-name"
        elif self.metaDataFound and not self.songTitleFound and tag == 'td' and attrs.has_key('class') and attrs['class'] == "td-song-name":
            self.songTitleFound = True
        
        # <td class="td-format"
        elif not self.fileFormatFound and tag == 'td' and attrs.has_key('class') and attrs['class'] == "td-format":
            self.fileFormatFound = True
        
        # <div class="download"
        elif not self.fileUrlFound and tag == 'div' and attrs.has_key('class') and attrs['class'] == "download":
            self.fileUrlFound = True
    
        # <div class="contract-info"
        elif self.fileUrlFound and tag == 'div' and attrs.has_key('class') and attrs['class'] == "contract-info":
            self.contractInfoFound = True
    
        # <a href="/music/top100/url?q=...
        elif self.fileUrlFound and not self.contractInfoFound and tag == 'a' and attrs.has_key('href'):
            self.fileUrl = unquote(attrs['href'][20:attrs['href'].index('&')])


    def handle_endtag(self, tag):
        if self.metaDataFound and tag == 'tr':
            self.metaDataFound = False
        
        elif self.songTitleFound and tag == 'td':
            self.songTitleFound = False
        
        elif self.fileFormatFound and tag == 'td':
            self.fileFormatFound = False
        
        elif self.contractInfoFound and tag == 'div':
            self.contractInfoFound = False
        
        elif self.fileUrlFound and not self.contractInfoFound and tag == 'div':
            self.fileUrlFound = False
        
    def handle_data(self, data):
        if self.songTitleFound and not self.titleGiven:
            debug('Raw data for title: ' + data)
            self.title += data.replace('/', ', ')
        
        if self.fileFormatFound:
            self.fileFormat = data.lower()
            
def download_progress(count, size, total):
    if count * size >= total:
        print '100%'
    elif count % 200 == 100:
        print '%d%%...' % (count * size * 100 / total),
        stdout.flush()

def fix_captcha(captcha):
    if args.refresher is None or 0 != call(args.refresher):
        raise UnfixableCaptcha(captcha)
            

def debug(message):
    if args.verbose:
        print '[DEBUG]', message

class Captcha(Exception):
    def __init__(self, id):
        self.id = id

class UnfixableCaptcha(Exception):
    def __init__(self, captcha):
        self.captcha = captcha

class InvalidId(Exception):
    def __init__(self, id):
        self.id = id

main()
