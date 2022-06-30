"""Module for the service announcements listener and publisher.

You can reuse it in all your services.
"""

import logging
import os
import threading

import Ice

try:
    import IceFlix
except ImportError:
    Ice.loadSlice(os.path.join(os.path.dirname(__file__), "iceflix.ice"))
    import IceFlix

logging.basicConfig(level=logging.INFO)

class ServiceAnnouncementsListener(IceFlix.ServiceAnnouncements):
    """Listener for the ServiceAnnouncements topic."""

    def __init__(self, own_servant, own_service_id, own_type):
        """Initialize a ServiceAnnouncements topic listener.

        The `own_servant` argument should be the service servant object, that is
        expected to have a `share_data_with` method. That method should receive
        the proxy of the new announced service and is expected that it invokes
        remotely the `updateDB` method with the appropriate values.

        The `own_service_id` argument should be a string with an unique
        identifier. It should be the same used to announce this service.

        The `own_type` argument should be a class reference for the type of the
        `own_servant`. For example, IceFlix.MainPrx.
        """
        self.servant = own_servant
        self.service_id = own_service_id
        self.own_type = own_type

        self.authenticators = {}
        self.catalogs = {}
        self.mains = {}
        self.providers = {}
        self.known_ids = set()

    def newService(
        self, service, service_id, current
    ):  # pylint: disable=invalid-name,unused-argument
        """Receive the announcement of a new started service."""
        if service_id == self.service_id:
            logging.debug("Received own announcement. Ignoring")
            return
        if self.own_type == IceFlix.StreamProviderPrx and service.ice_isA("::IceFlix::MediaCatalog"):
            self.servant.reannounceMedia(service_id)
        proxy = self.own_type.checkedCast(service)
        if proxy:
            self.servant.share_data_with(proxy)

    def announce(self, service, service_id, current):  # pylint: disable=unused-argument
        """Receive an announcement."""
        # self.checkServices()
        if service_id == self.service_id or service_id in self.known_ids:
            logging.debug("Received own announcement or already known. Ignoring")
            return

        if service.ice_isA("::IceFlix::Main"):
            logging.debug("Main service received")
            self.mains[service_id] = IceFlix.MainPrx.uncheckedCast(service)
            self.known_ids.add(service_id)

        elif service.ice_isA("::IceFlix::Authenticator"):
            logging.debug("Authenticator service received")
            self.authenticators[service_id] = IceFlix.AuthenticatorPrx.uncheckedCast(
                service
            )
            self.known_ids.add(service_id)

        elif service.ice_isA("::IceFlix::MediaCatalog"):
            logging.debug("MediaCatalog service received")
            self.catalogs[service_id] = IceFlix.MediaCatalogPrx.uncheckedCast(service)
            self.known_ids.add(service_id)

        elif service.ice_isA("::IceFlix::StreamProvider"):
            logging.debug("StreamProvider service received")
            self.providers[service_id] = IceFlix.StreamProviderPrx.uncheckedCast(service)
            self.known_ids.add(service_id)

        else:
            logging.info(
                "Received annoucement from unknown service %s: %s",
                service_id,
                service.ice_ids(),
            )
    def checkServices(self):
        for main in self.mains.keys():
            try:
                self.mains[main].ice_ping()
            except Ice.LocalException:
                del self.mains[main]
                self.known_ids.remove(main)

        for auth in self.authenticators.keys():
            try:
                self.authenticators[auth].ice_ping()
            except Ice.LocalException:
                del self.authenticators[auth]
                self.known_ids.remove(auth)

        for catalog in self.catalogs.keys():
            try:
                self.catalogs[catalog].ice_ping()
            except Ice.LocalException:
                del self.catalogs[catalog]
                self.known_ids.remove(catalog)

        for provider in self.providers.keys():
            try:
                self.providers[provider].ice_ping()
            except Ice.LocalException:
                del self.providers[provider]
                self.known_ids.remove(provider)


class ServiceAnnouncementsSender:
    """The instances send the announcement events periodically to the topic."""

    def __init__(self, topic, service_id, servant_proxy):
        """Initialize a ServiceAnnoucentsSender.
        
        The `topic` argument should be a IceStorm.TopicPrx object.
        The `service_id` should be the unique identifier of the announced proxy
        The `servant_proxy` should be a object proxy to the servant.
        """
        self.publisher = IceFlix.ServiceAnnouncementsPrx.uncheckedCast(
            topic.getPublisher(),
        )
        self.service_id = service_id
        self.proxy = servant_proxy
        self.timer = None

    def start_service(self):
        """Start sending the initial announcement."""
        self.publisher.newService(self.proxy, self.service_id)
        self.timer = threading.Timer(3.0, self.announce)
        self.timer.start()

    def announce(self):
        """Start sending the announcements."""
        self.timer = None
        self.publisher.announce(self.proxy, self.service_id)
        self.timer = threading.Timer(10.0, self.announce)
        self.timer.daemon = True
        self.timer.start()

    def stop(self):
        """Stop sending the announcements."""
        if self.timer:
            self.timer.cancel()
            self.timer = None