import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests, csv, time, threading, warnings, re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from collections import Counter
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

# ---------- Globals ----------
user_activity = {}
sites = ["Codeforces", "LeetCode", "CodeChef", "AtCoder"]
subjects = [
    "All Topics", "Arrays", "Strings", "Graphs", "Dynamic Programming",
    "Greedy", "Math", "Data Structures", "Trees", "Sorting", "Searching"
]
current_fig = None

# ---------- TREE (DSA Topic Hierarchy) ----------
class TreeNode:
    def __init__(self, name):
        self.name = name
        self.children = []

    def add_child(self, node):
        self.children.append(node)

def build_topic_tree():
    root = TreeNode("DSA")
    categories = {
        "Data Structures": ["Arrays", "Linked Lists", "Stacks", "Queues", "Trees", "Graphs"],
        "Algorithms": ["Sorting", "Searching", "Greedy", "Dynamic Programming"]
    }
    for cat, subs in categories.items():
        cat_node = TreeNode(cat)
        for sub in subs:
            cat_node.add_child(TreeNode(sub))
        root.add_child(cat_node)
    return root

topic_tree = build_topic_tree()

# ---------- GRAPH (Problem → Tags Mapping) ----------
problem_graph = {}
def add_edge(problem, tags):
    if problem not in problem_graph:
        problem_graph[problem] = set()
    for tag in tags:
        problem_graph[problem].add(tag)

# ---------- NEW ALGORITHM: Topic Transition Learning Algorithm (TTLA) ----------
transition_matrix = {}   # stores transitions between topic → next topic
last_topic = None        # keeps track of previous solved topic

# ---------- FETCHERS ----------
def fetch_codeforces(username, subject):
    global last_topic
    try:
        url = f"https://codeforces.com/api/user.status?handle={username}"
        data = requests.get(url, timeout=10).json()
        if data.get("status") != "OK":
            return None

        submissions = data.get("result", [])
        solved, unsolved = 0, 0
        tags = Counter()
        recent = []

        subject_tag_map = {
            "Arrays": ["implementation", "data structures", "two pointers"],
            "Strings": ["strings"],
            "Graphs": ["graphs", "dfs and similar", "shortest paths", "dsu"],
            "Dynamic Programming": ["dp"],
            "Greedy": ["greedy"],
            "Math": ["math", "number theory", "combinatorics"],
            "Data Structures": ["data structures", "trees"],
            "Trees": ["trees"],
            "Sorting": ["sortings"],
            "Searching": ["binary search"],
            "All Topics": []
        }
        subject_tags = [s.lower() for s in subject_tag_map.get(subject, [])]

        for sub in submissions:
            verdict = sub.get("verdict", "")
            problem = sub.get("problem", {})
            problem_tags = [t.lower() for t in problem.get("tags", [])]

            add_edge(problem.get("name", "Unknown"), problem_tags)

            # ---- TTLA Algorithm: Track topic transitions ----
            if problem_tags:
                current_topic = problem_tags[0]  # take primary tag
                if current_topic not in transition_matrix:
                    transition_matrix[current_topic] = Counter()
                global last_topic
                if last_topic is not None:
                    transition_matrix[last_topic][current_topic] += 1
                last_topic = current_topic

            if subject != "All Topics" and not any(tag in problem_tags for tag in subject_tags):
                continue

            if verdict == "OK":
                solved += 1
                tags.update(problem_tags)
            else:
                unsolved += 1

        for sub in submissions[:5]:
            p = sub.get("problem", {})
            name = p.get("name", "Unknown")
            link = f"https://codeforces.com/problemset/problem/{p.get('contestId','')}/{p.get('index','')}"
            recent.append((name, sub.get("verdict","N/A"), link))

        return {"solved": solved, "unsolved": unsolved, "tags": tags, "recent": recent}

    except:
        return None

def fetch_leetcode(username):
    try:
        url = "https://leetcode.com/graphql"
        headers = {"User-Agent": "Mozilla/5.0"}
        query = {"query": f'''query {{ matchedUser(username: "{username}") {{ submitStats: submitStatsGlobal {{ acSubmissionNum {{ count }} }} }} }}'''}
        r = requests.post(url, headers=headers, json=query, timeout=10).json()
        user = r.get("data", {}).get("matchedUser")
        if not user:
            return None
        solved = sum(i["count"] for i in user["submitStats"]["acSubmissionNum"])
        return {"solved": solved, "unsolved": "N/A", "tags": {}, "recent": []}
    except:
        return None

def fetch_codechef(username):
    try:
        opts = webdriver.ChromeOptions()
        opts.add_argument("--headless=new")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        driver.get(f"https://www.codechef.com/users/{username}")
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "lxml")
        driver.quit()
        solved = sum(int(h5.text.split("(")[1].split(")")[0]) for h5 in soup.find_all("h5") if "(" in h5.text)
        return {"solved": solved, "unsolved": "N/A", "tags": {}, "recent": []}
    except:
        return None

def fetch_atcoder(username):
    try:
        r = requests.get(f"https://atcoder.jp/users/{username}", timeout=10)
        if r.status_code != 200:
            return None
        return {"solved": "N/A", "unsolved": "N/A", "tags": {}, "recent": []}
    except:
        return None

# ---------- THREADING ----------
def fetch_activity():
    threading.Thread(target=run_fetch, daemon=True).start()

def run_fetch():
    site = site_var.get()
    subject = subject_var.get()
    username = username_entry.get().strip()

    if not username:
        return messagebox.showwarning("Warning", "Enter a username.")

    fetch_button.config(state="disabled")

    if site == "Codeforces": data = fetch_codeforces(username, subject)
    elif site == "LeetCode": data = fetch_leetcode(username)
    elif site == "CodeChef": data = fetch_codechef(username)
    else: data = fetch_atcoder(username)

    if not data:
        show_error(username, site)
    else:
        user_activity[site] = data
        show_result(username, site, subject)
        save_csv(username, site, subject, data)

    fetch_button.config(state="normal")

# ---------- DISPLAY ----------
def show_error(username, site):
    output_text.delete(1.0, tk.END)
    output_text.insert(tk.END, f"⚠️ Could not fetch data for '{username}' on {site}.\n")

def show_result(username, site, subject):
    d = user_activity[site]
    output_text.delete(1.0, tk.END)
    output_text.insert(tk.END, f"📌 Site: {site}\n👤 User: {username}\n\n")
    output_text.insert(tk.END, f"✅ Solved: {d['solved']}\n❌ Unsolved: {d['unsolved']}\n")

    # ---- NEW TTLA OUTPUT DISPLAY ----
    if site == "Codeforces" and transition_matrix:
        output_text.insert(tk.END, "\n🔁 Topic Transition Patterns:\n")
        for src, dests in transition_matrix.items():
            for dest, count in dests.items():
                output_text.insert(tk.END, f"   {src} → {dest}: {count} times\n")

# ---------- CSV ----------
def save_csv(username, site, subject, data):
    with open("tracker_report.csv", "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([site, username, subject, data["solved"], data["unsolved"]])

# ---------- GUI ----------
root = tk.Tk()
root.title("Competitive Programming Tracker (with TTLA)")

tk.Label(root, text="Select Site:").grid(row=0, column=0)
site_var = tk.StringVar(value=sites[0])
ttk.Combobox(root, textvariable=site_var, values=sites).grid(row=0, column=1)

tk.Label(root, text="Select Subject:").grid(row=1, column=0)
subject_var = tk.StringVar(value=subjects[0])
ttk.Combobox(root, textvariable=subject_var, values=subjects).grid(row=1, column=1)

tk.Label(root, text="Enter Username:").grid(row=2, column=0)
username_entry = tk.Entry(root)
username_entry.grid(row=2, column=1)

fetch_button = tk.Button(root, text="Fetch", command=fetch_activity)
fetch_button.grid(row=2, column=2)

output_text = tk.Text(root, width=95, height=30)
output_text.grid(row=3, column=0, columnspan=3)

root.mainloop()
