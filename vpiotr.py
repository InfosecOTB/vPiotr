from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import smtplib
from pypdf import PdfReader
import gradio as gr


load_dotenv(override=True)

def send_email(subject, body):
    msg = f"Subject: {subject}\n\n{body}"
    print(msg)
    server = smtplib.SMTP(os.getenv("SMTP_SERVER"), os.getenv("SMTP_PORT"))
    server.starttls()
    server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
    server.sendmail(os.getenv("SMTP_USER"), os.getenv("SMTP_RECIPIENT"), msg)
    server.quit()


def record_user_details(email, name="Name not provided", notes="not provided"):
    send_email(f"New user interested in being in touch: {name}", f"Email: {email}\nNotes: {notes}")
    return {"recorded": "ok"}

def record_unknown_question(question):
    send_email("New question", f"Question: {question}")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch or has additional questions and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]


class AboutMe:

    def __init__(self):
        self.openai = OpenAI()
        self.first_name = "Piotr"
        self.last_name = "Kowalczyk"
        self.about_me = {}
        files= os.listdir("about_me")

        for document in files:
            if document.endswith(".pdf"):
                reader = PdfReader(f"about_me/{document}")
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                self.about_me[document.split(".")[0]] = text
                
            if document.endswith(".txt"):
                with open(f"about_me/{document}", "r", encoding="utf-8") as f:
                    self.about_me[document.split(".")[0]] = f.read()

    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
        return results
    
    def system_prompt(self):
        system_prompt = f"You are acting as AI avatar of {self.first_name} {self.last_name} with name v{self.first_name}. You are answering questions on {self.first_name} {self.last_name}'s website, \
particularly questions related to {self.first_name} {self.last_name}'s career, background, skills, experience and some private information. \
Your responsibility is to represent {self.first_name} {self.last_name} for interactions on the website as faithfully as possible. \
You are given a summary of {self.first_name} {self.last_name}'s background in couple of documentswhich you can use to answer questions. \
You are also given a summary of {self.first_name} {self.last_name}'s private information which you can use to answer questions. If private information is not listed, please answer that this is private information. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
Also, you should mention that real {self.first_name} {self.last_name} may answer the question if the email address will be provided and record the e-mail with record_user_details tool. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "
        for information in self.about_me:
            system_prompt += f"\n\n## {information}:\n{self.about_me[information]}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as v{self.first_name} AI avatar of {self.first_name} {self.last_name}."
        print(system_prompt)
        return system_prompt
    
    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            response = self.openai.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools)
            if response.choices[0].finish_reason=="tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content
    

if __name__ == "__main__":
    about_me = AboutMe()
    gr.ChatInterface(about_me.chat, type="messages").launch()
    