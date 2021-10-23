import logging
import os
logging.basicConfig(level=logging.DEBUG)
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler

# load environment variables
load_dotenv()
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]


app = App()


@app.view("new-story")
def handle_submission(ack, body, client, view, logger):
    ack()
    #TODO create a new name if taken?
    input_data = view["state"]["values"]
    user = body["user"]["id"]    
    response = app.client.conversations_create(name=input_data['title']['plain_text_input-action']['value'], is_private=True)
    app.client.conversations_invite(channel=response["channel"]["id"], users=user)
    logger.info("HERE")
    logger.info(app.client.conversations_archive(channel=response["channel"]["id"]))
    
@app.command("/create_story")
def open_modal(ack, body, logger):
    # Acknowledge the request
    ack()
    # Call the views_open method using the built-in WebClient
    response = app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "new-story", 
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
                    "block_id": "title",
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
                    "block_id": "desc",
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
                    "block_id": "to",
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



# Add functionality here
from flask import Flask, request

flask_app = Flask(__name__)
#handler = SlackRequestHandler(app)
handler = SocketModeHandler(app, SLACK_APP_TOKEN)
handler.connect()
'''
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)
'''

if __name__ == "__main__":
    flask_app.run(debug=True)