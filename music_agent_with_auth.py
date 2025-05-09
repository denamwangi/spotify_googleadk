from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import Agent, SequentialAgent
from pydantic import BaseModel, Field
from google.genai import types
from typing import Optional
from constants import MODEL_GEMINI_2_0_FLASH, MODEL_GPT_40, MODEL_CLAUDE_SONNET, SESSION_ID, APP_NAME, USER_ID
import asyncio
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.runners import Runner
from helpers import auth_config, is_pending_auth_event, get_function_call_auth_config, get_function_call_id, get_user_input
import urllib.parse
from tools.music_tool import auth_spotify, create_spotify_playlist, create_spotify_playlist_tool


orchestrator_model = MODEL_GPT_40
cheap_model = MODEL_CLAUDE_SONNET


class SpotifySearchTags(BaseModel):
    title: str = Field(..., description="A fun title for the playlist ")
    mood: str = Field(..., description="1-3 space separated descriptors of the type of mood the playlist should have e.g. 'happy emo' ")
    genre: Optional[str] = Field(None, description="The musical genre e.g. afrobeats, pop, R&B")
    

get_music_tags_agent = Agent(
    name="get_music_tags_agent",
    model=LiteLlm(cheap_model),
    description="Generates a playlist title and musical tags based on the destination city which will be used to get tracks from spotify",
    instruction="You are a musical expert generating playlist tags based on a user's travel destination. "
                "Your output should include a mood and genre suitable for the city and time of year. "
                "Respond in structured JSON using the SpotifySearchTags schema and use only the fields included."
                " Include 2-3 for each field. For example for Nairobi as the destination you might return" 
                "SpotifySearchTags(title='Breezy Summer in Paris' mood='upbeat happy' genre='afrobeats amapiano')"
                "Your output must be a pure JSON object and must not include any text, commentary, or Markdown formatting. "
                "Return only the JSON object with fields 'mood' and 'genre'.",
    output_key="spotify_search_tags",
)

# create_spotify_playlist_agent = Agent(
#     name="create_spotify_playlist_agent",
#     model=LiteLlm(orchestrator_model),
#     description="Creates a spotify playlist for the travel destination",
#     instruction=(
#         "Your job is to create a Spotify playlist for the user's travel destination. "
#         "Use the 'create_spotify_playlist_tool' tool to do this. "
#         "You do not need to pass any input to the tool — just call it when appropriate. "
#     ),                
#     tools=[create_spotify_playlist_tool]
# )


auth_spotify_agent = Agent(
    name="auth_spotify_agent",
    model=LiteLlm(orchestrator_model),
    description="Authenticated a user to spotify",
    instruction=(
        "Your job is to authenticate with Spotify "
        "Use the 'auth_spotify' tool to do this. "
        "You do not need to pass any input to the tool — just call it when appropriate. "
    ),                
    tools=[auth_spotify]
)


music_playlist_pipeline_agent = SequentialAgent(
    name="music_playlist_pipeline_agent",
    sub_agents=[get_music_tags_agent, auth_spotify_agent],
    description="Spotify playlist "
)

# music_playlist_pipeline_agent = SequentialAgent(
#     name="music_playlist_pipeline_agent",
#     sub_agents=[auth_spotify_agent, get_music_tags_agent, create_spotify_playlist_agent],
# )

# music_playlist_pipeline_agent = Agent(
#     name="music_playlist_pipeline_agent",
#     model=LiteLlm(orchestrator_model),
#     description="Orchestrator of the spotify playlist creation",
#     instruction = (
#         "Your job is to orchestrate the creation of Spotify playlist tags in 2 steps:\n\n"
#         "2. FIRST, delegate to 'get_music_tags_agent' to get music tags based on the user's trip or destination.\n"
#         "1. NEXT delegate to  'auth_spotify_agent' to authenticate the user. It will return {'status': 'sucess'} when it's successfully done authing"
#         "DO NOT EVER delegate to 'get_music_tags_agent' a second time.\n"
#         "Only call each agent once per session unless you are explicitly told to retry by the user."
#     ),        
#     sub_agents=[get_music_tags_agent, auth_spotify_agent]
     
# )

# music_playlist_pipeline_agent = Agent(
#     name="music_playlist_pipeline_agent",
#     model=LiteLlm(orchestrator_model),
#     description="Orchestrator of the spotify playlist creation",
#     instruction = (
#         "Your job is to orchestrate the creation of a Spotify playlist in three steps:\n\n"
#         "1. FIRST, delegate to  'auth_spotify_agent' to authenticate the user"
#         "2. Next delegate to 'get_music_tags_agent' to get music tags based on the user's trip or destination.\n"
#         "3. Lastly , delegate to 'create_spotify_playlist_agent' using the tags from step 1 to create the playlist.\n\n"
#         "DO NOT EVER delegate to 'get_music_tags_agent' a second time.\n"
#         "Only call each agent once per session unless you are explicitly told to retry by the user."
#     ),        
#     sub_agents=[auth_spotify_agent,  get_music_tags_agent, create_spotify_playlist_agent]
     
# )


async def run_team_conversation():
    user_id = USER_ID
    session_id = SESSION_ID

    # create a session
    session_service = InMemorySessionService()
    artifacts_service = InMemoryArtifactService()
    session = session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
        
    )
    print(f" Session created: App={session.app_name}  User: {session.user_id} session_id={session.id}")
    
    # create a runner
    runner = Runner(
        agent=music_playlist_pipeline_agent,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifacts_service,
    )

    query = f"Hi! Can you create a playlist for my trip to Nairobi?"

    print(f"Runner created for agent {runner.agent.name}")
 

    print(f"\n >>> User Query: {query}")

    content = types.Content(role="user", parts=[types.Part(text=query)])


    events_async = runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
    # auth_request_event_id, auth_config = None, None
    auth_request_event_id = None
    async for event in events_async:
        print('%'*50)
        print(f" Event Info: Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()} Content: {event.content}")
        print('%'*50)
        if event.is_final_response():
            if event.content and event.content.parts:
                # Assuming text response in the first part
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate: # Handle potential errors/escalations
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            # Add more checks here if needed (e.g., specific error codes)
            print(f" <<< Agent Response: {final_response_text}")

        if is_pending_auth_event(event):
            print("--> Authentication required by agent.")
            auth_request_event_id = get_function_call_id(event)
            # auth_config = get_function_call_auth_config(event)

            break
    
    oath2_config = auth_config.exchanged_auth_credential.oauth2
    redirect_uri = oath2_config.redirect_uri

    params = {
        "client_id": oath2_config.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": ' '.join(oath2_config.scopes),
    }
    params_encoded = urllib.parse.urlencode(params)
    auth_request_uri = 'https://accounts.spotify.com/authorize?' + params_encoded
    print('auth_request_uri: ', auth_request_uri)
    auth_response_uri = await get_user_input(
        f'1. Please open this URL in your browser to log in:\n   {auth_request_uri}\n\n'
        f'2. After successful login and authorization, your browser will be redirected.\n'
        f'   Copy the *entire* URL from the browser\'s address bar.\n\n'
        f'3. Paste the copied URL here and press Enter:\n\n> '
    )
    print('.'*50)
    print('auth_response_uri', auth_response_uri)
    auth_response_uri = auth_response_uri.strip()

    print('.'*50)
    print('\n Update the auth_config')
    oath2_config.auth_response_uri = auth_response_uri
    oath2_config.redirect_uri = redirect_uri

    print('Construct the FunctionResponse Content object to send back to the tool')
    auth_content = types.Content(
        role='user',
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=auth_request_event_id,
                    name='adk_request_credential',
                    response=auth_config.model_dump()
                )
            )
        ]
    )
    print(f"Sending it all back to the tool with { auth_config }")

    events_async = runner.run_async(
      session_id=session_id,
      user_id=user_id,
      new_message=auth_content
    )
    print('created events_async correctly...')
    async for event in events_async:
        print(f" Event Info: Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()} Content: {event.content}")
        print('_'*50)



if __name__ == "__main__":
    try:
        asyncio.run(run_team_conversation())
    except Exception as e:
        print(f"Oops! An error occured: {e}")
