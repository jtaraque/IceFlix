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

def openDB(path):
    with open(path) as db:
        data = json.load(db)
    return data

class MediaCatalog(IceFlix.MediaCatalog):    
    def __init__(self):
        self.media_providers = {}
        self.service_id = str(uuid.uuid4())
        self.catalog_updates_prx = None
        self.servant_serv_announ = None
        self.path_db = createDB(self.service_id)
        self.is_updated = False

    def getUser(self, user_token):
        main_prx = random.choice(self.servant_serv_announ.mains.values())
        try:
            auth_prx = main_prx.getAuthenticator()
            user_name = auth_prx.whois(user_token)
        except IceFlix.TemporaryUnavailable:
            raise IceFlix.TemporaryUnavailable()
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()
    def getTile(self, media_id, user_token, current=None):
        
        #Search user name
        if user_token:
            try:
                user_name = self.getUser(user_token)
            except IceFlix.TemporaryUnavailable:
                raise IceFlix.TemporaryUnavailable()
            except IceFlix.Unauthorized:
                raise IceFlix.Unauthorized()
        
        #Search media in DB
        data = openDB(self.path_db)
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
        data = openDB(self.path_db)
        ids = []
        if exact:
            for media_id in data["info"].keys():
                if name == data["info"][media_id]:
                    ids.append(media_id)
            return ids
        for media_id in data["info"].keys():
            if name in data["info"][media_id]:
                ids.append(media_id)        
        return ids

    def getTilesByTags(self, tags, include_all_tags, user_token, current=None):
        #Get user name
        try:
            user_name = self.getUser(user_token)
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()

        #Get tags
        data = openDB(self.path_db)
        tags_user = data["tags"][user_name]
        ids = []
        if include_all_tags:
            for media_id in tags_user.keys():
                if all(elem in tags_user[media_id] for elem in tags):
                    ids.append(media_id)
            return ids
        for media_id in tags_user.keys():
                if any(elem in tags_user[media_id] for elem in tags):
                    ids.append(media_id)
        return ids

    def addTags(self, media_id, tags, user_token, current=None):
        #Get user name
        try:
            user_name = self.getUser(user_token)
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()

        #Search medio
        data = openDB(self.path_db)
        media_user = data["tags"][user_name].keys()
        if not media_id in media_user:
            raise IceFlix.WrongMediaId(media_id)

        #Get tags
        current_tags = data["tags"][user_name][media_id]
        new_tags = current_tags
        for tag in tags:
            if not tag in new_tags: new_tags.append(tag)
        #Set tags
        data["tags"][user_name][media_id] = new_tags
        db = open(self.path_db, "w")
        json.dump(data, db, indent=6)
        self.catalog_updates_prx.addTags(media_id, tags, user_token,self.service_id)

    def removeTags(self, media_id, tags, user_token, current=None):
        #Get user name
        try:
            user_name = self.getUser(user_token)
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()

        #Search medio
        data = openDB(self.path_db)
        media_user = data["tags"][user_name].keys()
        if not media_id in media_user:
            raise IceFlix.WrongMediaId(media_id)
        
        #Get tags
        current_tags = data["tags"][user_name][media_id]
        new_tags = current_tags
        for tag in tags:
            if tag in new_tags:
                new_tags.remove(tag)
        data["tags"][user_name][media_id] = new_tags
        db = open(self.path_db, "w")
        json.dump(data, db, indent=6)
        self.catalog_updates_prx.removeTags(media_id, tags, user_token,self.service_id)

    def renameTile(self, media_id, name, admin_token, current=None):
        #Check admin token
        main_prx = random.choice(self.servant_serv_announ.mains.values())
        is_admin = False
        try:
            is_admin = main_prx.isAdmin(admin_token)
        except Ice.LocalException:
            error("Servicio main no disponible")
        if not is_admin:
            raise IceFlix.Unauthorized()
        
        #Search medio
        data = openDB(self.path_db)
        if not media_id in data["info"].keys():
            raise IceFlix.WrongMediaId(media_id)
        
        data["info"][media_id] = name
        self.catalog_updates_prx.renameTile(media_id, name, self.service_id)
        
    def updateDB(self, catalog_database, service_id, current=None):
        if not service_id in self.servant_serv_announ.catalogs.keys():
            raise IceFlix.UnknownService()
        if not self.is_updated:
            data = {}
            for media_db in catalog_database:
                data["info"][media_db.mediaId] = media_db.name
                data["tags"] = media_db.tagsPerUser

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