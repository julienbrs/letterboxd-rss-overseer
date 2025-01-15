import os
import logging
import xml.etree.ElementTree as ET
import requests
from typing import Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OverseerrAPI:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        }

    def search_movie(self, title: str, year: str) -> Optional[int]:
        try:
            search_url = f"{self.base_url}/api/v1/search"
            params = {
                'query': f"{title} {year}",
                'mediaType': 'movie'
            }
            response = requests.get(search_url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['results']:
                for result in data['results']:
                    if result.get('releaseDate', '').startswith(year):
                        logger.info(f"Film trouvé : {title} ({year}) - ID: {result['id']}")
                        return result['id']
            
            logger.warning(f"Film non trouvé : {title} ({year})")
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de {title} : {str(e)}")
            return None

    def request_movie(self, movie_id: int) -> bool:
        try:
            request_url = f"{self.base_url}/api/v1/request"
            data = {
                'mediaType': 'movie',
                'mediaId': movie_id,
                'is4k': False
            }
            
            response = requests.post(request_url, headers=self.headers, json=data)
            response.raise_for_status()
            logger.info(f"Film demandé avec succès (ID: {movie_id})")
            return True
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "Request for this media item already exists" in error_msg:
                logger.info(f"Film déjà demandé (ID: {movie_id})")
                return True
            logger.error(f"Erreur lors de la demande du film {movie_id}: {error_msg}")
            return False

def parse_movies_from_xml(xml_file: str) -> List[Dict[str, str]]:
    movies = []
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    for item in root.findall('.//item'):
        title = item.find('title')
        if title is not None:
            title_text = title.text
            if title_text and '(' in title_text and ')' in title_text:
                name = title_text.split('(')[0].strip()
                year = title_text.split('(')[1].replace(')', '').strip()
                movies.append({
                    'title': name,
                    'year': year
                })
    
    return movies

def main():
    load_dotenv()
    
    overseerr_url = os.getenv('OVERSEERR_URL')
    overseerr_api_key = os.getenv('OVERSEERR_API_KEY')
    xml_file = os.getenv('XML_FILE', 'feed.xml')

    if not all([overseerr_url, overseerr_api_key]):
        logger.error("Variables d'environnement manquantes. Créez un fichier .env avec OVERSEERR_URL et OVERSEERR_API_KEY")
        return

    overseerr = OverseerrAPI(overseerr_url, overseerr_api_key)
    
    logger.info(f"Lecture du fichier {xml_file}")
    movies = parse_movies_from_xml(xml_file)
    logger.info(f"Nombre de films trouvés : {len(movies)}")

    def process_movie(movie: Dict[str, str]) -> None:
        movie_id = overseerr.search_movie(movie['title'], movie['year'])
        if movie_id:
            overseerr.request_movie(movie_id)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_movie, movie)
            for movie in movies
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Erreur lors du traitement d'un film : {str(e)}")

if __name__ == "__main__":
    main()