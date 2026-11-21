import os
import requests
from fastapi import FastAPI, Request, Response, HTTPException
from langgraph.types import Command
from agent import build_graph

app = FastAPI()
graph = build_graph()

VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")

def send_fb_message(recipient_id: str, text: str):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    requests.post(url, params=params, json=payload, timeout=10)

# 1. Meta Webhook Verification Endpoint
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")

# 2. Incoming Facebook Messenger Events
@app.post("/webhook")
async def handle_messages(request: Request):
    body = await request.json()
    if body.get("object") == "page":
        for entry in body.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]
                if "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"]
                    config = {"configurable": {"thread_id": f"fb_{sender_id}"}}
                    snapshot = graph.get_state(config)

                    # If waiting on cancellation confirmation, interpret user's reply
                    if snapshot.next and snapshot.tasks and snapshot.tasks[0].interrupts:
                        approved = user_text.strip().lower() in ("კი", "დადასტურება", "yes", "ok")
                        result = graph.invoke(Command(resume=approved), config=config)
                    else:
                        result = graph.invoke(
                            {"messages": [("user", user_text)], "thread_id": f"fb_{sender_id}"},
                            config=config,
                        )
                        new_snap = graph.get_state(config)
                        if new_snap.next and new_snap.tasks and new_snap.tasks[0].interrupts:
                            prompt_msg = new_snap.tasks[0].interrupts[0].value["message"]
                            send_fb_message(sender_id, f"{prompt_msg} (მომწერეთ 'კი' ან 'არა')")
                            return {"status": "ok"}

                    reply_text = result["messages"][-1].content
                    send_fb_message(sender_id, reply_text)
    return {"status": "ok"}