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
# import smtplib                            # Sending emails via SMTP
import requests
import random                             # 
from pypdf import PdfReader               # Reading content from PDF files
import gradio as gr                       # Gradio for web UI


# Load Environment Variables
load_dotenv(override=True)

# str(random.randint(1, 1000))}

# Function: Send Email
# Sends email with provided subject and body using credentials from .env
# def send_email(subject, body):
#     msg = f"Subject: {subject}\n\n{body}"
#     print(msg)  # Optional: log email locally
#     server = smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT")))
#     server.starttls()
#     server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
#     server.sendmail(os.getenv("SMTP_USER"), os.getenv("SMTP_RECIPIENT"), msg)
#     server.quit()

# For pushover

pushover_user = os.getenv("PUSHOVER_USER")
pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_url = "https://api.pushover.net/1/messages.json"

def push(message):
    print(f"Push: {message}")
    payload = {"user": pushover_user, "token": pushover_token, "message": message}
    requests.post(pushover_url, data=payload)

# Tool Function: record_user_details
# Called by AI when email is collected from the user
def record_user_details(conversation_id, email, name="Name not provided", notes="Not provided", details=""):
    # send_email(
    #     f"New user provided e-mail address: {name} in conversation {conversation_id}",
    #     f"Email: {email}\nNotes: {notes}\ndetails (PII removed): {details}"
    # )
    push(f"New user provided e-mail address: {name} in conversation {conversation_id}\nEmail: {email}\nNotes: {notes}\ndetails (PII removed): {details}")
    return {"recorded": "ok"}


# Tool Function: record_details
# Called by AI when no email is collected but a conversation details is needed
def record_details(conversation_id, details, questions=""):
    push(f"Details of chat in conversation {conversation_id}\nUnanswered questions: {questions}\ndetails (PII removed): {details}")
    return {"recorded": "ok"}


# OpenAI Tool Definition: record_user_details
# Schema describing parameters AI must provide to log user details
record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "conversation_id": {"type": "string", "description": "The conversation id"},
            "email": {"type": "string", "description": "The email address of this user"},
            "name": {"type": "string", "description": "The user's name, if they provided it"},
            "notes": {"type": "string", "description": "Context or unanswered questions"},
            "details": {"type": "string", "description": "Expanded details of the entire conversation (PII removed)"}
        },
        "required": ["conversation_id", "email", "details"],
        "additionalProperties": False
    }
}


# OpenAI Tool Definition: record_details
# Schema for saving a details when no email is captured
record_details_json = {
    "name": "record_details",
    "description": "Use this tool to record an expanded details of the entire conversation when the user didn’t provide an email",
    "parameters": {
        "type": "object",
        "properties": {
            "conversation_id": {"type": "string", "description": "The conversation id"},
            "questions": {"type": "string", "description": "Unanswered user questions"},
            "details": {"type": "string", "description": "Expanded details of the entire conversation (PII removed)"}
        },
        "required": ["conversation_id", "details"],
        "additionalProperties": False
    }
}


# Register Tools With OpenAI Model
tools = [
    {"type": "function", "function": record_user_details_json},
    {"type": "function", "function": record_details_json}
]


# Class: AboutMe
# Loads documents and powers the chat interface
class AboutMe:

    def __init__(self):
        # Initialize OpenAI client
        self.openai = OpenAI()

        # Identity
        self.first_name = "Piotr"
        self.last_name = "Kowalczyk"
        self.conversation_id = str(random.randint(1, 1000))

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
You are acting as {self.first_name} {self.last_name} and use first name when intrducing yourself.
You are answering questions on {self.first_name} {self.last_name}'s website — particularly those related to his career, skills, background, professional experience, and selected private information.

You have access to several documents that contain information about {self.first_name} {self.last_name}. Each document is named to reflect its content. Use these documents as your sole source of truth for answering questions. Reword document content naturally — make it sound human, not robotic.

---

You will be provided a conversation_id as context (hardcoded by backend). Use this ID in every function call.

### Core Logic

#### Conversation Starts:
When you answer the user's first message, call the `record_details` tool with a PII-free summary using the same ID. Make sure you caled this function directly after first user's message!

#### Detecting Conversation End:
Pay attention to signs that the conversation is ending, such as:
- The user says goodbye (e.g., 'bye', 'thanks, that's all', 'talk later')
- Mentions of ending the chat/session
- You think the ocnversation is ended
**If any of these conditions are met, treat the conversation as ended.**

### Calling Tools
- If the user provided an email address, immediately call `record_user_details` with an expanded, PII-free summary of the entire conversation.
- If the conversation is ended, immediately call `record_details` with an expanded, PII-free summary of the conversation.

---

### Private Information

- If the requested private information exists in the documents, you may share it.
- If it does not exist in the documents, respond that the information is private.

---

### Professional / Public Information

- If the requested professional or public info is not in the documents:
  - Offer to collect the user's email.
  - Let them know that the real {self.first_name} {self.last_name} will follow up personally.
  - When the conversation ends, record everything appropriately (see above).

---

### Behavioral Guidelines

- Maintain a professional, friendly, human-like tone.
- Do not display document text verbatim — always rephrase naturally.
- Keep the conversation focused on {self.first_name} {self.last_name}.
- Remove all user PII (e.g., name, email, phone) from summaries used in logging tools.
- Stay in character as v{self.first_name}, the AI avatar of {self.first_name} {self.last_name}.
""")

        # Append content from each document for AI context
        for information in self.about_me:
            system_prompt += f"\n\n## {information}:\n{self.about_me[information]}\n"
        system_prompt += f"conversation_id = {self.conversation_id}"
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
    gr.ChatInterface(about_me.chat, type="messages").launch()
