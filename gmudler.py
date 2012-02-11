#!/usr/bin/env python

from HTMLParser import HTMLParser
from urllib import urlopen, urlretrieve, unquote, ContentTooShortError
from os import makedirs, access, F_OK, listdir, rename, remove
from pickle import dump
from argparse import ArgumentParser
from eyeD3 import Tag, UTF_8_ENCODING, ID3_V2_4

__DEBUG__ = False

def main():

    parser = ArgumentParser(description='Download music from music.google.cn.')
    parser.add_argument('-p', '--path', required=True)
    parser.add_argument('-t', '--title')
    parser.add_argument('id')
    args = parser.parse_args()
    
    try:
        download(args.id, args.title, args.path)
    except Captchaed:
        print 'CAPTCHA!', 'Refresh IP and retry.'
        exit(100)

    exit(0)

def download(id, t, path = './', dry = False):
    if id.startswith('A'):
        Artist(id, 'http://www.google.cn/music/artist?id=' + id).entitle(t).download(path, dry)
    elif id.startswith('B'):
        Album(id, 'http://www.google.cn/music/album?id=' + id).entitle(t).download(path, dry)
    elif id.startswith('S'):
        song = Song(id, 'http://www.google.cn/music/top100/musicdownload?id=' + id).entitle(t).download(path, dry)
    else:
        print 'ID is not valid.'
        exit(-1)

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
            print 'Using given title:', t
            self.title = t
            self.titleGiven = True

        return self
        
    def download(self, path, dry):
        print self.id, self.title
        dirname = self.id + '.' + self.title if len(self.title) > 0 else self.id
        path += dirname + '/'
        
        # Make the directory
        if not access(path, F_OK):
            print 'Making directory "%s"...' % path,
            if not dry: makedirs(path)
            print 'Done.'
            print
            
        # Process all albums, no matter it's a dry run or not
        items = self.albumList.items()
        count = len(items)
        for index in range(0, count):
            print self.id, self.title, '[%02d/%02d]' % (index + 1, count),
            Album(items[index][0], items[index][1], self).download(path, dry)
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
        
        # Process controlers
        self.songListFound = False
        self.albumImageFound = False
        self.albumFound = False
        self.albumTitleFound = False
        self.titleGiven = False

        self.feed(urlopen(self.url).read().replace('下载', '__DOWNLOAD__').replace('《','').replace('》',''))

    def entitle(self, t):
        if t is not None:
            print 'Using given title:', t
            self.title = t
            self.titleGiven = True

        return self
        
    def download(self, path, dry):
        print self.id, self.title
        dirname = self.id + '.' + self.title if len(self.title) > 0 else self.id
        path += dirname + '/'
        cover = path + 'cover.jpg'
        
        # Make the directory
        if not access(path, F_OK):
            print 'Making directory "%s"...' % path,
            if not dry: makedirs(path)
            print 'Done.'
            print
        
        # Download the cover image
        if not access(cover, F_OK):
            print 'Downloading cover image...',
            if not dry: urlretrieve(self.imageUrl, cover)
            print 'Done.'
            print
        
        # List all files in the directory
        existings = {} if dry else listdir(path)
        
        # Process all songs, no matter it's a dry run or not
        items = self.songList.items()
        count = len(items)
        for index in range(0, count):
            print self.id, self.title, '[%02d/%02d]' % (index + 1, count),
            for filename in existings:
                if filename.startswith(items[index][0]) and not filename.endswith('.tmp'):
                    print 'File found.', 'Skipping...'
                    print filename
                    break
            else:
                Song(items[index][0], items[index][1], self, cover).download(path, dry)
            print

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
        self.captchaed = False
        
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
            print 'Using given title:', t
            self.title = t
            self.titleGiven = True

        return self
        
    def download(self, path, dry):
        print self.id, self.title
        debug('id = ' + self.id)
        debug('url = ' + self.url)

        if not hasattr(self, 'fileUrl'):
            print 'Unavailable.', 'This song is unavailable for downloading.'
            
        else:
            debug('fileUrl = ' + self.fileUrl)
            
            if not dry:
                tmpname = path + self.id + '.tmp'
                realname = path + self.id + '.' + self.title + '.' + self.fileFormat
                def __progress(count, size, total):
                    if count % 200 == 100: print '%d%%' % (count * size * 100 / total)

                try:
                    # This is where the downloading actually happens.
                    urlretrieve(self.fileUrl, tmpname, __progress)
                except ContentTooShortError:
                    print 'Failed.', 'Removing incomplete file...',
                    remove(tmpname)
                    print 'Done.'
                    return

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

                rename(tmpname, realname)
                print 'Done.'
        
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        
        # <div class="captcha"
        if tag == 'div' and attrs.has_key('class') and attrs['class'] == "captcha":
            raise Captchaed()
                    
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
            
def debug(message):
    if __DEBUG__:
        print '[DEBUG]', message

class Captchaed(Exception):
    pass

main()
