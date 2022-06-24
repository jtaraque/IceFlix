from distutils.log import error
import logging
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

def writeJSON(data):
    json.dump("../users.json", data)

class Authenticator(IceFlix.Authenticator):

    def __init__(self, main_prx, updates_prx, revocations_prx) -> None:
        self.user_tokens = {}
        self.main_prx = main_prx
        self.updates_prx = updates_prx
        self.revocations_prx = revocations_prx
        self.users_passwords = json.load("../user.json")
        self.announcer = None
        self.subscriber = None
        self.srvId = str(uuid.uuid4())

    def remove_token(self, token, current=None):
        for user in self.user_tokens.keys():
            if token == self.user_tokens[user]:
                del self.user_tokens[user]
                self.revocations_prx.revokeToken(token, self.srvId)

    def refreshAuthorization(self, user, passwordHash, current=None):
        if user in self.users_passwords.keys() and passwordHash == self.users_passwords[user]:
            new_token = secrets.token_urlsafe(40)
            self.user_tokens[user] = new_token
            self.updates_prx.newToken(user, new_token, self.srvId)
            timer = threading.Timer(120.0, self.remove_token, args=(new_token,))
            timer.start()
            return new_token
        raise IceFlix.Unauthorized()

    def isAuthorized(self, userToken, current=None):
        for user in self.userTokens.keys():
            if userToken == self.userTokens[user]:
                return True
        return False

    def whois(self, userToken, current=None):
        for user in self.userTokens.keys():
            if userToken == self.userTokens[user]:
                return user
        raise IceFlix.Unauthorized()

    def addUser(self, user, passwordHash, adminToken, current=None):
        try:
            if not self.main_prx.isAdmin(adminToken):
                raise IceFlix.Unauthorized()
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()
        except Exception:
            raise IceFlix.TemporaryUnavailable()

        self.users_passwords[user] = passwordHash
        writeJSON(self.users_passwords)
        self.updates_prx.newUser(user, passwordHash, self.srvId)

    def removeUser(self, user, adminToken, current=None):
        try:
            if not self.main_prx.isAdmin(adminToken):
                raise IceFlix.Unauthorized()
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()
        except Exception:
            raise IceFlix.TemporaryUnavailable()

        del self.users_passwords[user]
        writeJSON(self.users_passwords)
        self.revocations_prx.revokeUser(user, self.srvId)

    def updateDB(self, currentDatabase, srvId, current=None):
        if not srvId in self.subscriber.knowns_ids:
            raise IceFlix.UnknownService()
        self.users_passwords = currentDatabase.usersPasswords
        self.user_tokens = currentDatabase.usersTokens

class UserUpdates(IceFlix.UserUpdates):

    def __init__(self, serv_auth, self_subscriber) -> None:
        self.serv_auth = serv_auth
        self.serv_subscriber = self_subscriber

    def newUser(self, user, passwordHash, srvId, current=None):
        if srvId in self.subscriber.knowns_ids:  
            self.serv_auth.users_passwords[user] = passwordHash
            writeJSON(self.serv_auth.users_passwords)
        
    def newToken(self, user, userToken, srvId, current=None):
        if srvId in self.subscriber.knowns_ids:   
            self.serv_auth.user_tokens[user] = userToken
        

class Revocations(IceFlix.Revocations):

    def __init__(self, serv_auth, self_subscriber) -> None:
        self.serv_auth = serv_auth
        self.serv_subscriber = self_subscriber

    def revokeToken(self, userToken, srvId, current=None):
        if srvId in self.subscriber.knowns_ids:
            for user in self.serv_auth.user_tokens.keys():
                if self.serv_auth.user_tokens[user] == userToken:
                    del self.serv_auth.user_tokens[user]
                    return
    def revokeUser(self, user, srvId, current=None):
        if srvId in self.subscriber.knowns_ids:
            del self.serv_auth.users_passwords[user]
            writeJSON(self.serv_auth.user_passwords)

class AuthApp(Ice.Application):
    print()

if __name__ == "__main__":
    APP = AuthApp()
    sys.exit(APP.main(sys.argv))