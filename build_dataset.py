import json, pandas as pd

IN = "data_raw.json"
OUT = "dataset.csv"

def featurize(rec):
    s = rec.get("summary", {})
    features = {
        "handle": rec.get("handle"),
        "rating": rec.get("rating") or 0,
        "maxRating": rec.get("maxRating") or 0,
        "total_submissions": s.get("total_submissions") or 0,
        "accepted_submissions": s.get("accepted_submissions") or 0,
        "distinct_problems": s.get("distinct_problems") or 0,
        "avg_problem_rating": s.get("avg_problem_rating") or 0
    }
    features["accept_rate"] = (
        features["accepted_submissions"] / features["total_submissions"]
        if features["total_submissions"] > 0
        else 0
    )
    return features

def main():
    data = json.load(open(IN))
    rows = [featurize(r) for r in data]
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print("✅ Saved", OUT)

if __name__ == "__main__":
    main()
