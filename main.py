import os 
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

from config import max_iterations, system_prompt
from call_funtion import call_function, available_functions

def main(): 
    if len(sys.argv) < 2:
        print("Usage: python main.py <prompt>")
        sys.exit(1)
    if len(sys.argv) == 3 and sys.argv[2] == "--verbose":
        verbose = True
    else:
        verbose = False
    user_prompt = sys.argv[1]

    # Load the API key from the environment variable
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)   

    config = types.GenerateContentConfig(
        system_instruction=system_prompt, 
        tools=[available_functions],
        candidate_count=1
    )
    messages = [
            types.Content(role="user", parts=[types.Part(text=user_prompt)])
        ]

    for i in range(max_iterations):
        print(f"Iteration {i+1}:")
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=messages,
                config=config
                )  
        except Exception as e:
            print(f"Error: {e}")
            return
        
        if response is None or response.usage_metadata is None:
            print("Response is None or Usage metadata is None")
            return
      
    
        if response.candidates:
            candidate = response.candidates[0]
            messages.append(candidate.content)
        else:
            print("No candidates in the response")
               

        

        if verbose:
            print("User prompt: ", user_prompt)
            
            print(f"prompt tokens: {response.usage_metadata.prompt_token_count} tokens")
            
            print(f"response tokens: {response.usage_metadata.candidates_token_count} tokens")
        
        if response.function_calls:            
            function_response_parts = []
            for function_call_part in response.function_calls:
                function_result = call_function(function_call_part, verbose)
                function_response_parts.extend(function_result.parts)
            messages.append(
                types.Content(
                    role='tool',
                    parts=function_response_parts
                )
            )

        else:
            #that is the final answer
            print('--------------------------------')
            print("Messages:", messages)
            
            print('--------------------------------')
            print("Final answer:")
            print(response.text)
            return

main()