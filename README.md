# War Thunder Tech Tree Scraper

A Python scraper that collects vehicle research tree data from the official War Thunder Wiki. It is designed to populate a database, managed in a [separate repository](https://github.com/Muxomor/WTExpCalc_db), for a [research calculator project](https://github.com/Muxomor/WTExpCalc). The scraper also integrates supplementary data from the [gszabi99 War Thunder Datamine project](https://github.com/gszabi99/War-Thunder-Datamine).

**Note:** The project is not maintained and lacks support for modern game mechanics such as "slave units" (e.g., IRIS-T, Buk-M3).

-----

## Technology Stack

  * **Python 3**
  * **Selenium WebDriver**
  * **BeautifulSoup4**
  * **PostgreSQL** with a **PostgREST** API layer

-----

## Installation and Usage

**Prerequisites:** Python 3, Mozilla Firefox, and a running [PostgreSQL/PostgREST instance](https://github.com/Muxomor/WTExpCalc_db).

1.  Clone the repository and install dependencies:
    ```bash
    pip install selenium requests beautifulsoup4 pyjwt
    ```
2.  Download the [GeckoDriver](https://github.com/mozilla/geckodriver/releases) corresponding to your Firefox version.
3.  Create a `config.txt` file and provide your API credentials and the absolute path to the GeckoDriver executable.
4.  Run the script(you may also need to modify code):
    ```bash
    python main.py
    ```