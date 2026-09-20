import os
import uuid
import requests

from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)


# ==========================================================
# SECRET KEY
# ==========================================================

app.secret_key = os.environ.get("SECRET_KEY", "development-secret-key")


# ==========================================================
# MYSQL CONFIGURATION
# ==========================================================

app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"

# Put your existing MySQL password here
app.config["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD")

app.config["MYSQL_DB"] = "rubix_club"
app.config["MYSQL_CURSORCLASS"] = "DictCursor"

mysql = MySQL(app)


def get_db_connection():
    return mysql.connection

GOOGLE_SHEETS_URL = "https://script.google.com/macros/s/AKfycbw-YBdHXt92qy5X-7chLPlBtvBUf9LYS4tMOCtk7J45_KszipWipZYzC-_4CllVJgKUnA/exec"

# ==========================================================
# ADMIN LOGIN DETAILS
# ==========================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "rubix123"


# ==========================================================
# ADMIN LOGIN CHECK
# ==========================================================

def admin_required():

    return session.get(
        "admin_logged_in",
        False
    )



# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():

    cursor = mysql.connection.cursor()

    # ------------------------------------------------------
    # HOME FEATURED PHOTO
    # ------------------------------------------------------

    home_gallery = [
    {
        "image": url_for("static", filename="images/home-banner.jpg"),
        "title": "RUBIX CLUB",
        "description": "Think. Solve. Conquer."
    },
    {
        "image": url_for("static", filename="images/home-banner-2.jpg"),
        "title": "APTITUDE AUCTION",
        "description": "Challenge Your Thinking"
    },
    {
        "image": url_for("static", filename="images/home-banner-3.jpg"),
        "title": "RUBIX MOMENTS",
        "description": "Memories That Stay"
    }
]
    # ------------------------------------------------------
    # UPCOMING EVENTS
    # ------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            title,
            description,
            event_date,
            event_time,
            venue,
            category,
            team_size,
            image,
            registration_link,
            status
        FROM events
        WHERE status = 'upcoming'
        ORDER BY event_date ASC
        LIMIT 3
    """)

    home_events = cursor.fetchall()

    cursor.close()

    return render_template(
        "index.html",
        home_gallery=home_gallery,
        home_events=home_events
    )
# ==========================================================
# ABOUT - PUBLIC
# ==========================================================

@app.route("/about")
def about():

    return render_template("about.html")
# ==========================================================
# EVENTS - PUBLIC
# ==========================================================

@app.route("/events")
def events():

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT
            id,
            title,
            description,
            event_date,
            event_time,
            venue,
            category,
            team_size,
            max_teams,
            image,
            registration_link,
            registration_qr,
            rules,
            status
        FROM events
        ORDER BY event_date ASC
    """)

    events_data = cursor.fetchall()

    # ------------------------------------------------------
    # ADD CAPACITY INFORMATION TO EACH EVENT
    # ------------------------------------------------------

    events_with_capacity = []

    for event in events_data:

        cursor.execute("""
            SELECT COUNT(*) AS registered_teams
            FROM event_registrations
            WHERE event_id = %s
        """, (event["id"],))

        count_row = cursor.fetchone()

        registered_teams = int(
            count_row["registered_teams"] or 0
        )

        max_teams = int(
            event["max_teams"] or 30
        )

        remaining_teams = max(
            max_teams - registered_teams,
            0
        )

        almost_full_threshold = max(
            1,
            (max_teams * 8 + 9) // 10
        )

        if registered_teams >= max_teams:

            capacity_status = "FULL"

        elif registered_teams >= almost_full_threshold:

            capacity_status = "ALMOST FULL"

        else:

            capacity_status = "OPEN"

        # Convert database row into a dictionary
        event_data = dict(event)

        event_data["registered_teams"] = registered_teams
        event_data["remaining_teams"] = remaining_teams
        event_data["capacity_status"] = capacity_status

        events_with_capacity.append(event_data)

    cursor.close()

    return render_template(
        "events.html",
        events=events_with_capacity
    )
# ==========================================================
# EVENT DETAILS
# ==========================================================

@app.route("/event/<int:event_id>")
def event_details(event_id):

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT
            id,
            title,
            description,
            event_date,
            event_time,
            venue,
            category,
            team_size,
            image,
            registration_link,
            registration_qr,
            rules,
            status,
            created_at
        FROM events
        WHERE id = %s
    """, (event_id,))

    event = cursor.fetchone()

    cursor.close()

    if not event:
        return """
        <h1>Event Not Found</h1>
        <p>The requested event does not exist.</p>
        """

    # ------------------------------------------------------
    # FORMAT MYSQL TIME
    # MySQL TIME is returned as timedelta by some drivers.
    # Convert it to a normal display string such as 10:00 AM.
    # ------------------------------------------------------

    event_time = event["event_time"]

    if event_time is not None:

        total_seconds = int(
            event_time.total_seconds()
        )

        hours = (total_seconds // 3600) % 24
        minutes = (total_seconds % 3600) // 60

        period = "AM" if hours < 12 else "PM"

        display_hour = hours % 12

        if display_hour == 0:
            display_hour = 12

        event["event_time_display"] = (
            f"{display_hour:02d}:{minutes:02d} {period}"
        )

    else:

        event["event_time_display"] = "Time not specified"

    return render_template(
        "event_details.html",
        event=event
    )


# ==========================================================
# GALLERY - PUBLIC
# ==========================================================

@app.route("/gallery")
def gallery():

    cursor = mysql.connection.cursor()

    # ------------------------------------------------------
    # GET GALLERIES
    # ------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            title,
            description,
            cover_image,
            event_id,
            created_at
        FROM gallery
        ORDER BY id DESC
    """)

    galleries = cursor.fetchall()

    # ------------------------------------------------------
    # GET GALLERY IMAGES
    # ------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            gallery_id,
            image,
            uploaded_at
        FROM gallery_images
        ORDER BY id DESC
    """)

    gallery_images = cursor.fetchall()

    cursor.close()

    return render_template(
        "gallery.html",
        galleries=galleries,
        gallery_images=gallery_images
    )

# ==========================================================
# EVENT REGISTRATION
# ==========================================================

@app.route("/register/<int:event_id>", methods=["GET", "POST"])
def register_event(event_id):

    cursor = mysql.connection.cursor()

    # ------------------------------------------------------
    # GET EVENT DETAILS
    # ------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            title,
            event_date,
            event_time,
            venue,
            team_size,
            max_teams,
            status
        FROM events
        WHERE id = %s
    """, (event_id,))

    event = cursor.fetchone()

    if not event:
        cursor.close()
        return "<h1>Event Not Found</h1>"

    # ------------------------------------------------------
    # GET CURRENT TEAM COUNT
    # ------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*) AS registered_teams
        FROM event_registrations
        WHERE event_id = %s
    """, (event_id,))

    count_row = cursor.fetchone()

    registered_teams = int(
        count_row["registered_teams"] or 0
    )

    max_teams = int(
        event["max_teams"] or 30
    )

    remaining_teams = max(
        max_teams - registered_teams,
        0
    )

    # ------------------------------------------------------
    # CALCULATE CAPACITY STATUS
    # ------------------------------------------------------

    almost_full_threshold = max(
        1,
        (max_teams * 8 + 9) // 10
    )

    if registered_teams >= max_teams:

        capacity_status = "FULL"

    elif registered_teams >= almost_full_threshold:

        capacity_status = "ALMOST FULL"

    else:

        capacity_status = "OPEN"

    # ------------------------------------------------------
    # POST - PROCESS REGISTRATION
    # ------------------------------------------------------

    if request.method == "POST":

        # ----------------------------------------------
        # CHECK CAPACITY AGAIN
        # ----------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS registered_teams
            FROM event_registrations
            WHERE event_id = %s
        """, (event_id,))

        latest_count = cursor.fetchone()

        registered_teams = int(
            latest_count["registered_teams"] or 0
        )

        remaining_teams = max(
            max_teams - registered_teams,
            0
        )

        if registered_teams >= max_teams:

            cursor.close()

            flash(
                "Registration is full for this event.",
                "error"
            )

            return redirect(
                url_for(
                    "register_event",
                    event_id=event_id
                )
            )

        # ----------------------------------------------
        # GET FORM DATA
        # ----------------------------------------------

        team_name = request.form.get(
            "team_name",
            ""
        ).strip()

        participant_name = request.form.get(
            "participant_name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        year = request.form.get(
            "year",
            ""
        ).strip()

        section = request.form.get(
            "section",
            ""
        ).strip()

        member_2 = request.form.get(
            "member_2",
            ""
        ).strip()

        member_3 = request.form.get(
            "member_3",
            ""
        ).strip()

        member_4 = request.form.get(
            "member_4",
            ""
        ).strip()

        # ----------------------------------------------
        # VALIDATION
        # ----------------------------------------------

        if not team_name:

            cursor.close()

            flash(
                "Team name is required.",
                "error"
            )

            return render_template(
                "register.html",
                event=event,
                capacity_status=capacity_status,
                registered_teams=registered_teams,
                remaining_teams=remaining_teams
            )

        if not participant_name:

            cursor.close()

            flash(
                "Team leader name is required.",
                "error"
            )

            return render_template(
                "register.html",
                event=event,
                capacity_status=capacity_status,
                registered_teams=registered_teams,
                remaining_teams=remaining_teams
            )

        if not email:

            cursor.close()

            flash(
                "Team leader email is required.",
                "error"
            )

            return render_template(
                "register.html",
                event=event,
                capacity_status=capacity_status,
                registered_teams=registered_teams,
                remaining_teams=remaining_teams
            )

        if not phone:

            cursor.close()

            flash(
                "Team leader phone is required.",
                "error"
            )

            return render_template(
                "register.html",
                event=event,
                capacity_status=capacity_status,
                registered_teams=registered_teams,
                remaining_teams=remaining_teams
            )

        if not year:

            cursor.close()

            flash(
                "Please select your year.",
                "error"
            )

            return render_template(
                "register.html",
                event=event,
                capacity_status=capacity_status,
                registered_teams=registered_teams,
                remaining_teams=remaining_teams
            )

        if not section:

            cursor.close()

            flash(
                "Please select your section.",
                "error"
            )

            return render_template(
                "register.html",
                event=event,
                capacity_status=capacity_status,
                registered_teams=registered_teams,
                remaining_teams=remaining_teams
            )

        if not member_2 or not member_3 or not member_4:

            cursor.close()

            flash(
                "All 4 team member names are required.",
                "error"
            )

            return render_template(
                "register.html",
                event=event,
                capacity_status=capacity_status,
                registered_teams=registered_teams,
                remaining_teams=remaining_teams
            )

        # ----------------------------------------------
        # CREATE REGISTRATION ID
        # ----------------------------------------------

        registration_id = str(
            uuid.uuid4()
        )[:8].upper()

        # ----------------------------------------------
        # GOOGLE SHEETS DATA
        # ----------------------------------------------

        google_data = {

            "registration_id": registration_id,

            "event": event["title"],

            "team_name": team_name,

            "team_leader_name": participant_name,

            "team_leader_email": email,

            "team_leader_phone": phone,

            "year": year,

            "section": section,

            "member_2": member_2,

            "member_3": member_3,

            "member_4": member_4,

            "status": "new",

            "registered_at": ""
        }

        # ----------------------------------------------
        # SAVE TO GOOGLE SHEETS
        # ----------------------------------------------

        try:

            response = requests.post(
                GOOGLE_SHEETS_URL,
                json=google_data,
                timeout=15
            )

            response.raise_for_status()

            result = response.json()

            if not result.get("success"):

                cursor.close()

                flash(
                    "Registration could not be saved to Google Sheets.",
                    "error"
                )

                return render_template(
                    "register.html",
                    event=event,
                    capacity_status=capacity_status,
                    registered_teams=registered_teams,
                    remaining_teams=remaining_teams
                )

        except Exception as error:

            print(
                "Google Sheets Error:",
                error
            )

            cursor.close()

            flash(
                "Unable to connect to Google Sheets. Please try again.",
                "error"
            )

            return render_template(
                "register.html",
                event=event,
                capacity_status=capacity_status,
                registered_teams=registered_teams,
                remaining_teams=remaining_teams
            )

        # ----------------------------------------------
        # FINAL CAPACITY CHECK
        # ----------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS registered_teams
            FROM event_registrations
            WHERE event_id = %s
        """, (event_id,))

        final_count = cursor.fetchone()

        final_registered_teams = int(
            final_count["registered_teams"] or 0
        )

        if final_registered_teams >= max_teams:

            cursor.close()

            flash(
                "Registration filled up just before your submission. Please try another event.",
                "error"
            )

            return redirect(
                url_for(
                    "register_event",
                    event_id=event_id
                )
            )

        # ----------------------------------------------
        # SAVE TO MYSQL
        # ----------------------------------------------

        cursor.execute("""
            INSERT INTO event_registrations
            (
                event_id,
                team_name,
                participant_name,
                email,
                phone,
                members,
                status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (

            event_id,

            team_name,

            participant_name,

            email,

            phone,

            f"{participant_name}, "
            f"{member_2}, "
            f"{member_3}, "
            f"{member_4}",

            "new"
        ))

        mysql.connection.commit()

        cursor.close()

        # ----------------------------------------------
        # REGISTRATION SUCCESS
        # ----------------------------------------------

        return redirect(
            url_for(
                "registration_success",
                event_id=event_id
            )
        )

    # --------------------------------------------------
    # GET REQUEST
    # --------------------------------------------------

    cursor.close()

    return render_template(
        "register.html",

        event=event,

        capacity_status=capacity_status,

        registered_teams=registered_teams,

        remaining_teams=remaining_teams
    )
# ==========================================================
# REGISTRATION SUCCESS
# ==========================================================

@app.route("/registration-success/<int:event_id>")
def registration_success(event_id):

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT title
        FROM events
        WHERE id = %s
    """, (event_id,))

    event = cursor.fetchone()

    cursor.close()

    if not event:
        return redirect(
            url_for("events")
        )

    return f"""
    <!DOCTYPE html>

    <html lang="en">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>Registration Successful | RUBIX Club</title>


        <style>

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}


            body {{

                min-height: 100vh;

                display: flex;

                align-items: center;

                justify-content: center;

                padding: 30px;

                background:
                    radial-gradient(
                        circle at 15% 20%,
                        rgba(124, 58, 237, 0.14),
                        transparent 30%
                    ),
                    radial-gradient(
                        circle at 85% 80%,
                        rgba(6, 182, 212, 0.10),
                        transparent 30%
                    ),
                    #070b1a;

                color: #f1f3f7;

                font-family:
                    Arial,
                    Helvetica,
                    sans-serif;

                overflow: hidden;

            }}


            /* ==========================================
               BACKGROUND GLOW
            ========================================== */

            .glow {{

                position: fixed;

                width: 350px;

                height: 350px;

                border-radius: 50%;

                filter: blur(120px);

                pointer-events: none;

            }}


            .glow-one {{

                top: -180px;

                left: -150px;

                background:
                    rgba(124, 58, 237, 0.15);

            }}


            .glow-two {{

                bottom: -180px;

                right: -150px;

                background:
                    rgba(6, 182, 212, 0.12);

            }}


            /* ==========================================
               SUCCESS CARD
            ========================================== */

            .success-card {{

                width: 100%;

                max-width: 650px;

                position: relative;

                z-index: 2;

                padding: 55px 50px;

                text-align: center;

                border-radius: 28px;

                border:
                    1px solid
                    rgba(139, 92, 246, 0.20);

                background:
                    linear-gradient(
                        145deg,
                        rgba(255,255,255,0.055),
                        rgba(255,255,255,0.018)
                    );

                box-shadow:
                    0 35px 90px
                    rgba(0, 0, 0, 0.35);

                backdrop-filter: blur(20px);

            }}


            /* ==========================================
               SUCCESS ICON
            ========================================== */

            .success-icon {{

                width: 85px;

                height: 85px;

                margin: 0 auto 25px;

                display: flex;

                align-items: center;

                justify-content: center;

                border-radius: 50%;

                background:
                    linear-gradient(
                        135deg,
                        #7c3aed,
                        #06b6d4
                    );

                box-shadow:
                    0 15px 40px
                    rgba(124, 58, 237, 0.30);

                font-size: 38px;

                font-weight: 700;

                animation:
                    pop 0.6s ease;

            }}


            @keyframes pop {{

                0% {{
                    transform: scale(0.5);
                    opacity: 0;
                }}

                70% {{
                    transform: scale(1.08);
                }}

                100% {{
                    transform: scale(1);
                    opacity: 1;
                }}

            }}


            /* ==========================================
               LABEL
            ========================================== */

            .label {{

                display: inline-block;

                margin-bottom: 18px;

                padding: 8px 14px;

                border-radius: 50px;

                border:
                    1px solid
                    rgba(139, 92, 246, 0.30);

                background:
                    rgba(139, 92, 246, 0.08);

                color: #a78bfa;

                font-size: 9px;

                font-weight: 800;

                letter-spacing: 2px;

            }}


            /* ==========================================
               HEADING
            ========================================== */

            h1 {{

                margin-bottom: 15px;

                font-size:
                    clamp(36px, 6vw, 58px);

                line-height: 1;

                letter-spacing: -2px;

                font-weight: 900;

            }}


            h1 span {{

                background:
                    linear-gradient(
                        90deg,
                        #8b5cf6,
                        #06b6d4
                    );

                background-clip: text;

                -webkit-background-clip: text;

                color: transparent;

            }}


            /* ==========================================
               DESCRIPTION
            ========================================== */

            .description {{

                max-width: 500px;

                margin: 0 auto;

                color: #8995aa;

                font-size: 14px;

                line-height: 1.7;

            }}


            .event-name {{

                margin-top: 25px;

                padding: 18px 20px;

                border-radius: 14px;

                border:
                    1px solid
                    rgba(255,255,255,0.07);

                background:
                    rgba(255,255,255,0.025);

            }}


            .event-name small {{

                display: block;

                margin-bottom: 7px;

                color: #59667c;

                font-size: 8px;

                font-weight: 800;

                letter-spacing: 2px;

            }}


            .event-name strong {{

                color: #eef1f7;

                font-size: 17px;

            }}


            /* ==========================================
               STATUS
            ========================================== */

            .status {{

                display: flex;

                align-items: center;

                justify-content: center;

                gap: 9px;

                margin-top: 25px;

                color: #67e8f9;

                font-size: 11px;

                font-weight: 700;

                letter-spacing: 0.5px;

            }}


            .status-dot {{

                width: 8px;

                height: 8px;

                border-radius: 50%;

                background: #22d3ee;

                box-shadow:
                    0 0 12px
                    rgba(34,211,238,0.8);

            }}


            /* ==========================================
               BUTTONS
            ========================================== */

            .actions {{

                display: flex;

                justify-content: center;

                gap: 12px;

                margin-top: 35px;

                flex-wrap: wrap;

            }}


            .button {{

                display: inline-flex;

                align-items: center;

                justify-content: center;

                padding: 14px 24px;

                border-radius: 11px;

                text-decoration: none;

                font-size: 10px;

                font-weight: 900;

                letter-spacing: 1px;

                transition: 0.3s ease;

            }}


            .primary-button {{

                background:
                    linear-gradient(
                        135deg,
                        #7c3aed,
                        #06b6d4
                    );

                color: white;

                box-shadow:
                    0 12px 30px
                    rgba(124,58,237,0.22);

            }}


            .primary-button:hover {{

                transform: translateY(-3px);

                box-shadow:
                    0 18px 40px
                    rgba(124,58,237,0.35);

            }}


            .secondary-button {{

                border:
                    1px solid
                    rgba(255,255,255,0.10);

                background:
                    rgba(255,255,255,0.035);

                color: #b7c0d0;

            }}


            .secondary-button:hover {{

                border-color:
                    rgba(139,92,246,0.35);

                color: white;

                transform:
                    translateY(-3px);

            }}


            /* ==========================================
               FOOTER
            ========================================== */

            .footer-text {{

                margin-top: 35px;

                color: #4f5b70;

                font-size: 9px;

                letter-spacing: 1px;

            }}


            .footer-text span {{

                color: #8b5cf6;

            }}


            /* ==========================================
               MOBILE
            ========================================== */

            @media(max-width: 600px) {{

                body {{
                    padding: 18px;
                }}

                .success-card {{

                    padding: 40px 25px;

                    border-radius: 22px;

                }}

                .success-icon {{

                    width: 72px;

                    height: 72px;

                    font-size: 32px;

                }}

                h1 {{

                    font-size: 38px;

                }}

                .description {{

                    font-size: 13px;

                }}

                .actions {{

                    flex-direction: column;

                }}

                .button {{

                    width: 100%;

                }}

            }}

        </style>

    </head>


    <body>


        <div class="glow glow-one"></div>

        <div class="glow glow-two"></div>


        <div class="success-card">


            <div class="success-icon">
                ✓
            </div>


            <div class="label">
                RUBIX CLUB
            </div>


            <h1>
                Registration
                <span>Complete.</span>
            </h1>


            <p class="description">

                Your team registration has been
                successfully submitted.

                Get ready to compete, think and conquer.

            </p>


            <div class="event-name">

                <small>
                    REGISTERED FOR
                </small>

                <strong>
                    {event["title"]}
                </strong>

            </div>


            <div class="status">

                <span class="status-dot"></span>

                Registration successfully submitted

            </div>


            <div class="actions">

                <a
                    href="/events"
                    class="button secondary-button"
                >
                    ← BACK TO EVENTS
                </a>


                <a
                    href="/event/{event_id}"
                    class="button primary-button"
                >
                    VIEW EVENT →
                </a>

            </div>


            <div class="footer-text">

                <span>RUBIX</span>
                &nbsp;•&nbsp;
                THINK. SOLVE. CONQUER.

            </div>


        </div>


    </body>

    </html>
    """

# ==========================================================
# ADMIN LOGIN
# ==========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == ADMIN_USERNAME
            and
            password == ADMIN_PASSWORD
        ):

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin_dashboard")
            )

        flash(
            "Invalid username or password."
        )

    return render_template(
        "admin_login.html"
    )


# ==========================================================
# ADMIN LOGOUT
# ==========================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    cursor = mysql.connection.cursor()

    # ------------------------------------------------------
    # TOTAL EVENTS
    # ------------------------------------------------------

    cursor.execute(
        "SELECT COUNT(*) AS total FROM events"
    )

    total_events = cursor.fetchone()["total"]

    # ------------------------------------------------------
    # TOTAL REGISTRATIONS
    # ------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM event_registrations
    """)

    total_registrations = cursor.fetchone()["total"]

    # ------------------------------------------------------
    # ACTIVE / UPCOMING EVENTS
    # ------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM events
        WHERE status = 'upcoming'
           OR status = 'active'
    """)

    active_events = cursor.fetchone()["total"]

    # ------------------------------------------------------
    # RECENT EVENTS
    # ------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            title,
            event_date,
            venue,
            category,
            status
        FROM events
        ORDER BY id DESC
        LIMIT 5
    """)

    recent_events = cursor.fetchall()

    cursor.close()

    return render_template(
        "admin_dashboard.html",
        total_events=total_events,
        total_registrations=total_registrations,
        active_events=active_events,
        recent_events=recent_events
    )


# ==========================================================
# NEWS SYSTEM - PUBLIC + ADMIN
# ==========================================================

def ensure_news_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            summary VARCHAR(500) NOT NULL,
            content LONGTEXT NOT NULL,
            image VARCHAR(500) NULL,
            status ENUM('draft','published') NOT NULL DEFAULT 'draft',
            published_at DATETIME NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)


@app.route("/news")
def news():
    cursor = mysql.connection.cursor()
    ensure_news_table(cursor)
    cursor.execute("""
        SELECT id, title, summary, content, image, published_at, created_at
        FROM news WHERE status = 'published'
        ORDER BY COALESCE(published_at, created_at) DESC, id DESC
    """)
    articles = cursor.fetchall()
    cursor.close()
    return render_template("news.html", articles=articles)


@app.route("/news/<int:news_id>")
def news_details(news_id):
    cursor = mysql.connection.cursor()
    ensure_news_table(cursor)
    cursor.execute("""
        SELECT id, title, summary, content, image, published_at, created_at
        FROM news WHERE id = %s AND status = 'published'
    """, (news_id,))
    article = cursor.fetchone()
    cursor.close()
    if not article:
        return render_template("news_not_found.html"), 404
    return render_template("news_details.html", article=article)


@app.route("/admin/news")
def admin_news():
    if not admin_required():
        return redirect(url_for("admin_login"))
    cursor = mysql.connection.cursor()
    ensure_news_table(cursor)
    cursor.execute("""
        SELECT id, title, summary, status, created_at, published_at
        FROM news ORDER BY created_at DESC, id DESC
    """)
    articles = cursor.fetchall()
    cursor.close()
    return render_template("admin_news.html", articles=articles)


@app.route("/admin/news/add", methods=["GET", "POST"])
def admin_add_news():
    if not admin_required():
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        image = request.form.get("image", "").strip() or None
        status = request.form.get("status", "draft")
        if not title or not summary or not content or status not in ("draft", "published"):
            flash("Please complete all required fields.", "error")
            return render_template("admin_news_form.html", article=request.form, page_title="Add News")
        cursor = mysql.connection.cursor()
        ensure_news_table(cursor)
        cursor.execute("""
            INSERT INTO news (title, summary, content, image, status, published_at)
            VALUES (%s, %s, %s, %s, %s, CASE WHEN %s = 'published' THEN NOW() ELSE NULL END)
        """, (title, summary, content, image, status, status))
        mysql.connection.commit()
        cursor.close()
        flash("News article created.", "success")
        return redirect(url_for("admin_news"))
    return render_template("admin_news_form.html", article={}, page_title="Add News")


@app.route("/admin/news/<int:news_id>/edit", methods=["GET", "POST"])
def admin_edit_news(news_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    cursor = mysql.connection.cursor()
    ensure_news_table(cursor)
    cursor.execute("SELECT * FROM news WHERE id = %s", (news_id,))
    article = cursor.fetchone()
    if not article:
        cursor.close()
        flash("News article not found.", "error")
        return redirect(url_for("admin_news"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        image = request.form.get("image", "").strip() or None
        status = request.form.get("status", "draft")
        if not title or not summary or not content or status not in ("draft", "published"):
            cursor.close()
            flash("Please complete all required fields.", "error")
            return render_template("admin_news_form.html", article=request.form, page_title="Edit News")
        cursor.execute("""
            UPDATE news SET title=%s, summary=%s, content=%s, image=%s,
                status=%s,
                published_at=CASE WHEN %s='published' THEN COALESCE(published_at, NOW()) ELSE NULL END
            WHERE id=%s
        """, (title, summary, content, image, status, status, news_id))
        mysql.connection.commit()
        cursor.close()
        flash("News article updated.", "success")
        return redirect(url_for("admin_news"))
    cursor.close()
    return render_template("admin_news_form.html", article=article, page_title="Edit News")


@app.route("/admin/news/<int:news_id>/delete", methods=["POST"])
def admin_delete_news(news_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    cursor = mysql.connection.cursor()
    ensure_news_table(cursor)
    cursor.execute("DELETE FROM news WHERE id = %s", (news_id,))
    mysql.connection.commit()
    cursor.close()
    flash("News article deleted.", "success")
    return redirect(url_for("admin_news"))


@app.route("/admin/news/<int:news_id>/toggle", methods=["POST"])
def admin_toggle_news(news_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    cursor = mysql.connection.cursor()
    ensure_news_table(cursor)
    cursor.execute("""
        UPDATE news SET
            status = IF(status='published', 'draft', 'published'),
            published_at = IF(status='published', NULL, COALESCE(published_at, NOW()))
        WHERE id = %s
    """, (news_id,))
    mysql.connection.commit()
    cursor.close()
    flash("News publication status updated.", "success")
    return redirect(url_for("admin_news"))


# ==========================================================
# ADMIN GALLERY
# ==========================================================

@app.route(
    "/admin/gallery",
    methods=["GET", "POST"]
)
def admin_gallery():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    cursor = mysql.connection.cursor()

    # ------------------------------------------------------
    # CREATE GALLERY
    # ------------------------------------------------------

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        cover_image = request.form.get(
            "cover_image",
            ""
        ).strip()

        event_id = request.form.get(
            "event_id"
        )

        if not title:

            cursor.close()

            flash(
                "Gallery title is required.",
                "error"
            )

            return redirect(
                url_for("admin_gallery")
            )

        if not event_id:

            event_id = None

        cursor.execute("""
            INSERT INTO gallery
            (
                title,
                description,
                cover_image,
                event_id
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
        """, (
            title,
            description,
            cover_image,
            event_id
        ))

        mysql.connection.commit()

        cursor.close()

        flash(
            "Gallery created successfully!"
        )

        return redirect(
            url_for("admin_gallery")
        )

    # ------------------------------------------------------
    # GET GALLERIES
    # ------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            title,
            description,
            cover_image,
            event_id,
            created_at
        FROM gallery
        ORDER BY id DESC
    """)

    galleries = cursor.fetchall()

    # ------------------------------------------------------
    # GET EVENTS
    # ------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            title
        FROM events
        ORDER BY event_date DESC
    """)

    events_data = cursor.fetchall()

    # ------------------------------------------------------
    # GET GALLERY IMAGES
    # ------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            gallery_id,
            image,
            uploaded_at
        FROM gallery_images
        ORDER BY id DESC
    """)

    gallery_images = cursor.fetchall()

    cursor.close()

    return render_template(
        "admin_gallery.html",
        galleries=galleries,
        events=events_data,
        gallery_images=gallery_images
    )


# ==========================================================
# ADD IMAGE TO GALLERY
# ==========================================================

@app.route("/admin/gallery/<int:gallery_id>/image", methods=["POST"])
def admin_gallery_add_image(gallery_id):

    if not admin_required():
        return redirect(url_for("admin_login"))

    cursor = mysql.connection.cursor()

    # Check whether gallery exists
    cursor.execute(
        "SELECT id, title FROM gallery WHERE id = %s",
        (gallery_id,)
    )

    gallery = cursor.fetchone()

    if not gallery:
        cursor.close()
        flash("Gallery not found.", "error")
        return redirect(url_for("admin_gallery"))

    # Get uploaded file
    image_file = request.files.get("image")

    if not image_file or image_file.filename == "":
        cursor.close()
        flash("Please select an image to upload.", "error")
        return redirect(url_for("admin_gallery"))

    # Allowed image extensions
    allowed_extensions = {
        "png",
        "jpg",
        "jpeg",
        "webp",
        "gif"
    }

    filename = image_file.filename
    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in allowed_extensions:
        cursor.close()
        flash("Invalid image format.", "error")
        return redirect(url_for("admin_gallery"))

    # Create upload directory
    upload_folder = os.path.join(
        app.root_path,
        "static",
        "uploads",
        "gallery"
    )

    os.makedirs(upload_folder, exist_ok=True)

    # Create unique filename
    import uuid

    new_filename = (
        str(uuid.uuid4())
        + "."
        + extension
    )

    file_path = os.path.join(
        upload_folder,
        new_filename
    )

    # Save image
    image_file.save(file_path)

    # URL stored in database
    image_url = url_for(
        "static",
        filename=f"uploads/gallery/{new_filename}"
    )

    # Insert image into database
    cursor.execute(
        """
        INSERT INTO gallery_images
        (gallery_id, image)
        VALUES (%s, %s)
        """,
        (gallery_id, image_url)
    )

    mysql.connection.commit()
    cursor.close()

    flash("Image uploaded successfully.", "success")

    return redirect(url_for("admin_gallery"))
    # ==========================================================
# DELETE GALLERY IMAGE
# ==========================================================

@app.route(
    "/admin/gallery/image/delete/<int:image_id>",
    methods=["POST"]
)
def admin_delete_gallery_image(image_id):

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    cursor = mysql.connection.cursor()
    # ==========================================================
# DELETE ENTIRE GALLERY
# ==========================================================

@app.route(
    "/admin/gallery/delete/<int:gallery_id>",
    methods=["POST"]
)
def admin_delete_gallery(gallery_id):

    if not admin_required():
        return redirect(url_for("admin_login"))

    cursor = mysql.connection.cursor()

    # ------------------------------------------------------
    # GET ALL IMAGES BELONGING TO THIS GALLERY
    # ------------------------------------------------------

    cursor.execute("""
        SELECT image
        FROM gallery_images
        WHERE gallery_id = %s
    """, (gallery_id,))

    images = cursor.fetchall()

    # ------------------------------------------------------
    # DELETE IMAGE FILES FROM COMPUTER
    # ------------------------------------------------------

    for image in images:

        image_path = image["image"]

        if image_path.startswith("/static/"):

            file_path = os.path.join(
                app.root_path,
                image_path.lstrip("/")
            )

            if os.path.exists(file_path):
                os.remove(file_path)

    # ------------------------------------------------------
    # DELETE IMAGE RECORDS
    # ------------------------------------------------------

    cursor.execute("""
        DELETE FROM gallery_images
        WHERE gallery_id = %s
    """, (gallery_id,))

    # ------------------------------------------------------
    # DELETE GALLERY
    # ------------------------------------------------------

    cursor.execute("""
        DELETE FROM gallery
        WHERE id = %s
    """, (gallery_id,))

    mysql.connection.commit()

    cursor.close()

    flash("Gallery deleted successfully!")

    return redirect(
        url_for("admin_gallery")
    )


    # ------------------------------------------------------
    # GET IMAGE
    # ------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            image
        FROM gallery_images
        WHERE id = %s
    """, (image_id,))

    image = cursor.fetchone()

    if not image:

        cursor.close()

        flash(
            "Image not found.",
            "error"
        )

        return redirect(
            url_for("admin_gallery")
        )

    # ------------------------------------------------------
    # DELETE IMAGE FILE FROM COMPUTER
    # ------------------------------------------------------

    image_path = image["image"]

    if image_path.startswith("/static/"):

        file_path = os.path.join(
            app.root_path,
            image_path.lstrip("/")
        )

        if os.path.exists(file_path):

            os.remove(file_path)

    # ------------------------------------------------------
    # DELETE DATABASE RECORD
    # ------------------------------------------------------

    cursor.execute("""
        DELETE FROM gallery_images
        WHERE id = %s
    """, (image_id,))

    mysql.connection.commit()

    cursor.close()

    flash(
        "Image deleted successfully!"
    )

    return redirect(
        url_for("admin_gallery")
    )

    # ------------------------------------------------------
    # ALLOWED FILE TYPES
    # ------------------------------------------------------

    allowed_extensions = {
        "png",
        "jpg",
        "jpeg",
        "webp",
        "gif"
    }

    filename = secure_filename(
        image_file.filename
    )

    if "." not in filename:

        flash(
            "Invalid image file.",
            "error"
        )

        return redirect(
            url_for("admin_gallery")
        )

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()

    if extension not in allowed_extensions:

        flash(
            "Only PNG, JPG, JPEG, WEBP and GIF images are allowed.",
            "error"
        )

        return redirect(
            url_for("admin_gallery")
        )

    cursor = mysql.connection.cursor()

    # ------------------------------------------------------
    # CHECK GALLERY EXISTS
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT id
        FROM gallery
        WHERE id = %s
        """,
        (gallery_id,)
    )

    gallery = cursor.fetchone()

    if not gallery:

        cursor.close()

        flash(
            "Gallery not found.",
            "error"
        )

        return redirect(
            url_for("admin_gallery")
        )

    # ------------------------------------------------------
    # CREATE UPLOAD FOLDER
    # ------------------------------------------------------

    upload_folder = os.path.join(
        app.root_path,
        "static",
        "uploads",
        "gallery"
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    # ------------------------------------------------------
    # CREATE UNIQUE FILE NAME
    # ------------------------------------------------------

    unique_filename = (
        str(uuid.uuid4())
        + "."
        + extension
    )

    file_path = os.path.join(
        upload_folder,
        unique_filename
    )

    # ------------------------------------------------------
    # SAVE IMAGE
    # ------------------------------------------------------

    image_file.save(
        file_path
    )

    # ------------------------------------------------------
    # IMAGE URL
    # ------------------------------------------------------

    image_url = (
        "/static/uploads/gallery/"
        + unique_filename
    )

    # ------------------------------------------------------
    # SAVE IMAGE PATH IN DATABASE
    # ------------------------------------------------------

    cursor.execute("""
        INSERT INTO gallery_images
        (
            gallery_id,
            image
        )
        VALUES
        (
            %s,
            %s
        )
    """, (
        gallery_id,
        image_url
    ))

    mysql.connection.commit()

    cursor.close()

    flash(
        "Image uploaded successfully!"
    )

    return redirect(
        url_for("admin_gallery")
    )


# ==========================================================
# ADMIN EVENTS
# ==========================================================

@app.route("/admin/events")
def admin_events():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT
            id,
            title,
            event_date,
            event_time,
            venue,
            category,
            team_size,
            status
        FROM events
        ORDER BY id DESC
    """)

    events_data = cursor.fetchall()

    cursor.close()

    return render_template(
        "admin_events.html",
        events=events_data
    )


# ==========================================================
# ADD EVENT
# ==========================================================

@app.route(
    "/admin/events/add",
    methods=["GET", "POST"]
)
def admin_add_event():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        event_date = request.form.get(
            "event_date"
        )

        event_time = request.form.get(
            "event_time"
        )

        venue = request.form.get(
            "venue",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        team_size = request.form.get(
            "team_size",
            ""
        ).strip()

        image = request.form.get(
            "image",
            ""
        ).strip()

        team_size = request.form.get(
            "team_size",
            ""
        ).strip()

        max_teams = request.form.get(
            "max_teams",
            30
        )

        registration_link = request.form.get(
            "registration_link",
            ""
        ).strip()

        registration_qr = request.form.get(
            "registration_qr",
            ""
        ).strip()

        rules = request.form.get(
            "rules",
            ""
        ).strip()

        status = request.form.get(
            "status",
            "upcoming"
        )

        if not title:

            flash(
                "Event title is required."
            )

            return render_template(
                "admin_add_event.html"
            )

        cursor = mysql.connection.cursor()

        cursor.execute("""
            INSERT INTO events
            (
                title,
                description,
                event_date,
                event_time,
                venue,
                category,
                team_size,
                max_teams,
                image,
                registration_link,
                registration_qr,
                rules,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            title,
            description,
            event_date,
            event_time,
            venue,
            category,
            team_size,
            max_teams,
            image,
            registration_link,
            registration_qr,
            rules,
            status
        ))
        mysql.connection.commit()

        cursor.close()

        flash(
            "Event added successfully!"
        )

        return redirect(
            url_for("admin_events")
        )

    return render_template(
        "admin_add_event.html"
    )


# ==========================================================
# EDIT EVENT
# ==========================================================

@app.route(
    "/admin/events/edit/<int:event_id>",
    methods=["GET", "POST"]
)
def admin_edit_event(event_id):

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    cursor = mysql.connection.cursor()

    # ------------------------------------------------------
    # GET EXISTING EVENT
    # ------------------------------------------------------

    cursor.execute("""
        SELECT *
        FROM events
        WHERE id = %s
    """, (event_id,))

    event = cursor.fetchone()

    if not event:

        cursor.close()

        flash(
            "Event not found."
        )

        return redirect(
            url_for("admin_events")
        )

    # ------------------------------------------------------
    # UPDATE EVENT
    # ------------------------------------------------------

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        event_date = request.form.get(
            "event_date"
        )

        event_time = request.form.get(
            "event_time"
        )

        venue = request.form.get(
            "venue",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        team_size = request.form.get(
            "team_size",
            ""
        ).strip()

        image = request.form.get(
            "image",
            ""
        ).strip()

        registration_link = request.form.get(
            "registration_link",
            ""
        ).strip()

        registration_qr = request.form.get(
            "registration_qr",
            ""
        ).strip()

        rules = request.form.get(
            "rules",
            ""
        ).strip()

        status = request.form.get(
            "status",
            "upcoming"
        )

        if not title:

            flash(
                "Event title is required."
            )

            cursor.close()

            return render_template(
                "admin_edit_event.html",
                event=event
            )

        cursor.execute("""
            UPDATE events
            SET
                title = %s,
                description = %s,
                event_date = %s,
                event_time = %s,
                venue = %s,
                category = %s,
                team_size = %s,
                image = %s,
                registration_link = %s,
                registration_qr = %s,
                rules = %s,
                status = %s
            WHERE id = %s
        """, (
            title,
            description,
            event_date,
            event_time,
            venue,
            category,
            team_size,
            image,
            registration_link,
            registration_qr,
            rules,
            status,
            event_id
        ))

        mysql.connection.commit()

        cursor.close()

        flash(
            "Event updated successfully!"
        )

        return redirect(
            url_for("admin_events")
        )

    cursor.close()

    return render_template(
        "admin_edit_event.html",
        event=event
    )


# ==========================================================
# DELETE EVENT
# ==========================================================

@app.route(
    "/admin/events/delete/<int:event_id>",
    methods=["POST"]
)
def admin_delete_event(event_id):

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    cursor = mysql.connection.cursor()

    # ------------------------------------------------------
    # DELETE REGISTRATIONS FIRST
    # ------------------------------------------------------

    cursor.execute("""
        DELETE FROM event_registrations
        WHERE event_id = %s
    """, (event_id,))

    # ------------------------------------------------------
    # DELETE EVENT
    # ------------------------------------------------------

    cursor.execute("""
        DELETE FROM events
        WHERE id = %s
    """, (event_id,))

    mysql.connection.commit()

    cursor.close()

    flash(
        "Event deleted successfully!"
    )

    return redirect(
        url_for("admin_events")
    )


# ==========================================================
# DATABASE TEST
# ==========================================================

@app.route("/test-db")
def test_database():

    try:

        cursor = mysql.connection.cursor()

        cursor.execute(
            "SELECT DATABASE() AS database_name"
        )

        database = cursor.fetchone()

        cursor.execute(
            "SHOW TABLES"
        )

        tables = cursor.fetchall()

        cursor.close()

        return {
            "status": "success",
            "database": database,
            "tables": tables
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }



# ==========================================================
# RESULTS SYSTEM - PUBLIC + ADMIN
# ==========================================================

def ensure_results_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            event_name VARCHAR(200) NOT NULL,
            team_name VARCHAR(200) NOT NULL,
            position_name VARCHAR(100) NOT NULL,
            members TEXT,
            score VARCHAR(100),
            details TEXT,
            status ENUM('published','draft') NOT NULL DEFAULT 'published',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

@app.route('/results')
def results():
    cursor = mysql.connection.cursor()
    ensure_results_table(cursor)
    cursor.execute("SELECT * FROM results WHERE status='published' ORDER BY created_at DESC, id DESC")
    rows = cursor.fetchall()
    cursor.close()
    return render_template('results.html', results=rows)

@app.route('/admin/results')
def admin_results():
    if not admin_required():
        return redirect(url_for('admin_login'))
    cursor = mysql.connection.cursor()
    ensure_results_table(cursor)
    cursor.execute("SELECT * FROM results ORDER BY created_at DESC, id DESC")
    rows = cursor.fetchall()
    cursor.close()
    return render_template('admin_results.html', results=rows)

@app.route('/admin/results/add', methods=['GET','POST'])
def admin_add_result():
    if not admin_required():
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        event_name = request.form.get('event_name','').strip()
        team_name = request.form.get('team_name','').strip()
        position_name = request.form.get('position_name','').strip()
        if not all([event_name, team_name, position_name]):
            flash('Event, team name, and position are required.', 'error')
            return render_template('admin_result_form.html', item=request.form, page_title='Add Result')
        cursor = mysql.connection.cursor()
        ensure_results_table(cursor)
        cursor.execute("INSERT INTO results (event_name,team_name,position_name,members,score,details,status) VALUES (%s,%s,%s,%s,%s,%s,%s)", (
            event_name, team_name, position_name, request.form.get('members','').strip(), request.form.get('score','').strip(), request.form.get('details','').strip(), request.form.get('status','published') if request.form.get('status') in ('published','draft') else 'published'))
        mysql.connection.commit(); cursor.close()
        flash('Result added successfully.', 'success')
        return redirect(url_for('admin_results'))
    return render_template('admin_result_form.html', item={}, page_title='Add Result')

@app.route('/admin/results/<int:result_id>/edit', methods=['GET','POST'])
def admin_edit_result(result_id):
    if not admin_required():
        return redirect(url_for('admin_login'))
    cursor = mysql.connection.cursor(); ensure_results_table(cursor)
    cursor.execute('SELECT * FROM results WHERE id=%s', (result_id,)); item=cursor.fetchone()
    if not item:
        cursor.close(); flash('Result not found.', 'error'); return redirect(url_for('admin_results'))
    if request.method == 'POST':
        event_name=request.form.get('event_name','').strip(); team_name=request.form.get('team_name','').strip(); position_name=request.form.get('position_name','').strip()
        if not all([event_name,team_name,position_name]):
            cursor.close(); flash('Event, team name, and position are required.', 'error')
            return render_template('admin_result_form.html', item=request.form, page_title='Edit Result')
        status=request.form.get('status','published'); status=status if status in ('published','draft') else 'published'
        cursor.execute('UPDATE results SET event_name=%s,team_name=%s,position_name=%s,members=%s,score=%s,details=%s,status=%s WHERE id=%s', (event_name,team_name,position_name,request.form.get('members','').strip(),request.form.get('score','').strip(),request.form.get('details','').strip(),status,result_id))
        mysql.connection.commit(); cursor.close(); flash('Result updated.', 'success'); return redirect(url_for('admin_results'))
    cursor.close(); return render_template('admin_result_form.html', item=item, page_title='Edit Result')

@app.route('/admin/results/<int:result_id>/delete', methods=['POST'])
def admin_delete_result(result_id):
    if not admin_required(): return redirect(url_for('admin_login'))
    cursor=mysql.connection.cursor(); ensure_results_table(cursor); cursor.execute('DELETE FROM results WHERE id=%s',(result_id,)); mysql.connection.commit(); cursor.close()
    flash('Result deleted.', 'success'); return redirect(url_for('admin_results'))

# ==========================================================
# RESOURCES SYSTEM - PUBLIC + ADMIN
# ==========================================================

def ensure_resources_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            resource_url TEXT NOT NULL,
            status ENUM('published','draft') NOT NULL DEFAULT 'published',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

@app.route('/resources')
def resources():
    cursor=mysql.connection.cursor(); ensure_resources_table(cursor)
    cursor.execute("SELECT * FROM resources WHERE status='published' ORDER BY created_at DESC, id DESC")
    rows=cursor.fetchall(); cursor.close()
    return render_template('resources.html', resources=rows)

@app.route('/admin/resources')
def admin_resources():
    if not admin_required(): return redirect(url_for('admin_login'))
    cursor=mysql.connection.cursor(); ensure_resources_table(cursor)
    cursor.execute('SELECT * FROM resources ORDER BY created_at DESC, id DESC'); rows=cursor.fetchall(); cursor.close()
    return render_template('admin_resources.html', resources=rows)

@app.route('/admin/resources/add', methods=['GET','POST'])
def admin_add_resource():
    if not admin_required(): return redirect(url_for('admin_login'))
    if request.method=='POST':
        title=request.form.get('title','').strip(); resource_url=request.form.get('resource_url','').strip()
        if not title or not resource_url:
            flash('Resource title and URL are required.', 'error')
            return render_template('admin_resource_form.html', item=request.form, page_title='Add Resource')
        status=request.form.get('status','published'); status=status if status in ('published','draft') else 'published'
        cursor=mysql.connection.cursor(); ensure_resources_table(cursor)
        cursor.execute('INSERT INTO resources (title,description,category,resource_url,status) VALUES (%s,%s,%s,%s,%s)',(title,request.form.get('description','').strip(),request.form.get('category','').strip(),resource_url,status))
        mysql.connection.commit(); cursor.close(); flash('Resource added successfully.', 'success'); return redirect(url_for('admin_resources'))
    return render_template('admin_resource_form.html', item={}, page_title='Add Resource')

@app.route('/admin/resources/<int:resource_id>/edit', methods=['GET','POST'])
def admin_edit_resource(resource_id):
    if not admin_required(): return redirect(url_for('admin_login'))
    cursor=mysql.connection.cursor(); ensure_resources_table(cursor); cursor.execute('SELECT * FROM resources WHERE id=%s',(resource_id,)); item=cursor.fetchone()
    if not item:
        cursor.close(); flash('Resource not found.', 'error'); return redirect(url_for('admin_resources'))
    if request.method=='POST':
        title=request.form.get('title','').strip(); resource_url=request.form.get('resource_url','').strip()
        if not title or not resource_url:
            cursor.close(); flash('Resource title and URL are required.', 'error')
            return render_template('admin_resource_form.html', item=request.form, page_title='Edit Resource')
        status=request.form.get('status','published'); status=status if status in ('published','draft') else 'published'
        cursor.execute('UPDATE resources SET title=%s,description=%s,category=%s,resource_url=%s,status=%s WHERE id=%s',(title,request.form.get('description','').strip(),request.form.get('category','').strip(),resource_url,status,resource_id))
        mysql.connection.commit(); cursor.close(); flash('Resource updated.', 'success'); return redirect(url_for('admin_resources'))
    cursor.close(); return render_template('admin_resource_form.html', item=item, page_title='Edit Resource')

@app.route('/admin/resources/<int:resource_id>/delete', methods=['POST'])
def admin_delete_resource(resource_id):
    if not admin_required(): return redirect(url_for('admin_login'))
    cursor=mysql.connection.cursor(); ensure_resources_table(cursor); cursor.execute('DELETE FROM resources WHERE id=%s',(resource_id,)); mysql.connection.commit(); cursor.close()
    flash('Resource deleted.', 'success'); return redirect(url_for('admin_resources'))

# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )