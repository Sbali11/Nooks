import logging
logging.basicConfig(level=logging.DEBUG)
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

# load environment variables
load_dotenv()

app = App()

@app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()


@app.command("/create_story")
def open_modal(ack, body, logger):
    # Acknowledge the request
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



# Add functionality here
from flask import Flask, request

flask_app = Flask(__name__)
handler = SlackRequestHandler(app)


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(debug=True)