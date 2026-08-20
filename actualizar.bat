@echo off
echo Iniciando actualizacion automatica de arriendos...
cd /d "D:\Computador Maf E\Escritorio\Arriendos cali"
python scraper.py
python normalizador.py
echo ¡Actualizacion finalizada con exito!