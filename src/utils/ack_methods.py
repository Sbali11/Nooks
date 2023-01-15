
def success_modal_ack(ack, body, view, logger, message, title="Success"):
    ack(
        response_action="update",
        view={
            "type": "modal",
            "callback_id": "success_close",
            "title": {"type": "plain_text", "text": title},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message,
                    },
                }
            ],
        },
    )

