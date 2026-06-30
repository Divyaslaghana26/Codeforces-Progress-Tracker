import requests, time, json

OUT = "data_raw.json"

# Sample handles — you can add more Codeforces usernames here
SAMPLE_HANDLES = [
    "tourist", "Petr", "Benq", "ecnerwala", "jiangly"
]

def fetch_user(handle):
    url = f"https://codeforces.com/api/user.info?handles={handle}"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["result"][0]

def fetch_user_status(handle, max_count=1000):
    url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count={max_count}"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["result"]

def summarize_submissions(subs):
    total = len(subs)
    accepted = sum(1 for s in subs if s.get("verdict") == "OK")
    problems = set()
    ratings = []
    for s in subs:
        pid = (s.get("problem", {}).get("contestId"), s.get("problem", {}).get("index"))
        problems.add(pid)
        r = s.get("problem", {}).get("rating")
        if r:
            ratings.append(r)
    return {
        "total_submissions": total,
        "accepted_submissions": accepted,
        "distinct_problems": len(problems),
        "avg_problem_rating": sum(ratings) / len(ratings) if ratings else None
    }

def main():
    out = []
    for handle in SAMPLE_HANDLES:
        try:
            user = fetch_user(handle)
            subs = fetch_user_status(handle, max_count=500)
            summary = summarize_submissions(subs)
            record = {
                "handle": handle,
                "rating": user.get("rating"),
                "maxRating": user.get("maxRating"),
                "organization": user.get("organization"),
                "country": user.get("country"),
                "summary": summary
            }
            print("Fetched", handle)
            out.append(record)
            time.sleep(1.2)  # be polite to API
        except Exception as e:
            print("Error", handle, e)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)

if __name__ == "__main__":
    main()
