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

import Ice
import IceStorm

try:
    import IceFlix
except ImportError:
    Ice.loadSlice(os.path.join(os.path.dirname(__file__), "iceflix.ice"))
    import IceFlix

RECONNECTION_ATTEMPTS = 3

class MediaUploader(IceFlix.MediaUploader):
    print()
class ClientApp(Ice.Application):

    def __init__(self):
        self.broker = None
        self.adapter = None
        self.main_prx = None
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
            i+=1
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
        return admin_token

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
        admin_token = self.getAdminToken()
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