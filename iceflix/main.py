'''
    Module created to implement the main service
    By: Juan Tomás Araque Martínez
        and Ángel García Collado
'''

from distutils.log import error
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
    # pylint: disable=W0613
    # pylint: disable=R0201
    # pylint: disable=W0702
    """Servant for the IceFlix.Main interface."""

    def __init__(self):
        """Create the Main servant instance."""
        self.service_id = str(uuid.uuid4())

    def share_data_with(self, service):
        """Share the current database with an incoming service."""
        service.updateDB(None, self.service_id)

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

    def updateDB(self, currentServices, service_id, current=None):  # pylint: disable=invalid-name,unused-argument
        """Receives the current main service database from a peer."""
        logging.info(
            "Receiving remote data base from %s to %s", service_id, self.service_id
        )
        if service_id in APP.subscriber.mains.keys():
            for auth in currentServices.authenticators:
                APP.subscriber.authenticators.append(auth)
            for catalog in currentServices.catalogs:
                APP.subscriber.catalogs.append(catalog)

    def isAdmin(self, adminToken, current=None):
        """ Returns if a given adminToken is correct"""
        if MY_ADMIN_TOKEN == adminToken:
            return True
        return False

    # pylint: enable=W0613
    # pylint: enable=R0201
    # pylint: enable=W0702
class MainApp(Ice.Application):
    # pylint: disable=W0221
    # pylint: disable=W0613
    # pylint: disable=R0201
    # pylint: disable=W0702
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

    def check_token(self, args):
        """Check if the given token is the admin one"""
        if len(args) != 3:
            error("Incorrect number of arguments")
            self.announcer.stop()
            raise SystemExit

        admin_token_given = args[1]
        if not self.proxy.isAdmin(admin_token_given):
            error("Admin token given is incorrect")
            self.announcer.stop()
            raise SystemExit

    def run(self, args):
        """Run the application, adding the needed objects to the adapter."""
        logging.info("Running Main application")
        comm = self.communicator()
        self.adapter = comm.createObjectAdapter("Main")
        self.adapter.activate()

        self.proxy = self.adapter.addWithUUID(self.servant)
        print("Main Proxy: " + comm.proxyToString(self.proxy))
        self.check_token(args)
        self.setup_announcements()
        self.announcer.start_service()

        self.shutdownOnInterrupt()
        comm.waitForShutdown()

        self.announcer.stop()
        return 0

    # pylint: enable=W0221
    # pylint: enable=W0613
    # pylint: enable=R0201
    # pylint: enable=W0702
if __name__ == "__main__":
    APP = MainApp()
    sys.exit(APP.main(sys.argv))