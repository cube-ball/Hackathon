import streamlit as st


def render_chat(messages, dispatch):
    st.subheader("Tell us about your week")
    st.caption("Example: I have a report due Friday and work Wednesday evening.")
    for message in messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    with st.form("chat_form", clear_on_submit=False):
        message = st.text_area("Your message", key="chat_draft", height=130)
        send = st.form_submit_button("Send", type="primary")
    if send:
        if not message.strip():
            st.warning("Type a message first.")
        else:
            dispatch({"type": "chat", "message": message.strip(), "timezone": "Europe/Dublin"})
