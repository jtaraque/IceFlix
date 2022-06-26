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
import threading

import Ice
import IceStorm
from iceflix.catalog import StreamAnnouncements

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
APP = None
def getTopic(communicator, topic_name):
    topic_manager = IceStorm.TopicManagerPrx.checkedCast(
        communicator.propertyToProxy("IceStorm.TopicManager"),
    )
    try:
        topic = topic_manager.create(topic_name)
    except IceStorm.TopicExists:
        topic = topic_manager.retrieve(topic_name)

    return topic

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

        try:
            user_name = auth_prx.whois(user_token)
        except IceFlix.Unauthorized:
            raise IceFlix.Unauthorized()

        servant_stream_controller = StreamController(user_token)
        stream_controller_prx = current.adapter.addwithUUID(servant_stream_controller)
        stream_controller_prx = IceFlix.StreamControllerPrx.uncheckedCast(stream_controller_prx)

        servant_revocations = Revocations(user_token, user_name, self.servant_serv_announ)
        revocations_topic = getTopic(APP.communicator(), "Revocations")
        revocations_prx = current.adapter.addwithUUID(servant_revocations)
        revocations_topic.subscribeAndGetPublisher({}, revocations_prx)

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
    def __init__(self, user_token, user_name, servant_serv_announ) -> None:
        self.user_token = user_token
        self.user_name = user_name
        self.servant_serv_announ = servant_serv_announ
        self.stream_sync_topic = getTopic(StreamingApp().communicator(), "StreamSync")
        stream_sync_prx = self.stream_sync_topic.getPublisher()
        self.stream_sync_prx = IceFlix.StreamSyncPrx.uncheckedCast(stream_sync_prx)

    def revokeToken(self, user_token, srv_id, current=None):
        if srv_id in self.servant_serv_announ.known_ids:
            if user_token == self.user_token:
                old_token = self.token
                self.stream_sync_prx.requestAuthentication()
                threading.Timer(5.0, None)
                new_token = self.token
                if new_token == old_token:
                    self.stop()

    def revokeUser(self, user, srv_id, current=None):
        if srv_id in self.servant_serv_announ.known_ids:
            if user == self.user_name:
                old_token = self.token
                self.stream_sync_prx.requestAuthentication()
                threading.Timer(5.0, None)
                new_token = self.token
                if new_token == old_token:
                    self.stop()

class StreamingApp(Ice.Application):
    def __init__(self):
        self.adapter = None
        self.servant = StreamProvider()
        self.proxy = None
        self.servant_serv_announcements = None
        self.serv_announcements_sender = None
    def run(self, args):
        broker = self.communicator()
        self.adapter = broker.createObjectAdapter("Streaming")
        self.adapter.activate()

        #Subscriptions
        #Stream Announcements
        stream_announcements_topic = getTopic(broker, "StreamAnnouncements")
        stream_announcements_pub = stream_announcements_topic.getPublisher()
        stream_announcements_pub = IceFlix.StreamAnnouncementsPrx.uncheckedCast(stream_announcements_pub)
        #Service Announcements
        serv_announcements_topics = getTopic(broker, "ServiceAnnouncements")
        self.servant_serv_announcements = ServiceAnnouncementsListener(self.servant,self.servant.service_id, IceFlix.AuthenticatorPrx)
        serv_announcements_prx = self.adapter.addWithUUID(self.servant_serv_announcements)
        serv_announcements_topics.subscribeAndGetPublisher({}, serv_announcements_prx)

        self.proxy = self.adapter.add(self.servant, broker.stringToIdentity("StreamProvider"))
        self.serv_announcements_sender = ServiceAnnouncementsSender(serv_announcements_topics,self.servant.service_id, self.proxy)

        self.servant.servant_serv_announ = self.servant_serv_announcements
        self.servant.stream_announ_prx = stream_announcements_pub
        
        self.shutdownOnInterrupt()
        broker.waitForShutdown()
        return 0



        

if __name__ == "__main__":
    APP = StreamingApp()
    sys.exit(APP.main(sys.argv))
