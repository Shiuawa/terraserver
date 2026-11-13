# TerraServer 1.4.5.8

Servidor de Terraria listo para jugar con amigos, sin instalar nada.

## Cómo jugar

1. Abre **app** (Linux) o **app.exe** (Windows).
2. La primera vez, sigue el asistente para conectar playit.gg: inicia sesión,
   abre **New Agent Wizard**, elige **Docker** y pega el bloque SECRET_KEY.
3. Crea o elige un mundo desde la app.
4. Pulsa **Iniciar servidor**.
5. Copia la dirección que aparece y compártela con tus amigos.

## Dónde queda todo

Los mundos, la configuración, el servidor, el agente de playit y el registro
viven dentro de `dependencias/`. La app los gestiona; no hay que editar archivos
ni abrir scripts. La clave de playit se guarda en
`dependencias/playit/secret.toml` y no debe compartirse.

El puerto por defecto es 7778. Si lo cambias, cambia también el túnel de playit.