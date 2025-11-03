import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
# Používáme Streamlit secrets pro bezpečné načtení klíčů
from streamlit import secrets 

# --- Nastavení a Autorizace ---
# Načtení klíčů ze souboru secrets.toml
try:
    CLIENT_ID = secrets["spotify"]["client_id"]
    CLIENT_SECRET = secrets["spotify"]["client_secret"]
    REDIRECT_URI = secrets["spotify"]["redirect_uri"]
except KeyError:
    st.error("CHYBA: Zabezpečené klíče nenalezeny. Zkontrolujte soubor .streamlit/secrets.toml.")
    st.stop()

# Nastavení práv a pokus o načtení tokenu
SCOPE = "user-library-read user-top-read playlist-modify-private"
sp: spotipy.Spotify | None = None
user_name = None

def authorize_spotify():
    try:
        auth = SpotifyOAuth(
            scope=SCOPE,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI
        )
        token_info = auth.get_cached_token()
        if not token_info:
            auth_url = auth.get_authorize_url()
            st.markdown(f"[Klikněte zde pro přihlášení ke Spotify]({auth_url})")
            return None

        sp = spotipy.Spotify(auth_manager=auth)
        return sp
    except Exception as e:
        st.error(f"Chyba autorizace: {e}")
        return None

# --- Definice Funkcí (Logika Playlistu) ---

# Funkce pro načtení semen (vašich top skladeb)
def get_user_seeds(limit=10):
    results = sp.current_user_top_tracks(limit=limit, time_range='long_term')
    return results['items']

# Funkce pro rozšíření kandidátů
def expand_candidates_from_seed_tracks(seeds, per_seed=5):
    candidates = []
    for t in seeds:
        artist = t['artists'][0]['name']
        track_name = t['name']
        query = f"{artist} {track_name}"
        res = sp.search(q=query, type='track', limit=per_seed)
        for item in res['tracks']['items']:
            candidates.append(item)
            
        artist_id = t['artists'][0]['id']
        albums = sp.artist_albums(artist_id, album_type='album,single', limit=3)
        for alb in albums['items']:
            tracks = sp.album_tracks(alb['id'])
            for tr in tracks['items']:
                candidates.append(sp.track(tr['id']))
                
    unique = {c['id']: c for c in candidates}
    return list(unique.values())

# Funkce pro filtrování a řazení
def filter_and_rank(candidates, seeds, max_count=30):
    seed_ids = {t['id'] for t in seeds}
    filtered = [c for c in candidates if c['id'] not in seed_ids] 
    filtered.sort(key=lambda x: x['popularity'], reverse=True)
    return filtered[:max_count]

# Funkce pro tvorbu playlistu
def create_playlist_with_tracks(name, tracks):
    user_id = sp.me()['id']
    # Nastavíme playlist jako soukromý (public=False)
    pl = sp.user_playlist_create(user_id, name, public=False, description="Vygenerováno pomocí AI Playlist Maker") 
    uris = [t['uri'] for t in tracks]
    sp.playlist_add_items(pl['id'], uris)
    st.success(f"Playlist '{name}' s {len(tracks)} skladbami byl úspěšně vytvořen na Spotify!")
    st.write(f"Odkaz: {pl['external_urls']['spotify']}")
    return pl

# --- Hlavní Rozhraní Streamlit (Webové GUI) ---
def main():
    st.title("AI Playlist Generator")
    sp = authorize_spotify()
    if not sp:
        st.stop()

    user_name = sp.me()["display_name"]
    st.markdown(f"**Přihlášen jako:** {user_name}")

    # Interaktivní vstupy
    name = st.text_input("Zadejte název nového playlistu:", value="Doporučení od Bota")
    track_limit = st.slider("Počet doporučených skladeb:", min_value=10, max_value=100, value=30, step=5)
    seed_limit = st.slider("Počet vašich TOP skladeb pro inspiraci (Seeds):", min_value=5, max_value=20, value=10, step=1)

    # Tlačítko pro spuštění celého procesu
    if st.button('VYTVOŘIT PLAYLIST!'):

        if not name:
            st.warning("Zadejte prosím název playlistu.")
        else:
            # Použití Streamlit spinner pro zobrazení průběhu
            with st.spinner('Pracuji... Načítání a filtrování skladeb (může trvat delší dobu)...'):
                try:
                    # 1. Generování skladeb
                    seeds = get_user_seeds(limit=seed_limit)

                    st.info(f"Načteno {len(seeds)} oblíbených skladeb pro inspiraci. Hledám podobné kandidáty...")

                    candidates = expand_candidates_from_seed_tracks(seeds, per_seed=3)

                    # 2. Filtrování
                    selected = filter_and_rank(candidates, seeds, max_count=track_limit)

                    # 3. Tvorba playlistu
                    if selected:
                        create_playlist_with_tracks(name, selected)
                    else:
                        st.warning("Nebyla nalezena žádná nová doporučená skladba. Zkuste zvýšit limit 'Seeds'.")

                except Exception as e:
                    st.error(f"Při generování playlistu nastala chyba: {e}")

if __name__ == "__main__":
    main()