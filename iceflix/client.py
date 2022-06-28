'''
    Module created to implement the client
    By: Juan Tomás Araque Martínez
        and Ángel García Collado
'''

from distutils.log import error
import logging
import os
import sys
import time
import getpass
import hashlib

import Ice
import IceStorm

from rtsputils import(
    RTSPPlayer
)

try:
    import IceFlix
except ImportError:
    Ice.loadSlice(os.path.join(os.path.dirname(__file__), "iceflix.ice"))
    import IceFlix

RECONNECTION_ATTEMPTS = 3

def getTopic(communicator, topic_name):
    topic_manager = IceStorm.TopicManagerPrx.checkedCast(
        communicator.propertyToProxy("IceStorm.TopicManager"),
    )
    try:
        topic = topic_manager.create(topic_name)
    except IceStorm.TopicExists:
        topic = topic_manager.retrieve(topic_name)

    return topic

class StreamSync(IceFlix.StreamSync):
    def __init__(self, stream_controller_prx, client) -> None:
        self.stream_controller_prx = stream_controller_prx
        self.client = client
    def requestAuthentication(self, current=None):
        try:
            self.stream_controller_prx.refreshAuthentication(self.client.user["token"])
        except IceFlix.Unauthorized:
            error("Token incorrecto")

class Revocations(IceFlix.Revocations):
    def __init__(self, client) -> None:
        self.client = client
    def revokeToken(self, userToken, srvId, current=None):
        if self.client.user["token"] == userToken:
            try:
                auth_prx = self.client_main_prx.getAuthenticator()
                self.client.user["token"] = auth_prx.refreshAuthentication(
                    self.client.user["user"], self.client.user["pass_encoded"])
            except IceFlix.TemporaryUnavailable:
                error("Servicio de autenticación no disponible")
            except IceFlix.Unauthorized:
                error("Los datos de usuario no son correctos")

class MediaUploader(IceFlix.MediaUploader):
    print()
class ClientApp(Ice.Application):

    def __init__(self):
        self.broker = None
        self.adapter = None
        self.main_prx = None
        self.admin_token = None
        self.user = {}
        self.player = None
        self.stream_controller_prx = None

    def play(self, media):
        stream_provider_prx = media.provider
        stream_controller_prx = stream_provider_prx.getStream(
            media.mediaId, self.user["token"])
        uri = stream_controller_prx.getSDP(self.user["token"], 8080)
        servant_stream_sync = StreamSync(stream_controller_prx, self)
        sync_topic = self.getTopic(
            self.broker, "StreamSync")
        sync_prx = self.adapter.addWithUUID(servant_stream_sync)
        sync_prx = IceFlix.RevocationsPrx.uncheckedCast(sync_prx)
        sync_topic.subscribeAndGetPublisher({}, sync_prx)
        logging.info(uri)
        self.player = RTSPPlayer()
        self.player.play(uri)

    def edit_tags(self, catalog_prx, media):
        election = self.numQuestion(
            "¿Qué quiere hacer?\n1. Añadir tags\n2. Eliminar tags\n", list(range(1, 3)))
        if election == 1:
            new_tags = input("Introduzca los nuevo tags: ")
            new_tags_list = new_tags.split(", ")
            try:
                catalog_prx.addTags(media.mediaId, new_tags_list, self.user["token"])
            except IceFlix.Unauthorized:
                error("Token de usuario no válido")
            except IceFlix.WrongMediaId:
                error("Id del medio no válido")
            except Ice.LocalException:
                error("Servicio de catálogo no disponible")
        elif election == 2:
            remove_tags = input("Introduzca los tags a eliminar: ")
            remove_tags_list = remove_tags.split(", ")
            try:
                catalog_prx.removeTags(media.mediaId, remove_tags_list, self.user["token"])
            except IceFlix.Unauthorized:
                error("Token de usuario no válido")
            except IceFlix.WrongMediaId:
                error("Id del medio no válido")
            except Ice.LocalException:
                error("Servicio de catálogo no disponible")

    def show_media(self, medias):
        counter = 0
        for media in medias:
            print(str(counter) + ": " + media.info.name + ". Tags: " + str(media.info.tags))
            counter += 1

    def search_by_id(self, catalog_prx, ids_media):
        media = []
        try:
            for id in ids_media:
                media.append(catalog_prx.getTile(id, self.user["token"]))
            return media
        except IceFlix.WrongMediaId:
            error("El id del medio no es correcto")
        except IceFlix.TemporaryUnavailable:
            error("El servicio de catálogo o algún medio no están disponibles")
        except IceFlix.Unauthorized:
            error("El token de usuario no es correcto")
        except Ice.LocalException:
            error("Servicio de catálogo no disponible")

    def search_by_tile(self, catalog_prx):
        media = []
        tile = input("Introduce el título del medio: ")
        exact = self.yesnoQuestion("¿Quiere que la búsqueda sea exacta? [y/n]: ")
        try:
            ids_media = catalog_prx.getTilesByName(tile, exact)
        except Ice.LocalException:
            error("Servicio de catálogo no disponible")
        if len(ids_media) == 0:
            logging.info("No se ha encontrado ningún medio con ese nombre")
        else:
            media = self.search_by_id(catalog_prx, ids_media)
        return media

    def search_by_tags(self, catalog_prx):
        media = []
        tags = input("Introduzca los tags de búsqueda: ")
        tags_list = tags.split(", ")
        include_all_tags = self.yesnoQuestion("¿Quiere que el medio contenga todos los tags? [y/n]")
        try:
            ids_media = catalog_prx.getTilesByTags(tags_list, include_all_tags, self.user["toker"])
        except IceFlix.Unauthorized:
            error("Token de usuario incorrecto")
        except Ice.LocalException:
            error("Servicio de catálogo no disponible")

        if len(ids_media) == 0:
            logging.info("No se ha encontrado ningún medio con ese nombre")
        else:
            media = self.search_by_id(catalog_prx, ids_media)
        return media

    def numQuestion(self, msg, range):
        num = input(msg)
        while True:
            if not num.isdigit():
                num = input("Introduzca un número\n")
            if num not in range:
                num = input("Introduzca un valor válido\n")
            if num.isdigit() and num in range:
                break
        return int(num)

    def admin1(self):
        print()
    def admin2(self):
        print()
    def admin3(self):
        print()
    def admin4(self):
        print()
    def admin5(self):
        print()
    def opcion1(self):
        """Method to login the user"""
        user = input("Usuario: ")
        password = getpass.getpass("Contraseña: ")
        pass_encoded = hashlib.sha256(password.encode()).hexdigest()

        try:
            auth_prx = self.main_prx.getAuthenticator()
            self.user["token"] = auth_prx.refreshAuthentication(user, pass_encoded)
            if self.user["token"]:
                logging.info("Se ha iniciado sesión con éxito")
                self.user["user"] = user
                self.user["pass_encoded"] = pass_encoded

                servant_revocations = Revocations(self)
                revocations_topic = getTopic(self.broker, "Revocations")
                revocations_prx = self.adapter.addWithUUID(servant_revocations)
                revocations_prx = IceFlix.RevocationsPrx.uncheckedCast(revocations_prx)
                revocations_topic.subscribeAndGetPublisher({}, revocations_prx)

        except IceFlix.TemporaryUnavailable:
            error("Servicio de autenticación no disponible")
        except IceFlix.Unauthorized:
            error("Los datos de usuario no son correctos")
        except:
            error("Error al conectar con el servidor principal")
            self.main_prx = self.reconnect(self.main_prx)
            if not self.main_prx:
                error("No se pudo conectar con el servidor principal")
                raise SystemExit
    def opcion2(self):
        try:
            catalog_prx = self.main_prx.getCatalog()
            if self.user["token"]:
                type_search = self.numQuestion(
                    "¿Qué búsqueda desea realizar?\n1. Por nombre\n2. Por tags\n",
                    list(range(1, 3)))
                if type_search == 1:
                    media = self.search_by_tile(catalog_prx)
                else:
                    media = self.search_by_tags(catalog_prx)
            else:
                media = self.search_by_tile(catalog_prx)
            if len(media) > 0:
                self.show_media(media)
                if self.user["token"]:
                    election = self.numQuestion(
                        "¿Qué desea hacer?\n1. Editar los tags\n2. Reproducir\n3. Nada\n",
                        list(range(1, 4)))
                    if election == 1:
                        media_election = self.numQuestion(
                            "Seleccione el medio del que quiere editar sus tags\n",
                            list(range(len(media))))
                        self.edit_tags(catalog_prx, media[media_election])
                    elif election == 2:
                        media_election = self.numQuestion(
                            "Seleccione el medio que quiere reproducir\n",
                            list(range(len(media))))
                        self.play(media[media_election])
        except IceFlix.WrongMediaId:
            logging.error("El id del medio proporcionado no es correcto")
        except IceFlix.Unauthorized:
            logging.error("El token de autenticación proporcionado no es válido")
        except IceFlix.TemporaryUnavailable:
            logging.error("Servicio de catálogo no disponible. Inténtelo más tarde")
        except Ice.NotRegisteredException:
            error("Error al conectar con el servidor principal")
            self.main_prx = self.reconnect(self.main_prx)
            if not self.main_prx:
                error("No se pudo conectar con el servidor principal")
                raise SystemExit

    def opcion3(self):
        """Method to change the reconnection configuration"""
        attempts = self.numQuestion(
                        "Introduzca el número de intentos de reconexión con el servidor principal (max 10): ",
                        str(list(range(10))))
        RECONNECTION_ATTEMPTS = attempts
        print(
            "El número de intentos de reconexión se ha establecido a "+str(RECONNECTION_ATTEMPTS))

    def opcion4(self):
        """Method to sign out"""
        logging.info("Va a cerrar sesión")
        self.user["token"] = None
        self.user["user"] = None
        self.user["pass_encoded"] = None
    def opcion5(self):
        if not self.player:
            logging.info("No hay ninguna reproducción en curso")
        else:
            self.player.stop()
            self.player = None
            try:
                self.stream_controller_prx.stop()
            except Ice.LocalException:
                error("Error de conexión con el servidor de StreamController")
            logging.info("Reproducción pausada")

    def reconnect(self, main_prx):
        logging.info("Intentado reconectar con el servicio principal")
        attempts = 0
        main_prx_new = None
        while not main_prx_new and (attempts < RECONNECTION_ATTEMPTS):
            time.sleep(5.0)
            try:
                main_prx_new = IceFlix.MainPrx.uncheckedCast(main_prx)
            except Exception:
                error(f"Error en el intento de reconexión. {attempts}/{RECONNECTION_ATTEMPTS}")
            i += 1
        return main_prx_new

    def connectToMain(self):
        main_prx = input("Para comenzar introduzca un  proxy del servicio principal")
        main_prx = self.broker.stringToProxy(main_prx)
        try:
            self.main_prx = IceFlix.MainPrx.unchekedCast(main_prx)
        except:
            error("Error al conectar con el servidor principal")
            self.main_prx = self.reconnect(self.main_prx)
            if not self.main_prx:
                error("No se pudo conectar con el servidor principal")
                raise SystemExit

    def yesnoQuestion(self, msg):
        while True:
            yn_answer = input(msg)
            if not yn_answer in ['y', 'n']:
                error("Valor no válido. [y/n]")
            elif yn_answer == 'y':
                return True
            else:
                return False

    def getAdminToken(self):
        admin_token = getpass.getpass("Token de administración: ")
        try:
            is_admin = self.main_prx.isAdmin(admin_token)
        except Exception:
            error("Error al conectar con el servidor principal")
            self.main_prx = self.reconnect(self.main_prx)
            if not self.main_prx:
                error("No se pudo conectar con el servidor principal")
                raise SystemExit

        if not is_admin:
            error("Token de administración incorrecto")
            raise SystemExit
        self.admin_token = admin_token

    def printAdminMenu(self):
        print("\nSeleccione una de las siguientes opciones:")
        print("1. Añadir usuario")
        print("2. Eliminar usuario")
        print("3. Renombrar medio")
        print("4. Añadir medio")
        print("5. Eliminar medio")
        print("6. Salir")
        opcion = input("Opción: ")
        print()
        if not opcion.isdigit() or int(opcion) not in range(1, 7):
            raise ValueError
        return int(opcion)

    def printMenu(self):
        print("\nSeleccione una de las siguientes opciones:")
        print("1. Iniciar sesión")
        print("2. Buscar en catálogo")
        print("3. Cambiar configuración de conexión con el servidor")
        print("4. Cerrar sesión")
        print("5. Parar reproducción")
        print("6. Salir")
        opcion = input("Opción: ")
        print()
        if not opcion.isdigit() or int(opcion) not in range(1, 7):
            raise ValueError
        return int(opcion)

    def adminMenu(self):
        #Token
        self.getAdminToken()
        #Menu
        opcion = 0
        while opcion != 6:
            opcion = self.printAdminMenu()
            if opcion == 1:
                self.admin1()
            elif opcion == 2:
                self.admin2()
            elif opcion == 3:
                self.admin3()
            elif opcion == 4:
                self.admin4()
            else:
                self.admin5()

    def normalMenu(self):
        opcion = 0
        while opcion != 6:
            opcion = self.printMenu()
            if opcion == 1:
                self.opcion1()
            elif opcion == 2:
                self.opcion2()
            elif opcion == 3:
                self.opcion3()
            elif opcion == 4:
                self.opcion4()
            else:
                self.opcion5()

    def run(self, args):
        print("Bienvenid@ al servicio IceFlix")

        self.broker = self.communicator()
        self.adapter = self.broker.createObjectAdapter("Client")

        self.connectToMain()
        admin = self.yesnoQuestion("¿Desea iniciar como administrador?[y/n]")
        if admin:
            self.adminMenu()
        else:
            self.normalMenu()
        logging.info("Gracias por usar nuestro servicio")
        return 0

if __name__ == '__main__':
    APP = ClientApp()
    sys.exit(APP.main(sys.argv))