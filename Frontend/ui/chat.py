import streamlit as st


def render_chat(messages, dispatch, bot_name="Sparky", student_first_name=None):
    who = f" for {student_first_name}" if student_first_name else ""
    st.markdown(f"<div class='coach'><div class='avatar'>⚡</div><div><b>{bot_name}</b><br>"
                f"<span>Personal study coach{who}</span></div></div>", unsafe_allow_html=True)
    with st.container(height=520, border=True):
        if not messages:
            st.caption("Say hi to get started.")
        for message in messages:
            with st.chat_message(message["role"], avatar="⚡" if message["role"] == "assistant" else None):
                st.markdown(message["content"])
    with st.form("chat_form", clear_on_submit=True):
        message = st.text_area(f"Message {bot_name}", key="chat_draft", height=90,
                               placeholder=f"Ask {bot_name}… e.g. “I'm wrecked Tuesday” or “What's on tomorrow?”",
                               label_visibility="collapsed")
        send = st.form_submit_button("Send", type="primary")
    if send:
        if not message.strip():
            st.warning("Type a message first.")
        else:
            dispatch({"type": "chat", "message": message.strip(), "timezone": "Europe/Dublin"})
