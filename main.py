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

@app.middleware("http")
async def add_cors_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

VERSION = "1.1.0"
COMMUNITY_VERSION = os.getenv("IS_COMMUNITY_VERSION") == "true"
SPONSOR_MESSAGE = os.getenv("SPONSOR_MESSAGE")
ADDON_ID = os.getenv("ADDON_ID") if os.getenv("ADDON_ID") else "community.aymene69.akwam"
RGX_QUALITY_TAG = r'tab-content quality.*?a href="(https?://\w*\.*\w+\.\w+/link/\d+)"'
RGX_SIZE_TAG = r'font-size-14 mr-auto">([0-9.MGB ]+)</'
HTTP = 'https://'

templates = Jinja2Templates(directory="templates")

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

manifest_data = {
    "id": ADDON_ID,
    "icon": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTAr_UMfGGxBCd0GKqqW77SMWbYM2nOWPoIwA&s",
    "version": VERSION,
    "catalogs": [
        {
            "type": "movie",
            "id": "akwam-movies",
            "name": "Akwam Movies",
            "genres": [genre[0] for genre in get_genres('movie')]
        },
        {
            "type": "series",
            "id": "akwam-series",
            "name": "Akwam Series",
            "genres": [genre[0] for genre in get_genres('series')]
        },
        {
            "type": "movie",
            "id": "akwam-movies-search",
            "name": "Akwam Movies",
            "extra": [{"name": "search", "isRequired": True}]
        },
        {
            "type": "series",
            "id": "akwam-series-search",
            "name": "Akwam Series",
            "extra": [{"name": "search", "isRequired": True}]
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

def extract_season_episode(title):
    match = re.search(r'Saison (\d+) Épisode (\d+)', title)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1, 1

def extract_episode_number(title):
    """Extrait le numéro d'épisode d'un titre arabe ou anglais."""
    # Patterns pour différents formats
    patterns = [
        r'الحلقة\s*(\d+)',  # الحلقة 950
        r'حلقة\s*(\d+)',     # حلقة 950
        r'[Ee]pisode\s*(\d+)',  # Episode 123
        r'[Ee]p\s*(\d+)',       # Ep 123
        r'E(\d+)',              # E123
        r'(\d+)',               # Juste un nombre
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return int(match.group(1))
    return 0

def sort_streams_by_episode(streams):
    """Trie les streams par numéro d'épisode."""
    def get_sort_key(stream):
        return extract_episode_number(stream.get('title', ''))
    
    return sorted(streams, key=get_sort_key)


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
        self.posters = {}
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
        search_url = f'{self.search_url}{query}&section={self.type}&page={page}'
        print(f"🔍 Akwam search URL: {search_url}")
        self.cur_page = get(search_url)
        
        # Scraper les résultats avec BeautifulSoup pour récupérer les images
        soup = BeautifulSoup(self.cur_page.content, 'html.parser')
        self.results = {}
        self.posters = {}  # Dictionnaire pour stocker les posters
        
        widget_body = soup.find('div', class_='widget-body row flex-wrap')
        if widget_body:
            for item in widget_body.find_all('div', class_='col-lg-auto col-md-4 col-6 mb-12'):
                entry_box = item.find('div', class_='entry-box')
                if not entry_box:
                    continue
                
                title_elem = entry_box.find('h3', class_='entry-title')
                title = title_elem.text.strip() if title_elem else None
                
                link_elem = entry_box.find('a', class_='box')
                link = link_elem['href'] if link_elem else None
                
                thumb_elem = entry_box.find('img', class_='img-fluid w-100 lazy')
                thumb = thumb_elem['data-src'] if thumb_elem and thumb_elem.has_attr('data-src') else (thumb_elem['src'] if thumb_elem else '')
                
                if title and link:
                    self.results[title] = link
                    self.posters[title] = thumb
        
        print(f"🔍 Found {len(self.results)} results from Akwam")

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
        soup = BeautifulSoup(self.cur_page.content, 'html.parser')
        self.results = {}
        
        # Trouver tous les épisodes dans le HTML
        episodes = soup.find_all('div', class_='bg-primary2')
        
        for episode in episodes:
            h2 = episode.find('h2', class_='font-size-18')
            if not h2:
                continue
            
            link = h2.find('a')
            if not link:
                continue
            
            url = link.get('href', '')
            title_text = link.text.strip()
            
            # Extraire le numéro d'épisode depuis "حلقة 1 : ..." ou similaire
            episode_match = re.search(r'حلقة\s*(\d+)', title_text)
            if episode_match:
                episode_num = episode_match.group(1)
                episode_title = f"Episode {episode_num}"
                self.results[episode_title] = url
            else:
                # Fallback: essayer d'extraire depuis l'URL
                episode_id_match = re.search(r'/episode/(\d+)/', url)
                if episode_id_match:
                    episode_title = f"Episode {episode_id_match.group(1)}"
                    self.results[episode_title] = url

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
):
    print("Getting stream link for", stream_id)
    try:
        title = stream_id.replace("akwam", "").replace(".json", "")
        try:
            title = title.split(":")[0]
        except:
            pass
        decoded_data = base64.b64decode(title).decode("utf-8")
        is_base64 = True
    except Exception:
        is_base64 = False

    if is_base64:
        # Vérifier si le format contient une URL (nouveau format: "titre::url")
        if "::" in decoded_data:
            parts = decoded_data.split("::", 1)
            decoded_title = parts[0]
            direct_url = parts[1]
            print(f"🎯 Direct URL found for '{decoded_title}': {direct_url}")
            
            # Utiliser directement l'URL sans refaire de recherche
            akwam_results = {decoded_title: direct_url}
        else:
            # Ancien format : juste le titre, il faut faire une recherche
            decoded_title = decoded_data
            print(f"Searching for '{decoded_title}' in Akwam directly (type: {stream_type})")
            akwam = Akwam('https://ak.sv/')
            akwam.type = stream_type
            akwam.search(decoded_title)
            akwam_results = akwam.results
            
            print(f"Found {len(akwam_results)} results for '{decoded_title}'")
            if akwam_results:
                print(f"Results: {list(akwam_results.keys())}")

        streams = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for akwam_title, akwam_url in akwam_results.items():
                if stream_type == "series":
                    # Pour les séries, récupérer d'abord les épisodes
                    akwam_series = Akwam('https://ak.sv/')
                    akwam_series.type = stream_type
                    akwam_series.cur_url = akwam_url
                    akwam_series.fetch_episodes()
                    for episode_key, episode_url in akwam_series.results.items():
                        futures.append(executor.submit(get_stream_link, episode_url, episode_key, stream_type))
                else:
                    # Pour les films
                    print(f"Adding movie to process: {akwam_title}")
                    futures.append(executor.submit(get_stream_link, akwam_url, akwam_title, stream_type))

            print(f"Processing {len(futures)} items...")
            for future in as_completed(futures):
                try:
                    stream = future.result()
                    if stream:
                        print(f"Got stream: {stream['title']}")
                        streams.append(stream)
                except Exception as e:
                    print(f"Error when getting link : {e}")

        # Trier les streams par numéro d'épisode pour les séries
        if stream_type == "series" and streams:
            streams = sort_streams_by_episode(streams)
            print(f"Streams sorted by episode number")
        
        print(f"Returning {len(streams)} streams")
        return {
            "streams": streams
        }

    else:
        # ID non-Akwam (ex: IMDb, Cinemeta)
        # Ne pas chercher de liens pour éviter les doublons avec d'autres addons
        print(f"⚠️ Non-Akwam ID detected: {stream_id} - Skipping")
        return {"streams": []}

def extract_season_episode(title):
    """Extracts season and episode numbers from a title."""
    match = re.search(r'Saison (\d+) Épisode (\d+)', title)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1, 1

def get_stream_link(url, title, stream_type):
    """Gathers stream link for a given URL."""
    try:
        # Créer une nouvelle instance Akwam pour chaque thread
        akwam = Akwam('https://ak.sv/')
        akwam.type = stream_type
        akwam.cur_url = url
        akwam.load()
        
        # Essayer différentes qualités jusqu'à en trouver une qui fonctionne
        for quality in ['1080p', '720p', '480p']:
            if quality in akwam.qualities:
                akwam.get_direct_url(quality)
                if akwam.dl_url:
                    print(f"✓ Found {quality} link for: {title}")
                    return {
                        "title": title,  # Titre sans la qualité
                        "name": f"Akwam {quality}",  # Nom du provider avec qualité
                        "url": akwam.dl_url
                    }
        
        print(f"✗ No valid quality found for: {title}")
    except Exception as e:
        print(f"✗ Error getting stream link for {title}: {e}")
        import traceback
        traceback.print_exc()
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
    # Garder le type Stremio original (movie ou series)
    stremio_type = catalog_type
    
    # Convertir pour l'URL Akwam (movies ou series)
    akwam_type = "movies" if catalog_type == "movie" else catalog_type
    genre_url = f'{akwam.url}/{akwam_type}?category=0'

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
            "type": stremio_type,  # Utiliser le type Stremio original
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
    # Garder le type Stremio original (movie ou series)
    stremio_type = catalog_type
    
    genres = get_genres(catalog_type)

    genre_id = None
    for name, id_ in genres:
        if name == genre:
            genre_id = id_
            break

    if not genre_id:
        return JSONResponse(content={"metas": []})

    # Convertir pour l'URL Akwam (movies ou series)
    akwam_type = "movies" if catalog_type == "movie" else catalog_type
    genre_url = f'{akwam.url}/{akwam_type}?category={genre_id}'

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
            "type": stremio_type,  # Utiliser le type Stremio original
            "name": title,
            "poster": thumb,
            "year": year,
            "genres": tags,
            "background": thumb
        })
    print(f"Returning {len(metas)} metas (skip={skip}, limit={limit})")
    return JSONResponse(content={"metas": metas})

@app.get("/catalog/{catalog_type}/{catalog_id}/skip={skip}.json")
@app.get("/{param}/catalog/{catalog_type}/{catalog_id}/skip={skip}.json")
async def get_catalog_with_skip(
    param: str = None,
    catalog_type: str = Path(..., description="Catalog type (Akwam Movies or Akwam Series)"),
    catalog_id: str = Path(..., description="Catalog ID"),
    skip: int = Path(..., description="Number of elements to skip"),
):
    limit = 24

    akwam = Akwam('https://ak.sv/')
    # Garder le type Stremio original (movie ou series)
    stremio_type = catalog_type
    
    # Convertir pour l'URL Akwam (movies ou series)
    akwam_type = "movies" if catalog_type == "movie" else catalog_type
    genre_url = f'{akwam.url}/{akwam_type}?category=0'

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
            "type": stremio_type,  # Utiliser le type Stremio original
            "name": title,
            "poster": thumb,
            "year": year,
            "genres": tags,
            "background": thumb
        })
    print(f"Returning {len(metas)} metas (skip={skip}, limit={limit})")
    return JSONResponse(content={"metas": metas})

@app.get("/catalog/{catalog_type}/{catalog_id}/search={search_query}.json")
@app.get("/{param}/catalog/{catalog_type}/{catalog_id}/search={search_query}.json")
async def get_catalog_search(
    param: str = None,
    catalog_type: str = Path(..., description="Catalog type"),
    catalog_id: str = Path(..., description="Catalog ID"),
    search_query: str = Path(..., description="Search query"),
    skip: int = Query(default=0, description="Number of elements to skip"),
):
    print(f"Searching Akwam for: '{search_query}' (type: {catalog_type})")
    limit = 20
    
    akwam = Akwam('https://ak.sv/')
    akwam.type = catalog_type
    
    # Calculer la page pour Akwam (ils utilisent aussi la pagination)
    page = (skip // limit) + 1
    akwam.search(search_query, page=page)
    
    print(f"Found {len(akwam.results)} results for '{search_query}'")
    
    metas = []
    for title, url in list(akwam.results.items())[:limit]:
        # Stocker l'URL et le titre ensemble pour éviter de perdre l'information
        # Format: titre::url
        id_data = f"{title}::{url}"
        poster = akwam.posters.get(title, "https://via.placeholder.com/300x450?text=No+Image")
        metas.append({
            "id": f"akwam{base64.b64encode(id_data.encode()).decode()}",
            "type": catalog_type,
            "name": title,
            "poster": poster,
        })
    
    print(f"Returning {len(metas)} search results")
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

    # Si le format contient "titre::url", extraire seulement le titre
    if "::" in meta_id_decoded:
        title = meta_id_decoded.split("::", 1)[0]
    else:
        title = meta_id_decoded

    meta = {
        "id": meta_id,
        "type": meta_type,
        "name": title,
        "description": f"Watch {title} on Akwam.",
        "poster": "https://via.placeholder.com/300x450",
        "background": "https://via.placeholder.com/1920x1080",
        "year": "2023",
        "genres": ["Action", "Drama"],
        "cast": [],
        "imdbRating": "N/A",
    }

    return JSONResponse(content={"meta": meta})

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)