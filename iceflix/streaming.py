'''
    Module created to implement the Streaming service
    By: Juan Tomás Araque Martínez
        and Ángel García Collado
'''

from distutils.log import error
import logging
import uuid
import random
import os
import sys
import string
import hashlib

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
from rtsputils import(
    RTSPEmitter,
    RTSPPlayer
)

CHUNK_SIZE = 1024

class StreamProvider(IceFlix.StreamProvider):
    
    def __init__(self) -> None:
        self.service_id = str(uuid(uuid.uuid4()))
        self.media_available = []
        self.servant_serv_announ = None
        self.stream_announ_prx = None
    def share_data_with(self, service):
        """Share the current database with an incoming service."""
        service.updateDB(None, self.service_id)

    def readMedia(self):
        iterator = os.scandir("./media")
        while 1:
            try:
                media = iterator.__next__()
                media_path = media.path
                file = open(media_path, "rb")
                media_content = file.read()
                media_id = hashlib.sha256(str(media_content).encode()).hexdigest()
                media_name = media_path.split("/")[2].split(".")[0]
                self.stream_announ_prx.newMedia(media_id, media_name, self.service_id)
                self.media_available.append(media_id)
            except StopIteration:
                break
            except Exception:
                error("Error durante el anunciamento de medios")

    def getStream(self, media_id, user_token, current=None):
        #Get authenticator
        authorized = False
        main_prx = random.choice(self.servant_serv_announ.mains.values())
        try:
            auth_prx = main_prx.getAuthenticator()
            authorized = auth_prx.isAuthorized(user_token)
        except IceFlix.TemporaryUnavailable:
            error("Servicio de autenticación no disponible")

        if not authorized:
            raise IceFlix.Unauthorized()

        if not self.isAvailable(media_id):
            raise IceFlix.WrongMediaId(media_id)

        servant_stream_controller = StreamController(user_token)
        stream_controller_prx = current.adapter.addwithUUID(servant_stream_controller)
        stream_controller_prx = IceFlix.StreamControllerPrx.uncheckedCast(stream_controller_prx)

        return stream_controller_prx

    def isAvailable(self, media_id, current=None):
        if media_id in self.media_available:
            return True
        return False

    def reannounceMedia(self, srv_id, current=None):
        if not srv_id in self.servant_serv_announ.known_ids:
            raise IceFlix.UnknownService()
        self.readMedia()

    def uploadMedia(self, file_name, uploader, admin_token, current=None):
        is_admin = False
        main_prx = random.choice(self.servant_serv_announ.mains.values())
        try:
            auth_prx = main_prx.getAuthenticator()
            is_admin = auth_prx.isAdmin(admin_token)
        except Ice.LocalException:
            error("Servicio principal no disponible")
        if not is_admin:
            raise IceFlix.Unauthorized()
        media_title = file_name.split("/")[-1]
        media_size = os.path.getsize(file_name)
        media_path = "./media/"+media_title
        if not os.path.exists(media_path):
            file_bytes = bytes()
            file = open(media_path, "wb")
            while 1:
                try:
                    chunk = uploader.receive(CHUNK_SIZE)
                    file.write(chunk)
                    file_bytes += chunk
                except Exception:
                    raise IceFlix.UploadError()
                if len(file_bytes) >= media_size:
                    break
            media_id = hashlib.sha256(str(file_bytes).encode()).hexdigest()
            media_name = media_title.split(".")[0]
            self.stream_announ_prx.newMedia(media_id, media_name, self.service_id)
            self.media_available.append(media_id)

    def deleteMedia(self, media_id, admin_token, current=None):
        is_admin = False
        main_prx = random.choice(self.servant_serv_announ.mains.values())
        try:
            auth_prx = main_prx.getAuthenticator()
            is_admin = auth_prx.isAdmin(admin_token)
        except Ice.LocalException:
            error("Servicio principal no disponible")
        if not is_admin:
            raise IceFlix.Unauthorized()
        self.media_available.remove(media_id)
        self.stream_announ_prx.removedMedia(media_id, self.service_id)

class StreamController(IceFlix.StreamController):
    def __init__(self, user_token) -> None:
        self.emitter = None
        self.media = None
        self.main_prx = None
        self.user_token = user_token

    def getSDP(self, user_token, port, current=None):
        authorized = False
        try:
            auth_prx = self.main_prx.getAuthenticator()
            authorized = auth_prx.isAuthorized(user_token)
        except IceFlix.TemporaryUnavailable:
            error("Servicio de autenticación no disponible")

        if not authorized:
            raise IceFlix.Unauthorized()
        
        self.emitter = RTSPEmitter(self.media, "127.0.0.1", port)
        self.emitter.start()
        return self.emitter.playback_uri

    def getSyncTopic(self, current = None):
        length = 10
        topic = ''.join(random.SystemRandom().choice(
            string.ascii_letters + string.digits) for _ in range(length))
        return topic

    def refreshAuthentication(self, user_token, current = None):
        authorized = False
        try:
            auth_prx = self.main_prx.getAuthenticator()
            authorized = auth_prx.isAuthorized(user_token)
        except IceFlix.TemporaryUnavailable:
            error("Servicio de autenticación no disponible")

        if not authorized:
            self.stop()
            raise IceFlix.Unauthorized()
        self.user_token = user_token


    def stop(self, current = None):
        self.emitter.stop()

class Revocations(IceFlix.Revocations):
    def __init__(self) -> None:
        super().__init__()
    def revokeToken(self, user_token, srv_id, current=None):
        print()
    def revokeUser(self, user, srv_id, current=None):
        print()

class StreamingApp(Ice.Application):
    def __init__(self):
        print()
    def run(self, args):
        return super().run(args)

if __name__ == "__main__":
    APP = StreamingApp()
    sys.exit(APP.main(sys.argv))
