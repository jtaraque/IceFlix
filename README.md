# IceFlix

Autores:  
Juan Tomás Araque Martínez  
Ángel García Collado

https://github.com/jtaraque/IceFlix

## Instrucciones de uso

1. Ejecutar run_iceflix.
2. Ejecutar run_client.
3. En la terminal del paso 2, introducir el Proxy obtenido en la terminal del servicio Main. Ej: Main -t -e 1.1:tcp -h 10.0.2.15 -p 32965 -t 60000
4. Responder Y/N en función de si queremos acceder como administrador o como usuario normal. El token de administrador es "admin", mientras que el usuario existente tiene como identificador "angel" y contraseña "angel".
5. Seleccionamos "Iniciar sesión" e introducimos los credenciales del usuario normal.
6. Seleccionamos "Buscar" seleccionamos "por nombre", introducimos "Messi" y a continuación pulsamos "n" para que la búsqueda no sea exacta. 
7. Seleccionamos "Reproducir", seleccionamos el id del medio a reproducir y éste se abrirá en el reproductor de video. Cuando queramos salir es importante que no usemos la "X" de la esquina superior derecha, en lugar de eso volveremos a la terminal y seleccionaremos la opción "Parar reproducción".
8. Para cambiar las tags, en lugar de "Reproducir" seleccionaremos "Editar los tags", volveremos a seleccionar el medio y podremos añadir o eliminar a nuestro gusto.
9. Para editar su nombre, necesitamos iniciar sesión como administrador, seleccionando la opción "Renombrar medio", avanzaremos como en pasos anteriores y seleccionaremos finalmente el nuevo nombre del medio.
