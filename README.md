# Examination Management Portal (EMP)

## Project Overview
This is a role-based web application built for the AppDev1 final project. It allows an Administrator to manage courses and examinations, approved Examiners to schedule time slots, and Students to book those slots and view their final evaluated results.

## Tech Stack
*   **Backend:** Python 3, Flask
*   **Database:** SQLite (managed programmatically via Flask-SQLAlchemy)
*   **Frontend:** HTML5, Jinja2 Templating, Bootstrap 5 CSS
*   **Security:** Werkzeug Password Hashing, Server-Side Sessions, Custom RBAC Decorators

## How to Run the Project Locally
1. Clone the repository to your local machine.
2. Activate the virtual environment:
   * Windows: `venv\Scripts\activate`
   * Mac/Linux: `source venv/bin/activate`
3. Install the dependencies:
   `pip install -r requirements.txt`
4. Run the Flask server:
   `python app.py`
5. Open a web browser and navigate to `http://127.0.0.1:5000`.

## Default Credentials
The system automatically generates a default Admin account on the first run.
*   **Username:** admin
*   **Password:** admin123