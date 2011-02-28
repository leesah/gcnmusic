#!/usr/bin/env python

from gmusic import download

ids = ['A40e8a994ed8b4b01', 'A52520a7812726f66']
path = '~/Music/Downloads/'
for id in ids:
    download(id, path)

exit()
#try:
#    download(id, path)
#except Captchaed:
#    # Refresh IP
#    reconnect()
#    # Try download again
#    download(id, path)
