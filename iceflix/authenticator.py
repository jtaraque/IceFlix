'''
    Module created to implement the Authentication service
    By: Juan Tomás Araque Martínez
        and Ángel García Collado
'''

from distutils.log import error
import logging
from time import sleep
import uuid
import random
import os
import sys
import json
import threading
import secrets

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

def readJSON():
    with open("./users.json") as db:
        data = json.load(db)
    return data

def writeJSON(data):
    db = open("./users.json", "w")
    json.dump(data, db, indent=6)

def getTopic(communicator, topic_name):
    topic_manager = IceStorm.TopicManagerPrx.checkedCast(
        communicator.propertyToProxy("IceStorm.TopicManager"),
    )
    try:
        topic = topic_manager.create(topic_name)
    except IceStorm.TopicExists:
        topic = topic_manager.retrieve(topic_name)

    return topic

class Authenticator(IceFlix.Authenticator):

    def __init__(self) -> None:
        self.service_id = str(uuid.uuid4())
        self.user_tokens = {}
        self.users_passwords = readJSON()
        self.servant_serv_announ = None
        self.updates_prx = None
        self.revocations_prx = None
        self.is_updated = False

    def getMain(self):
        main_prx = random.choice(list(self.servant_serv_announ.mains.values()))
        return main_prx

    def share_data_with(self, service):
        """Share the current database with an incoming service."""
        db = IceFlix.UsersDB(self.users_passwords, self.user_tokens)
        service.updateDB(db, self.service_id)

    def remove_token(self, token, current=None):
        iterator = iter(list(self.user_tokens.keys()))
        while True:
            try:
                user = iterator.__next__()
                if self.user_tokens[user] == token:
                    del self.user_tokens[user]
                    self.revocations_prx.revokeToken(token, self.service_id)
            except StopIteration:
                break

    def refreshAuthorization(self, user, passwordHash, current=None):
        if user in self.users_passwords.keys() and passwordHash == self.users_passwords[user]:
            new_token = secrets.token_urlsafe(40)
            self.user_tokens[user] = new_token
            self.updates_prx.newToken(user, new_token, self.service_id)
            timer = threading.Timer(120.0, self.remove_token, args=(new_token,))
            timer.start()
            return new_token
        raise IceFlix.Unauthorized()

    def isAuthorized(self, userToken, current=None):
        for user in self.user_tokens.keys():
            if userToken == self.user_tokens[user]:
                return True
        return False

    def whois(self, userToken, current=None):
        for user in self.user_tokens.keys():
            if userToken == self.user_tokens[user]:
                return user
        raise IceFlix.Unauthorized()

    def addUser(self, user, passwordHash, adminToken, current=None):
        main_prx = self.getMain()
        try:
            if not main_prx.isAdmin(adminToken):
                raise IceFlix.Unauthorized()
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()
        except Exception:
            raise IceFlix.TemporaryUnavailable()

        self.users_passwords[user] = passwordHash
        writeJSON(self.users_passwords)
        self.updates_prx.newUser(user, passwordHash, self.service_id)

    def removeUser(self, user, adminToken, current=None):
        main_prx = self.getMain()
        try:
            if not main_prx.isAdmin(adminToken):
                raise IceFlix.Unauthorized()
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()
        except Exception:
            raise IceFlix.TemporaryUnavailable()

        del self.users_passwords[user]
        writeJSON(self.users_passwords)
        self.revocations_prx.revokeUser(user, self.service_id)

    def updateDB(self, currentDatabase, srvId, current=None):
        # if not srvId in self.servant_serv_announ.known_ids:
        #     raise IceFlix.UnknownService()
        if not self.is_updated:
            self.users_passwords = currentDatabase.userPasswords
            self.user_tokens = currentDatabase.usersToken
            self.is_updated = True

class UserUpdates(IceFlix.UserUpdates):

    def __init__(self) -> None:
        self.serv_auth = None
        self.serv_subscriber = None

    def newUser(self, user, passwordHash, srvId, current=None):
        if srvId in self.serv_subscriber.known_ids:  
            self.serv_auth.users_passwords[user] = passwordHash
            writeJSON(self.serv_auth.users_passwords)

    def newToken(self, user, userToken, srvId, current=None):
        if srvId in self.serv_subscriber.known_ids:   
            self.serv_auth.user_tokens[user] = userToken

class Revocations(IceFlix.Revocations):

    def __init__(self) -> None:
        self.serv_auth = None
        self.serv_subscriber = None

    def revokeToken(self, userToken, srvId, current=None):
        if srvId in self.serv_subscriber.known_ids:
            for user in self.serv_auth.user_tokens.keys():
                if self.serv_auth.user_tokens[user] == userToken:
                    del self.serv_auth.user_tokens[user]
                    return

    def revokeUser(self, user, srvId, current=None):
        if srvId in self.serv_subscriber.known_ids:
            del self.serv_auth.users_passwords[user]
            writeJSON(self.serv_auth.user_passwords)

class AuthApp(Ice.Application):
    def __init__(self):
        self.servant = Authenticator()
        self.proxy = None
        self.adapter = None
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
            self.servant, self.servant.service_id, IceFlix.AuthenticatorPrx
        )

        subscriber_prx = self.adapter.addWithUUID(self.subscriber)
        topic.subscribeAndGetPublisher({}, subscriber_prx)

    def run(self, args):
        broker = self.communicator()
        self.adapter = broker.createObjectAdapter("Authenticator")
        self.adapter.activate()

        #Subscriptions
        #User Updates
        user_updates_topic = getTopic(broker, "UserUpdates")
        servant_user_updates = UserUpdates()
        user_updates_prx = self.adapter.addWithUUID(servant_user_updates)
        user_updates_topic.subscribeAndGetPublisher({}, user_updates_prx)

        user_updates_pub = user_updates_topic.getPublisher()
        user_updates_pub = IceFlix.UserUpdatesPrx.uncheckedCast(user_updates_pub)

        #Revocations
        revocations_topic = getTopic(broker, "Revocations")
        servant_revocations = Revocations()
        revocations_prx = self.adapter.addWithUUID(servant_revocations)
        revocations_topic.subscribeAndGetPublisher({}, revocations_prx)

        revocations_pub = revocations_topic.getPublisher()
        revocations_pub = IceFlix.RevocationsPrx.uncheckedCast(revocations_pub)

        #Service Announcements

        self.proxy = self.adapter.add(self.servant, broker.stringToIdentity("Authenticator"))
        self.setup_announcements()
        self.announcer.start_service()


        #Authenticator attributes
        
        self.servant.servant_serv_announ = self.subscriber
        self.servant.revocations_prx = revocations_pub
        self.servant.updates_prx = user_updates_pub

        #User updates attributes
        servant_user_updates.serv_auth = self.servant
        servant_user_updates.serv_subscriber = self.subscriber

        #Revocations attributes
        servant_revocations.serv_auth = self.servant
        servant_revocations.serv_subscriber = self.subscriber

       
        logging.info(self.proxy)
        self.shutdownOnInterrupt()
        broker.waitForShutdown()
        return 0

if __name__ == "__main__":
    APP = AuthApp()
    sys.exit(APP.main(sys.argv))