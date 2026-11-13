@echo off
rem Configuracion del servidor portatil (Windows)
set "WORLD_NAME=mundo"
set "PORT=7778"
set "PLAYERS=8"
set "PASSWORD="
set "AUTOCREATE=1"
if not "%PASSWORD%"=="" set "PASSWORDARG=-password %PASSWORD%"
