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
MAX_NUM_CONNECTIONS = 10
