'''
    Module created to implement the Media Catalog service
    By: Juan Tomás Araque Martínez
        and Ángel García Collado
'''

from distutils.log import error
import logging
import uuid
import random
import os
import sys
import json

import Ice
import IceStorm

try:
    import IceFlix
except ImportError:
    Ice.loadSlice(os.path.join(os.path.dirname(__file__), "iceflix.ice"))
    import IceFlix
from service_announcement import (
    ServiceAnnouncementsListener,
    ServiceAnnouncementsSender,
)
def createDB(service_id):
    msg = "Catalog " + service_id + " creating DB"
    logging.info(msg)
    dest_file = "./catalogDB/"+service_id 
    os.open(dest_file)
    return dest_file

def removeDB(service_id):
    msg = "Catalog " + service_id + " removing DB"
    logging.info(msg)
    dest_file = "./catalogDB/"+service_id + ".json"
    os.remove(dest_file)

class MediaCatalog(IceFlix.MediaCatalog):    
    def __init__(self):
        self.media_providers = {}
        self.service_id = str(uuid.uuid4())
        self.catalog_updates_prx = None
        self.servant_serv_announ = None
        self.path_db = createDB(self.service_id)

    def getTile(self, media_id, user_token, current=None):
        main_prx = random.choice(self.servant_serv_announ.mains.values())
        #Search user name
        if user_token:
            try:
                auth_prx = main_prx.getAuthenticator()
                user_name = auth_prx.whois(user_token)
            except IceFlix.TemporaryUnavailable:
                raise IceFlix.TemporaryUnavailable()
            except IceFlix.Unauthorized:
                raise IceFlix.Unauthorized()

        #Search media in DB
        with open(self.path_db) as db:
            data = json.load(db)
        media_name = data["info"][media_id]
        if not media_name:
            raise IceFlix.WrongMediaId(media_id)

        #Search tags
        tags = [""]
        if user_token:
            tags = data["tags"][user_name][media_id]

        #Search provider
        try:
            media_provider = self.media_providers[media_id]
            media_provider = IceFlix.StreamProviderPrx.uncheckedCast(media_provider)
            media_provider.ping()
        except Ice.LocalException:
            self.media_providers[media_id] = None
            raise IceFlix.TemporaryUnavailable()

        #Objets creation
        media_info = IceFlix.MediaInfo(media_name, tags)
        media = IceFlix.Media(media_id, media_provider, media_info)
        return media

    def getTilesByName(self, name, exact, current=None):
        print()
    def getTilesByTags(self, tags, include_all_tags, current=None):
        print()
    def addTags(self, media_id, tags, user_token, current=None):
        print()
    def removeTags(self, media_id, tags, user_token, current=None):
        print()
    def renameTile(self, media_id, name, admin_token, current=None):
        print()
    def updateDB(self, catalog_database, service_id, current=None):
        print()

class CatalogUpdates(IceFlix.CatalogUpdates):
    def renameTile(self, media_id, name, service_id, current=None):
        print()
    def addTags(self, media_id, tags, user, service_id, current=None):
        print()
    def removeTags(self, media_id, tags, user, service_id, current=None):
        print()

class StreamAnnouncements(IceFlix.StreamAnnouncements):
    def newMedia(self, media_id, initial_name, service_id, current=None):
        print()
    def removedMedia(self, media_id, service_id, current=None):
        print()

class CatalogApp(Ice.Application):
    def __init__(self):
        self.adapter = None
        self.servant = MediaCatalog()
        self.proxy = None
    def run(self, args):
        broker = self.communicator()
        self.adapter = broker.createObjectAdapter("Catalog")
        self.adapter.activate()

        logging.info(self.proxy)
        self.shutdownOnInterrupt()
        broker.waitForShutdown()
        removeDB(self.servant.service_id)
        return 0

if __name__ == "__main__":
    APP = CatalogApp()
    sys.exit(APP.main(sys.argv)) 