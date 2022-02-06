EPSILON = 0.001

SAME_HOMOPHILY_FACTORS = {
    "Gender"
}
RANGE_HOMOPHILY_FACTORS = {
    "Age", "Role", "Number of years in the organization"
}
HOMOPHILY_FACTORS = {
    "Age": {
        "18-25": 0,
        "26-35": 1,
        "35-50": 2,
        ">50": 3
    },
    "Role": {
        "Professor": 0,
        "PhD Student": 1,
        "Master's Student": 2,
        "Undergrad Student": 3,
    },
    "Gender": {"Male": 0, "Female": 1, "Non-Binary": 2, "Prefer Not to Disclose": 3},
    "Number of years in the organization": {
        "0-1 yrs": 0,
        "1-5 yrs": 1,
        "5-10 yrs": 2,
        ">10 yrs": 3,
    },
}

def get_fibonacci(n):
    # calculate fibonacci series 
    i = 0
    j = 1
    fib = []
    fib.append(j)
    for i in range(n-1):
        new_i = j
        j = i + j
        i = new_i 
        fib.append(j)
    return fib

FIBONACCI = get_fibonacci(len(HOMOPHILY_FACTORS))



def get_homophily_question_options(factor):
    options = HOMOPHILY_FACTORS[factor]
    options_list = [(options[key], key) for key in options]
    options_list.sort()
    return [question for _, question in options_list]


SIGNUP_QUESTIONS = {
    "Step 1": {
        factor: get_homophily_question_options(factor) for factor in HOMOPHILY_FACTORS
    },
    "Step 2": [
        "I get frustrated when others at work are not around as much as I would like",
        "When I’m not connected to people at work, I feel somewhat anxious and insecure",
        "I feel comfortable sharing my private thoughts and feelings with others at work",
        "When I am at work I don’t mind asking other people for comfort, advice, or help",
        "Sometimes I don’t feel as if I belong in my organization.",
        "I feel very different from most other employees at my organization.",
        "When I am at work, people are around me but not with me",
        "At work I can find companionship when I want it",
        "I talk to people in my organization about shared interests.",
    ],
}

CONSENT_FORM = {
    "Summary": 'This study seeks to understand how to build software to improve workplace connectedness and professional networks by optimally structuring online informal communication in organizations. Our Slack plugin creates opportunities for people to "virtually bump into" each other, enabling opportunistic shared experiences grounded in common interests. It allows workspace members to anonymously create short-lived conversations around specific topics(this could be anything from discussions around co-occurring events: "Thoughts on the talk from earlier today" to directed workrelated brainstorming feedback). Members, across the workspace, receive a curated daily list of invites to conversations, allowing them to join ongoing conversations and interact and bond with others over common interests. You MAY want to participate because: this application is designed to help expand your professional network and improve workplace connectedness and wellbeing. It can improve socialization patterns in workspaces- fostering inclusivity, sparking connections between individuals, and inspiring collaboration and knowledge sharing.',
    "Purpose": "This study seeks to understand how to build software to improve workplace connectedness and professional networks by optimally structuring online informal communication in organizations. By reducing shared experiences between individuals, remote work has caused organizations to become less interconnected. Organization communication networks have become static and insular with fewer new connections being added and fewer information flows across disparate parts of organizations. Our research seeks to design software to structure interaction between peers and improve socialization patterns in workspaces- fostering inclusivity, sparking connections between diverse individuals, and inspiring collaboration and knowledge sharing. ",
    "Procedures": 'This application allows workspace members to anonymously create short-lived conversations around specific topics(this could be anything from discussions around co-occurring events: "Thoughts on the talk from earlier today" to directed workrelated brainstorming feedback). Members, across the workspace, receive a curated daily list of invites to conversations, allowing them to join ongoing conversations and interact and bond with others over common interests. In order to do this, our application requires you to create a user profile that will help us curate conversations recommended for you. At this time you will also be asked to fill up a survey for us to understand extant socialization in your workplace. The only data that will be stored on our secure server is your username, your user profile, and messages you’ve exchanged within conversation channels created by our application. You can use this application for as long as you like while we are still actively hosting it. We will continue to collect your data during this time. Weeks after using this application, we will request you to complete a survey for us to understand your experience using the system and to get your feedback. We may request a follow-up interview with some participants (which we would conduct remotely via Zoom), to understand longer-term use of this application.',
    "Participants": "Participation in this study is limited to individuals age 18 and older.",
    "Risks": "The risks and discomfort associated with participation in this study are no greater than those ordinarily encountered in daily life or during other online activities. Your data- your username and messages exchanges only within channels created by our application- are stored on a secure server and is encrypted between your computer and the server",
    "Benefits": "You may receive indirect benefits by participating in conversations with your colleagues which can expand your professional network and improve socialization patterns in your workspace- fostering inclusivity, sparking connections between individuals, and inspiring collaboration and knowledge sharing.",
    "Compensation": "There is no compensation for participation in this study. There will be no cost to you if you participate in this study",
    "Future Use of Information": "In the future, once we have removed all identifiable information from your data, we may use the data for our future research studies, or we may distribute the data to other researchers for their research studies. We would do this without getting additional informed consent from you (or your legally authorized representative). Sharing of data with other researchers will only be done in such a manner that you will not be identified.",
    "Confidentiality": "By participating in this research, you understand and agree that Carnegie Mellon may be required to disclose your consent form, data and other personally identifiable information as required by law, regulation, subpoena or court order. Otherwise, your confidentiality will be maintained in the following manner: Your data and consent form will be kept separate. Your consent form will be stored in a secure location on Carnegie Mellon property and will not be disclosed to third parties. By participating, you understand and agree that the data and information gathered during this study may be used by Carnegie Mellon and published and/or disclosed by Carnegie Mellon to others outside of Carnegie Mellon. However, your name, address, contact information and other direct personal identifiers will not be mentioned in any such publication or dissemination of the research data and/or results by Carnegie Mellon. Note that per regulation all research data must be kept for a minimum of 3 years. All identifiable information will be held on a secure server and will only be accessible to researchers. Access will be protected with public key encryption. All data transfers will be on encrypted channels. There is a risk of breach of confidentiality. The research team takes every precaution to prevent this from happening by storing data securely.",
    "Right to Ask Questions & Contact Information": "If you have any questions about this study, you should feel free to ask them by contacting the Principal Investigator Shreya Bali by phone(412-699-2178) or email(sbali@cs.cmu.edu). If you have questions later, desire additional information, or wish to withdraw your participation please contact the Principal Investigator by phone(412-699-2178) or e-mail(sbali@cs.cmu.edu). If you have questions pertaining to your rights as a research participant; or to report concerns to this study, you should contact the Office of Research integrity and Compliance at Carnegie Mellon University. Email: irb-review@andrew.cmu.edu . Phone: 412-268-1901 or 412-268-5460.",
    "Voluntary Participation": "Your participation in this research is voluntary. You may discontinue participation at any time during the research activity. You may print a copy of this consent form for your records. ",
}
NOOKS_BOT_NAME = "nooks-bot"
MAX_NUM_CONNECTIONS = 10
