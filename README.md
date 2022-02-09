# HumanisticManagement: Nooks

The Nooks bot allows members in the Slack workspace to 'bump' into each other by sparking and joining conversations you are interested in. The bot matches members to conversations in a way that optimizes for networks that are unlikely to exist outside of this framework using a member-dependent 'heterophily' factor and 
provides pathways to develop these ephemeral networks into long lasting connections. For more information about the bot, visit https://nooks.vercel.app/. 

## Tech Stack
The bot was developed Flask(with slack bolt API), and MongoDB for the Database. The github repo is setup to work with Digital Ocean. 

## Setting up 



### Set up Slack Workspace
If you're setting up a new workspace or creating a new bot, follow the steps outlined here: https://slack.dev/bolt-python/tutorial/getting-started. Make sure you've added the needed OAuth permissions. In particular, we are using the following permissions:

```
bot scopes = [
    "app_mentions:read",
    "pins:write",
    "channels:manage",
    "channels:read",
    "chat:write",
    "commands",
    "groups:read",
    "groups:write",
    "im:read",
    "im:write",
    "mpim:read",
    "mpim:write",
    "users.profile:read",
    "users:read",
    "files:write",
    "files:read",
    "channels:join",
]
user_scopes = [
    "channels:read",
    "channels:write",
    "groups:write",
    "chat:write",
    "files:read",
    "pins:write",
    "im:write",
    "mpim:write",
    "groups:read",
    "mpim:read",
    "im:read",
    "users:read",
]
```

### Set up environment locally
```
git clone https://github.com/Sbali11/HumanisticManagement.git
conda env create -f environment.yml
[Or]
pip install -r requirements.txt
```

Note: if you're using the conda environment and made some changes to the environment - you can update requirements.txt by running the following command in the conda environment, this allows the code to run in the Digital Ocean Interface
```
pip list --format=freeze > requirements.txt
```

Next, create a .env file in the HumanisticManagement folder, and add the following variables here (For more information, refer to: https://github.com/slackapi/bolt-python/tree/main/examples/flask)

```
// from the slack app workspace
SLACK_APP_TOKEN=
SLACK_SIGNING_SECRET=

[Bot token is ignored when the app is publicly distributed]
SLACK_BOT_TOKEN= 

[Client Secret and Client Id are used publicly distributed slack apps]
SLACK_CLIENT_SECRET=
SLACK_CLIENT_ID=


// link to your mongodb database
MONGODB_LINK=


// replace {{host}} to wherever your slack app is hosted
REDIRECT_URI="{{host}}/slack/oauth_redirect"

```



The current app is setup in order to be publicly distributed. In case you want to adapt the code for apps run on single workspaces, replace according to the instructions given under comments labelled: "# [SINGLE] Replace with ... "

### Running the bot
After installing the bot to the workspace, run the following command:
```
conda activate slackbot
python wsgi.py
```

## Repository Structure

The repository is set up to run using Digital Ocean. 
```
.
├── experiments                 
│   ├── PrioritySimulation.ipynb    # initial experiments to visualize the matching function
├── utils                           # utility functions for the bot 
│   ├── matching_algorithm          # code related to the matching process
│   |   ├── nooks_alloc.py          # contains the the class for matching members to nooks
│   ├── app_ui                      # helper functions for the bot ui 
│   |   ├── app_home.py             # the code to update the app home page
│   ├── constants.py                # all the constants used across the workspace
├── slack_bot.py                    # workflow and code for the slack bot backend and flask app backend
├── wsgi.py                         # file to run the app formatted to run on Digital ocean
└── README.md
```



