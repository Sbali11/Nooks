import logging
import os
import re

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]

app = App(token=SLACK_BOT_TOKEN, name="Stories Bot")
logger = logging.getLogger(__name__)


@app.command("/create_story")
def open_modal(ack, body, logger):
    logger.info(body)
    # Acknowledge the shortcut request
    ack()
    # Call the views_open method using the built-in WebClient
    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": "Create a Story!"},
            "close": {"type": "plain_text", "text": "Close"},
            "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Let's start discussing :smile:."
                    }
                },
		        {
			        "type": "input",
			        "element": {
				        "type": "plain_text_input",
				        "action_id": "plain_text_input-action"
			        },
			        "label": {
				        "type": "plain_text",
				        "text": "Give your story an interesting title",
				        "emoji": True
			        }
		        }, 
		        {
			        "type": "input",
			        "element": {
				        "type": "plain_text_input",
				        "multiline": True,
				        "action_id": "plain_text_input-action"
			        },
			        "label": {
				        "type": "plain_text",
				        "text": "Add some initial thoughts",
				        "emoji": True
			        }
		        },
                {
                    "type": "section",
                    "block_id": "section678",
                    "text": 
                    {
                        "type": "mrkdwn",
                        "text": "Pick conversations to send the story to"
                    },
                    "accessory": 
                    {
                        "action_id": "text1234",
                        "type": "multi_conversations_select",
                        "placeholder": 
                        {
                            "type": "plain_text",
                            "text": "Select conversations"
                        }
                    }
                }
            ]
        }
    )


def main():
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    main()