"""
About Me AI Avatar
=====================================

This application powers a conversational About Me AI avatar for personal website.
It is designed to answer questions about professional background, skills, experience, and selected private information
based on structured documents provided in a local `about_me/` folder.
"""

# Import Required Libraries
from dotenv import load_dotenv            # Load environment variables from .env file
from openai import OpenAI                 # OpenAI API wrapper
import json                               # JSON parsing for tool call arguments
import os                                 # File system interaction
import requests                           # Sending push notifications
from pypdf import PdfReader               # Reading content from PDF files
import gradio as gr                       # Gradio for web UI


# Load Environment Variables
load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY")

def send_email(subject, body):
    payload = {
        "api_key": os.getenv("SMTP2GO_API_KEY"),
        "to": [
            "Piotr Kowalczyk <piotr.kowalczyk@infosecotb.com>"
        ],
        "sender": "InfoSec <info@infosecotb.com>",
        "subject": subject,
        "text_body": body
      }
    headers = { "Content-Type": "application/json" }
    response = requests.post("https://api.smtp2go.com/v3/email/send", headers=headers, data=json.dumps(payload))
    if response.status_code == requests.codes.ok:
        print(response.json)
    else:
        print("An Error Occurred: " + response.text)  

# Tool Function: record_user_details
# Called by AI when email is collected from the user
def record_user_details(email, name="Name not provided", notes="Not provided"):
    send_email(
        f"New user provided e-mail address: {name}",
        f"Email: {email}\nNotes: {notes}"
    )
    return {"recorded": "ok"}


# Tool Function: record_details
# Called by AI when no email is collected but a conversation details is needed
def record_start(description):
    send_email(
        f"New conversation started",
        f"Description: {description}"
    )
    return {"recorded": "ok"}


# OpenAI Tool Definition: record_user_details
# Schema describing parameters AI must provide to log user details
record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user provided an email address and name",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The email address of this user"},
            "name": {"type": "string", "description": "The user's name, if they provided it"},
            "notes": {"type": "string", "description": "Context or unanswered questions"},
           },
        "required": ["email"],
        "additionalProperties": False
    }
}


# OpenAI Tool Definition: record_details
# Schema for saving a details when no email is captured
record_start_json = {
    "name": "record_start",
    "description": "Use this tool to record begin of the conversation",
    "parameters": {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "A new conversation has started"}
        },
        "required": ["description"],
        "additionalProperties": False
    }
}


# Register Tools With OpenAI Model
tools = [
    {"type": "function", "function": record_user_details_json},
    {"type": "function", "function": record_start_json}
]


# Class: AboutMe
# Loads documents and powers the chat interface
class AboutMe:
    def __init__(self):
        # Initialize OpenAI client
        self.openai = OpenAI()

        # Identity
        self.name = "Piotr kowalczyk"

       # Load all documents from 'about_me' folder
        self.about_me = {}
        files = os.listdir("about_me")
        for document in files:
            if document.endswith(".pdf"):
                reader = PdfReader(f"about_me/{document}")
                text = "".join([page.extract_text() for page in reader.pages])
                self.about_me[document.split(".")[0]] = text
            elif document.endswith(".txt"):
                with open(f"about_me/{document}", "r", encoding="utf-8") as f:
                    self.about_me[document.split(".")[0]] = f.read()

    
    # Handles OpenAI tool calls dynamically
    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tool_call.id
            })
        return results


    # Returns system prompt defining AI's personality and behavior
    def system_prompt(self):
        system_prompt = (f"""
You are acting as {self.name}. You are answering questions on {self.name}'s website,
particularly questions related to {self.name}'s career, background, skills and experience.
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible.
You have access to several documents that contain information about {self.name}, each document is named to reflect its content.  You can use these documents to answer questions.
Be professional and engaging, as if talking to a potential client or future employer who came across the website.
When conversation starts, imidietely use your record_start tool to record the start of the conversation. Use the record_start tool only once, when the conversation starts and you see only one message from the user.
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. 
Don't use the record_user_details tool again if the user doesn't provide a new email or name, check the history of the conversation to see if the user has provided an email or name before.
""")
        # Append content from each document for AI context
        for information in self.about_me:
            system_prompt += f"\n\n## {information}:\n{self.about_me[information]}\n"
        return system_prompt


    # Main chat loop
    # Sends user messages to OpenAI, handles tool calls, returns response
    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools
            )
            if response.choices[0].finish_reason == "tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content


# Launch Gradio UI
if __name__ == "__main__":
    about_me = AboutMe()
    gr.ChatInterface(about_me.chat, type="messages", title="vPiotr", analytics_enabled="True").launch()