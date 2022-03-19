import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks:
    stocks the user owns, the numbers of shares owned, the current price of each stock, and the total value of each holding"""

    holdings = db.execute(
        "SELECT symbol, SUM(shares) as shares, transaction_type FROM shares WHERE user_id = ? GROUP BY symbol;",
        session["user_id"],
    )

    total_fv = 0

    for holding in holdings:

        # Query quote, name, price
        quote = lookup(holding["symbol"])
        holding["name"] = quote["name"]
        holding["price"] = quote["price"]

        # Calculate fair value
        holding["total"] = holding["price"] * holding["shares"]

        # Calculate total holdings
        total_fv += holding["total"]

    # Check total cash
    balance = db.execute("SELECT cash FROM users WHERE id = ? ", session["user_id"])[0]["cash"]

    return render_template("index.html", holdings=holdings, total_fv=total_fv, total_cash=balance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        # Ensure quote and shares was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        elif not request.form.get("shares"):
            return apology("must provide shares", 400)
        else:
            symbol = request.form.get("symbol").upper()
            shares = request.form.get("shares")

            # Ensure shares is an integer
            try:
                shares = int(shares)
            except:
                return apology("Shares must be an integer", 400)

            # Ensure shares is above zero
            if shares <= 0:
                return apology("Shares must be above zero", 400)

            # Look up quote for symbol
            try:
                quote = lookup(symbol)
                price = int(quote["price"])
            except:
                return apology("Invalid symbol", 400)

            # Calculate purchase cost
            cost = price * shares

            # Check user's balance
            balance = db.execute("SELECT cash FROM users WHERE id = ? ", session["user_id"])[0]["cash"]
            if cost > balance:
                return apology("You don't have enough balance to purchase this amount of shares", 400)
            else:

                # Deduct balance from user
                db.execute(
                    "UPDATE users SET cash = cash - ? WHERE id = ?",
                    cost,
                    session["user_id"],
                )

                # Purchase shares
                db.execute(
                    "INSERT INTO shares (user_id, symbol, shares, price, transaction_type) VALUES (?, ?, ?, ?, ?)",
                    session["user_id"],
                    symbol,
                    shares,
                    cost,
                    "buy",
                )

                # Message flashing https://flask.palletsprojects.com/en/1.1.x/quickstart/#message-flashing
                flash("Purchase completed")
                return redirect("/")

    # No form submission actions
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions
    whether a stock was bought or sold and include the stock’s symbol, the (purchase or sale) price,
    the number of shares bought or sold, and the date and time at which the transaction occurred."""

    history_entries = db.execute(
        "SELECT * FROM shares WHERE user_id = ?",
        session["user_id"]
        )

    return render_template("history.html", history_entries=history_entries)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":

        # Ensure quote was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        else:
            symbol = request.form.get("symbol")

            try:
                quote = lookup(symbol)
                # Look up quote for symbol
                return render_template(
                    "quote_result.html",
                    name=quote["name"],
                    price=quote["price"],
                    symbol=quote["symbol"]
                )

            except:
                return apology("Invalid symbol", 400)

    # No form submission actions
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    #return apology("TODO")
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)

        # Ensure password confirmation was valid
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password confirmation does not match", 400)

        else:

            # Get variables from form submission
            username = request.form.get("username")
            password = request.form.get("password")

            # Query database for username to see if this already exists
            rows = db.execute("SELECT * FROM users WHERE username = ?", username)
            if len(rows) > 0:
                return apology("Username already exists", 400)

            else:

                # Hash password https://werkzeug.palletsprojects.com/en/1.0.x/utils/#werkzeug.security.generate_password_hash
                hash = generate_password_hash(
                    password, method="pbkdf2:sha256", salt_length=32
                )

                # Insert row to database
                db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)

                # Redirect user to login form
                return redirect("/")

    # No form submission actions
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    if request.method == "POST":

        # Ensure quote and shares was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        elif not request.form.get("shares"):
            return apology("must provide shares", 400)
        else:
            symbol = request.form.get("symbol").upper()
            shares = request.form.get("shares")

            # Ensure shares is an integer
            try:
                shares = int(shares)
            except:
                return apology("Shares must be an integer", 400)

            # Ensure shares is above zero
            if shares <= 0:
                return apology("Shares must be above zero", 400)
            shares=int(shares)

            # Look up quote for symbol
            quote = lookup(symbol)
            price = int(quote["price"])

            # Calculate selling proceeds
            proceeds = price * shares

            # Check user's holding
            try:
                holding = db.execute("SELECT SUM(shares) as shares FROM shares WHERE user_id = ? AND symbol = ?;",
                    session["user_id"],
                    symbol,
                )
            except:
                return apology("You don't have holdings of this company", 400)

            holding_shares = int(holding[0]["shares"])

            if shares > holding_shares:
                return apology("You don't have enough shares to be sold", 400)
            else:

                # Add balance to user
                db.execute(
                    "UPDATE users SET cash = cash + ? WHERE id = ?",
                    proceeds,
                    session["user_id"],
                )

                # Sell shares
                shares = -1 * shares
                db.execute(
                    "INSERT INTO shares (user_id, symbol, shares, price, transaction_type) VALUES (?, ?, ?, ?, ?)",
                    session["user_id"],
                    symbol,
                    shares,
                    proceeds,
                    "sell",
                )

                # Message flashing https://flask.palletsprojects.com/en/1.1.x/quickstart/#message-flashing
                flash("Selling completed")
                return redirect("/")

    # No form submission actions
    else:
        holdings = db.execute(
            "SELECT symbol FROM shares WHERE user_id = ? GROUP BY symbol;",
            session["user_id"],
        )
        symbols = []
        for holding in holdings:
            symbols.append(holding['symbol'])

        return render_template("sell.html", symbols=symbols)



@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """Add cash"""

    if request.method == "POST":

        # Ensure cash was submitted
        if not request.form.get("cash"):
            return apology("must provide cash amount", 400)
        else:
            cash = request.form.get("cash")
            # Add balance to user
            db.execute(
                "UPDATE users SET cash = cash + ? WHERE id = ?",
                cash,
                session["user_id"],
            )

            flash("Balance added")
            return redirect("/add")

    # No form submission actions
    else:

        # Check user's balance
        balance = db.execute("SELECT cash FROM users WHERE id = ? ", session["user_id"])[0]["cash"]
        return render_template("add.html", balance=balance)
