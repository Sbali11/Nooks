# Nooks

The Nooks bot allows members in the Slack workspace to 'bump' into each other by sparking and joining conversations they are interested in. For more information about the bot, visit https://nooks.vercel.app/. 

## Tech Stack
The bot was developed Flask(with slack bolt API), and MongoDB for the Database. The github repo is setup to work with Digital Ocean. 

## App Set Up

### Set up Slack Workspace

#### Create Bot
If you're setting up a new workspace or creating a new bot, follow the steps outlined here: https://slack.dev/bolt-python/tutorial/getting-started. 

#### Enable Socket Mode
The Nooks bot uses the socket mode to operate, so you would have to enable the socket mode in the bot workspace settings

#### Add OAuth & Permissions
The Nooks Bot  requires the following permissions:

```
Bot Token Scopes-
app_mentions:read, pins:write, channels:manage, channels:read, chat:write, commands, groups:read, groups:write, im:read, im:write, mpim:read, mpim:write, users.profile:read, users:read, files:write, files:read, channels:join

User Token Scopes-
channels:read, channels:write, groups:write, chat:write, files:read, pins:write, im:write, mpim:write, groups:read, mpim:read, im:read, users:read
```

#### Event Subscriptions
Subscription to events allows the bot to 'listen' to events and take the appropriate actions. Subscribe to the following events for the app: 
```
Bot Events-
app_home_opened, app_mention, im_history_changed, member_joined_channel, message.channels, message.groups, message.im, team_join

```

#### [Optional] Enable Public Distribution of the App
To enable the public distribution of the app, go to Manage Distribution in the Slack App page for the bot, follow the listed steps and "Enable Public Distribution". You *don't* need to make any changes to the code as the repository assumes public distribution

#### Install to workspace
If you're using the publicly distributed app(the default option for the github repository), just head over to the {{host}}/slack/install and click on the install button. If you've updated the code to only run on a single workspace, install to the workspace by heading over to the app settings page

-----


### Create a MongoDB Cluster
Follow the steps listed here https://www.mongodb.com/basics/create-database

-----

### Set up environment locally

#### Install required packages
```
git clone https://github.com/Sbali11/Nooks.git
conda env create -f environment.yml
[Or]
pip install -r requirements.txt
```



#### Set Environment Variables
Next, create a .env file in the Nooks folder, and add the following variables here (For more information, refer to: https://github.com/slackapi/bolt-python/tree/main/examples/flask)

```
// from the slack app workspace
SLACK_APP_TOKEN=
SLACK_SIGNING_SECRET=

[Bot token is ignored when the app is publicly distributed]
SLACK_BOT_TOKEN= 

[Client Secret and Client Id are used in publicly distributed slack apps]
SLACK_CLIENT_SECRET=
SLACK_CLIENT_ID=


// link to your mongodb database
MONGODB_LINK=


// replace {{host}} to wherever your slack app is hosted
REDIRECT_URI="{{host}}/slack/oauth_redirect"

```

The current app is setup in order to be publicly distributed. In case you want to adapt the code for apps run on single workspaces, replace according to the instructions given under comments labelled: "# [SINGLE] Replace with ... "

#### Run the bot
After installing the bot to the workspace, run the following command:
```
conda activate slackbot
python src/wsgi.py
```

-----

### [Optional] Create a Digital Ocean Instance
The code in this repository is already structured to run on Digital Ocean(https://www.digitalocean.com/). To run the code on digital ocean, create a new "App", link the app to your github repository(or upload your code manually). After the app has been created, go to settings and edit the App-level environment variables to include the values stored in your .env file. Make sure you don't include any double quotes to indicate strings here-they would automatically be loaded as the correct values in the python file. 

Note: If you're using the conda environment and made some changes to the environment - you can update requirements.txt by running the following command in the conda environment, this allows the code to run in the Digital Ocean Interface
```
pip list --format=freeze > requirements.txt
```

-----

