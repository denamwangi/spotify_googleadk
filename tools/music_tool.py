from typing import List, Dict
from constants import MODEL_GEMINI_2_0_FLASH, MODEL_GPT_40, MODEL_CLAUDE_SONNET, SESSION_ID, APP_NAME, USER_ID
from google.adk.tools.tool_context import ToolContext
from google.adk.runners import Runner
from helpers import auth_config, auth_scheme, is_pending_auth_event, get_function_call_auth_config, get_function_call_id, get_user_input
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset
from google.adk.tools import FunctionTool
import requests
import json
from google.oauth2.credentials import Credentials

cheap_model = MODEL_CLAUDE_SONNET

spotify_user_id = 'dmwangi-us'
spotify_search_uri = "https://api.spotify.com/v1/search"
spotify_create_playlist_uri = f"https://api.spotify.com/v1/users/{spotify_user_id}/playlists"


def _get_track_uris(tracks):
    track_ids = []
    track_uris = ''
    for track in tracks:
        name = track["name"]
        artists = track["artists"]
        id = track["id"]
        track_ids.append(id)
        track_uris += f"{track['uri']},"
        print(f"name: {name} \n uri: {track['uri']} \n artists: {artists[0]['name']}")
    print('.'*50)
    print('\n adding tracks to uris')


    return track_uris[:-1]

def _get_tracks(search_query: str, access_token: str) -> List[str]:
    # GET TRACKS BASED ON TAGS
    tracks_response = requests.get(
        spotify_search_uri,
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        params={
            "q":search_query,
            "type": "track",
            "limit":10,
        }
    )
    print(f'tracks response {tracks_response}')
    return tracks_response.json()["tracks"]["items"]

def _create_playlist(title: str, access_token: str) -> Dict[str, str]:
    print('>'*50)
    print(' ')
    print(' ')
    print('creating playlist...')
    print('    spotify_create_playlist_uri: ', spotify_create_playlist_uri )
    print('    access_token: ', access_token )
    
    print(' ')
    # CREATE EMPTY PLAYLIST WITH FUN NAME
    create_playlist_response = requests.post(
        spotify_create_playlist_uri,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json={
            
                "name": title,
                "description": "Travel playlist",
                "public": False,
            
        }
    )
    print('create_playlist_response', create_playlist_response)
    return create_playlist_response.json()


TOKEN_CACHE_KEY = "groupchat_travel_tokens"
def auth_spotify(tool_context: ToolContext) -> Dict[str, str]:
    """ Goes through spotify auth

    Args:
     tool_context: Automatically provided by ADK.

    Returns:
        dict: A dictionary with keys:
            - 'status' (str): 'pending' if auth needed, 'success' if auth succeeded, 'error' if failed
            - 'message' (str): A status message, e.g., 'User is authenticated'.
    """
    print('>'*50)
    print('auth_Spotify...')
    state = tool_context.state
    print('state...', tool_context.state.to_dict())
    SCOPES = ["user-read-private", "user-read-email", "playlist-modify-private", "playlist-modify-public"]

    creds = None
    cached_token_info = tool_context.state.get(TOKEN_CACHE_KEY)

    if cached_token_info:
        print('CHECKING CACHED INFO VALIDITY')

        try:
            creds = Credentials.from_authorized_user_info(cached_token_info, SCOPES)
            import pdb; pdb.set_trace()
            if not creds.valid and creds.expired and creds.refresh_token:
                creds.refresh()
                tool_context.state[TOKEN_CACHE_KEY] = json.loads(creds.to_json()) # Update cache
            elif not creds.valid:
                creds = None # Invalid, needs re-auth
                tool_context.state[TOKEN_CACHE_KEY] = None
        except Exception as e:
            print(f"Error loading/refreshing cached creds: {e}")
            creds = None
            tool_context.state[TOKEN_CACHE_KEY] = None

    if creds and creds.valid:
        print('CACHED CREDS AVAILABLE> CONGRATS!!!')
        pass

        
    else:
        print('CHECKING IF WE JUST COMPLETED AUTH FLOW')

        # import pdb; pdb.set_trace()
        exchanged_credential = tool_context.get_auth_response(
            auth_config
        )
        if exchanged_credential:
            print('exchanged_credential', exchanged_credential)
            access_token = exchanged_credential.oauth2.access_token
            refresh_token = exchanged_credential.oauth2.refresh_token
            creds = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri=auth_scheme.flows.authorizationCode.tokenUrl,
                client_id=exchanged_credential.oauth2.client_id,
                client_secret=exchanged_credential.oauth2.client_secret,
                scopes=list(auth_scheme.flows.authorizationCode.scopes.keys()),
            )
            tool_context.state[TOKEN_CACHE_KEY] = json.loads(creds.to_json())
            print('STATE', tool_context.state.to_dict())
            print(' ')
            print(f"DEBUG: Cached/updated tokens under key: {TOKEN_CACHE_KEY}")


        else:
            print('Nothing cached, nothing valid, and no exchanged creds yet')
            print('KICKING OFF AUTH FLOW FROM TOOL...')

            tool_context.request_credential(auth_config)
            return {'pending': True, 'message': 'Awaiting user authentication.'}
 
        playlist_response = create_spotify_playlist(tool_context)
        return playlist_response

def create_spotify_playlist(tool_context: ToolContext) -> str:
    """ Uses tags to fetch tracks for a Spotify playlist that match those tags

    Args:
        None

    Returns:
        playlist link (str): Spotify link to playlist
    """
    # START WORK FOR THE PLAYLIST
    tool_context_state =  tool_context.state.to_dict()
    access_token = tool_context_state[TOKEN_CACHE_KEY]['token']
    

    # spotify_search_tags = tool_context_state['spotify_search_tags']
    # tags = json.loads(spotify_search_tags)
    # mood = tags.get('mood')
    # genre = tags.get('genre')
    # search_query = f"{mood} {genre}"
    # title = tags.get('title', 'Travel playlist 2025')
    title = "Test 123 playlist"
    search_query = "fun, vibrant summer paris"


    # CREATE EMPTY PLAYLIST WITH FUN NAME

    playlist = _create_playlist(title, access_token)
    return playlist
    playlist_url = playlist.get('uri')
    return {
        "status": "success",
        "data": playlist_url,
    }

    # # GET TRACKS FOR THE PLAYLIST
    # tracks = _get_tracks(search_query, access_token)    
    # track_uris = _get_track_uris(tracks)
    # tool_context.state['spotify_playlist_url'] = "https://open.spotify.com/playlist/37i9dQZF1Eta3yIt7Xb0IB?si=3fjCpfHLQRyhpn0wOGOEOw"
    # return "https://open.spotify.com/playlist/37i9dQZF1Eta3yIt7Xb0IB?si=3fjCpfHLQRyhpn0wOGOEOw"


    # ADD TRACKS TO PLAYLIST
    # add_playlist_tracks_response = _add_tracks_to_playlist(track_uris, playlist_id)
    # print(add_playlist_tracks_response)


create_spotify_playlist_tool = FunctionTool(func=create_spotify_playlist)
