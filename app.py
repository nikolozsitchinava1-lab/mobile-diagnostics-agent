import uuid
import streamlit as st
from langgraph.types import Command
from agent import build_graph

st.set_page_config(page_title="Mobile Auto Diagnostics AI", page_icon="🚗")
st.title("🚗 Mobile Auto Diagnostics Assistant")
st.caption("OBD2 დიაგნოსტიკა და ყიდვისწინა შემოწმება გამოძახებით თბილისში")

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pending_interrupt" not in st.session_state:
    st.session_state.pending_interrupt = None

config = {"configurable": {"thread_id": st.session_state.thread_id}}

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle Human-in-the-Loop Approval Buttons when interrupt() fires
if st.session_state.pending_interrupt:
    info = st.session_state.pending_interrupt
    st.warning(info.get("message", "ადასტურებთ მოქმედებას?"))
    col1, col2 = st.columns(2)
    if col1.button("✅ დადასტურება (Confirm)"):
        res = st.session_state.graph.invoke(Command(resume=True), config=config)
        reply = res["messages"][-1].content
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.session_state.pending_interrupt = None
        st.rerun()
    if col2.button("❌ უარი (Cancel)"):
        res = st.session_state.graph.invoke(Command(resume=False), config=config)
        reply = res["messages"][-1].content
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.session_state.pending_interrupt = None
        st.rerun()

if prompt := st.chat_input("მომწერეთ მანქანის მოდელი, პრობლემა და უბანი..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        result = st.session_state.graph.invoke(
            {"messages": [("user", prompt)], "thread_id": st.session_state.thread_id},
            config=config,
        )
        # Check if graph paused on interrupt()
        state_snapshot = st.session_state.graph.get_state(config)
        if state_snapshot.next and state_snapshot.tasks and state_snapshot.tasks[0].interrupts:
            st.session_state.pending_interrupt = state_snapshot.tasks[0].interrupts[0].value
            st.rerun()
        else:
            reply = result["messages"][-1].content
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)
    except Exception as e:
        st.error(f"API შეცდომა ან ლიმიტი ამოიწურა: {e}")