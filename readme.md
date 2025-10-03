# MercadoLibre Selenium

Este repositorio contiene un script en **Python + Selenium** que automatiza una búsqueda en MercadoLibre (https://www.mercadolibre.com) y realiza los pasos solicitados: seleccionar país, buscar "playstation 5", filtrar por `Nuevo`, aplicar un código postal, ordenar por precio y obtener los primeros 5 productos (nombre y precio).

## Estructura del proyecto

mercadolibre-scraper/
├── scraper.py       # Script principal (Selenium)
├── requirements.txt # Dependencias
└── README.md        # Este archivo

## Requisitos previos

- Python 3.8 o superior
- Google Chrome instalado (o el navegador que prefieras y su driver correspondiente)
- Git (opcional, para subir a GitHub)

**Consejo:** Usa `webdriver-manager` para evitar descargar `chromedriver` manualmente.

## Instalación paso a paso (Windows / Mac / Linux)

1. Clona el repositorio (o crea una carpeta y pega los archivos)

```bash
git clone https://github.com/tuusuario/mercadolibre-scraper.git
cd mercadolibre-scraper
```

2. Crea y activa un entorno virtual (recomendado)

- En Windows (PowerShell):

   powershell
python -m venv venv
venv\Scripts\Activate.ps1


- En Windows (CMD):

```cmd
python -m venv venv
venv\Scripts\activate
```

3. Instala las dependencias

```bash
pip install -r requirements.txt
```

Contenido sugerido para `requirements.txt`:

```
selenium==4.23.1
webdriver-manager==3.8.6
```

(Usa la versión más reciente)


## Configurar ChromeDriver

1. Abre Chrome → `Configuración` → `Ayuda` → `Información de Google Chrome` y anota la versión.
2. Descarga el `chromedriver` correspondiente desde: https://chromedriver.chromium.org/downloads
3. Descomprime y coloca `chromedriver` en una carpeta incluida en tu `PATH`, o guarda la ruta y pásala al script.

## Ejecutar el scraper

Desde la carpeta del proyecto (y con el entorno virtual activado):

   bash
python scraper.py


El script abrirá Chrome, ejecutará los pasos y mostrará en consola los primeros 5 productos con su precio.

## Ejemplo de uso con `webdriver-manager` (en `scraper.py`)

```python
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
```

Esto evita que tengas que descargar `chromedriver` manualmente.

---
