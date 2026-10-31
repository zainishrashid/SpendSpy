import csv
import json
import os
import statistics
from collections import defaultdict
from datetime import datetime
from functools import wraps
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from dataclasses import dataclass


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILES = os.path.join(BASE_DIR, "categories.json")
BUDGET_FILES = os.path.join(BASE_DIR, "budgets.json")
DEFAULT_CSV = os.path.join(BASE_DIR, "transactions.csv")

DEFAULT_RULES = {
    "Income": ["payroll", "salary", "transfer from", "interest paid"],
    "Rent": ["rent"],
    "Transport": ["opal", "uber *trip", "didi", "shell", "bp ", "7-eleven fuel", "fuel"],
    "Dining": ["mcdonalds", "kfc", "dominos", "uber *eats", "doordash", "guzman",
               "subway", "chatime", "menulog", "restaurant"],
    "Coffee": ["starbucks", "gloria jeans", "cafe", "coffee"],
    "Groceries": ["woolworths", "coles", "aldi", "harris farm", "iga"],
    "Utilities": ["telstra", "origin", "optus", "agl", "vodafone"],
    "Entertainment": ["netflix", "spotify", "hoyts", "steam", "eventbrite", "disney"],
    "Shopping": ["amazon", "kmart", "uniqlo", "jb hi-fi", "cotton on", "bunnings"],
    "Health": ["chemist", "priceline", "anytime fitness", "dental", "pharmacy"],
    "Education": ["co-op bookshop", "coursera", "udemy", "officeworks"],
    "Travel": ["qantas", "jetstar", "virgin australia", "airbnb"],
    "Cash": ["atm"],
}
UNCATEGORISED = "Uncategorized"
INCOME = "Income"

BG = "#0B1220"
CARD_BG = "#172235"
BORDER = "#26364D"
TEXT = "#E8EEF8"
MUTED = "#91A2BA"
PRIMARY = "#70A5FF"
PRIMARY_DARK = "#477FE0"
GOOD = "#34D399"
WARN = "#FBBF24"
BAD = "#F87171"
FONT = ("Arial", 10)  # normal text
FONT_BOLD = ("Arial", 10, "bold")  # bold text
FONT_SMALL = ("Arial", 9)  # small text
FONT_HEAD = ("Arial", 11, "bold")  # headings
FONT_BIG = ("Arial", 18, "bold")  # big numbers on cards

# Colours given to categories in charts (used in stage 2); cycled if there are more categories.
PALETTE = ["#60A5FA", "#F59E0B", "#34D399", "#F87171", "#2DD4BF", "#C084FC",
           "#FB7185", "#A78BFA", "#94A3B8", "#FACC15", "#38BDF8", "#A3E635"]
CATEGORY_COLOURS = {}
CORNER_RADIUS = 14


def colour_for(category):
    if category == "Other":
        return "#64748B"
    if category not in CATEGORY_COLOURS:
        CATEGORY_COLOURS[category] = PALETTE[len(CATEGORY_COLOURS) % len(PALETTE)]
    return CATEGORY_COLOURS[category]


#for borders
def round_rect_points(x1, y1, x2, y2, r):
    """Returning the polygon points of a rectangle with rounded corners."""
    return [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1,
            x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2,
            x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2,
            x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]

#rounded box
def draw_panel(canvas, width, height, radius=CORNER_RADIUS + 2, tags=()):
    return canvas.create_polygon(round_rect_points(1, 1, width - 2, height - 2, radius),
                                 smooth=True, fill=CARD_BG, outline=BORDER, width=1, tags=tags)


class RoundedCard(tk.Canvas):
   #for rounded box with thin corners
    def __init__(self, parent, pad=14, fill_height=False, **kwargs):
        kwargs.setdefault("width", 10)
        kwargs.setdefault("height", 10)
        super().__init__(parent, bg=BG, highlightthickness=0, bd=0, **kwargs)
        self.pad = pad
        self.fill_height = fill_height
        self.body = tk.Frame(self, bg=CARD_BG)
        self.window = self.create_window(pad, pad, window=self.body, anchor="nw")
        self.bind("<Configure>", self.on_resize)
        if not fill_height:
            self.body.bind("<Configure>", self.on_body_resize)
#resizing the content area
    def on_resize(self, event):
        options = {"width": max(1, event.width - 2 * self.pad)}
        if self.fill_height:
            options["height"] = max(1, event.height - 2 * self.pad)
        self.itemconfigure(self.window, **options)
        self.delete("box")
        draw_panel(self, event.width, event.height, tags="box")
        self.tag_lower("box")

#keeping the height same
    def on_body_resize(self, event):
        needed = max(155,event.height + 2 * self.pad)
        if int(float(self.cget("height"))) != needed:
            self.configure(height=needed)


class DataError(Exception):
    """error will be raised when csv is missing, empty or badly formatted"""


def safe_action(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DataError as err:
            messagebox.showwarning("Data problem", str(err))
        except (ValueError, KeyError) as err:
            messagebox.showerror("Invalid input", str(err))
        except OSError as err:
            messagebox.showerror("File problem", str(err))

    return wrapper


@dataclass
class Transaction:
    date: datetime
    description: str
    amount: float
    category: str = UNCATEGORISED

    @property
    def month(self):
        return self.date.strftime("%Y-%m")

    @property
    def is_spending(self):
        return self.amount <0 and self.category != INCOME


class Categoriser:
    def __init__(self, path=RULES_FILES):
        self.path = path
        self.rules = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as file:
                    return json.load(file)
            except (OSError, json.JSONDecodeError):
                print("Unable to read categories.json using defeault")

        return {cat: list(words) for cat, words in DEFAULT_RULES.items()}

    def save(self):
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(self.rules, file, indent=2)

    def categories(self, description):
        text = description.lower()
        for category, keywords in self.rules.items():
            if any(word in text for word in keywords):
                return category
        return UNCATEGORISED

    def add_keyword(self, category, keyword):
        keyword = keyword.strip().lower()

        if not keyword:
            raise ValueError("keyword cannot be empty")

        if not category.strip():
            raise ValueError("category cannot be empty")

        self.rules.setdefault(category, [])

        if keyword not in self.rules[category]:
            self.rules[category].append(keyword)

        self.save()


    def delete_category(self, category):
        category = category.strip()

        if not category:
            raise ValueError("Please select a category to delete.")

        if category not in self.rules:
            raise ValueError("Category does not exist.")

        del self.rules[category]
        self.save()




class BudgetManager:
    WARN_AT = 0.80

    def __init__(self, path=BUDGET_FILES):
        self.path = path
        self.budgets = {}
        if os.path.exists(path):
            try:
                with open(self.path, encoding="utf-8") as file:
                    self.budgets = json.load(file)
            except (OSError, json.JSONDecodeError):
                print("Unable to read budget.json")

    def save(self):
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(self.budgets, file, indent=2)

    def set_budget(self, category, amount):
        if amount < 0:
            raise ValueError("Budget cannot be negative")
        self.budgets[category] = round(amount, 2)
        self.save()

    def clear_budget(self, category):
        if self.budgets.pop(category, None) is not None:
            self.save()

    def clear_all(self):
        # NEW: remove every budget and save the empty list
        self.budgets.clear()
        self.save()

    def check(self, month_totals):
        results = []
        for category, limit in self.budgets.items():
            spent = month_totals.get(category, 0.0)
            if spent > limit:
                status = "OVER BUDGET"
            elif spent >= limit * self.WARN_AT:
                status = "WARNING"
            else:
                status = "OK"
            results.append((category, spent, limit, status))
        return sorted(results, key=lambda r: r[1] / r[2] if r[2] else 0, reverse=True)


class ExpenseAnalyzer:
    def __init__(self, categoriser):
        self.categoriser = categoriser
        self.transactions = []

    @staticmethod
    def parse_date(text):
        #adding all types of date formats
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"Unrecognized date '{text}'")

    @staticmethod
    def parse_amount(text):
        cleaned = text.strip().replace("$", "").replace(",", "")
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        return float(cleaned)

    @staticmethod
    def read_rows(path):
        try:
            with open(path, newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                if reader.fieldnames is None:
                    raise DataError("File is empty")
                names = {n.strip().lower(): n for n in reader.fieldnames}
                missing = {"date", "description", "amount"} - set(names)
                if missing:
                    raise DataError(f"Missing {','.join(sorted(missing))}")
                for row in reader:
                    yield {key: row[names[key]] for key in ("date", "description", "amount")}
        except FileNotFoundError:
            raise DataError(f"File not found: {path}")

    def load_csv(self, path):
        loaded, skipped = [], 0
        for row in self.read_rows(path):
            try:
                tx = Transaction(self.parse_date(row["date"]), row["description"].strip(),
                                 self.parse_amount(row["amount"]))
            except (ValueError, AttributeError):
                skipped += 1
                continue
            tx.category = self.categoriser.categories(tx.description)
            loaded.append(tx)
        if not loaded:
            raise DataError("No valid transactions found. Check the CSV date and amount columns.")
        self.transactions = sorted(loaded, key=lambda t: t.date)
        return len(loaded), skipped

    def require_data(self):
        if not self.transactions:
            raise DataError("Import a CSV file first")

    def recategorise(self):
        for tx in self.transactions:
            tx.category = self.categoriser.categories(tx.description)

    # ANALYSIS
    def months(self):
        return sorted({t.month for t in self.transactions})

    def spending_by_month(self):
        data = defaultdict(lambda: defaultdict(float))
        for t in self.transactions:
            if t.is_spending:
                expense = abs(t.amount)
                data[t.month][t.category] += expense
        return {month: dict(categories)
                for month, categories in data.items()}

    def income_by_month(self):
        totals = defaultdict(float)

        for t in self.transactions:
            # Count only positive transactions identified as income.
            if t.category == INCOME and t.amount > 0:
                totals[t.month] += t.amount

        return dict(totals)

    def uncategorised(self):
        return [t for t in self.transactions if t.category == UNCATEGORISED]

    def category_averages(self, last_months=None):
       #calculating average
        by_month = self.spending_by_month()
        chosen = sorted(by_month)[-last_months:] if last_months else sorted(by_month)
        categories = {c for m in chosen for c in by_month[m]}
        return {c: statistics.mean(by_month[m].get(c, 0.0) for m in chosen) for c in categories}

    def spending_categories(self):
        return sorted({t.category for t in self.transactions if t.is_spending})
#selecting the top 5 merchants
    def top_merchants(self, month, count=5):
        totals = defaultdict(float)
        for t in self.transactions:
            if t.month == month and t.is_spending and t.amount < 0:
                totals[t.description] += -t.amount
        return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:count]

    def build_report(self):
        spend = self.spending_by_month()
        income = self.income_by_month()
        lines = ["PERSONAL EXPENSE REPORT", "=" * 40]
        for month in sorted(spend):
            total = sum(spend[month].values())
            lines.append(f"\n{month} spend ${total:,.2f} income ${income.get(month, 0):,.2f}")
            for cat, val in sorted(spend[month].items(), key=lambda kv: kv[1], reverse=True):
                lines.append(f"{cat:<15} ${val:>9,.2f}")
        return "\n".join(lines) + "\n"

#checking cash transactions
    def check_cash_transactions(self):
        for t in self.transactions:
            if t.category == "Cash":
                print(t.date.strftime("%Y-%m-%d"),
                      t.description,
                      t.amount,
                      t.category)




# VIEW tab
class BaseTab(ttk.Frame):
    def __init__(self, notebook, app):
        super().__init__(notebook, padding=10)
        self.app = app

    def refresh(self):
        raise NotImplementedError


# DASHBOARD
class DashboardTab(BaseTab):
    def __init__(self, notebook, app):
        super().__init__(notebook, app)
        self.card_values = {}
        self.trend_points = []

        cards = ttk.Frame(self)
        cards.pack(fill="x",pady=(0,12))
        for title in ("Total spending", "Total income", "Net balance", "Savings rate"):
            card = RoundedCard(cards, pad=16, height=155)
            card.pack(side="left", expand=True, fill="both", padx=6, pady=5)
            accent = tk.Frame(card.body, bg=PRIMARY if title == "Total spending" else
                              (GOOD if title == "Total income" else
                               (WARN if title == "Savings rate" else PRIMARY)),
                              height=3, bd=0)
            accent.pack(fill="x", side="top", pady=(0, 12))
            heading = tk.Label(card.body, text=title.upper(), bg=CARD_BG, fg=MUTED,
                               font=("Arial", 9, "bold"))
            heading.pack(anchor="w", pady=(0, 7))
            value = tk.Label(card.body, text="—", bg=CARD_BG, fg=TEXT,
                             font=("Arial", 21, "bold"))
            value.pack(anchor="w")
            self.card_values[title] = value


        charts = ttk.Frame(self)
        charts.pack(pady=(10, 14), fill="both", expand=True)

        self.donut = tk.Canvas(charts, width=560, height=290, bg=BG,
                               highlightthickness=0, bd=0)
        self.trend = tk.Canvas(charts, width=560, height=290, bg=BG,
                               highlightthickness=0, bd=0)
        self.donut.pack(side="left", padx=(4, 8), fill="both", expand=True)
        self.trend.pack(side="left", padx=(8, 4), fill="both", expand=True)
        self.trend.bind("<Button-1>", self.on_trend_click)
        self.donut.bind("<Configure>", lambda event: self.redraw_charts())
        self.trend.bind("<Configure>", lambda event: self.redraw_charts())
        #bottom row
        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True, pady=(4, 2))

        left = RoundedCard(bottom, pad=14, fill_height=True, height=210)
        left.pack(side="left", fill="both", expand=True, padx=6)
        tk.Label(left.body, text="TOP MERCHANTS THIS MONTH", bg=CARD_BG, fg=MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 8))


        self.merchants = ttk.Treeview(left.body, columns=("merchant", "spent"), show="headings",
                                      height=5, style="Compact.Treeview")
        self.merchants.heading("merchant", text="Merchant")
        self.merchants.heading("spent", text="Spent")
        self.merchants.column("merchant", width=300)
        self.merchants.column("spent", width=90, anchor="e")
        self.merchants.pack(fill="both", expand=True)
        right = RoundedCard(bottom, pad=14, fill_height=True, height=210)
        right.pack(side="left", fill="both", expand=True, padx=6)
        tk.Label(right.body, text="BUDGET ALERTS", bg=CARD_BG, fg=MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 8))
        self.alerts = tk.Listbox(right.body, height=5, bd=0, highlightthickness=0, font=FONT,
                                 bg=CARD_BG, fg=TEXT, selectbackground=PRIMARY_DARK,
                                 selectforeground="#FFFFFF", activestyle="none")
        self.alerts.pack(fill="both", expand=True)

# drawing everything again

    def refresh(self):
        model = self.app.model
        month = self.app.month_var.get()
        if not model.transactions or not month:
            self.draw_empty()
            return
        spend = model.spending_by_month().get(month, {})
        spent = sum(spend.values())
        income = model.income_by_month().get(month, 0.0)
        net = income - spent
        results = self.app.budgets.check(spend)
        over = [r for r in results if r[3] == "OVER BUDGET"]

        # updating the four cards
        savings_rate = (net / income * 100) if income > 0 else None
        self.card_values["Total spending"].config(text=f"${spent:,.2f}", fg=TEXT)
        self.card_values["Total income"].config(text=f"${income:,.2f}", fg=GOOD)
        self.card_values["Net balance"].config(
            text=f"${net:,.2f}", fg=GOOD if net >= 0 else BAD)
        self.card_values["Savings rate"].config(
            text=f"{savings_rate:.1f}%" if savings_rate is not None else "N/A",
            fg=(GOOD if savings_rate is not None and savings_rate >= 20
                else WARN if savings_rate is not None and savings_rate >= 0
                else BAD))

        # charts
        self.draw_donut(month, spend)
        self.draw_trend(month)

        # top merchants table
        self.merchants.delete(*self.merchants.get_children())
        for name, value in model.top_merchants(month):
            self.merchants.insert("", "end", values=(name, f"${value:,.2f}"))

        # budget alerts list
        self.alerts.delete(0, "end")
        if not results:
            self.alerts.insert("end", "No budgets set yet - open the budget tab.")
        else:
            flagged = [r for r in results if r[3] != "OK"]
            for i, (cat, s, limit, status) in enumerate(flagged):
                self.alerts.insert("end", f"{status}: {cat} ${s:,.0f} of ${limit:,.0f}")
                self.alerts.itemconfig(i, fg=BAD if status == "OVER BUDGET" else WARN)
            if not flagged:
                self.alerts.insert("end", "All categories are within budget.")
                self.alerts.itemconfig(0, fg=GOOD)

    def draw_empty(self):
        # "placeholder shown before any CSV is imported"
        for value in self.card_values.values():
            value.config(text="—", fg=TEXT)
        for canvas in (self.donut, self.trend):
            canvas.delete("all")
            width = max(canvas.winfo_width(), 420)
            height = max(canvas.winfo_height(), 280)
            draw_panel(canvas, width, height)                    # CHANGED: rounded panel
            canvas.create_text(width / 2, height / 2, text="Click 'Import CSV' to begin",
                               font=FONT_HEAD, fill=MUTED)
        self.merchants.delete(*self.merchants.get_children())
        self.alerts.delete(0, "end")

    def redraw_charts(self):
        #drawing the charts again after canvas resize
        if not hasattr(self, "app"):
            return
        if self.app.model.transactions:
            month = self.app.month_var.get()
            spend = self.app.model.spending_by_month().get(month, {})
            self.draw_donut(month, spend)
            self.draw_trend(month)

    # donut chart
    def draw_donut(self, month, spend):
        c = self.donut
        c.delete("all")
        width = max(c.winfo_width(), 420)
        height = max(c.winfo_height(), 280)
        draw_panel(c, width, height)
        c.create_text(22, 24, text=f"Spending breakdown  /  {month}",
                      anchor="w", font=("Arial", 12, "bold"), fill=TEXT)
        items = sorted(((k, v) for k, v in spend.items() if v > 0),
                       key=lambda kv: kv[1], reverse=True)
        total = sum(v for _, v in items)
        if total <= 0:
            c.create_text(width / 2, height / 2, text="No spending this month",
                          fill=MUTED, font=FONT)
            return
        shown = items[:8]
        other = sum(v for _, v in items[8:])
        if other > 0:
            shown.append(("Other", other))

        radius = min(height * 0.34, width * 0.20)
        cx, cy = width * 0.27, height * 0.57
        box = (cx - radius, cy - radius, cx + radius, cy + radius)
        start = 90
        for cat, val in shown:
            extent = -min(359.99, val / total * 360)
            c.create_arc(*box, start=start, extent=extent, fill=colour_for(cat),
                         outline=CARD_BG, width=3, style="pieslice")
            start += extent
        inner = radius * 0.58
        c.create_oval(cx-inner, cy-inner, cx+inner, cy+inner,
                      fill=CARD_BG, outline=CARD_BG)
        c.create_text(cx, cy-5, text=f"${total:,.0f}", font=("Arial", 19, "bold"), fill=TEXT)
        c.create_text(cx, cy+22, text="spent this month", font=FONT_SMALL, fill=MUTED)

        legend_x = width * 0.55
        line_gap = min(27, (height - 75) / max(1, len(shown)))
        for i, (cat, val) in enumerate(shown):
            y = 58 + i * line_gap
            c.create_oval(legend_x, y-5, legend_x+10, y+5,
                          fill=colour_for(cat), outline="")
            c.create_text(legend_x+19, y, anchor="w", font=FONT_SMALL, fill=TEXT,
                          text=f"{cat}   ${val:,.0f}  ({val / total * 100:.0f}%)")

    # trend chart
    def draw_trend(self, selected):
        c = self.trend
        c.delete("all")
        self.trend_points = []
        model = self.app.model
        spend = {m: sum(cats.values()) for m, cats in model.spending_by_month().items()}
        income = model.income_by_month()
        months = model.months()
        width = max(c.winfo_width(), 420)
        height = max(c.winfo_height(), 280)
        draw_panel(c, width, height)
        c.create_text(22, 24, text="Income vs spending",
                      anchor="w", font=("Arial", 12, "bold"), fill=TEXT)
        if not months:
            return
        left, right, top, bottom = 62, width-28, 62, height-42
        high = max(list(spend.values()) + list(income.values()) + [1])
        for i in range(5):
            y = bottom - i / 4 * (bottom - top)
            c.create_line(left, y, right, y, fill=BORDER, width=1)
            c.create_text(left-10, y, text=f"${high*i/4:,.0f}",
                          anchor="e", font=FONT_SMALL, fill=MUTED)
        step = (right-left) / max(1, len(months)-1)
        xs = {m: left+i*step for i, m in enumerate(months)}

        def y_of(value):
            return bottom - value/high*(bottom-top)

        for series, colour in ((spend, PRIMARY), (income, GOOD)):
            pts = [(xs[m], y_of(series.get(m, 0.0))) for m in months]
            if len(pts) > 1:
                flat = [coord for point in pts for coord in point]
                c.create_line(*flat, fill=colour, width=3, smooth=True,
                              splinesteps=16, capstyle=tk.ROUND, joinstyle=tk.ROUND)
        every = max(1, round(len(months)/7))
        for i, m in enumerate(months):
            x, y = xs[m], y_of(spend.get(m, 0.0))
            self.trend_points.append((x, m))
            if m == selected:
                c.create_line(x, top, x, bottom, fill=WARN, dash=(3, 4))
                c.create_oval(x-5, y-5, x+5, y+5, fill=WARN, outline=CARD_BG, width=2)
            elif len(months) <= 24:
                c.create_oval(x-2.5, y-2.5, x+2.5, y+2.5, fill=PRIMARY, outline="")
            if i % every == 0 or m == selected:
                c.create_text(x, bottom+17, text=m, font=("Arial", 8), fill=MUTED)

        legend_y = 25
        legend_x = width - 215
        c.create_line(legend_x, legend_y, legend_x+18, legend_y, fill=PRIMARY, width=3)
        c.create_text(legend_x+24, legend_y, text="Spending", anchor="w",
                      font=FONT_SMALL, fill=TEXT)
        c.create_line(legend_x+95, legend_y, legend_x+113, legend_y, fill=GOOD, width=3)
        c.create_text(legend_x+119, legend_y, text="Income", anchor="w",
                      font=FONT_SMALL, fill=TEXT)

    def on_trend_click(self, event):
        if not self.trend_points:
            return
        # min() with a lambda finds the point with the smallest horizontal distance
        _, month = min(self.trend_points, key=lambda p: abs(p[0] - event.x))
        self.app.month_var.set(month)
        self.app.refresh_all()


##TRANSACTIONS TAB
class TransactionsTab(BaseTab):
    COLUMNS = (("date", "Date", 100), ("description", "Description", 360),
               ("category", "Category", 130), ("amount", "Amount", 110))

    def __init__(self, notebook, app):
        super().__init__(notebook, app)
        self.sort_col = "date"
        self.sort_reverse = True
        self.row_lookup = {}

        # filter bar
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Category").pack(side="left")
        self.cat_var = tk.StringVar(value="All")
        self.cat_box = ttk.Combobox(bar, textvariable=self.cat_var, state="readonly", width=16)
        self.cat_box.pack(side="left", padx=(4, 14))
        self.cat_box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.search_var, width=22).pack(side="left", padx=(4, 14))
        self.search_var.trace_add("write", lambda *args: self.refresh())
        self.month_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Selected month only", variable=
        self.month_only, command=self.refresh).pack(side="left", padx=(0, 14))
        ttk.Button(bar, text="Teach keyword for selected row", command=self.teach_keyword).pack(side="right")

        # the table
        holder = RoundedCard(self, pad=8, fill_height=True, height=300)
        holder.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(holder.body, columns=[c[0] for c
                                                       in self.COLUMNS], show="headings")
        for col, heading, width in self.COLUMNS:
            self.tree.heading(col, text=heading, command=lambda c=col: self.sort_by(c))
            self.tree.column(col, width=width, anchor="e" if col == "amount" else "w")
        scroll = ttk.Scrollbar(holder.body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.tag_configure("income", foreground=GOOD)
        self.tree.tag_configure("unknown", background="#59451F")
        self.footer = ttk.Label(self, text="")
        self.footer.pack(anchor="w", pady=(6, 0))
#sorting
    def sort_by(self, column):
        if self.sort_col == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col, self.sort_reverse = column, False
        self.refresh()

    def refresh(self):
        model = self.app.model
        categories = ["All"] + sorted({t.category for t in model.transactions})
        self.cat_box["values"] = categories
        if self.cat_var.get() not in categories:
            self.cat_var.set("All")
        needle = self.search_var.get().strip().lower()
        month = self.app.month_var.get()
        rows = [t for t in model.transactions
                if (self.cat_var.get() == "All" or t.category == self.cat_var.get())
                and (not needle or needle in t.description.lower())
                and (not self.month_only.get() or t.month == month)]
        # A dictionary of lambdas: how to get the sort value for each column.
        keys = {"date": lambda t: t.date, "description": lambda t: t.description.lower(),
                "category": lambda t: t.category, "amount": lambda t: t.amount}
        rows.sort(key=keys[self.sort_col], reverse=self.sort_reverse)
        self.tree.delete(*self.tree.get_children())
        self.row_lookup = {}
        for t in rows:
            tag = "income" if t.category == INCOME else ("unknown" if t.category ==
                                                                      UNCATEGORISED else "")
            row_id = self.tree.insert("", "end", tags=(tag,), values=(t.date.strftime("%d/%m/%Y"),
                                                                      t.description, t.category, f"{t.amount:,.2f}"))
            self.row_lookup[row_id] = t
        total = sum(t.amount for t in rows)
        self.footer.config(text=f"Showing {len(rows):,} "
                                f"transactions  |  net amount ${total:,.2f}")

    @safe_action
    def teach_keyword(self):
       #asking for the key word
        selected = self.tree.selection()
        if not selected:
            raise ValueError("Click a transaction row first.")
        tx = self.row_lookup[selected[0]]
        keyword = simpledialog.askstring(  # pop-up asking for text
            "Teach keyword", f"Keyword to look for in descriptions like:\n{tx.description}",
            initialvalue=tx.description.split()[0].lower(), parent=self.app)
        if not keyword:  # user pressed Cancel
            return
        category = simpledialog.askstring(
            "Teach keyword", f"Which category should '{keyword}' belong to?\n"
                             "(type an existing one, or a new name)", parent=self.app)
        if not category:
            return
        self.app.model.categoriser.add_keyword(category.strip().title(), keyword)
        self.app.model.recategorise()  # applying to every transaction
        self.app.refresh_all()


# BUDGETS TAB
class BudgetsTab(BaseTab):
    BAR_WIDTH = 240
   #choices for the Calculate button.
    PERIODS = {"Last 3 months": 3, "Last 6 months": 6, "Last 12 months": 12, "All months": None}
    BUFFERS = ("0%", "5%", "10%", "15%", "20%")

    def __init__(self, notebook, app):
        super().__init__(notebook, app)
        #string variable
        self.entries = {}
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 4))
        #choosing what the calculation is based on
        ttk.Label(top, text="Based on:").pack(side="left")
        self.period_var = tk.StringVar(value="Last 6 months")
        ttk.Combobox(top, textvariable=self.period_var, values=list(self.PERIODS),
                     state="readonly", width=15).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Buffer:").pack(side="left")
        self.buffer_var = tk.StringVar(value="10%")
        ttk.Combobox(top, textvariable=self.buffer_var, values=self.BUFFERS,
                     state="readonly", width=6).pack(side="left", padx=(4, 12))
        ttk.Button(top, text="Calculate budgets", command=self.calculate).pack(side="left")
        ttk.Button(top, text="Save budgets", style="Accent.TButton",
                   command=self.save_budgets).pack(side="left", padx=8)
        ttk.Button(top, text="Clear all budgets", style="Danger.TButton",
                   command=self.clear_all).pack(side="left")
        ttk.Label(self, foreground=MUTED,
                  text="'Calculate' fills the boxes from your spending history - press 'Save budgets' "
                       "to keep them. Leave a box empty for 'no budget'.").pack(anchor="w", pady=(0, 8))
        self.grid_frame = ttk.Frame(self)
        self.grid_frame.pack(fill="both", expand=True)

    def refresh(self):
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.entries = {}
        model = self.app.model
        if not model.transactions:
            ttk.Label(self.grid_frame, text="Import a CSV to set budgets.").grid()
            return
        month = self.app.month_var.get()
        #spendings in current month
        spent = model.spending_by_month().get(month, {})
        budgets = self.app.budgets.budgets
        # Dict comprehension: category -> its budget status tuple.
        status = {cat: (s, lim, st) for cat, s, lim, st in self.app.budgets.check(spent)}
        headers = ("Category", "Monthly budget ($)", f"Spent in {month}", "Usage", "Status")
        for col, text in enumerate(headers):  # header row
            ttk.Label(self.grid_frame, text=text, font=FONT_BOLD).grid(
                row=0, column=col, sticky="w", padx=8, pady=6)
        for row, cat in enumerate(model.spending_categories(), start=1):
            var = tk.StringVar(value=f"{budgets[cat]:.2f}" if cat in budgets else "")
            self.entries[cat] = var  # remember it for save_budgets()
            ttk.Label(self.grid_frame, text=cat).grid(row=row, column=0, sticky="w", padx=8, pady=3)
            ttk.Entry(self.grid_frame, textvariable=var, width=14).grid(row=row, column=1, padx=8)
            ttk.Label(self.grid_frame, text=f"${spent.get(cat, 0):,.2f}").grid(
                row=row, column=2, sticky="w", padx=8)
            # ---- progress bar drawn on a tiny canvas ----
            bar = tk.Canvas(self.grid_frame, width=self.BAR_WIDTH, height=18,
                            bg="#374151", highlightthickness=0)
            bar.grid(row=row, column=3, padx=8)
            label, colour = "No budget", MUTED
            if cat in status:
                s, limit, state = status[cat]
                ratio = s / limit if limit else 0  # fraction of budget used
                colour = {"OVER BUDGET": BAD, "WARNING": WARN, "OK": GOOD}[state]
                bar.create_rectangle(0, 0, min(ratio, 1) * self.BAR_WIDTH, 18,
                                     fill=colour, outline="")  # filled part (max = full bar)
                bar.create_text(self.BAR_WIDTH / 2, 9, text=f"{ratio * 100:.0f}%",
                                font=FONT_SMALL, fill=TEXT)
                label = state
            tk.Label(self.grid_frame, text=label, fg=colour, bg=BG,
                     font=FONT_BOLD).grid(row=row, column=4, sticky="w", padx=8)

    @safe_action
    def save_budgets(self):
        for cat, var in self.entries.items():
            text = var.get().strip().replace("$", " ")
            if text == "":
                self.app.budgets.clear_budget(cat)
                continue
            try:
                amount = float(text)
            except ValueError:
                raise ValueError(f"'{text}' is not valid number for {cat}.")
            self.app.budgets.set_budget(cat, amount)
        self.app.refresh_all()
        self.app.set_status("Budgets saved.")

    @safe_action
    def calculate(self):
        self.app.model.require_data()

        # Check whether any budget input has been entered
        has_input = any(
            var.get().strip()
            for var in self.entries.values()
        )

        # Display warning if all fields are empty
        if not has_input:
            messagebox.showwarning(
                "No Input Provided",
                "No budget amount has been entered.\n"
                "Please enter at least one budget value "
                "before calculating."
            )
            return

        months = self.PERIODS[self.period_var.get()]
        buffer = int(self.buffer_var.get().rstrip("%")) / 100
        averages = self.app.model.category_averages(months)

        filled = 0

        for cat, var in self.entries.items():
            current = var.get().strip()

            # Skip empty budget fields
            if current == "":
                continue

            # Preserve previously saved budgets
            if cat in self.app.budgets.budgets:
                continue

            average = averages.get(cat, 0.0)

            if average > 0 and cat != UNCATEGORISED:
                suggested = round(average * (1 + buffer))
                var.set(f"{suggested:.2f}")
                filled += 1

        self.app.set_status(
            f"Calculated {filled} budgets. "
            "Empty categories were skipped."
        )

    @safe_action
    def clear_all(self):
        #removing every saved budget  and emptying the boxes.
        saved = len(self.app.budgets.budgets)
        typed = any(var.get().strip() for var in self.entries.values())
        if not saved and not typed:
            messagebox.showinfo("Nothing to clear", "There are no budgets to clear.")
            return
        if saved and not messagebox.askyesno(
                "Clear all budgets", f"Remove all {saved} saved budgets?\nThis cannot be undone."):
            return
        self.app.budgets.clear_all()
        self.app.refresh_all()
        self.app.set_status("All budgets cleared.")


# KEYWORDS TAB
class KeywordsTab(BaseTab):
    def __init__(self, notebook, app):
        super().__init__(notebook, app)
        top = ttk.Frame(self)
        top.pack(fill="both", expand=True)
        left = ttk.LabelFrame(top, text="Categories", padding=6)
        left.pack(side="left", fill="y", padx=(0, 8))
        self.cat_list = tk.Listbox(left, width=22, height=14, exportselection=False, font=FONT,
                                   bg=CARD_BG, fg=TEXT, selectbackground=PRIMARY_DARK,
                                   selectforeground="#FFFFFF", highlightbackground=BORDER)
        self.cat_list.pack(fill="y", expand=True)
        self.cat_list.bind("<<ListboxSelect>>", lambda e: self.show_keywords())
        mid = ttk.LabelFrame(top, text="Keywords for the selected category", padding=6)
        mid.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.keyword_label = ttk.Label(mid, text="", wraplength=300, justify="left")
        self.keyword_label.pack(anchor="nw")
        right = ttk.LabelFrame(top, text="Couldn't categorise these", padding=6)
        right.pack(side="left", fill="both", expand=True)
        self.unknown_list = tk.Listbox(right, height=14, font=FONT, bg=CARD_BG, fg=TEXT,
                                       selectbackground=PRIMARY_DARK, selectforeground="#FFFFFF",
                                       highlightbackground=BORDER)
        self.unknown_list.pack(fill="both", expand=True)
        # bottom - add a keyword
        add = ttk.LabelFrame(self, text="Teach a new keyword", padding=8)
        add.pack(fill="x", pady=(10, 0))
        ttk.Label(add, text="Category:").pack(side="left")
        self.new_cat = tk.StringVar()
        self.new_cat_box = ttk.Combobox(add, textvariable=self.new_cat, width=18)  # editable
        self.new_cat_box.pack(side="left", padx=(4, 12))
        ttk.Label(add, text="Keyword:").pack(side="left")
        self.new_word = tk.StringVar()
        ttk.Entry(add, textvariable=self.new_word, width=22).pack(side="left", padx=(4, 12))
        ttk.Button(add, text="Add keyword", style="Accent.TButton",
                   command=self.add_keyword).pack(side="left")
        ttk.Button(add,text="Delete Category"
                   ,command=self.delete_category).pack(side="left", padx=5)

    def refresh(self):
        rules = self.app.model.categoriser.rules
        chosen = self.cat_list.curselection()
        self.cat_list.delete(0, "end")
        for cat in rules:
            self.cat_list.insert("end", cat)
        if chosen:
            self.cat_list.selection_set(chosen[0])
        self.new_cat_box["values"] = list(rules)
        self.show_keywords()
        self.unknown_list.delete(0, "end")
        # set comprehension: unique description of uncategorised transactions.
        unknown = sorted({t.description for t in self.app.model.uncategorised()})
        for description in unknown[:200]:
            self.unknown_list.insert("end", description)
        if not unknown:
            self.unknown_list.insert("end", "Everything is categorised!")

    def show_keywords(self):
        # showing the keywords belonging to the highlighted category."""
        selection = self.cat_list.curselection()
        if not selection:
            self.keyword_label.config(text="Select a category on the left.")
            return
        cat = self.cat_list.get(selection[0])
        words = self.app.model.categoriser.rules.get(cat, [])
        self.keyword_label.config(text=", ".join(words) if words else "(no keywords yet)")

    @safe_action
    def add_keyword(self):
        self.app.model.categoriser.add_keyword(self.new_cat.get().strip().title(), self.new_word.get())
        self.app.model.recategorise()
        self.app.refresh_all()
        left_over = len(self.app.model.uncategorised())
        self.app.set_status(f"Keyword added.{left_over} transaction(s) still uncategorised.")

    @safe_action
    def delete_category(self):
        category = self.new_cat.get().strip()

        if not category:
            messagebox.showwarning(
                "No Category Selected",
                "Please select a category to delete."
            )
            return

        confirm = messagebox.askyesno(
            "Delete Category",
            f"Are you sure you want to delete '{category}'?\n\n"
            "All keywords associated with this category "
            "will also be removed."
        )

        if not confirm:
            return

        self.app.model.categoriser.delete_category(category)

        self.app.model.recategorise()
        self.app.refresh_all()

        self.new_cat.set("")
        self.new_word.set("")

        self.app.set_status(
            f"Category '{category}' deleted successfully."
        )


"""Application Main Window"""

class ExpenseApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SpendSpy")
        self.geometry("1240x860")  # wider layout for a more comfortable dashboard
        self.minsize(1080, 760)
        self.configure(bg=BG)
       #backbone of program
        self.categoriser = Categoriser()
        self.budgets = BudgetManager()
        self.model = ExpenseAnalyzer(self.categoriser)
        #holds current month
        self.month_var = tk.StringVar()
        #building window
        self.setup_style()
        self.build_toolbar()
        self.status = ttk.Label(self, text="Ready.", anchor="w", foreground=MUTED)
        self.status.pack(side="bottom", fill="x", padx=18, pady=(0, 10))  # status bar at the bottom
        self.notebook = ttk.Notebook(self)  # the row of tabs
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.tabs = {}  # tab name -> tab object
        for name, tab_class in (("Dashboard", DashboardTab), ("Transactions", TransactionsTab),
                                ("Budgets", BudgetsTab), ("Keywords", KeywordsTab)):
            tab = tab_class(self.notebook, self)
            self.notebook.add(tab, text=f"  {name}  ")
            self.tabs[name] = tab
        #file will be loaded automatically
        if os.path.exists(DEFAULT_CSV):
            self.load_file(DEFAULT_CSV)
        self.refresh_all()  #

    def setup_style(self):
        """Applying the theme to ttk widgets."""
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=FONT)

        style.configure("TLabelframe", background=BG, bordercolor=BORDER,
                        lightcolor=BG, darkcolor=BG, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=BG, foreground=TEXT,
                        font=FONT_BOLD)
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=FONT)
        style.map("TCheckbutton", background=[("active", BG)],
                  foreground=[("disabled", MUTED)])


        style.configure("TButton", padding=9, font=FONT, relief="flat", background="#26364D",
                        foreground=TEXT, bordercolor="#26364D",
                        lightcolor="#26364D", darkcolor="#26364D", borderwidth=1)
        style.map("TButton", background=[("active", "#34445B")],
                  foreground=[("disabled", MUTED)])
        style.configure("Accent.TButton", background=PRIMARY, foreground="#0B1220",
                        font=FONT_BOLD, padding=8, borderwidth=1, bordercolor=PRIMARY,
                        lightcolor=PRIMARY, darkcolor=PRIMARY)
        style.map("Accent.TButton", background=[("active", PRIMARY_DARK)],
                  foreground=[("active", "#FFFFFF")])

        #Clear all budgets
        style.configure("Danger.TButton", background="#26364D", foreground=BAD, padding=9,
                        font=FONT_BOLD, bordercolor="#26364D", lightcolor="#26364D",
                        darkcolor="#26364D", borderwidth=1)
        style.map("Danger.TButton", background=[("active", "#3A2A33")],
                  foreground=[("active", BAD)])

        # border outline
        style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(4, 8, 4, 0),
                        bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure("TNotebook.Tab", padding=(18, 10), font=FONT_BOLD,
                        background="#273449", foreground=MUTED, borderwidth=1,
                        bordercolor=BORDER, lightcolor="#273449", darkcolor="#273449")
        style.map("TNotebook.Tab",
                  background=[("selected", CARD_BG), ("!selected", "#273449"),
                              ("active", "#34445B")],
                  foreground=[("selected", PRIMARY), ("!selected", MUTED)],
                  lightcolor=[("selected", CARD_BG)], darkcolor=[("selected", CARD_BG)])


        no_border = [("Treeview.treearea", {"sticky": "nswe"})]
        style.layout("Treeview", no_border)
        style.layout("Compact.Treeview", no_border)
        style.configure("Treeview", rowheight=34, font=FONT, relief="flat",
                        background=CARD_BG, fieldbackground=CARD_BG,
                        foreground=TEXT, borderwidth=0)
        style.configure("Treeview.Heading", font=FONT_BOLD, relief="flat",
                        background="#273449", foreground=TEXT, padding=(8, 8))
        style.map("Treeview", background=[("selected", "#1D4ED8")],
                  foreground=[("selected", "#FFFFFF")])
        #table for the dashboard
        style.configure("Compact.Treeview", rowheight=26, font=FONT, relief="flat",
                        background=CARD_BG, fieldbackground=CARD_BG,
                        foreground=TEXT, borderwidth=0)
        style.configure("Compact.Treeview.Heading", font=FONT_BOLD, relief="flat",
                        background="#273449", foreground=TEXT, padding=(8, 5))
        style.map("Compact.Treeview", background=[("selected", "#1D4ED8")],
                  foreground=[("selected", "#FFFFFF")])

        #outline for input boxes
        style.configure("TEntry", padding=6, fieldbackground="#273449", foreground=TEXT,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.configure("TCombobox", padding=5, fieldbackground="#273449",
                        background="#374151", foreground=TEXT, arrowcolor=TEXT,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#273449")],
                  foreground=[("readonly", TEXT)],
                  selectbackground=[("readonly", "#273449")],
                  selectforeground=[("readonly", TEXT)])
        style.configure("Vertical.TScrollbar", background="#374151",
                        troughcolor=CARD_BG, bordercolor=CARD_BG, arrowcolor=TEXT,
                        lightcolor="#374151", darkcolor="#374151")

    def build_toolbar(self):
        #Top bar: Import / Export buttons on the left, month selector on the right.
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=18, pady=14)
        ttk.Button(bar, text="Import CSV", style="Accent.TButton",
                   command=self.on_import).pack(side="left")
        ttk.Button(bar, text="Export report",
                   command=self.export_report).pack(side="left", padx=8)

        ttk.Button(bar, text=">", width=3, command=lambda: self.shift_month(1)).pack(side="right")
        self.month_box = ttk.Combobox(bar, textvariable=self.month_var, state="readonly", width=10)
        self.month_box.pack(side="right", padx=4)
        self.month_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_all())
        ttk.Button(bar, text="<", width=3, command=lambda: self.shift_month(-1)).pack(side="right")
        ttk.Label(bar, text="Month:").pack(side="right", padx=(0, 6))

    # helper method
    def set_status(self, text):
        self.status.config(text=text)

    def refresh_all(self):
        months = self.model.months()
        self.month_box["values"] = months
        if months and self.month_var.get() not in months:
            self.month_var.set(months[-1])
        for tab in self.tabs.values():
            tab.refresh()

    def shift_month(self, step):
        #The < and > buttons on the right
        months = self.model.months()
        if not months:
            return
        current = self.month_var.get()
        index = months.index(current) if current in months else len(months) - 1
        index = max(0, min(len(months) - 1, index + step))  # stay inside the list
        self.month_var.set(months[index])
        self.refresh_all()

    # button handlers

    @safe_action
    def load_file(self, path):
        count, skipped = self.model.load_csv(path)

        months = self.model.months()
        self.month_var.set(months[-1])
        unknown = len(self.model.uncategorised())
        self.set_status(
            f"Loaded {count:,} transactions ({months[0]} to {months[-1]}), "
            f"{skipped} skipped, {unknown} uncategorised - {os.path.basename(path)}"
        )

    def on_import(self):
    #adding a button to import a csv file other than the default
        path = filedialog.askopenfilename(title="Choose a transactions CSV",
                                          filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    # empty string = user pressed Cancel
        if path:
            self.load_file(path)
            self.refresh_all()

    @safe_action
    def export_report(self):
        # export report button: save the monthly report as text file
        self.model.require_data()
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            initialfile="spending_report.txt", filetypes=[("Text files", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as file:
            file.write(self.model.build_report())
        self.set_status(f"Report saved to {path}")
        messagebox.showinfo("Export complete", f"Report saved to: \n{path}")


if __name__ == "__main__":
    ExpenseApp().mainloop()