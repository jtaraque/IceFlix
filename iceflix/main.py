"""Module containing a template for a main service."""

import logging
import uuid
import random
import os
import sys

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

MY_ADMIN_TOKEN = "admin"
APP = None

class Main(IceFlix.Main):
    """Servant for the IceFlix.Main interface.

    Disclaimer: this is demo code, it lacks of most of the needed methods
    for this interface. Use it with caution
    """

    def __init__(self):
        """Create the Main servant instance."""
        self.service_id = str(uuid.uuid4())

    def share_data_with(self, service):
        """Share the current database with an incoming service."""
        service.updateDB(None, self.service_id)

    #Authenticator* getAuthenticator() throws TemporaryUnavailable;
    def getAuthenticator(self, current=None):
        """ Returns a valid authenticator proxy"""
        if len(APP.subscriber.authenticators.keys()) < 1:
            raise IceFlix.TemporaryUnavailable()
        key = random.choice(APP.subscriber.authenticators.keys())
        prx_auth = self.listener.authenticators[key]
        try:
            prx_auth.ice_ping()
            return prx_auth
        except Ice.LocalException:
            raise IceFlix.TemporaryUnavailable()

    # MediaCatalog* getCatalog() throws TemporaryUnavailable;
    def getCatalog(self, current=None):
        """ Returns a valid catalog proxy"""
        if len(APP.subscriber.catalogs.keys()) < 1:
            raise IceFlix.TemporaryUnavailable()
        key = random.choice(APP.subscriber.catalogs.keys())
        prx_catalog = APP.subscriber.catalogs[key]
        try:
            prx_catalog.ice_ping()
            return prx_catalog
        except Ice.LocalException:
            raise IceFlix.TemporaryUnavailable()

    # void updateDB(VolatileServices currentServices, string srvId) throws UnknownService;
    def updateDB(self, values, service_id, current=None):  # pylint: disable=invalid-name,unused-argument
        """Receives the current main service database from a peer."""
        logging.info(
            "Receiving remote data base from %s to %s", service_id, self.service_id
        )

    # bool isAdmin(string adminToken);
    def isAdmin(self, adminToken, current=None):
        """ Returns if a given adminToken is correct"""
        if MY_ADMIN_TOKEN == adminToken:
            return True
        return False

class MainApp(Ice.Application):
    """ Ice.Application for a Main service."""

    def __init__(self):
        super().__init__()
        self.servant = Main()
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
            self.servant, self.servant.service_id, IceFlix.MainPrx
        )

        subscriber_prx = self.adapter.addWithUUID(self.subscriber)
        topic.subscribeAndGetPublisher({}, subscriber_prx)

    def run(self, args):
        """Run the application, adding the needed objects to the adapter."""
        logging.info("Running Main application")
        comm = self.communicator()
        self.adapter = comm.createObjectAdapter("Main")
        self.adapter.activate()

        self.proxy = self.adapter.addWithUUID(self.servant)

        self.setup_announcements()
        self.announcer.start_service()

        self.shutdownOnInterrupt()
        comm.waitForShutdown()

        self.announcer.stop()
        return 0

if __name__ == "__main__":
    APP = MainApp()
    sys.exit(APP.main(sys.argv))
