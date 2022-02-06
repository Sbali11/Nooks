from utils.app_home import NooksHome
from utils.nooks_alloc import NooksAllocation
from slack_bot import main, db

nooks_home = NooksHome(db=db)
nooks_alloc = NooksAllocation(db=db)
main(nooks_home, nooks_alloc)


from slack_bot import app 

if __name__ == "__main__":
    app.run(ssl_context='adhoc')
