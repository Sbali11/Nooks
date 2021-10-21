# HumanisticManagement

Tech Stack:
We're using Flask for the backend(with slack bolt API), and MongoDB for the Database. 

## Setting up 

### Set up environment locally
'''
    git clone https://github.com/Sbali11/HumanisticManagement.git
    cd HumanisticManagament
    conda env create -f environment.yml
'''

- If you're working on the same workspace, ask to be added as a collaborator to bot (email balishreya1@gmail.com)
- Alternatively, if you're setting up a new workspace or creating a new bot, follow the steps outlined here: https://slack.dev/bolt-python/tutorial/getting-started. Make sure you've addded the needed OAuth permissions 

After you've done this, go to the corresponding folder(create a new one if you're creating a new bot) and add the environment variables in the .env file(Read more in the examples here: https://github.com/slackapi/bolt-python/tree/main/examples/flask). For a new bot, add the following code at the beginning of the script:

'''
    from dotenv import load_dotenv
    load_dotenv()
'''
This would load all the environment variables

### Running a bot

(Make sure the bot is installed in the workspace before these steps)

'''
    cd <name-of-bot>
    FLASK_APP=app.py FLASK_ENV=development flask run -p 3000
    (in a new terminal:)
    ngrok http 3000
'''


## Bots provided

### Stories
About: 
