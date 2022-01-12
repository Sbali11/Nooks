from utils import NooksHome, NooksAllocation, get_member_vector
from slack_bot import main, db

nooks_home = NooksHome(db=db)
nooks_alloc = NooksAllocation(db=db)
main(nooks_home, nooks_alloc)


from slack_bot import app 

if __name__ == "__main__":
    app.run()
