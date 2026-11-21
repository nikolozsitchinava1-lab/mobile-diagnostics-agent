import getpass
import os
from langgraph.types import Command
from agent import build_graph

if not os.environ.get("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = getpass.getpass("Enter GROQ_API_KEY: ")

graph = build_graph()
thread_id = "cli-session-1"
config = {"configurable": {"thread_id": thread_id}}

print("Mobile Diagnostics CLI started. Type 'exit' to quit.\n")
while True:
    user_input = input("You: ")
    if user_input.strip().lower() == "exit":
        break

    result = graph.invoke({"messages": [("user", user_input)], "thread_id": thread_id}, config=config)
    snapshot = graph.get_state(config)

    if snapshot.next and snapshot.tasks and snapshot.tasks[0].interrupts:
        intr = snapshot.tasks[0].interrupts[0].value
        ans = input(f"\n[APPROVAL REQUIRED] {intr['message']} (yes/no): ")
        approved = ans.strip().lower() in ("yes", "y", "კი")
        result = graph.invoke(Command(resume=approved), config=config)

    print(f"Agent: {result['messages'][-1].content}\n")