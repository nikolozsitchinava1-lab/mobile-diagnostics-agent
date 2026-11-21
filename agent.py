import json
import os
import requests
import os
import requests
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt

load_dotenv()

# Simple in-memory booking database keyed by thread_id so users don't share data
BOOKINGS_DB: dict[str, list[dict]] = {}

# Tbilisi district coordinates (lat, lon) for OSRM distance calculation
TBILISI_DISTRICTS = {
    "saburtalo": (41.7225, 44.7490),
    "vake": (41.7095, 44.7565),
    "gldani": (41.7915, 44.8155),
    "didube": (41.7450, 44.7820),
    "isani": (41.6850, 44.8410),
    "samgori": (41.6820, 44.8750),
    "varketili": (41.6960, 44.8720),
    "rustavi": (41.5495, 44.9935),
    "mtskheta": (41.8456, 44.7186),
}

# --- EXTERNAL API 1: NHTSA VIN Decoder (Free, no key required) ---
@tool
def decode_vehicle_vin(vin: str) -> dict:
    """Decode a 17-character vehicle VIN using the NHTSA vPIC API to verify make, model, year, and engine compatibility."""
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin.strip()}?format=json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()["Results"][0]
    return {
        "make": data.get("Make") or "Unknown",
        "model": data.get("Model") or "Unknown",
        "year": data.get("ModelYear") or "Unknown",
        "engine_cylinders": data.get("EngineCylinders") or "Unknown",
        "fuel_type": data.get("FuelTypePrimary") or "Unknown",
    }

# --- EXTERNAL API 2: OSRM Driving Distance & Quote Calculator ---
@tool
def calculate_callout_quote(district: str, service_type: str) -> dict:
    """Calculate driving distance from central Tbilisi (Saburtalo base) and estimate call-out price in GEL.
    service_type must be either 'obd2_scan' or 'pre_purchase'.
    """
    key = district.strip().lower()
    dest = TBILISI_DISTRICTS.get(key)
    if not dest:
        return {
            "error": f"District '{district}' not in quick list. Available: {', '.join(TBILISI_DISTRICTS.keys())}"
        }

    base_lat, base_lon = TBILISI_DISTRICTS["saburtalo"]
    dest_lat, dest_lon = dest
    url = f"http://router.project-osrm.org/route/v1/driving/{base_lon},{base_lat};{dest_lon},{dest_lat}?overview=false"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    route = resp.json()["routes"][0]

    distance_km = round(route["distance"] / 1000, 1)
    duration_min = round(route["duration"] / 60)

    # Example pricing logic (adjust to your exact rates)
    base_fee = 50 if service_type == "obd2_scan" else 100
    distance_fee = round(distance_km * 1.5)  # 1.5 GEL/km buffer
    total_gel = base_fee + distance_fee

    return {
        "district": district,
        "service_type": service_type,
        "one_way_km": distance_km,
        "est_drive_minutes": duration_min,
        "estimated_price_gel": total_gel,
    }

# --- STATEFUL BOOKING TOOLS ---
@tool@tool
def create_booking(
    thread_id: str,
    car_info: str,
    district: str,
    service_type: str,
    estimated_price_gel: int,
    customer_contact: str,
    preferred_time: str = "As soon as possible",
) -> str:
    """Create and save a confirmed mobile auto diagnostics appointment."""  # <-- Must be present!
    bookings = BOOKINGS_DB.setdefault(thread_id, [])
@tool
def create_booking(
    thread_id: str,
    car_info: str,
    district: str,
    service_type: str,
    estimated_price_gel: int,
    customer_contact: str,
    preferred_time: str = "As soon as possible",
) -> str:
    """Create and save a confirmed mobile auto diagnostics appointment."""
    bookings = BOOKINGS_DB.setdefault(thread_id, [])
    booking = {
        "booking_id": len(bookings) + 1,
        "car_info": car_info,
        "district": district,
        "service_type": service_type,
        "estimated_price_gel": estimated_price_gel,
        "customer_contact": customer_contact,
        "preferred_time": preferred_time,
        "status": "confirmed",
    }
    bookings.append(booking)

    # --- SEND TELEGRAM NOTIFICATION TO YOUR PHONE ---
    tg_token = os.getenv("9255132474:AAHYO7ZOJf7294-ChWg_8kUrdbhzA79K1z4")
    tg_chat_id = os.getenv("1786717256")
    if tg_token and tg_chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={
                    "chat_id": tg_chat_id,
                    "text": f"🚗 ახალი ჯავშანი (#{booking['booking_id']}):\n{json.dumps(booking, ensure_ascii=False, indent=2)}",
                },
                timeout=5,
            )
        except Exception as e:
            print("Telegram notification failed:", e)
    # ------------------------------------------------

    return json.dumps({"message": "Booking confirmed!", "booking": booking}, ensure_ascii=False)

@tool
def decode_vehicle_vin(vin: str) -> str:
    """Decode a 17-character vehicle VIN using the NHTSA vPIC API to verify make, model, year, and engine compatibility."""
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin.strip()}?format=json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()["Results"][0]
    return json.dumps({
        "make": data.get("Make") or "Unknown",
        "model": data.get("Model") or "Unknown",
        "year": data.get("ModelYear") or "Unknown",
        "engine_cylinders": data.get("EngineCylinders") or "Unknown",
        "fuel_type": data.get("FuelTypePrimary") or "Unknown",
    }, ensure_ascii=False)

@tool
def calculate_callout_quote(district: str, service_type: str) -> str:
    """Calculate driving distance from central Tbilisi (Saburtalo base) and estimate call-out price in GEL.
    service_type must be either 'obd2_scan' or 'pre_purchase'.
    """
    key = district.strip().lower()
    dest = TBILISI_DISTRICTS.get(key)
    if not dest:
        return f"District '{district}' not in quick list. Available: {', '.join(TBILISI_DISTRICTS.keys())}"

    base_lat, base_lon = TBILISI_DISTRICTS["saburtalo"]
    dest_lat, dest_lon = dest
    url = f"http://router.project-osrm.org/route/v1/driving/{base_lon},{base_lat};{dest_lon},{dest_lat}?overview=false"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    route = resp.json()["routes"][0]

    distance_km = round(route["distance"] / 1000, 1)
    duration_min = round(route["duration"] / 60)
    base_fee = 50 if service_type == "obd2_scan" else 100
    distance_fee = round(distance_km * 1.5)
    total_gel = base_fee + distance_fee

    return json.dumps({
        "district": district,
        "service_type": service_type,
        "one_way_km": distance_km,
        "est_drive_minutes": duration_min,
        "estimated_price_gel": total_gel,
    }, ensure_ascii=False)

@tool
def list_bookings(thread_id: str) -> str:
    """List all scheduled mobile diagnostics bookings for the current user session."""
    bookings = BOOKINGS_DB.get(thread_id, [])
    if not bookings:
        return "No active bookings found for this session."
    return json.dumps(bookings, ensure_ascii=False)
@tool
def cancel_booking(thread_id: str, booking_id: int) -> str:
    """Cancel and delete a booking by its ID. Always pauses for human approval before deleting."""
    user_bookings = BOOKINGS_DB.get(thread_id, [])
    target = next((b for b in user_bookings if b["id"] == booking_id), None)
    if not target:
        return f"Booking #{booking_id} was not found."

    # Mandatory LangGraph interrupt() for human-in-the-loop confirmation
    approved = interrupt({
        "action": "cancel_booking",
        "booking_id": booking_id,
        "details": target,
        "message": f"Confirm cancellation of Booking #{booking_id} ({target['car']} in {target['district']})?",
    })

    if approved:
        BOOKINGS_DB[thread_id] = [b for b in user_bookings if b["id"] != booking_id]
        return f"Booking #{booking_id} has been canceled."
    return f"Cancellation aborted. Booking #{booking_id} remains active."

TOOLS = [
    decode_vehicle_vin,
    calculate_callout_quote,
    create_booking,
    list_bookings,
    cancel_booking,
]

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    thread_id: str

SYSTEM_PROMPT = """You are the AI assistant for a Mobile Auto Diagnostics service in Tbilisi, Georgia.
Respond in the same language the user writes in (Georgian or English).
Your job:
1. Qualify leads by collecting: Car Make/Model/Year (or 17-char VIN), Service needed (OBD2 diagnostic scan vs. Pre-purchase car inspection), Symptom/Issue, and Tbilisi District.
2. Use `decode_vehicle_vin` if the user provides a VIN.
3. Use `calculate_callout_quote` once you know their district and service type.
4. Use `create_booking` only when the user confirms they want to book. Always pass the exact `thread_id` provided in context.
5. If a user asks for complex module coding or custom electrical repairs, collect their car details and note that the technician will confirm a custom quote manually.
"""

def build_graph():
    llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0).bind_tools(TOOLS)
    def assistant_node(state: AgentState):
        sys_msg = SystemMessage(
            content=f"{SYSTEM_PROMPT}\nCurrent session thread_id: {state['thread_id']}"
        )
        response = llm.invoke([sys_msg] + state["messages"])
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("assistant", assistant_node)
    builder.add_node("tools", ToolNode(TOOLS))

    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")

    memory = InMemorySaver()
    return builder.compile(checkpointer=memory)