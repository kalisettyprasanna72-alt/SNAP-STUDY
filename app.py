import json
import time

import streamlit as st
from google import genai
from google.genai import types
from twilio.base.exceptions import TwilioException
from twilio.rest import Client

from prompts import (
    SUMMARY_REQUEST_PROMPT,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Snap & Study",
    page_icon="📸",
    layout="centered",
)


# ============================================================
# CONFIGURATION
# ============================================================

SUPPORTED_IMAGE_TYPES = [
    "jpg",
    "jpeg",
    "png",
]


# ============================================================
# SECRET HELPER
# ============================================================

def get_secret(key, default=None):
    """
    Safely read a value from Streamlit secrets.
    """

    try:
        value = st.secrets.get(key, default)
    except Exception:
        value = default

    return value if value is not None else default


# ============================================================
# GEMINI MODEL
# ============================================================

MODEL_NAME = (
    get_secret(
        "GEMINI_MODEL",
        "gemini-2.5-flash",
    )
    or "gemini-2.5-flash"
)


# ============================================================
# GEMINI CLIENT
# ============================================================

@st.cache_resource
def get_gemini_client():
    """
    Create and cache the Gemini client.
    """

    api_key = get_secret(
        "GEMINI_API_KEY"
    )

    if not api_key:
        return None

    try:
        return genai.Client(
            api_key=api_key
        )

    except Exception:
        return None


# ============================================================
# TWILIO CLIENT
# ============================================================

@st.cache_resource
def get_twilio_client():
    """
    Create and cache the Twilio client.
    """

    account_sid = get_secret(
        "TWILIO_ACCOUNT_SID"
    )

    auth_token = get_secret(
        "TWILIO_AUTH_TOKEN"
    )

    if not account_sid or not auth_token:
        return None

    try:
        return Client(
            account_sid,
            auth_token,
        )

    except Exception:
        return None


# ============================================================
# GEMINI CHAT
# ============================================================

def ensure_chat():
    """
    Create a Gemini chat if one does not already exist.
    """

    if (
        "chat" not in st.session_state
        or st.session_state.chat is None
    ):

        client = get_gemini_client()

        if client is None:

            st.session_state.chat = None

            return None

        try:

            st.session_state.chat = (
                client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    ),
                )
            )

        except Exception:

            st.session_state.chat = None

    return st.session_state.chat


# ============================================================
# MESSAGE RENDERING
# ============================================================

def render_message(message):
    """
    Display a message in the Streamlit chat interface.
    """

    with st.chat_message(
        message["role"]
    ):

        if message["kind"] == "text":

            st.write(
                message["content"]
            )

        elif message["kind"] == "image":

            image_content = message["content"]

            if isinstance(
                image_content,
                (bytes, bytearray),
            ):

                st.image(
                    image_content,
                    use_container_width=True,
                )

            elif image_content:

                st.image(
                    image_content,
                    use_container_width=True,
                )


# ============================================================
# ADD MESSAGE
# ============================================================

def add_message(
    role,
    kind,
    content,
):
    """
    Save and immediately display a message.
    """

    if "messages" not in st.session_state:

        st.session_state.messages = []

    message = {
        "role": role,
        "kind": kind,
        "content": content,
    }

    st.session_state.messages.append(
        message
    )

    render_message(
        message
    )


# ============================================================
# ASK GEMINI
# ============================================================

def ask_gemini(parts):
    """
    Send text/image content to Gemini and return the answer.
    """

    chat = ensure_chat()

    if chat is None:

        return (
            "⚠️ Gemini is not configured yet.\n\n"
            "Please add your `GEMINI_API_KEY` to "
            "`.streamlit/secrets.toml`."
        )

    max_retries = 3

    for attempt in range(
        max_retries
    ):

        try:

            response = chat.send_message(
                parts
            )

            response_text = getattr(
                response,
                "text",
                None,
            )

            if response_text:

                return response_text

            return (
                "⚠️ Gemini returned an empty response."
            )

        except Exception as exc:

            error_message = str(exc)

            # ------------------------------------------------
            # 503 / UNAVAILABLE
            # ------------------------------------------------

            if (
                "503" in error_message
                or "UNAVAILABLE" in error_message
            ):

                if attempt < max_retries - 1:

                    time.sleep(2)

                    continue

                return (
                    "⚠️ Gemini is temporarily busy.\n\n"
                    "Please try again in a few seconds."
                )

            # ------------------------------------------------
            # 429 / QUOTA
            # ------------------------------------------------

            if (
                "429" in error_message
                or "RESOURCE_EXHAUSTED"
                in error_message
            ):

                return (
                    "⚠️ Gemini API quota has been reached.\n\n"
                    "Please wait until the quota resets or "
                    "use a Gemini API project with available quota."
                )

            # ------------------------------------------------
            # AUTHENTICATION
            # ------------------------------------------------

            if (
                "401" in error_message
                or "API_KEY" in error_message
                or "authentication"
                in error_message.lower()
                or "unauthenticated"
                in error_message.lower()
            ):

                return (
                    "⚠️ There is a problem with your Gemini API key.\n\n"
                    "Please check your `.streamlit/secrets.toml` file."
                )

            # ------------------------------------------------
            # MODEL NOT FOUND
            # ------------------------------------------------

            if (
                "404" in error_message
                or "NOT_FOUND" in error_message
                or "not found"
                in error_message.lower()
            ):

                return (
                    "⚠️ The Gemini model configured for this app "
                    "is not available.\n\n"
                    f"Current model: `{MODEL_NAME}`\n\n"
                    "Please change GEMINI_MODEL to a model available "
                    "in your Google AI project."
                )

            # ------------------------------------------------
            # OTHER ERROR
            # ------------------------------------------------

            return (
                "⚠️ Sorry, something went wrong.\n\n"
                f"{exc}"
            )

    return (
        "⚠️ Unable to get a response from Gemini."
    )


# ============================================================
# SUMMARY PROMPT
# ============================================================

def build_summary_prompt(messages):
    """
    Convert the conversation into a summary prompt.
    """

    lines = []

    for message in messages:

        role = message.get(
            "role",
            "user",
        )

        kind = message.get(
            "kind",
            "text",
        )

        content = message.get(
            "content",
            "",
        )

        if kind == "image":

            label = "[Uploaded study image]"

        elif isinstance(
            content,
            str,
        ):

            label = content.strip()

        else:

            label = "[Study material]"

        if label:

            lines.append(
                f"{role.title()}: {label}"
            )

    transcript = "\n".join(
        lines
    )

    return (
        f"{SUMMARY_REQUEST_PROMPT}\n\n"
        f"Conversation:\n{transcript}"
    )


# ============================================================
# GENERATE SUMMARY
# ============================================================

def generate_summary_message():
    """
    Generate a study summary using Gemini.
    """

    client = get_gemini_client()

    if client is None:

        return (
            "⚠️ Gemini is not configured.\n\n"
            "Add your API key to "
            "`.streamlit/secrets.toml`."
        )

    messages = st.session_state.get(
        "messages",
        [],
    )

    if not messages:

        return (
            "No study conversation is available "
            "to summarize."
        )

    summary_prompt = build_summary_prompt(
        messages
    )

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=summary_prompt,
        )

        response_text = getattr(
            response,
            "text",
            None,
        )

        if response_text:

            return response_text

    except Exception as exc:

        return (
            "⚠️ Summary generation failed.\n\n"
            f"{exc}"
        )

    return (
        "⚠️ No study summary could be generated."
    )


# ============================================================
# WHATSAPP TEXT CLEANING
# ============================================================

def clean_whatsapp_text(text):
    """
    Keep useful formatting while respecting message size.
    """

    if not text:

        return (
            "No study summary available."
        )

    text = str(text).strip()

    # Keep the message reasonably small.
    if len(text) > 1500:

        text = (
            text[:1500]
            + "..."
        )

    return text


# ============================================================
# WHATSAPP NUMBER NORMALIZATION
# ============================================================

def normalize_whatsapp_number(number):
    """
    Convert common user-entered phone formats
    into a simple international format.
    """

    if not number:

        return None

    number = str(
        number
    ).strip()

    number = (
        number
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if not number.startswith("+"):

        return None

    return number


# ============================================================
# SEND WHATSAPP
# ============================================================

def send_whatsapp(
    to_number,
    user_name,
    summary,
):
    """
    Send the study summary using a Twilio WhatsApp template.
    """

    # --------------------------------------------------------
    # CHECK DESTINATION NUMBER
    # --------------------------------------------------------

    if not to_number:

        return (
            False,
            "Add a WhatsApp number in onboarding.",
        )

    # --------------------------------------------------------
    # NORMALIZE DESTINATION NUMBER
    # --------------------------------------------------------

    to_number = normalize_whatsapp_number(
        to_number
    )

    if not to_number:

        return (
            False,
            "Enter the WhatsApp number in international "
            "format, for example +919876543210.",
        )

    # --------------------------------------------------------
    # GET TWILIO CLIENT
    # --------------------------------------------------------

    twilio_client = get_twilio_client()

    if twilio_client is None:

        return (
            False,
            "Twilio credentials are missing from "
            "`.streamlit/secrets.toml`.",
        )

    # --------------------------------------------------------
    # READ TWILIO SETTINGS
    # --------------------------------------------------------

    twilio_from = get_secret(
        "TWILIO_WHATSAPP_FROM"
    )

    content_sid = get_secret(
        "TWILIO_CONTENT_SID"
    )

    # --------------------------------------------------------
    # CHECK FROM NUMBER
    # --------------------------------------------------------

    if not twilio_from:

        return (
            False,
            "TWILIO_WHATSAPP_FROM is missing "
            "from secrets.toml.",
        )

    # --------------------------------------------------------
    # CHECK CONTENT SID
    # --------------------------------------------------------

    if not content_sid:

        return (
            False,
            "TWILIO_CONTENT_SID is missing "
            "from secrets.toml.",
        )

    # --------------------------------------------------------
    # CLEAN CONTENT SID
    # --------------------------------------------------------

    content_sid = str(
        content_sid
    ).strip()

    # --------------------------------------------------------
    # CHECK CONTENT SID FORMAT
    # --------------------------------------------------------

    if not content_sid.startswith("HX"):

        return (
            False,
            "❌ Invalid Content SID format.\n\n"
            "TWILIO_CONTENT_SID should start with HX.",
        )

    # --------------------------------------------------------
    # CLEAN SUMMARY
    # --------------------------------------------------------

    cleaned_summary = clean_whatsapp_text(
        summary
    )

    # --------------------------------------------------------
    # The configured template should use {{1}} for the name
    # and {{2}} for the generated study summary.

    content_variables = json.dumps(
        {
            "1": str(user_name),
            "2": cleaned_summary,
        },
        ensure_ascii=False,
    )

    # --------------------------------------------------------
    # SEND WHATSAPP
    # --------------------------------------------------------

    try:

        message = twilio_client.messages.create(
            from_=twilio_from,
            to=f"whatsapp:{to_number}",
            content_sid=content_sid,
            content_variables=content_variables,
        )

        return (
            True,
            message.sid,
        )

    # --------------------------------------------------------
    # TWILIO ERROR
    # --------------------------------------------------------

    except TwilioException as exc:

        error_code = str(
            getattr(exc, "code", "") or ""
        )
        error_message = str(
            getattr(exc, "msg", None) or exc
        )
        safe_error_message = error_message

        for secret_name in (
            "GEMINI_API_KEY",
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_WHATSAPP_FROM",
            "TWILIO_CONTENT_SID",
        ):

            secret_value = get_secret(secret_name)

            if secret_value:

                safe_error_message = safe_error_message.replace(
                    str(secret_value),
                    "[redacted]",
                )

        lower_error_message = error_message.lower()

        if error_code == "21655" or "21655" in error_message:

            explanation = (
                "The Content SID or template is invalid or unavailable "
                "for the configured sender/account. Confirm that the "
                "SID belongs to a template available to this Twilio "
                "WhatsApp sender and Trial account."
            )

        elif error_code == "20003" or "20003" in error_message:

            explanation = (
                "The Trial account does not have access to the attempted "
                "Content API operation. This app sends with "
                "`messages.create` and must not use Content API fetch "
                "operations. Confirm the sender and account setup in "
                "Twilio Console."
            )

        elif (
            error_code in {"63015", "21608"}
            or any(
                phrase in lower_error_message
                for phrase in (
                    "trial",
                    "not verified",
                    "not joined",
                    "join the sandbox",
                    "sandbox",
                )
            )
        ):

            explanation = (
                "For a Twilio WhatsApp Trial, the recipient must be "
                "verified or joined to the Twilio WhatsApp Trial "
                "(Sandbox). Also confirm that the configured template "
                "is available to the Trial account."
            )

        elif (
            any(
                phrase in lower_error_message
                for phrase in (
                    "authentication",
                    "authenticate",
                    "invalid account sid",
                    "auth token",
                )
            )
            or error_code in {"20004", "20005"}
        ):

            explanation = (
                "Twilio authentication failed. Check "
                "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in "
                "`.streamlit/secrets.toml`."
            )

        else:

            explanation = "Twilio rejected the WhatsApp message."

        return (
            False,
            "❌ WhatsApp sending failed.\n\n"
            f"{explanation}\n\n"
            f"Twilio error: {safe_error_message}",
        )


# ============================================================
# SESSION STATE
# ============================================================

if "onboarded" not in st.session_state:

    st.session_state.onboarded = False


if "messages" not in st.session_state:

    st.session_state.messages = []


if "chat" not in st.session_state:

    st.session_state.chat = None


if "name" not in st.session_state:

    st.session_state.name = "Student"


if "whatsapp_number" not in st.session_state:

    st.session_state.whatsapp_number = ""


# ============================================================
# ONBOARDING
# ============================================================

if not st.session_state.onboarded:

    st.title(
        "📸🧠 Snap & Study"
    )

    st.caption(
        "📚 Upload a question, diagram, or notes — "
        "or type your question — and learn it in simple language."
    )

    st.divider()

    with st.form(
        "onboarding_form"
    ):

        name = st.text_input(
            "Student name",
            placeholder="Enter your name",
        )

        whatsapp_number = st.text_input(
            "WhatsApp number",
            placeholder="+91XXXXXXXXXX",
            help=(
                "Enter the number in international format. "
                "Example: +919876543210"
            ),
        )

        submitted = st.form_submit_button(
            "Let's Study 🚀",
            use_container_width=True,
        )

    if submitted:

        # ----------------------------------------------------
        # NAME VALIDATION
        # ----------------------------------------------------

        if not name.strip():

            st.warning(
                "⚠️ Please enter your name "
                "before continuing."
            )

        # ----------------------------------------------------
        # WHATSAPP VALIDATION
        # ----------------------------------------------------

        elif not whatsapp_number.strip():

            st.warning(
                "⚠️ Please enter your WhatsApp number "
                "before continuing."
            )

        elif normalize_whatsapp_number(
            whatsapp_number
        ) is None:

            st.warning(
                "⚠️ Please enter your WhatsApp number "
                "in international format, "
                "e.g. +919876543210."
            )

        # ----------------------------------------------------
        # SUCCESSFUL ONBOARDING
        # ----------------------------------------------------

        else:

            st.session_state.name = (
                name.strip()
            )

            st.session_state.whatsapp_number = (
                whatsapp_number.strip()
            )

            st.session_state.chat = (
                ensure_chat()
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# ============================================================
# MAIN HEADER
# ============================================================

header_col, action_col, new_chat_col = st.columns(
    [4, 3, 2],
    vertical_alignment="center",
)


# ============================================================
# HEADER
# ============================================================

with header_col:

    st.title(
        "📸🧠 Snap & Study"
    )

    st.caption(
        f"Welcome, "
        f"{st.session_state.name}! "
        "Let's make learning simple."
    )


# ============================================================
# SEND SUMMARY BUTTON
# ============================================================

with action_col:

    if st.button(
        "📤 Send Summary",
        use_container_width=True,
    ):

        # ----------------------------------------------------
        # CHECK CHAT HISTORY
        # ----------------------------------------------------

        if not st.session_state.messages:

            st.warning(
                "⚠️ There is no study conversation "
                "to summarize yet."
            )

        else:

            # ------------------------------------------------
            # GENERATE SUMMARY
            # ------------------------------------------------

            with st.spinner(
                "🧠 Creating your study summary..."
            ):

                summary = (
                    generate_summary_message()
                )

            # ------------------------------------------------
            # SEND WHATSAPP
            # ------------------------------------------------

            success, info = send_whatsapp(
                st.session_state.get(
                    "whatsapp_number",
                    "",
                ),
                st.session_state.name,
                summary,
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if success:

                st.success(
                    "WhatsApp message sent successfully. ✅"
                )

                st.caption(
                    f"Message SID: {info}"
                )

            # ------------------------------------------------
            # ERROR
            # ------------------------------------------------

            else:

                st.error(
                    "Couldn't send via WhatsApp:\n\n"
                    f"{info}"
                )


# ============================================================
# NEW CHAT
# ============================================================

with new_chat_col:

    if st.button(
        "🔄 New Chat",
        use_container_width=True,
    ):

        with st.spinner(
            "Starting a new chat..."
        ):

            st.session_state.chat = None

            st.session_state.messages = []

            st.session_state.chat = (
                ensure_chat()
            )

        st.rerun()


# ============================================================
# DIVIDER
# ============================================================

st.divider()


# ============================================================
# DISPLAY CHAT HISTORY
# ============================================================

if not st.session_state.messages:

    welcome_message = (
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        )
    )

    add_message(
        "assistant",
        "text",
        welcome_message,
    )

else:

    for message in (
        st.session_state.messages
    ):

        render_message(
            message
        )


# ============================================================
# CHAT INPUT
# ============================================================

user_input = st.chat_input(
    "Ask a study question, or attach a photo of your notes 📸",
    accept_file=True,
    file_type=SUPPORTED_IMAGE_TYPES,
)


# ============================================================
# PROCESS USER INPUT
# ============================================================

if user_input:

    photo = None

    # --------------------------------------------------------
    # GET UPLOADED PHOTO
    # --------------------------------------------------------

    if getattr(
        user_input,
        "files",
        None,
    ):

        if len(
            user_input.files
        ) > 0:

            photo = (
                user_input.files[0]
            )

    text = user_input.text

    parts = []

    # ========================================================
    # IMAGE
    # ========================================================

    if photo is not None:

        photo_bytes = (
            photo.getvalue()
        )

        add_message(
            "user",
            "image",
            photo_bytes,
        )

        mime_type = (
            photo.type
            or "image/jpeg"
        )

        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=mime_type,
            )
        )

    # ========================================================
    # TEXT
    # ========================================================

    if text:

        add_message(
            "user",
            "text",
            text,
        )

        parts.append(
            text
        )

    # ========================================================
    # IMAGE WITHOUT TEXT
    # ========================================================

    elif photo is not None:

        parts.append(
            "Analyze this study material and explain "
            "the main concept in simple language. "
            "Identify the problem or topic, explain "
            "the important parts step by step, and "
            "give an example where useful."
        )

    # ========================================================
    # NOTHING ENTERED
    # ========================================================

    if not parts:

        st.warning(
            "⚠️ Please type a question "
            "or upload an image."
        )

        st.stop()

    # ========================================================
    # GEMINI RESPONSE
    # ========================================================

    with st.spinner(
        "🧠 Understanding your study material..."
    ):

        answer = ask_gemini(
            parts
        )

    # ========================================================
    # DISPLAY RESPONSE
    # ========================================================

    add_message(
        "assistant",
        "text",
        answer,
    )