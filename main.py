import base64
import os
from fastapi import FastAPI, Request, HTTPException, Query, Path
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from requests import get
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
VERSION = "1.0.0"
isDev = os.getenv("NODE_ENV") == "development"
COMMUNITY_VERSION = os.getenv("IS_COMMUNITY_VERSION") == "true"
SPONSOR_MESSAGE = os.getenv("SPONSOR_MESSAGE")
ADDON_ID = os.getenv("ADDON_ID") if os.getenv("ADDON_ID") else "community.aymene69.akwam"
RGX_QUALITY_TAG = r'tab-content quality.*?a href="(https?://\w*\.*\w+\.\w+/link/\d+)"'
RGX_SIZE_TAG = r'font-size-14 mr-auto">([0-9.MGB ]+)</'
HTTP = 'https://'

templates = Jinja2Templates(directory="templates")

manifest_data = {
    "id": ADDON_ID,
    "icon": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTAr_UMfGGxBCd0GKqqW77SMWbYM2nOWPoIwA&s",
    "version": VERSION,
    "catalogs": [
        {
            "type": "Akwam Movies",
            "id": "movie",
            "name": "Akwam Movies",
            "genres": ["رمضان", "أكشن", "كوميدي", "دراما", "رومانسي", "رعب", "خيال علمي", "فانتازيا", "مغامرة", "جريمة", "تاريخي", "وثائقي", "حربي", "رياضي", "عائلي", "موسيقى", "سيرة ذاتية", "مدبلج", "NETFLIX", "أطفال", "قصير"]
        },
        {
            "type": "Akwam Series",
            "id": "series",
            "name": "Akwam Series",
            "genres": ["رمضان", "أكشن", "كوميدي", "دراما", "رومانسي", "رعب", "خيال علمي", "فانتازيا", "مغامرة", "جريمة", "تاريخي", "وثائقي", "حربي", "رياضي", "عائلي", "موسيقى", "سيرة ذاتية", "مدبلج", "NETFLIX", "أطفال", "قصير"]
        }
    ],
    "resources": ["stream", "catalog", "meta"],
    "types": ["movie", "series"],
    "name": "Akwam",
    "description": "Elevate your Stremio experience with seamless access to Akwam links, effortlessly",
    "behaviorHints": {
        "configurable": True,
    }
}

def get_genres(content_type):
    """Returns genres for a specific content type."""
    genres = {
        'movie': [
            ("أكشن", 18), ("كوميدي", 20), ("دراما", 23), ("رومانسي", 27),
            ("رعب", 22), ("خيال علمي", 24), ("فانتازيا", 43), ("مغامرة", 19),
            ("جريمة", 21), ("تاريخي", 26), ("وثائقي", 28), ("حربي", 25),
            ("رياضي", 32), ("عائلي", 33), ("موسيقى", 31), ("سيرة ذاتية", 29),
            ("مدبلج", 71), ("NETFLIX", 72), ("أطفال", 88), ("قصير", 89), ("رمضان", 87)
        ],
        'series': [
            ("أكشن", 18), ("كوميدي", 20), ("دراما", 23), ("رومانسي", 27),
            ("رعب", 22), ("خيال علمي", 24), ("فانتازيا", 43), ("مغامرة", 19),
            ("جريمة", 21), ("تاريخي", 26), ("وثائقي", 28), ("حربي", 25),
            ("رياضي", 32), ("عائلي", 33), ("موسيقى", 31), ("سيرة ذاتية", 29),
            ("مدبلج", 71), ("NETFLIX", 72), ("أطفال", 88), ("قصير", 89), ("رمضان", 87)
        ]
    }
    return genres.get(content_type, [])

def extract_season_episode(title):
    match = re.search(r'Saison (\d+) Épisode (\d+)', title)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1, 1


def fetch_entries_by_genre(url):
    """Gather entries for a specific genre."""
    response = get(url)
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    entries = []

    widget_body = soup.find('div', class_='widget-body row flex-wrap')
    if not widget_body:
        return []

    for item in widget_body.find_all('div', class_='col-lg-auto col-md-4 col-6 mb-12'):
        entry_box = item.find('div', class_='entry-box')
        if not entry_box:
            continue

        title_elem = entry_box.find('h3', class_='entry-title')
        title = title_elem.text.strip() if title_elem else 'No Title'

        link_elem = entry_box.find('a', class_='box')
        link = link_elem['href'] if link_elem else '#'

        thumb_elem = entry_box.find('img', class_='img-fluid w-100 lazy')
        thumb = thumb_elem['data-src'] if thumb_elem and thumb_elem.has_attr('data-src') else thumb_elem['src'] if thumb_elem else ''

        year_elem = entry_box.find('span', class_='badge badge-pill badge-secondary')
        year = year_elem.text.strip() if year_elem else 'N/A'

        tags = []
        for tag_elem in entry_box.find_all('span', class_='badge badge-pill badge-light'):
            tags.append(tag_elem.text.strip())

        entries.append((title, link, thumb, year, tags))

    return entries

def fetch_entries_for_page(url, page):
    """Fetch entries for a specific page."""
    page_url = f"{url}&page={page}"
    return fetch_entries_by_genre(page_url)

class Akwam:
    def __init__(self, url):
        url = get(url).url
        self.url = [url, url[:-1]][url[-1] == '/']
        self.search_url = self.url + '/search?q='
        self.cur_page = None
        self.qualities = {}
        self.results = None
        self.parsed = None
        self.dl_url = None
        self.type = 'movie'

    def parse(self, regex, no_multi_line=False):
        page = self.cur_page.content.decode()
        if no_multi_line:
            page = page.replace('\n', '')
        self.parsed = re.findall(regex, page)

    def search(self, query, page=1):
        query = query.replace(' ', '+')
        self.cur_page = get(f'{self.search_url}{query}&section={self.type}&page={page}')
        self.parse(rf'({self.url}/{self.type}/\d+/.*?)"')
        self.results = {
            url.split('/')[-1].replace('-', ' ').title(): url for url in self.parsed[::-1]
        }

    def load(self):
        self.cur_page = get(self.cur_url)
        self.parse(RGX_QUALITY_TAG, no_multi_line=True)
        i = 0
        for q in ['1080p', '720p', '480p']:
            if f'>{q}</' in self.cur_page.text:
                self.qualities[q] = self.parsed[i]
                i += 1

    def get_direct_url(self, quality='720p'):
        try:
            quality_url = self.qualities[quality]
            if not quality_url.startswith(('http://', 'https://')):
                quality_url = HTTP + quality_url

            self.cur_page = get(quality_url)
            self.parse(r'https?://(\w*\.*\w+\.\w+/download/.*?)"')

            download_url = self.parsed[0]
            if not download_url.startswith(('http://', 'https://')):
                download_url = HTTP + download_url

            self.cur_page = get(download_url)
            self.parse(r'([a-z0-9]{4,}\.\w+\.\w+/download/.*?)"')

            final_url = self.parsed[0]
            if not final_url.startswith(('http://', 'https://')):
                final_url = HTTP + final_url

            self.dl_url = final_url
        except Exception as e:
            self.dl_url = None

    def fetch_episodes(self):
        self.cur_page = get(self.cur_url)
        self.parse(rf'({self.url}/episode/\d+/.*?)"')
        self.results = {
            url.split('/')[-1].replace('-', ' ').title(): url \
                for url in self.parsed[::-1]
        }

@app.get("/")
async def root():
    return RedirectResponse(url="/configure")

@app.get("/configure")
@app.get("/{params}/configure")
async def configure(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "isCommunityVersion": COMMUNITY_VERSION, "sponsorMessage": SPONSOR_MESSAGE, "version": VERSION}
    )

@app.get("/manifest.json")
@app.get("/{params}/manifest.json")
async def get_manifest():
    return JSONResponse(content=manifest_data)

@app.get("/static/{file_path:path}")
async def function(file_path: str):
    response = FileResponse(f"templates/{file_path}")
    return response

from concurrent.futures import ThreadPoolExecutor

@app.get("/stream/{stream_type}/{stream_id}")
@app.get("/{config}/stream/{stream_type}/{stream_id}")
async def get_results(
    config: str = None,
    stream_type: str = Path(..., description="Media type"),
    stream_id: str = Path(..., description="ID du contenu"),
    request: Request = None,
):
    print("Getting stream link for", stream_id)
    try:
        title = stream_id.replace("akwam", "").replace(".json", "")
        try:
            title = title.split(":")[0]
        except:
            pass
        decoded_title = base64.b64decode(title).decode("utf-8")
        is_base64 = True
    except Exception:
        is_base64 = False

    if is_base64:
        print("Seaching for", decoded_title, "in Akwam directly")
        akwam = Akwam('https://ak.sv/')
        akwam.type = stream_type
        akwam.search(decoded_title)

        streams = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for akwam_title, akwam_url in akwam.results.items():
                akwam.cur_url = akwam_url
                if stream_type == "series":
                    akwam.fetch_episodes()
                    for episode_key, episode_url in akwam.results.items():
                        futures.append(executor.submit(get_stream_link, akwam, episode_url, episode_key))
                else:
                    futures.append(executor.submit(get_stream_link, akwam, akwam_url, akwam_title))

            for future in as_completed(futures):
                try:
                    stream = future.result()
                    if stream:
                        streams.append(stream)
                except Exception as e:
                    print(f"Error when getting link : {e}")

        return {
            "streams": streams
        }

    else:
        if stream_type == "series":
            return []

        if config is None:
            return {"streams": []}

        tmdb_api_key = base64.b64decode(config).decode("utf-8")
        print("Searching for", stream_id, "in Akwam using TMDB API")
        if stream_type == "movie":
            imdb_id = stream_id.split(".")[0]
            tmdb_url = f"https://api.themoviedb.org/3/find/{imdb_id}?external_source=imdb_id&api_key={tmdb_api_key}"

        response = get(tmdb_url)
        data = response.json()

        if stream_type == "movie":
            movie = data.get("movie_results", [{}])[0]
            title = movie.get("title")
            original_title = movie.get("original_title")

        akwam = Akwam('https://ak.sv/')
        akwam.type = stream_type
        akwam.search(title)

        if not akwam.results:
            akwam.search(original_title)

        streams = []
        for akwam_title, akwam_url in akwam.results.items():
            akwam.cur_url = akwam_url

            akwam.load()
            akwam.get_direct_url()
            if akwam.dl_url:
                streams.append({
                    "title": akwam_title,
                    "url": akwam.dl_url
                })

        return {
            "streams": streams
        }

def extract_season_episode(title):
    """Extracts season and episode numbers from a title."""
    match = re.search(r'Saison (\d+) Épisode (\d+)', title)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1, 1

def get_stream_link(akwam, url, title):
    """Gathers stream link for a given URL."""
    akwam.cur_url = url
    akwam.load()
    akwam.get_direct_url()
    if akwam.dl_url:
        return {
            "title": title,
            "url": akwam.dl_url
        }
    return None
    
@app.get("/catalog/{catalog_type}/{catalog_id}.json")
@app.get("/{param}/catalog/{catalog_type}/{catalog_id}.json")
async def get_catalog(
    param: str = None,
    catalog_type: str = Path(..., description="Catalog type (Akwam Movies or Akwam Series)"),
    catalog_id: str = Path(..., description="Catalog ID"),
    skip: int = Query(default=0, description="Number of elements to skip"),
):
    limit = 24

    akwam = Akwam('https://ak.sv/')
    if catalog_type == "Akwam Movies": catalog_type = "movie"
    if catalog_type == "Akwam Series": catalog_type = "series"

    if catalog_type == "movie": catalog_type = "movies"
    genre_url = f'{akwam.url}/{catalog_type}?category=0'

    page = (skip // limit) + 1
    genre_url_with_page = f"{genre_url}&page={page}"
    print(f"Fetching page {page} from: {genre_url_with_page}")

    try:
        entries = fetch_entries_by_genre(genre_url_with_page)
    except Exception as e:
        print(f"Error when getting page {page}: {e}")
        return JSONResponse(content={"metas": []})

    start_index = skip % limit
    end_index = start_index + limit
    paginated_entries = entries[start_index:end_index]

    metas = []
    for title, link, thumb, year, tags in paginated_entries:
        metas.append({
            "id": f"akwam{base64.b64encode(title.encode()).decode()}",
            "type": "movie",
            "name": title,
            "poster": thumb,
            "year": year,
            "genres": tags,
        })
    print(f"Returning {len(metas)} metas (skip={skip}, limit={limit})")
    return JSONResponse(content={"metas": metas})

@app.get("/catalog/{catalog_type}/{catalog_id}/genre={genre}&skip={skip}.json")
@app.get("/{param}/catalog/{catalog_type}/{catalog_id}/genre={genre}&skip={skip}.json")
async def get_catalog_by_genre_with_skip(
    param: str = None,
    catalog_type: str = Path(..., description="Catalog type (Akwam Movies or Akwam Series)"),
    catalog_id: str = Path(..., description="Catalog ID"),
    genre: str = Path(..., description="Selected genre"),
    skip: int = Path(..., description="Nombre d'éléments à sauter"),
):
    return await get_catalog_by_genre(param, catalog_type, catalog_id, genre, skip)

@app.get("/catalog/{catalog_type}/{catalog_id}/genre={genre}.json")
@app.get("/{param}/catalog/{catalog_type}/{catalog_id}/genre={genre}.json")
async def get_catalog_by_genre_initial(
    param: str = None,
    catalog_type: str = Path(..., description="Catalog type (Akwam Movies or Akwam Series)"),
    catalog_id: str = Path(..., description="Catalog ID"),
    genre: str = Path(..., description="Selected genre"),
):
    return await get_catalog_by_genre(param, catalog_type, catalog_id, genre, skip=0)

async def get_catalog_by_genre(
    param: str,
    catalog_type: str,
    catalog_id: str,
    genre: str,
    skip: int,
):
    limit = 24
    akwam = Akwam('https://ak.sv/')
    if catalog_type == "Akwam Movies": catalog_type = "movie"
    if catalog_type == "Akwam Series": catalog_type = "series"
    genres = get_genres(catalog_type)

    genre_id = None
    for name, id_ in genres:
        if name == genre:
            genre_id = id_
            break

    if not genre_id:
        return JSONResponse(content={"metas": []})

    if catalog_type == "movie": catalog_type = "movies"
    genre_url = f'{akwam.url}/{catalog_type}?category={genre_id}'

    page = (skip // limit) + 1
    genre_url_with_page = f"{genre_url}&page={page}"
    print(f"Fetching page {page} from: {genre_url_with_page}")

    try:
        entries = fetch_entries_by_genre(genre_url_with_page)
    except Exception as e:
        print(f"Error when getting page {page}: {e}")
        return JSONResponse(content={"metas": []})

    start_index = skip % limit
    end_index = start_index + limit
    paginated_entries = entries[start_index:end_index]

    metas = []
    for title, link, thumb, year, tags in paginated_entries:
        metas.append({
            "id": f"akwam{base64.b64encode(title.encode()).decode()}",
            "type": "movie" if catalog_type == "movies" else "series",
            "name": title,
            "poster": thumb,
            "year": "2020",
            "genres": "ramadan",
            "background": thumb
        })
    print(f"Returning {len(metas)} metas (skip={skip}, limit={limit})")
    return JSONResponse(content={"metas": metas})

@app.get("/catalog/{catalog_type}/{catalog_id}/skip={skip}.json")
@app.get("/{param}/catalog/{catalog_type}/{catalog_id}/skip={skip}.json")
async def get_catalog(
    param: str = None,
    catalog_type: str = Path(..., description="Catalog type (Akwam Movies or Akwam Series)"),
    catalog_id: str = Path(..., description="Catalog ID"),
    skip: int = Path(..., description="Number of elements to skip"),
):
    limit = 24

    akwam = Akwam('https://ak.sv/')
    if catalog_type == "Akwam Movies": catalog_type = "movie"
    if catalog_type == "Akwam Series": catalog_type = "series"

    if catalog_type == "movie": catalog_type = "movies"
    genre_url = f'{akwam.url}/{catalog_type}?category=0'

    page = (skip // limit) + 1
    genre_url_with_page = f"{genre_url}&page={page}"
    print(f"Fetching page {page} from: {genre_url_with_page}")

    try:
        entries = fetch_entries_by_genre(genre_url_with_page)
    except Exception as e:
        print(f"Error when getting {page}: {e}")
        return JSONResponse(content={"metas": []})

    start_index = skip % limit
    end_index = start_index + limit
    paginated_entries = entries[start_index:end_index]

    metas = []
    for title, link, thumb, year, tags in paginated_entries:
        metas.append({
            "id": f"akwam{base64.b64encode(title.encode()).decode()}",
            "type": "movie",
            "name": title,
            "poster": thumb,
            "year": 2020,
            "genres": "ramadan",
            "background": thumb
        })
    print(f"Returning {len(metas)} metas (skip={skip}, limit={limit})")
    return JSONResponse(content={"metas": metas})

@app.get("/meta/{meta_type}/{meta_id}.json")
@app.get("/{param}/meta/{meta_type}/{meta_id}.json")
async def get_meta(
    param: str = None,
    meta_type: str = Path(..., description="Metadata type"),
    meta_id: str = Path(..., description="Element ID"),
):
    print(f"Fetching metadata for {meta_type} with ID: {meta_id}")

    try:
        meta_id_decoded = base64.b64decode(meta_id.replace("akwam", "")).decode("utf-8")
    except Exception:
        meta_id_decoded = meta_id

    meta = {
        "id": meta_id,
        "type": meta_type,
        "name": meta_id_decoded,
        "description": f"Watch {meta_id_decoded} on.",
        "poster": "https://via.placeholder.com/300x450",
        "background": "https://via.placeholder.com/1920x1080",
        "year": "2023",
        "genres": ["Action", "Drama"],
        "cast": [],
        "imdbRating": "N/A",
    }

    return JSONResponse(content={"meta": meta})