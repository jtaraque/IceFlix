'''
    Module created to implement the Media Catalog service
    By: Juan Tomás Araque Martínez
        and Ángel García Collado
'''

from datetime import datetime
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

def getTopic(communicator, topic_name):
    topic_manager = IceStorm.TopicManagerPrx.checkedCast(
        communicator.propertyToProxy("IceStorm.TopicManager"),
    )
    try:
        topic = topic_manager.create(topic_name)
    except IceStorm.TopicExists:
        topic = topic_manager.retrieve(topic_name)

    return topic

def createDB(service_id):
    data = openDB("./catalogDB/catalogDB.json")

    msg = "Catalog " + service_id + " creating DB"
    logging.info(msg)
    dest_file = "./catalogDB/"+service_id+".json"
    os.open(dest_file, os.O_CREAT | os.O_WRONLY)
    db = open(dest_file, "w")
    json.dump(data, db, indent=6)
    return dest_file

def removeDB(service_id):
    msg = "Catalog " + service_id + " removing DB"
    logging.info(msg)
    dest_file = "./catalogDB/"+service_id + ".json"
    my_data = openDB(dest_file)
    persistent_bd = open("./catalogDB/catalogDB.json", "w")
    json.dump(my_data, persistent_bd, indent=6)
    os.remove(dest_file)

def openDB(path):
    with open(path) as db:
        data = json.load(db)
    return data

def writeDB(path, data):
    db = open(path, "w")
    json.dump(data, db, indent=6)

def checkMediaId(media_id, data):
    if not media_id in data["info"].keys():
        raise IceFlix.WrongMediaId(media_id)

def addTagsList(data, user_name, media_id, tags):
    try:
        current_tags = data["tags"][user_name][media_id]
    except KeyError:
        current_tags = []
    new_tags = current_tags
    for tag in tags:
        if not tag in new_tags: new_tags.append(tag)
    return new_tags

def removeTagsList(data, user_name, media_id, tags):
    current_tags = data["tags"][user_name][media_id]
    new_tags = current_tags
    for tag in tags:
        if tag in new_tags:
            new_tags.remove(tag)
    return new_tags

class MediaCatalog(IceFlix.MediaCatalog):    
    def __init__(self):
        self.media_providers = {}
        self.service_id = str(uuid.uuid4())
        self.catalog_updates_prx = None
        self.servant_serv_announ = None
        self.announcer = None
        self.path_db = createDB(self.service_id)
        self.is_updated = False

    def share_data_with(self, service):
        """Share the current database with an incoming service."""
        data = openDB(self.path_db)
        media_list = []
        for media_id in data["info"].keys():
            tags_user = {}
            for user in data["tags"].keys():
                for id in data["tags"][user].keys():
                    if id == media_id:
                        tags_user[user] = data["tags"][user][id]
            media = IceFlix.MediaDB(media_id, data["info"][media_id], tags_user)
            media_list.append(media)
        service.updateDB(media_list, self.service_id)

    def getUser(self, user_token, current=None):
        main_prx = random.choice(list(self.servant_serv_announ.mains.values()))
        try:
            auth_prx = main_prx.getAuthenticator()
            user_name = auth_prx.whois(user_token)
        except IceFlix.TemporaryUnavailable:
            raise IceFlix.TemporaryUnavailable()
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()
        return user_name

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
        try:
            checkMediaId(media_id, data)
        except IceFlix.WrongMediaId:
            raise IceFlix.WrongMediaId(media_id)
        media_name = data["info"][media_id]
    
        #Search tags
        tags = [""]
        if user_token:
            try:
                tags = data["tags"][user_name][media_id]
            except KeyError:
                tags = [""]

        #Search provider
        try:
            media_provider = self.media_providers[media_id]
            media_provider = IceFlix.StreamProviderPrx.uncheckedCast(media_provider)
            media_provider.ice_ping()
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
        try:
            checkMediaId(media_id, data)
        except IceFlix.WrongMediaId:
            raise IceFlix.WrongMediaId(media_id)

        #Get tags
        new_tags = addTagsList(data, user_name, media_id, tags)
        #Set tags
        try:
            data["tags"][user_name][media_id] = new_tags
        except KeyError:
            data["tags"][user_name] = {}
            data["tags"][user_name][media_id] = new_tags

        writeDB(self.path_db, data)
        self.catalog_updates_prx.addTags(media_id, tags, user_name,self.service_id)

    def removeTags(self, media_id, tags, user_token, current=None):
        #Get user name
        try:
            user_name = self.getUser(user_token)
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()

        #Search medio
        data = openDB(self.path_db)
        try:
            checkMediaId(media_id, data)
        except IceFlix.WrongMediaId:
            raise IceFlix.WrongMediaId(media_id)
        
        #Get tags
        new_tags = removeTagsList(data, user_name, media_id, tags)
        data["tags"][user_name][media_id] = new_tags
        writeDB(self.path_db, data)
        self.catalog_updates_prx.removeTags(media_id, tags, user_name,self.service_id)

    def renameTile(self, media_id, name, admin_token, current=None):
        #Check admin token
        main_prx = random.choice(list(self.servant_serv_announ.mains.values()))
        is_admin = False
        try:
            is_admin = main_prx.isAdmin(admin_token)
        except Ice.LocalException:
            error("Servicio main no disponible")
        if not is_admin:
            raise IceFlix.Unauthorized()
        
        #Search medio
        data = openDB(self.path_db)
        try:
            checkMediaId(media_id, data)
        except IceFlix.WrongMediaId:
            raise IceFlix.WrongMediaId(media_id)
        
        data["info"][media_id] = name
        writeDB(self.path_db, data)
        self.catalog_updates_prx.renameTile(media_id, name, self.service_id)
        
    def updateDB(self, catalog_database, service_id, current=None):
        # if not service_id in self.servant_serv_announ.known_ids:
        #     raise IceFlix.UnknownService()
        if not self.is_updated:
            data = {}
            data["info"] = {}
            data["tags"] = {}

            for media_db in catalog_database:
                data["info"][media_db.mediaId] = media_db.name
                for user in media_db.tagsPerUser.keys():
                    try:
                        data["tags"][user][media_db.mediaId] = media_db.tagsPerUser[user]
                    except KeyError:
                        data["tags"][user] = {}

            writeDB(self.path_db, data)
            self.is_updated = True

class CatalogUpdates(IceFlix.CatalogUpdates):

    def __init__(self) -> None:
        self.servant_serv_announ = None
        self.servant = None
    def renameTile(self, media_id, name, service_id, current=None):
        #Check service
        data = {}
        if service_id in self.servant_serv_announ.known_ids and service_id != self.servant.service_id:
            data = openDB(self.servant.path_db)
        try:
            checkMediaId(media_id, data)
        except IceFlix.WrongMediaId:
            raise IceFlix.WrongMediaId(media_id)
        
        data["info"][media_id] = name
        db = open(self.servant.path_db, "w")
        json.dump(data, db, indent=6)

    def addTags(self, media_id, tags, user, service_id, current=None):

        if service_id in self.servant_serv_announ.known_ids and service_id != self.servant.service_id:
            data = openDB(self.servant.path_db)
        try:
            checkMediaId(media_id, data)
        except IceFlix.WrongMediaId:
            raise IceFlix.WrongMediaId(media_id)
        
        new_tags = addTagsList(data, user, media_id, tags)
      
        #Set tags
        data["tags"][user][media_id] = new_tags
        writeDB(self.servant.path_db, data)

    def removeTags(self, media_id, tags, user, service_id, current=None):
        if service_id in self.servant_serv_announ.known_ids and service_id != self.servant.service_id:
            data = openDB(self.servant.path_db)
        try:
            checkMediaId(media_id, data)
        except IceFlix.WrongMediaId:
            raise IceFlix.WrongMediaId(media_id)

        #Get tags
        new_tags = removeTagsList(data, user, media_id, tags)

        data["tags"][user][media_id] = new_tags
        writeDB(self.servant.path_db, data)

class StreamAnnouncements(IceFlix.StreamAnnouncements):
    def __init__(self):
        self.servant_serv_announ = None
        self.servant = None

    def newMedia(self, media_id, initial_name, service_id, current=None):
        if service_id in self.servant_serv_announ.known_ids:
            logging.info(f"Receiving {initial_name}")
            data = openDB(self.servant.path_db)
            data["info"][media_id] = initial_name
            self.servant.media_providers[media_id] = self.servant_serv_announ.providers[service_id]
            writeDB(self.servant.path_db, data)

    def removedMedia(self, media_id, service_id, current=None):
        if service_id in self.servant_serv_announ.known_ids:
            logging.info(f"Deleting {service_id}")
            data = openDB(self.servant.path_db)
            del data["info"][media_id]
            del self.servant.media_providers[media_id] 
            writeDB(self.servant.path_db, data)

class CatalogApp(Ice.Application):
    def __init__(self):
        self.adapter = None
        self.servant = MediaCatalog()
        self.proxy = None
        self.announcer = None
        self.subscriber = None

    def setup_announcements(self):
        """Configure the announcements sender and listener."""

        communicator = self.communicator()
        topic_manager = IceStorm.TopicManagerPrx.checkedCast(
            communicator.propertyToProxy("IceStorm.TopicManager"),
        )

        try:
            topic = topic_manager.create("ServiceAnnouncements")
        except IceStorm.TopicExists:
            topic = topic_manager.retrieve("ServiceAnnouncements")

        self.announcer = ServiceAnnouncementsSender(
            topic,
            self.servant.service_id,
            self.proxy,
        )

        self.subscriber = ServiceAnnouncementsListener(
            self.servant, self.servant.service_id, IceFlix.MediaCatalogPrx
        )

        subscriber_prx = self.adapter.addWithUUID(self.subscriber)
        topic.subscribeAndGetPublisher({}, subscriber_prx)

    def run(self, args):
        broker = self.communicator()
        self.adapter = broker.createObjectAdapter("Catalog")
        self.adapter.activate()

        #Subscriptions
        #StreamAnnouncements
        stream_announ_topic = getTopic(broker, "StreamAnnouncements")
        servant_stream_announ = StreamAnnouncements()
        stream_announ_prx = self.adapter.addWithUUID(servant_stream_announ)
        stream_announ_topic.subscribeAndGetPublisher({}, stream_announ_prx)

        #CatalogUpdates
        catalog_updates_topic = getTopic(broker, "CatalogUpdates")
        servant_catalog_updates = CatalogUpdates()
        catalog_updates_prx = self.adapter.addWithUUID(servant_catalog_updates)
        catalog_updates_topic.subscribeAndGetPublisher({}, catalog_updates_prx)

        catalog_updates_pub = catalog_updates_topic.getPublisher()
        catalog_updates_pub = IceFlix.CatalogUpdatesPrx.uncheckedCast(catalog_updates_pub)

        #Service Announcements
        self.proxy = self.adapter.add(self.servant, broker.stringToIdentity("MediaCatalog"))
        self.setup_announcements()
        self.announcer.start_service()


        self.servant.catalog_updates_prx = catalog_updates_pub
        self.servant.servant_serv_announ = self.subscriber
        self.servant.announcer = self.announcer

        servant_catalog_updates.servant = self.servant
        servant_catalog_updates.servant_serv_announ = self.subscriber
        

        servant_stream_announ.servant = self.servant
        servant_stream_announ.servant_serv_announ = self.subscriber

        logging.info(self.proxy)
        self.shutdownOnInterrupt()
        broker.waitForShutdown()
        removeDB(self.servant.service_id)

        return 0

if __name__ == "__main__":
    APP = CatalogApp()
    sys.exit(APP.main(sys.argv))