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

user_activity = {}
sites = ["Codeforces", "LeetCode", "CodeChef", "AtCoder"]
subjects = [
    "All Topics", "Arrays", "Strings", "Graphs", "Dynamic Programming",
    "Greedy", "Math", "Data Structures", "Trees", "Sorting", "Searching"
]
current_fig = None

class TreeNode:
    def __init__(self, name):
        self.name = name
        self.children = []

    def add_child(self, node):
        self.children.append(node)

    def display(self, level=0):
        print(" " * level * 2 + f"- {self.name}")
        for child in self.children:
            child.display(level + 1)

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


problem_graph = {}

def add_edge(problem, tags):
    """Connect problem node to its tags (Graph Representation)."""
    if problem not in problem_graph:
        problem_graph[problem] = set()
    for tag in tags:
        problem_graph[problem].add(tag)



def fetch_codeforces(username, subject):
    """Fetch Codeforces user submissions, filter by subject."""
    try:
        username = username.strip()
        url = f"https://codeforces.com/api/user.status?handle={username}"
        response = requests.get(url, timeout=10)
        data = response.json()
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

            
            if problem_tags:
                add_edge(problem.get("name", "Unknown"), problem_tags)

            if subject != "All Topics" and not any(tag in problem_tags for tag in subject_tags):
                continue
            if verdict == "OK":
                solved += 1
                tags.update(problem_tags)
            else:
                unsolved += 1

        if solved == 0 and unsolved == 0 and subject != "All Topics":
            return fetch_codeforces(username, "All Topics")

        for sub in submissions[:5]:
            problem = sub.get("problem", {})
            name = problem.get("name", "Unknown")
            cid, index = problem.get("contestId", ""), problem.get("index", "")
            verdict = sub.get("verdict", "N/A")
            link = f"https://codeforces.com/problemset/problem/{cid}/{index}" if cid and index else "N/A"
            recent.append((name, verdict, link))

        return {"solved": solved, "unsolved": unsolved, "tags": tags, "recent": recent}
    except Exception:
        return None


def fetch_leetcode(username):
    url = "https://leetcode.com/graphql"
    headers = {"User-Agent": "Mozilla/5.0"}
    query = {"query": f'''query {{
        matchedUser(username: "{username}") {{
          submitStats: submitStatsGlobal {{ acSubmissionNum {{ difficulty count }} }}
        }}
        allQuestionsCount {{ difficulty count }}
    }}'''}

    try:
        r = requests.post(url, headers=headers, json=query, timeout=10).json()
        user = r.get("data", {}).get("matchedUser")
        if not user:
            return None
        solved = sum(i["count"] for i in user["submitStats"]["acSubmissionNum"])
        total = sum(q["count"] for q in r["data"]["allQuestionsCount"] if q["difficulty"] != "All")
        unsolved = max(total - solved, 0)
        return {"solved": solved, "unsolved": unsolved, "tags": {}, "recent": []}
    except Exception:
        return None


def fetch_codechef(username):
    """Fetch CodeChef data (clean rating and stars)."""
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        driver.get(f"https://www.codechef.com/users/{username}")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//section[contains(@class, 'problems-solved')]"))
        )
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "lxml")
        driver.quit()

        rating_div = soup.find("div", class_="rating-number")
        rating_raw = rating_div.get_text(strip=True) if rating_div else "N/A"
        rating_match = re.findall(r"\d+", rating_raw)
        rating = rating_match[0] if rating_match else "N/A"

        star_span = soup.find("span", class_="rating")
        stars = "".join(re.findall(r"★+", star_span.get_text(strip=True))) if star_span else "★"

        solved_total = 0
        for sec in soup.find_all("section", class_="problems-solved"):
            for h5 in sec.find_all("h5"):
                if "(" in h5.text:
                    solved_total += int(h5.text.split("(")[1].split(")")[0])

        links = soup.find_all("a", href=True)
        problems = {a.text.strip() for a in links if "/problems/" in a["href"] and a.text.strip()}
        unsolved_total = max(len(problems) - solved_total, 0)

        return {"solved": solved_total, "unsolved": unsolved_total, "tags": {}, "recent": [("Rating", rating, stars)]}
    except Exception:
        return None


def fetch_atcoder(username):
    try:
        r = requests.get(f"https://atcoder.jp/users/{username}", timeout=10)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        tag = soup.find("th", string="Rating")
        rating = tag.find_next("td").text.strip() if tag else "N/A"
        return {"solved": "N/A", "unsolved": "N/A", "tags": {}, "recent": [("Rating", rating, "")]}
    except Exception:
        return None


def fetch_activity():
    threading.Thread(target=run_fetch, daemon=True).start()

def run_fetch():
    site = site_var.get()
    subject = subject_var.get()
    username = username_entry.get().strip()
    if not username:
        root.after(0, lambda: messagebox.showwarning("Warning", "Enter a username."))
        return

    root.after(0, lambda: fetch_button.config(state="disabled"))
    root.after(0, lambda: message_label.config(text=f"Fetching data from {site}..."))

    if site == "Codeforces":
        data = fetch_codeforces(username, subject)
    elif site == "LeetCode":
        data = fetch_leetcode(username)
    elif site == "CodeChef":
        data = fetch_codechef(username)
    else:
        data = fetch_atcoder(username)

    if not data:
        root.after(0, lambda: show_error(username, site))
    else:
        user_activity[site] = data
        root.after(0, lambda: show_result(username, site, subject))
        root.after(0, lambda: save_csv(username, site, subject, data))
        root.after(0, lambda: update_chart(subject))

    root.after(0, lambda: fetch_button.config(state="normal"))


def show_error(username, site):
    output_text.delete(1.0, tk.END)
    output_text.insert(tk.END, f"⚠️ Could not fetch data for '{username}' on {site}.\n")
    message_label.config(text="No data or invalid username.")

def show_result(username, site, subject):
    d = user_activity[site]
    output_text.delete(1.0, tk.END)
    output_text.insert(tk.END, f"📊 Site: {site}\n👤 User: {username}\n🏷️ Subject: {subject}\n\n")
    output_text.insert(tk.END, f"✅ Solved: {d['solved']}\n❌ Unsolved: {d['unsolved']}\n")

    if site in ["CodeChef", "AtCoder"]:
        for r in d["recent"]:
            output_text.insert(tk.END, f"🏆 {r[0]}: {r[1]} {r[2]}\n")

    if site == "Codeforces" and d["recent"]:
        output_text.insert(tk.END, "\n🕒 Recent Submissions:\n")
        for i, (name, verdict, link) in enumerate(d["recent"], 1):
            output_text.insert(tk.END, f"{i}. {name} → {verdict}\n")
            output_text.insert(tk.END, f"   🔗 {link}\n")

   
    if site == "Codeforces" and problem_graph:
        output_text.insert(tk.END, "\n🌐 Problem-Tag Relationships (Graph):\n")
        count = 0
        for problem, tags in problem_graph.items():
            count += 1
            output_text.insert(tk.END, f"{count}. {problem} → {', '.join(tags)}\n")
            if count >= 5:
                break

    message_label.config(text="✅ Data fetched successfully!")


def save_csv(username, site, subject, data):
    try:
        with open("tracker_report.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            rating = data["recent"][0][1] if data["recent"] else "N/A"
            writer.writerow([site, username, subject, data["solved"], data["unsolved"], rating])
    except Exception as e:
        messagebox.showerror("Error", str(e))

def update_chart(subject):
    global current_fig
    labels, solved, unsolved = [], [], []
    for site, d in user_activity.items():
        labels.append(site)
        solved.append(0 if d["solved"] == "N/A" else d["solved"])
        unsolved.append(0 if d["unsolved"] == "N/A" else d["unsolved"])
    if not labels:
        return

    fig, axs = plt.subplots(1, 2, figsize=(10, 4), facecolor="#f4f6f8")
    x = range(len(labels))
    axs[0].bar(x, solved, color="#00bfa5", width=0.4, label="Solved")
    axs[0].bar(x, unsolved, bottom=solved, color="#ff7043", width=0.4, label="Unsolved")
    axs[0].set_xticks(x)
    axs[0].set_xticklabels(labels)
    axs[0].set_ylabel("Problems")
    axs[0].set_title(f"Solved vs Unsolved ({subject})")
    axs[0].legend()
    for s in axs[0].spines.values():
        s.set_visible(False)

    cf_data = user_activity.get("Codeforces")
    if cf_data and cf_data["tags"]:
        tag_counts = cf_data["tags"].most_common(6)
        labels_pie = [t for t, _ in tag_counts]
        values_pie = [v for _, v in tag_counts]
        axs[1].pie(values_pie, labels=labels_pie, autopct="%1.0f%%", startangle=90)
        axs[1].set_title("Codeforces Topic Distribution")
    else:
        axs[1].text(0.5, 0.5, "No tag data available", ha="center", va="center", fontsize=10)

    plt.tight_layout()
    for w in chart_frame.winfo_children():
        w.destroy()

    can = FigureCanvasTkAgg(fig, master=chart_frame)
    can.draw()
    can.get_tk_widget().pack(fill="both", expand=True)
    current_fig = fig

def save_chart_png():
    if not current_fig:
        messagebox.showinfo("Info", "Generate a chart first.")
        return
    file = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png")])
    if file:
        current_fig.savefig(file, bbox_inches="tight", dpi=200)
        messagebox.showinfo("Saved", f"Chart saved as {file}")

        
root = tk.Tk()
root.title("Competitive Programming Tracker (Final With Graph & Tree)")
root.geometry("1100x800")
root.configure(bg="#f4f6f8")

tk.Label(root, text="Select Site:", bg="#f4f6f8").grid(row=0, column=0, padx=10, pady=10, sticky="w")
site_var = tk.StringVar(value=sites[0])
ttk.Combobox(root, textvariable=site_var, values=sites, state="readonly").grid(row=0, column=1, pady=10, sticky="ew")

tk.Label(root, text="Select Subject:", bg="#f4f6f8").grid(row=1, column=0, padx=10, pady=10, sticky="w")
subject_var = tk.StringVar(value=subjects[0])
ttk.Combobox(root, textvariable=subject_var, values=subjects, state="readonly").grid(row=1, column=1, pady=10, sticky="ew")

tk.Label(root, text="Enter Username:", bg="#f4f6f8").grid(row=2, column=0, padx=10, pady=10, sticky="w")
username_entry = tk.Entry(root, width=30)
username_entry.grid(row=2, column=1, pady=10, sticky="ew")

fetch_button = tk.Button(root, text="Fetch & Save Activity", bg="#2196f3", fg="white", command=fetch_activity)
fetch_button.grid(row=2, column=2, padx=10, pady=10)
tk.Button(root, text="📸 Save Chart as PNG", bg="#4caf50", fg="white", command=save_chart_png)\
    .grid(row=2, column=3, padx=10, pady=10)

output_text = tk.Text(root, height=14, width=120, wrap="word")
output_text.grid(row=3, column=0, columnspan=4, padx=10, pady=10)

chart_frame = tk.Frame(root, bg="#f4f6f8", height=300)
chart_frame.grid(row=4, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")

message_label = tk.Label(root, text="", bg="#f4f6f8", fg="green", font=("Segoe UI", 10))
message_label.grid(row=5, column=0, columnspan=4, pady=10)

root.mainloop()
