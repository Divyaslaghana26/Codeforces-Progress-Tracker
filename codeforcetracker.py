"""
CP-Tracker (fixed)
Multi-platform tracker (Codeforces, LeetCode, CodeChef, AtCoder, HackerRank)
GUI: Tkinter + Matplotlib
Fixes included:
 - robust numeric parsing (no NaN passed to matplotlib)
 - guard pie/bar plotting for zero or missing data
 - safe contest rating plotting with label skipping
 - exception handling so GUI won't crash on API anomalies
"""

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import defaultdict, deque
from math import isnan, floor

# --------------------- Helpers for safe parsing ---------------------
def safe_int(x, default=0):
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return int(x)
        # remove commas if present
        return int(str(x).replace(",", ""))
    except Exception:
        return default

def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return float(x)
        return float(str(x).replace("%", "").replace(",", ""))
    except Exception:
        return default

# --------------------- Fetchers ---------------------
def fetch_codeforces(handle):
    base = "https://codeforces.com/api/"
    try:
        user_info = requests.get(base + f"user.info?handles={handle}", timeout=10).json()
        subs = requests.get(base + f"user.status?handle={handle}", timeout=10).json()
        contests = requests.get(base + f"user.rating?handle={handle}", timeout=10).json()
        if user_info.get("status") != "OK":
            return None, None, None
        user = user_info["result"][0]
        submissions = subs.get("result", [])
        contest_history = contests.get("result", [])
        return user, submissions, contest_history
    except Exception as e:
        messagebox.showerror("Network/API Error", f"Codeforces fetch failed:\n{e}")
        return None, None, None

def fetch_leetcode(username):
    # Note: this uses a community-hosted endpoint. It can be rate-limited or sometimes unavailable.
    url = f"https://leetcode-stats-api.herokuapp.com/{username}"
    try:
        res = requests.get(url, timeout=10).json()
        # The endpoint sometimes returns strings or missing fields; parse safely.
        if isinstance(res, dict) and res.get("status") == "error":
            return None
        # Typical keys: totalSolved, totalQuestions, easySolved, mediumSolved, hardSolved, acceptanceRate
        data = {
            "platform": "LeetCode",
            "username": username,
            "totalSolved": safe_int(res.get("totalSolved")),
            "totalQuestions": safe_int(res.get("totalQuestions")),
            "easySolved": safe_int(res.get("easySolved")),
            "mediumSolved": safe_int(res.get("mediumSolved")),
            "hardSolved": safe_int(res.get("hardSolved")),
            "acceptanceRate": safe_float(res.get("acceptanceRate"))
        }
        return data
    except Exception as e:
        messagebox.showerror("Network/API Error", f"LeetCode fetch failed:\n{e}")
        return None

def fetch_codechef(username):
    # Community API used here; may vary in fields
    try:
        res = requests.get(f"https://codechef-api.vercel.app/{username}", timeout=10).json()
        if not isinstance(res, dict) or res.get("status") == "failed":
            return None, None
        # res may contain 'solved' list and 'contests' list; parse safely
        solved = res.get("solved", [])
        contests = res.get("contests", [])  # may have rating info
        return res, contests
    except Exception as e:
        # fallback: return None
        return None, None

def fetch_atcoder(username):
    try:
        # AtCoder API (community) - returns list of contest results
        res = requests.get(f"https://atcoder-api.vercel.app/results/{username}", timeout=10)
        if res.status_code != 200:
            return None
        return res.json()
    except Exception:
        return None

def fetch_hackerrank(username):
    try:
        url = f"https://www.hackerrank.com/rest/contests/master/hackers/{username}/profile"
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return None
        j = res.json()
        return j.get("model", None)
    except Exception:
        return None


# --------------------- Analyzers ---------------------
def analyze_codeforces(subs):
    solved = set()
    attempted = set()
    tags = defaultdict(int)
    recent_contests = deque(maxlen=12)
    for sub in subs:
        prob = sub.get("problem", {})
        contestId = prob.get("contestId")
        index = prob.get("index")
        if contestId is None or index is None:
            continue
        pid = f"{contestId}-{index}"
        attempted.add(pid)
        verdict = sub.get("verdict", "")
        if verdict == "OK":
            solved.add(pid)
        for t in prob.get("tags", []):
            tags[t] += 1
        # recent contests (store as strings)
        if contestId:
            recent_contests.append(str(contestId))
    unsolved = attempted - solved
    accuracy = round((len(solved) / len(attempted) * 100), 2) if attempted else 0.0
    return {
        "solved": len(solved),
        "attempted": len(attempted),
        "unsolved": len(unsolved),
        "accuracy": accuracy,
        "tags": dict(sorted(tags.items(), key=lambda x: -x[1])[:6]),
        "recent": list(recent_contests)
    }

def analyze_leetcode(data):
    totalSolved = safe_int(data.get("totalSolved", 0))
    totalQuestions = safe_int(data.get("totalQuestions", 0))
    easy = safe_int(data.get("easySolved", 0))
    medium = safe_int(data.get("mediumSolved", 0))
    hard = safe_int(data.get("hardSolved", 0))
    acceptance = safe_float(data.get("acceptanceRate", 0.0))
    unsolved = max(0, totalQuestions - totalSolved)
    return {
        "solved": totalSolved,
        "unsolved": unsolved,
        "accuracy": round(acceptance, 2),
        "difficulty": {"Easy": easy, "Medium": medium, "Hard": hard},
        "totalQuestions": totalQuestions
    }


# --------------------- Plot helpers ---------------------
def safe_pie(ax, sizes, labels, colors=None, title=""):
    """
    Draw pie only if sizes are numeric and sum>0; otherwise display a message in plot area.
    """
    # coerce to floats and replace negative/None with 0
    safe_sizes = []
    for v in sizes:
        try:
            fv = float(v) if v is not None else 0.0
            if isnan(fv) or fv < 0:
                fv = 0.0
            safe_sizes.append(fv)
        except Exception:
            safe_sizes.append(0.0)
    total = sum(safe_sizes)
    if total <= 0.0:
        ax.text(0.5, 0.5, "No data to display", ha="center", va="center", fontsize=10)
        ax.set_title(title)
        ax.axis("off")
        return
    # draw pie
    try:
        ax.pie(safe_sizes, labels=labels, autopct='%1.1f%%', startangle=140,
               colors=colors)
        ax.set_title(title)
    except Exception as e:
        # fallback: show bar chart
        ax.bar(labels, safe_sizes)
        ax.set_title(title + " (fallback bar)")


def plot_rating_trend(platform, contests):
    """
    contests: list of contest records. This function tries to extract rating numbers safely.
    Returns a matplotlib Figure or None.
    """
    if not contests:
        return None
    ratings = []
    labels = []
    # Codeforces contest format: dicts with 'contestName', 'newRating', 'ratingUpdateTimeSeconds'
    # AtCoder format: list of dicts with keys e.g. 'NewRating' or 'NewRating' may not exist.
    for c in contests:
        if isinstance(c, dict):
            # try Codeforces
            nr = c.get("newRating") or c.get("NewRating") or c.get("rating")
            name = c.get("contestName") or c.get("ContestName") or c.get("name") or c.get("contest")
            if nr is None:
                # maybe CodeChef contest structure: c.get("oldRating"), c.get("rating")
                nr = c.get("rating") or c.get("after") or c.get("new_rating")
            nr = safe_int(nr, default=None)
            if nr is None:
                continue
            ratings.append(nr)
            labels.append(str(name)[:20] if name else "")
    if not ratings:
        return None

    # reduce labels to avoid clutter: pick only some xtick labels
    fig, ax = plt.subplots(figsize=(7, 3))
    x = list(range(len(ratings)))
    ax.plot(x, ratings, marker="o", linewidth=2)
    ax.set_title(f"{platform} Rating Progress")
    ax.set_ylabel("Rating")
    ax.grid(True, linestyle="--", alpha=0.6)
    # choose tick locations (max 10 labels)
    n = len(labels)
    step = max(1, int(n / 8))
    xticks = x[::step]
    xlabels = [labels[i] if i < len(labels) else "" for i in xticks]
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels, rotation=25, fontsize=8)
    plt.tight_layout()
    return fig


# --------------------- Dashboard UI ---------------------
def show_dashboard(platform, username, stats, cf_user=None, contests=None):
    dash = tk.Toplevel(root)
    dash.title(f"{platform} Dashboard - {username}")
    dash.geometry("980x700")
    dash.configure(bg="#f4f6f8")

    tk.Label(dash, text=f"📊 {platform} Performance Dashboard", font=("Arial", 18, "bold"), bg="#f4f6f8").pack(pady=10)
    tk.Label(dash, text=f"User: {username}", font=("Arial", 12), bg="#f4f6f8").pack(pady=2)

    # summary frame
    frame = tk.Frame(dash, bg="#f4f6f8")
    frame.pack(pady=8)

    # create a figure with appropriate subplots
    fig, axes = plt.subplots(1, 2, figsize=(9, 3))
    fig.patch.set_facecolor("#f4f6f8")

    try:
        if platform == "LeetCode":
            # summary box
            totalQ = stats.get("totalQuestions", 0)
            text = f"✅ Total Solved: {stats['solved']}\n❌ Unsolved: {stats['unsolved']}\n🎯 Acceptance Rate: {stats['accuracy']}%\nTotal Questions (catalog): {totalQ}"
            tk.Label(frame, text=text, font=("Consolas", 12), bg="#e8f0fe", padx=10, pady=10, relief="ridge").pack(pady=5)
            # pie for difficulty
            diff = stats.get("difficulty", {})
            sizes = [safe_int(diff.get("Easy", 0)), safe_int(diff.get("Medium", 0)), safe_int(diff.get("Hard", 0))]
            labels = ["Easy", "Medium", "Hard"]
            safe_pie(axes[0], sizes, labels, colors=["#81C784", "#FFB74D", "#E57373"], title="Difficulty Distribution")
            # progress bar/mini chart
            solved = stats.get("solved", 0)
            total = stats.get("totalQuestions", max(solved, 1))
            axes[1].bar(["Solved", "Remaining"], [solved, max(0, total - solved)], color=["#4CAF50", "#E57373"])
            axes[1].set_title("Solved vs Remaining")
        elif platform == "Codeforces":
            text = f"🏆 Rank: {cf_user.get('rank','N/A').title() if cf_user else 'N/A'}\n⭐ Rating: {cf_user.get('rating','N/A') if cf_user else 'N/A'}\n✅ Solved: {stats['solved']}\n🧩 Attempted: {stats['attempted']}\n❌ Unsolved: {stats['unsolved']}\n🎯 Accuracy: {stats['accuracy']}%"
            tk.Label(frame, text=text, font=("Consolas", 12), bg="#e8f0fe", padx=10, pady=10, relief="ridge").pack(pady=5)
            safe_pie(axes[0], [stats['solved'], stats['unsolved']], ["Solved", "Unsolved"], colors=["#4CAF50", "#E57373"], title="Solved vs Unsolved")
            tags = stats.get("tags", {})
            if tags:
                axes[1].barh(list(tags.keys()), list(tags.values()), color="#2196F3")
                axes[1].set_title("Top Tags")
                axes[1].set_xlabel("Count")
            else:
                axes[1].text(0.5, 0.5, "No tag data", ha="center", va="center")
                axes[1].axis("off")
        else:
            # generic layout for other platforms
            text = f"✅ Solved: {stats.get('solved', 0)}\n❌ Unsolved: {stats.get('unsolved', 0)}\n🎯 Metric: {stats.get('accuracy', 'N/A')}"
            tk.Label(frame, text=text, font=("Consolas", 12), bg="#e8f0fe", padx=10, pady=10, relief="ridge").pack(pady=5)
            safe_pie(axes[0], [stats.get('solved', 0), stats.get('unsolved', 0)], ["Solved", "Unsolved"], colors=["#4CAF50", "#E57373"], title="Progress")
            axes[1].axis("off")
    except Exception as e:
        messagebox.showwarning("Plot Warning", f"An error occurred while preparing plots:\n{e}")

    plt.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=dash)
    canvas.draw()
    canvas.get_tk_widget().pack(pady=10)

    # rating trend (if contests available)
    if contests:
        fig2 = plot_rating_trend(platform, contests)
        if fig2:
            tk.Label(dash, text="📈 Rating Progress", font=("Arial", 14, "bold"), bg="#f4f6f8").pack(pady=8)
            canvas2 = FigureCanvasTkAgg(fig2, master=dash)
            canvas2.draw()
            canvas2.get_tk_widget().pack(pady=6)
        else:
            tk.Label(dash, text="No rating contest history available or not parseable.", bg="#f4f6f8").pack(pady=6)


# --------------------- Main handler ---------------------
def track_user():
    site = site_combo.get().strip().lower()
    username = user_entry.get().strip()
    if not username:
        messagebox.showwarning("Input Error", "Enter a username/handle!")
        return

    if site == "codeforces":
        user, subs, contests = fetch_codeforces(username)
        if user is None:
            messagebox.showerror("Not found", "Codeforces user not found or API error.")
            return
        stats = analyze_codeforces(subs)
        show_dashboard("Codeforces", username, stats, cf_user=user, contests=contests)
    elif site == "leetcode":
        data = fetch_leetcode(username)
        if data is None:
            messagebox.showerror("Not found", "LeetCode user not found or API error.")
            return
        stats = analyze_leetcode(data)
        show_dashboard("LeetCode", username, stats)
    elif site == "codechef":
        data, contests = fetch_codechef(username)
        if data is None:
            messagebox.showerror("Not found", "CodeChef user not found or API error.")
            return
        # lightweight stats (fields vary by API). adapt as available.
        solved = safe_int(len(data.get("solved", [])))
        stats = {"solved": solved, "unsolved": 0, "accuracy": 0}
        show_dashboard("CodeChef", username, stats, contests=contests)
    elif site == "atcoder":
        contests = fetch_atcoder(username)
        if contests is None:
            messagebox.showerror("Not found", "AtCoder user not found or API error.")
            return
        # attempt to create a solved count from contests list length (best-effort)
        stats = {"solved": safe_int(len(contests)), "unsolved": 0, "accuracy": 0}
        show_dashboard("AtCoder", username, stats, contests=contests)
    elif site == "hackerrank":
        data = fetch_hackerrank(username)
        if data is None:
            messagebox.showerror("Not found", "HackerRank user not found or API error.")
            return
        solved = safe_int(data.get("solved_challenges", 0))
        stats = {"solved": solved, "unsolved": 0, "accuracy": 0}
        show_dashboard("HackerRank", username, stats)
    else:
        messagebox.showinfo("Not supported", f"Platform '{site}' is not supported.")


# --------------------- GUI Setup ---------------------
root = tk.Tk()
root.title("CP-Tracker Fixed (Multi-Platform + Rating)")
root.geometry("520x360")
root.configure(bg="#f4f6f8")

tk.Label(root, text="💻 CP-Tracker Fixed", font=("Arial", 18, "bold"), bg="#f4f6f8").pack(pady=15)
tk.Label(root, text="Select Platform:", font=("Arial", 11), bg="#f4f6f8").pack()
site_combo = ttk.Combobox(root, values=["Codeforces", "LeetCode", "CodeChef", "AtCoder", "HackerRank"], font=("Arial", 11))
site_combo.current(0)
site_combo.pack(pady=6)

tk.Label(root, text="Enter Username / Handle:", font=("Arial", 11), bg="#f4f6f8").pack()
user_entry = tk.Entry(root, width=34, font=("Arial", 11))
user_entry.pack(pady=6)

tk.Button(root, text="Track Performance", command=track_user,
          bg="#2196F3", fg="white", font=("Arial", 12, "bold"),
          relief="ridge", padx=10, pady=6).pack(pady=14)

root.mainloop()
