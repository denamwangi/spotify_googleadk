from google.genai import types
from google.adk.events import Event
from google.adk.auth import AuthConfig
import asyncio 
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import Agent, SequentialAgent
from pydantic import BaseModel, Field
from google.genai import types
from typing import List, Dict
from constants import MODEL_GEMINI_2_0_FLASH, MODEL_GPT_40, MODEL_CLAUDE_SONNET, SESSION_ID, APP_NAME, USER_ID
import asyncio
from google.adk.auth import AuthConfig, auth_credential
from fastapi.openapi.models import OAuth2
from fastapi.openapi.models import OAuthFlowAuthorizationCode
from fastapi.openapi.models import OAuthFlows
from google.adk.auth import AuthCredential
from google.adk.auth import AuthCredentialTypes
from google.adk.auth import OAuth2Auth
import os
from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth



client_id = os.environ['SPOTIFY_KEY']
client_secret = os.environ['SPOTIFY_SECRET']

auth_credential = AuthCredential(
    auth_type=AuthCredentialTypes.OAUTH2,
    oauth2=OAuth2Auth(
        client_id=client_id, 
        client_secret=client_secret,
        authorization_url="https://accounts.spotify.com/authorize",
        token_url="https://accounts.spotify.com/api/token",
        scopes=["user-read-private", "user-read-email", "playlist-modify-public", "playlist-modify-private"],
        redirect_uri="http://127.0.0.1:8000/callback"
    ),
)
scopes_dict = {
    "user-read-private": "Read your private user data", 
    "user-read-email": "Read your primary email address",
    "playlist-modify-public": "Modify public playlist", 
    "playlist-modify-private": "Modify private playlist", 
}
auth_scheme = OAuth2(flows=OAuthFlows(authorizationCode=OAuthFlowAuthorizationCode(authorizationUrl="https://accounts.spotify.com/authorize",tokenUrl="https://accounts.spotify.com/api/token",scopes=scopes_dict)))
auth_config = AuthConfig(auth_scheme=auth_scheme, raw_auth_credential=auth_credential, exchanged_auth_credential=auth_credential)



async def get_user_input(prompt: str) -> str:
    """
    Async prompt for the user when input is needed in the console

    uses asyncio's event loop and run_in_executor to avoid blocking the main 
    async execution thread while waiting for the input. (Why is this important?)

    Args:
        prompt: The message to display to the user with what you need them to do

    Returns:
        The string entered by the user.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)

async def call_agent_async(query: str, runner, user_id, session_id):
    print(f"\n >>> User Query: {query}")

    content = types.Content(role="user", parts=[types.Part(text=query)])

    final_response_text = "Agent did not produce any results sorry"

    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        print(f" Event Info: Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()} Content: {event.content}")
        print('_'*50)
        if event.is_final_response():

            if event.content and event.content.parts:
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate:
                final_response_text = f"Agent escalated: {event.error_message} or No specific error messgae"
            # break
    print(f" <<< Agent Response: {final_response_text}")


def is_pending_auth_event(event: Event) -> bool:
    """
    Checks if an ADK Event represents a request for user Auth

    Args:
        event: The ADK Event object to inspect

    Returns:
        True if event is 'adk_request_credential' function call. False otherwise.
    """
    return (
        event.content
        and event.content.parts
        and event.content.parts[0]
        and event.content.parts[0].function_call
        and event.content.parts[0].function_call.name == 'adk_request_credential'
    )

def get_function_call_id(event: Event) -> str:
    """
    Extracts unique ID of cuntion call from ADK Event
    Need this to tie the response once the request for auth credentials is complete

    Args:
        event: The ADK Event object containing the function call

    Returns:
        Unique identifier string of the function call

    Raises:
        ValueError If can't find the ID in the event 
    """
    if (
        event
        and event.content
        and event.content.parts
        and event.content.parts[0]
        and event.content.parts[0].function_call
        and event.content.parts[0].function_call.id
    ):
        function_call_id = event.content.parts[0].function_call.id 
        print('.'*50)
        print(f'Function all id {function_call_id}')

        return function_call_id
    raise ValueError(f"Cannot get functional call id from event {event}")


def get_function_call_auth_config(event: Event):
    """
    Extracts the config details from 'adk_request_credential'

    Args:
        event: The ADK event object containing the 'adk_request_credential' call.
    
    Returns:
        An AUthConfig object populated with details from the function call arguments.
    
    Raises:
        ValueError if 'auth_config' not found in the event
    """
    return auth_config

    if (
        event
        and event.content
        and event.content.parts
        and event.content.parts[0]
        and event.content.parts[0].function_call
        and event.content.parts[0].function_call.args
        and event.content.parts[0].function_call.args.get('auth_config')
    ): 
        
        auth_config = event.content.parts[0].function_call.args.get('auth_config')
        print('?'*50)
        print('?'*50)
        print('?')
        print('\nAuth config...')
        print(auth_config)
        return AuthConfig(**auth_config)
    return ValueError(f"Cannot get auth config for event {event}")