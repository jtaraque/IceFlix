'''
    Module created to implement the Streaming service
    By: Juan Tomás Araque Martínez
        and Ángel García Collado
'''

# pylint: disable=C0103
# pylint: disable=W0613
# pylint: disable=E1101
# pylint: disable=W0707

from distutils.log import error
from time import sleep
import logging
import uuid
import random
import os
import sys
import string
import hashlib
import threading
import time

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
    RTSPEmitter
)

CHUNK_SIZE = 10
APP = None
def getTopic(communicator, topic_name):
    """Method to create streaming topic."""
    topic_manager = IceStorm.TopicManagerPrx.checkedCast(
        communicator.propertyToProxy("IceStorm.TopicManager"),
    )
    try:
        topic = topic_manager.create(topic_name)
    except IceStorm.TopicExists:
        topic = topic_manager.retrieve(topic_name)

    return topic

class StreamProvider(IceFlix.StreamProvider):
    """Class used to get stream information."""
    def __init__(self) -> None:
        self.service_id = str(uuid.uuid4())
        self.media_available = {}
        self.servant_serv_announ = None
        self.stream_announ_prx = None
    def share_data_with(self, service):
        """Share the current database with an incoming service."""
        service.updateDB(None, self.service_id)

    def readMedia(self):
        """Method to read the system media."""
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
                self.media_available[media_id] = media_name
            except StopIteration:
                break
            except Exception:
                error("Error durante el anunciamento de medios")

    def getStream(self, media_id, user_token, current=None):
        """Used to get the stream."""
        #Get authenticator
        authorized = False
        main_prx = random.choice(list(self.servant_serv_announ.mains.values()))
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
        media_path = "./media/"+self.media_available[media_id]+".mp4"
        servant_stream_controller = StreamController(user_token, main_prx, media_path)
        stream_controller_prx = current.adapter.addWithUUID(servant_stream_controller)
        stream_controller_prx = IceFlix.StreamControllerPrx.uncheckedCast(stream_controller_prx)

        servant_revocations = Revocations(user_token, user_name, self.servant_serv_announ)
        revocations_topic = getTopic(APP.communicator(), "Revocations")
        revocations_prx = current.adapter.addWithUUID(servant_revocations)
        revocations_topic.subscribeAndGetPublisher({}, revocations_prx)

        return stream_controller_prx

    def isAvailable(self, media_id, current=None):
        """Check if media is available."""
        if media_id in self.media_available.keys():
            return True
        return False

    def reannounceMedia(self, srv_id, current=None):
        """Method to reannounce the media to the client."""
        if not srv_id in self.servant_serv_announ.known_ids:
            raise IceFlix.UnknownService()
        self.readMedia()

    def uploadMedia(self, file_name, uploader, admin_token, current=None):
        """Method to upload new media."""
        logging.info(f"Receiving medio {file_name}")
        is_admin = False
        main_prx = random.choice(list(self.servant_serv_announ.mains.values()))
        try:
            is_admin = main_prx.isAdmin(admin_token)
        except Ice.LocalException:
            error("Servicio principal no disponible")
        if not is_admin:
            raise IceFlix.Unauthorized()
        media_title = file_name.split("/")[-1]
        media_size = os.path.getsize(file_name)
        media_path = "./media/"+media_title

        if not os.path.exists(media_path):
            file_bytes = bytes()
            with open(media_path, "wb") as file:
                while True:
                    try:
                        chunk = uploader.receive(CHUNK_SIZE)
                        file.write(chunk)
                        file_bytes += chunk
                        if len(file_bytes) >= media_size:
                            uploader.close()
                            break
                    except Exception:
                        raise IceFlix.UploadError()
            media_id = hashlib.sha256(str(file_bytes).encode()).hexdigest()
            media_name = media_title.split(".")[0]
            self.stream_announ_prx.newMedia(media_id, media_name, self.service_id)
            self.media_available[media_id] = media_name
            return media_id

    def deleteMedia(self, media_id, admin_token, current=None):
        """Method to delete media."""
        is_admin = False
        main_prx = random.choice(list(self.servant_serv_announ.mains.values()))
        try:
            is_admin = main_prx.isAdmin(admin_token)
        except Ice.LocalException:
            error("Servicio principal no disponible")
        if not is_admin:
            raise IceFlix.Unauthorized()
        del self.media_available[media_id]
        self.stream_announ_prx.removedMedia(media_id, self.service_id)

class StreamController(IceFlix.StreamController):
    """Class used to control the stream player."""
    def __init__(self, user_token, main_prx, media) -> None:
        self.emitter = None
        self.media = media
        self.main_prx = main_prx
        self.user_token = user_token

    def getSDP(self, user_token, port, current=None):
        """Used to start the RTSP."""
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

    def getSyncTopic(self, current=None):
        """Method that syncs to the topic."""
        length = 10
        topic = ''.join(random.SystemRandom().choice(
            string.ascii_letters + string.digits) for _ in range(length))
        return topic

    def refreshAuthentication(self, user_token, current=None):
        """Method to authenticate."""
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

    def stop(self, current=None):
        """Method to stop the current playing media"""
        self.emitter.stop()

class Revocations(IceFlix.Revocations):
    """Used to revoke users and tokens."""
    def __init__(self, user_token, user_name, servant_serv_announ) -> None:
        self.user_token = user_token
        self.user_name = user_name
        self.servant_serv_announ = servant_serv_announ
        self.stream_sync_topic = getTopic(StreamingApp().communicator(), "StreamSync")
        stream_sync_prx = self.stream_sync_topic.getPublisher()
        self.stream_sync_prx = IceFlix.StreamSyncPrx.uncheckedCast(stream_sync_prx)

    def revokeToken(self, user_token, srv_id, current=None):
        """Method to revoke token."""
        if srv_id in self.servant_serv_announ.known_ids:
            if user_token == self.user_token:
                old_token = self.user_token
                self.stream_sync_prx.requestAuthentication()
                threading.Timer(5.0, None)
                new_token = self.user_token
                if new_token == old_token:
                    self.stream_sync_prx.stop()

    def revokeUser(self, user, srv_id, current=None):
        """Method to revoke user."""
        if srv_id in self.servant_serv_announ.known_ids:
            if user == self.user_name:
                old_token = self.user_token
                self.stream_sync_prx.requestAuthentication()
                threading.Timer(5.0, None)
                new_token = self.user_token
                if new_token == old_token:
                    self.stream_sync_prx.stop()

class StreamingApp(Ice.Application):
    """Streaming app init."""
    def __init__(self):
        self.adapter = None
        self.servant = StreamProvider()
        self.proxy = None
        self.subscriber = None
        self.announcer = None
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
            self.servant, self.servant.service_id, IceFlix.StreamProviderPrx
        )

        subscriber_prx = self.adapter.addWithUUID(self.subscriber)
        topic.subscribeAndGetPublisher({}, subscriber_prx)
    def run(self, args):
        """Streaming class initialization."""
        broker = self.communicator()
        self.adapter = broker.createObjectAdapter("Streaming")
        self.adapter.activate()

        #Subscriptions
        #Stream Announcements
        stream_announcements_topic = getTopic(broker, "StreamAnnouncements")
        stream_announcements_pub = stream_announcements_topic.getPublisher()
        stream_announcements_pub = IceFlix.StreamAnnouncementsPrx.uncheckedCast(
            stream_announcements_pub)
        #Service Announcements
        self.proxy = self.adapter.add(self.servant, broker.stringToIdentity("StreamProvider"))
        self.setup_announcements()
        self.announcer.start_service

        self.servant.servant_serv_announ = self.subscriber
        self.servant.stream_announ_prx = stream_announcements_pub

        time.sleep(2)
        self.announcer.announce()
        self.servant.readMedia()
        logging.info(self.proxy)

        self.shutdownOnInterrupt()
        broker.waitForShutdown()
        return 0





if __name__ == "__main__":
    APP = StreamingApp()
    sys.exit(APP.main(sys.argv))
