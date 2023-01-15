from handlers.home import NooksHome
from matching_algorithm.nooks_alloc import NooksAllocation
from main import slack_app, main, db
from handlers.onboarding import Onboarding
from handlers.signup import Signup
from handlers.swiping import Swiping
from handlers.nook_channels import NookChannels
from handlers.guess_game import GuessGame
from handlers.survey import Survey
from handlers.settings import Settings
from handlers.beyond_nooks import BeyondNooks
from handlers.feedback import Feedback

nooks_home = NooksHome(db=db)
nooks_alloc = NooksAllocation(db=db)
onboarding = Onboarding(slack_app, db, nooks_home, nooks_alloc)
signup = Signup(slack_app, db, nooks_home, nooks_alloc)
swiping = Swiping(slack_app, db, nooks_home)
nooks_channels = NookChannels(slack_app, db, nooks_home, nooks_alloc)
guess_game = GuessGame(slack_app, db)
survey = Survey(slack_app, db)
settings = Settings(slack_app, db, nooks_home, nooks_alloc)
beyond_nooks = BeyondNooks(slack_app, db)
feedback = Feedback(slack_app, db)

main(nooks_home, nooks_alloc, onboarding, signup, swiping, nooks_channels, guess_game, survey, settings, beyond_nooks, feedback)


from main import app 

if __name__ == "__main__":
    app.run(ssl_context='adhoc')
