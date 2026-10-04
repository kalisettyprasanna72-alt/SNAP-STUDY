# 📸🧠 Snap & Study

Snap & Study is an AI-powered study companion that helps students understand questions, diagrams, and notes. Ask a question or upload a study image to receive a clear, step-by-step explanation, then generate and send a concise revision summary through WhatsApp.

## Features

- AI-powered study assistance
- Text-based questions
- Image-based study questions
- Gemini-powered explanations
- AI-generated study summaries
- WhatsApp summary delivery using Twilio
- Streamlit interface

## Tech Stack

- Python
- Streamlit
- Google Gemini API
- Twilio WhatsApp API

## Architecture

```text
User
  → Streamlit
  → Gemini
  → Answer / Summary
  → Twilio
  → WhatsApp
```

Streamlit collects text questions and uploaded images. Gemini generates study explanations and summaries. When requested, the application passes the summary to Twilio for WhatsApp delivery.

## Project Structure

```text
snapstudy/
├── .streamlit/
│   └── secrets.toml.example  # Safe template for local configuration
├── app.py                    # Streamlit UI, Gemini chat, and Twilio integration
├── prompts.py                # Tutor, welcome, and summary prompts
├── requirements.txt          # Python dependencies
├── .gitignore                # Excludes secrets and local/generated files
└── README.md                 # Project documentation
```

Create `.streamlit/secrets.toml` locally to configure credentials. That file is intentionally ignored by Git and should never be committed.

## Installation

```bash
git clone <repository-url>
cd snapstudy
pip install -r requirements.txt
```

Optionally, create and activate a virtual environment before installing dependencies.

## Configuration

Create `.streamlit/secrets.toml` in the project directory. You can start from `.streamlit/secrets.toml.example` and replace each placeholder with your own values:

```toml
GEMINI_API_KEY = "your-gemini-api-key"
TWILIO_ACCOUNT_SID = "your-twilio-account-sid"
TWILIO_AUTH_TOKEN = "your-twilio-auth-token"
TWILIO_WHATSAPP_FROM = "whatsapp:+your-twilio-whatsapp-sender"
TWILIO_CONTENT_SID = "your-real-content-sid-starting-with-HX"
```

Use the real Content SID provided in your Twilio Console; the value above is only a placeholder. The configured WhatsApp template is expected to use `{{1}}` for the student's name and `{{2}}` for the generated summary. Keep all credentials in the local secrets file, never in source code or documentation.

## Run the Application

```bash
streamlit run app.py
```

## WhatsApp Setup

WhatsApp delivery requires a Twilio WhatsApp sender and a suitable message template configured for the account. For Twilio's WhatsApp Sandbox or a Trial account, follow Twilio's current setup instructions; recipients may need to verify or join the Sandbox. Confirm that the selected sender and template are available to the account. Trial-account restrictions can affect delivery, so a configured template is not a guarantee that every Trial message will be accepted.

Enter the destination number in international format, for example `+919876543210`. The app formats it as a WhatsApp destination when sending.

## Security

- Never commit `.streamlit/secrets.toml`, `.env` files, API keys, account identifiers, or authentication tokens.
- The repository's `.gitignore` excludes local secrets and common development artifacts.
- The example configuration contains placeholders only. Replace them in your local secrets file, not in the example.
- If a credential was committed or otherwise exposed, revoke or rotate it in the provider console.

## Future Improvements

- Persistent conversation history
- Study analytics and progress tracking
- Personalized learning plans
- PDF and document support
- Deployment guidance and hosted deployment
- More flexible WhatsApp template support
